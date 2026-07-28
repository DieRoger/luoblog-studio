# BLOG_RULES.md

# Purpose

This document defines how engineering blogs should be generated for this project.

The goal is **not** to create tutorials.

The goal is to document engineering thinking, design decisions, trade-offs, and lessons learned throughout the project.

Every blog should be something that an experienced engineer would find valuable.

---

# Target Audience

Primary readers:

- AI Engineers
- Backend Engineers
- ML Engineers
- LLM Application Developers
- Software Architects
- Graduate students interested in AI Systems

Assume readers already know basic Python, Git, APIs, and LLM concepts.

Do not spend paragraphs explaining basic knowledge.

Focus on engineering decisions.

---

# Writing Philosophy

Every article should answer questions like:

- Why was this feature necessary?
- Why was this architecture chosen?
- What alternatives were considered?
- What problems appeared?
- What mistakes were made?
- How were they solved?
- What would be done differently next time?

The blog should emphasize thinking rather than implementation.

---

# Writing Style

The tone should be:

- Professional
- Honest
- Evidence-driven
- Engineering-focused
- Practical

Avoid:

- Marketing language
- Clickbait
- Excessive excitement
- Buzzwords without explanation
- Empty conclusions

Never exaggerate.

If something failed, explain why.

If something is uncertain, say so.

---

# Engineering First

The article should prioritize:

1. Design
2. Architecture
3. Trade-offs
4. Engineering decisions
5. Lessons learned

Actual code should be secondary.

Never explain code line by line.

Instead explain:

- Why this module exists.
- Why this abstraction exists.
- Why this API looks like this.
- Why another approach was rejected.

---

# Preferred Blog Structure

Every engineering article should follow this structure.

---

## 1. Background

What problem are we trying to solve?

Why does it matter?

---

## 2. Initial Design

Describe the first design idea.

Explain why it seemed reasonable.

---

## 3. Problems Encountered

Describe real engineering issues.

Examples:

- architecture conflicts
- framework limitations
- prompt instability
- retrieval failures
- performance bottlenecks
- testing issues

Avoid artificial examples.

---

## 4. Alternative Solutions

List multiple solutions.

For each solution explain:

Advantages

Disadvantages

Why rejected

---

## 5. Final Design

Explain the chosen solution.

Include:

- architecture
- data flow
- module responsibilities

Prefer diagrams over long paragraphs.

---

## 6. Implementation Notes

Briefly describe implementation.

Focus on key engineering ideas.

Avoid code dumps.

---

## 7. Lessons Learned

Summarize practical engineering experience.

Readers should gain reusable knowledge.

---

## 8. Future Improvements

Be honest.

What is still imperfect?

What would be redesigned?

---

# Trade-off Section

Every technical article must include trade-offs.

Examples:

Why FastAPI instead of Django?

Why PGVector instead of FAISS?

Why LangGraph instead of custom workflow?

Why SQLite during MVP?

Explain both strengths and weaknesses.

Never present a technology as universally best.

---

# Evidence

Whenever possible include evidence.

Examples:

- benchmark numbers
- latency
- memory usage
- screenshots
- architecture diagrams
- logs
- evaluation metrics

Avoid unsupported opinions.

---

# Visuals

Prefer visuals whenever useful.

Examples:

- Mermaid diagrams
- sequence diagrams
- workflow diagrams
- architecture diagrams
- tables

Large code blocks should be avoided.

---

# Code

Code is supporting material.

Do not let code dominate the article.

Only include snippets when they explain an important engineering decision.

Each code block should answer:

"Why is this code interesting?"

---

# Blog Length

Short article

1000~1500 words

Medium article

2000~3500 words

Deep dive

4000~7000 words

Avoid unnecessary filler.

---

# SEO

Generate:

Title

Description

Keywords

Slug

Suggested URL

Reading Time

Difficulty

---

# Frontmatter

Every article should generate:

```yaml
---
title:
description:
date:
tags:
categories:
slug:
draft:
author: Luo Runjie
readingTime:
difficulty:
---
```

---

# Tags

Prefer consistent tags.

Examples:

AI

LLM

Agent

RAG

Evaluation

Prompt Engineering

FastAPI

LangGraph

Observability

Vector Database

PostgreSQL

Python

Architecture

Engineering

Audit

Workflow

Knowledge Graph

Evidence

---

# Screenshots

If screenshots are referenced:

Use:

/images/posts/<slug>/

Example:

/images/posts/agent-workflow/

---

# Diagrams

Prefer Mermaid.

Example:

- flowchart
- sequenceDiagram
- graph TD
- stateDiagram

Architecture should be visual whenever possible.

---

# Personal Voice

Write as an engineer documenting a real project.

Not as a teacher.

Not as a marketer.

Use first-hand experience.

Examples:

"I originally chose..."

"After testing..."

"This approach failed because..."

"We later replaced..."

Avoid generic AI-generated phrasing.

---

# What Makes a Good Blog

A good engineering blog should leave readers thinking:

"I understand why this design exists."

instead of

"I learned another API."

Engineering thinking is always more valuable than implementation details.

---

# End of Article

Every article should finish with:

## Key Takeaways

3~5 concise engineering insights.

Then:

## Next Step

Explain what will be explored next in the project.

Keep readers following the engineering journey.