---
title: "Four Code Reviews Later: What Reading AuditFlow's Source Taught Me About Building Trustworthy AI"
description: "Consolidating the findings from four code-grounded reviews — hardcoded citations, a real DAG, an honest RAG baseline, and proxy metrics — into engineering principles for AI systems you can trust."
date: 2026-07-31
tags: [AI, Engineering, Architecture, Evidence, Evaluation, Lessons]
categories: [Engineering Decisions, Project Reflection]
slug: auditflow-four-reviews-lessons
draft: false
author: Luo Runjie
readingTime: 20 min
difficulty: advanced
---

# Four Code Reviews Later: What Reading AuditFlow's Source Taught Me About Building Trustworthy AI

## Background

This is the fifth article in a series. The first four were grounded in reading AuditFlow's actual source: the evidence agent, the workflow engine, the RAG pipeline, and the evaluation framework. This final article steps back and consolidates what those reviews found — not as a summary of AuditFlow, but as a set of engineering principles for building AI systems you can trust.

Each principle below comes from a specific finding in one of the four reviews. Each finding is verifiable against the code. That's the whole point of the series: **claims about AI systems should be checkable, not asserted.**

## Principle 1: Evidence-Driven AI Is Structural, Not Prompted

The first review found the evidence agent's citation with a hardcoded `document_id="evidence_source"`. In an evidence-driven system, "the source" is the entire point — and the code literally could not answer where a citation came from.

The principle: **if an unsupported claim can reach the output, the system is not evidence-driven, regardless of what the prompts say.** Prompt instructions ("cite your sources!") are advisory. Architecture — where every claim must resolve to a typed evidence node with a real source reference — is enforcement.

The counter-example in the same codebase proved this: the Evidence Graph (`AssertionNode.conclusion()`) computes SATISFIED/PARTIALLY/NOT_SATISFIED deterministically from typed evidence nodes. No LLM involved. That's what enforcement looks like. The evidence agent that feeds it `matched: true/false` flags with no document linkage is the gap.

**Practical rule**: when designing an evidence-driven AI, decide what makes a claim *emittable* — and encode that as a type check, not a prompt instruction.

The hallucination-detection papers in the knowledge base all converge on the same structural answer, each with a different mechanism:

| Paper | Mechanism | Similarity | What it enforces |
|-------|-----------|-----------|------------------|
| SelfCheckGPT (2303.08896) | Multi-sample consistency | 0.710 | A claim that varies across samples is hallucinated — confidence must come from agreement, not one pass |
| Chain-of-Verification (2309.11495) | Plan verification questions, then verify | 0.687 | Verification is a separate planning step, not an afterthought |
| CRITIC (2305.11738) | Verify-then-correct with external tools | 0.665 | The verify step calls a tool (search, calculator), not memory |
| GopherCite (2203.11147) | Inline evidence: verbatim quote + page | 0.750 | Evidence is a quoted fragment from a real source, penalized if unverifiable |

Each mechanism is a different *type* of structural enforcement: sampling consistency, verification planning, tool-grounded correction, and verbatim-quote citation. None of them are prompts that say "please be accurate." The AuditFlow evidence agent's hardcoded citation ID fails all four of these tests at once — which is precisely why the review flagged it as the central gap, not a cosmetic issue.

## Principle 2: Docs Describe Intent; Code Is Reality

Every one of the four reviews found the same pattern:

| Handover doc said | Code does |
|------------------|-----------|
| Evidence chain from retrieval | Hardcoded citation ID |
| Chain-only orchestration | Real `GraphDefinition` DAG |
| No token budget | `TokenBudgetTracker` (50000 tokens) |
| Hybrid search, 67 PDFs | Hybrid exists (RRF); index uses 5 docs |
| Four-layer evaluation | RecallAtK + keyword-based golden eval |

The doc wasn't malicious — it was written at a point in time, describing intent. Code is reality because it's what actually runs.

**Practical rule**: never describe an architecture from its documentation. Grep the code. If a claim in a blog, review, or handover can't be verified against a `grep`, it's a hypothesis, not a fact. This series' own errors (claiming "no DAG," then "no token budget," then "no hybrid") all came from reading too little code, and each was corrected by reading more.

## Principle 3: The Gap Between Intent and Code Is Where the Interesting Engineering Lives

This is the constructive corollary of Principle 2. The gaps weren't failures to be embarrassed about — they were the most informative parts of the codebase:

- The hardcoded citation ID revealed *why* the Evidence Graph can't consume the agent's output (different languages: `matched` flags vs typed evidence nodes).
- The missing retrieval evaluator revealed *how* a false-negative could silently pass (fixed top-K, no "we might have missed something" signal).
- The keyword-based detection metric revealed *why* the F1 regression might be a formatting regression, not a behavior regression.
- The in-memory trace/checkpoint defaults revealed *where* production incidents hide (between "has a store class" and "persists by default").

The literature reinforces this from a different angle. The retrieval papers in the knowledge base each name a specific gap that the code's design doesn't address:

| Paper | Similarity | Gap it names | Where the gap lives in AuditFlow |
|-------|-----------|--------------|----------------------------------|
| Self-RAG (2310.11511) | 0.758 | "consistently retrieves a fixed number of documents regardless of the retrieval necessity" | The pipeline always retrieves top-K, never asks whether retrieval is needed |
| CRAG (2401.15884) | 0.783 | A retriever-evaluator scores retrieval quality and decides to correct | No evaluation of retrieval before the evidence agent uses it |
| ColBERT (2004.12832) | 0.803 | Token-level late interaction for exact matching | Single-vector similarity can't find "paragraph 17 of CAS 14" precisely |
| RAPTOR (2401.18059) | 0.810 | Multi-granularity hierarchical retrieval | Flat chunk list retrieves one level of abstraction |

The pattern is consistent: the code's gaps are *named* by the papers, and the papers' fixes are *additive* — none require re-architecting. This is what makes the gap analysis actionable rather than just critical.

**Practical rule**: in any review, spend the most time on the places where the design doc and the code disagree. That's where the real system — with its real constraints and real compromises — is visible. Then check whether the research literature has already named the gap and proposed a fix.

## Principle 4: Trust Requires Multiple Evidence Sources

The knowledge base had the papers. The code had the implementation. The handover doc had the intent. No single source was sufficient:

- **Papers** (SelfCheckGPT, CoVe, CRITIC, GopherCite, CRAG, Self-RAG, ColBERT, RAPTOR, AgentBench, SWE-bench, GAIA, LLM-as-a-Judge) told me what the field says about retrieval, grounding, and evaluation.
- **Code** told me what AuditFlow actually does.
- **Docs** told me what AuditFlow intends.

The conclusions only held when all three agreed — or when the disagreement was itself the finding. The Evidence Graph's deterministic sufficiency judgment is good *domain* engineering that no paper describes. The hardcoded citation ID is a *code* reality that no doc mentions. Papers alone would have produced a generic "grounding is important" article; code alone would have missed the literature's concrete fixes; docs alone produced the wrong first versions of all four articles.

**Practical rule**: an engineering claim should trace to at least three source types — and if two of them disagree, that disagreement is the finding.

The evaluation papers make the same point about measurement itself. The knowledge base's evaluation benchmarks each warn against single-source evaluation:

- **AgentBench** (2308.03688) argues task-success rate over answer quality — the metric must match the actual task, not a convenient proxy.
- **SWE-bench** (2310.06770, similarity 0.819) opens with "Language models have outpaced our ability to evaluate them effectively" — evaluation lags the systems it measures.
- **GAIA** (2311.12983, similarity 0.807) requires human-baseline calibration so benchmark difficulty is separated from model capability.
- **LLM-as-a-Judge** (2306.05685, similarity 0.720) documents judge biases (position, verbosity, self-preference) — a single LLM judge is not trustworthy alone.
- **Holistic Evaluation** (2211.09110, similarity 0.850) defines scenario/adaptation/metric primitives — evaluation must be multi-dimensional.

These are not abstract warnings. The golden dataset's keyword detection (R01-R08) is exactly the kind of proxy these papers caution against: it's deterministic and reproducible, but "contains 'cutoff'" ≠ "understands cutoff risk." The multi-source principle applies to *metrics* as much as to evidence: no single metric should gate a release.

## Principle 5: Proxy Metrics Need a Second Check

The golden evaluation scored risk detection by keyword presence ("contains 'cutoff'" = detected). This is deterministic and reproducible — but it measures keyword presence, not risk understanding. A refactor that changes output wording could drop F1 without changing detection behavior.

The same issue appears in the literature: LLM-as-a-Judge scores are biased (position, verbosity, self-preference) and need calibration against human annotation. SWE-bench warns that models outpace our ability to evaluate them — proxies age.

**Practical rule**: every metric is a proxy for something you actually care about. Name the proxy and the target, and when a metric moves, check whether the *behavior* moved or just the proxy. The F1 regression story needs exactly this second check.

## Principle 6: Local-First Is a Compliance Decision, Not a Cost Decision

The RAG pipeline uses 384-dim BGE-small via fastembed — local, private, zero API cost. The handover doc frames this as a cost/privacy trade. Reading it against the domain reframes it: financial audit documents are confidential. Sending them to an embedding API is not a cost question; it's a compliance violation.

This is the same reasoning that drove LuoBlog Studio's local embedding choice. Local-first isn't "cheaper" — it's "the only option that doesn't leak the data."

**Practical rule**: for regulated domains, "local-first" is not a preference; it's the boundary of what's legal. Design for it from the start, not as a later optimization.

The engineering consequence is concrete: local inference means *model choice is constrained by what runs on your hardware*, not by what's best on a leaderboard. AuditFlow's 384-dim BGE-small via ONNX is not the strongest embedder — but it's the strongest one that runs entirely on the machine, and that constraint is non-negotiable. The trade is real and worth stating plainly: you give up embedding quality for the guarantee that client data never leaves the box. For confidential financial data, that's a correct trade, and building it in from the start (as both AuditFlow and LuoBlog did with fastembed) avoids a painful mid-project migration away from an API embedder whose use was always going to be a compliance violation.

## Principle 7: CJK Awareness Is a Correctness Feature

The chunker's token estimator counts Chinese at 1.5 chars/token and English at 4 — separately. On a Chinese financial corpus, a naive `len/4` estimator would undercount Chinese tokens by ~3x, silently violating the 500-token chunk budget.

This was a real bug in my own LuoBlog chunker (English-only sentence splitting that broke on `。`). AuditFlow got it right from the start in the estimator. The lesson generalizes: **any text-processing system that serves non-English content must treat language as a first-class correctness dimension, not an edge case.**

**Practical rule**: add at least one non-Latin test case to every text-processing module. English-only test data hides exactly the bugs that appear at 3am on a Chinese user's document.

## Principle 8: The Reviewer Can't Verify What It Can't Look Up

The workflow's Reviewer Agent is the final gate — but the Knowledge Agent's fallback path can produce citations like `IFRS 15.27` from memory, and whether that's caught depends on the reviewer's ability to verify it against a real source. If the reviewer can't look up the citation, the fallback path is a hallucination pipeline with a citation-shaped output format.

The literature converges on the same fix: CRITIC verifies with tools, CoVe plans verification queries, GopherCite requires verbatim quotes. A reviewer without retrieval tools is a reviewer that trusts everything it's shown.

**Practical rule**: give every verification agent the tools to check claims against ground truth. A reviewer that only reads text is a rubber stamp.

The tool-armed verification idea has three concrete implementations in the knowledge base, each with a different verification tool:

- **CRITIC** (2305.11738, similarity 0.665): the model critiques its output *using external tools* — search, calculators, code execution — then corrects. The retrieved chunk describes the "verify-then-correct" iteration loop until stopping criteria are met. The tool is what makes the verification non-circular: the model checks against something outside itself.
- **Chain-of-Verification** (2309.11495, similarity 0.687): the model plans verification questions and answers them *independently*, so the verification isn't biased by the original answer. The tool here is a second, independent reasoning pass.
- **GopherCite** (2203.11147, similarity 0.750): the evidence is a *verbatim quote with a page title*, presented separately from the claim. The "tool" is the retrieval store, and the check is: does this quote actually exist in the source?

In AuditFlow, the Knowledge Agent already demonstrates the right pattern — its retrieved path demands `[Page N]` + `source_page` in the citation JSON, which is GopherCite's inline-evidence structure. The gap is the Reviewer Agent: nothing in the workflow gives it a retrieval tool to verify `IFRS 15.27` against the standards corpus. It can only read the claim and judge plausibility. That's the rubber-stamp failure mode, and it's the single most consequential gap for a system whose output is an audit opinion.

**Practical rule**: before shipping any AI that produces consequential claims, ask: what tool does the verifier have, and what does it check against? If the answer is "nothing" or "the same text it's verifying," the verification is theater.

## Principle 9: Explicit Fallback Beats Silent Degradation

The Knowledge Agent has two structurally different prompts: one for retrieved chunks (demands `source_page`), one for fallback (no page numbers). The system *knows* when it's answering from memory because the output schema changes.

This is honest engineering. Silent degradation — where the system quietly produces lower-quality output without signaling — is what makes AI untrustworthy. The visible mode switch lets downstream consumers (and humans) treat memory-answers differently from retrieval-answers.

**Practical rule**: when an AI system degrades (no retrieval, low confidence, fallback), make the degradation visible in the output structure, not just in a log line.

## Principle 10: The Audit Trail Is the Product

Everything in AuditFlow — the workflow events, the ExecutionTrace, the checkpoints, the page-provenance in citations — serves one requirement: the execution must be reconstructable. The custom workflow engine was chosen over LangGraph not for features but because the audit trail is the deliverable.

This is the deepest lesson and the one that generalizes beyond audit: **for AI systems where decisions have consequences, inspectability is not a nice-to-have — it's the product.** Every design decision should be evaluated against "can we reconstruct why this output exists?"

## Lessons Learned (Synthesis)

1. **Read code, then docs, then write.** The first versions of all four articles were wrong because they started from docs. Every correction came from reading the code.
2. **Evidence-driven AI is a type system, not a prompt.** If an unsupported claim can reach output, the architecture failed.
3. **The gap between intent and code is the most informative place to look.** Spend review time there.
4. **Three evidence sources minimum** — paper, code, doc — and disagreements between them are findings.
5. **Every metric is a proxy.** Name the target; when the metric moves, verify the behavior moved too.
6. **Local-first is compliance for regulated domains.** Design for it from day one.
7. **CJK is a correctness dimension, not an edge case.** Test with non-Latin data.
8. **Reviewers need tools.** A verifier that can't look things up is a rubber stamp.
9. **Explicit fallback builds trust.** Make degradation visible in the output.
10. **The audit trail is the product.** Inspectability drives design.

## Key Takeaways

- **Trustworthy AI is an architecture problem.** Structural enforcement beats prompt instruction every time.
- **Documentation describes intent; code is reality.** Grep before you claim.
- **Evidence gaps are the most valuable engineering artifacts.** The hardcoded citation ID taught more than the whole handover doc.
- **Proxy metrics need a behavioral second check.** Keyword detection and LLM judges both drift.
- **Local-first is the compliance boundary for confidential data.**
- **CJK-awareness is a correctness feature** — for both token estimation and sentence splitting.
- **Explicit fallback and tool-armed reviewers** are what make AI honest under pressure.
- **When the audit trail is the product, inspectability drives every design decision.**

## What I'd Do Differently

If I were re-doing this series:

1. **Start with a code map.** Before writing anything, list every module I plan to describe and grep each one. The first four articles each had at least one claim that a grep would have caught.
2. **Measure the gaps quantitatively.** "The evidence agent doesn't link citations" is an anecdote; "of 10 test claims, 0 resolved to a real chunk" is a number. The evaluation framework exists — use it on the claims.
3. **Write the correction into the process, not just the article.** The series caught its own errors, but the errors happened because the writing process didn't force code verification first. The fix is a checklist: for every architectural claim, cite the file and line it comes from.
4. **State the similarity score for every paper citation.** The knowledge base retrieval returns a number for each paper (SelfCheckGPT 0.71, CoVe 0.69, CRAG 0.78, ColBERT 0.80). Publishing those scores turns "I recall this paper says X" into "this paper's actual chunk matches this query at 0.71" — a measurable claim instead of an assertion.

The four-step method — retrieve the paper, read the code, quote both, then interpret — turned five articles from unverifiable summaries into a series where every claim has a file or a similarity score behind it. That's the difference the new blog rules were designed to enforce, and it's the difference between an opinion piece and an engineering record.

## Next Step

The principles in this article are now being applied to LuoBlog Studio's own evidence layer — which has the same hardcoded-citation risk in its pipeline and the same need for local-first, CJK-aware, inspectable design. The series continues there, with the same method: read the code, quote it, interpret it, and correct what's wrong.

The immediate next moves: (1) audit LuoBlog's evidence pipeline for the same `document_id` hardcoding the AuditFlow review found; (2) wire the Grounding Checker into the Review Agent so citations are verified against the knowledge base at query time, not assumed; (3) add a retrieval evaluator to the search path so weak retrieval surfaces as a signal instead of a silent failure. Each is a concrete, code-level application of the principles in this article.
