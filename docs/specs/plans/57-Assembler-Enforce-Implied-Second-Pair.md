# Assembler: enforce the implied second pair in 16-bit register-pair ops — Plan

**Plan Status**: `FINAL`

**Story Type**: `Internal`

**Plan Revision**: `A0`

> This plan captures **what** to build and **why**. The implementation agent discovers the **how** against live code.

---

## 1. Problem Statement

*   **Context**: the 16-bit register-register form of `CLC` (`add csci, dsdi`, encoding `5F k8 pq`) carries both pairs: the first in the high nibble `p` and the second in the low nibble `q` of the third byte. The CPU (`op_CLC`, `CLC_EXT` branch in `src/bc64/bc8183_cpu.py`) reads only `p` and derives the second pair from it: `csci → dsdi`, `dsdi → csci`, `af → csci`. The assembler accepts any second operand, so `add csci, csci` assembles silently and adds `dsdi`. `docs/02-assembler.md` already warns about this, and `PinnedFindingsTests.test_16bit_rr_second_operand_is_ignored_by_cpu` pins it.
*   **Owner decision (2026-11-19, issue #57 body)**: keep the CPU as it is. The implied pair is part of the ISA; the written second operand documents it and no longer selects anything. The assembler must reject every source line whose second operand differs from the implied pair.
*   **Goal**: `add`/`sub`/`mul`/`div`/`mod`/`and`/`or`/`xor`/`shl`/`shr` in register-register form assemble only as `csci, dsdi`, `dsdi, csci` and `af, csci`. Every other combination, and any unknown pair name in any 16-bit form, is a positioned assembler error. Valid programs assemble byte for byte as before.
*   **In scope**: the assembler check (`src/bc81asmc/`), its tests, the replacement of the pinned test, docs (`docs/02-assembler.md`, `docs/01-emulator.md`, `src/bc81asmc/CLAUDE.md`, a design decision, the roadmap's owner-decision row).
*   **Out of scope**: any CPU change (AC 4); `inc af` / `dec af` being a parse error (`test_inc_and_dec_of_af_cannot_be_parsed`, a separate finding); BASM (it does not exist yet — the issue only says its encoder must apply the same rule later); the shared ISA table (#5).

### 1.1 Technical Summary

One validation in the assembler AST, applied before any nibble is emitted, for the 16-bit classes `CLC16_R_R`, `CLC16_R_IMM`, `INC16`, `DEC16`, `NOT16`. A failed check raises from `emit`, which `compile()` in `bc81asmc.py` already turns into a positioned `cannot encode '<line>': <reason>` diagnostic (#10) — no new diagnostic plumbing.

---

## 2. Architecture & Design

### 2.1 Architecture Overview

#### Involved components & owners

| Component | Technical Owner |
| :--- | :--- |
| assembler (`src/bc81asmc/`) | repo owner (bcichonski) |
| emulator CPU (`src/bc64/bc8183_cpu.py`) — read only | repo owner |
| docs (`docs/`) | repo owner |

#### Flow diagram

```
source line --parsy--> CLC16_R_R(oper, reg, reg2)
                          |
                          | emit(context)
                          v
               check: reg in {csci, dsdi, af}?  -- no --> raise  --+
               check: reg2 == implied(reg)?     -- no --> raise  --+
                          | yes                                     |
                          v                                         v
               emit 5F k8 pq (unchanged)        compile(): Diagnostic(line, col,
                                                 "cannot encode '<line>': <reason>")
```

### 2.2 External Contracts & Evidence

N/A — Internal story.

#### Source Conflict Log

| Topic | Source A | Source B | Conflict | Chosen Handling |
| :--- | :--- | :--- | :--- | :--- |
| Unknown pair names | Issue body: "crashes the assembler with a raw `KeyError` in `REG2BIN`, with no line or column" | `compile()` (since #10) catches every exception from `emit`; a `KeyError` becomes `cannot encode '<line>': operand not supported by this instruction` at line/col. The raw `KeyError` only happens when `emit` is called directly (as in the probe used while refining the issue) | The issue overstates today's failure | AC 2 is kept as written (proper positioned error, not a `KeyError`). The plan replaces the generic reason with a specific one naming the valid pairs (D3) and adds tests that pin it. Recorded in the PR so the issue text is not read as a crash fix |

### 2.3 Affected Areas

| Area / File (pointer) | Role in this change | Likely action |
| :--- | :--- | :--- |
| `src/bc81asmc/bc81asmc_ast.py` — `Bc8183.registers_bin`/`REG2BIN`, `CLC16_R_R`, `CLC16_R_IMM`, `INC16`, `DEC16`, `NOT16` | 16-bit emit | add the pair check (one shared helper) |
| `src/bc81asmc/bc81asmc.py` — `compile()` emit `try/except` | turns an emit exception into a `cannot encode` diagnostic | read only; no change expected |
| `src/bc81asmc/bc81asmc_grammar.py` — `paramreg2`, `m*16r`, `m*16i16`, `mINC16`/`mDEC16`/`mNOT16` | parses any two register names as a pair | no change (D2) |
| `src/bc64/bc8183_cpu.py` — `op_CLC` `CLC_EXT` branch | the implied-pair rule | read only (AC 4) |
| `src/bc81asmc/tests/bc81asmc_opcode_agreement_tests.py` — `PinnedFindingsTests.test_16bit_rr_second_operand_is_ignored_by_cpu`; the 16-bit cases in the table builder | assembler↔CPU agreement | replace the pinned test (listed in T1's Tests to modify); add tests |
| `src/bc81asmc/tests/bc81asmc_compile_diag_tests.py` | errors raised by `compile()` | add tests (style model) |
| `docs/02-assembler.md` — "16-bit ALU" section and the error table | user docs | replace the warning with the rule |
| `docs/01-emulator.md` — registers/16-bit ALU text near "The 16-bit ALU works on the pairs" | CPU docs | document the implied pair |
| `docs/specs/memory/design-decisions.md` — assembler section (A1–A6) | decisions | new decision A7 |
| `docs/analysis/08-self-hosted-roadmap.md` — Phase 0 step 8 and "Decisions the owner still has to make" | roadmap | mark #57 decided |
| `src/bc81asmc/CLAUDE.md` | agent notes | one rule line |

### 2.4 Key Algorithms & Behaviour

*   **Implied pair** (the rule, mirrors the CPU): `csci → dsdi`, `dsdi → csci`, `af → csci`. Valid 16-bit pair names: `csci`, `dsdi`, `af` (the keys of `registers_bin` that map to a pair; the 8-bit names `a`, `cs`, `ds` etc. are not pairs).
*   **Register-register form** (`CLC16_R_R`, all ten operations incl. `shl`/`shr`): first operand must be a valid pair, second must equal `implied(first)`. Otherwise error, no bytes.
*   **Pair-immediate and single-operand forms** (`CLC16_R_IMM`, `INC16`, `DEC16`, `NOT16`): the pair must be a valid pair. Otherwise error, no bytes.
*   **Messages** (reason part of `cannot encode '<line>': <reason>`; exact wording may differ slightly but must contain the quoted parts):
    *   wrong second pair: `second operand must be <implied>` plus a short why, e.g. `second operand must be dsdi (16-bit ops pair csci with dsdi)`;
    *   unknown pair: `'<name>' is not a 16-bit pair (use csci, dsdi or af)`.
*   **Position**: as for every `cannot encode` error — line of the instruction, column of its first non-blank character. Assembly continues and reports every bad line (existing pass-1 behaviour).
*   **Encoding unchanged**: valid lines emit exactly the same nibbles as before (the low nibble keeps the second pair, which is now always the implied one).

---

## 3. Key Decisions & Assumptions

*   **D1 — The check lives in the AST `emit`, not in the grammar.** Raising from `emit` reuses #10's positioned `cannot encode` path and keeps parse errors for real syntax problems. A grammar-level restriction would produce `syntax error: expected …` lists, which are less helpful and would change which alternative wins in `mnemonic`.
*   **D2 — The grammar is unchanged.** `paramreg2` keeps accepting any two register names; the AST decides. Parse-level tests (`bc81asmc_tests.py`, e.g. `mADD16r.parse('add csci, dsdi')`, `NOT16('af')`) keep passing.
*   **D3 — Unknown pair names get a specific reason** instead of the generic `operand not supported by this instruction`, in all five 16-bit classes. (The generic reason already gives line/col, see §2.2; the specific one names the valid pairs.)
*   **D4 — The pinned test is turned into a CPU-level pin of the convention.** `test_16bit_rr_second_operand_is_ignored_by_cpu` can no longer assemble `add csci, csci`. It is rewritten to run the hand-encoded bytes of that instruction (`5F A8 88`) on the CPU and assert that `dsdi` is added — the CPU behaviour is now specified, not a finding — and a separate assembler test asserts the error. The existing agreement cases `csci,dsdi`, `dsdi,csci` (every op) and `add af,csci` already pin the three valid forms end to end.
*   **D5 — `af` as a first operand stays valid in every form** (`add af, csci`, `add af, 0x0100`, `not af`) because the CPU supports it and agreement tests cover it.
*   **Assumption A1** — no committed source uses an invalid combination. Verified while refining the issue: every 16-bit rr line in `src/bc/bc_stdlib.py`, `src/bc/bc_ast.py` templates, `bcOS/bcos.basm` and `src/bdos/boot.basm` is `csci, dsdi` or `dsdi, csci`. The full rebuild in §5 confirms it.

### 3.1 Decision Lock (Constants & Policies)

| Item | Value |
| :--- | :--- |
| Valid pairs | `csci`, `dsdi`, `af` |
| Implied second pair | `csci→dsdi`, `dsdi→csci`, `af→csci` |
| Error class | `cannot encode '<line>': <reason>` (existing) |
| CPU | unchanged |

### 3.2 Open Questions

None.

---

## 4. Task Breakdown

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| T1 | Assembler enforces the implied pair + tests | — | Medium |
| T2 | Document the implied-pair rule | — | Low |

### T1 — Assembler enforces the implied pair + tests

*   **Goal**: the assembler rejects every 16-bit rr combination other than `csci, dsdi` / `dsdi, csci` / `af, csci`, and any unknown pair name in a 16-bit form, with a positioned `cannot encode` error; valid lines encode as before.
*   **Depends on**: —
*   **Complexity**: `Medium`.
*   **Pointers**: `src/bc81asmc/bc81asmc_ast.py` (`Bc8183.registers_bin`, `REG2BIN`, `CLC16_R_R`, `CLC16_R_IMM`, `INC16`, `DEC16`, `NOT16`), `src/bc81asmc/bc81asmc.py` (`compile()` emit `except`), `src/bc64/bc8183_cpu.py` (`op_CLC`, read only), `src/bc81asmc/tests/bc81asmc_opcode_agreement_tests.py` (`PinnedFindingsTests`, `run_case`, `assemble`, the CPU-running helpers), `src/bc81asmc/tests/bc81asmc_compile_diag_tests.py` (style model).
*   **Definition of Done**:
    *   §2.4 holds for all ten rr operations and the four other 16-bit classes.
    *   `add csci, csci`, `add dsdi, dsdi`, `add af, dsdi`, `add af, af` (and at least one non-`add` operation, e.g. `shl csci, csci`) fail with `cannot encode` whose message contains `second operand must be <implied>`, at the instruction's line/col; no bytes are emitted for them and later lines still assemble/are reported.
    *   `add csci, sssi`, `add sssi, csci`, `add sssi, 0x0001`, `inc sssi` fail with the unknown-pair reason (positioned, no `KeyError` escapes `compile()`).
    *   The three valid rr forms and the existing imm/single forms produce identical bytes to before (existing agreement and emit tests pass unchanged).
    *   The pinned test is rewritten per D4.
    *   `src/bc64/bc8183_cpu.py` is not modified.
*   **Tests expected**: unit (assembler): compile-diagnostic tests for wrong second pair and unknown pair (message, line, column, multiple bad lines all reported); agreement tests: CPU pin of the convention on hand-encoded `5F A8 88` (adds `dsdi`) and that the three valid forms still agree. Run `cd src/bc81asmc && python3 -m unittest discover -s tests -t . -p "*_tests.py"` and `python3 run_tests.py --group unit < /dev/null` from the repo root.
*   **Tests to modify**: `src/bc81asmc/tests/bc81asmc_opcode_agreement_tests.py :: PinnedFindingsTests.test_16bit_rr_second_operand_is_ignored_by_cpu` — it assembles `add csci, csci`, which AC 1 (owner decision) makes an assembler error; rewrite it to pin the CPU convention on hand-encoded bytes (D4).

### T2 — Document the implied-pair rule

*   **Goal**: the docs state the rule as part of the ISA and the assembler's enforcement of it, with the table from §3.1.
*   **Depends on**: —
*   **Complexity**: `Low`.
*   **Pointers**: `docs/02-assembler.md` ("16-bit ALU" section — replace the "the CPU ignores the written second operand" warning; add the new message to the error table's `unencodable line` row or a row of its own), `docs/01-emulator.md` (the 16-bit ALU / register-pair text), `docs/specs/memory/design-decisions.md` (new `A7` after `A6`: Purpose / Rationale / Usage / Trade-offs like its neighbours, citing #57 and the owner decision), `docs/analysis/08-self-hosted-roadmap.md` (Phase 0 step 8 row: say what was decided; the "Decisions the owner still has to make" row: drop #57 from the list), `src/bc81asmc/CLAUDE.md` (Rules: one line).
*   **Definition of Done**: the five files describe the implied pair (`csci→dsdi`, `dsdi→csci`, `af→csci`), that the second operand must be written as the implied pair, and that anything else is an assembler error; no doc still says `add csci, af` "actually adds dsdi" as current, accepted behaviour.
*   **Tests expected**: none (docs only); `python3 run_tests.py --group unit < /dev/null` still passes.
*   **Tests to modify**: None.

---

## 5. Verification

*   **All tests**: from the repo root, `python3 run_tests.py < /dev/null` (builds `buildos`/`buildtools`/`buildapps`/`makedisc`, then every suite incl. e2e) — exit 0. The build assembles every committed `.basm` and every compiled program, which confirms Assumption A1.
*   **Guard**: `git status` clean apart from intended source/test/doc changes (build outputs are ignored).
*   **Observable behaviour**: a file with `add csci, csci` assembled via `cd src && python3 bc81asmc/bc81asmc.py x.basm` exits 1 with `x.basm:<line>:<col>: error: cannot encode 'add csci, csci': second operand must be dsdi …`; `add csci, dsdi` assembles to `5F A8 89` as before.

---

## 6. Fact-Integrity Checklist

| Check | Status |
| :--- | :--- |
| Every AC mapped to a task (AC1–3 → T1, AC4 → T1 DoD, AC5 → T2, Tests → T1) | Yes |
| CPU rule verified in code (`op_CLC` `CLC_EXT` branch) | Yes |
| Emit-exception → positioned diagnostic verified (`compile()`) | Yes |
| Existing tests using invalid combinations searched (only the pinned one) | Yes |
| Committed sources using invalid combinations searched (none) | Yes |
| No Open Questions | Yes |

**Self-review note**: the only conflict with the issue text is the "raw `KeyError`" claim (§2.2): `compile()` already positions it, so AC 2 is met by giving the error a specific reason and tests, not by fixing a crash. No AC is dropped or reinterpreted. Encoding of valid lines is unchanged, so no golden or e2e test should move.

---

## 7. Amendment Log

| Revision | Request | Source | Decision | Plan changes |
| :--- | :--- | :--- | :--- | :--- |
