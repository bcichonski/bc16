# Build before Test: Stop Committing the ROM, `os.bdd` and `smoke.bdd` (Rest of #90) Plan

**Plan Status**: `FINAL`

**Story Type**: `Internal`

**Plan Revision**: `A0`

> This plan captures **what** to build and **why**: domain, architecture, decisions and verified facts.
> It does **not** contain implementation code, pseudocode, line numbers or test bodies.

Issue: [bcichonski/bc16#92](https://github.com/bcichonski/bc16/issues/92) (no comments). PR base: `bc64`.
Predecessor: #90 (PR #91, merged as `ee35df4`). This story restores #90's original rules
"what is committed" and "build before test", which the #90 plan had relaxed in its decisions D8/D9.

---

## 1. Problem Statement

CI's e2e job builds every output and then **restores** the committed ROM (`bcos_v1_2_0.b81`) and system
disc (`src/os.bdd`) with `git checkout`, and most e2e scenarios boot a frozen copy of the disc
(`src/bc64/testdata/smoke.bdd`). So a change to bcOS, bdos or a program that is not followed by a rebuild
and commit still passes CI on the old binaries. This story stops committing these three binaries and makes
every test that boots the machine use images built from the sources in the same run.

### 1.1 Technical Summary

* Untrack the ROM, `src/os.bdd` and `src/bc64/testdata/smoke.bdd`, and drop their `.gitignore` negations.
* `run_tests.py` builds the pipeline (`buildos → buildtools → buildapps → makedisc`) before the e2e suite
  (`--group e2e` and `all`); `--no-build` skips it. Unit suites never trigger it.
* Every e2e test, including the smoke transcript test, boots a temp copy of the freshly built `src/os.bdd`.
  `smoke.bdd` is deleted. `smoke_transcript.txt` and the e2e goldens stay committed.
* Unit tests that boot the real ROM move to the e2e group (the unit CI job has no build).
* CI: the e2e job uses `run_tests.py`'s build, never restores binaries, and keeps the "build leaves no
  change" check. `release.yml` drops the restore too.
* `scripts/make_release.py bc64` takes the ROM and `os.bdd` from the build in the working tree.
* `src/run` prints the build command when the ROM or `os.bdd` is missing.
* Docs describe the rule (README, CLAUDE.md files, docs 01/04/05, design decision G12).

---

## 2. Architecture & Design

### 2.1 Architecture Overview

#### Involved services & owners

| Service | Technical Owner |
| :--- | :--- |
| `bc16` repo (test runner, e2e tests, release script, CI, docs) | repo owner (bcichonski) |

#### Flow diagram

```
python3 run_tests.py [--group all|e2e]               python3 run_tests.py --group unit
      │                                                     │
      ├─ (unless --no-build) build in src/:                 └─ unit suites only, no build,
      │    ./buildos && ./buildtools && ./buildapps            never read the ROM / os.bdd
      │    && ./makedisc   → bcos_v1_2_0.b81, os.bdd (ignored)
      │      build fails → e2e FAIL (build output shown), e2e not run
      ├─ (--no-build) a needed output missing → e2e FAIL with the build command
      └─ e2e suite → every scenario boots a temp copy of src/os.bdd + the built ROM

CI tests.yml e2e:  pip install -e . → run_tests.py --group e2e (builds) → guard: git status clean
release.yml:       build → git status clean → run_tests.py --no-build → make_release.py bc64
                   (ROM + os.bdd taken from the working tree build) → zip
```

### 2.2 External Contracts & Evidence

N/A — Internal story.

### 2.3 Affected Areas

Verified facts (2026-11-12, worktree at `origin/bc64` = `ee35df4`):

* `git ls-files '*.b81' '*.bdd' '*.btap' '*.sector' '*.sectors'` lists `src/bc64/testdata/smoke.bdd`,
  `src/bc81asmc/bcOS/bcos_v1_2_0.b81`, `src/bdos/testb.sectors`, `src/os.bdd`. There is no other
  `testdata/*.bdd` fixture and no `src/utils.bdd`.
* A full pipeline build in the sandbox (`cd src && ./buildos && ./buildtools && ./buildapps && ./makedisc`)
  leaves `git status` clean, i.e. the freshly built ROM and `os.bdd` are **byte-identical** to the committed
  ones, and `os.bdd` is byte-identical to `smoke.bdd`. So pointing every test at the fresh `os.bdd` keeps
  the committed transcript and goldens valid.
* Baseline `python3 run_tests.py` (after the build): emulator 351 OK (3 xfail), ftool 84, assembler 231
  (7 xfail), compiler 66, release 37, e2e passes.
* `src/run` piped `os.bdd\nls\nexit\n` boots the disc and runs `ls` headless (exit 0).
* Unit-group tests that boot the real ROM: `src/bc64/tests/test_bc64_cli.py ::
  test_no_floppy_boots_the_real_rom_to_the_prompt` and `src/tests/test_bc64_toolchain.py ::
  test_bc64_headless_run_matches_the_script`. Both would fail in the unit CI job once the ROM is untracked.
* `scripts/tests/test_make_release.py :: Bc64ZipTests` (unit group) builds a real bc64 zip from HEAD;
  `make_bc64` refuses unless `src/os.bdd` and the ROM are tracked.

| Area / File (pointer) | Role in this change | Likely action |
| :--- | :--- | :--- |
| `.gitignore` | negations keeping ROM, `os.bdd`, `utils.bdd`, `testdata/*.bdd` | Change |
| `run_tests.py` | runner; today only reports missing manifest sources | Change: build step, `--no-build` |
| `src/tests/test_run_tests.py` | runner tests | Add tests; adapt hint tests to `--no-build` |
| `src/tests/e2e_harness.py` | `OS_DISK`, `SMOKE_DISK`, `ROM` constants | Change: drop `SMOKE_DISK` |
| `src/tests/test_bc64_smoke.py` | transcript test on `smoke.bdd`, live test on `os.bdd` | Change: both on `os.bdd` |
| `src/tests/test_e2e_*.py` using `h.SMOKE_DISK` | shell / texted / theodore / disc / harness scenarios | Change: use `h.OS_DISK` |
| `src/bc64/testdata/smoke.bdd` | frozen disc | Delete |
| `src/bc64/testdata/smoke_transcript.txt`, `e2e/*` | expected output | Keep (unchanged) |
| `src/bc64/tests/test_bc64_cli.py`, `src/tests/test_bc64_toolchain.py` | real-ROM tests in the unit group | Move those two tests to a new e2e module |
| `scripts/make_release.py`, `scripts/tests/test_make_release.py` | bc64 zip from tracked files | Change: built ROM/`os.bdd` from the working tree |
| `src/run` | interactive launcher | Change: missing-build message |
| `.github/workflows/tests.yml`, `release.yml` | CI | Change |
| `README.md`, `CLAUDE.md`, `src/bc64/CLAUDE.md`, `src/bdos/CLAUDE.md`, `docs/01-emulator.md`, `docs/04-bcos.md`, `docs/05-bdos.md`, `docs/specs/memory/design-decisions.md` (G3, G12, the e2e decision naming `smoke.bdd`) | rules and how-tos | Change |

### 2.4 Key Algorithms & Behaviour

**Runner build rule (`run_tests.py`).**
* The build runs once, before any suite, when the selected suites include the e2e suite (suite **name**
  `e2e`; `--group e2e` or `all`) and `--no-build` is not given. `--group unit` never builds.
* It runs the pipeline in `src/` exactly as the docs state it (`./buildos && ./buildtools && ./buildapps &&
  ./makedisc`, via `bash`, stdin closed), and prints one line before it starts (e.g. `build      ...`), then a
  `build PASS/FAIL` line in the same style as the suite lines.
* Build failure: the e2e suite is reported FAIL ("not run, the build failed"), the captured build output is
  shown, the other selected suites still run, exit code 1.
* With `--no-build`: when a needed output is missing — the ROM, `src/os.bdd`, or a manifest source (the
  existing `missing_disc_source` check) — e2e is reported FAIL with the missing path and the build
  command, and is not run (today's behaviour, extended to the ROM and `os.bdd`).
* The build is injectable in `main()` (like `runner`) so the runner's own tests never run the real pipeline.

**e2e images.** Every e2e scenario boots a **temp copy** of the freshly built `src/os.bdd`; nothing writes
the built image itself (the harness already checks the source image is unchanged). The smoke transcript test
compares the session on `os.bdd` byte for byte with `smoke_transcript.txt`; its regenerate hint now
copies `os.bdd`. An intended output change is handled as today: regenerate the transcript/goldens and review.

**Release zip (`make_release.py bc64`).** Tracked files at HEAD as before, plus the two **built files**
`src/os.bdd` and `src/bc81asmc/bcOS/bcos_v1_2_0.b81` read from the working tree (mode 0644). If either is
missing it fails with one line naming the file and the build command. The working-tree location is a
parameter of `make_bc64` (default: the repo root) so the release tests can supply stand-in files without a
build.

**`src/run`.** Before starting the emulator, if the ROM or `os.bdd` is missing in `src/`, print which file
is missing and the build command (`./buildos && ./buildtools && ./buildapps && ./makedisc`) to stderr and exit
1. Otherwise behave as today.

---

## 3. Key Decisions & Assumptions

* **D1 — No hand-made `.bdd` fixtures remain.** The only `testdata/*.bdd` is `smoke.bdd`, which is a copy of
  the built `os.bdd` (byte-identical today), so it is deleted, not kept as a fixture. AC1's tracked list is
  therefore exactly `src/bdos/testb.sectors`. The `!src/utils.bdd` negation also goes: `utils.bdd` will be a
  build output too (#85).
* **D2 — Build trigger is the e2e suite, inside `run_tests.py`.** CI and local runs use the same code path.
  CI's e2e job calls `run_tests.py --group e2e` (which builds) and then checks `git status --porcelain` is
  empty, so the "build leaves no tracked change" guard is kept and also covers files left by tests.
* **D3 — The harness drops `SMOKE_DISK`;** every caller uses `h.OS_DISK`. A leftover alias would hide that
  the frozen disc is gone. Tests that only duplicated an `os.bdd` check for `smoke.bdd`
  (`test_e2e_disc :: test_smoke_bdd_matches_manifest`, the `SMOKE_DISK` half of
  `test_e2e_theodore :: test_catalog_entry_and_ls`) lose that duplicate.
* **D4 — The smoke module keeps both tests,** both on `os.bdd`: the byte-exact transcript test and the
  marker-only live test (`smoke_live_session.txt`). Removing the live test is not asked for.
* **D5 — Real-ROM tests move to the e2e group.** `test_no_floppy_boots_the_real_rom_to_the_prompt` and
  `test_bc64_headless_run_matches_the_script` move, unchanged in behaviour, to a new module
  `src/tests/test_e2e_rom.py` (picked up by `select_src_modules` as e2e). The unit job has no build (AC2:
  "Unit suites don't trigger it"); skipping them when the ROM is missing would silently drop coverage.
* **D6 — `release.yml`** keeps its explicit build step and clean-status check (the zip needs the build),
  drops the restore line, and runs `run_tests.py --no-build` so it doesn't build twice.
* **D7 — Release zip contents are unchanged:** same paths, the ROM and `os.bdd` now come from the build.
  The release tests check: the built files are in the zip with the working-tree bytes; every other entry is
  tracked at HEAD and not ignored; a missing built file is refused with the build command.
* **D8 — Design decision G12 is rewritten** to "only sources are committed; the ROM and discs are built
  before tests and zipped from the build", with the CI guard updated. G3 (already "superseded in part")
  gets a pointer that #92 supersedes the rest. The e2e decision that names the frozen `smoke.bdd` is updated
  to `os.bdd`.
* **Assumption A1 (deviates from AC 5, evidence only):** `release.yml`'s `workflow_dispatch` dry run is
  only available on the default branch (`master`), so it can't be run for this PR. AC5 is verified by
  running the workflow's steps locally (build, clean status, `make_release.py bc64`, unzip, boot the zipped
  ROM + `os.bdd` headless and run `hellowrd`). The workflow file itself is checked by `actionlint` (Docker
  image). No Open Question: the AC's behaviour is still checked, only the evidence path differs.
* **Assumption A2:** the build needs `bash` on `PATH` (Linux, macOS, Git Bash on Windows — the documented
  environments). The runner reports a clear FAIL if `bash` can't be started.

### 3.1 Decision Lock (Constants & Policies)

| Constant / Policy | Selected Value | Why | Where it lives |
| :--- | :--- | :--- | :--- |
| Build command | `./buildos && ./buildtools && ./buildapps && ./makedisc` in `src/` | the documented pipeline (`PIPELINE` already holds it with `cd src && `) | `run_tests.py`, `src/run`, `make_release.py`, docs |
| Skip flag | `--no-build` | AC2 | `run_tests.py` |
| Built files in the bc64 zip | `src/os.bdd`, `src/bc81asmc/bcOS/bcos_v1_2_0.b81` | issue step 7 | `make_release.py` |
| Tracked binaries | only `src/bdos/testb.sectors` | AC1, D1 | `.gitignore` |

### 3.2 Open Questions

No open questions.

---

## 4. Task Breakdown

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| `T1` | `run_tests.py` builds before e2e, `--no-build` | — | `Medium` |
| `T2` | e2e tests boot only the freshly built `os.bdd`; real-ROM tests move to e2e | — | `Medium` |
| `T3` | `make_release.py bc64` zips the built ROM and `os.bdd` | — | `Medium` |
| `T4` | `src/run` prints the build command when outputs are missing | — | `Low` |
| `T5` | Untrack the binaries, `.gitignore`, CI workflows | `T1`, `T2`, `T3` | `Medium` |
| `T6` | Docs describe the build-before-test rule | `T1`, `T2`, `T3`, `T4`, `T5` | `Medium` |

### T1 — `run_tests.py` builds before e2e, `--no-build`

* **Goal**: `python3 run_tests.py` and `--group e2e` build the ROM and discs from source before the e2e
  suite; `--no-build` skips it; `--group unit` never builds.
* **Depends on**: —
* **Complexity**: `Medium`
* **Pointers**: `run_tests.py` (`main`, `missing_disc_source`, `PIPELINE`, module docstring);
  `src/tests/test_run_tests.py`.
* **Definition of Done**: behaviour of §2.4 "Runner build rule"; usage text and docstring describe the build
  and `--no-build`; the build is injectable into `main()`; standard library only, Python ≥ 3.10.
* **Tests expected**: unit tests in `src/tests/test_run_tests.py` with a stub build: builds once before the
  suites for `all` and `e2e`; never for `unit`; never with `--no-build`; build failure → e2e FAIL (not run),
  other suites still run, exit 1; `--no-build` with a missing ROM / `os.bdd` / manifest source → e2e FAIL
  with the path and the build command. No test runs the real pipeline.
* **Tests to modify**:
  * `src/tests/test_run_tests.py :: DiscSourceHintTests.run_main` (helper) and
    `test_e2e_fails_with_hint_and_does_not_run`, `test_e2e_runs_when_sources_present` — they call `main([])`
    on an `e2e` suite, which now builds; they must pass `--no-build` (or a stub build) to keep testing the
    missing-source path (AC2, D2). Their assertions stay.

### T2 — e2e tests boot only the freshly built `os.bdd`; real-ROM tests move to e2e

* **Goal**: no test reads `smoke.bdd`; every e2e scenario boots a temp copy of the built `src/os.bdd`; the
  unit group needs no built output.
* **Depends on**: — (uses the build already present in the working tree)
* **Complexity**: `Medium`
* **Pointers**: `src/tests/e2e_harness.py`; `src/tests/test_bc64_smoke.py`; `src/tests/test_e2e_bdos.py`,
  `test_e2e_texted.py`, `test_e2e_texted_commands.py`, `test_e2e_texted_flows.py`, `test_e2e_disc.py`,
  `test_e2e_theodore.py`, `test_e2e_harness.py`; `src/bc64/tests/test_bc64_cli.py`;
  `src/tests/test_bc64_toolchain.py`; new `src/tests/test_e2e_rom.py`; delete `src/bc64/testdata/smoke.bdd`
  from disk (T5 untracks it).
* **Definition of Done**: `rg -n "SMOKE_DISK|smoke\.bdd" src/tests src/bc64/tests` finds nothing (except
  wording that says the frozen disc is gone, if any); the smoke transcript test boots `os.bdd` and its
  regenerate hint copies `os.bdd`; docstrings no longer say "frozen smoke.bdd"; the two real-ROM tests live
  in `src/tests/test_e2e_rom.py` with the same assertions and are gone from the unit modules;
  `python3 run_tests.py --group unit` passes with the ROM and `os.bdd` deleted from the working tree;
  `python3 run_tests.py` (after a build) passes with `smoke.bdd` deleted; committed transcript and goldens
  unchanged.
* **Tests expected**: existing e2e tests keep passing on the built disc; `select_src_modules` picks up
  `test_e2e_rom` as e2e (an assertion may be added to `test_run_tests.py` as a new test).
* **Tests to modify**:
  * `src/tests/e2e_harness.py` — remove `SMOKE_DISK` and its docs (D3, AC2 "boot only freshly built images").
  * `src/tests/test_bc64_smoke.py` — `SMOKE_DISK` constant, module docstring, `REGENERATE` text,
    `test_frozen_disc_session_matches_transcript` boots `OS_DISK` (may be renamed to say so) (AC2, issue step 3).
  * `src/tests/test_e2e_bdos.py`, `src/tests/test_e2e_texted.py`, `src/tests/test_e2e_texted_commands.py`,
    `src/tests/test_e2e_texted_flows.py`, `src/tests/test_e2e_harness.py` — `h.SMOKE_DISK` → `h.OS_DISK` and
    docstrings (D3, AC2).
  * `src/tests/test_e2e_disc.py :: test_smoke_bdd_matches_manifest` (removed, duplicate of the `os.bdd`
    check), `test_check_detects_a_corrupt_source_byte` and `DiscSessionTests.run_scenario` (→ `OS_DISK`),
    module docstring (D3).
  * `src/tests/test_e2e_theodore.py :: test_catalog_entry_and_ls` (drop the `SMOKE_DISK` iteration),
    `test_ls_lists_theodore` and the module's `run` helper (→ `OS_DISK`) (D3).
  * `src/bc64/tests/test_bc64_cli.py :: test_no_floppy_boots_the_real_rom_to_the_prompt` — moved to
    `src/tests/test_e2e_rom.py` (D5, AC1/AC2).
  * `src/tests/test_bc64_toolchain.py :: test_bc64_headless_run_matches_the_script` (and the then-unused
    `ROM` constant) — moved to `src/tests/test_e2e_rom.py` (D5).

### T3 — `make_release.py bc64` zips the built ROM and `os.bdd`

* **Goal**: once the ROM and `os.bdd` are untracked, `make_release.py bc64` still produces a zip with a
  working ROM and `os.bdd`, taken from the build in the working tree.
* **Depends on**: —
* **Complexity**: `Medium`
* **Pointers**: `scripts/make_release.py` (`make_bc64`, `bc64_files`, module docstring and usage);
  `scripts/tests/test_make_release.py :: Bc64ZipTests`.
* **Definition of Done**: §2.4 "Release zip" and D7; works whether or not the two files are still tracked
  (a built file replaces, never duplicates, a tracked entry of the same path); the error for a missing file
  names it and the build command; docstring updated.
* **Tests expected**: release-suite unit tests that run **without a real build** (stand-in files in a temp
  working-tree folder): the zip holds both built files with the stand-in bytes and mode 0644; all other
  entries are tracked at HEAD and not ignored; a missing built file raises `ReleaseError` mentioning the
  build command.
* **Tests to modify**:
  * `scripts/tests/test_make_release.py :: Bc64ZipTests.build` — supply the stand-in built files (D7).
  * `scripts/tests/test_make_release.py :: Bc64ZipTests.test_no_ignored_file`,
    `test_only_files_tracked_at_head`, `test_content_is_the_committed_blob` — the ROM and `os.bdd` are
    ignored, untracked build outputs now; these tests exempt exactly those two paths and check them against
    the built files instead (AC1, AC5, D7).

### T4 — `src/run` prints the build command when outputs are missing

* **Goal**: on a fresh clone, `cd src && ./run` prints the build command instead of a Python traceback; after
  the build it boots as today.
* **Depends on**: —
* **Complexity**: `Low`
* **Pointers**: `src/run` (LF, 100755 — keep both; see `.gitattributes`).
* **Definition of Done**: §2.4 "`src/run`"; exit 1 and nothing started when the ROM or `os.bdd` is missing;
  unchanged behaviour otherwise.
* **Tests expected**: a new unit test module (e.g. `src/tests/test_run_script.py`, emulator suite, **not**
  named `test_e2e_*`) that copies `run` into a temp folder without the outputs and checks the message, the
  build command and exit code 1, using stand-in files where needed. It needs no real build.
* **Tests to modify**: None

### T5 — Untrack the binaries, `.gitignore`, CI workflows

* **Goal**: AC1 and AC3 — only `src/bdos/testb.sectors` is tracked among the binary patterns, and CI builds,
  never restores, and tests on the fresh build.
* **Depends on**: `T1`, `T2`, `T3`
* **Complexity**: `Medium`
* **Pointers**: `.gitignore`; `git rm --cached` of `src/os.bdd` and `src/bc81asmc/bcOS/bcos_v1_2_0.b81`
  (keep the built files on disk), `git rm` of `src/bc64/testdata/smoke.bdd`;
  `.github/workflows/tests.yml` (e2e job), `.github/workflows/release.yml`.
* **Definition of Done**:
  * `.gitignore` keeps only the `testb.sectors` negation among the binary rules (D1);
    `git ls-files '*.b81' '*.bdd' '*.btap' '*.sector' '*.sectors'` prints only `src/bdos/testb.sectors`;
    `git ls-files -i -c --exclude-standard` prints nothing.
  * `tests.yml` e2e job: install, then `python run_tests.py --group e2e` (builds), then a guard step that
    fails when `git status --porcelain` is not empty (message as today's: an output is not ignored). The
    restore step, the smoke-disc/transcript refresh step and the `git diff --exit-code src/bc64/testdata/`
    step are gone. The golden-regeneration and artifact upload on failure stay. The unit job is unchanged.
  * `release.yml`: restore line removed; build + clean-status check kept; tests run with `--no-build` (D6).
  * Both workflow files pass `actionlint` (`docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint`).
* **Tests expected**: none new (workflow files); full local verification of §5.
* **Tests to modify**: None

### T6 — Docs describe the build-before-test rule

* **Goal**: AC6 — every doc listed in issue step 6 describes: only sources are committed; build before
  running or testing; `run_tests.py` builds (and `--no-build`); e2e tests boot the fresh `os.bdd`; people who
  only want to run the machine use the Release zip.
* **Depends on**: `T1`, `T2`, `T3`, `T4`, `T5`
* **Complexity**: `Medium`
* **Pointers**: `README.md` (Getting started: build first, Release zip for running only); `CLAUDE.md` (build
  pipeline rules, "fresh clone", tests section, smoke paragraph, CI section, "commit a refreshed smoke.bdd");
  `src/bc64/CLAUDE.md` (end-to-end sections: refresh procedure goes, transcript regeneration from a fresh
  `os.bdd` stays); `src/bdos/CLAUDE.md` (committed outputs line); `docs/01-emulator.md` (e2e section,
  "frozen smoke.bdd"); `docs/04-bcos.md` (ROM "the only ROM committed"); `docs/05-bdos.md` (fresh clone,
  smoke disc mentions; the pre-#37 caveat can stay as history but must not imply `smoke.bdd` exists);
  `docs/specs/memory/design-decisions.md` (G12, G3 pointer, the e2e decision naming `smoke.bdd`) (D8).
* **Definition of Done**: `rg -n "smoke\.bdd" README.md CLAUDE.md src docs --glob '!docs/specs/plans/**'
  --glob '!docs/CHANGELOG.md'` finds only historical mentions that say it is gone; no doc says the ROM or
  `os.bdd` is committed or that a fresh clone runs without a build; commands shown in docs are correct.
* **Tests expected**: none (docs).
* **Tests to modify**: None

---

## 5. Verification

* **Unit, no build present**: delete (or move aside) `src/os.bdd` and the ROM, then
  `python3 run_tests.py --group unit < /dev/null` → all unit suites pass (no build runs).
* **Full run**: `python3 run_tests.py < /dev/null` → builds first, every suite passes; transcript and goldens
  unchanged (`git status` clean apart from the intended changes).
* **`--no-build`**: with an output missing, `python3 run_tests.py --group e2e --no-build` → e2e FAIL with the
  build command, exit 1.
* **AC1**: `git ls-files '*.b81' '*.bdd' '*.btap' '*.sector' '*.sectors'` → only `src/bdos/testb.sectors`;
  `git ls-files -i -c --exclude-standard` → empty.
* **AC4**: in a fresh clone of the branch (`git clone` of the worktree into a temp dir), `cd src && ./run`
  prints the build command and exits 1; after the pipeline, `printf 'os.bdd\nls\nhellowrd\nexit\n' | ./run`
  boots and prints `Hello world!`.
* **AC5** (A1): in that clone, run release.yml's steps: build, `git status --porcelain` empty,
  `python3 run_tests.py --no-build`, `python3 scripts/make_release.py bc64 --tag bc64-dryrun --out dist`;
  unzip, `cd bc64-dryrun/src` and boot the zipped ROM + `os.bdd` headless (`hellowrd` prints `Hello world!`).
* **AC3**: `actionlint` passes on both workflows; the PR's `tests` run (unit 3.10/3.14, e2e) is green.
* **Python 3.10**: the unit group under `docker run --rm -v "$PWD":/w -w /w python:3.10-slim` (copy inside the
  container, `pip install parsy`).

---

## 6. Fact-Integrity Checklist

| Check | Yes / No / N/A | Notes |
| :--- | :--- | :--- |
| External contracts verified from producer/contract source | N/A | Internal |
| Evidence sources are reproducible | N/A | Internal |
| Identifier directionality / ordering / freshness meaning evidenced | N/A | Internal |
| Every `Assumption` is linked to an Open Question (§3.2) | Yes | A1/A2 need no stakeholder answer: A1 changes only the evidence path for AC5 (flagged as a deviation), A2 is the documented environment |
| No unresolved Open Questions (for `FINAL`) | Yes | |
| Each Decision states a single committed approach | Yes | |
| Tasks are independent, each with a Definition of Done and test expectations | Yes | T5 waits for T1–T3 so nothing breaks when the binaries are untracked |
| Required infra reflected | N/A | no toggles, no Service Bus |

**Self-review note**: The plan rests on the measured fact that a fresh build reproduces the committed ROM and
`os.bdd` byte for byte and that `smoke.bdd` equals `os.bdd`, so switching tests to the fresh disc should not
change any golden; if an implementer sees a golden diff, that is a real defect, not a reason to regenerate.
Take care with T1's test isolation (never run the real pipeline from `test_run_tests.py`), with T2's
"Tests to modify" bounds (rename the disc constant and move the two ROM tests; do not weaken assertions), and
with keeping `src/run`'s LF/100755 attributes. The `workflow_dispatch` dry run of AC5 can't run on this
branch; it is verified locally (A1, a flagged deviation in evidence only).

---

## 7. Amendment Log

| Revision | Request | Decision | Plan changes |
| :--- | :--- | :--- | :--- |
