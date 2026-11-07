# [Feature/Bugfix Name] Plan

**Plan Status**: `FINAL` or `DRAFT - BLOCKED`

**Story Type**: `Internal` or `Integration`

> This plan captures **what** to build and **why** — domain, architecture, decisions, and verified facts.
> It deliberately does **not** contain implementation code, pseudocode, line numbers, mock setups, or test bodies.
> The implementation agent discovers the **how** against live code. See §4 Task Breakdown.

Status rules:
*   `FINAL` requires: no unresolved Open Questions (§3.2), no `Assumption` left in Contract Evidence (§2.2), and every row in the §6 Fact-Integrity Checklist passing.
*   `DRAFT - BLOCKED` when any of the above is open. Each blocker must map to an Open Question with an owner.

Filename rule:
*   Path: `docs/specs/plans/{work_item_id}-{short-slug}.md`.
*   Title Case for major words; lowercase minor words (`a`, `an`, `the`, `and`, `or`, `but`, `for`, `nor`, `on`, `at`, `to`, `from`, `by`, `with`, `in`, `of`) unless first or last.
*   Example: `430344-Resource-Based-ACL-for-Contact-Information.md`.

---

## 1. Problem Statement

*   **Context**: What is the current state? What is missing or broken?
*   **Goal**: What are we trying to achieve?
*   **In scope / Out of scope**: Call out boundaries when relevant.

### 1.1 Technical Summary

*3–5 bullets orienting a developer before they read §2. Answer "what we're building", not "why".*

*   **Touched services/projects**: e.g. `<Service>` (API), `<Service>.Application`
*   **New patterns / abstractions**: e.g. pipeline behaviour, ACL provisioning, retry policy
*   **Infrastructure changes**: e.g. new DB table, new Service Bus subscription — or `None`
*   **End-state observable behavior**: e.g. ACL resource provisioned on first contact access; access enforced via `IAcl4ResourcesEnforcer`

---

## 2. Architecture & Design

*Conceptual and durable. No code, no pseudocode, no line numbers. Describe the design; let the implementation agent write it.*

### 2.1 Architecture Overview

#### Involved services & owners

| Service | Technical Owner |
| :--- | :--- |
| `<Service>` | … |

#### C2 diagram

Mermaid diagram of dependencies between the involved services and modules.

#### Flow diagram

Mermaid sequence/flow of the happy path only — no error branching. Hide infrastructure plumbing (Mediator, pipeline behaviours, controllers) unless essential to the design.

### 2.2 External Contracts & Evidence

> **Integration stories only.** For Internal stories, state `N/A — Internal story` and skip the tables below.
> For Integration stories, this section MUST be completed (contracts retrieved and verified) **before** §2.3 and §2.4 are drafted.

#### Retrieval Manifest

How each external contract artifact was retrieved. The first row records the mandatory `Explore` (thorough) discovery pass; follow-up rows record concrete ADO/source retrieval.

| Ref | Artifact Category | Retrieval Method | Source Path / Query | Status |
| :--- | :--- | :--- | :--- | :--- |
| `M1` | Event / DTO / route contract | `Explore` (thorough) | `repo/path/or-query` | `Found` / `Missing` |
| `M2` | … | `ADO MCP` follow-up | `repo/path` | `Found` / `Missing` |

#### Contract Evidence

One JSON block per artifact. The block header carries the manifest ref, the source, and the status. Record only what the contract source explicitly states.

```json
// [M1] — External.SystemA — EntityUpdated event — Verified
// Source: path/to/EventContracts/EntityUpdated.cs
{
  "EntityIdentifier.SourceId": "string",
  "EntityIdentifier.TargetId": "string"
}
```

For unresolved items, replace the source with a gap description and link the Open Question:

```json
// [M2] — External.SystemA — SomeEvent — Assumption (see OQ-1)
// Gap: contract file not accessible; payload type id assumed from class name
{
  "SomeField": "string (assumed)"
}
```

**Summary**: `All Verified` / `N verified, M assumption(s) — see OQ-…`

Rules:
*   `Verified` only when confirmed from producer source code, an explicit API contract, or official docs — never from story text alone when producer code exists.
*   Source comments must be reproducible (exact repo file path, optionally a symbol). `subagent search result` is not valid evidence.
*   **Structure ≠ meaning.** A verified field does not prove its business meaning. Identifier directionality, ownership, ordering, and freshness semantics must be evidenced separately (a caller / usage example / test) or recorded as an Open Question.
*   Never infer field names, types, or semantics. Any `Assumption` block must have a matching §3.2 Open Question, and blocks the plan from `FINAL`.
*   Label local types derived from a contract: `mirror of external contract` (contains every verified field) or `consumed subset` (list each omitted field). Do not call a type a mirror if any verified field is omitted.

#### Source Conflict Log

If story text, external contracts, and current repository behaviour disagree, record it. State `No conflicts found` if none.

| Topic | Source A | Source B | Conflict | Chosen Handling |
| :--- | :--- | :--- | :--- | :--- |

The `Chosen Handling` must be reflected consistently in §2.4 and §4. Do not silently blend sources.

### 2.3 Affected Areas

A map of the code most likely involved — pointers for the implementation agent, **not** a transcription checklist. Describe the role each area plays; do not prescribe exact edits or line numbers.

| Area / File (pointer) | Role in this change | Likely action |
| :--- | :--- | :--- |
| `Path/To/Area.cs` | What it does and why it is relevant here. | New / Change / Reference |

### 2.4 Key Algorithms & Behaviour

The non-trivial logic at a conceptual level — decision trees, ordering rules, idempotency, error and no-data behaviour. **State the rule, not the code.**

For flows that depend on ordering or freshness, separate explicitly:
*   **Ordering source**: which contract field determines freshness.
*   **Initialization source**: which value is used during bootstrap.
*   **No-data behaviour**: `Skip` / `Persist null + version` / `Retry` / `Dead-letter`, and why.

A field appearing in a contract does not prove its business meaning. Any field used for freshness, ordering, ownership, or identifier directionality must have explicit semantic evidence (§2.2) or be an Open Question (§3.2) — never assumed from a field name or type shape.

---

## 3. Key Decisions & Assumptions

Record non-obvious choices so future maintainers understand the "why".

*   **Decision**: One concrete chosen approach + rationale. For a `FINAL` plan, do not hedge with "option A or option B" — pick one. Alternatives may appear only in `DRAFT - BLOCKED`.
*   **Assumption**: What was taken for granted and why. Every assumption that affects correctness must have a matching Open Question (§3.2).

### 3.1 Decision Lock (Constants & Policies)

When a value or policy is fixed for implementation, record it explicitly so it does not drift during implementation.

| Constant / Policy | Selected Value | Why | Where it lives |
| :--- | :--- | :--- | :--- |
| Relation type | `IsSupplierOf` | Example rationale | Handler / client |
| Missing-data policy | `Persist null + version` | Example rationale | Handler flow |

### 3.2 Open Questions

Genuinely unresolved points that can affect correctness. **Before** creating one, attempt resolution from: (1) AC text, (2) an existing equivalent handler in the local codebase, (3) local registration/config files, (4) callers/usage examples in the external repo, (5) shared-library source. If the answer is found, close it and record the fact — do not create an Open Question. An OQ without a documented resolution attempt is invalid.

| Question | Impact if wrong | Resolution Attempt | Owner / Follow-up |
| :--- | :--- | :--- | :--- |
| … | … | Sources checked and why none answered | Named owner + target date |

For `FINAL` plans, this section must be empty (or state `No open questions.`).

---

## 4. Task Breakdown

The implementable units of work. Each task is a **medium-sized, independent slice** — something an agent can build from beginning to end and verify on its own. Order by dependency; mark `Depends on` so the orchestrator can run independent tasks in parallel.

**The implementation agent owns the *how*** — it reads live code, designs the implementation, and writes the code and the tests. This breakdown gives it the *what* and the done-criteria, not the code.

Each task carries a **Complexity** tier that selects which model implements it (the orchestrator maps tier → model: `Low`→haiku, `Medium`→sonnet, `High`→opus):
*   **`Low`** — mechanical/trivial and well-specified: a constant, DI registration, a simple extension method, a straightforward mapping or boilerplate test.
*   **`Medium`** *(default)* — standard implementation needing design judgment: a handler, a strategy class, a pipeline behaviour, non-trivial tests. When unsure, choose this.
*   **`High`** — very complex, **critical**, or touching the **domain core** where a mistake is costly and deep understanding is required: concurrency/ordering, external-contract semantics, aggregate invariants, several interacting components.

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| `T1` | … | — | `Low` |
| `T2` | … | `T1` | `Medium` |
| `T3` | … | — | `High` |

### T1 — [Short title]

*   **Goal**: One or two sentences — the observable outcome of this task.
*   **Depends on**: `—` (or `T?`).
*   **Complexity**: `Low` / `Medium` / `High` — be honest; over-rating wastes budget, under-rating risks a cheap model on hard work.
*   **Pointers**: Files/areas likely involved (from §2.3); links speed the agent up.
*   **Definition of Done**: Concrete, checkable conditions (behaviour exists, wired in DI, toggle-gated, bicep updated, etc.).
*   **Tests expected**: High-level — which layer (unit / integration) and which behaviours to cover. Name the behaviour, not the test method. (If the task touches `Application/_Shared/HttpClients`, integration tests with `WireMock.Net` covering happy path + one error/no-data path are expected.)

### T2 — …

*(repeat per task)*

---

## 5. Verification

How to confirm the whole change once all tasks are `Done`.

*   **Build**: `dotnet build <Solution>.sln` — no errors, no nullable warnings.
*   **Unit Tests**: `dotnet test test/<Service>.UnitTests` — all green.
*   **Integration Tests**: `dotnet test test/<Service>.IntegrationTests` — all green (when applicable).
*   **Observable behaviour**: HTTP responses, DB rows, outbox rows, queue messages that demonstrate the goal is met.

---

## 6. Fact-Integrity Checklist

A short self-check on the facts the plan rests on — not a process audit. Mark `Yes` / `No` / `N/A`.

| Check | Yes / No / N/A | Notes |
| :--- | :--- | :--- |
| External contracts (routes, payload type ids, DTO fields, identifier types) verified from producer/contract source — not story text | | Integration only; else `N/A` |
| Evidence sources are reproducible (exact repo file path/symbol) | | Integration only; else `N/A` |
| Identifier directionality / ordering / freshness **meaning** evidenced separately from field shape, or moved to an Open Question | | Integration only; else `N/A` |
| Every `Assumption` is linked to an Open Question (§3.2) | | |
| No unresolved Open Questions (for `FINAL`) | | |
| Each Decision states a single committed approach | | |
| Tasks are independent, each with a Definition of Done and test expectations | | |
| Required infra reflected: toggle-gated where the story carries a toggle key; new Service Bus subscription/queue ⇒ a task updates `infrastructure.bicep` | | A missing bicep entry causes `MessagingEntityNotFound` at runtime |

**Self-review note**: 2–4 sentences — what was uncertain, what was assumed, and where the implementation agent should take extra care.
