---
title: "Citation System: APA and MLA Formatting"
description: "A 60-line formatter that turns Evidence records into properly formatted citations."
date: 2026-07-30
tags: [Python, Engineering, Evidence]
categories: [Build Log]
slug: citation-system
draft: false
author: Luo Runjie
readingTime: 3 min
difficulty: beginner
---

# Citation System: APA and MLA Formatting

The final piece of the Evidence Layer: a formatter that takes an `Evidence` record from the database and outputs a properly formatted citation string.

The API is a single function: `format_citation(evidence, style="apa")`. Two styles supported: APA and MLA. The formatter is extensible — adding a new style is a one-line registration in the `FORMATTERS` dict.

The formatter reads `source_location`, `metadata.title`, and `metadata.page` from the Evidence record. If metadata is missing, it falls back gracefully — `"Unknown"` for author, `"n.p."` for page number.

This completes the Claim → Evidence → Source → Citation chain that is the core differentiator of LuoBlog Studio.
