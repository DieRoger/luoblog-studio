---
title: "Phase 1 Complete: The Knowledge Hub Is Searchable"
description: "Four modules, 82 tests, and one pipeline later — LuoBlog Studio can now import a PDF, parse it, chunk it, embed it, and return search results."
date: 2026-07-30
tags: [Architecture, Python, RAG, Engineering, Vector Database, FastAPI]
categories: [Build Log, Project Diary]
slug: phase-1-knowledge-hub-complete
draft: false
author: Luo Runjie
readingTime: 12 min
difficulty: intermediate
---

# Phase 1 Complete: The Knowledge Hub Is Searchable

## Background

Three weeks ago, I started building LuoBlog Studio — a personal AI Engineering Knowledge OS. The PRD defined Phase 1 as the **Knowledge Hub**: the infrastructure layer that transforms raw documents into searchable knowledge assets.

The pipeline in the PRD was a single arrow:

```
Raw Material → Document Intelligence → Structured Knowledge → Search + Evidence + Agent
```

Three weeks later, that arrow is a working API.

## What Was Built

The Knowledge Hub has four modules connected by a pipeline service:

```mermaid
graph LR
    UPLOAD["POST /documents/upload"] --> PROCESS["POST /knowledge/process/{id}"]
    PROCESS --> PARSE["PdfParser"]
    PARSE --> CHUNK["ChunkingService"]
    CHUNK --> EMBED["EmbeddingService"]
    EMBED --> STORE["PGVector<br/>document_chunks"]
    STORE --> SEARCH["GET /knowledge/search?q=..."]

    style UPLOAD fill:#2563EB,color:#fff
    style SEARCH fill:#16A34A,color:#fff
    style PROCESS fill:#7C3AED,color:#fff
```

### Module Checklist

| Module | Lines | Tests | Status |
|--------|-------|-------|--------|
| Document Upload | 400 | 34 | ✅ |
| PDF Parser (PyMuPDF) | 200 | 15 | ✅ |
| Chunking Service | 260 | 19 | ✅ |
| Embedding Service | 380 | 14 | ✅ |
| Pipeline + Search | 250 | — | ✅ |
| **Total** | **~1500** | **82** | **✅** |

### Key Metrics

- **82 tests, 1.06 seconds** — the entire test suite runs in about a second
- **4 Principal Engineer Reviews** — each module was reviewed before shipping
- **5 critical/major bugs fixed** — all caught by review, not by tests (path traversal, race condition, fake async, English-only regex, batch missing)

## The Three Reviews That Shaped the Code

Each module's Principal Engineer Review found real issues that changed the design:

### Document Upload: Security and Correctness

The first review found a path traversal vulnerability (upload to `../../../etc` with a crafted `doc_id`) and a race condition in deduplication (two concurrent uploads of the same file would create duplicate records). Both were fixed with database-level enforcement.

### PDF Parser: The Fake Async Trap

The parser was declared `async def` but was entirely synchronous underneath. PyMuPDF has no async API. The review flagged this as a violation of caller expectations — any service depending on this would think it could interleave parsing with other async work when it actually blocks the event loop. Fixed by making the interface synchronous and documenting that callers should use `run_in_executor` for concurrency.

### Chunking Service: The CJK Blind Spot

The sentence-splitting regex only handled English punctuation (`.!?`). Chinese documents using `。` were treated as one continuous paragraph, then hard-cut character-by-character. This was the most surprising bug — all 19 tests passed because all test data was English. Fixed by extending the regex to handle CJK punctuation and ideographs.

## Architecture Decisions That Held Up

### 1. Clean Architecture Paid Off in All Four Modules

The strict layering (API → Service → Domain ← Infrastructure) meant:

- **Domain entities have zero dependencies.** Document, DocumentChunk, ParsedSection, and their state machines are pure Python dataclasses. They can be tested in any Python environment.
- **Repository interfaces allowed swapping implementations.** The ChunkRepository ABC defined 5 methods. The PGVector implementation was written in one pass — the interface forced the right design.
- **Mock tests work without infrastructure.** All 82 tests run without PostgreSQL, without pgvector, without sentence-transformers, and without a network connection.

The cost is real: about 30% more files than a flat architecture. But every infrastructure swap or interface change has been a single-file edit.

### 2. The ABC + Two Implementations Pattern for Embedding

The EmbeddingService has two implementations (LiteLLM API and local BGE-m3). The ABC guarantees they share the same contract. The PipelineService depends on the ABC, not on either implementation. Switching between local and API mode is a one-line config change.

### 3. Graceful Degradation Over Hard Crashes

Three external dependencies would block development if required:

- `pgvector` — C extension, requires PostgreSQL client libraries
- `litellm` — requires network access to an LLM provider
- `sentence-transformers` — requires 2GB model weights

Each one is wrapped in a try/except that provides a clear error message instead of crashing. The test suite mocks all three at the module level using `sys.modules` injection, so CI doesn't need any of them.

## What Could Be Better

### ChunkRepository Depends on pgvector Model

The `ChunkRepository` implementation imports `DocumentChunkModel` which has a `Vector(1024)` column from `pgvector.sqlalchemy`. This means the repository can't be imported without pgvector installed. The fix (lazy imports inside methods and module-level mocking in tests) works but is fragile.

A better design would separate the vector column into a dedicated embedding table, making the chunk model pgvector-free. For MVP, the current approach is acceptable.

### Pipeline is Synchronous on CPU-bound Operations

The pipeline calls `parser.parse()` (CPU-bound, PDF layout analysis) in the async event loop. For a 100-page academic paper, this blocks the server for 2-5 seconds. The proper fix is to run the parser in a thread pool or subprocess, but that complicates error handling. For MVP with personal use, synchronous is acceptable.

### No Search Quality Evaluation

The hybrid search endpoint returns results, but I haven't measured retrieval quality. There's no benchmark dataset, no ground truth, no precision/recall numbers. The search "feels correct" on my test documents, but that's not engineering evidence. This is the next priority.

## What I'd Do Differently

### Add a Principal Engineer Review Checklist Earlier

The review process was added after the Document Upload module was built. By the time it caught the CJK bug in the Chunking Service, the code was already committed. If I had created a review checklist at Phase 0 — including a "test data diversity" check — the English-only regex would never have shipped.

### Write Integration Tests from Day One

The 82 unit tests are fast and reliable, but they don't verify that the pipeline actually works. A single integration test that uploads a real PDF, processes it, and searches it would catch pipeline-level bugs that unit tests miss. I deferred integration tests because pgvector isn't available on Windows, but a Docker-based CI step would have solved this.

## Evidence

### Test Suite Growth

```
Week 1:  34 tests (Document Upload + Domain)
Week 2:  49 tests (+ PDF Parser)
Week 3:  68 tests (+ Chunking Service)
Week 4:  82 tests (+ Embedding Service)
```

All 82 pass in 1.06 seconds on a single CPU core. The fastest-growing test category is "failure and edge cases" — 28 of 82 test invalid inputs, boundary conditions, or error paths.

### GitHub

The full project is at [github.com/DieRoger/luoblog-studio](https://github.com/DieRoger/luoblog-studio).

```
8ad5a83 — 80 commits, 73 files, ~6,400 lines
42 files in apps/api/, 3 test files, 0 infrastructure dependencies at module level
```

## Key Takeaways

- **A Principal Engineer review finds bugs that tests miss.** All 82 tests passed before the first review. The review found 5 bugs. Add reviews, not just tests.
- **"English-first" is a silent correctness bug.** Your text processing code works on English data. The moment a Chinese user uploads a PDF, it breaks. Add at least one non-Latin test case.
- **Async functions that aren't actually async are worse than sync functions.** They signal a contract they don't fulfill. Either make the function sync or wrap the blocking call.
- **82 tests running in 1 second is better than 200 tests running in 5 minutes.** Fast tests run more often. Keep your test suite fast by mocking infrastructure.
- **A pipeline that works end-to-end is more valuable than five modules that each work in isolation.** Integration tests catch bugs that unit tests miss. Ship the pipeline early, even if it's slow.

## Next Step

The next milestone is **Search Quality Evaluation**. I'll create a benchmark dataset of 20+ test queries with expected results, measure precision/recall for both vector and hybrid search, and establish a baseline before iterating on the retrieval pipeline. Without evaluation, the search endpoint is a black box.
