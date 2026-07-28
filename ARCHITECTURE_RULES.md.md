# ARCHITECTURE_RULES.md

# Purpose

This document defines the architectural evolution rules of this project.

Unlike ARCHITECTURE.md, which describes the current system,
this document defines what changes are allowed and how architectural decisions should be made.

ARCHITECTURE.md is the source of truth.

These rules protect that architecture from uncontrolled evolution.

---

# Core Philosophy

Architecture exists to reduce long-term complexity.

Never sacrifice maintainability for short-term implementation speed.

Every architectural change should have a measurable benefit.

If a change cannot clearly improve the system, do not make it.

---

# Source of Truth

The following documents have descending priority.

1. PRD.md
2. ARCHITECTURE.md
3. ARCHITECTURE_RULES.md
4. AGENTS.md

If conflicts exist:

Do not guess.

Raise an Architecture Change Proposal (ACP).

---

# Architecture Stability

Assume the architecture is stable.

Do NOT:

- invent new layers
- invent new architectural patterns
- rename modules
- reorganize directories
- merge unrelated responsibilities
- split modules without justification

Every implementation should fit into the existing architecture.

---

# Layer Dependency Rules

Allowed dependencies:

Presentation
↓

Application
↓

Domain
↓

Infrastructure

Reverse dependency is forbidden.

Domain must never depend on Infrastructure.

Business logic must never live in:

- Controllers
- API
- Routers

Infrastructure must not contain business decisions.

---

# Module Boundaries

Every module should have a single responsibility.

Avoid:

God classes

Utility dumping grounds

Shared helper folders

Large service objects

If a module grows too large,
propose a redesign instead of continuing to expand it.

---

# AI Components

Every Agent should communicate through defined interfaces.

Agents should never:

- access databases directly
- call internal repositories directly
- bypass workflow orchestration
- manipulate infrastructure objects

All interactions should be explicit.

---

# Workflow Rules

Workflow is responsible for orchestration.

Business logic belongs to services.

LLMs should never coordinate the workflow themselves.

Workflow should remain deterministic whenever possible.

---

# Data Access Rules

Only Repository layer accesses persistence.

Never:

SQL inside services

SQL inside Agents

SQL inside Controllers

Caching should also be abstracted.

---

# External Dependencies

Before introducing any new dependency:

Generate a Technology Proposal.

Include:

Purpose

Alternatives

Maintenance cost

Community maturity

Performance impact

Security impact

Migration difficulty

Recommendation

Never introduce libraries "because they are popular."

---

# Introducing New Components

Adding any of the following requires justification:

- new service
- new agent
- new database
- new cache
- new queue
- new storage
- new framework
- new layer

Explain:

Why existing components cannot solve the problem.

---

# Architecture Change Proposal (ACP)

When architecture must change:

Stop implementation.

Generate an ACP.

Template:

## Background

Current limitation.

---

## Problem

Why current architecture is insufficient.

---

## Alternatives

Option A

Pros

Cons

Option B

Pros

Cons

---

## Recommendation

Preferred solution.

Reasoning.

---

## Impact

Affected modules.

Migration cost.

Backward compatibility.

---

## Risks

Technical risks.

Maintenance risks.

Future complexity.

Implementation resumes only after approval.

---

# Technical Debt

Every architectural shortcut must be documented.

Examples:

Temporary abstraction

Performance compromise

Known limitation

Future refactoring

Never hide technical debt.

---

# Scalability

Prefer solutions that scale naturally.

Avoid introducing distributed complexity before it is necessary.

Monolith first.

Modular monolith before microservices.

Only distribute when there is evidence.

---

# Documentation

Every architectural decision should update:

ARCHITECTURE.md

ADR

Engineering Journal

Changelog

Architecture documentation is part of the implementation.

---

# Architecture Review

Before completing any feature, verify:

Does it follow existing architecture?

Does it increase coupling?

Does it reduce cohesion?

Does it duplicate responsibilities?

Does it introduce unnecessary abstractions?

Would a new developer understand this design?

If the answer is "No",

revise the implementation.

---

# Success Criteria

Architecture should become simpler over time.

Not more complicated.

Every new feature should make the system easier to understand rather than harder.

Architecture is considered successful when future changes become easier, not harder.