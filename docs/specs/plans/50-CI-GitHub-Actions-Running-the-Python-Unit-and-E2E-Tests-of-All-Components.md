# CI: GitHub Actions Running the Python Unit and E2E Tests of All Components Plan

**Plan Status**: `FINAL`

**Story Type**: `Internal`

**Plan Revision**: `A0`

**Issue**: [bcichonski/bc16#50](https://github.com/bcichonski/bc16/issues/50)

**Builds on**: #48 (one test runner, `run_tests.py`), #49 (e2e harness and scenarios), #3 (headless emulator, frozen smoke disc).

---

## 1. Problem Statement

There is no CI. `.github/` doesn't exist, so a regression shows up only when somebody runs
`python3 run_tests.py` by hand. The story adds a GitHub Actions workflow that runs the Python test
suites of every component on each push and pull request to `bc64`, with the unit tests and the
headless end-to-end tests as separate jobs, a per-component summary, and the transcript diffs as an
artifact when the e2e job fails.

Out of scope (per the issue): `build.py all`, the committed-outputs `git diff --exit-code` check (G3)
and the code-size report from `docs/analysis/06-toolchain.md` next step 3.

### 1.1 Technical Summary

- **Acceptance criteria, as verifiable facts:**
  - AC-1: a push or PR to `bc64` runs the workflow; both Python versions (3.10 and the newest) pass.
  - AC-2: each component's suite (emulator, assembler, compiler, `ftool`) runs and is visible in the
    log or the job summary.
  - AC-3: the e2e job runs after the unit job, and on failure uploads the transcript diffs.
  - AC-4: a deliberately broken test makes the run red (checked once, on a throwaway PR).
  - AC-5: a normal run finishes in under 10 minutes.
  - AC-6: a CI status badge in `README.md`; the root `CLAUDE.md` says CI must be green before merge,
    and the `/grind` workflow refers to it.
  - AC-7 (owner, recommended): the workflow is a required status check on `bc64`.
- **Proposal facts from the issue body** (closed, not open questions): file
  `.github/workflows/tests.yml`; triggers `push` to `bc64` and `pull_request` targeting `bc64`;
  `concurrency` cancels superseded runs; job `unit` on `ubuntu-latest` with a 3.10 + newest matrix,
  `actions/setup-python` with pip cache, install `parsy`; job `e2e` with `needs: unit`, newest
  Python only, `timeout-minutes` plus `--max-instructions`; `$GITHUB_STEP_SUMMARY` pass/fail counts
  per component; the workflow never touches `release/` and never writes `cpudebug.log`.
- **Comment refinement (owner, 2026-11-09):** the e2e job refreshes the frozen disc on every run —
  copy `src/os.bdd` to `src/bc64/testdata/smoke.bdd`, regenerate `smoke_transcript.txt` with the
  command in `src/bc64/CLAUDE.md` → "End-to-end (smoke) tests", fail on
  `git diff --exit-code src/bc64/testdata/` (upload the diff), then run the smoke test.
- **Verified in this worktree (2026-11-09, origin/bc64 @ `75a8c46`):**
  - `python3 run_tests.py < /dev/null` passes on Python 3.14.4 (emulator 328 tests, assembler 160,
    compiler 58) in ~37 s; it also passes on Python 3.10 (`python:3.10-slim` Docker image,
    `pip install parsy`). The 3.10 lower bound needs no code change.
  - Of those 37 s, the e2e + smoke modules (`src/test_e2e_*.py`, `src/test_bc64_smoke.py`) take
    ~35 s. AC-5 has ample headroom.
  - `src/os.bdd` and `src/bc64/testdata/smoke.bdd` are byte-identical today, so the refresh step
    is green on the current tree.
  - The only dependency is `parsy>=2.2` in `requirements.txt` (no `pyproject.toml` yet, #12), which
    also serves as the pip-cache key file.
  - The runner today has three suites (`emulator` = all `src/test_*.py` incl. `ftool` and e2e,
    `assembler`, `compiler`) and prints one `PASS`/`FAIL` line per suite. `ftool` and e2e are not
    separately visible.
  - The e2e harness (`src/e2e_harness.py`) runs each scenario in a temp dir and compares with
    goldens in `src/bc64/testdata/e2e/`; `BC64_UPDATE_GOLDEN=1` rewrites the goldens instead of
    failing. Slow scenarios run only with `BC64_E2E_SLOW=1`.
  - Transcripts and goldens contain CRLF in the committed blobs; the GitHub runner checks out blob
    bytes unchanged (no `autocrlf`), so byte-exact comparisons hold there.

---

## 2. Architecture & Design

### 2.1 Architecture Overview

#### Involved services & owners

| Component | Owner | Change |
|---|---|---|
| `run_tests.py` (root test runner) | repo | component-level suites, unit/e2e group selection, job summary |
| `.github/workflows/tests.yml` | repo | new workflow |
| `README.md`, `CLAUDE.md`, `src/bc64/CLAUDE.md`, `docs/analysis/06-toolchain.md` | repo | badge, CI rules, docs |

#### C2 diagram

```
push/PR → bc64
      │
      ▼
 tests.yml ──► job unit  (matrix: 3.10, 3.14)  ── run_tests.py --group unit ──► summary table
                    │ needs
                    ▼
               job e2e   (3.14)  ── refresh smoke.bdd + transcript ── git diff ──► run_tests.py --group e2e
                                                                         │ on failure
                                                                         ▼
                                                     regenerate goldens → diff → upload artifact
```

#### Flow diagram

e2e job: checkout → setup-python → install → refresh `smoke.bdd` from `os.bdd` → regenerate the smoke
transcript in a temp dir → `git diff --exit-code src/bc64/testdata/` → `run_tests.py --group e2e` →
(on failure) regenerate e2e goldens with `BC64_UPDATE_GOLDEN=1`, write `git diff` to a patch file,
upload patch + changed testdata → (always) guard: no `cpudebug.log`, `release/` untouched.

### 2.2 External Contracts & Evidence

`N/A — Internal story`. (GitHub Actions marketplace actions are used through their stable major
tags; no new external API is called by the project.)

### 2.3 Affected Areas

- `run_tests.py` — suite table, `main()`, `summarise()`.
- New: `.github/workflows/tests.yml`.
- New test module for the runner's pure logic: `src/test_run_tests.py` (co-located with the
  emulator/tool tests that `run_tests.py`'s `src` suites discover; it imports the root
  `run_tests.py` by path and never spawns the suites itself).
- `README.md` (badge), root `CLAUDE.md` (CI section, tests commands), `src/bc64/CLAUDE.md`
  (smoke section: CI does the refresh), `docs/analysis/06-toolchain.md` (problem "No CI", next step 3).

### 2.4 Key Algorithms & Behaviour

**Component suites.** The runner reports one line per component, in this order:

| Suite | Group | Directory | Modules |
|---|---|---|---|
| `emulator` | unit | `src` | `src/bc64/test_*.py` and every other `src/test_*.py` not listed below (today: `test_bc64_cli.py`, plus the new `test_run_tests.py`) |
| `ftool` | unit | `src` | `src/test_ftool.py` |
| `assembler` | unit | `src/bc81asmc` | `*_tests.py` (unchanged) |
| `compiler` | unit | `src/bc` | `*_tests.py` (unchanged) |
| `e2e` | e2e | `src` | `src/test_e2e_*.py` and `src/test_bc64_smoke.py` |

- The selection must be by rule, not a hard-coded list of today's files, so a new `src/test_*.py`
  lands in `emulator` and a new `src/test_e2e_*.py` lands in `e2e` automatically.
- **Invariant:** with no option (`--group all`, the default) the union of the five suites is exactly
  the set of tests `run_tests.py` runs today — same total count (546 on the current tree, plus the
  new runner tests), no test run twice, none dropped. Each suite still runs in its own subprocess
  with its own working directory (flat imports).
- `--group unit` runs the four unit suites; `--group e2e` runs only `e2e`. Exit code 0 only if every
  selected suite passes. The existing output lines and the `ALL PASSED` / `SOME SUITES FAILED`
  footer stay.
- **Job summary.** When the environment variable `GITHUB_STEP_SUMMARY` names a file, the runner
  appends a Markdown table: one row per suite run, with result, tests run, failures, errors,
  skipped and expected failures (parsed from unittest's output; a suite that crashed before
  reporting shows its exit code). Unset → nothing is written, so local runs are unchanged.

**Workflow** (`.github/workflows/tests.yml`, workflow name `tests`):
- Triggers: `push` to `bc64`; `pull_request` with base `bc64`. `concurrency` group per workflow +
  ref, `cancel-in-progress: true`. `permissions: contents: read`.
- Job `unit`: `ubuntu-latest`, matrix Python `3.10` and `3.14`, `fail-fast: false`,
  `timeout-minutes: 10`; `actions/setup-python` with `cache: pip` keyed on `requirements.txt`;
  `pip install -r requirements.txt`; `python run_tests.py --group unit < /dev/null`.
- Job `e2e`: `needs: unit`, Python `3.14`, `timeout-minutes: 10`. Steps as in §2.1 flow. The smoke
  transcript regeneration uses the same command as `src/bc64/CLAUDE.md` (temp dir,
  `--max-instructions 200000000`, stdin from `/dev/null`). Every emulator run in CI is bounded by
  `--max-instructions` (the harness and smoke test already pass one) plus the job timeout.
- The failure-artifact step runs `if: failure()`, regenerates the e2e goldens with
  `BC64_UPDATE_GOLDEN=1` (the default, non-slow scenarios), writes `git diff` of
  `src/bc64/testdata/` (binary-aware) to a patch file, and uploads the patch and
  `src/bc64/testdata/` with `actions/upload-artifact`. It must also capture the smoke-transcript diff
  when the refresh check is what failed.
- A final guard step (`if: always()`, both jobs) fails if any `cpudebug.log` exists in the checkout
  or if `release/` has any change (tracked or untracked).
- The workflow never passes `d` (trace) to the emulator and never writes outside the checkout and
  the runner temp dir.

---

## 3. Key Decisions & Assumptions

- **D1 — Newest Python is 3.14.** The issue allows 3.13 or 3.14; the sandbox and the owner's
  recent work use 3.14, and #13 made the compiler run on 3.13+. 3.10 is the floor (also the
  `requires-python` planned in #12).
- **D2 — Split by component inside `run_tests.py`, not in YAML.** The workflow calls the one runner
  with `--group`; the per-component split and the summary live in the runner so local runs and CI
  report the same thing (AC-2) and there is still one command (#48).
- **D3 — `ftool` gets its own suite line** (AC-2 names it); it still runs from `src`.
- **D4 — E2E artifact via golden regeneration.** Instead of changing the harness to save actual
  outputs, the failure step reruns the e2e modules with `BC64_UPDATE_GOLDEN=1` and diffs the
  testdata dir; the smoke refresh step already produces its diff in-tree. No test file changes.
- **D5 — Slow e2e scenarios stay off in CI** (`BC64_E2E_SLOW` unset), matching the local default
  and AC-5.
- **D6 — `/grind` reference lives in the repo.** The `/grind` skill is user tooling outside this
  repo (`/c/workspace/.claude/skills`), so it is not edited here. The root `CLAUDE.md` gets a CI
  section that `/grind`'s agents read: CI (`tests` workflow) must be green before merge, and a
  `/grind` PR is finished only when its `tests` checks pass (its PR monitor watches them).
- **D7 — Owner-only ACs.** AC-4 (deliberately broken test on a throwaway PR) and AC-7 (required
  status check) need actions on GitHub beyond this branch; they are left to the owner and listed
  in the PR description. This run covers AC-4 locally (a failing test makes `run_tests.py` exit
  non-zero in both groups, covered by the runner tests) and AC-1 by this story's own PR, whose
  `pull_request` event targets `bc64` and runs the new workflow.
- **D8 — Action versions:** `actions/checkout@v5`, `actions/setup-python@v6`,
  `actions/upload-artifact@v4` (major tags).

### 3.1 Decision Lock (Constants & Policies)

| Item | Value |
|---|---|
| Workflow file / name | `.github/workflows/tests.yml` / `tests` |
| Python matrix | `3.10`, `3.14` (e2e: `3.14`) |
| Job timeouts | 10 min each |
| Runner groups | `--group unit` / `--group e2e` / `--group all` (default) |
| Suite names | `emulator`, `ftool`, `assembler`, `compiler`, `e2e` |
| Badge | `https://github.com/bcichonski/bc16/actions/workflows/tests.yml/badge.svg?branch=bc64` |

### 3.2 Open Questions

None.

---

## 4. Task Breakdown

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| `T1` | Runner: component suites, `--group`, job summary | — | `Medium` |
| `T2` | Workflow `tests.yml` (unit matrix, e2e with smoke refresh and failure artifact) | `T1` | `Medium` |
| `T3` | Docs: badge, CI rules in `CLAUDE.md`, toolchain analysis | `T2` | `Low` |

### T1 — Runner: component suites, `--group`, job summary

*   **Goal**: `run_tests.py` reports `emulator`, `ftool`, `assembler`, `compiler` and `e2e` separately,
    can run only the unit or only the e2e group, and writes a Markdown summary table when
    `GITHUB_STEP_SUMMARY` is set (§2.4).
*   **Depends on**: `—`.
*   **Complexity**: `Medium`.
*   **Pointers**: `run_tests.py`; new `src/test_run_tests.py`; root `CLAUDE.md` "Tests" block for the
    command forms (doc update itself is T3).
*   **Definition of Done**: the selection rule of §2.4 holds; `python3 run_tests.py < /dev/null` runs
    the same total number of pre-existing tests as before (546) plus the new ones, exit 0;
    `--group unit` and `--group e2e` each run only their suites and their counts add up to the
    total; summary table written only when the env var is set; standard library only; still works
    from any working directory.
*   **Tests expected**: unit tests of the runner's pure logic in `src/test_run_tests.py` — selection
    partitions the `src/test_*.py` modules (no overlap, no gap, rule-based for new files), group
    filtering, summary parsing of unittest output (OK, FAILED with failures/errors, skipped,
    expected failures, crash with no `Ran` line), Markdown table rendering, and that the summary is
    not written when the env var is absent. They must not spawn the real suites. One check that a
    failing suite yields a non-zero exit (AC-4 locally) may use a stub/fake suite run.
*   **Tests to modify**: `None`.

### T2 — Workflow `tests.yml`

*   **Goal**: `.github/workflows/tests.yml` as specified in §2.4 / §3.1.
*   **Depends on**: `T1` (uses `--group` and the summary).
*   **Complexity**: `Medium`.
*   **Pointers**: `.github/workflows/tests.yml` (new); `src/bc64/CLAUDE.md` "End-to-end (smoke)
    tests" for the regeneration command; `src/e2e_harness.py` for `BC64_UPDATE_GOLDEN`.
*   **Definition of Done**: valid workflow YAML (lint with `actionlint` via Docker if available, else
    a YAML parse); triggers, concurrency, permissions, matrix, cache, timeouts, `needs`, failure
    artifact and the `cpudebug.log`/`release/` guard all present; every shell step's commands run
    green locally from a clean checkout (smoke refresh + `git diff --exit-code src/bc64/testdata/`
    leaves the tree clean, `--group unit`, `--group e2e`), and the failure-artifact commands
    produce a non-empty patch when a golden is deliberately perturbed (revert the perturbation
    afterwards, without git stash/checkout).
*   **Tests expected**: none in the Python suites (workflow config); local dry run of the steps as
    above, recorded in the task notes.
*   **Tests to modify**: `None`.

### T3 — Docs

*   **Goal**: AC-6 and the doc updates of §2.3.
*   **Depends on**: `T2`.
*   **Complexity**: `Low`.
*   **Pointers**: `README.md` (badge near the top), root `CLAUDE.md` (new "CI" section per D6; the
    tests block gains `--group`), `src/bc64/CLAUDE.md` (CI performs the smoke refresh and fails on an
    unreviewed disc change), `docs/analysis/06-toolchain.md` (problem 3/"No CI" line and next step 3:
    items 1–3 and 6 done in #50, items 4–5 and the code-size report remain).
*   **Definition of Done**: badge links to the workflow on `bc64`; `CLAUDE.md` states CI must be
    green before merge and how `/grind` uses it; no other doc claims there is no CI.
*   **Tests expected**: none.
*   **Tests to modify**: `None`.

---

## 5. Verification

1. `python3 run_tests.py < /dev/null` → `ALL PASSED`, five suite lines, totals as in T1.
2. `python3 run_tests.py --group unit < /dev/null` and `--group e2e` → each passes; counts add up.
3. `GITHUB_STEP_SUMMARY=$(mktemp) python3 run_tests.py < /dev/null` → the file holds the table.
4. Optional: the same on Python 3.10 via `docker run --rm -v "$PWD":/w -w /w python:3.10-slim sh -c "pip install -q parsy && python run_tests.py < /dev/null"`.
5. `actionlint` (Docker `rhysd/actionlint`) on the workflow, if the image can be pulled.
6. The PR for this story targets `bc64`, so its own `tests` run is the end-to-end check of AC-1/2/3/5.

## 6. Fact-Integrity Checklist

| Check | Yes / No / N/A | Notes |
| :--- | :--- | :--- |
| External contracts verified from producer/contract source | N/A | Internal |
| Evidence sources are reproducible | N/A | Internal |
| Identifier directionality / ordering / freshness meaning evidenced | N/A | Internal |
| Every `Assumption` is linked to an Open Question (§3.2) | Yes | none left; D6/D7 are decisions |
| No unresolved Open Questions (for `FINAL`) | Yes | |
| Each Decision states a single committed approach | Yes | |
| Tasks are independent, each with a Definition of Done and test expectations | Yes | |
| Required infra reflected | N/A | no toggle, no Service Bus |

**Self-review note**: The GitHub Actions run can't be executed locally, so T2 is checked by linting
and by running each step's commands by hand; the story's own PR is the first real run. Take care in
T1 that the new partition keeps the exact same pre-existing test count, and that the e2e group still
runs from `src` with flat imports. Python 3.10 was verified only by a Docker run of today's tree;
T1's new code must stay 3.10-compatible (no 3.11+ syntax or stdlib).

## 7. Amendment Log

| Rev | Request | Decision | Plan changes |
|---|---|---|---|
