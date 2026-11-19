# Release bc64 v0.1: First BC64 Preview Release Plan

**Plan Status**: `FINAL`

**Story Type**: `Internal`

**Plan Revision**: `A0`

> This plan captures **what** to build and **why**. The implementation agent discovers the **how** against live code.

---

## 1. Problem Statement

*   **Context**: `bc16-v1.0` and `bc32-v1.0` are published (#90). The bc64 release pipeline is complete. A pushed `bc64-v*` tag makes `.github/workflows/release.yml` build, test, zip (`scripts/make_release.py bc64 --tag`, with the ROM, `src/os.bdd` and `src/utils.bdd` since #100) and create the GitHub Release. Its body is `make_release.py notes bc64`. Two things stand in the way of a first bc64 release:
    *   README → Releases says bc64 tags are "`bc64-v1.0` and later", but the BC64 is still in progress, so the first release is the preview `bc64-v0.1`.
    *   `notes bc64` prints the README `# BC64` section. Today that section holds only the roadmap, architectural notes, memory and the software list. It says nothing about how to run the zip, what works, or what's known to be broken.
*   **Goal**: the repo is ready for the owner to tag `bc64-v0.1`. The README describes bc64 tags from `v0.1`, `notes bc64` gives useful release notes, a test pins those notes, and the zip is checked to boot and run the apps.
*   **In scope**: issue scope 1, 2, 3 (as a local equivalent plus a `workflow_dispatch` dry run on the PR branch, see D5), and 5 (README table). Issue scope 4 (publishing) is the owner's step after merge (D4).
*   **Out of scope**: code changes to the release pipeline (the `bc64-v*` trigger and `TAG_RE` already accept `bc64-v0.1`, verified); fixing any listed known bug; legacy releases.

### 1.1 Technical Summary

*   **Touched areas**: `README.md` (Releases section, `# BC64` section), `CLAUDE.md` (one sentence on bc64 tags), `scripts/make_release.py` (docstring/`--help` example names only), `scripts/tests/test_make_release.py` (new tests).
*   **New patterns**: none. Release notes stay "the README section of that generation", the rule `make_release.py` and its tests already use (D1).
*   **Infrastructure changes**: none.
*   **End state**: `python3 scripts/make_release.py notes bc64` prints a `# BC64` section that opens with a release-notes part for `bc64-v0.1`: how to run from the zip with both discs, what ships on each disc, the toolchain, and known limitations linked to open issues. `python3 scripts/make_release.py bc64 --tag bc64-v0.1` produces a zip that boots in the default A/B setup.

---

## 2. Architecture & Design

### 2.1 Architecture Overview

```
README.md "# BC64" section ──► make_release.notes("bc64") ──► dist/notes.md ──► gh release create --notes-file
       ▲ (new "release notes" subsection first)          (release.yml, unchanged)
       │
scripts/tests/test_make_release.py: new test reads the working-tree README section and pins the required content
```

### 2.2 External Contracts & Evidence

N/A — Internal story.

### 2.3 Affected Areas

| Area | Today | After |
|---|---|---|
| README → Releases table | `bc64-v*` row: "`bc64-v1.0` and later" | bc64 releases start at `bc64-v0.1`, and pre-1.0 means in progress. A `bc64-v0.1` row says the BC64 preview, tagged by the owner on the merge commit (D3) |
| README → Releases text | example `--tag bc64-v1.0`; owner commands only for legacy | example `--tag bc64-v0.1`. Short owner steps for bc64: optional dry run (`gh workflow run release.yml -f name=bc64-v0.1`), then `git tag bc64-v0.1 <master commit>` + `git push origin bc64-v0.1` |
| README `# BC64` | roadmap first | a new first subsection, release notes for `bc64-v0.1` (§2.4), then the existing content unchanged |
| `CLAUDE.md` | "released as `bc64-v*`" | also says the first is the `bc64-v0.1` preview |
| `scripts/make_release.py` | docstring/`--help` example `bc64-v1.0` | `bc64-v0.1` (text only, no behaviour change) |
| `scripts/tests/test_make_release.py` | notes = README section (kept) | new tests pin the release-notes content (§2.4) and that `bc64-v0.1` is a valid zip name |

### 2.4 Release notes content (README `# BC64`, first subsection)

The facts below were verified against `src/disc.bddmanifest`, `src/utils.bddmanifest`, `src/run`, `pyproject.toml` and the open issues on 2026-11-19.

*   **What it is**: `bc64-v0.1` is the first, preview release of the BC64. Pre-1.0 means the machine, OS and toolchain are still changing.
*   **Running from the zip**: unpack, then `cd bc64-v0.1/src && ./run`. Python 3.10+ is needed. At `Disk A name:` enter `os.bdd`, and at `Disk B name:` enter `utils.bdd`. Type `b:` to switch to the apps disc. The text must contain `os.bdd`, `utils.bdd`, `Disk B name:` and `b:`.
*   **What's on the discs**: `os.bdd` (drive A) holds bcOS 1.2 boot + bdos (`BDOS.SYS`), the system utilities `ls`, `cp`, `rm`, `format`, `cha`, `cat`, plus `hellowrd` and the sample file `TEST.B`. `utils.bdd` (drive B, also bootable alone) holds `texted`, `calc`, `hellowrd`, `theodore`.
*   **Toolchain**: the B compiler (`bc`/`bcc`), the assembler (`bc81asmc`), `ftool` (disc images), and the build scripts. Building from source needs `pip install -e .` (parsy). Keep it short, and link `docs/README.md` for the reference docs.
*   **Known limitations**: a list that links each open bug a user of the zip can hit, with one line each. At least: #73 (`cp` reads keys until input runs out and never creates the copy), #82 (TextEd's missing-argument checks never fire). For people writing programs: CPU flag/ALU issues (#53–#58), compiler gaps (no `return` anywhere #20, undeclared-variable crash #68), assembler issues (#64–#67). Also one line saying files only grow on the disc (no free-space reuse, #41). The agent re-checks each listed issue is still open (`gh issue view`). It lists numbers only for issues that are open, and it doesn't invent bugs.
*   Heading wording is the agent's choice, but the test (T2) pins: the text `bc64-v0.1`, the four disc/prompt strings above, every program name on both discs, and a "known limitations" heading (case-insensitive) with at least `#73`.

---

## 3. Key Decisions & Assumptions

*   **D1 — notes source stays the README `# BC64` section.** Rejected alternatives: a separate notes file, or a prefix generated in code. Either would split the content from the user docs and break the existing `NotesTests.test_each_generation_uses_its_readme_section` equality (`notes(bc64) == README section`). Keeping it means no existing test changes, and the README itself documents the release.
*   **D2 — the content test reads the working-tree README**, through `make_release.readme_section`. `notes()` reads `HEAD:README.md`, so a test through `notes()` would fail until the README is committed. Equality with `notes()` is already proven by the existing HEAD-based test.
*   **D3 — the tagged commit in the table.** The commit to tag is the merge commit of this PR, which doesn't exist yet. The `bc64-v0.1` row says so ("the merge commit of #109, tagged by the owner"), and the owner can replace it with the hash after tagging. **Deviates from AC-1** ("the table gives the tagged commit"): the hash can't be written before the merge. Flag it in the PR.
*   **D4 — publishing is the owner's step.** Pushing a tag and creating a Release are outward, owner-only actions (CLAUDE.md: "Publishing a release … is the repo owner's step"). Uploading release assets also fails from the agent sandbox. **AC-5 (tag + Release exist) is not met by this PR.** The PR uses `Refs #109`, not `Closes`, so the issue stays open until the owner tags.
*   **D5 — dry run (AC-3, AC-4).** Locally: build, `make_release.py bc64 --tag bc64-v0.1`, unpack into a temp dir, boot `src/run`'s emulator command headless with `os.bdd`/`utils.bdd`, and run `b:` then `texted`, `calc`, `theodore`. Each must start (banner) and return to the prompt. On GitHub: after the PR branch is pushed, `gh workflow run release.yml --ref <branch> -f name=bc64-v0.1` (no Release is created, it only uploads an artifact), and check the run is green with all three built files in the `unzip -l` listing. The workflow runs from the branch ref, so it also tests the new notes. If dispatch is refused, record it and fall back to the local check. AC-3 then stays the owner's check.
*   **D6 — CHANGELOG.** Scope 5 asks to record the release in `docs/CHANGELOG.md`. That file's rule is one entry per completed story, made by the changelog generator from the merged PR. The #109 entry made after merge is that record, so no hand-written entry goes in this PR.
*   **D7 — `TAG_RE`/workflow unchanged.** Verified: `TAG_RE = ^[A-Za-z0-9][A-Za-z0-9._-]*$` accepts `bc64-v0.1`, and `release.yml` triggers on `bc64-v*`. T2 adds a test that `bc64-v0.1` is a valid zip name, to pin it.

### 3.1 Decision Lock

D1–D7 are locked for this revision.

### 3.2 Open Questions

None.

---

## 4. Task Breakdown

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| T1 | README/CLAUDE.md/docstring: bc64-v0.1 and the release notes | — | Medium |
| T2 | Tests pinning the bc64 release notes and the v0.1 name | T1 | Low |

### T1 — README/CLAUDE.md/docstring: bc64-v0.1 and the release notes

*   **Goal**: the README Releases section and `# BC64` section, `CLAUDE.md` and `make_release.py`'s help text match §2.3/§2.4.
*   **Depends on**: —
*   **Complexity**: `Medium`
*   **Pointers**: `README.md` (`# Releases`, `# BC64`), `CLAUDE.md` (the "Earlier machine generations…" paragraph), `scripts/make_release.py` (module docstring, `parse_args` help), `src/disc.bddmanifest`, `src/utils.bddmanifest`, `src/run`, `docs/05-bdos.md` (utility names), open issues via `GH_TOKEN="$GITHUB_PERSONAL_ACCESS_TOKEN" gh issue view N -R bcichonski/bc16`.
*   **Definition of Done**:
    *   §2.3 rows for README, CLAUDE.md and make_release.py are done. No `bc64-v1.0` example remains in README/CLAUDE.md/make_release.py, except where a sentence talks about 1.0 as a future version.
    *   The `# BC64` section starts with the §2.4 subsection. Everything after it in the section is unchanged. No top-level (`# `) heading is added outside code fences, because a stray `# ` would cut the section.
    *   Every issue number in "known limitations" is open at the time of writing.
    *   `make_release.py` behaviour is unchanged (text only).
*   **Tests expected**: none new here (T2). Existing `python3 run_tests.py --group unit` passes.
*   **Tests to modify**: None

### T2 — Tests pinning the bc64 release notes and the v0.1 name

*   **Goal**: the release-notes content and the `bc64-v0.1` zip name are pinned by tests, so a later README edit can't silently drop them.
*   **Depends on**: T1
*   **Complexity**: `Low`
*   **Pointers**: `scripts/tests/test_make_release.py` (`NotesTests`, `Bc64ZipTests`/the invalid-tag test for the existing pattern), `scripts/make_release.py` (`readme_section`, `TAG_RE`/`make_bc64` validation).
*   **Definition of Done / Tests expected** (new test methods only, in the existing file):
    *   The working-tree README's `BC64` section (D2) contains `bc64-v0.1`, `os.bdd`, `utils.bdd`, `Disk B name:`, `b:`, each program name of both manifests (`ls cp rm format cha cat hellowrd texted calc theodore`, case-insensitive), a "known limitations" heading (case-insensitive) and `#73`.
    *   The Releases section of the working-tree README names `bc64-v0.1`.
    *   `bc64-v0.1` passes the zip-name check (`TAG_RE`). It must not need a built ROM: test the regex/validation, not a full zip build.
    *   `python3 run_tests.py --group unit` passes.
*   **Tests to modify**: None

---

## 5. Verification

*   `python3 run_tests.py --group unit < /dev/null` (the release suite is in unit), and the full `python3 run_tests.py < /dev/null` (builds, then e2e).
*   `python3 scripts/make_release.py notes bc64` after the commit: it starts with `# BC64`, and the release-notes subsection comes first.
*   D5 local zip boot check, with the result recorded in the PR body.
*   CI `tests` green. Then the D5 `workflow_dispatch` dry run on the branch.

## 6. Fact-Integrity Checklist

| Check | Result |
|---|---|
| Every AC mapped to a task, a verification step or a flagged deviation | Yes: AC-1 T1 (+D3 deviation), AC-2 T1/T2, AC-3/AC-4 D5, AC-5 D4 (owner, deviation), AC-6 §5 |
| Facts verified against live code (manifests, TAG_RE, release.yml trigger, notes()) | Yes |
| No existing test's expectation changes | Yes (D1/D2) |
| Open questions | None |

Self-review: D3 and D4 are explicit AC deviations, and they must be listed in the PR body and the final report.

## 7. Amendment Log

| Rev | Request | Decision | Plan changes |
|---|---|---|---|
