---
title: "Markdown Parser and Production Readiness: The Final Infrastructure Layer"
description: "Adding Markdown document support and making the system runnable with Docker + PostgreSQL."
date: 2026-07-31
tags: [Python, Docker, PostgreSQL, Engineering]
categories: [Build Log]
slug: markdown-docker-production
draft: false
author: Luo Runjie
readingTime: 5 min
difficulty: beginner
---

# Markdown Parser and Production Readiness: The Final Infrastructure Layer

## Markdown Parser

The Knowledge Hub already had a PDF parser. Adding a Markdown parser was straightforward — implement the same `DocumentParser` ABC that `PdfParser` already uses:

```python
class MarkdownParser(DocumentParser):
    def parse(self, file_path: str) -> ParsedDocument: ...
```

The implementation is ~100 lines. No AST library needed — Markdown structure is simple enough for line-by-line parsing with code fence awareness (` ``` ` and `~~~`). Supports ATX headings (# through ######) and skips headings inside code blocks.

The hardest bug was that empty sections between consecutive headings were silently discarded — a file with `# H1\n## H2\n### H3` produced zero sections because each heading replaces the previous one before any content accumulates.

## Docker + PGVector

The system runs on PostgreSQL 15 with PGVector extension. Docker Compose starts both services, creates 16 database tables from the schema, and loads the PGVector extension automatically.

Getting `pgvector` working on Windows required Docker — the C extension can't compile locally without PostgreSQL client libraries. The fix was a `sys.modules` mock in tests that isolates the pgvector dependency from the test suite, allowing 184 tests to run without Docker.

The `metadata` column name in three ORM models conflicted with SQLAlchemy's reserved `Base.metadata` attribute. Renaming the Python attribute to `meta` with an explicit column name `"metadata"` in `mapped_column()` resolved the conflict while keeping the database schema unchanged.
