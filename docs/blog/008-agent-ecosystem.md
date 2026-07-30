---
title: "The Agent Ecosystem: API, Publishing, Auto-tagging, Citations, and Multi-Agent Debate"
description: "Five modules that extend the core agents into a complete publishing pipeline — API endpoints, GitHub sync, AI tagging, formatted citations, and multi-perspective debate."
date: 2026-07-31
tags: [API, GitHub, Agent, LLM, Engineering]
categories: [Build Log]
slug: agent-ecosystem
draft: false
author: Luo Runjie
readingTime: 8 min
difficulty: intermediate
---

# The Agent Ecosystem: API, Publishing, Auto-tagging, Citations, and Multi-Agent Debate

Five modules built around the core agents, each adding a specific capability to the publishing pipeline.

## Agent API Endpoints

Before this, the only way to generate an article was to import Python modules and call methods directly. Two endpoints exposed the agents via HTTP:

- `POST /api/v1/agents/write` — takes `{"topic": "...", "max_sections": 5}`, returns title, summary, and sections with citations
- `POST /api/v1/agents/review` — takes `{"article": "..."}`, returns scores, issues, and summary
- `POST /api/v1/agents/debate` — runs a multi-agent debate on a topic

The Review Agent is automatically wired with the Grounding Checker.

## GitHub Sync

A `POST /api/v1/publish/{article_id}` endpoint that takes a draft from the Article system, formats it as a Markdown file with YAML frontmatter (title, description, date, tags), and pushes it to any GitHub repository via the GitHub Contents API.

The target path is `content/posts/{slug}.md` — compatible with Hugo, Jekyll, and Next.js static sites. If the file already exists, it's updated. GitHub token and repo are configured via environment variables.

## AI Auto-tagging

When a document is uploaded, the LLM reads the title and content excerpt and returns a comma-separated list of relevant tags. The system prompt constrains output to technical terms (Python, RAG, Agent, Architecture, etc.), limited to 3-5 tags per document. Tags are automatically created and linked to the document.

## Citation System

A formatter that takes an `Evidence` record and outputs a properly formatted citation string. Supports APA and MLA styles. Extensible via a `FORMATTERS` dict — adding a new style is a one-line registration.

## Multi-Agent Debate

The final Agent module implements a debate pattern: spawn three agents with distinct personas, have each analyze the same topic independently, then synthesize their perspectives into a balanced output.

The three personas:
- **Researcher** — evidence-based, cites papers, cautious about claims
- **Practitioner** — experience-based, focuses on production trade-offs
- **Critic** — devil's advocate, identifies weaknesses and assumptions

A Moderator system prompt synthesizes all perspectives into a final analysis. This completes the agent ecosystem at 21 total backend modules.
