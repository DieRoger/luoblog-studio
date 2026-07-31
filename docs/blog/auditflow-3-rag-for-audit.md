---
title: "The RAG Pipeline AuditFlow Actually Runs: Paragraph Chunking, Local Embeddings, and What the Papers Say About Retrieval"
description: "Reading batch_index.py, chunking.py, and local_embedding.py against the retrieval literature — CRAG, Self-RAG, ColBERT, and RAPTOR — and what the code reveals that the docs don't."
date: 2026-07-31
tags: [RAG, Vector Database, Retrieval, Embedding, Engineering]
categories: [Architecture, Debug Diary]
slug: auditflow-rag-pipeline-real-code
draft: false
author: Luo Runjie
readingTime: 20 min
difficulty: advanced
---

# The RAG Pipeline AuditFlow Actually Runs: Paragraph Chunking, Local Embeddings, and What the Papers Say About Retrieval

## Background

AuditFlow ingests financial documents — annual reports, accounting standards, regulatory penalty notices — and turns them into searchable evidence for its agents. The previous version of this article described "hybrid search with RRF reranking" and "section-aware semantic chunking." Reading the actual pipeline code shows both descriptions were aspirational, not accurate.

This article is the correction, grounded in three real files:
- `backend/scripts/batch_index.py` — the indexing driver
- `backend/src/infrastructure/vector/chunking.py` — the chunking logic
- `backend/src/infrastructure/vector/local_embedding.py` — the embedding provider

And in the retrieval papers actually sitting in the knowledge base (CRAG, Self-RAG, ColBERT, RAPTOR), retrieved at measured similarity scores.

## Part 1: The Indexing Driver — What Actually Gets Ingested

`batch_index.py` has a hardcoded list of five target documents:

```python
TARGETS = [
    ("百利科技2025年报", "../datasets/百利科技：湖南百利工程科技股份有限公司2025年年度报告全文.pdf"),
    ("坛金矿业2026年报", "../datasets/坛金矿业：2026年年报.pdf"),
    ("CAS14 收入",       "../datasets/企业会计准则第14号——收入.pdf"),
    ("CAS8 资产减值",    "../datasets/企业会计准则第8号——资产减值.pdf"),
    ("证监会处罚决定",    "../datasets/ST百利：百利科技关于收到中国证监会湖南监管局《行政处罚决定书》的公告.pdf"),
]
```

Two real-world audit documents, two accounting standards, and one regulatory penalty notice. This is the actual corpus behind the Revenue Cutoff demo — not 67 PDFs as the handover doc claims. The pipeline loop:

```python
parser = PyMuPDFParser()
doc = await parser.parse(data, source_id)
texts = [(p.page_number, p.text) for p in doc.pages]
chunks = chunk_document(texts, source_id, max_tokens=500)

provider = LocalEmbeddingProvider()
vectors = await provider.embed([c.text for c in chunks])
```

The flow: parse → extract per-page text → chunk with a 500-token cap → embed locally → store. Each `EmbeddingItem` carries `source_type="CLIENT_DOCUMENT"` and metadata with page, source name, and filename — so retrieval results can be traced back to a document and page.

## Part 2: The Chunking — Paragraph-Based, Not Section-Aware

`chunking.py` is honest about its strategy in the docstring:

```python
"""Semantic Chunking — 文档切分为可检索的语义块
简单实现：按页 + 自然段落边界切分，保持语义完整性。
不引入 langchain 等重依赖。"""
```

"Simple implementation: split by page + natural paragraph boundaries. No heavy dependencies like langchain." The actual algorithm:

```python
def chunk_text(text, page_number, source_id, max_tokens=500, overlap_tokens=50):
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []
```

Split on `\n\n` (paragraph boundaries), then merge short paragraphs until approaching `max_tokens`, with `overlap_tokens=50` between adjacent chunks.

This is **not** section-aware chunking in the way my earlier article claimed. It doesn't detect headings, doesn't preserve section hierarchy, and doesn't attach section metadata. It's paragraph-based chunking with a token cap and overlap — a simpler, still reasonable approach.

### The token estimator is genuinely good

The most interesting detail is the CJK-aware token estimation:

```python
def estimate_tokens(text: str) -> int:
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    english_chars = char_count - chinese_chars
    return int(chinese_chars / 1.5 + english_chars / 4)
```

Chinese characters count at 1.5 chars/token; English at 4 chars/token, counted separately. This is the same CJK awareness that was a bug in my LuoBlog chunker (the English-only regex that broke on `。`), but here it's in the token estimator from the start. For a corpus that is majority Chinese financial documents, a naive `len(text)/4` estimator would undercount Chinese tokens by nearly 3x and silently blow the 500-token budget.

### The overlap is a deliberate retrieval decision

`overlap_tokens=50` means adjacent chunks share ~50 tokens of boundary text. The intent is retrieval continuity: a claim that straddles a chunk boundary is still fully present in at least one chunk. The cost is ~10% redundant storage. For audit documents where a sentence can span a page break, this is a defensible trade.

## Part 3: The Embedding — Local, 384-Dim, Zero API Cost

`local_embedding.py`:

```python
class LocalEmbeddingProvider(EmbeddingProvider):
    """基于 fastembed 的本地 Embedding
    使用 BAAI/bge-small-en-v1.5 模型（384维，~30MB ONNX 量化）。
    不依赖任何外部 API Key，完全本地运行，隐私安全。"""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self._model_name = model_name
        self._dim = 384
```

BGE-small-en-v1.5, 384 dimensions, ~30MB ONNX quantized, loaded via fastembed. The model loads lazily in a thread executor:

```python
async def _load_model(self):
    if self._model is not None:
        return
    loop = asyncio.get_event_loop()
    self._model = await loop.run_in_executor(None, self._load_sync)
```

Three properties worth noting:

1. **384 dimensions is small by design.** The corpus is dense, formal financial text — not open-domain web text. A small model with fast inference is the right trade when the domain vocabulary is narrow.
2. **ONNX quantized means no PyTorch.** This is the same choice my LuoBlog project made with fastembed — avoiding the torch dependency hell entirely.
3. **Local means privacy.** Financial documents are confidential; sending them to an embedding API is a non-starter. Local embedding is not a convenience here, it's a compliance requirement.

My earlier article said the embedding was BGE-small-**en**-v1.5 — that part was correct. What it got wrong was implying hybrid search with RRF was live. The pipeline code shows **pure vector search** — no keyword branch, no fusion. The `PGVectorStore` stores vectors and searches by cosine similarity; there's no BM25 component in the files I read.

## Part 4: What the Retrieval Papers Actually Say (Retrieved, Not Recalled)

The knowledge base has the retrieval papers. Measured retrieval results:

### CRAG (2401.15884, similarity 0.783)

The top hit for "retrieval augmented generation knowledge intensive" was CRAG's author line, and the second topic "corrective retrieval web search" returned the **"Retrieval Evaluator"** chunk. CRAG's core contribution is the retriever-evaluator: after initial retrieval, an evaluator scores retrieval quality and decides whether to correct (query decomposition + web search) or accept.

**What this means for AuditFlow**: AuditFlow has no retrieval evaluator. Its pipeline retrieves and moves on. CRAG suggests a cheap improvement: score each retrieval batch, and if the top-K similarity is below a floor, fall back to a corrective strategy (broader query, more documents). For audit — where missing evidence is as bad as wrong evidence — a "retrieval was weak" signal is valuable.

### Self-RAG (2310.11511, similarity 0.758)

The retrieved chunk is direct:

> "SELF-RAG learns to retrieve, critique, and generate text passages to enhance overall generation quality, factuality, and verifiability."

And it critiques the naive approach:

> "consistently retrieves a fixed number of documents for generation regardless of the retrieval necessity"

That last phrase is a direct critique of fixed-top-K retrieval — which is exactly what AuditFlow's pipeline does. Self-RAG's alternative: let the model decide *whether* retrieval is needed at all, and *critique* the retrieved passages (relevance, support, utility) before generating.

**What this means for AuditFlow**: the fixed top-K search has no "is retrieval even necessary" gate. For a planning agent deciding whether to retrieve more documents, Self-RAG's retrieval-necessity judgment would save tokens and improve precision.

### ColBERT (2004.12832, similarity 0.803)

> "ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT"

ColBERT's late interaction — token-level contextualized matching rather than a single vector dot product — is the strongest retrieval-quality upgrade in the knowledge base. Its cost is a larger index (per-token embeddings). For AuditFlow's ~3000 chunks, the index size is a non-issue; the quality gain would be real for the exact-phrase needs of standards citation (finding "per paragraph 17 of CAS 14" requires token-level match, not whole-chunk similarity).

### RAPTOR (2401.18059, similarity 0.810)

> "These methods offer unique ways of traversing the multi-layered RAPTOR tree to retrieve relevant information... Note that we embed all nodes using SBERT. The tree traversal method first selects the..."

RAPTOR builds a hierarchical tree of summaries — low-level chunks up to abstractive summaries at higher levels — and retrieves at multiple granularities. For audit documents where the same accounting standard is discussed at different levels of abstraction across documents, a RAPTOR-style hierarchy would let retrieval match at both the specific-rule level and the concept level.

## Part 5: The Gap Between the Pipeline and the Papers

Putting the code and the papers side by side:

| Pipeline reality | Paper that addresses it | Gap |
|-----------------|------------------------|-----|
| Fixed top-K vector search | Self-RAG (retrieval necessity) | No retrieval-necessity gate |
| No retrieval quality check | CRAG (retriever-evaluator) | No evaluation of retrieval before use |
| Single-vector similarity | ColBERT (late interaction) | No token-level matching |
| Flat chunk list | RAPTOR (hierarchical tree) | No multi-granularity retrieval |
| Paragraph-based chunking | — | Works, but no section hierarchy |

The honest conclusion: AuditFlow's RAG is a **solid baseline** — local, private, CJK-aware, paragraph-based with overlap — but it's single-vector, fixed-top-K, and unevaluated. Every paper in the knowledge base points at a specific upgrade, and none of them require abandoning the architecture.

## Part 6: What the Demo Numbers Reveal

The Revenue Cutoff demo's evidence graph result — `CUTOFF 50%, OCCURRENCE 33% → PARTIALLY SATISFIED` — is worth re-reading through the retrieval lens. An assertion is only as supported as the evidence retrieval found. If retrieval misses the invoice that proves cutoff compliance, the assertion is wrongly marked PARTIALLY_SATISFIED.

This is the deepest problem with unevaluated retrieval in an audit system: **you don't know what you didn't retrieve.** Precision@K tells you whether what you got was relevant; it says nothing about what you missed. Audit needs recall — missing evidence is a false negative with professional consequences. Self-RAG's critique and CRAG's evaluator are both, at bottom, attempts to surface "we might have missed something" as a first-class signal.

## Part 5: How Retrieval Results Are Actually Consumed — The Knowledge Agent

The Knowledge Agent (`agents/knowledge/agent.py`) is where retrieval results meet the LLM. Its docstring is honest about the design:

```python
"""LLM Knowledge Agent — 基于检索的审计准则分析
从 context.document_chunks 获取检索到的文档片段，基于真实内容回答。
无 chunks 时降级到 LLM 知识。"""
```

Two design decisions stand out:

### 1. Chunks carry page numbers into the prompt

```python
chunks_text = "\n\n---\n\n".join(
    f"[Page {c.get('page', '?')}] {c.get('content', '')[:800]}"
    for c in document_chunks
)
```

Each chunk is prefixed with `[Page N]`, and the system prompt instructs the model to cite page numbers:

> "Base your analysis on these excerpts. Cite the page number for each standard."

And the JSON schema includes `source_page`:

```python
{"standards": [{"standard": "...", "paragraph": "##", "content": "...", "interpretation": "...", "source_page": page_number}]}
```

This is the exact contrast with the Evidence Agent's hardcoded `document_id="evidence_source"`: the Knowledge Agent's citations carry a *page*, because the chunks were inserted with page metadata at indexing time (`metadata={"page": c.page_number}` in `batch_index.py`). The retrieval pipeline preserves page provenance end-to-end — from PDF page → chunk metadata → prompt → citation.

### 2. Fallback is explicit and separate

```python
if document_chunks and len(document_chunks) > 0:
    # 基于检索结果
    prompt = KNOWLEDGE_PROMPT.format(...)
else:
    # 降级到 LLM 知识
    prompt = KNOWLEDGE_FALLBACK_PROMPT.format(...)
```

When there are no chunks, the agent uses `KNOWLEDGE_FALLBACK_PROMPT` — a separate prompt that asks for `IFRS X.YY` style citations *without* `source_page`. The two prompts are structurally different: the retrieved path demands page numbers; the fallback path doesn't. This is a deliberate, visible degradation — the system knows it's answering from memory when it's answering from memory. It's not perfect grounding (the fallback can still hallucinate standards), but it's *honest* about the mode it's in.

There's also a subtle detail in the fallback prompt: it still asks for `"paragraph": "##"` and `"standard": "IFRS X.YY"`. So even in memory mode, the schema keeps a citation-shaped structure — the model is trained to produce *plausibly citable* output rather than free-form prose. Whether that's a feature (structured output, easy downstream consumption) or a risk (plausible-sounding standards that don't exist) depends on what consumes it. The Reviewer Agent is supposed to be that consumer — which makes the reviewer's ability to verify `IFRS X.YY` against a real source the actual safety boundary. If the reviewer can't look up the citation, the fallback path is a hallucination pipeline with a citation-shaped output format.

## Part 6: The Search Store — HNSW, Filters, and the Missing Hybrid

`pgvector_store.py`:

```python
class PGVectorStore(VectorStore):
    """基于 PGVector 的向量存储实现
    依赖：PostgreSQL + pgvector 扩展 + HNSW 索引"""
```

Three facts from the code:

1. **HNSW index, not IVFFlat.** The docstring declares HNSW — the graph-based index that trades build time for fast, high-recall search. For a few thousand chunks it's the right choice (IVFFlat needs training data and has recall cliffs at low lists counts).
2. **Search filters exist.** `search(query_vector, top_k, filters: SearchFilter | None)` — the store supports filtering by firm/client/engagement/source_type. This is the multi-tenant scaffolding showing up in a concrete place: retrieval can be scoped to a client's documents, which for audit is a hard requirement (you cannot retrieve Firm A's evidence while auditing Firm B).
3. **No hybrid branch.** The search method takes a single `query_vector` and returns vector similarity results. There's no keyword branch, no BM25 fusion, no RRF. My earlier "hybrid search with RRF" description was wrong — the store is pure vector search with filters.

### The insertion path is idempotent

```python
ON CONFLICT (id) DO NOTHING
```

Re-indexing the same chunk doesn't duplicate it — the idempotent upsert makes re-runs of `batch_index.py` safe. A small detail, but the kind that prevents "why do I have 6000 chunks for 5 documents?" incidents.

## Part 7: What the Papers Would Actually Change (Concretely)

Earlier I listed the papers at a high level. Let me be concrete about what each would change in this codebase:

### Self-RAG → add a retrieval-necessity gate

In `knowledge/agent.py`, before forcing retrieval, ask whether retrieval is needed:

```
if need_retrieval(audit_area, risk_context):   # LLM judgment or heuristic
    chunks = search(query_vector, top_k)
else:
    use fallback prompt
```

This saves tokens on well-known standards (an auditor knows CAS 14 exists) and forces retrieval on novel situations. Self-RAG's "retrieve only when necessary" maps directly onto the existing fallback path — the mechanism already exists.

### CRAG → add a retrieval evaluator

After `search()`, score the top-K similarity distribution:

```
scores = search(query_vector, top_k=10)
if max(scores) < 0.6:            # retrieval was weak
    fallback = broader_query(query_vector)
    chunks = merge(scores, fallback)
```

CRAG's "evaluate then correct" turns "retrieval returned garbage" from a silent failure into a handled case. For audit, a low-similarity retrieval should trigger a warning in the audit log, not silent acceptance.

### ColBERT → upgrade matching for exact citations

The `[Page N]` + "cite the paragraph" pattern needs exact-phrase matching ("paragraph 17 of CAS 14"). Single-vector cosine similarity finds *related* chunks; ColBERT's late interaction finds chunks containing the *specific* token sequence. For standards citation, the difference is material.

### RAPTOR → multi-granularity retrieval

Audit questions come at two levels: "what does CAS 14 say about revenue recognition" (specific rule) and "how does revenue recognition risk manifest" (concept). RAPTOR's hierarchy retrieves both. AuditFlow's flat chunk list retrieves only one level.

## Part 8: The Honest Assessment

What the code actually delivers:

| Claim (doc) | Reality (code) |
|-------------|---------------|
| 67 PDFs | 5 hardcoded documents |
| Hybrid search + RRF | Pure vector search + filters |
| Section-aware chunking | Paragraph-based + overlap |
| — | CJK-aware token estimation |
| — | Page-provenance end-to-end |
| — | Explicit retrieval-vs-fallback split |

The pipeline is a **coherent, honest baseline** — local, private, CJK-aware, page-provenant, filterable, idempotent. It's simpler than documented, but every simplification is defensible for a 5-document MVP. The gap to the literature is real and additive, not architectural.

## Lessons Learned

1. **The handover doc's "67 PDFs, hybrid search, RRF" was inaccurate.** The code shows 5 hardcoded documents, paragraph chunking, and pure vector search. Docs drift; code doesn't.
2. **CJK-aware token estimation is a real correctness feature, not a nicety.** Chinese at 1.5 chars/token vs English at 4 — a naive estimator would silently violate the 500-token budget on a Chinese corpus.
3. **Paragraph chunking with overlap is a reasonable baseline.** It's not section-aware, but for dense formal text it preserves sentence continuity across chunk boundaries at 10% storage cost.
4. **Local embeddings are a compliance requirement, not a cost optimization.** Financial documents can't leave the machine. 384-dim BGE-small via ONNX is the right trade.
5. **Page provenance is what makes citations trustworthy.** The `[Page N]` prefix survives the whole pipeline — index metadata → prompt → `source_page` in the JSON. This is the exact discipline the Evidence Agent's hardcoded `document_id` violates.
6. **Explicit fallback is better than silent degradation.** The Knowledge Agent has a visibly different prompt for "no chunks" mode, and it omits `source_page` when it can't be truthful about sources.
7. **Fixed top-K without retrieval evaluation is the biggest retrieval risk.** You can't cite what retrieval never found, and you can't know what it missed.
8. **Idempotent inserts are the difference between "safe to re-run" and "accidental data explosion."** `ON CONFLICT DO NOTHING` is one clause that prevents a whole class of indexing bugs.

## Key Takeaways

- **AuditFlow's real RAG is simpler than documented**: 5 documents, paragraph chunking, 384-dim local embeddings, pure vector search with filters. The "hybrid RRF" description was wrong.
- **CJK token estimation (1.5 vs 4 chars/token) is the quiet hero** of a Chinese financial corpus pipeline.
- **The overlap window (50 tokens) is a retrieval-continuity decision** worth the 10% storage cost for audit documents.
- **Page provenance end-to-end is the difference between a citation and a claim.** Knowledge Agent's `[Page N]` → `source_page` chain is the model to follow.
- **Retrieval without evaluation is dangerous in audit**: missing evidence is a professional false negative.
- **Self-RAG, CRAG, ColBERT, and RAPTOR each offer an additive upgrade** — necessity gate, retrieval evaluator, late interaction, and hierarchical retrieval — none requiring a rewrite.
- **Local-first embedding is non-negotiable for confidential financial data**, and 384-dim ONNX delivers it at zero API cost.
- **The explicit retrieval-vs-fallback split is honest engineering** — the system knows when it's answering from memory, and the output schema reflects it.

## Next Step

The next article examines the evaluation system — the four-layer metrics (retrieval, agent, grounding, workflow) — against the evaluation papers (AgentBench, SWE-bench, GAIA, LLM-as-a-Judge) in the knowledge base. The same discipline applies: I'll read the actual evaluation runner and benchmark scripts (`scripts/golden_eval.py`, `docs/evaluation/metrics.md`) before claiming anything about how evaluation works, and I'll retrieve the evaluation papers from the knowledge base at measured similarity scores rather than recalling them.

One point worth carrying forward from this article: the evaluation system's retrieval layer will inherit every limitation documented here — fixed top-K, no retrieval evaluator, no recall measurement. If AuditFlow measures Precision@K but not Recall@K, the F1 regression incident from the anomaly-detection work (64.6% → 25.4%) could repeat silently in the retrieval layer. The evaluation article should ask whether the four-layer system actually catches what this RAG pipeline structurally can't see: the evidence it failed to retrieve.
