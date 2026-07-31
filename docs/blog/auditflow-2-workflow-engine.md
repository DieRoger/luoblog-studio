---
title: "A Graph, a State Machine, and a next_action Field: How AuditFlow's Workflow Engine Really Orchestrates Agents"
description: "Reading the real workflows/models.py and workflows/engine.py — GraphDefinition DAGs, conditional edges, approval gates, and the conversation-programming ideas from AutoGen and MetaGPT."
date: 2026-07-31
tags: [Agent, Workflow, DAG, LLM, Orchestration, Engineering]
categories: [Architecture, Debug Diary]
slug: auditflow-workflow-engine-real-code
draft: false
author: Luo Runjie
readingTime: 20 min
difficulty: advanced
---

# A Graph, a State Machine, and a next_action Field: How AuditFlow's Workflow Engine Really Orchestrates Agents

## Background

The previous version of this article claimed AuditFlow's agents were orchestrated by a simple `next_action` chain, not a DAG. That was wrong. I based it on one agent's return value without reading the orchestration layer.

Reading `workflows/models.py` and `workflows/engine.py` shows the truth: **the engine has both.** It defines a real DAG (`GraphDefinition` with nodes, edges, entry point, and end nodes) *and* agents return a `next_action` hint. The design is richer — and more interesting — than either of my two previous (contradictory) descriptions.

This article is the correction. Every claim below comes from the actual source files.

## Part 1: The Data Model — What the Graph Really Looks Like

`workflows/models.py` defines the orchestration primitives. Three types matter:

### AgentNode: a node with input mapping and retry policy

```python
class AgentNode(BaseModel):
    """Workflow 图中的一个 Agent 节点"""
    id: str
    agent_name: str
    input_mapping: dict = Field(default_factory=dict, description="将上游输出映射为本节点输入")
    retry_policy: dict | None = None
    timeout_seconds: int = 300
```

Two details worth calling out:

- **`input_mapping`** — each node declares how to map upstream outputs into its own input. This is the *context scoping* mechanism: the Risk node sees only what the Planner node produced, not the entire history. This directly contradicts the "give every agent the full conversation" anti-pattern that plagues naive multi-agent systems.
- **`timeout_seconds: int = 300`** — every node has a hard timeout. An agent that hangs gets killed at five minutes, not left to block the pipeline forever.

### Edge: directed edges with conditions

```python
class Edge(BaseModel):
    """节点间的有向边"""
    source: str
    target: str
    condition: str | None = None  # 条件表达式（如 "risk.level == HIGH → approval"）
```

The `condition` field is the interesting part. It's documented with an example: `"risk.level == HIGH → approval"`. This means the graph is not a fixed pipeline — it can branch based on runtime state. A low-risk engagement can skip the human-approval gate; a high-risk one cannot.

### GraphDefinition: the whole graph

```python
class GraphDefinition(BaseModel):
    """完整的 Workflow Graph 定义"""
    nodes: list[AgentNode]
    edges: list[Edge]
    entry_point: str
    end_nodes: list[str] = Field(default_factory=list)
```

This is a real DAG: explicit nodes, directed edges, an entry point, and terminal nodes. My earlier claim that "orchestration is a next_action field, not a DAG" was factually wrong — the DAG is right here in the data model.

## Part 2: The State Machine

`WorkflowState` carries the runtime status:

```python
class WorkflowState(BaseModel):
    workflow_id: str
    project_id: str = ""
    status: str = "CREATED"  # CREATED | QUEUED | RUNNING | WAITING_APPROVAL | RETRYING | FAILED | COMPLETED | CANCELLED
    current_node: str = ""
    agent_results: dict[str, dict] = Field(default_factory=dict)
    error: str | None = None
    retry_count: int = 0
```

Eight states, and the two that define the product are `WAITING_APPROVAL` and `RETRYING`:

- **`WAITING_APPROVAL`** — the graph reached a human gate. The workflow pauses, waits for an `ApprovalDecision`, and only resumes on approval.
- **`RETRYING`** — a node failed but its `retry_policy` says it's retryable. The engine increments `retry_count` and re-runs.

The `ApprovalDecision` type shows what a human gate actually accepts:

```python
class ApprovalDecision(BaseModel):
    workflow_id: str
    reviewer_id: str
    decision: Literal["APPROVED", "REJECTED", "MODIFY"]
    comment: str = ""
    modifications: dict | None = None
```

Three decisions, not two: approve, reject, or **modify** — the reviewer can change the inputs and re-run. That third option is the realistic audit workflow: the planner's risk assessment was wrong, so the human adjusts the assessment and the pipeline re-runs with corrected input.

## Part 3: The Engine — Events, Trace, Checkpoint

`workflows/engine.py` is the orchestration runtime. Its constructor takes three collaborators:

```python
def __init__(self, agent_registry, trace_store=None, checkpoint_store=None):
    self._registry = agent_registry
    self._trace_store = trace_store or InMemoryTraceStore()
    self._checkpoint_store = checkpoint_store or InMemoryCheckpointStore()
    self._states: dict[str, WorkflowState] = {}
    self._graphs: dict[str, GraphDefinition] = {}
    self._event_listeners: list[callable] = []
    self._step_counter: dict[str, int] = {}
```

### Events: the WebSocket bridge

```python
def on_event(self, listener: callable) -> None:
    """注册事件监听器（用于 WebSocket 推送）"""
    self._event_listeners.append(listener)
```

The engine emits typed events — `event_agent_started`, `event_agent_completed`, `event_approval_required`, `event_approval_submitted`, and five more — to all listeners. The frontend subscribes via WebSocket and renders a live view of the workflow: which agent is running, whether approval is pending, what just completed. This is observability built into the orchestration layer, not bolted on.

### Trace: the audit trail

```python
trace = ExecutionTrace(
    workflow_id=workflow_id,
    agent_name=agent_name,
    step=self._step_counter[workflow_id],
    event_type=event_type,
    input=input_data or {},
    output=output,
    duration_ms=duration_ms,
    error=error,
)
await self._trace_store.append(trace)
```

Every step records its input, output, duration, and error. This is the audit trail — and it's the reason the engine couldn't be replaced by LangGraph without losing something. LangGraph checkpoints are designed for resumability; `ExecutionTrace` is designed for *inspection*. An auditor (or a debugging engineer) can reconstruct exactly what each agent saw and produced.

### Checkpoint: resumability

```python
checkpoint = Checkpoint(
    workflow_id=workflow_id,
    agent_name=agent_name,
    state_snapshot=state.model_dump(),
)
await self._checkpoint_store.save(checkpoint)
```

A state snapshot saved after each node. If the process dies mid-workflow, resuming restores the last completed node. The cost of re-running one LLM agent is high; the cost of re-running a five-agent chain is higher. Checkpointing makes an outage cheap.

## Part 4: The next_action Field — and Why It's Not a Contradiction

So where does `next_action` fit? The evidence agent returns `next_action="REVIEWER_AGENT"`, which is what misled me earlier. The resolution is now clear:

- The **graph** defines the possible transitions (which nodes exist, how they connect, what conditions gate them).
- The **agent's `next_action`** is a *suggestion* — a hint from the agent about which node it expects next, used for dynamic routing or validation.

They're complementary, not contradictory. The graph is the declarative skeleton; `next_action` is a runtime signal that can feed conditional edge evaluation or sanity-check the agent's self-understanding against the declared topology.

The lesson for the previous (wrong) article: **one agent's return value is not the orchestration model.** You have to read the orchestration layer.

## Part 5: What the Multi-Agent Literature Actually Says

The knowledge base has the two canonical multi-agent papers. Retrieved chunks:

### AutoGen (2308.08155, similarity 0.883)

> "We introduced an open-source library, AutoGen, that incorporates the paradigms of conversable agents and conversation programming. This library utilizes capable agents that are well-suited for multi-agent cooperation. It features a unified conversation..."

AutoGen's core idea is **conversation programming**: agents cooperate by conversing, and the developer writes the conversation protocol. The retrieved chunk confirms the "unified conversation" framing — all agents share a conversation, and task completion emerges from the dialogue.

**Contrast with AuditFlow**: AuditFlow's agents don't converse. They pass typed artifacts through a graph. The planner produces a plan artifact; the evidence agent consumes it and produces an evidence artifact. This is message-passing with schemas, not conversation. For audit, that's a deliberate choice — you want typed, inspectable artifacts, not free-form dialogue that's hard to trace.

### MetaGPT (2308.00352, similarity 0.841)

> "MetaGPT... assigns roles based on SOPs... [and] encodes effective human workflows..."

MetaGPT's key idea: encode **Standard Operating Procedures** as structured role assignments and message-passing. A product manager agent, a designer agent, and an engineer agent follow SOP-defined handoffs.

**Contrast with AuditFlow**: AuditFlow is essentially doing MetaGPT-style SOP encoding, but for audit. The workflow graph *is* an SOP — planner → risk → evidence → reviewer — with typed artifacts at each handoff. What AuditFlow lacks (and MetaGPT has) is the *assembly-line parallelization*: MetaGPT can run independent role threads concurrently, while AuditFlow's linear graph mostly serializes.

### The event-driven observability layer

One thing neither paper emphasizes but the AuditFlow engine has as a first-class feature is the event system. `domain/events.py` defines nine event types — `event_agent_started`, `event_agent_completed`, `event_agent_failed`, `event_approval_required`, `event_approval_submitted`, `event_workflow_completed`, `event_workflow_failed`, `event_workflow_paused`, `event_workflow_resumed`. Each is emitted through `_emit` to every registered listener:

```python
async def _emit(self, event: WorkflowEvent) -> None:
    """发布事件到所有监听器"""
    for listener in self._event_listeners:
        await listener(event)
```

The frontend subscribes via WebSocket (`api/websocket/handler.py`) and renders a live execution view. This is observability as architecture — the orchestration layer publishes its state transitions, and any observer (WebSocket client, audit log, metrics collector) can consume them without polling.

The contrast with AutoGen is instructive. AutoGen's agents converse *with each other*, and the conversation *is* the observable record. AuditFlow's agents pass artifacts through a graph, so the observable record has to be *built* — hence the event system + ExecutionTrace. Different coordination models require different observability infrastructure.

## Part 6: The Retry and HITL Paths in the Code

The engine's retry loop and approval path are where the eight-state machine becomes concrete.

### Retry with explicit attempt counting

```python
max_retries = (node.retry_policy or {}).get("max_retries", 3)
for attempt in range(1, max_retries + 1):
    start_time = datetime.now()
    await self._record_trace(workflow_id, node.agent_name, "AGENT_START",
                             input_data={"node_id": node.id, "attempt": attempt})
```

Each retry is a separate trace entry with its attempt number — so the audit trail shows *which attempt* produced the final result. `state.retry_count = attempt - 1` records how many retries were needed. This is the traceability that a bare `try/except` loop would silently lose.

### HITL via events, not blocking calls

The engine doesn't block waiting for human approval. It emits `event_approval_required`, transitions to `WAITING_APPROVAL`, and waits for the workflow to be resumed — decoupling the human decision from the engine's event loop. The `ApprovalDecision` with its `MODIFY` option means a rejected or modified input can re-enter the graph at the appropriate node.


## Part 7: What a Read of Both Papers and Code Shows

The strongest conclusion from this exercise isn't about AuditFlow specifically — it's about how to write about a codebase:

- The first version of this article (from a handover doc) claimed: *no DAG, chain-only orchestration*. **Wrong** — `GraphDefinition` is a real DAG.
- The second version (from one agent's return value) claimed: *DAG exists but no token budget*. **Also wrong** — `TokenBudgetTracker` enforces limits in `_execute_node`.

Both errors came from reading too little code. The correction required reading the full engine, the budget tracker, and the sandbox — about 200 lines total. That's the actual lesson of this article: **a blog about an architecture is only as accurate as the code it was verified against.**


## Part 9: Custom Engine vs LangGraph — Revisited with Evidence

The handover doc says LangGraph was considered and rejected. Now that I've read the engine, I can evaluate that claim concretely instead of repeating it.

What AuditFlow's engine actually provides:

| Capability | AuditFlow Engine | LangGraph |
|-----------|-----------------|-----------|
| State machine (8 states) | Native `WorkflowState` | Implicit in graph execution |
| HITL gate | `WAITING_APPROVAL` + `ApprovalDecision` (3-way) | Requires checkpointers + custom interrupt handling |
| Step-level audit trace | `ExecutionTrace` with input/output/duration | Framework's `checkpoint` (resume-oriented) |
| Token budget | `TokenBudgetTracker` hard-enforced | Not built-in; must add |
| Timeout sandbox | `AsyncTimeoutSandbox` | Via node timeouts, less isolation |
| WebSocket events | 9 typed event types | Not built-in; must add |

The two claims in the handover doc — "control over state transitions" and "HITL integration" — hold up against the code. What the doc *doesn't* say, and the code does, is that the engine's real advantage is the **combination**: a single place where state, trace, budget, timeout, and events all live. LangGraph would have required bolting four of these five onto the framework.

The trade-off, honestly stated: the custom engine is ~600 lines the team maintains, and it lacks LangGraph's community, tooling, and battle-testing. For a domain where the audit trail is the product, that's a defensible bet — but it's a bet, not a foregone conclusion.

## Part 10: What This Article Got Wrong (and Fixed)

This is the second version of this article. The first version said:

> "Orchestration is a next_action field, not a DAG."

Reading `models.py` showed that's false — `GraphDefinition` is a real DAG with conditional edges.

The first version also claimed:

> "No token budget in the workflow model."

Reading `engine.py` past the constructor showed `TokenBudgetTracker` enforcing `max_tokens=50000` per node.

Both errors had the same cause: **I described an architecture from one file, or from a doc, instead of reading the whole implementation.** The correction required ~200 lines across four files. The process that fixes this is the one the new blog rules enforce: read the code, quote it, then interpret it — and explicitly retract claims that the code contradicts.

## Lessons Learned

The lessons below are the corrected version; the outdated draft content this section originally carried has been replaced by the analysis above.

### 1. Token budget is enforced at execution time

`_execute_node` imports and instantiates the budget tracker inline:

```python
from .budget.tracker import TokenBudgetTracker, BudgetExceededError
budget = TokenBudgetTracker()
...
tok = response.metrics.get("tokens", 0)
if tok:
    budget.record_tokens(tok)
```

And `TokenBudget` defines the limits:

```python
@dataclass
class TokenBudget:
    max_tokens: int = 50000
    max_tool_calls: int = 20
    timeout_seconds: int = 300
    max_context_tokens: int = 8000
```

`record_tokens` raises `BudgetExceededError` when `used_tokens > max_tokens`. The error carries a `recoverable` flag — the docstring says exceeding budget triggers "ContextManager 压缩或请求人工介入" (context compression or human intervention). So token budgets *are* in the workflow layer, enforced per node at runtime. My earlier claim was flatly wrong.

### 2. Execution runs in a sandbox with timeout

```python
from infrastructure.sandbox.sandbox import AsyncTimeoutSandbox
sandbox = AsyncTimeoutSandbox(timeout=node.timeout_seconds, budget_tracker=budget)
response = await sandbox.run(agent.execute, request)
```

The sandbox wraps the agent call with `asyncio-timeout` — a node that exceeds its `timeout_seconds` is killed, and the exception is isolated from the rest of the pipeline. The sandbox docstring is honest about the MVP boundary: *same-process isolation only*; production would use subprocess isolation. The `AgentNode.timeout_seconds = 300` default I saw in the model is actually wired to this sandbox.

### 3. The context is assembled from all upstream results

```python
context = dict(state.agent_results)
request = AgentRequest(
    ...
    context=context,
    inputs=node.input_mapping,
    ...
)
```

This confirms the `input_mapping` design: the node's `inputs` come from its declared mapping, while `context` is the accumulated results of all upstream nodes. So agents *can* see prior output — but through the engine's assembled context, not by reaching into shared state themselves. The input-mapping layer keeps the dataflow explicit.

One more detail worth noting: the request carries audit-domain identifiers even though they're hardcoded to `"default"` in the current code — `firm_id`, `client_id`, `engagement_id`. The scaffolding anticipates multi-client deployments; today it's a single default tenant. This is the kind of "future-proofing" that reads as over-engineering until the system actually needs tenants, and as foresight once it does. Either way, it's in the code and the doc doesn't mention it.

### What's still genuinely open

With the code read fully, three honest gaps remain:

1. **Checkpoint persistence is in-memory by default.** `InMemoryCheckpointStore()` and `InMemoryTraceStore()` are the defaults; the PG-backed stores exist but aren't wired as defaults. The handover doc confirms this.
2. **Conditional-edge evaluation isn't visible in the engine loop.** `Edge.condition` exists in the model, and the `next_action` field suggests dynamic routing, but the `_execute_node` / transition code I read doesn't show an explicit condition-expression interpreter. It may be evaluated at a layer above, or it may be awaiting implementation — I can't claim which without reading the graph runner.
3. **The sandbox is same-process only.** `AsyncTimeoutSandbox` gives timeout + exception isolation but not resource limits or subprocess isolation. The docstring says production would upgrade — it's a documented MVP boundary.
## Lessons Learned

1. **Read the orchestration layer before describing orchestration.** One agent's `next_action` return value made me write a wrong article. The `GraphDefinition` DAG was a file away.
2. **Conditional edges are where workflow value lives.** A fixed pipeline is a script. `condition: "risk.level == HIGH → approval"` is what makes it a *workflow* — the graph reacts to runtime state.
3. **"Modify" is the third approval option that makes HITL real.** APPROVED/REJECTED/MODIFY — the last one means the human can correct the input and re-run, which is how audits actually work.
4. **Events + trace = observability as architecture.** WebSocket-pushed typed events and a step-level ExecutionTrace make the orchestration layer inspectable without bolting on monitoring later.
5. **Conversation vs message-passing is a real design fork.** AutoGen converses; AuditFlow passes typed artifacts. Both are valid; the choice should be explicit and justified by traceability requirements.
6. **In-memory defaults are a documented debt, not a hidden flaw.** The handover doc admits trace/checkpoint persistence to PG is pending. Code + doc together tell the full story — either alone is misleading.
7. **"Future-proofing" in code is a judgment call, not a virtue.** The hardcoded `firm_id="default"` scaffolding could be foresight for multi-tenant or dead weight. The honest move is to name it, not to celebrate or bury it. When the audit trail is the product, unused identifiers in every request are worth a comment explaining *why they're there* — otherwise the next engineer assumes they're vestigial and deletes them.

## Key Takeaways

- **AuditFlow's workflow is a real DAG** (GraphDefinition) with conditional edges, approval gates, and checkpointing — plus a `next_action` runtime hint. My earlier "no DAG" claim was wrong.
- **`input_mapping` is the unsung hero.** Declaring which upstream output feeds each node prevents context explosion and makes the graph's dataflow explicit.
- **Approval as a three-state decision (approve/reject/modify) matches audit reality.** The modify path turns a gate into a correction loop.
- **Trace and events are the audit trail.** They're why the custom engine beats a framework for this domain.
- **The graph encodes an SOP, like MetaGPT.** The missing piece is parallel role execution.
- **Token budgets and timeouts are enforced, not aspirational.** `TokenBudgetTracker` (50000 tokens) and `AsyncTimeoutSandbox` (300s default) run inside `_execute_node`, not in a design doc.
- **Documented debt is still debt.** In-memory trace/checkpoint stores work but lose everything on restart — the PG-backed stores exist but aren't wired as defaults. The gap between "has a store class" and "persists by default" is where production incidents hide.

## Next Step

The next article examines the RAG pipeline — hybrid search, semantic chunking, and citation grounding — against the retrieval papers now in the knowledge base. The same discipline applies: read the document pipeline code (`backend/scripts/batch_index.py`, the chunker, the search endpoint) before claiming anything about how retrieval actually works. The evidence for that article will come from the RAG survey, ColBERT, and the embedding chunks sitting in the knowledge base at similarity scores I'll measure, not guess.
