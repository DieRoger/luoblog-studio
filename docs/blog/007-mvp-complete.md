---
title: "Phase 1 Complete: MVP Done — 8 Modules, 127 Tests, 1 Pipeline"
description: "LuoBlog Studio's Phase 1 Knowledge Hub + AI Writing MVP is complete. Here's what was built, what went wrong, and what came next."
date: 2026-07-31
tags: [Architecture, Engineering, Python, FastAPI, AI, Agent]
categories: [Build Log, Project Diary]
slug: phase-1-mvp-complete
draft: false
author: Luo Runjie
readingTime: 15 min
difficulty: intermediate
---

# Phase 1 Complete: MVP Done — 8 Modules, 127 Tests, 1 Pipeline

## What Was Built

Eight modules over three weeks:

| # | Module | Lines | Tests |
|---|--------|-------|-------|
| 1 | Document Upload | 400 | 34 |
| 2 | PDF Parser | 200 | 15 |
| 3 | Chunking Service | 260 | 19 |
| 4 | Embedding Service | 380 | 14 |
| 5 | Knowledge Pipeline + Search | 250 | — |
| 6 | Tag System | 200 | 13 |
| 7 | Writing Agent | 300 | 14 |
| 8 | Review Agent | 200 | 12 |
|   | **Total** | **~2,200** | **127** |

All 127 tests pass in 1.7 seconds.

## API Surface

```
POST   /api/v1/documents/upload          — Upload a PDF/markdown/code file
GET    /api/v1/documents                  — List uploaded documents
GET    /api/v1/documents/{id}             — Get document details
DELETE /api/v1/documents/{id}             — Delete a document

POST   /api/v1/knowledge/process/{id}     — Parse → chunk → embed → index
GET    /api/v1/knowledge/search?q=...     — Hybrid search across all chunks

POST   /api/v1/tags                       — Create a tag
GET    /api/v1/tags                       — List all tags
POST   /api/v1/tags/link/{doc_id}         — Tag a document

POST   /api/v1/articles                   — Save a draft article
GET    /api/v1/articles/{id}              — Get draft
PUT    /api/v1/articles/{id}              — Update content/status
```

## Test Growth

```
Week 1:  34 tests   (Upload, Domain)
Week 2:  68 tests   (+ PDF Parser, Chunking)
Week 3:  95 tests   (+ Embedding, Tags, Pipeline)
Week 4: 127 tests   (+ Writing Agent, Review Agent, Articles)
```

## Key Statistics

- **8 Principal Engineer Reviews** — one per module
- **~20 bugs fixed** — found by reviews, not by tests
- **0 dependencies on pgvector/litellm in CI** — all mocked at module level
- **3 blog series articles** generated during development

## What I'd Do Differently

### Start Integration Tests Earlier

All 127 tests are unit tests with mocked infrastructure. Zero integration tests. The pipeline works in theory — upload a file, process it, search it — but I've never run it end-to-end without Docker. A single integration test that uploads a real PDF, parses it, searches it, and returns results would have caught pipeline-level wiring bugs that unit tests miss.

### Add a Review Checklist Before Phase 0

The Principal Engineer Review process was added after the first module was built. A pre-built checklist covering "test data diversity" would have caught the CJK bug in the Chunking Service before it shipped.

### Standardize the Mock Pattern Earlier

Three test files reinvented the same `sys.modules["litellm"]` mock pattern. A shared test helper module would have eliminated the bug where one test file's mock overwrote another's.

[goal:continue]
