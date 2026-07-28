---
title: "The Review Agent: Closing the Quality Loop"
description: "Building an AI-powered critic that scores technical articles across 4 dimensions — and why system vs user message roles matter more than I thought."
date: 2026-07-31
tags: [AI, Agent, LLM, Prompt Engineering, Engineering, Evaluation, Python]
categories: [AI Engineering, Engineering Decisions]
slug: review-agent-quality-loop
draft: false
author: Luo Runjie
readingTime: 12 min
difficulty: intermediate
---

# The Review Agent: Closing the Quality Loop

## Background

The Writing Agent generates articles. But generated content is worthless without quality control.

The PRD defined the Review Agent as the last step in the AI writing pipeline:

> Review Agent — AI 生成后质量检查: 技术准确性 / 逻辑完整性 / AI 味 / 工程真实性

The output is a structured report with scores from 0–10 across four dimensions:

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Technical Accuracy | 35% | Are claims correct? Is the code valid? |
| Evidence Coverage | 30% | Is every claim backed by a source? |
| Writing Quality | 20% | Is the structure logical? Is it clear? |
| Originality | 15% | Is there real experience or just generic advice? |

The weighted overall score creates a single number: `technical * 0.35 + evidence * 0.30 + writing * 0.20 + originality * 0.15`.

## Design

The Review Agent is simpler than the Writing Agent — one LLM call, not multiple:

```
Article → Build Prompt → Call LLM → Parse JSON → ReviewReport
```

The system prompt (from `agents/prompts/review/system.md`) defines the scoring criteria and JSON output format. The `_parse_report` method handles three response formats: plain JSON, JSON inside markdown code fences, and invalid/non-JSON (falls back to default 7.0 scores).

## The Bug That Shouldn't Have Happened

The first version of the Review Agent had this in `_call_llm`:

```python
messages=[{"role": "user", "content": prompt}]
```

Where `prompt` was:

```
Review the following technical article:
---ARTICLE START---
...article content...
---ARTICLE END---

(system prompt text here)
```

The system prompt was **appended to the user message**, not sent as a `system` role message. The LLM received the scoring criteria as "user input" rather than as authoritative instructions.

Why does this matter? LLMs treat `system` messages as higher-priority instructions than `user` messages. OpenAI's documentation states: "system messages set the behavior of the assistant." When the scoring criteria are mixed into the user message, the model may weigh them differently — or ignore them entirely if the article content is compelling.

The fix was a one-line change:

```python
messages=[
    {"role": "system", "content": self._system_prompt},
    {"role": "user", "content": article + instructions},
]
```

This is a fundamental LLM interaction pattern that I got wrong because I was thinking of the `_build_prompt` method as "gathering text" rather than "constructing a structured API call."

## Trade-offs

### Why not use the Writing Agent's system prompt format?

The Writing Agent loads its system prompt from `agents/prompts/writing/system.md` and uses it as a `system` message. The Review Agent should do the same — and now it does. The original inconsistency was an oversight, not a design decision.

### Single LLM call vs multi-step reasoning

A more thorough review could use chain-of-thought: first identify issues, then score each dimension, then suggest fixes. The single-call approach trades depth for speed (~3s vs ~15s). For MVP, speed wins — the user can always re-run if the review seems superficial.

### Defensive JSON parsing

LLMs occasionally return invalid JSON (truncated responses, extra text). The `_parse_report` method handles three failure modes:
1. Markdown code fences → strip and parse
2. Missing score keys → default 7.0
3. Totally invalid → fallback report with warning

This ensures the review never crashes, even if the LLM response is malformed.

## Lessons Learned

### 1. System vs user message roles are not cosmetic

Putting instructions in the wrong role changes how the model interprets them. System messages set behavior; user messages provide input. Mixing them is like putting configuration in the data layer.

### 2. A review agent without a Writing Agent is useless; a Writing Agent without a Review Agent is dangerous

The two agents form a closed loop: Write → Review → Revise. Without review, AI-generated content is a black box. Without writing, there's nothing to review. Both are needed for the system to be trustworthy.

### 3. Fallback scores are better than crashes

When the LLM returns garbage, `_parse_report` returns a default report with a warning issue. This means the user always gets something — and the warning tells them the review quality is degraded.

## Next Step

With the Writing Agent and Review Agent complete, the next milestone is connecting them into a full pipeline: Topic → Write → Review → Refine → Publish. This will be the first end-to-end AI writing workflow in LuoBlog Studio.
