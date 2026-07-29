---
title: "The Evidence Layer: Claim → Evidence → Source"
description: "Storing the connection between every AI-generated claim and the actual knowledge base chunk that supports it — the core differentiator of LuoBlog Studio."
date: 2026-07-31
tags: [Architecture, Evidence, RAG, Engineering, Python]
categories: [Engineering Decisions]
slug: evidence-layer-claim-source
draft: false
author: Luo Runjie
readingTime: 6 min
difficulty: intermediate
---

# The Evidence Layer: Claim → Evidence → Source

Every module so far has been infrastructure for this one. The Knowledge Hub stored chunks. The Writing Agent generated text. The Grounding Checker verified claims. The Evidence Layer stores the *connection* between them.

The data model is straightforward:

```
Article → Claim → Evidence → DocumentChunk → Document
```

When the Writing Agent generates a paragraph that says "RAG evaluation requires multi-dimensional metrics," the Evidence Layer:
1. Stores the claim text as a `Claim` record linked to the article
2. Stores the matching Knowledge Hub chunk as an `Evidence` record
3. Links them: `Claim ← Evidence → Chunk → Document`

This is what makes LuoBlog different from a standard AI writing tool. Every claim in a generated article can be traced back to the source document and page it came from. No more "the AI made it up" — the source is either there or it isn't.

The implementation was straightforward because the domain entities and database schemas were already created in Phase 0. The new code is the service layer that orchestrates the linking.
