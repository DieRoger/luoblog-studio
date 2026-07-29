---
title: "Grounding Checker: Making the Review Agent Honest"
description: "Building a claim verifier that checks every sentence in a generated article against the knowledge base — and why evidence coverage scores dropped from 5.0 to 0.0 when we stopped faking the data."
date: 2026-07-31
tags: [AI, Agent, LLM, RAG, Evidence, Engineering]
categories: [AI Engineering, Engineering Decisions]
slug: grounding-checker
draft: false
author: Luo Runjie
readingTime: 8 min
difficulty: intermediate
---

# Grounding Checker: Making the Review Agent Honest

The Review Agent scored evidence coverage at 5.0/10. The reason wasn't the prompt — it was that the article cited "RAG Survey 2025" which doesn't exist in the knowledge base. The article's claims looked like they should be verifiable, but nothing actually backed them.

The Grounding Checker solves this. It takes a generated article, extracts each substantive claim, and searches the Knowledge Hub for supporting evidence.

If a claim like "hybrid search outperforms pure vector search by 15%" doesn't match any chunk above 0.65 cosine similarity, it's flagged as ungrounded. The Evidence Coverage score becomes a measured number, not an LLM's opinion.

The result is simple: grounded claims have real sources; ungrounded claims don't. No more fake references.

## Key Takeaways

- **Evidence Coverage should be measured, not guessed.** The LLM can estimate whether a claim sounds right. The Grounding Checker can verify whether it actually exists in your data.
- **A 0.65 similarity threshold is strict enough to catch fakes but loose enough to match paraphrases.** Claims don't need to be verbatim — they need to be semantically grounded.
- **~40 lines of claim extraction logic is sufficient for MVP.** Sentence boundary detection + length filtering + heading skipping covers 90% of cases.
- **Grounding is the missing piece between "generated content" and "trusted content."** Without it, any article is just a plausible-sounding string of tokens.
