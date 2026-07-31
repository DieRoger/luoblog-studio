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

**硬性要求：每篇博客至少 3000 词（含代码块和图表说明）。低于 3000 词视为不合格，需要扩充后再交付。**

| 类型 | 词数 |
|------|------|
| 标准文章（默认） | **3000~4500 词** |
| 深度长文（技术详解） | 4500~7000 词 |
| 短文（不推荐，仅限极简记录） | 1500~3000 词 |

**为什么是 3000 词**：
- 3000 词以下无法展开完整的工程叙事（背景 → 设计 → 问题 → 权衡 → 实现 → 教训）
- 3000 词是"有实质内容"与"摘要"的分界线——用户能区分深度文章和凑数的概述
- 多出来的篇幅应投入**真实细节**（真实代码、真实 bug、真实数字、真实权衡），而不是填充词

**质量优先于数量**：3000 词必须是实质内容。如果凑不到 3000 词，说明素材不足——先读代码/文档补充素材，再扩充，而不是用空话填充。

Avoid unnecessary filler.
Avoid padding with generic statements — the length requirement is for substance, not words.

---

# Evidence Sources（证据来源多元化）

**硬性要求：一篇博客的证据来源不得少于 3 类。禁止只依赖单一来源（尤其是只依赖论文）。**

| 来源类型 | 示例 | 优先级 |
|---------|------|--------|
| **真实代码** | 项目源码片段、真实函数名、真实行数 | 🔴 最高 |
| **项目文档/实验** | README、ADR、实测数据、benchmark 结果 | 🔴 高 |
| **论文/外部文献** | 从知识库检索到的论文 chunk（必须真实入库） | 🟡 中 |
| **个人经验** | 真实踩过的坑、真实调试过程、真实权衡 | 🔴 高 |

**论文引用规则**：
- 引用论文前**必须从知识库检索**，确认论文真实存在并阅读其内容摘要
- 禁止凭印象描述论文内容（"这篇论文讲了..."必须是读过的）
- 引用时要说明**这篇论文的哪个观点支撑了你的哪个论点**，不能泛泛而谈

**禁止**：
- 只靠论文撑起全文（每篇博客至少一半内容来自真实代码/项目/经验）
- 引用未入库、未读过的论文
- 把论文摘要转述当成"自己的分析"

---

# Originality（原创性与查重）

**硬性要求：每篇博客必须通过原创性自查。禁止转述、复制、或"文档摘要式"写作。**

### 查重自查清单（交付前逐项检查）

1. **不是转述**：内容不是 handover.md / README / 论文摘要的改写。用原文对照检查——结构、段落、句子不能与来源文档重合
2. **有自己的发现**：至少包含一个**代码里读出来的、文档里没有的**事实（如硬编码 bug、真实常量、真实边界条件）
3. **有自己的判断**：对架构选择、技术缺陷、权衡给出**自己的观点**，而非复述文档结论
4. **有具体证据**：真实文件名、真实函数、真实数字、真实 log，而不是"系统表现良好"
5. **转述测试**：如果一段内容去掉来源引用后依然成立且无个人视角，它就是转述，重写

### 转述 vs 原创示例

| 转述（不合格） | 原创（合格） |
|---------------|-------------|
| "系统采用证据驱动架构，确保每个结论可追溯" | "我读 `evidence/agent.py` 发现 `document_id='evidence_source'` 是硬编码的——这个 citation 无法追溯到真实文档" |
| "我们实现了四层评估体系" | "F1 从 64.6% 掉到 25.4% 的那次重构，是 benchmark 门禁拦下的——如果靠人工 review，这个回归就上线了" |

---

# AI 味控制（Anti-AI-Flavor）

**硬性要求：文章必须读起来像工程师写的，不像 AI 生成的。**

### 禁止的 AI 味表达

- ❌ 模板化开头："在当今快速发展的..."、"随着大语言模型的兴起..."
- ❌ 空洞过渡："值得注意的是"、"总而言之"、"综上所述"
- ❌ 对称排比堆砌："不仅...而且...既...又..."
- ❌ 万金油结论："总的来说，这是一个充满挑战又富有意义的过程"
- ❌ 每个段落都以"xxx 是关键/重要/核心"结尾
- ❌ 编造的第一人称经验（"我遇到了..."但实际没发生）

### 合格标准

- ✅ 第一人称只描述**真实发生**的事（真实 bug、真实失败、真实修改）
- ✅ 用具体数字/文件名/函数名替代形容词（"慢"→"42 秒"）
- ✅ 允许口语化、不完美、有个人视角的句子
- ✅ 敢于写"这个设计其实是错的"、"当初不该这么做"
- ✅ 每篇文章至少 1 处真实失败的记录（debug 过程/踩坑/回滚）

### AI 味自查测试

- 把文章读给自己听：如果有任何句子让你觉得"这段话删掉也不影响信息量"，删掉
- 如果文章 70% 的段落可以互换顺序而不影响阅读，说明是模板堆砌
- 如果读者无法从文中判断你实际做了什么，只是"系统采用了 X"，重写

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