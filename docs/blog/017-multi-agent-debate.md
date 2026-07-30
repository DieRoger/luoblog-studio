---
title: "Multi-Agent Debate: Three Perspectives, One Synthesis"
description: "Implementing a debate system where Researcher, Practitioner, and Critic agents argue a topic, then a Moderator produces a balanced synthesis."
date: 2026-07-30
tags: [AI, Agent, LLM, Multi-Agent, Debate, Engineering]
categories: [AI Engineering]
slug: multi-agent-debate
draft: false
author: Luo Runjie
readingTime: 5 min
difficulty: intermediate
---

# Multi-Agent Debate: Three Perspectives, One Synthesis

The final Agent module implements a debate pattern: spawn multiple agents with distinct personas, have each analyze the same topic independently, then synthesize their perspectives into a balanced output.

The three personas:

- **Researcher** — evidence-based, cites papers, cautious about claims
- **Practitioner** — experience-based, focuses on production trade-offs
- **Critic** — devil's advocate, identifies weaknesses and assumptions

Each persona has its own system prompt defining its role. They analyze the topic independently (no interaction between them — this is a "panel debate" not a "roundtable debate"). A Moderator system prompt then synthesizes all perspectives.

The implementation is 120 lines of service code plus an API endpoint at `POST /api/v1/agents/debate` that takes a topic and optional persona list.

This completes all 21 backend modules for LuoBlog Studio.
