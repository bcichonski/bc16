# CPU: 16-bit results in the A:F pair — document the flags overwrite — Plan

**Plan Status**: `FINAL`

**Story Type**: `Internal`

**Plan Revision**: `A0`

> This plan captures **what** to build and **why**. The implementation agent discovers the **how** against live code.

---

## 1. Problem Statement

*   **Context**: `A:F` is accepted as a 16-bit pair by the 16-bit ALU (`add/sub/mul/div/mod/and/or/xor af, 0xHHHH`, `shl/shr af, 0xHH`, and the register form `op af, csci`). In `src/bc64/bc8183_cpu.py`, `alu_setval16` stores the result's high byte in `A` and its low byte in `F`, then `set_flags16` sets `Z/N/C/O` in `F`. So after a 16-bit op on `af`, `A` holds the result's high byte, the low byte is lost, and `F` holds the flags. Two tests in `src/bc64/tests/test_cpu_alu.py` (`test_add16_on_a_f_pair`, `test_add16_reg_on_a_f_pair_uses_cs_ci`) exercise this; the first is commented `PINNED` as a bug.
*   **Issue "Expected"**: either reject 16-bit arithmetic on `af` in the assembler, or keep the low byte and set no flags. "Decide and document it."
*   **Owner decision (issue comment, 2026-11-20)**: "that is correct cpu behavior af is not to be used in this context although allowed". So: the CPU stays as it is, the assembler keeps accepting `af`, and the behaviour is documented as the defined result of these forms, with the advice not to use `af` as a 16-bit ALU destination.
*   **Goal**: the documented ISA states exactly what a 16-bit ALU op on `af` does; the tests assert it as defined behaviour (no longer "pinned bug"); the decision is recorded; the roadmap shows #58 decided.
*   **In scope**: `docs/01-emulator.md`, `docs/02-assembler.md`, `docs/specs/memory/design-decisions.md` (new E-decision), `docs/analysis/08-self-hosted-roadmap.md` (step 9 row + owner-decision table), `src/bc64/tests/test_cpu_alu.py` (reword the pinned test, add coverage).
*   **Out of scope**: any change to the CPU (`bc8183_cpu.py`) or to the assembler's accepted forms; an assembler warning for `af` (there is no warning channel and the owner said "allowed"); `inc/dec/not/clr af` parse/crash issues (#66, #67); `C`/`O` meaning (#54); `A:F` used as a memory address (`mov ci, #af` etc. — unaffected, tests in `test_cpu_control.py`).

### 1.1 Technical Summary

*   **Touched**: docs only plus one emulator test module. No production code change.
*   **New patterns**: none.
*   **Infrastructure changes**: none.
*   **End-state observable behaviour**: identical to today. A 16-bit ALU op with destination `af` leaves `A` = high byte of the 16-bit result and `F` = the flags of that op; the low byte is not kept anywhere. Docs say so and say not to use it for arithmetic.

---

## 2. Architecture & Design

### 2.1 Architecture Overview

| Component | Technical Owner |
| :--- | :--- |
| emulator CPU (`src/bc64/bc8183_cpu.py`) — read only | repo owner (bcichonski) |
| assembler (`src/bc81asmc/`) — read only | repo owner |
| docs (`docs/`) | repo owner |

```
op af, x  -->  r = 16-bit result  -->  A := r >> 8 ; F := r & 0xff  -->  set_flags16(r) overwrites F
                                                                       => A = high byte, F = flags
```

### 2.2 External Contracts & Evidence

N/A — Internal story.

#### Source Conflict Log

| Topic | Source A | Source B | Conflict | Chosen Handling |
| :--- | :--- | :--- | :--- | :--- |
| What to do about `af` | Issue body "Expected": reject in assembler, or keep low byte with no flags | Owner comment 2026-11-20: current behaviour is correct, `af` allowed but not to be used | The owner picked a third option the body did not list | Follow the owner comment (newer, by the owner). Flagged as a deviation from the issue's "Expected" in the PR body (see D1). |

### 2.3 Affected Areas

| Area / File (pointer) | Role in this change | Likely action |
| :--- | :--- | :--- |
| `src/bc64/bc8183_cpu.py` (`alu_setval16`, `set_flags16`) | the behaviour being documented | Reference |
| `docs/01-emulator.md` (registers table / "The 16-bit ALU works on the pairs…" paragraph, Flags section) | emulator reference | Change: state the `af` result rule |
| `docs/02-assembler.md` ("16-bit ALU (bc8183 extension, on `csci`, `dsdi` or `af`)") | assembler reference | Change: state the `af` result rule and the "don't use for arithmetic" advice |
| `docs/specs/memory/design-decisions.md` (Emulator section, after E11) | standing decisions | New E12 |
| `docs/analysis/08-self-hosted-roadmap.md` (step 9 row; "Decisions the owner still has to make" row `#54, #56, #58`) | roadmap | Change: mark #58 decided, drop #58 from the open-decision row |
| `src/bc64/tests/test_cpu_alu.py` (`# --- A:F pair` block) | tests of the behaviour | Change comment of one test, add tests |
| `src/bc81asmc/tests/bc81asmc_opcode_agreement_tests.py` (`add16 af,imm`, `add16 af,csci` cases) | already compare only `A` for `af` | Reference (no change) |

### 2.4 Key Algorithms & Behaviour

Defined behaviour of every 16-bit ALU op whose destination pair is `af` (imm form, register form `op af, csci`, `shl/shr af, imm`):
*   the 16-bit source value is `A << 8 | F` (the flags register is the low byte of the input);
*   `A` = bits 15–8 of the result truncated to 16 bits;
*   `F` = the flags the op sets, as for any 16-bit op (E11: `Z`/`N` from the stored 16-bit value, `C`/`O` from the unwrapped value, #54). The result's low byte is discarded;
*   `div`/`mod` by zero: destination unchanged and `O` set (E10) — i.e. `A` unchanged and `F` changed;
*   advice: use `csci` or `dsdi` for 16-bit arithmetic; the compiler and the hand-written sources never use `af` as a 16-bit ALU destination (audit below).

**Dependency audit (done during planning)**: no `.b`/`.basm` source under `src/` (bcOS, bdos, apps, `bc_stdlib.py`) has a 16-bit ALU op with `af` as destination (grep for `add|sub|mul|div|mod|and|or|xor|shl|shr|inc|dec|not|clr  af`); `bc_stdlib.py` mentions `af` only as a `MEM_CPY` length argument. Nothing changes at runtime, so no rebuild-dependent behaviour changes.

---

## 3. Key Decisions & Assumptions

*   **D1 — Keep the CPU and the assembler; document the result (owner decision 2026-11-20).** Deviates from the issue's "Expected" (which offered only "reject" or "keep the low byte"); the owner's later comment chose this. The PR body lists it as a deviation.
*   **D2 — No assembler warning.** The owner said "allowed"; the assembler has no warning channel (A6 is errors only). Adding one is new scope.
*   **D3 — Record as design decision E12** in the Emulator section of `design-decisions.md`, in the existing format (Purpose / Rationale / Usage / Trade-offs).
*   **D4 — Tests assert defined behaviour.** `test_add16_on_a_f_pair` loses its `PINNED` wording (the issue names it to be changed when this is decided); its assertions stay. New tests cover the rule beyond `add`: `F` is the low byte of the input, `F` after the op holds flags (not the result's low byte) for a result whose low byte is non-zero, and the register form.
*   **Assumption**: none affecting correctness.

### 3.1 Decision Lock

| Constant / Policy | Selected Value | Why | Where it lives |
| :--- | :--- | :--- | :--- |
| Design decision id | `E12` | next free in Emulator section (E11 is last) | `design-decisions.md` |
| CPU / assembler behaviour | unchanged | owner comment | — |

### 3.2 Open Questions

No open questions.

---

## 4. Task Breakdown

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| `T1` | Document the A:F 16-bit result rule (docs, E12, roadmap) | — | `Low` |
| `T2` | Turn the pinned A:F test into defined-behaviour tests | — | `Low` |

### T1 — Document the A:F 16-bit result rule

*   **Goal**: the docs and the decision record state what a 16-bit ALU op on `af` does and advise against it.
*   **Depends on**: `—`.
*   **Complexity**: `Low`.
*   **Pointers**: `docs/01-emulator.md`, `docs/02-assembler.md`, `docs/specs/memory/design-decisions.md`, `docs/analysis/08-self-hosted-roadmap.md`; behaviour per §2.4; check it against `alu_setval16`/`set_flags16`.
*   **Definition of Done**:
    *   `01-emulator.md` and `02-assembler.md` each state: input is `A:F` (F = low byte), after the op `A` = result high byte, `F` = flags, low byte lost; `af` is allowed but not meant for 16-bit arithmetic (use `csci`/`dsdi`). Both link to E12 or to each other consistently with the surrounding style.
    *   `design-decisions.md` has `### E12.` after E11 in the same format, citing #58 and the owner comment.
    *   Roadmap step 9 row records "**Decided (2026-11-20):** …" like step 8; the open-decision row no longer lists #58.
    *   No source/code file changed. Keep existing line endings of each file.
*   **Tests expected**: none (docs). `python3 run_tests.py --group unit < /dev/null` still exits 0.
*   **Tests to modify**: None.

### T2 — Turn the pinned A:F test into defined-behaviour tests

*   **Goal**: the emulator tests assert the `af` rule as defined behaviour, with coverage beyond the one `add` case.
*   **Depends on**: `—`.
*   **Complexity**: `Low`.
*   **Pointers**: `src/bc64/tests/test_cpu_alu.py` (`# --- A:F pair` block, helpers `run_code`, `imm`, `check16`); CPU in `src/bc64/bc8183_cpu.py`.
*   **Definition of Done**: the `PINNED` comment of `test_add16_on_a_f_pair` is replaced by one stating the defined behaviour (E12, #58); its assertions are unchanged. New tests (added, in the same block) cover: a result with non-zero low byte leaves `F` = flags, not that byte; `F` is read as the low byte of the input; at least one non-`add` op (e.g. `sub` or `mul`) on `af`; the register form `op af, csci`. All pass against the unchanged CPU.
*   **Tests expected**: unit (emulator suite).
*   **Tests to modify**: `src/bc64/tests/test_cpu_alu.py :: test_add16_on_a_f_pair — comment only: "PINNED" bug wording becomes defined behaviour (D1/D4; the issue body asks for this test to change once decided). Assertions must stay.`

---

## 5. Verification

*   `python3 run_tests.py < /dev/null` from the repo root exits 0 (builds the pipeline; e2e unaffected because no code changes). Report any expected failures by name.
*   `git diff --stat origin/master` shows only docs, the plan files and `src/bc64/tests/test_cpu_alu.py`.
*   Docs read consistently: 01 and 02 describe the same rule; E12 matches.

---

## 6. Fact-Integrity Checklist

| Check | Yes / No / N/A | Notes |
| :--- | :--- | :--- |
| External contracts verified | N/A | Internal |
| Evidence sources reproducible | N/A | Internal |
| Identifier meaning evidenced | N/A | Internal |
| Every `Assumption` linked to an OQ | Yes | none |
| No unresolved Open Questions | Yes | owner comment closes the decision |
| Each Decision states a single approach | Yes | |
| Tasks independent with DoD and tests | Yes | |
| Required infra reflected | N/A | |

**Self-review note**: the only judgement call is following the owner's comment over the issue body's two listed options; it is recorded as D1 and must appear in the PR as a deviation. The rule in §2.4 was read from `alu_setval16`/`set_flags16`; the agent should confirm each statement (especially `F` as input low byte and E10's div-by-zero case) against the CPU before writing docs.

---

## 7. Amendment Log

| Amendment | Request | Decision | Plan changes |
| :--- | :--- | :--- | :--- |
