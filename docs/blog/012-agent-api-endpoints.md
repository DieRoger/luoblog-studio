---
title: "Agent API Endpoints: Writing and Reviewing via HTTP"
description: "Exposing the Writing Agent and Review Agent as REST endpoints — 24 total API routes for the LuoBlog Studio MVP."
date: 2026-07-30
tags: [API, Agent, FastAPI, Engineering]
categories: [Build Log]
slug: agent-api-endpoints
draft: false
author: Luo Runjie
readingTime: 5 min
difficulty: beginner
---

# Agent API Endpoints: Writing and Reviewing via HTTP

The final piece of the MVP was exposing the agents via HTTP. Before this, the only way to generate an article was to import Python modules and call methods directly.

Two new endpoints:

- `POST /api/v1/agents/write` — takes `{"topic": "...", "max_sections": 5}`, returns title, summary, and sections with citations
- `POST /api/v1/agents/review` — takes `{"article": "..."}`, returns scores, issues, and summary

The Review Agent is automatically wired with the Grounding Checker — every review includes real evidence coverage data from the Knowledge Hub.

The full API surface is now 24 routes across 6 routers.
