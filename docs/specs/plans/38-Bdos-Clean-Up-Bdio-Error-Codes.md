# bdos: clean up bdio error codes (duplicates and collisions) — Plan

**Plan Status**: `FINAL`

**Story Type**: `Internal`

**Plan Revision**: `A1`

> This plan captures **what** to build and **why**. The implementation agent discovers the **how** against live code.

---

## 1. Problem Statement

*   **Context**: `src/bdos/bdioh.b` holds the bdio result/error codes, an ABI (G7) shared by bdos and every program on the discs. Today:
    *   `BDIO_FOPEN_FDD_NOT_READY` was defined twice (`0xe1`, then `0xe5`). #19 (PR #148, merged) removed the `0xe1` line, so `0xe5` is the only value now; which value was right was left as an owner question.
    *   `0xe6` = `BDIO_FCREATE_FNAME_EXISTS` **and** `BDIO_FCLOSE_FCAT_READERR`.
    *   `0xe7` = `BDIO_FCLOSE_FCAT_SAVEERR` **and** `BDIO_FEXEC_ATTR_NOEXEC`.
    *   `bdio_printexecres` (in `bdioh.b`) knows only 7 codes (`e0 e3 e5 e7 e8 e9 ea`); everything else prints `unknown error`.
    *   `docs/05-bdos.md` documents the collisions; `design-decisions.md` G7 lists them as a trade-off.
*   **Goal**: one value per meaning, grouped by operation with the gaps documented; every changed code has a message (A1); bdos and all programs rebuilt together; docs and G7 updated.
*   **In scope**: `bdioh.b` defines and `bdio_printexecres`, a check test over `bdioh.b`, an e2e test of the by-hand error paths, `docs/05-bdos.md` error table, G7.
*   **Out of scope**: changing how programs react to codes (they all test `handle < BDIO_FOPEN_FNAME_NOTFOUND`, see §2.4, and that stays valid); FDD device status bytes (`0xe1..0xe3` in the emulator, `README.md`, `docs/01-emulator.md` — a different domain, not bdio results); the `cha` attribute-unset behaviour; bcOS error codes.

### 1.1 Technical Summary

*   **Touched**: `src/bdos/bdioh.b` (constants + `bdio_printexecres`), `src/bdos/bdio.b` only if a renamed/removed name is used there (it is not, see §2.3), new `src/tests/test_bdioh_codes.py`, an e2e test in `src/tests/`, `docs/05-bdos.md`, `docs/specs/memory/design-decisions.md`, `src/bc/code_size.csv` (recorded rows).
*   **New patterns**: a static test that parses `bdioh.b` `#define`s.
*   **Infrastructure changes**: None. Every program is rebuilt (all include `bdioh.b`); disc layout comes from the manifests, so program growth shifts files but nothing is pinned (#89).
*   **End-state observable behaviour**: the shell and utilities print `error: E1 fdd not ready` (was `E5`) and a real message for every bdio error; `hellowrd` without X prints `error: E7 execution not allowed`, `cat` of a file without R prints `error: E3 reading not allowed`, a missing program prints `error: E0 file not found` (unchanged).

---

## 2. Architecture & Design

### 2.1 Architecture Overview

```
program / shell ──bdosh.b wrapper──► bdio_call (bdio.b) ──► returns handle (< 0xe0) or error code (>= 0xe0)
       │                                                       (constants from bdioh.b)
       └── if result >= 0xe0 ──► bdio_printexecres(code)  →  "error: XX <message>"
```

`bdio_printexecres` lives in `bdioh.b`, so it is linked into bdos and every program that includes `bdosh.b`/`bdioh.b` (the compiler links every function of every include).

### 2.2 External Contracts & Evidence

N/A — Internal story.

### 2.3 Affected Areas

| Area / File (pointer) | Role in this change | Likely action |
| :--- | :--- | :--- |
| `src/bdos/bdioh.b` — error `#define`s (`BDIO_FOPEN_*`, `BDIO_FCREATE_*`, `BDIO_FCLOSE_*`, `BDIO_FEXEC_*`, `BDIO_FILE_*`), `bdio_printexecres` | the code table and the message function | Change |
| `src/bdos/bdio.b` | produces the codes by name (`bdio_fbinopen_internal`, `bdio_fclose`, `bdio_execute`, `bdio_finternal`, `bdio_fcreate`, `bdio_getfree_fdesc_internal` → `BDIO_FDESCRIPTOR_NUMBERFULL`) | Reference (no edit expected: only values change; `BDIO_FCREATE_FNAME_EXISTS` is not used anywhere) |
| `src/bdos/{bdos,cat,cha,cp,format,ls,rm,texted}.b` | compare `handle < BDIO_FOPEN_FNAME_NOTFOUND` and call `bdio_printexecres` | Reference (rebuild only) |
| `src/bc64/testdata/e2e/bdio_buffered_prog.b` | compares `h = 0xe0` (file not found) — unchanged value | Reference |
| `src/tests/test_bdioh_codes.py` | new static check (emulator suite: `run_tests.py` puts non-e2e `src/tests/test_*.py` there) | New |
| `src/tests/test_e2e_bdos.py` (or a new `src/tests/test_e2e_bdio_errors.py`) | by-hand error paths | Change / New (add tests only) |
| `docs/05-bdos.md` § "Result and error codes (bdioh.b)" | error table | Change |
| `docs/specs/memory/design-decisions.md` G7 | usage + trade-offs mention `0xe6`/`0xe7` reuse | Change |
| `docs/analysis/05-bdos.md` problem 6 row | names #38 | Optional: mark resolved |
| `src/bc/code_size.csv` | code-size history (metrics only) | Append rows via `scripts/code_size.py --record` |

### 2.4 Key Algorithms & Behaviour

*   **Handle/error split (invariant, verified)**: every caller treats a result `< 0xe0` (`BDIO_FOPEN_FNAME_NOTFOUND`) as a handle and `>= 0xe0` as an error (`bdio_execute`, `cat`, `cha`, `cp`, `format`, `ls`, `rm`, `texted`). So every error code must stay in `0xe0..0xff`, and `BDIO_FOPEN_FNAME_NOTFOUND` stays `0xe0`.
*   **Open returns the attribute code itself**: `bdio_fbinopen_internal` gets `BDIO_FOPEN_ATTR_NOREAD`/`NOWRITE` as its "which attribute to test" parameter and returns it unchanged when the attribute is missing. Those two codes keep their values (`0xe3`, `0xe4`).
*   **Open with no free descriptor** returns `BDIO_FDESCRIPTOR_NUMBERFULL` (`0xff`). It is an error result of open and belongs in the table and in the message function. (`BDIO_FCAT_FREEENTRY_FULL`, `BDIO_FNAME_EOC` are also `0xff` but are catalog bytes, never returned as a result; they are not error codes.)
*   **Final code table** (see D1–D4):

| Code | Name | Operation | Message in `bdio_printexecres` (A1: existing ones kept, new one only for a changed code) |
| :--- | :--- | :--- | :--- |
| `0xe0` | `BDIO_FOPEN_FNAME_NOTFOUND` | open/exec | `file not found` (unchanged) |
| `0xe1` | `BDIO_FOPEN_FDD_NOT_READY` | open/exec | `fdd not ready` (unchanged text; value changed) |
| `0xe2` | `BDIO_FCLOSE_FDESC_NOTFOUND` | close | — (`unknown error`) |
| `0xe3` | `BDIO_FOPEN_ATTR_NOREAD` | open/exec | `reading not allowed` (unchanged) |
| `0xe4` | `BDIO_FOPEN_ATTR_NOWRITE` | open | — (`unknown error`) |
| `0xe5` | — retired — | | (old open "drive not ready"; not reused) |
| `0xe6` | `BDIO_FCLOSE_FCAT_READERR` | close | — (`unknown error`) |
| `0xe7` | `BDIO_FEXEC_ATTR_NOEXEC` | exec | `execution not allowed` (unchanged) |
| `0xe8` | `BDIO_FEXEC_FDESCFCAT_ERR` | exec | unchanged |
| `0xe9` | `BDIO_FEXEC_OUTOFMEM` | exec | unchanged |
| `0xea` | `BDIO_FEXEC_SECTFAIL` | exec | unchanged |
| `0xeb` | `BDIO_FCREATE_READERR` | create | — (`unknown error`) |
| `0xec` | `BDIO_FCREATE_SAVEERR` | create | — (`unknown error`) |
| `0xed` | `BDIO_FCREATE_FDD_NOT_READY` | create | — (`unknown error`) |
| `0xee` | `BDIO_FCREATE_FNAME_FOUND` | create | — (`unknown error`) |
| `0xef` | `BDIO_FCLOSE_FCAT_SAVEERR` | close | `cat save error` — **new** (moved from `0xe7`) |
| `0xf0` | `BDIO_FILE_SAVEERR` | delete/setattr | — (`unknown error`) |
| `0xf1` | `BDIO_FILE_FDD_NOT_READY` | delete/setattr | — (`unknown error`) |
| `0xf2` | `BDIO_FILE_FNAME_NOTFOUND` | delete/setattr | — (`unknown error`) |
| `0xf3`–`0xfe` | free | | |
| `0xff` | `BDIO_FDESCRIPTOR_NUMBERFULL` | open | — (`unknown error`) |

*   **Messages (A1)**: only the changed codes get attention: `0xe1` keeps its existing message (it is matched by name), `0xef` gets the one new message. Codes that had no message keep printing `unknown error` with their code, which still tells them apart.
*   **Size**: `bdio_printexecres` grows by one comparison and one string in bdos and every program. Build-time asserts (`#codelimit` for bdos, `#heap` for programs) catch an overflow; disc positions are derived from the manifests (#89), so no golden pins a size.

---

## 3. Key Decisions & Assumptions

*   **D1 — Drive not ready on open is `0xe1` (owner decision, 2026-11-23).** The owner answered the #19/PR #148 question mid-run: "I would prefer 0xe1". `0xe5` becomes a documented retired gap and is not reused, so an old binary or note showing `E5` is not misread as another error.
*   **D2 — `0xe6` stays `BDIO_FCLOSE_FCAT_READERR`; `BDIO_FCREATE_FNAME_EXISTS` is deleted.** Verified: nothing references `BDIO_FCREATE_FNAME_EXISTS`; `bdio_fcreate` returns `BDIO_FCREATE_FNAME_FOUND` (`0xee`) when the name exists. Deleting a dead name keeps every produced value unchanged ("keep unique codes unchanged where possible").
*   **D3 — `0xe7` stays `BDIO_FEXEC_ATTR_NOEXEC`; `BDIO_FCLOSE_FCAT_SAVEERR` moves to `0xef`.** The exec code is the user-visible one (shell, AC 3), the close catalog-save error is rare; `0xef` has never had a meaning. Close codes are therefore `0xe2`, `0xe6`, `0xef` (not contiguous) — documented in the table rather than renumbering close/exec (which would change more callers' values, against the issue's "keep codes that are already unique unchanged").
*   **D4 — Messages only for the changed codes (Amended in: A1, owner).** `bdio_printexecres` keeps its existing messages (`e0`, `e1` by name, `e3`, `e7`–`ea`) and gains exactly one: `0xef` `cat save error`. The owner chose this to keep every program small ("only changes", 2026-11-23); it is exactly AC 2. Every other code prints `unknown error` with its code. (A0 had a message for every code.)
*   **D5 — The check is a unit test, `src/tests/test_bdioh_codes.py`** (emulator suite, runs in CI `unit`). It parses `bdioh.b` and asserts: no `#define` name occurs twice; among the error codes (every `BDIO_FOPEN_*`, `BDIO_FCREATE_*`, `BDIO_FCLOSE_*`, `BDIO_FEXEC_*`, `BDIO_FILE_*` define whose value is `>= 0xe0`, plus `BDIO_FDESCRIPTOR_NUMBERFULL`) no value occurs twice; every error code is `>= 0xe0`; `BDIO_FOPEN_FNAME_NOTFOUND` is `0xe0`; every changed code's name (`BDIO_FOPEN_FDD_NOT_READY`, `BDIO_FCLOSE_FCAT_SAVEERR`) is compared in `bdio_printexecres` (A1). Placed in `src/tests/` because bdos has no tests folder and its e2e tests already live there.
*   **D6 — By-hand error paths are covered by an e2e test** using the session verified in the spike: `cha -x hellowrd.prg` then `hellowrd` → `error: E7 execution not allowed`; `cha -r test.b` then `cat -c test.b` → `error: E3 reading not allowed`; `foo` → `error: E0 file not found`. Markers are enough; a golden is optional (masked with `DISC_MASKS` if added).
*   **D7 — No program source changes.** All callers use names and the `< 0xe0` split; a full rebuild is the whole update.
*   **Assumption A1** — none affecting correctness.
*   **Note for the PR**: the issue says "Update ... the shell and every program that compares codes": verified that none needs a source edit (D7); the rebuild covers it. Not a deviation from an AC.

### 3.1 Decision Lock (Constants & Policies)

| Constant / Policy | Selected Value | Why | Where it lives |
| :--- | :--- | :--- | :--- |
| `BDIO_FOPEN_FDD_NOT_READY` | `0xe1` | owner, D1 | `bdioh.b` |
| `BDIO_FCLOSE_FCAT_SAVEERR` | `0xef` | D3 | `bdioh.b` |
| `BDIO_FCREATE_FNAME_EXISTS` | removed | dead name, D2 | `bdioh.b` |
| Retired value | `0xe5` (not reused) | D1 | docs table |
| Error range | `0xe0..0xff`, handles `< 0xe0` | callers' split | `bdioh.b`, test |
| Message format | `error: %x %s` (unchanged) | goldens/tests match `error: E0 file not found` | `bdio_printexecres` |

### 3.2 Open Questions

None. (The `0xe1`/`0xe5` question from PR #148 was answered by the owner, D1.)

---

## 4. Task Breakdown

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| `T1` | Renumber codes, messages for changed codes, check test, rebuild | — | `Medium` |
| `T2` | e2e test of the by-hand error paths | `T1` | `Low` |
| `T3` | Docs: error table and G7 | — | `Low` |

### T1 — Renumber codes, messages for changed codes, check test, rebuild
*   **Amended in**: A1
*   **Goal**: `bdioh.b` has the §2.4 table (one value per meaning), `bdio_printexecres` has a message for every changed code, and a unit test guards both.
*   **Depends on**: —
*   **Complexity**: `Medium`
*   **Pointers**: `src/bdos/bdioh.b`; producers in `src/bdos/bdio.b` (reference); `src/tests/` (new `test_bdioh_codes.py`); `scripts/code_size.py`.
*   **Definition of Done**:
    *   `BDIO_FOPEN_FDD_NOT_READY` = `0xe1`, `BDIO_FCLOSE_FCAT_SAVEERR` = `0xef`, `BDIO_FCREATE_FNAME_EXISTS` gone, all other values unchanged; error defines grouped by operation with a short comment block naming the groups and the gaps (`0xe5` retired, `0xf3`–`0xfe` free, `0xff` = no free handle).
    *   `bdio_printexecres` keeps its existing messages and adds only `0xef` `cat save error` (D4, A1); other codes still print `unknown error`; the output format stays `error: %x %s`.
    *   Full rebuild from `src/`: `./buildos && ./buildtools && ./buildapps && ./makedisc` succeeds (no assert failure). Report bdos end address and the largest per-program growth.
    *   `python3 scripts/code_size.py --record` appended the changed rows to `src/bc/code_size.csv`.
    *   `python3 run_tests.py < /dev/null` exits 0 from the repo root (full suite incl. e2e; foreground, ~8 min).
*   **Tests expected**: unit (`src/tests/test_bdioh_codes.py`): the D5 invariants, each as its own test; plus one test that the specific fixed values hold (`e1`, `ef`, `e6` = close read error, `e7` = exec not executable) so a regression names the code.
*   **Tests to modify**: None.

### T2 — e2e test of the by-hand error paths
*   **Goal**: AC 3's three error paths are triggered in a headless session on a temp copy of the built `os.bdd` and their messages asserted.
*   **Depends on**: `T1` (messages; and no two builds in one worktree at once)
*   **Complexity**: `Low`
*   **Pointers**: `src/tests/test_e2e_bdos.py` (pattern: `run_session`, `assert_markers`, `LIMIT`), `src/tests/e2e_harness.py`.
*   **Definition of Done**: a new e2e test (new test method or new `src/tests/test_e2e_bdio_errors.py`) runs `cha -x hellowrd.prg`, `hellowrd`, `cha -r test.b`, `cat -c test.b`, `foo`, `exit` and asserts `error: E7 execution not allowed`, `error: E3 reading not allowed`, `error: E0 file not found`, `bye!`; `python3 run_tests.py --group e2e < /dev/null` exits 0.
*   **Tests expected**: e2e, markers (golden optional, masked).
*   **Tests to modify**: None.

### T3 — Docs: error table and G7
*   **Amended in**: A1
*   **Goal**: the docs describe the new table and the ABI rule.
*   **Depends on**: —
*   **Complexity**: `Low`
*   **Pointers**: `docs/05-bdos.md` § "Result and error codes (bdioh.b)"; `docs/specs/memory/design-decisions.md` G7; optionally `docs/analysis/05-bdos.md` problem 6 (mark fixed by #38).
*   **Definition of Done**: the `05-bdos.md` table lists every code of §2.4 grouped by operation, with the message only where `bdio_printexecres` has one (others: `unknown error`, A1), marks `0xe5` retired and `0xf3`–`0xfe` free, and states the `< 0xe0` handle / `>= 0xe0` error split; G7 drops the "codes are reused (`0xe6`, `0xe7`)" trade-off, says one value per meaning, never reuse a retired value, keep the `>= 0xe0` split, a new or changed code gets a message in `bdio_printexecres` (codes without one print `unknown error`), and records the owner's `0xe1` choice (D1) with #38.
*   **Tests expected**: none (docs).
*   **Tests to modify**: None.

---

## 5. Verification

*   **Build**: `cd src && ./buildos && ./buildtools && ./buildapps && ./makedisc` — no errors or assert failures.
*   **Tests**: `python3 run_tests.py < /dev/null` from the repo root — exit 0 (state any expected failures by name; there should be none new).
*   **Static check**: `src/tests/test_bdioh_codes.py` passes; `git grep -n FNAME_EXISTS` finds nothing in `src/`.
*   **Observable behaviour** (headless, copy of `src/os.bdd`): `printf 'cha -x hellowrd.prg\nhellowrd\ncha -r test.b\ncat -c test.b\nfoo\nexit\n' | python3 bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81 --disk-a <copy> --output out.txt` prints `error: E7 execution not allowed`, `error: E3 reading not allowed`, `error: E0 file not found`.
*   **CI**: `tests` workflow green (unit 3.10/3.14, e2e with clean `git status`).

---

## 6. Fact-Integrity Checklist

| Check | Yes / No / N/A | Notes |
| :--- | :--- | :--- |
| External contracts verified from source | N/A | Internal |
| Evidence sources reproducible | N/A | Internal |
| Identifier meaning evidenced | N/A | Internal |
| Every `Assumption` linked to an Open Question | Yes | none |
| No unresolved Open Questions (for `FINAL`) | Yes | D1 answered by owner |
| Each Decision states a single committed approach | Yes | |
| Tasks independent, each with DoD and test expectations | Yes | T2 after T1 to avoid parallel builds |
| Required infra reflected | N/A | |

**Self-review**: verified by grep that `BDIO_FCREATE_FNAME_EXISTS` is unused and that every caller uses the `< 0xe0` split; spike on a fresh build (2026-11-23) showed E7/E3/E0 already reachable by hand with `cha`, so T2 adds coverage, not behaviour. `0xe1` collides only with the FDD *device* status `STATE_DRIVE_FAILURE`, which never reaches a bdio caller as a result (bdio compares FDD results only against `FDD_RESULT_OK`).

---

## 7. Amendment Log

| Rev | Request | Decision | Plan changes |
| :--- | :--- | :--- | :--- |
| A1 | contradiction — owner: messages for changed codes only (D4 gave every code one) | accepted (owner instruction; matches AC 2 exactly) | D4 rewritten; §2.4 message column, D5 invariant; T1, T3 amended |
