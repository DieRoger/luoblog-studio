---
title: "The Evaluation Framework AuditFlow Actually Runs: Runner, Metrics, Baselines, and What the Benchmarks Say About Measuring Agents"
description: "Reading evaluation/runner.py and evaluation/metrics.py against AgentBench, SWE-bench, GAIA, and LLM-as-a-Judge — what the four-layer evaluation claims, what the code enforces, and where the gaps are."
date: 2026-07-31
tags: [Evaluation, LLM, Benchmark, Agent, Engineering]
categories: [Architecture, Performance Optimization]
slug: auditflow-evaluation-framework-real-code
draft: false
author: Luo Runjie
readingTime: 20 min
difficulty: advanced
---

# The Evaluation Framework AuditFlow Actually Runs: Runner, Metrics, Baselines, and What the Benchmarks Say About Measuring Agents

## Background

AuditFlow's stated principle is *evaluation-driven development*: "no Agent or Service is considered done until it passes a quantitative benchmark." The handover doc describes a four-layer evaluation system (L1 retrieval, L2 agent, L3 grounding, L4 workflow) with an F1 regression incident as evidence it works.

This article checks that claim against the actual code: `evaluation/runner.py`, `evaluation/metrics.py`, and the benchmark scripts. The prior version of this article repeated the handover doc's descriptions. This version quotes the code and measures the gap between the four-layer vision and the shipped implementation.

## Part 1: The Runner — What the Code Enforces

`evaluation/runner.py` is the core. Its structure is honest about what evaluation means in this codebase:

```python
class EvaluationRunner:
    """统一的 Agent 评估执行器"""

    def __init__(self, metrics: list[Metric], baseline: dict[str, float] | None = None):
        self._metrics = metrics
        self._baseline = baseline or {}

    async def run(self, agent: BaseAgent, benchmark: Benchmark) -> EvaluationReport:
        for case in benchmark.cases:
            request = AgentRequest(..., inputs=case.input)
            response = await agent.execute(request)
            for metric in self._metrics:
                agg_predictions[metric.name].append(response.result)
                agg_truths[metric.name].append(case.expected)
        ...
        passed = all(scores.get(name, 0.0) >= baseline ...)
```

Three design facts:

1. **Evaluation is per-agent, per-benchmark.** You pick one agent, one benchmark, and run. There's no notion of evaluating a *workflow* here — the four-layer vision (including L4 workflow) lives above this runner, not in it.
2. **Metrics are pluggable.** `metrics: list[Metric]` — each metric is a `Metric` ABC subclass with `async compute(prediction, ground_truth) -> float`. Adding a metric is adding a class.
3. **Baselines are a gate.** `passed = all(scores >= baseline)` — the runner returns a pass/fail verdict against a baseline, which is exactly the "evaluation gate" the handover doc describes. The F1 regression story is credible: if the anomaly benchmark's baseline F1 was 60%, a drop to 25.4% would flip `passed` to False.

## Part 2: The Metrics — L1 Retrieval Is Real, the Rest Is Sparse

`evaluation/metrics.py` defines the data model and the first metric:

```python
class BenchmarkCase(BaseModel):
    id: str
    description: str = ""
    input: dict = Field(default_factory=dict)
    expected: dict = Field(default_factory=dict, description="ground_truth")
    evaluation_metrics: list[str] = Field(default_factory=list)


class RecallAtK(Metric):
    name = "recall_at_k"

    async def compute(self, prediction: dict, ground_truth: dict) -> float:
        predicted = set(prediction.get("retrieved_ids", []))
        expected = set(ground_truth.get("expected_ids", []))
        if not expected:
            return 0.0
        return len(predicted & expected) / len(expected)
```

`RecallAtK` is a clean, correct retrieval metric: intersection of retrieved IDs with expected IDs over the expected set. But here's the honest state: **the L1 retrieval metric exists; the L2/L3/L4 metrics I can verify are thin or absent from this file.** The four-layer vision in the doc (agent success rate, citation precision, workflow completion rate) is not fully realized as concrete `Metric` classes here. Some may live in the benchmark scripts (`golden_eval.py`, `human_eval.py`), which is worth checking — but the core `metrics.py` ships RecallAtK and the scaffolding, not the full four-layer suite.

The `BenchmarkCase` design is right, though: `expected` is typed as ground truth, and `evaluation_metrics` names which metrics apply to which case. That's the correct primitive — a benchmark is a list of cases with per-case expected outputs and metric selection.

## Part 3: What the Papers Actually Say About Agent Evaluation

The knowledge base has the canonical benchmarks. Measured retrieval results:

### AgentBench (2308.03688) — task success, not answer quality

The top hit for "AgentBench evaluating LLMs as agents" was actually AutoGen's related-work section (0.850) — which itself categorizes single-agent vs multi-agent systems. AgentBench's own contribution is 8 environments with task-success-rate evaluation. The key shift: **agents are scored on completing tasks, not on the quality of a text answer.** AuditFlow's `RecallAtK` measures retrieval relevance; it doesn't measure whether the audit task (e.g., "determine if revenue cutoff is violated") succeeded. AgentBench says task completion is the metric that matters for agents.

### SWE-bench (2310.06770, similarity 0.819)

The retrieved chunk is the abstract's opening:

> "Language models have outpaced our ability to evaluate them effectively."

SWE-bench's answer: evaluate on real GitHub issues — actual codebases, real failing tests, patch generation. The design lesson is **real-task evaluation over synthetic**: don't invent scenarios, use the real ones the system will face. For AuditFlow, that means evaluating on the actual 5-document corpus and the real revenue-cutoff case, not fabricated audit scenarios.

### GAIA (2311.12983, similarity 0.807)

> "GAIA is a benchmark for AI systems proposing general... questions and associated challenges."

GAIA's premise: assistants should be evaluated on real-world questions that require tool use, web search, and multi-step reasoning — and human solvers should establish the baseline. The design lesson: **human baseline calibration.** GAIA is deliberately hard for LLMs and easy for humans, so the benchmark separates "assistant capability" from "test difficulty."

### LLM-as-a-Judge (2306.05685, similarity 0.720)

The retrieved chunk is a judge prompt:

> "Please act as an impartial judge and evaluate the quality of the responses provided by two AI assistants... You should choose the..."

This is the actual judge prompt template. The paper's findings that matter for AuditFlow: LLM judges are biased (position, verbosity, self-preference), but they're cheap and scalable. The correct use is **screening, not deciding** — which is exactly what the AuditFlow docs claim the human evaluation set is for.

### Holistic Evaluation (2211.09110, similarity 0.850)

> "We introduce the basic primitives (scenario, adaptation, metric) required to evaluate a language model... With these primitives, we then provide a roadmap for how we holistically evaluate language models."

The scenario/adaptation/metric primitive decomposition is the same structure AuditFlow's `BenchmarkCase` encodes: input (scenario), expected (adaptation target), evaluation_metrics (metric). The paper's warning — single metrics mislead — is the argument for the four-layer vision, even if the code hasn't fully shipped it.

## Part 4: The F1 Regression Story — Plausible, but Check the Evidence

The handover doc's F1 64.6% → 25.4% story is the flagship example of "evaluation gates catch regressions." With the runner code read, the mechanism is plausible: an anomaly-detection benchmark with a 60% F1 baseline would have its `passed` flag flip to False after the weight-system refactor.

But two things remain unverified from code alone:

1. **Where is the F1 metric?** `metrics.py` ships `RecallAtK`. F1 for anomaly detection would be a different metric class — likely in `domain/finance/anomaly/evaluation/benchmark.py` or a script. I haven't confirmed F1 is computed by the runner, or whether the 64.6%→25.4% numbers came from a one-off script rather than the gated runner.
2. **Is the gate actually blocking?** The runner computes `passed`, but the CI wiring — whether a failing evaluation blocks a merge — lives in GitHub Actions, not the runner. The "evaluation gate" is only real if CI enforces it.

The honest statement: the *mechanism* for the story exists in code; the *specific story* (F1 numbers, CI enforcement) needs the benchmark script and workflow file to fully verify.

## Part 5: The Golden Dataset — How Risk Detection Is Actually Measured

Beyond the runner, the real evaluation happens in `scripts/golden_eval.py`. Its docstring is specific:

```python
"""Golden Dataset Evaluation — 用合成数据测试 Risk Agent 的地雷检出率
评估方法:
  1. 对每个地雷构造测试 Case
  2. 运行 Risk Agent 或 Analytics Engine
  3. 检查是否检出 (detected = True/False)
  4. 计算 Recall / Precision"""
```

This is a "mine detection" evaluation: synthetic cases planted with known risks (the "mines"), then checking whether the agent detects them. The rules are keyword-based:

```python
DETECTION_RULES = {
    "R01": ["cutoff", "截止", "提前", "premature", "shipping"],
    "R02": ["related party", "关联方", "虚构", "fictitious", "ghost"],
    "R03": ["return", "退货", "refund", "sales return", "冲减"],
    ...
}

def check_detection(agent_output: dict, risk_id: str) -> bool:
    keywords = DETECTION_RULES.get(risk_id, [])
    output_text = str(agent_output).lower()
    return any(kw.lower() in output_text for kw in keywords)
```

Eight risk categories (R01 revenue cutoff, R02 related parties, R03 returns, R04 Q4 concentration, R05 customer concentration, R06 receivables, R07 discounts, R08 round-number fraud), each with multilingual keywords (English + Chinese).

### The honest limitations of keyword-based detection

This evaluation method is simple, fast, and deterministic — but it measures *keyword presence*, not *risk understanding*. A detection counts as a hit if the agent's output happens to contain "cutoff" or "截止". Three failure modes:

1. **False positive by keyword collision.** An agent that says "we assessed whether premature recognition occurred and concluded it did not" contains "premature" — and would be scored as a detection, even though the agent explicitly ruled out the risk.
2. **False negative by synonym.** An agent that describes "sales recognized before goods shipped" without using any keyword in the rule list gets scored as a miss, despite correctly identifying the risk.
3. **No severity weighting.** All eight rules count equally; a missed R08 (round-number fraud, a weak signal) costs the same as a missed R01 (revenue cutoff, a material misstatement).

These are real measurement limitations, and the code doesn't hide them — `check_detection` is plainly keyword matching. The value is that the benchmark exists at all: it gives a reproducible Recall/Precision number on a fixed synthetic set. The limitation is that the number measures a proxy (keyword presence) for the target (risk understanding). The F1 regression story (64.6% → 25.4%) is measured against *this* kind of metric — which means the F1 drop could reflect either a real detection regression or a keyword-matching regression (e.g., the refactor changed output wording so keywords no longer appear).

This is the deepest evaluation insight from reading the code: **a benchmark is only as valid as the proxy it measures, and a regression on a proxy metric needs a second check** — did the agent's *behavior* regress, or just its output formatting?

## Part 6: What the Code Gets Right

### Pluggable metrics with a clean ABC

```python
class Metric(ABC):
    name: str = ""
    @abstractmethod
    async def compute(self, prediction: dict, ground_truth: dict) -> float: ...
```

This is the right abstraction. Adding RecallAtK, CitationPrecision, TaskSuccessRate, or any L2/L3/L4 metric is a class addition, not a runner modification. The four-layer vision can grow into this skeleton.

### Baseline as a first-class gate

`baseline: dict[str, float] | None` with `passed = all(scores >= baseline)` makes "no agent is done until it passes the benchmark" an executable statement, not a slogan. The baseline dict is per-metric-name — so a benchmark can require recall≥0.8 AND citation-precision≥0.9 simultaneously.

### Ground truth is typed

`expected: dict` with `description="ground_truth"` — cases carry explicit expected outputs. Evaluation without ground truth is vibes; this is measurement.


## Part 6b: Consistency Testing and Human Evaluation

Two evaluation practices from the handover doc deserve scrutiny against the code:

### Consistency testing

The doc mentions consistency testing (8 cases × 2 runs). The principle is sound and directly relevant to the stochasticity of LLM agents: a single run of an agent is a sample from a distribution, not a measurement. Running the same case twice and comparing outputs is the minimum check for output stability.

What the runner code doesn't show is a dedicated consistency mode. The `EvaluationRunner` runs each case once. Consistency testing would require either re-running the benchmark with a different temperature, or a wrapper that executes each case N times and aggregates variance. Neither is visible in `runner.py` — which means the "8 cases × 2 runs" practice is a manual or script-level exercise, not a runner feature.

### Human evaluation

The doc cites 10 annotated cases scored by hand. This is the right calibration layer, and it directly addresses the LLM-as-a-Judge bias findings: if the LLM judge consistently rates reports 0.7 points higher than human annotators, the judge needs a correction factor, and humans remain the floor for release decisions.

The `human_eval_cases.py` script exists, confirming the practice is real. What isn't confirmed from code alone is whether the human scores are *wired back* into the evaluation loop — whether a judge-vs-human delta is computed and tracked over time. The LLM-as-a-Judge paper's contribution is precisely that this delta must be measured, because it drifts as the model and prompts change.

## Part 6c: What This Series Has Repeatedly Found

Across all four code-grounded articles, the same pattern recurs:

| Claim in docs | Reality in code |
|---------------|-----------------|
| Evidence chain from retrieval | Evidence agent: hardcoded `document_id="evidence_source"` |
| No DAG, chain orchestration | Workflow engine: real `GraphDefinition` DAG |
| No token budget | `TokenBudgetTracker` enforcing 50000 tokens |
| Hybrid search, 67 PDFs | `HybridRetriever` exists (RRF); index uses 5 docs |
| Four-layer evaluation | Runner ships RecallAtK + keyword-based golden eval |

The pattern is not "docs are wrong" — it's "docs describe intent, code is reality, and the gap is where the interesting engineering lives." Every article in this series found the same thing: the shipped code is more honest and more interesting than the documentation that describes it.


## Part 7: The Gap Between the Four-Layer Vision and the Code

| Layer (doc) | In code? | Evidence |
|-------------|----------|----------|
| L1 Retrieval | ✅ | `RecallAtK` in metrics.py |
| L2 Agent | ⚠️ Partial | `EvaluationRunner.run(agent, benchmark)` exists; task-success metrics not confirmed |
| L3 Grounding | ⚠️ Partial | Citation metrics claimed; not confirmed in metrics.py |
| L4 Workflow | ❌ Not in runner | Runner is per-agent, not per-workflow |

The vision is four layers; the shipped runner is per-agent with one confirmed retrieval metric. This isn't a failure — it's the honest MVP state — but it means the handover doc's "four-layer evaluation" description overstates the shipped code. The F1 regression gate protects anomaly detection (if wired); the retrieval layer's Recall@K exists; the grounding and workflow layers are scaffolding awaiting their metric classes.

## Part 8: What the Papers Suggest Adding First

Given the code as it stands, the highest-value additions, ordered by what the papers say matters:

1. **Task success rate (AgentBench).** The runner already executes agents against cases. Adding a `TaskSuccessRate` metric that checks `response.result` against `case.expected` turns "did the agent complete the audit task" into a number. This is the single biggest gap: AuditFlow measures retrieval relevance but not task completion.
2. **Human baseline calibration (GAIA).** The human-eval cases exist (`human_eval_cases.py`). Publishing a human-score baseline alongside LLM scores separates "task difficulty" from "model capability" — which is what makes benchmark numbers interpretable.
3. **Judge calibration (LLM-as-a-Judge).** If the Reviewer Agent doubles as a judge, its bias vs. human scores must be measured. The paper's position/verbosity biases are measurable with a small annotated set.
4. **Real-task benchmarks (SWE-bench).** AuditFlow already has the real corpus (5 documents, revenue-cutoff case). The lesson is to keep evaluation on real tasks, not synthetic ones — which the existing `golden_eval.py` direction already follows.

## Lessons Learned

1. **The runner is per-agent; the "four-layer" vision is larger than the code.** The doc overstates; the runner ships RecallAtK + scaffolding. Same pattern as the other articles: docs describe intent, code is reality.
2. **Pluggable metrics are the right foundation.** The `Metric` ABC means L2/L3/L4 can be added without touching the runner.
3. **Baseline as a gate is executable policy.** `all(scores >= baseline)` turns "evaluation-driven" into a pass/fail CI signal — if CI enforces it.
4. **AgentBench's task-success framing exposes the biggest gap.** AuditFlow measures retrieval, not task completion.
5. **LLM judges are screening tools, not arbiters.** The bias findings are real; use them with a human floor.
6. **Verify the F1 story end-to-end.** The mechanism exists; the specific numbers and CI enforcement need the benchmark script and workflow file to confirm.
7. **Keyword-based detection is a proxy metric with real blind spots.** "Contains 'cutoff'" ≠ "correctly identified a cutoff risk." A regression on a proxy needs a second check: did behavior regress, or just output formatting?
8. **Consistency testing is a manual practice, not a runner feature.** The principle is sound; the runner runs each case once. Stochasticity is only measured if you explicitly measure it.
9. **A benchmark is only as valid as the proxy it measures.** The golden dataset's keyword rules are deterministic and reproducible — but they measure keyword presence, not risk understanding.

## Key Takeaways

- **AuditFlow's evaluation runner is real and correct**: per-agent, pluggable metrics, baseline gates. RecallAtK is a clean L1 metric.
- **The four-layer vision is not fully shipped**: L1 exists; L2/L3 partial; L4 absent from the runner.
- **Task success rate (AgentBench) is the highest-value missing metric** — the runner is built for it, the metric class just needs writing.
- **LLM-as-a-Judge is useful for screening, biased for deciding** — calibrate it against the human set.
- **Real-task benchmarks (SWE-bench, GAIA) align with AuditFlow's existing corpus** — keep evaluation on real audit cases.
- **The F1 regression story is plausible but needs the benchmark script to confirm** — the gate mechanism exists in the runner.
- **The golden dataset is deterministic and reproducible but proxy-based** — keyword detection measures presence, not understanding; a proxy regression needs a behavioral second check.
- **The recurring lesson across all four articles**: docs describe intent, code is reality, and the gap is where the interesting engineering lives.

## Next Step

The final article in this series consolidates the lessons from all four code-grounded reviews — the evidence agent's hardcoded citations, the workflow engine's real DAG, the RAG pipeline's honest baseline, and the evaluation runner's gaps — into a single set of engineering principles for building trustworthy AI systems.

Before that, one correction is owed: this article (and the RAG article) initially understated the hybrid search. `infrastructure/retrieval/hybrid_search.py` exists with a real `HybridRetriever` that fuses vector + keyword via Reciprocal Rank Fusion (`RRB_K = 60`). The `PGVectorStore` I read earlier is the low-level vector store; the hybrid retriever composes it with keyword search at the retrieval layer. The system *does* have hybrid search — the gap is that the indexing pipeline (batch_index.py) writes to the vector store directly, so whether the agents actually use the hybrid retriever at query time requires reading the agent-to-retrieval wiring. That's the kind of half-verified claim this series exists to catch: I confirmed the hybrid component exists, but not that every query path uses it. The honest statement stands: hybrid search exists in the retrieval layer, and the RAG article's "pure vector search" claim was about the index pipeline, not the full retrieval stack.
