# bdos: `cp` reads keys until the input runs out and never creates the copy — Plan

**Plan Status**: `FINAL`

**Story Type**: `Internal`

**Plan Revision**: `A0`

> This plan captures **what** to build and **why**. The implementation agent discovers the **how** against live code.

---

## 1. Problem Statement

*   **Context**: issue #73 (filed 2026-11-09 from #49's e2e scenarios) reports that `cp test.b copy.b` prints its loading dots and then nothing more. It eats every remaining input line and creates no `COPY.B`. **The bug has already been fixed on master by #37** (PR #88, 2026-11-11). Before #37, the hand-made catalog `fcat0800.sector` gave `CP.PRG` 56 sectors, but the program builds to 57. bdos loaded a truncated program, so the end of `cp` was never in memory. Since #37, catalog lengths come from the real builds (`src/disc.bddmanifest` → `ftool mkdisc`), and `CP.PRG` is 57 sectors. #37 also removed the `@unittest.expectedFailure` decorator from `test_cp_then_cat_shows_same_text` and took `cp` off the known-failures list in `docs/01-emulator.md`. The issue stayed open because no PR referenced it.
*   **Verified on master `c745b4c` (probe, 2026-11-22, fresh `./buildos && ./buildtools && ./buildapps && ./makedisc`)**:
    *   The issue's script (`cp test.b copy.b` / `cat -c copy.b` / `exit`) completes. `cp` returns to `A>`, `cat -c copy.b` prints the TEST.B text, `exit` prints `bye!`, exit code 0.
    *   `ls` after the copy lists `COPY    .B   -R-- 0100 24 0A 02`, the same length as `TEST.B` (2 sectors).
    *   A cross-drive copy works: with a copy of os.bdd in drive B, `cp test.b b:copy.b` → `ls b:` lists `COPY.B` → `cat -c b:copy.b` prints the text.
    *   `cp ls.prg new.prg` completes (57+ sector program copy, 64-sector buffer loop) and `new` runs the copy.
    *   **Root cause reproduced**: on a temp copy of the built os.bdd, lowering the `CP` catalog entry's length from 57 to 56 gives exactly the issue's symptom (dots, then nothing, the input runs out, exit 0).
    *   The `TypeError` in `op_JMP` mentioned in the issue came from pre-#7 emulator memory, which was smaller than 64 KB and partly unwritten. #7 (PR #80) made memory a full 0x10000 bytes, so a jump to an unwritten address no longer raises a Python error.
*   **Goal**: close #73 with evidence. Add e2e regression tests that pin the issue's full "Expected" section: `cp` returns to `A>`, `ls` lists `COPY.B`, and the copy has the same content as `test.b`, checked byte for byte on the disc image rather than only through a few printed markers. Cover the cross-drive path (`getdrive`/`changeDriveIfNeeded`) that the issue names. Add a golden for the scenario (issue "Test", step 2). Add a docs note on the root cause.
*   **In scope**: new e2e tests and scenario/golden files under `src/tests/` and `src/bc64/testdata/e2e/`, an optional small read helper in `src/tests/e2e_harness.py`, and docs (`docs/01-emulator.md`, `docs/05-bdos.md`).
*   **Out of scope**: any change to `src/bdos/cp.b`, bdio or the emulator (none needed). `cp`'s deliberate removal of the `W` attribute from the copy (`nowritemask` in `cp.b`: TEST.B `-RW-` → COPY.B `-R--`) is existing design and stays. Other expected failures (`test_tape_round_trip` #32/#62, the assembler `#11` ones) belong to their own issues.

### 1.1 Technical Summary

*   **Touched projects**: `src/tests/` (e2e tests and harness, tests only), `src/bc64/testdata/e2e/` (new scenario scripts and goldens), docs.
*   **New patterns / abstractions**: possibly a harness helper that returns a file's bytes from a disc image by catalog name (track/sector/length → sectors), next to `read_catalog`/`disc_put`.
*   **Infrastructure changes**: none.
*   **End-state observable behavior**: unchanged from master. The cp scenario is now pinned by a golden, an `ls` check and a byte-level comparison, on the same drive and across drives.

---

## 2. Architecture & Design

### 2.1 Architecture Overview

| Service | Technical Owner |
| :--- | :--- |
| bdos `cp` utility + e2e harness | repo owner |

```mermaid
flowchart LR
  manifest[src/disc.bddmanifest] --> mkdisc[ftool mkdisc] --> osbdd[os.bdd: CP.PRG len = real build]
  osbdd --> e2e[e2e test: temp copy of os.bdd in A (and B)]
  e2e --> emu[bc64.py headless] --> out[printer output: golden + markers]
  e2e --> inspect[inspect hook: catalog + file bytes of the temp disc]
```

Flow of the new tests: the harness boots a temp copy of the built `os.bdd`, types the scenario script (`cp …`, `ls`, `cat -c …`, `exit`), and returns the printer bytes. The inspect hook then reads the temp disc images. The test checks the printed output against a masked golden and markers, then the catalog entry of the copy and its sector bytes against the source file.

### 2.2 External Contracts & Evidence

N/A — Internal story.

#### Source Conflict Log

| Topic | Source A | Source B | Conflict | Chosen Handling |
| :--- | :--- | :--- | :--- | :--- |
| Bug status | Issue #73: cp hangs, test is `expectedFailure` | master `c745b4c` + CHANGELOG [37] | Already fixed by #37; decorator already removed; known-failures list already updated | Deliver regression tests and docs only; state "no code change" in the PR (D1) |
| Issue "Test" steps 1 and 3 | Remove decorator; update known-failures list | Both done by #37 | Nothing left to do | Verify they stay done; no edit |
| Repro paths | Issue: `smoke.bdd`, committed `src/os.bdd`, `bc64/testdata/smoke.bdd` | #92: ROM/os.bdd/smoke.bdd no longer tracked; `SMOKE_DISK` gone | The issue's repro commands are obsolete | Tests boot a temp copy of the built `os.bdd` (`h.OS_DISK`), the current convention |
| Issue "Be careful" | Rebuild and commit `CP.PRG`/`os.bdd`, refresh `smoke.bdd` | #92: generated outputs are untracked, run_tests builds before e2e | Nothing to commit or refresh | No generated files are committed |

### 2.3 Affected Areas

| Area / File (pointer) | Role in this change | Likely action |
| :--- | :--- | :--- |
| `src/tests/test_e2e_bdos.py` | bdos shell e2e tests; holds `test_cp_then_cat_shows_same_text`, the `run`/`check` helpers and the `inspect` pattern used by the rm test | Change (add tests only) |
| `src/tests/e2e_harness.py` | `run_session(disks=…, inspect=…)`, `read_catalog`, `disc_put`, `DISC_MASKS`, `check_golden`, `ls_line`/`planned_entry` | Change (optional read helper) |
| `src/bc64/testdata/e2e/bdos_cp.in.txt` | Existing cp script | Reference (do not edit) |
| `src/bc64/testdata/e2e/` | Scenario scripts `*.in.txt` and goldens `*.golden.txt` | New files |
| `src/tests/test_e2e_disc.py` | Already checks every catalog length against the manifest plan and that a corrupt length is detected: the guard against the root cause | Reference |
| `src/bdos/cp.b` | The utility; source drive / target drive switching, attribute mask | Reference |
| `docs/01-emulator.md` | e2e test table (row for `test_e2e_bdos.py`) and Known failures | Change (small) |
| `docs/05-bdos.md` | `cp` row in the utilities table, disc layout section | Change (small note) |

### 2.4 Key Algorithms & Behaviour

*   **Same-drive copy** (A → A): after `cp test.b copy.b` the shell prompt returns. `ls` lists `COPY.B` with the same sector length as `TEST.B`. `cat -c copy.b` prints the TEST.B text. On the temp disc image, the copy's sectors hold the same bytes as TEST.B's sectors, for the source file's length.
*   **Cross-drive copy** (A → B): a second temp disc in drive B (a temp copy of the built os.bdd is fine; the source disc must not change). After `cp test.b b:copy.b`, `COPY.B` exists on B with the same length and bytes, and drive A's catalog is unchanged. Keep the scenario short: typing `b:` changes the current drive and utilities aren't found afterwards (bc16 fact from #85), so stay on A and use the `b:` prefix.
*   **Attributes**: the copy gets the source attributes minus `W` (`nowritemask` keeps E, S and R). The test may assert this observed rule, but must not treat it as a bug.
*   **Golden**: stored masked with `h.DISC_MASKS` (ls SIZE/TT/SS/LL, free-sector figure, dot-only lines), so program size changes don't churn it. Generate it with `BC64_UPDATE_GOLDEN=1`, then read it by eye.
*   **Byte comparison**: read from the temp image through the catalog (track, sector, length → `SECTOR_SIZE` blocks), not through pinned positions.

---

## 3. Key Decisions & Assumptions

*   **D1 — No code change**: the defect is fixed on master (verified by probe, and the root cause was reproduced by truncating the catalog length). This run only adds regression coverage and docs. The PR says so explicitly and uses `Closes #73`.
*   **D2 — New scenarios, existing test untouched**: the issue's optional golden (Test, step 2) and the `ls`/byte checks go into **new** scenario files and new test methods. `bdos_cp.in.txt` and `test_cp_then_cat_shows_same_text` stay as they are, so `Tests to modify` is `None`.
*   **D3 — No extra root-cause test**: `test_e2e_disc.py` already detects a catalog length that differs from the manifest plan, which is what broke `cp`. No duplicate "truncated CP.PRG hangs" test is added; it would only test the symptom of a broken disc.
*   **D4 — Cross-drive coverage is included**: the issue names `getdrive`/`changeDriveIfNeeded` and `bdio_setdrive` as suspects, and `docs/05-bdos.md` advertises "also between drives". The cost is one more short scenario.
*   **Assumption A1 (low stakes)**: the issue's "Expected" sentence "`cat -c copy.b` then shows the same text as `test.b`" is pinned as byte-identical sector content on the disc. That is stronger than the text and covers it. It is not a deviation from the AC.

### 3.1 Decision Lock (Constants & Policies)

| Constant / Policy | Selected Value | Why | Where it lives |
| :--- | :--- | :--- | :--- |
| Disc under test | temp copy of built `h.OS_DISK` (both drives for the cross-drive case) | #92 convention; never touch the built disc | tests |
| Golden masking | `h.DISC_MASKS` | #89 convention | tests |
| Instruction limit | the module's existing `LIMIT` (or a justified higher one if a bigger copy needs it) | consistency | `test_e2e_bdos.py` |

### 3.2 Open Questions

No open questions.

---

## 4. Task Breakdown

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| `T1` | e2e regression tests for `cp` (same drive with golden + byte check, cross-drive) | — | `Medium` |
| `T2` | Docs: cp root cause and test coverage | — | `Low` |

### T1 — e2e regression tests for `cp`

*   **Goal**: the issue's "Expected" behaviour is pinned end to end. If `cp` ever hangs, fails to return to `A>`, fails to create the catalog entry, or writes different bytes, a normal (non-xfail) test fails.
*   **Depends on**: `—`.
*   **Complexity**: `Medium`.
*   **Pointers**: `src/tests/test_e2e_bdos.py` (follow the rm test's `inspect` pattern), `src/tests/e2e_harness.py` (`run_session`, `read_catalog`, `DISC_MASKS`, `check_golden`), `src/bc64/testdata/e2e/`, `src/bdos/cp.b` (reference only).
*   **Definition of Done**:
    *   A new same-drive scenario (script: `cp test.b copy.b`, `ls`, `cat -c copy.b`, `exit`) has a masked golden. Its test asserts the markers (prompt after cp, `ls` line naming `COPY    .B`, TEST.B text, `bye!`). The inspect step checks that `COPY.B` is in the temp disc's catalog with TEST.B's length, and that its sector bytes equal TEST.B's.
    *   A new cross-drive scenario (`cp test.b b:copy.b`, `ls b:`, `cat -c b:copy.b`, `exit`, with a second temp disc in B) checks the same on drive B, and that drive A's catalog is unchanged by the copy.
    *   If a harness helper is added to read a file's bytes from an image by name, it has a small self-test in the harness test module (same style as the existing `disc_put`/`read_catalog` tests).
    *   `bdos_cp.in.txt` and `test_cp_then_cat_shows_same_text` are unchanged. No source outside `src/tests/` and `src/bc64/testdata/e2e/` changes. No generated build output is committed.
    *   `cd /c/workspace/bc16-73 && python3 run_tests.py < /dev/null` exits 0, and the expected-failure count is unchanged from master.
*   **Tests expected**: e2e (headless emulator), the two scenarios above. Harness unit test for any new helper.
*   **Tests to modify**: `None`.

### T2 — Docs: cp root cause and test coverage

*   **Goal**: a reader of the docs learns that a catalog length shorter than the program build truncates loading (that is what made `cp` hang before #37), and where `cp` is tested.
*   **Depends on**: `—`.
*   **Complexity**: `Low`.
*   **Pointers**: `docs/05-bdos.md` (`cp` row / disc layout: lengths come from the build via the manifest), `docs/01-emulator.md` (the `test_e2e_bdos.py` row of the e2e table; Known failures stays without `cp`).
*   **Definition of Done**: one short note in `docs/05-bdos.md`: the manifest takes lengths from the real builds, and a too-short catalog length loads a truncated program that never returns (issue #73, the `cp` hang fixed by #37). The `docs/01-emulator.md` table row still names `cp`, and the cross-drive check is mentioned if T1 adds it. No other doc rewrites. Docs style matches the surrounding text.
*   **Tests expected**: none (docs only).
*   **Tests to modify**: `None`.

---

## 5. Verification

*   **Build**: `cd src && ./buildos && ./buildtools && ./buildapps && ./makedisc` (or let `run_tests.py` build).
*   **Tests**: `python3 run_tests.py < /dev/null` from the repo root: exit 0. Report the expected-failure count, which should be unchanged from master (`test_tape_round_trip` #32/#62 and the assembler #11 tests). Never call it "all passed".
*   **Observable behaviour**: the issue's script on a temp copy of the built os.bdd ends with `A>exit` / `bye!`, and `ls` lists `COPY.B`.
*   **Git status**: clean apart from the new tests, scenario/golden files, harness helper and docs (the CI e2e job fails on any leftover build change).

---

## 6. Fact-Integrity Checklist

| Check | Yes / No / N/A | Notes |
| :--- | :--- | :--- |
| External contracts verified from producer/contract source | N/A | Internal |
| Evidence sources are reproducible | N/A | Internal |
| Identifier directionality / ordering / freshness meaning evidenced | N/A | Internal |
| Every `Assumption` is linked to an Open Question (§3.2) | Yes | A1 is low stakes, closed by the AC text (stronger check covers it) |
| No unresolved Open Questions (for `FINAL`) | Yes | |
| Each Decision states a single committed approach | Yes | |
| Tasks are independent, each with a Definition of Done and test expectations | Yes | T1 and T2 can run in parallel (T2 is docs only) |
| Required infra reflected (toggle / bicep) | N/A | |

**Self-review note**: the main risk is a wrong "already fixed" claim. It is covered by the probe on a fresh build and by reproducing the original symptom through truncating `CP`'s catalog length. In T1, be careful that the cross-drive scenario uses separate temp images and never writes to the built `os.bdd`. Assert the copy's attributes only as the observed `W`-stripping rule. Keep the golden masked.

---

## 7. Amendment Log

| Revision | Request | Decision | Plan changes |
| :--- | :--- | :--- | :--- |
