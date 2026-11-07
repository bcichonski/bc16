# Toolchain, build, tests and repository: analysis

Decisions: G3, G9, G10 in
[../specs/memory/design-decisions.md](../specs/memory/design-decisions.md). Commands are in
the root `CLAUDE.md`.

## Current state

- **Build:**
  - 8 bash scripts in `src/` (`bcc`, `buildos`, `buildtools`, `buildapps`, `makedisc`,
    `run`, `run_tests`, `rundebug`), most calling `winpty python` (Git Bash on Windows);
  - `ftool.py` for tape → binary and disc sector work.
- **Build outputs are committed:** 61 of 207 tracked files (`.genb`, `.basm`, `.btap`,
  `.sector(s)`, `.b81`, `.bdd`).
- **Dependencies:** `parsy` only. It's declared in `src/bc81asmc/Pipfile` with Python 3.7;
  there's no `pyproject.toml`.
- **Tests:** three separate `unittest` suites, each run from a different directory.
  Results: emulator 22/23, assembler 75/75, compiler 15/21 (0 on Linux without a stand-in
  for `msilib`). There are no code-generation or end-to-end tests.
- **No CI.** `.github/` doesn't exist apart from what `/grind` will use.
- **Docs:** `docs/` (reference, analysis, design decisions, the `/grind` workflow) and
  hierarchical CLAUDE.md files, all added in this session.

## Development direction

- The project grows by machine generations (G9); tooling has to keep up with each new CPU,
  OS and disc format.
- The `/grind` workflow (spec plans, labels, changelog) is now set up, so stories will be
  implemented by agents. That needs reliable, scripted build and test commands even more
  than human work does.

## Problems

| # | Problem | Evidence | Impact |
|---|---|---|---|
| 1 | Not cross-platform | `winpty` in scripts; `msilib` import; `getch` via `msvcrt` with a POSIX fallback | Linux and macOS users (and CI, and agents) need workarounds |
| 2 | No dependency-aware build | scripts rebuild fixed lists; the order (`buildos` → `buildtools` → `buildapps` → `makedisc`) is manual | forgotten steps → stale outputs (that's how the disc went stale) |
| 3 | Nothing checks committed outputs | no CI; no `git diff --exit-code` after a rebuild | stale `BDOS.SYS`/`CAT.PRG` went unnoticed for months |
| 4 | Fragmented, partly broken tests | 3 suites, 3 working directories, 7 failing or erroring tests, no end-to-end test | no safety net for optimisations or ABI changes |
| 5 | Outdated packaging | Python 3.7 Pipfile (EOL June 2023), only for the assembler | unclear supported Python version; `msilib` was removed in Python 3.13 |
| 6 | Mixed line endings | CRLF in `bcos.basm`, the generated `.basm` files and others; LF elsewhere; no `.gitattributes` | noisy diffs, and the editor/tool mismatches seen in this session |
| 7 | Leftovers | tracked: the top-level `bc/grammar.txt` (an old copy), and `src/rundebug`, which references the old `bc16.py`. Untracked but ignored local clutter: `src/string.btap` (0 bytes), `src/texted.compile.log`, `src/history.log`, `src/bc64.dmp` | clutter, and a broken script |
| 8 | Release snapshots are full copies | `release/bc16_v1.0`, `release/bc32_v1.0` | fine for history (G9); git tags would be lighter |

## Proposals

### Next steps

1. **Cross-platform build script** (`build.py` at `src/`, standard library only), with
   targets:
   - `rom`
   - `bdos`
   - `tools`
   - `apps`
   - `disc`
   - `all`
   - `test`
   - `clean-logs`

   Rebuild by timestamp or content hash. Keep the bash scripts as thin wrappers for a
   while, then remove them.
2. **`pyproject.toml`**:
   - `requires-python >= 3.10`;
   - `parsy` pinned to a major version;
   - console entry points `bc64`, `bc81asmc`, `bcc`, `ftool`.

   Delete the Pipfile. Fix `msilib` (issue #1).
3. **GitHub Actions CI:**
   1. set up Python;
   2. install;
   3. run all three test suites;
   4. `build.py all`;
   5. `git diff --exit-code` (committed outputs must match the sources, G3);
   6. later, an end-to-end boot test with the emulator's headless mode (see
      [01-emulator.md](01-emulator.md)).

   Optionally publish per-program code sizes as a job summary, to track compiler
   optimisations.
4. **`.gitattributes`:**
   - `*.btap *.bdd *.b81 *.sector *.sectors binary`;
   - an explicit choice for text: either keep CRLF for `*.basm`/`*.b` with `eol=crlf`, or
     normalise to LF once in a single commit and then run a full rebuild to confirm the
     binaries are unchanged.

### Improvements

5. **One test entry point** (`python -m unittest discover` configured, or `pytest` with
   `testpaths`) covering all suites, plus **golden tests**:
   - compiler: `.b` → `.basm`;
   - assembler: `.basm` → `.btap`;
   - end to end: scripted shell sessions on `os.bdd` with expected terminal output.
6. **Housekeeping commit:**
   - delete `bc/grammar.txt`;
   - fix or delete `rundebug`;
   - add `trace.in` (written by `rundebug`) to `.gitignore` (`*.log` and `*.dmp` are
     already ignored).
7. **Release tags** (`bc16-v1.0`, `bc32-v1.0`, later `bc64-v1.0`) in addition to the
   `release/` folders. Consider replacing the folders with tags once nobody needs a
   side-by-side checkout.
8. **Agent friendliness for `/grind`:** the root CLAUDE.md should point to the single
   `build.py test` / `build.py all` command once it exists, so every story ends with the
   same verification.

## Modernisation verdict

**Yes: this is the part of the project that most needs modernising.** None of it changes the
BC64 itself, and all of it makes every future story cheaper and safer:
- a cross-platform build;
- current Python packaging;
- CI that enforces the committed-outputs rule;
- consistent tests;
- normalised line endings.

Recommended as the first story after #1.
