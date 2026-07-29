# LuoBlog Studio — AI Coding Guidelines

This file instructs AI coding assistants how to work in this repository.

## Project Context

LuoBlog Studio is a personal AI Engineering Knowledge OS. It transforms technical
documents, code, and project experience into evidence-backed blog articles.

## Environment

| Tool | Path | Version |
|------|------|---------|
| Python | `E:\python\python.exe` | 3.11.5 |
| pip | `E:\python\python.exe -m pip` | — |

All Python commands in this project use `E:\python\python.exe`. Do NOT use the
system Python (3.7 in `.venv/`).

## Architecture Rules

### Clean Architecture (see ARCHITECTURE.md §3 and §7.2.1)

```
API Layer → Service Layer → Domain Layer ← Infrastructure Layer
```

Dependency direction: **outer layers depend on inner layers. Domain depends on nothing.**

- `domain/` — zero framework imports. No FastAPI, no SQLAlchemy, no LangChain.
- `services/` — depends on `domain/` interfaces, injected via DI (`api/dependencies.py`).
- `infrastructure/` — implements `domain/` interfaces (Repository pattern).

### When Adding Code

1. **New entity?** → Start in `domain/entities.py`. Define the dataclass + state transitions.
2. **New data access?** → Add an ABC in `domain/repositories.py`, implement in `infrastructure/persistence/`.
3. **New API endpoint?** → Create a router in `api/routers/`, register in `api/router.py`.
4. **New agent?** → Define a LangGraph StateGraph in `agents/<name>/`, prompt in `agents/prompts/<name>/`.

### What NOT To Do

- ❌ Don't create `utils.py`, `helpers.py`, or `common.py` dumpster files
- ❌ Don't import FastAPI/Starlette in `domain/` or `services/`
- ❌ Don't import SQLAlchemy models in `services/` — use repository interfaces
- ❌ Don't create abstractions for single-use code (YAGNI)
- ❌ Don't implement business logic in routers — routers delegate to services

## Code Standards

| Language | Tool | Config |
|----------|------|--------|
| Python | `ruff format` + `ruff check` | pyproject.toml |
| Python | `mypy --strict` | pyproject.toml |
| TypeScript | `prettier` + `eslint` | package.json |

### Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):
```
feat(api): add document upload endpoint
fix(web): correct dark mode flicker
refactor(domain): extract Score value object
chore: update dependencies
```

### Tests

- Unit tests for domain entities (state transitions, value objects)
- Integration tests for repositories (real PostgreSQL)
- API tests with `httpx.AsyncClient`
- Agent tests with mocked LLM responses

Run: `cd apps/api && pytest ../../tests/ -v`

## Key Files

| File | Purpose |
|------|---------|
| `ARCHITECTURE.md` | System architecture (read before major changes) |
| `docs/adr/` | Architecture Decision Records |
| `database/schema.sql` | Canonical DDL |
| `apps/api/src/domain/` | Core business objects |
| `apps/api/src/config.py` | All configuration via pydantic-settings |
| `.env.example` | Environment variable reference |

## Module Completion Workflow

Every completed module must generate a blog post. This is not optional.

### Step Sequence

```
1. Implement module (5-step: analyze → design → model → test → code)
2. Write tests (unit + failure + edge + performance)
3. Principal Engineer Review (architecture → code quality → AI reliability → production readiness)
4. Fix all Critical and Major issues
5. Run full test suite — must pass 100%
6. Write blog post → docs/blog/NNN-name.md
7. Commit + push to GitHub
```

### Blog Writing Rules

Use the same prompt structure every time (see `blog_rules.md` and `CONTENT_STRATEGY.md`):

- **Title**: Engineering-focused, specific to the module
- **Sections**: Background → Initial Design → Problems Encountered → Trade-offs → Final Design → Implementation Notes → Lessons Learned → Key Takeaways
- **Tone**: Professional, honest, evidence-driven. Write as an engineer documenting a real project, not a teacher or marketer.
- **Evidence**: Include test counts, before/after comparisons, architecture diagrams (Mermaid).
- **Code**: Show snippets only when they explain an important engineering decision. Never explain code line by line.
- **Length**: Medium article (2000-3500 words) or Deep dive (4000-7000 words).

### Blog Naming Convention

```
docs/blog/NNN-module-name.md
```

Where NNN is a 3-digit sequential number (001, 002, ...).
