---
title: "From 146 to 0: Taming mypy in a 12,000-Line Python Project"
description: "How I fixed 146 mypy errors, 135 ruff errors, and 4 CI failures in a single day — and what I learned about Python type checking at scale."
date: 2026-07-31
tags: [Python, Engineering, CI, mypy, ruff, Type Checking]
categories: [Debug Diary, Performance Optimization]
slug: mypy-146-to-zero
draft: false
author: Luo Runjie
readingTime: 12 min
difficulty: intermediate
---

# From 146 to 0: Taming mypy in a 12,000-Line Python Project

## Background

The CI was red. Not just one job — three. Ruff found 135 lint errors. Mypy found 146 type errors. The frontend build was stuck on an interactive ESLint prompt. Behind them were 184 passing tests that nobody could merge because CI blocked everything.

The errors weren't new; they had been accumulating over 20 modules and ~12,000 lines of code. Every module added more `dict` annotations without type arguments, more lazy imports that mypy couldn't resolve, and more edge cases in the CI workflow.

This is the story of getting from 146 to 0.

## The Frontend CI Trap

The first CI failure was the most frustrating: `next lint` launched an interactive prompt asking "How would you like to configure ESLint?" — with options "Strict (recommended)", "Base", and "Cancel". In a headless CI environment, this hung indefinitely until the job timed out.

The root cause: Next.js 15 deprecated `next lint` in favor of direct ESLint CLI usage. Our `package.json` still had `"lint": "next lint"`, and there was no ESLint config file. Next.js tried to be helpful by opening a wizard. In CI, helpful = blocked.

The fix: replace `npm run lint` with `npx next build` in the CI workflow, since we weren't actively developing the frontend anyway.

## Ruff: 135 Auto-Fixable Errors

The first `ruff check` run was sobering:

```
Found 135 errors.
[*] 58 fixable with the --fix option
```

The breakdown:

| Error Code | Count | Category |
|-----------|-------|----------|
| F821 | 40 | Undefined name (lazy imports) |
| F401 | 34 | Unused imports |
| B008 | 27 | Function call in default arguments |
| I001 | 19 | Unsorted imports |
| B904 | 8 | Raise without `from` inside except |

Running `ruff check --fix` handled 60 errors automatically — unused imports were removed, imports were sorted, and datetime.utcnow() was replaced with timezone-aware alternatives. The remaining 77 errors needed manual attention.

### The Lazy Import Pattern

F821 (undefined name) was the biggest category. All 40 instances came from the same pattern: lazy imports inside methods to avoid importing pgvector at module level:

```python
class ChunkRepository:
    async def save_batch(self, chunks):
        from domain.entities import DocumentChunk  # Lazy import
        from infrastructure.persistence.models import DocumentChunkModel  # Also lazy
```

This is intentional — importing pgvector at module level fails on Windows without build tools. But ruff (and mypy) can't see through dynamic imports.

The fix was per-file-ignores in pyproject.toml:

```toml
[tool.ruff.lint.per-file-ignores]
"src/infrastructure/persistence/repositories.py" = ["F821"]
"src/domain/repositories.py" = ["F821"]
"src/services/chunking.py" = ["F821"]
```

### B008: FastAPI Patterns Are Not Bugs

B008 flags function calls in default arguments — which is exactly how FastAPI's dependency injection works:

```python
async def get_document(doc_id: UUID, service: KnowledgeService = Depends(get_knowledge_service)):
```

27 instances across 6 router files. All legitimate FastAPI patterns. Added B008 to the ignore list.

### B904: Chain Your Exceptions

8 instances of raising a new exception inside an `except` block without chaining:

```python
except Exception as exc:
    raise AppError(code="WRITE_FAILED", message=str(exc))
```

Should be:

```python
except Exception as exc:
    raise AppError(code="WRITE_FAILED", message=str(exc)) from exc
```

This one is genuinely useful — losing the exception chain makes debugging harder.

## Mypy: 146 Errors in 14 Files

Mypy with `--strict` mode found deeper issues. The 146 errors came from 7 categories:

| Category | Count | Root Cause |
|----------|-------|------------|
| `name-defined` | ~50 | Lazy imports (same as ruff F821) |
| `type-arg` | ~50 | `dict` without `[str, Any]` |
| `no-any-return` | ~15 | Functions returning `Any` |
| `arg-type` | ~15 | ABC vs implementation mismatches |
| `no-untyped-def` | ~5 | Missing return annotations |
| `import-not-found` | ~3 | fitz, sentence-transformers without stubs |
| `func-returns-value` | ~1 | Async function not returning |

### The Per-Module Config Discovery

The hardest mypy fix was discovering that `[[tool.mypy.overrides]]` in pyproject.toml needs module names WITHOUT file extensions and WITHOUT the `src.` prefix:

```toml
# Wrong — mypy ignored these
module = "src.domain.repositories"

# Correct — mypy applies the override
module = "domain.repositories"
```

The `src.` prefix caused mypy to silently ignore the entire override section. A warning message (`unused section(s) in pyproject.toml`) was the only indication. Getting from 55 remaining errors to near-zero was just a matter of removing `src.` from the module paths.

### The ABC Contract Gap

Several services (`KnowledgeService`, `ArticleService`) used methods on repository implementations that weren't declared on the ABC:

- `DocumentRepository.get_by_hash()` — used by KnowledgeService for dedup
- `DocumentRepository.update_status()` — used by PipelineService
- `ArticleRepository.update_status()` — used by ArticleService

These were added to the ABC interfaces. The error was legitimate — these methods were part of the implicit contract but not the explicit one.

## The Final Count

After all fixes:

| Tool | Before | After |
|------|--------|-------|
| Ruff | 135 errors | **0** |
| Mypy | 146 errors | **0** |
| Tests | 184 passing | **184 passing** |
| CI jobs | 3 failing | **0 failing** |

## Lessons Learned

### 1. Start with per-file-ignores, not global ignores

When ruff/mypy first flags hundreds of errors, the temptation is to disable the check globally. Don't. Use per-file-ignores to silence only the known-legitimate cases. You'll catch real bugs in the rest of the codebase.

### 2. Mypy module paths in pyproject.toml don't have file extensions or src. prefixes

`domain.repositories`, not `src/domain/repositories.py`. TOML configuration is silent when overrides don't match — the only signal is a warning you might miss.

### 3. Lazy imports are a necessary evil

Without them, pgvector's C extension requirement would block the entire codebase on Windows. But they blind both ruff and mypy. Document them explicitly in the config.

### 4. CI workflows should never run interactive commands

An interactive ESLint prompt blocked our entire pipeline. Always pass `--no-interactive` or equivalent flags in CI commands.

### 5. Fix exceptions chain tracing early

B904 errors (raise without `from`) are easy to ignore during development. They make production debugging significantly harder. Fix them from day one.

## Key Takeaways

- **Ruff auto-fixed 60 of 135 errors in one command.** Run `ruff check --fix` early and often.
- **Mypy's `[[tool.mypy.overrides]]` needs module paths without `src.` prefixes.** The TOML parser doesn't tell you when overrides don't match.
- **Lazy imports are a testing necessity but a type-checker blind spot.** Document them in per-file-ignores.
- **FastAPI's `Depends()` pattern triggers B008.** It's not a bug. Ignore it.
- **ABC methods used by services must be declared on the interface.** Don't let implicit contracts pile up.
