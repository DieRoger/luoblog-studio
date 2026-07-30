---
title: "Review, Grounding, and Evidence: The Quality Assurance Stack"
description: "How the Review Agent, Grounding Checker, and Evidence Layer work together to ensure every AI-generated claim is verifiable."
date: 2026-07-31
tags: [AI, Agent, LLM, Evidence, Engineering, Evaluation]
categories: [AI Engineering, Architecture]
slug: review-grounding-evidence-stack
draft: false
author: Luo Runjie
readingTime: 12 min
difficulty: intermediate
---

# Review, Grounding, and Evidence: The Quality Assurance Stack

The Writing Agent generates articles. But generated content is worthless without quality control. Three modules form the quality assurance stack: the Review Agent scores articles, the Grounding Checker verifies claims, and the Evidence Layer stores the links between claims and sources.

## The Review Agent

The Review Agent evaluates articles across four dimensions with weighted scoring:

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Technical Accuracy | 35% | Are claims correct? Is the code valid? |
| Evidence Coverage | 30% | Is every claim backed by a source? |
| Writing Quality | 20% | Is the structure logical? Is it clear? |
| Originality | 15% | Is there real experience or just generic advice? |

The output is a structured report with scores, specific issues, and a summary. The system prompt (from `agents/prompts/review/system.md`) v2 includes brand standard checks — ensuring articles follow the "Building Reliable AI Systems" theme.

## The Grounding Checker

The Review Agent's Evidence Coverage score was always a guess — the LLM estimated whether claims seemed plausible. The Grounding Checker replaces estimation with measurement.

It extracts each substantive claim from an article, searches the Knowledge Hub via vector similarity, and flags claims below a 0.65 cosine similarity threshold as ungrounded. The results are injected into the Review Agent's prompt context:

```
Grounding Check Results:
- Total claims extracted: 12
- Verified (grounded in knowledge base): 8
- Unverified: 4
- Evidence coverage: 67%
```

This makes the Evidence Coverage score data-driven rather than opinion-based. Claims like "hybrid search outperforms pure vector search by 15%" that don't match any chunk are flagged automatically.

## The Evidence Layer

The Evidence Layer stores the persistent connection between claims and sources:

```
Article → Claim → Evidence → DocumentChunk → Document
```

When the Writing Agent generates content, the Evidence Service:
1. Runs the Grounding Checker on the article text
2. Saves each extracted claim as a `Claim` record linked to the article
3. For grounded claims, saves an `Evidence` record linking the claim to the matching Knowledge Hub chunk
4. Returns a GroundingReport showing which claims are verified

This is what makes LuoBlog different from a standard AI writing tool. Every claim in a generated article traces back to a source document and page. The source is either there or it isn't.
