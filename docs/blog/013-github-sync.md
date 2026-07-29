---
title: "GitHub Sync: Publishing from the Draft System"
description: "One API call to push a formatted Markdown article from the Draft System to any GitHub repository."
date: 2026-07-30
tags: [GitHub, API, Engineering, Python]
categories: [Build Log]
slug: github-sync
draft: false
author: Luo Runjie
readingTime: 4 min
difficulty: beginner
---

# GitHub Sync: Publishing from the Draft System

The final link in the publishing chain: a `POST /api/v1/publish/{article_id}` endpoint that takes a draft from the Article system, formats it as a Markdown file with YAML frontmatter, and pushes it to any GitHub repository via the GitHub Contents API.

The frontmatter includes title, description, date, and tags. The content body is preserved as-is. The target path is `content/posts/{slug}.md` — compatible with Hugo, Jekyll, and Next.js static sites.

If the file already exists, it's updated (preserving git history). If it doesn't, it's created.

GitHub token and target repo are configured via environment variables.
