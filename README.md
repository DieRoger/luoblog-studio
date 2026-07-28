# LuoBlog Studio

> A personal AI research operating system that transforms engineering experience
> into structured knowledge and technical publications.

**Phase 0 — Infrastructure Initialized**

## Overview

LuoBlog Studio is a personal AI Engineering Knowledge OS covering the full pipeline:
Research → Knowledge → Evidence → Writing → Publishing.

Every AI-generated claim is backed by an **Evidence → Source** traceable chain.

## Quick Start

### Prerequisites

- Docker Desktop
- Python 3.11+
- Node.js 22+

### 1. Clone & Setup

```bash
git clone <repo-url> luoblog-studio
cd luoblog-studio

# Create .env from template
cp .env.example .env
# Edit .env — add your LLM API keys
```

### 2. Start Services

```bash
# Start PostgreSQL + API
docker compose up -d

# Start frontend (separate terminal)
cd apps/web
npm install
npm run dev
```

### 3. Verify

- API: http://localhost:8000/docs
- Web: http://localhost:3000
- Health check: `curl http://localhost:8000/api/v1/health`

## Architecture

```
apps/web/         Next.js 15 frontend
apps/api/         FastAPI backend
agents/           LangGraph Agent definitions + prompts
database/         SQL schema + Alembic migrations
tests/            pytest + integration tests
docs/             PRD, ADRs, architecture docs
```

See [ARCHITECTURE.md](new/ARCHITECTURE.md) for the full architecture document.

## Commands

| Command | Directory | Purpose |
|---------|-----------|---------|
| `docker compose up -d` | root | Start PostgreSQL + API |
| `docker compose down -v` | root | Stop and remove volumes |
| `uvicorn src.main:create_app --factory --reload` | apps/api | Run API standalone |
| `pytest ../../tests/ -v` | apps/api | Run backend tests |
| `ruff check src/` | apps/api | Lint Python |
| `mypy src/` | apps/api | Type check |
| `npm run dev` | apps/web | Start Next.js dev server |
| `npm run build` | apps/web | Production build |
| `alembic revision --autogenerate -m "..."` | apps/api | Create migration |
| `alembic upgrade head` | apps/api | Apply migrations |

## Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 0 | Infrastructure & scaffolding | 🏗 In Progress |
| Phase 1 | Knowledge Hub (import, parse, search) | ⏳ Planned |
| Phase 2 | Agent Writing Engine | ⏳ Planned |
| Phase 3 | Integration & Polish | ⏳ Planned |

## License

MIT
