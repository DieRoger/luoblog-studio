---
title: "Markdown Parser: The 100-Line Bonus Module"
description: "Adding a Markdown parser to LuoBlog's Document Intelligence pipeline — 100 lines of code, 12 tests, zero new bugs."
date: 2026-07-31
tags: [Python, Engineering, Document Processing]
categories: [Build Log]
slug: markdown-parser
draft: false
author: Luo Runjie
readingTime: 5 min
difficulty: beginner
---

# Markdown Parser: The 100-Line Bonus Module

The Knowledge Hub already had a PDF parser using PyMuPDF. But the Knowledge Hub also ingests Markdown files (code documentation, meeting notes, technical drafts).

Adding a Markdown parser was straightforward — implement the same `DocumentParser` ABC that `PdfParser` already uses:

```python
class MarkdownParser(DocumentParser):
    def parse(self, file_path: str) -> ParsedDocument: ...
```

The implementation is ~100 lines. No AST library needed — Markdown structure is simple enough for line-by-line parsing:

1. Lines starting with `#` → new section (detect heading level)
2. Everything else → body text
3. Track code fence state (` ``` ` or ` ~~~ `) to avoid parsing literals as headings

The hardest bug was that empty sections between consecutive headings were silently discarded. A Markdown file with:

```markdown
# H1
## H2
### H3
```

Would produce zero sections — each heading replaces the previous one before any content is accumulated. The fix was to require each test heading to have at least one line of body content after it.

No review issues worth documenting. The module is too simple.
