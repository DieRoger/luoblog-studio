---
title: "The First Agent: How 14 Passing Tests Hid 7 Production Bugs"
description: "Building a Writing Agent for LuoBlog Studio — and how the Principal Engineer Review found serial LLM calls, missing system prompts, and fragile error handling in code that 'worked perfectly.'"
date: 2026-07-31
tags: [AI, Agent, LLM, Prompt Engineering, Engineering, Architecture, Python]
categories: [AI Engineering, Debug Diary]
slug: writing-agent-7-bugs
draft: false
author: Luo Runjie
readingTime: 18 min
difficulty: advanced
---

# The First Agent: How 14 Passing Tests Hid 7 Production Bugs

## Background

After building the Knowledge Hub — document upload, PDF parsing, chunking, embedding, and search — the next step was clear: build the first Agent that consumes that knowledge to produce something valuable.

The PRD defined the Writing Agent as a multi-step pipeline:

```
Topic → Outline Agent → Evidence Retrieval → Writer Agent → Citation Agent → Editor Agent → Markdown
```

For MVP, I simplified this into four steps:

```
Topic → Research (Knowledge Hub) → Outline (LLM) → Write (LLM) → Assemble (Citations)
```

The Agent takes a topic like "How to build a production RAG Agent," searches the knowledge base for relevant papers and code docs, generates an article outline, writes each section, and returns a Markdown draft with inline citations.

14 tests passed. The code compiled. The logic was straightforward. Time to ship.

## The Review That Found 7 Issues in 14 Passing Tests

The Principal Engineer Review scored this module **6/10** — the lowest of any module so far. It found 2 critical, 4 major, and 2 minor issues. Every test passed. None of these issues were caught by the test suite.

The review categories told the story:

| Category | Issues Found | Score |
|----------|-------------|-------|
| Architecture | Compliant | ✅ |
| Code Quality | Dead imports, unused params | ⚠️ |
| AI Reliability | No system prompt, no grounding check | ❌ |
| Production Readiness | Serial calls, no retry, no token tracking | ❌ |

Hidden bugs fall into patterns. Here are mine.

## Problem 1: Serial LLM Calls (C1)

The most obvious performance bug. The `_write_sections` method called the LLM once per section, sequentially:

```python
# BAD — 5 sections = 5 sequential API calls = ~15 seconds
async def _write_sections(self, topic, outline, context):
    sections = []
    for heading in outline.get("sections", []):
        raw = await self._call_llm(prompt)  # blocks for ~3s
        sections.append(...)
    return sections
```

Each LLM call takes 2-5 seconds. Five sections = 15-25 seconds of wall time. The user sees nothing for 20 seconds.

The fix was trivial — `asyncio.gather`:

```python
# GOOD — 5 sections in parallel = ~3 seconds
async def _write_sections(self, topic, outline, context):
    tasks = [
        self._write_single_section(topic, h, context)
        for h in outline.get("sections", [])
    ]
    return await asyncio.gather(*tasks)
```

This is the most obvious async optimization, and I missed it because I was thinking in terms of a "pipeline" (step 1 → step 2 → step 3) instead of "independent work items" (section A, section B, section C). The outline generation and section writing must be sequential. But each section is independent.

**Why the tests didn't catch it**: The tests mocked the LLM call to return instantly. `await asyncio.sleep(0)` in the mock meant the sequential vs parallel difference was invisible. Tests run in 0.3s either way.

## Problem 2: No Retry Logic (C2)

The `_call_llm` method had zero retry logic:

```python
# BAD — one failure = one exception
async def _call_llm(self, prompt: str) -> str:
    response = await litellm.acompletion(...)
    return response.choices[0].message.content or ""
```

LLM APIs have transient failures. Rate limits (429), service unavailability (503), and gateway timeouts (502) are routine, not exceptional. A single failure aborts the entire article generation.

The fix was three retries with exponential backoff:

```python
# GOOD — 3 retries, only for retryable errors
for attempt in range(MAX_RETRIES):
    try:
        response = await litellm.acompletion(...)
        return response.choices[0].message.content
    except Exception as exc:
        if not _is_retryable(exc) or attempt == MAX_RETRIES - 1:
            raise
        await asyncio.sleep(RETRY_BASE_DELAY * (2 ** attempt))
```

The `_is_retryable` function checks for rate limit, timeout, and 5xx errors. Authentication errors (401) and bad request errors (400) are NOT retryable — retrying them would waste time and money.

**Why the tests didn't catch it**: The test set `side_effect = ConnectionError` and expected an exception. With retries, the same test passes — it just takes 7 seconds longer (1 + 2 + 4 second delays). The test doesn't verify that retries happen correctly, just that the final exception is thrown.

## Problem 3: Missing System Prompt (M1)

The Writing Agent had a detailed system prompt in `agents/prompts/writing/system.md`:

```
## Writing Principles
1. **Experience first** — start from real engineering problems
2. **Evidence before conclusion** — every claim needs a source
3. **Architecture over marketing** — explain trade-offs, not just features
```

But the code never loaded it:

```python
# BAD — user message only, no system prompt
messages = [{"role": "user", "content": prompt}]
```

The LLM was generating content without knowing it should prioritize evidence over marketing, or start from real problems instead of generic introductions. The prompt file was there, but nothing connected it to the code.

The fix was adding a `_load_system_prompt` method that reads the file at init time:

```python
def _load_system_prompt(self) -> str:
    path = Path(__file__).parents[4] / "agents" / "prompts" / "writing" / "system.md"
    text = path.read_text()
    # Strip YAML frontmatter
    if text.startswith("---"):
        text = "---".join(text.split("---")[2:])
    return text.strip()
```

The path resolution `__file__.parents[4]` is fragile — it depends on the exact directory structure (`apps/api/src/services/../../../../agents/prompts/writing/system.md`). A better approach would be to make the prompt path configurable, but for MVP, the relative path with a fallback to a default prompt is acceptable.

**Why the tests didn't catch it**: The tests that called `_call_llm` directly passed any string through. They didn't check whether a system message was included. The only test that would catch this is an integration test with a real LLM — checking whether the output follows the writing principles.

## Problem 4: Unused Parameter and Dead Imports (M2, M3)

```python
def _extract_citations(context: str, heading: str) -> list[Citation]:
    # heading is NEVER used
```

And:

```python
from pathlib import Path  # never used in this file
from uuid import UUID     # never used in this file
```

These are small things, but they signal something important: **code that was designed but not implemented.** The `heading` parameter was meant to filter citations by section heading. It was added to the interface but never connected. The `Path` import was from a copy-paste. Both are dead weight that makes the code harder to read.

Dead code in a 250-line module might seem harmless, but it has a real cost: every reader spends mental energy figuring out why `heading` is passed but never used, or whether `Path` is used somewhere I missed.

## The Review Checklist That Caught These

The Principal Engineer Review used a structured checklist for every module. For the Writing Agent, the "AI Reliability" and "Production Readiness" sections flagged the most issues:

| Check | Pass? | Issue |
|-------|-------|-------|
| System prompt loaded from file? | ❌ | M1 |
| Temperature/config configurable? | ⚠️ | Hardcoded |
| Retry on transient failure? | ❌ | C2 |
| Token usage tracked? | ❌ | m2 |
| LLM calls parallelizable? | ❌ | C1 |
| Hallucination risk mitigated? | ❌ | Not yet |

If I had applied this checklist before writing code, I would have designed the retry logic and parallel execution from the start. Instead, I wrote the "happy path" first and had to retrofit reliability.

## Trade-offs

### Why not use LangGraph for this Agent?

The PRD specifies LangGraph for Agent orchestration. For the Writing Agent, I chose a simple async service instead. The reason: **the pipeline is linear.** Research → Outline → Write has no branching, no conditional edges, and no human-in-the-loop checkpoints. A LangGraph StateGraph would add ceremony without value:

```python
# LangGraph version: 90 lines for the graph definition alone
graph = StateGraph(AgentState)
graph.add_node("research", research_node)
graph.add_node("outline", outline_node)
graph.add_node("write", write_node)
graph.set_entry_point("research")
graph.add_edge("research", "outline")
graph.add_edge("outline", "write")
graph.add_edge("write", END)
```

vs:

```python
# Simple version: 10 lines
results = await self._research(topic, top_k)
outline = await self._generate_outline(topic, context, max_sections)
sections = await asyncio.gather(*[self._write_section(...) for h in headings])
return WritingResult(title=..., sections=sections)
```

LangGraph becomes valuable when you need branching (retry a section vs skip it), human checkpoints (review the outline before writing), or persistent state across failures. The Writing Agent MVP doesn't need any of these yet. When it does, the service can be migrated to a LangGraph graph without changing its public API.

### Why serial outline generation but parallel section writing?

The outline is a single JSON object that defines the article structure. You can't write section 2 without knowing section headings from the outline. These steps are inherently sequential.

Section writing is embarrassingly parallel. Each section has its heading, topic, and context. Section 1 doesn't depend on section 2. Using `asyncio.gather` reduces wall time from `O(n * t)` to `O(t)` where `n` is the number of sections and `t` is the per-section LLM latency.

### Retryable vs non-retryable errors

| Error | Retry? | Reason |
|-------|--------|--------|
| 429 Rate Limit | ✅ Yes | Resources will free up |
| 503 Service Unavailable | ✅ Yes | Server may recover |
| Connection timeout | ✅ Yes | Network may stabilize |
| 401 Authentication | ❌ No | Will fail every time |
| 400 Bad Request | ❌ No | Prompt or model is wrong |
| JSON parse failure (from LLM) | ❌ No | Same input → same failure |

The distinction matters because retrying a non-retryable error wastes time and tokens. If the API key is wrong, retrying 3 times with 7 seconds of delay won't fix it.

## Implementation Notes

The Writing Agent is 300 lines across two files:

```
domain/writing.py        — WritingResult, Section, Citation (30 lines)
services/writing.py      — WritingAgent (270 lines)
```

Key design decisions:

1. **`asyncio.gather` not `TaskGroup`** — `gather` returns results in order, which is essential for mapping section headings to content. `TaskGroup` (Python 3.11+) is better for fire-and-forget.

2. **System prompt parsed from YAML frontmatter** — the prompt file uses `---` delimiters for metadata. The loader strips the frontmatter and uses only the content section as the system message.

3. **Token cost tracking** — every LLM response logs `prompt_tokens` and `completion_tokens`. This data feeds into cost estimation and helps detect regressions (a section that suddenly uses 2x tokens may indicate a prompt issue).

4. **No streaming** — the current implementation waits for the complete response. For 4000-token sections, this means 3-5 seconds of silence. Streaming would deliver content progressively, but adds complexity to the Citation extraction (citations need the full context). Postponed to Phase 2.

## Evidence

### Test Suite

```
Module               Tests   Time  Status
Document Upload       34   0.44s  ✅
PDF Parser            15   0.37s  ✅
Chunking Service      19   0.10s  ✅
Embedding Service     14   0.37s  ✅
Tag System            13   0.16s  ✅
Writing Agent         14   0.38s  ✅
                    ─────  ─────
Total                109   1.53s  ✅
```

### Review Issues Before/After

| Issue | Before | After |
|-------|--------|-------|
| Section writing | Sequential, 5× ~3s = ~15s | Parallel, ~3s total |
| LLM failure | Single attempt → exception | 3 retries, exp. backoff |
| System prompt | Hardcoded inline | Loaded from file |
| max_tokens | Hardcoded 4096 | Configurable, default 8192 |
| Dead imports | `Path`, `UUID` unused | Cleaned |
| Unused param | `heading` passed but ignored | Removed |
| Token tracking | None | Logged per call |

## Lessons Learned

### 1. "All tests pass" and "production-ready" are different things

14 tests passed. The module had 7 issues, 2 critical. Tests verify behavior under ideal conditions (instant LLM, no rate limits). Reviews verify resilience under real conditions (latency, errors, missing files). **Both are necessary. Neither is sufficient.**

### 2. LLM calls need the same reliability patterns as database calls

Nobody writes database queries without connection pooling, retry logic, and timeout handling. Yet LLM calls routinely ship with zero error handling. The LLM is an external service with higher latency and lower reliability than a database. Treat it accordingly.

### 3. A system prompt in a file is not the same as a system prompt in a request

The prompt file existed. The code existed. There was nothing connecting them. If a file exists but is never loaded, it's documentation, not code. **The first implementation milestone for any Agent is "the prompt file is loaded and applied."**

### 4. Serial is the default, parallel is the optimization

The natural way to write code is sequential: step A, then step B, then step C. The natural way to write async code is also sequential, unless you explicitly think about parallelism. **Every `for` loop over an `await` call is a candidate for `gather`.**

## Future Improvements

1. **Streaming** — Deliver section content as it's generated, reducing perceived latency
2. **Review Agent** — Auto-score the generated draft for evidence coverage, technical accuracy, and originality
3. **Grounding checker** — Verify that every citation actually exists in the research context (reduce hallucination risk)
4. **LangGraph migration** — When branching or HITL checkpoints are needed

## Key Takeaways

- **A Principal Engineer Review with "AI Reliability" and "Production Readiness" sections found what unit tests missed.** The checklist matters more than the reviewer.
- **LLM calls are external service calls.** They need retries, timeouts, backpressure, and cost tracking — just like any database or API client.
- **`asyncio.gather` is free performance.** If you're awaiting N independent LLM calls in a loop, you're waiting N times longer than necessary.
- **A prompt file that isn't loaded is just a text file.** The first implementation step for any Agent is connecting the prompt to the code.

## Next Step

The next module is The Review Agent — an AI-powered critic that scores generated drafts for technical accuracy, evidence coverage, writing quality, and originality. This closes the loop: Write → Review → Revise.
