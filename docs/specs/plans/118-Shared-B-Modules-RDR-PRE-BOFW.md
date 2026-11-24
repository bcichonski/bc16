# Shared B Modules RDR PRE BOFW Plan

**Plan Status**: `DRAFT - BLOCKED`

**Story Type**: `Internal`

**Plan Revision**: `A0`

> This plan captures **what** to build and **why**. It does not contain implementation code.
> It is blocked on prerequisites that are not on `master` (see §3.2). The task breakdown in §4
> shows the intended shape once they land. It is not ready to implement.

---

## 1. Problem Statement

Issue #118 (roadmap step 36, phase 2 of `docs/analysis/08-self-hosted-roadmap.md`): write
three B modules once, so that BASM (#119), the compiler passes and BLINK share them:

- **RDR**: reads texted-format files record by record with their line numbers. It also
  accepts plain lines ending in `0x0a`, `0x0d` or `0x13`. It keeps an include stack of at
  most 3 levels, the main file counted (3 read handles).
- **PRE**: `#include` (the main file's drive, then A), a `#define` table, whole-identifier
  replacement outside strings (#19 rule), `#link`, and `#code`/`#heap`/`#codelimit`.
- **BOFW**: writes BOF v1 records through the one write handle, with the deterministic
  flush rules and fix lists.

### 1.1 Acceptance criteria (from the issue, verbatim)

- AC-1: an e2e test program on the BC64 exercises each module: it reads a texted file and a
  plain file, expands includes and defines, and writes a `.o` that `bc81asmc --dump` reads
  back as expected.
- AC-2: the code size of each module is recorded.
- AC-3: documented in `docs/05-bdos.md` (or a new tools page).

### 1.2 Why this is blocked

Verified on `origin/master` 5f74848 (2026-11-24):

- The roadmap orders phase 1 (steps 31–35: #113, #114, #115, #116, #117) before phase 2.
  All five issues are **OPEN**. None is implemented. The #113 run is only at its review step.
- **BOF v1 is not frozen.** `docs/analysis/07-self-hosted-compiler.md` → "Object file format"
  calls it "A proposal", and it says the `SECT` flags are "Still open". Freezing it as design
  decisions is the whole of #113 (step 31: "`SECT` flags decided"). BOFW *is* a writer of
  that format, so writing it now means inventing the frozen format in this story.
- **`bc81asmc --dump` does not exist.** `grep -rn -- "--dump\|--obj" src` finds nothing. It
  arrives with #115 (step 33: "a `.o` dump"). AC-1's oracle is that tool, so AC-1 cannot be
  checked on `master`.
- The roadmap memory says the owner set this order on 2026-11-19 (BASM after the host object
  tools), and an "owner decision" row (the `SECT` flags) must not be picked by an agent.

RDR and PRE don't depend on BOF. Delivering them alone would leave AC-1 (the `.o` part) and
the BOFW module unmet, which is a deviation from the AC that only the owner can accept.

---

## 2. Architecture & Design

### 2.1 Architecture Overview

Three B include files under `src/bdos/` (the "B sources included by each tool" option in the
issue; `.o` modules need BLINK, phase 3). Each tool includes them after `bdosh.b`. The
compiler links every function of every include until DCE; since #16 (decision C9) DCE drops
unreferenced functions, so including them costs only what a tool calls.

```
 source file (texted or plain) ──► RDR (3 read handles, include stack)
                                     │ line + line number + file
                                     ▼
                                   PRE (#include → RDR push, #define table,
                                        #link / #code / #heap / #codelimit)
                                     │ expanded line, directives as events
                                     ▼
                                 tool logic (BASM, compiler pass, test program)
                                     │ records
                                     ▼
                                   BOFW ──► NAME.O through the single write handle
```

### 2.2 External Contracts & Evidence

N/A — Internal story. The internal contracts it depends on:

| Contract | Source | Status |
|---|---|---|
| TextEd record format: `<decimal line number> <text>` + `0x13`, then one `0x00`, sector padded (decision D6) | `src/ftool_text.py` docstring; `docs/05-bdos.md` → "TextEd file format" | Verified |
| 3 read handles, 1 write handle (`BDIO_FDESCRIPTOR_READ_MAX 0x03`, `_WRITE_MAX 0x00`, indices 0-based) | `src/bdos/bdioh.b` | Verified |
| `#define` rule: name = first token, value = rest of line, whole identifiers only, in code and in `asm` strings (#19, `bc.py parse_define/apply_defines`) | `src/bc/bc.py` | Verified |
| BOF v1 record layout | `docs/analysis/07-self-hosted-compiler.md` "Object file format" (a proposal) | **Assumption — not frozen until #113 (OQ-1)** |
| `bc81asmc --dump` output format | does not exist (#115) | **Assumption — OQ-2** |
| Host `#include`/`#define`/`#link` from `.h` files in the assembler | does not exist (#114) | **Assumption — OQ-3** |

### 2.3 Affected Areas (pointers)

- New: `src/bdos/rdr.b`, `src/bdos/pre.b`, `src/bdos/bofw.b` (names to confirm against #113/#114's naming).
- New e2e test module under `src/tests/` plus a B test program; register it in `src/tests/e2e_areas.py` (a unit test fails otherwise).
- `scripts/code_size.py` / `src/bc/code_size.csv` (append-only) for AC-2.
- `docs/05-bdos.md` (AC-3).
- Patterns to follow: `src/tests/test_e2e_bdio_buffered.py` (a working B test program), `ftool importtext` to put inputs on a disc (#112), the e2e B-program probe runner (bc → asm → btap2bin → `h.disc_put` → `h.run_session`).

### 2.4 Key Behaviour

- **RDR.** Opens a file and reads it through the buffered read call. Detects texted records
  (leading decimal number + space, `0x13` end) versus plain lines (`0x0a`/`0x0d`/`0x13` end;
  the line number is a counter). Hands out one line at a time with its number and the name
  of the file it came from. On `#include` it pushes a handle; at end of file it pops. A 4th
  level is an error naming the file and line.
- **PRE.** Recognises directives at the start of a line. `#include NAME`: try the main file's
  drive, then A. `#define`: the #19 rule, a redefinition with a different value warns.
  Replacement is whole identifiers outside string literals. `#link`/`#code`/`#heap`/
  `#codelimit` are handed to the tool as events (BOFW turns them into `NEED`/`ADDR` records).
- **BOFW.** Buffers one `CODE` record (≤ 255 bytes) and its fix lists; flushes by the frozen
  rules (full, before `LABEL`/`GLOBL`/`SECT`/`END`/`EXTRN`, before an item that would not fit
  whole), writes fix records in tag order with ascending offsets, splits lists over 255 bytes.

---

## 3. Key Decisions & Assumptions

### 3.1 Decision Lock

- D-1: The modules are B include files, not `.o` modules (BLINK doesn't exist yet). From the issue text.
- D-2: Follow the roadmap order; do not freeze BOF v1 or write `--dump` inside this story.
- D-3: No new helpers in `bdosh.b`/`std.b` (owner rule from #2).

### 3.2 Open Questions

| # | Question | Owner | Blocks |
|---|---|---|---|
| OQ-1 | BOF v1 frozen as design decisions, including the `SECT` flags (#113, roadmap step 31, an owner decision). BOFW can't be written against a format that may still change. | Owner (#113) | BOFW, AC-1 |
| OQ-2 | `bc81asmc --dump` and its output format (#115, step 33). AC-1's oracle. | Owner / #115 | AC-1 |
| OQ-3 | Should PRE follow the host assembler's `#include`/`#define`/`#link` from `.h` files (#114, step 32) so that BASM and `bc81asmc` behave the same? The roadmap exit for phase 2 is byte-identity with `bc81asmc --obj`. | Owner / #114 | PRE details |
| OQ-4 | Alternatively, does the owner want RDR + PRE delivered now (no BOF dependency), with BOFW and the `.o` half of AC-1 split into a follow-up issue after #115? That deviates from AC-1 and from the roadmap order, so an agent must not choose it. | Owner | scope |

---

## 4. Task Breakdown (intended shape once unblocked — not to be executed at A0)

### T1 — RDR: texted and plain line reader with include stack
- Depends on: —
- Complexity: High
- Files: new `src/bdos/rdr.b`; probe program + e2e test under `src/tests/`.
- DoD: reads a texted file and a plain file (each line ending) with correct line numbers; 3-level include stack; a 4th level and a missing file give an error naming file and line.
- Tests: e2e on the emulator with inputs placed by `ftool importtext`; one happy test, one error test, tens of seconds total.
- Tests to modify: None

### T2 — PRE: directives and #define replacement
- Depends on: T1
- Complexity: High
- Files: new `src/bdos/pre.b`; e2e test.
- DoD: `#include` lookup (main drive, then A), #19 define rule incl. outside-strings and whole identifiers, redefinition warning, `#link`/`#code`/`#heap`/`#codelimit` events.
- Tests: e2e cases mirroring `bc.py`'s define tests on the BC64.
- Tests to modify: None

### T3 — BOFW: BOF v1 writer
- Depends on: OQ-1, OQ-2 (not T1/T2)
- Complexity: High
- Files: new `src/bdos/bofw.b`.
- DoD: writes every record kind of the frozen format with its flush and ordering rules; output read back by `bc81asmc --dump` matches.
- Tests: e2e program writes a `.o`, exported with ftool, dumped on the host, compared.
- Tests to modify: None

### T4 — AC-1 combined e2e, code size, docs
- Depends on: T1, T2, T3
- Complexity: Medium
- Files: e2e module registered in `src/tests/e2e_areas.py`; `src/bc/code_size.csv` via `scripts/code_size.py --record`; `docs/05-bdos.md`.
- DoD: AC-1 to AC-3 met.
- Tests to modify: None

---

## 5. Verification

- `python3 run_tests.py --group unit`, `--group e2e --tier happy`, `--group e2e --changed origin/master` during development; full `python3 run_tests.py < /dev/null` once before the PR.
- AC-1: the e2e test passes and the `--dump` output of the BC64-written `.o` matches the expected records.
- AC-2: one row per module in `code_size.csv`.

---

## 6. Fact-Integrity Checklist

| Check | Yes / No / N/A | Notes |
| :--- | :--- | :--- |
| External contracts verified | N/A | Internal |
| Evidence sources reproducible | N/A | Internal |
| Identifier meaning evidenced | N/A | Internal |
| Every `Assumption` is linked to an Open Question (§3.2) | Yes | BOF → OQ-1, dump → OQ-2, host `.h` → OQ-3 |
| No unresolved Open Questions (for `FINAL`) | No | OQ-1..OQ-4 |
| Each Decision states a single committed approach | Yes | |
| Tasks are independent, each with a Definition of Done and test expectations | Yes | T3 waits on OQ-1/OQ-2 |
| Required infra reflected | N/A | |

**Self-review note**: The format BOFW writes is a proposal that #113 exists to freeze (with an
owner decision on the `SECT` flags), and AC-1's oracle (`bc81asmc --dump`) comes with #115.
Both are earlier roadmap steps, still open. Making this plan FINAL would mean inventing both
inside this story, against the owner's roadmap order, so it stays blocked. RDR/PRE could go
first only if the owner accepts the split (OQ-4).

---

## 7. Amendment Log

| Revision | Request | Decision | Plan changes |
| :--- | :--- | :--- | :--- |
