# Compiler: Allow `return` Anywhere in a Function Plan

**Plan Status**: `FINAL`

**Story Type**: `Internal`

**Plan Revision**: `A0`

> This plan captures **what** to build and **why** — domain, architecture, decisions, and verified facts.
> It deliberately does **not** contain implementation code, pseudocode, line numbers, mock setups, or test bodies.
> The implementation agent discovers the **how** against live code. See §4 Task Breakdown.

---

## 1. Problem Statement

*   **Context**: Issue #20 (analysis problem 6, `bugs.txt`) says `return` only works as the last
    statement of a function, because `STATEMENT_RETURN.emit` emits `ret` and so skips the
    function epilogue (`pop_scope('FUNC')`), which it says moves `sys_stackhead` back at run time.
    bdos works around it with a `result` variable. The issue proposes an epilogue label and a jump.
*   **Verified on master (855e7bb), before planning — the described bug does not reproduce:**
    *   Under the current code model (design decision C2), the **caller** moves `sys_stackhead`:
        `EXPRESSION_CALL.emit` pushes a scope (emits `STACKHEAD += n`), stores the arguments, `cal`s,
        and pops the scope (emits `STACKHEAD -= n`). The callee's `FUNC` scope starts at offset 0
        from the global scope (the compiler has no globals). So `pop_scope('FUNC')` computes a
        difference of 0 and **emits no run-time code**. An early `ret` skips nothing.
    *   Compiled `src/bc/code/funrec.b`: the function body has no stack-head code after the
        function's own statements, and each function that ends with `return` ends with **two `ret`s**
        (the `return`'s and the epilogue's). The second one is dead code: 1 byte per such function.
    *   Emulator probes (built os.bdd, a B program run as `E2EPROG.PRG`, the e2e
        `bdio_buffered` model): `return` from inside `if`-in-`if`-in-`while`-in-`while`, from 3-deep
        nested `if`/`else` on every branch (7 paths), from a `byte` function whose only returns are in
        nested `else` branches, and from recursive functions returning at several nesting levels
        (`fact(6)` = 720, `fib(10)` = 55, a 3-level recursive `deep(5)` = 1112) all returned the right
        values, and the caller's locals set before and after the calls were intact.
    *   The comment `# context.pop_scope('RET')` in `STATEMENT_RETURN.emit` is a leftover of an older
        model where the callee moved the stack head; the docs and `bugs.txt` were never updated.
*   **Goal**: make the "return anywhere" guarantee explicit and tested, remove the dead second
    `ret`, keep `return` correct once block scopes (#24) arrive, and drop the restriction from the docs.
*   **In scope**: compiler epilogue (dead `ret`), a compile-time guard for `return` under an inner
    run-time scope, codegen unit tests, an e2e emulator test, docs and a design decision, the size record.
*   **Out of scope**: rewriting bdos/app code that uses the `result`-variable workaround (it works and
    is not asked for; a follow-up may simplify it); block scopes themselves (#24); `bc_dbg.py`.

### 1.1 Technical Summary

*   **Touched projects**: `src/bc/bc_ast.py` (compiler), `src/bc/tests/`, `src/tests/` (e2e),
    `src/bc64/testdata/e2e/` (e2e B program), docs.
*   **New patterns / abstractions**: none. A compile-time invariant check in `STATEMENT_RETURN`.
*   **Infrastructure changes**: None.
*   **End-state observable behavior**: `return` works anywhere in a function body (it already does,
    now pinned by tests); a function whose last statement is `return` ends with one `ret`, not two
    (every program shrinks; trial: −292 B over all programs, e.g. bdos −37, texted −28);
    the docs no longer state the restriction.

---

## 2. Architecture & Design

### 2.1 Architecture Overview

#### Involved services & owners

| Service | Technical Owner |
| :--- | :--- |
| compiler `bc` (`src/bc/`) | repo owner (bcichonski) |

#### C2 diagram

```mermaid
flowchart LR
  B[.b source] --> BC[bc: bc_grammar + bc_ast]
  BC --> BASM[.basm]
  BASM --> ASM[bc81asmc] --> BIN[.btap/.sectors] --> DISC[os.bdd]
  DISC --> EMU[bc64 emulator e2e test]
```

#### Flow diagram

```mermaid
sequenceDiagram
  participant Caller
  participant Callee
  Caller->>Caller: STACKHEAD += caller frame size (push scope)
  Caller->>Caller: store arguments as callee locals
  Caller->>Callee: cal
  Callee->>Callee: statements; return expr -> csci, ret (from any depth)
  Callee-->>Caller: ret
  Caller->>Caller: STACKHEAD -= caller frame size (pop scope)
```

### 2.2 External Contracts & Evidence

N/A — Internal story.

#### Source Conflict Log

| Topic | Source A | Source B | Conflict | Chosen Handling |
| :--- | :--- | :--- | :--- | :--- |
| Root cause | Issue #20 / analysis problem 6: early `ret` skips the `FUNC` epilogue that restores `sys_stackhead` | Live code + emulator probes (§1) | The epilogue emits no run-time code; the caller restores the stack head | Treat the bug as already fixed in code; deliver tests, the dead-`ret` removal, a guard for #24, and docs. The issue's epilogue-label + jump proposal is **not** implemented (it is a proposal, not an AC) — flagged in the PR (D1). |

### 2.3 Affected Areas

| Area / File (pointer) | Role in this change | Likely action |
| :--- | :--- | :--- |
| `src/bc/bc_ast.py` — `FUNCTION_DECLARATION.add_code` | Emits the function label, the body and the epilogue (`pop_scope('FUNC')` + `ret`) | Change: no trailing `ret` when the body's last top-level statement is a `return` |
| `src/bc/bc_ast.py` — `STATEMENT_RETURN.emit` | Evaluates into `csci`, emits `ret` | Change: compile-time guard (D3); drop the stale commented-out line |
| `src/bc/bc_ast.py` — `Context.push_scope`/`pop_scope`, `Scope` | Scope depth/offsets; `FUNC` scope is depth 1 | Reference |
| `src/bc/tests/bc_codegen_tests.py` (helpers `compile_source`, `function_lines`) | Codegen tests | Reference / new test file or class |
| `src/tests/test_e2e_bdio_buffered.py`, `src/tests/e2e_harness.py` | Model for compiling a B program, `disc_put` onto a temp os.bdd, running it headless | Reference |
| `src/bc64/testdata/e2e/` | Home of e2e B programs (`bdio_buffered_prog.b`) | New program |
| `scripts/code_size.py`, `src/bc/code_size.csv` | Size report (#15) | `--record` the new sizes |
| `src/bc/bugs.txt`, `docs/03-compiler.md`, `src/bc/CLAUDE.md`, `src/bdos/CLAUDE.md`, `docs/analysis/03-compiler.md`, `docs/specs/memory/design-decisions.md` | Docs stating the restriction / design decisions | Change |

### 2.4 Key Algorithms & Behaviour

*   **Return semantics (unchanged):** `return e` evaluates `e` into `csci` and executes `ret`, from any
    nesting depth. The callee never moves `sys_stackhead`; the caller does, around the `cal` (C2).
*   **Epilogue rule:** after the body, the function emits `ret` **unless** the body's last top-level
    statement is a `return` (then that `ret` is the last instruction already). Only the last
    top-level statement counts: a body ending in `if/else` with returns in both branches still gets
    the trailing `ret` (conservative; no flow analysis). A body with no statements, or ending in
    anything else, keeps the trailing `ret`. `pop_scope('FUNC')` still runs at compile time in all
    cases (it restores the compiler's scope chain; it emits nothing for a `FUNC` scope).
*   **Guard (D3):** when `return` is compiled while the current scope is not the function's own scope
    (i.e. an inner scope that moved the stack head at run time is open), compilation fails with a
    `CompilerError` naming the problem (return would skip unwinding the inner scope; see #24).
    Today no B source can reach it (blocks open no scope; call scopes close before the next
    statement), so it changes no output; it makes #24 fail loudly instead of silently corrupting
    the stack head.
*   **`main`:** unchanged; the entry point `cal`s main and then `kil`/`ret`s.

---

## 3. Key Decisions & Assumptions

*   **D1 — No epilogue label/jump.** Evidence in §1 shows `return` already works anywhere. Adding a
    jump to a shared epilogue would grow every early return for no gain today. The issue's second
    bullet (block scopes must unwind) is covered by the D3 guard plus decision C8, which tells #24
    to add the single unwinding path when it introduces run-time block scopes.
    *Deviates from the issue's Proposal section (not from its AC)*; flag it in the PR.
*   **D2 — Remove the dead trailing `ret`.** Satisfies AC 2 ("don't grow") strictly better: they
    shrink by 1 B each. Trial patch on master: all 105 compiler tests pass, full build OK,
    `code_size.py` −292 B total (deltas against the CSV's latest rows). Code size is the
    optimisation metric (C4).
*   **D3 — Compile-time guard in `STATEMENT_RETURN`** (see §2.4). No bytes, no output change.
*   **D4 — New design decision `C8`** in `docs/specs/memory/design-decisions.md` (last compiler id
    on master is C7): "`return` is a direct `ret` from any depth; the caller owns the frame; a
    function ends with one `ret`; a future run-time block scope (#24) must unwind on `return`
    (the guard enforces it)". C2's usage bullets stay true. Before the PR, re-check that
    `origin/master` hasn't taken C8 meanwhile (parallel stories collide on ids); renumber if so.
*   **D5 — e2e test asserts values directly** (known numbers in the test), no golden file needed;
    a golden is fine too if the agent prefers the harness's `check_golden` pattern.
*   **Assumption A1** — AC 1 "leaves `sys_stackhead` correct" is checked by the e2e program reading
    the `sys_stackhead` word (via an `asm` line, e.g. a small B function returning it in `csci`)
    before and after the nested-return calls in `main`, plus caller locals intact. Low stakes; no OQ.
*   **Assumption A2** — bdos's `result`-variable code is left as is (not in the AC).
    `src/bdos/CLAUDE.md`'s quirk bullet is reworded to say early `return` is fine; the existing
    style is not required anymore.

### 3.1 Decision Lock (Constants & Policies)

| Constant / Policy | Selected Value | Why | Where it lives |
| :--- | :--- | :--- | :--- |
| Trailing `ret` policy | Omitted only when the last top-level body statement is `return` | No flow analysis; exact and safe | `FUNCTION_DECLARATION.add_code` |
| Guard error | `CompilerError`, reported like other compiler errors (`file: error: …`, exit 1 from the CLI) | Same channel as other internal errors (C6) | `STATEMENT_RETURN.emit` |
| Design decision id | `C8` (renumber if master took it) | Next free compiler id | `docs/specs/memory/design-decisions.md` |

### 3.2 Open Questions

No open questions.

---

## 4. Task Breakdown

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| `T1` | Compiler: single trailing `ret`, return guard, codegen tests, size record | — | `Medium` |
| `T2` | e2e test: early returns in the emulator keep values and `sys_stackhead` | `T1` | `Medium` |
| `T3` | Docs: drop the restriction, decision C8 | `T1` | `Low` |

T2 depends on T1 only to serialise builds (two agents must not build in one worktree at once);
T3 is docs-only and may overlap with T2.

### T1 — Compiler: single trailing `ret`, return guard, codegen tests, size record

*   **Goal**: functions whose last top-level statement is `return` end with exactly one `ret`;
    `return` under an inner run-time scope is a compile error; behaviour pinned by unit tests.
*   **Depends on**: —
*   **Complexity**: `Medium`
*   **Pointers**: `src/bc/bc_ast.py` (`FUNCTION_DECLARATION.add_code`, `STATEMENT_RETURN.emit`,
    `Context.push_scope`/`pop_scope`); `src/bc/tests/bc_codegen_tests.py` helpers; `scripts/code_size.py`.
*   **Definition of Done**:
    *   §2.4 epilogue rule and guard implemented; the stale `# context.pop_scope('RET')` comment removed.
    *   Full build passes (`cd src && ./buildos && ./buildtools && ./buildapps && ./makedisc`).
    *   `python3 scripts/code_size.py --record` run once after the final build; only the appended
        rows are committed in `src/bc/code_size.csv` (append-only; never edit older rows).
    *   Compiler suite and the full `python3 run_tests.py < /dev/null` pass.
*   **Tests expected** (compiler unit, new tests in `src/bc/tests/`, new file or new class):
    *   a function ending in `return` ends with one `ret` (no two consecutive `ret`s at the end);
    *   a function with no `return` / ending in another statement still ends with `ret`;
    *   a function ending in `if/else` with returns in both branches still ends with a trailing `ret`;
    *   `return` inside nested `if` / `while`: the `ret` follows the return expression, and the
        function body contains no `stackheadrll8`/`stackheadroll` call other than those around
        its own calls (the callee never moves the stack head);
    *   the guard: compiling a `STATEMENT_RETURN` while an extra scope is pushed on a `Context`
        raises `CompilerError`.
*   **Tests to modify**: None (the trial patch passed all 105 existing compiler tests unchanged).

### T2 — e2e test: early returns in the emulator keep values and `sys_stackhead`

*   **Goal**: AC 1: an end-to-end test runs a B program in the emulator that returns from nested
    `if`/`else`/`while` and from recursion, and checks results, caller locals and `sys_stackhead`.
*   **Depends on**: `T1`
*   **Complexity**: `Medium`
*   **Pointers**: `src/tests/test_e2e_bdio_buffered.py` (compile → assemble → `btap2bin` →
    `h.disc_put` → `h.run_session`), `src/tests/e2e_harness.py`, `src/bc64/testdata/e2e/`.
    The §1 probe programs are a good model (nested-loop search, 3-deep if/else classifier,
    `byte` function returning only from nested `else`s, recursive `fact`/`fib`/multi-level returns).
*   **Definition of Done**:
    *   new B program under `src/bc64/testdata/e2e/` and a new `src/tests/test_e2e_*.py` test that
        builds and runs it on a temp copy of `h.OS_DISK`, and asserts every printed value;
    *   the program prints `sys_stackhead` before and after the calls in `main`; the test asserts
        they are equal; caller locals set before the calls are printed afterwards and asserted;
    *   uses `h.assert_markers` so an empty/truncated output can't pass;
    *   `python3 run_tests.py < /dev/null` passes; `git status` clean apart from the new files
        (CI's e2e job fails on any tracked-file change).
*   **Tests expected**: the e2e test above (one emulator session; keep it fast, it's in the e2e suite).
*   **Tests to modify**: None.

### T3 — Docs: drop the restriction, decision C8

*   **Goal**: AC 3: `bugs.txt`, `docs/03-compiler.md` and `src/bc/CLAUDE.md` no longer state the
    restriction; the design decision is recorded.
*   **Depends on**: `T1`
*   **Complexity**: `Low`
*   **Pointers**: `src/bc/bugs.txt` (first line), `docs/03-compiler.md` (the `bugs.txt` paragraph
    near the return-value bullet), `src/bc/CLAUDE.md` (last "Language quirks" bullet),
    `src/bdos/CLAUDE.md` ("B quirks" `result` bullet), `docs/analysis/03-compiler.md` (problem 6 row
    and improvement 7.1: mark resolved by #20 with the real cause), `docs/specs/memory/design-decisions.md` (new C8 after C7).
*   **Definition of Done**:
    *   the `bugs.txt` line is removed; `docs/03-compiler.md` says `return` may appear anywhere and
        explains why it is safe (caller-owned frame, C2/C8) and that a function ends with one `ret`;
    *   `src/bc/CLAUDE.md` quirk bullet removed (or replaced by a pointer to C8);
    *   `src/bdos/CLAUDE.md` bullet reworded: early `return` is fine; existing `result` code may stay;
    *   C8 per D4, in the same format as C1–C7 (Purpose, Rationale, Usage, Trade-offs);
    *   no edits outside these statements (don't touch other decisions' text).
*   **Tests expected**: none (docs). `python3 run_tests.py --group unit < /dev/null` still passes.
*   **Tests to modify**: None.

---

## 5. Verification

*   **Build**: `cd src && ./buildos && ./buildtools && ./buildapps && ./makedisc` — exit 0.
*   **Tests**: `python3 run_tests.py < /dev/null` from the repo root — exit 0; report expected
    failures (if any remain on master) by name, never as "all passed".
*   **Size (AC 2)**: `python3 scripts/code_size.py` shows every program ≤ its previous size; paste
    the table into the PR. Appended rows in `src/bc/code_size.csv`.
*   **Observable behaviour**: the new e2e test passes; `grep -c` on a built `.basm` finds no
    `ret` immediately followed by `ret` at a function end.
*   **Docs (AC 3)**: `grep -rn "last statement\|nested blocks" src/bc/bugs.txt src/bc/CLAUDE.md docs/03-compiler.md` finds nothing about the restriction.

---

## 6. Fact-Integrity Checklist

| Check | Yes / No / N/A | Notes |
| :--- | :--- | :--- |
| External contracts verified from producer/contract source | N/A | Internal |
| Evidence sources are reproducible | N/A | Internal; §1 probes reproducible from the T2 model |
| Identifier directionality / ordering / freshness meaning evidenced | N/A | Internal |
| Every `Assumption` is linked to an Open Question (§3.2) | Yes | A1/A2 are low-stakes, no correctness impact |
| No unresolved Open Questions (for `FINAL`) | Yes | |
| Each Decision states a single committed approach | Yes | |
| Tasks are independent, each with a Definition of Done and test expectations | Yes | |
| Required infra reflected | N/A | |

**Self-review note**: The main risk was the issue's root-cause claim; it was disproved by reading
`pop_scope` and by three emulator probes (nested loops, nested if/else, recursion). The plan
therefore deviates from the issue's *proposal* (no epilogue jump), not from its AC. T1 must keep
`pop_scope('FUNC')` running in every case (compile-time scope chain), and must not drop a `ret`
when the last statement only *contains* returns. Watch the C8 id against parallel stories.

---

## 7. Amendment Log

| Revision | Request | Decision | Plan changes |
| :--- | :--- | :--- | :--- |
