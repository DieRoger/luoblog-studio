---
title: "Docker, Grounding, and a Column Rename: The MVP Gets Production-Ready"
description: "Making the Review Agent honest with real evidence data, fixing a SQLAlchemy reserved-name collision, and running PostgreSQL for the first time."
date: 2026-07-30
tags: [Architecture, Engineering, Python, Docker, PostgreSQL, SQLAlchemy]
categories: [Build Log, Debug Diary]
slug: mvp-production-ready
draft: false
author: Luo Runjie
readingTime: 10 min
difficulty: intermediate
---

# Docker, Grounding, and a Column Rename: The MVP Gets Production-Ready

This week's work was less about new features and more about making existing features work correctly.

Three things happened:

1. The Review Agent learned to use the Grounding Checker
2. PostgreSQL started in Docker for the first time
3. A SQLAlchemy column name collision got fixed

## The Grounding Checker Integration

The Review Agent's Evidence Coverage score was always a guess. The LLM would read the article and estimate whether claims seemed supported. With the Grounding Checker, it doesn't have to guess anymore.

The integration is simple: pass a `GroundingChecker` to the `ReviewAgent` constructor. Before the LLM prompt is built, the checker runs against the Knowledge Hub. The results — total claims, grounded claims, ungrounded claims, and a list of unverifiable statements — are injected into the prompt context.

The LLM now sees:

```
Grounding Check Results:
- Total claims extracted: 12
- Verified (grounded in knowledge base): 8
- Unverified: 4
- Evidence coverage: 67%
- Unverified claims:
  * "hybrid search outperforms by 15%" (no source found)
```

This makes the Evidence Coverage score data-driven rather than opinion-based. If the Grounding Checker finds no evidence for a claim, the Review Agent will score accordingly regardless of how plausible the claim sounds.

## Docker

16 tables created, PGVector extension loaded, API starting with all 22 routes.

## A Column Name Collision

SQLAlchemy reserves `metadata` as a class attribute on its `Base` class. Three ORM models had a column named `metadata`. With the real pgvector package installed, SQLAlchemy validated the models and threw: `Attribute name 'metadata' is reserved`.

The fix was renaming the Python attribute to `meta` while keeping the database column name as `metadata` via explicit column naming.
