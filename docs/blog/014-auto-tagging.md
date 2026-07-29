---
title: "AI Auto-tagging: When the LLM Tags Your Documents for You"
description: "Using the same LLM that writes articles to generate technical tags for uploaded documents — and fixing a cross-test mock contamination issue in the process."
date: 2026-07-30
tags: [AI, LLM, Engineering, Python, Testing]
categories: [Build Log, Debug Diary]
slug: ai-auto-tagging
draft: false
author: Luo Runjie
readingTime: 6 min
difficulty: intermediate
---

# AI Auto-tagging: When the LLM Tags Your Documents for You

The PRD's Tag System supported manual tagging. AI auto-tagging generates tags automatically when a document is uploaded: the LLM reads the title and content excerpt, and returns a comma-separated list of relevant tags.

The implementation is straightforward — a single LLM call with a system prompt that constrains output to comma-separated tags.

The interesting engineering problem wasn't the auto-tagging itself, but the test infrastructure. `litellm` is imported inside the method body (lazy import to avoid hard dependencies). Tests mock it at module level using `sys.modules["litellm"]` — a shared mutable dictionary that every test file writes to.

When test file A sets `sys.modules["litellm"] = Mock(acompletion=AsyncMock())` and test file B sets `sys.modules["litellm"] = Mock(aembedding=AsyncMock())`, file B's mock overwrites file A's. The order depends on pytest's collection order (alphabetical). If A runs before B, A's tests pass, but if the collection order changes, they fail.

The fix was switching to `@patch("litellm.acompletion")` — which patches the attribute in-place rather than replacing the entire module reference. Each test gets its own clean mock. No cross-test contamination.
