<div align="center">

# LuoBlog Studio

**A personal AI Engineering Knowledge OS.**

Every AI-generated claim is backed by a traceable **Evidence → Source** chain.

[![CI](https://github.com/DieRoger/luoblog-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/DieRoger/luoblog-studio/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Tests](https://img.shields.io/badge/tests-184%20passing-green)
![Modules](https://img.shields.io/badge/modules-21-orange)
![License](https://img.shields.io/badge/license-MIT-blue)

</div>

---

## What It Is

LuoBlog Studio transforms engineering experience into structured knowledge and technical publications. Upload a research paper → it's parsed, chunked, embedded, and searchable. Pick a topic → an AI agent researches your knowledge base and writes a blog draft. The draft is automatically reviewed, claims are verified against sources, and everything is publishable to GitHub with one API call.

```
PDF Upload → Parse → Chunk → Embed → Search
                                           ↓
Topic → Writing Agent → Review Agent → Grounding Check → Publish
```

## What's Inside

**21 modules, 184 tests, ~12,000 lines of Python.**

| Layer | Modules |
|-------|---------|
| **Knowledge Hub** | Document Upload, PDF Parser, Markdown Parser, Chunking Service, Embedding Service, Hybrid Search, Tag System, Auto-tagging, Knowledge Graph |
| **AI Agents** | Writing Agent, Review Agent, Research Agent, Paper Agent, Knowledge Agent, Multi-Agent Debate, Grounding Checker |
| **Publishing** | Article Draft System, GitHub Sync, Citation Formatter (APA/MLA), Evidence Layer |
| **Infrastructure** | FastAPI, PostgreSQL + PGVector, Docker, LiteLLM, structlog, ruff + mypy — strict |

## Quick Start

```bash
# Start PostgreSQL + PGVector
docker compose up -d postgres

# Install + start API
cd apps/api
pip install -e ".[dev]"
uvicorn src.main:create_app --factory --reload

# API is live at http://localhost:8000/docs
```

```bash
# Upload a PDF
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@paper.pdf"

# Generate a blog post
curl -X POST http://localhost:8000/api/v1/agents/write \
  -H "Content-Type: application/json" \
  -d '{"topic": "RAG Evaluation Methods"}'

# Review the result
curl -X POST http://localhost:8000/api/v1/agents/review \
  -H "Content-Type: application/json" \
  -d '{"article": "# RAG Evaluation...全文..."}'
```

## Architecture

```
apps/web/         Next.js 15 frontend
apps/api/         FastAPI backend (21 modules, 184 tests)
agents/           Agent prompts + definitions
database/         PostgreSQL schema + PGVector (16 tables)
tests/            pytest unit tests (zero-infrastructure mocking)
docs/             ADRs, architecture, blog posts (10 articles)
```

Clean Architecture with strict dependency direction: **API → Service → Domain ← Infrastructure**.

## Test Suite

```
184 tests, all passing in ~3 seconds.
100% mocked — no PostgreSQL, no API keys, no network required.
```

| Area | Tests | What's tested |
|------|-------|---------------|
| Domain entities | 40+ | State machines, value objects, error handling |
| Storage | 34 | File upload, validation, path traversal, dedup |
| Parsers | 27 | PDF layout detection, Markdown section extraction |
| Chunking | 19 | Section splitting, CJK support, long content |
| Embedding | 14 | API mode, local mode, L2 normalization |
| Agents | 29 | Writing, Review, Research, Grounding, Paper |
| Everything else | 21 | Tags, Articles, Evidence, Citations, GitHub Sync |

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Vector search | **PGVector** (not LanceDB/FAISS) | Unified data stack, hybrid search in one SQL query |
| Agent framework | **LangGraph-ready** (not forced) | Writing agent uses async service; LangGraph for branching workflows |
| Embedding | **LiteLLM API + local BGE-m3** | API for convenience, local for privacy — switch via config |
| CI mocking | **`sys.modules` injection** | 184 tests run without pgvector, litellm, or any external service |
| Architecture | **Clean Architecture** | 23 domain modules with zero framework imports, fully testable |

## Project Status

**MVP complete.** 21 backend modules, 27 API endpoints, 6 AI agents, 184 tests.

Next: frontend UI, Knowledge Agent (automated), Paper Agent enhancements.

## License

MIT — build anything you want.
