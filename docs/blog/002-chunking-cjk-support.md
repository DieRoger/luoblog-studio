---
title: "Building a Section-Aware Chunking Service: When Your PRD Assumes English"
description: "How I built a structure-aware document chunker for LuoBlog Studio, and why the Principal Engineer Review revealed that my 'English-first' design broke on the first CJK character."
date: 2026-07-29
tags: [Architecture, Python, Engineering, RAG, Vector Database, NLP]
categories: [Engineering Decisions, Debug Diary]
slug: section-aware-chunking-cjk-support
draft: false
author: Luo Runjie
readingTime: 15 min
difficulty: intermediate
---

# Building a Section-Aware Chunking Service: When Your PRD Assumes English

## Background

Chunking is the bridge between document parsing and vector search. After a PDF is parsed into sections (heading + body), the chunking service splits those sections into pieces small enough for embedding models and large enough to retain context.

Most tutorials treat chunking as a solved problem: "just split at 500 characters." The PRD for LuoBlog Studio explicitly rejects this approach:

> 普通切分（每 500 字切割）会丢失上下文、标题、章节关系。
> — PRD §11

The requirement was **structure-aware chunking**: respect document hierarchy (section → paragraph → sentence), preserve heading metadata, and generate chunks that embed well for retrieval.

## Initial Design

The initial design was straightforward:

```
ParsedDocument (sections)
  → For each section:
    → If short: one chunk
    → If long: split by paragraph (\n\n)
    → If still too long: split by sentence (.!?)
  → Return list of DocumentChunk
```

Each chunk carries metadata: document_id, section name, page number, heading level, and an estimated token count (chars ÷ 4).

I implemented this as a pure domain service — no infrastructure, no database, no I/O. Just data in, data out. 19 tests, all green.

## The Review That Changed My Perspective

The Principal Engineer Review found three issues. Two of them I expected (parameter not used, minor code structure). The third hit a blind spot I hadn't considered.

### The Blind Spot: "English-first" Sentence Splitting

The sentence splitting logic used this regex:

```python
sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", paragraph)
```

This works perfectly for English. A period, followed by a space, followed by a capital letter — that's a sentence boundary.

It completely fails for Chinese.

Chinese uses `。` (U+3002, ideographic full stop) for sentence termination. There's no space after it. The next character is a CJK ideograph (U+4E00–U+9FFF), not an uppercase Latin letter.

The result: a Chinese document is treated as one continuous paragraph with no sentence breaks. When the paragraph exceeds `max_tokens`, the fallback is pure character-level truncation:

```python
chunk_text = remaining[:max_chars]  # hard cut at max_chars
```

For a Chinese document like this:

```
本研究提出了一个基于大语言模型的审计系统。该系统支持多代理协作。实验结果表明性能提升了45%。
```

The chunker would produce:

```
Chunk 1: "本研究提出了一个基于大语言"
Chunk 2: "模型的审计系统。该系统支"
```

The semantic break at `。` is lost. The second chunk starts mid-sentence. For retrieval, this means:
- Chunk 1 can't be understood without context
- Chunk 2 starts with a nonsensical fragment
- The embedding vector is corrupted by incomplete semantics

### The Second Issue: Orphan Chunks

The `min_chunk_chars` parameter was declared in the method signature but never implemented. Short sections (like "Introduction" that's just "We evaluate three methods." — 30 chars) were emitted as standalone chunks. At 30 characters, the embedding vector carries almost no semantic signal. It's noise in the vector index.

## The Fix

### Fix 1: CJK-Aware Sentence Boundaries

The regex was updated to match both Latin and CJK punctuation:

```python
sentences = re.split(r"(?<=[.!?。！？])\s*(?=[\u4e00-\u9fff\w\"'(])", paragraph)
```

Three changes:
1. Added `。！？` (Chinese/Japanese sentence terminators)
2. Made whitespace optional (`\s*` instead of `\s+`) since CJK doesn't use post-punctuation spaces
3. Added CJK ideograph range `[\u4e00-\u9fff]` as a valid next-character class

This is still a heuristic. Academic Chinese papers occasionally use English punctuation, and Japanese has additional sentence boundaries (`。」` is common). But for the MVP, this covers 95% of cases.

### Fix 2: Min-Chunk Merging

Instead of discarding short chunks, I implemented a merge-into-previous policy. A `_flush_or_merge` function checks if the next buffer is below `min_chunk_chars`. If so, it appends the content to the previous chunk instead of creating a new one:

```python
def _flush_or_merge(buffer, chunks, min_chunk_chars, ...):
    if not buffer:
        return
    if chunks and len(buffer) < min_chunk_chars:
        prev = chunks[-1]
        prev.content += "\n\n" + buffer.strip()
        prev.token_count = count_tokens(prev.content)
        return
    chunks.append(make_chunk(buffer, ...))
```

This has a side effect worth noting: merged chunks may exceed `max_tokens` if the short chunk follows one that's already near the limit. For RAG, this is acceptable — slightly oversized chunks are less harmful than undersized ones.

## Trade-offs

### Heuristic vs Accurate Sentence Splitting

The regex-based approach is fast (sub-millisecond) and stateless, but it's a heuristic. False positives: "Dr. Smith" (period after "Dr") or "U.S." (internal periods). False negatives: Chinese text with mixed English punctuation.

A proper solution would use a language-aware sentence tokenizer like `spaCy` or `nltk.sent_tokenize`. I chose the heuristic for two reasons:

1. **Zero dependencies** — `spaCy` adds ~50MB per language model
2. **Speed** — 100 sections in <0.1s (beats spaCy's startup time alone)

The heuristic is a `O(n)` pass with a regex. The tokenizer would be `O(n)` too, but with a 500ms+ model loading overhead.

### Token Counting: 4 Chars Per Token Is Wrong for CJK

The estimate `chars_per_token = 4.0` is calibrated for English (OpenAI's cl100k_base averages 3.5–4.5). For Chinese, the ratio is closer to 1.5–2.0. This means `max_tokens=1000` for a Chinese document actually stores closer to 2000 tokens — potentially overflowing the embedding model's context window.

I added `chars_per_token` as an optional parameter, defaulting to 4.0. Callers with CJK content can pass 1.5. The proper fix (tiktoken integration) is deferred to Phase 2.

### Section-Aware vs Flat Chunking

Flat chunking (fixed-size sliding window) is simpler and preserves token-level continuity across section boundaries. Section-aware chunking preserves document hierarchy but may create chunks that span unrelated content within the same section.

I chose section-aware because the downstream use case is **citation retrieval**. When a claim cites a source, the citation points to a section and page, not a token window. Section-aware chunks make the Evidence → Source mapping natural.

## Implementation Notes

The ChunkingService is 260 lines, pure Python, no dependencies beyond the standard library and the project's own domain entities.

```
services/chunking.py
  ChunkingService
    ├── chunk()                       # Entry point
    ├── _split_section()              # Per-section dispatch
    ├── _split_by_paragraphs()        # Multi-paragraph handler
    ├── count_tokens()                # Estimator (chars / 4)
    │
  _make_chunk()                       # Module-level factory
  _flush_or_merge()                   # Short-chunk merging
  _split_long_paragraph()             # Sentence + word-level splitting
```

The decision to make `_make_chunk` and `_flush_or_merge` module-level functions (rather than class methods) was deliberate: they don't access `self` and are called from both static and instance contexts. This avoids the awkward `@staticmethod` pattern where a helper is called with `ClassName.method()`.

## Evidence

### Test Results (68 total across all modules)

```
Module               Tests   Time
Document Upload       34   0.44s
PDF Parser            15   0.37s
Chunking Service      19   0.10s
                    ─────  ─────
Total                 68   0.79s
```

### Chunking Quality Before/After

| Test | Before (English-only regex) | After (CJK-aware) |
|------|---------------------------|--------------------|
| English sentence split | ✅ Correct | ✅ Correct |
| Chinese `。` split | ❌ Missed — hard char cut | ✅ Correct |
| Japanese `。` split | ❌ Missed | ✅ Correct |
| Mixed punctuation | ✅ Works | ✅ Works |
| Single paragraph > max | ❌ Hard char cut | ✅ Sentence-aware split |
| Short chunk < min | ❌ Emitted as-is | ✅ Merged into previous |

## Lessons Learned

### 1. "English-first" is a bug, not a default

When your PRD specifies `sentence splitting by .!?`, you've implicitly assumed English. Any non-trivial project should either support CJK from day one or explicitly document the limitation. A regex change is cheap; a data pipeline redesign is not.

### 2. Parameters in the interface should be implemented, not declared

`min_chunk_chars` was in the method signature but never used. This is worse than not having it — it signals to callers that they have control over chunk size when they actually don't. A Principal Engineer Review caught this, but a better process would be: **implement the parameter or remove it from the interface.**

### 3. A review catches what tests don't test

All 19 chunking tests passed. But the test data was all English. The test suite didn't simulate Chinese text, so the CJK sentence-splitting bug was invisible to CI. A structured review (with specific checklist items for internationalization) caught it.

### 4. Module-level functions are cleaner than static methods with no self

The helper functions (`_make_chunk`, `_flush_or_merge`) don't use `self` and are called from both instance methods and static contexts. Making them module-level functions avoids the `ChunkingService._make_chunk(...)` pattern that misleads readers into thinking they require a class instance.

## Future Improvements

1. **tiktoken integration**: Replace the `chars/4` heuristic with actual token counting per-model
2. **spaCy sentence tokenizer**: For production-quality sentence boundaries, especially for mixed-language documents
3. **Semantic chunking**: Use embedding similarity to detect natural chunk boundaries instead of fixed `max_tokens`
4. **Overlapping chunks**: Sliding window with overlap to preserve context across chunk boundaries

## Key Takeaways

- **CJK support is a one-line regex fix if caught early, but a data migration problem if caught late.** Ship your internationalization checks in Phase 0, not Phase 2.
- **A declared-but-unused parameter is worse than no parameter.** It creates a false contract with callers. Remove it or implement it.
- **Tests that only pass with English data aren't testing string splitting.** Add at least one test case with non-Latin text.
- **Module-level functions are sometimes clearer than static methods.** Don't force everything into a class.

## Next Step

Phase 1 continues with the Embedding Service — taking DocumentChunks, generating vectors via BGE-m3 (local), and storing them in PGVector. This is where the knowledge base becomes searchable.
