# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

BC64 is a made-up 8-bit computer that exists only as software, written in Python. The repo
holds its whole stack, and each component has its own `CLAUDE.md` with its specific rules:

| Component | Path | Reference doc |
|---|---|---|
| emulator: bc8183 CPU + devices | `src/bc64.py`, `src/bc64/` (tests: `src/bc64/test_*.py`) | `docs/01-emulator.md` |
| assembler `bc81asmc` | `src/bc81asmc/` | `docs/02-assembler.md` |
| compiler `bc` (C-like B language) | `src/bc/` | `docs/03-compiler.md` |
| bcOS ROM monitor | `src/bc81asmc/bcOS/` | `docs/04-bcos.md` |
| bdos disk OS, utilities, apps, B libraries | `src/bdos/` | `docs/05-bdos.md` |

`docs/0X-*.md` are the detailed reference. Read the relevant page before changing a
component, and update it in the same change when behaviour changes.

**Standing design decisions** (the ABI, memory map, register convention, error codes, and
per-component conventions) are recorded in `docs/specs/memory/design-decisions.md`. Follow
them, and record a new decision there when you make one. `docs/specs/plans/` (spec plans)
and `docs/CHANGELOG.md` belong to the `/grind` workflow.

Active development is on the `bc64`
branch. `release/bc16_v1.0` and `release/bc32_v1.0` are frozen snapshots of earlier machine
generations; don't modify them. The top-level `bc/grammar.txt` is an old copy of the
compiler's grammar notes.

## Build pipeline and global conventions

```
.b ──bc──► .basm ──bc81asmc──► .btap ──ftool btap2bin──► .b81 (ROM) / .sector(s) ──ftool mkdisc──► src/os.bdd
```

- **Generated files are committed:** `.genb`, `.basm`, `.btap`, `.sector(s)`, `.b81` and
  `os.bdd`. After changing a source file, rebuild it and commit the outputs together with
  the source. Keep unrelated rebuild churn in a separate commit.
- **Shell scripts:** all of them live in `src/` and must be run from there (`bcc`,
  `buildos`, `buildtools`, `buildapps`, `makedisc`, `run`, `run_tests`, `ftool`; `run_tests` only wraps the root `run_tests.py`). The ones that call
  Python (`bcc`, `buildos`, `ftool`, `run`) pick the interpreter themselves: `winpty python` when
  `winpty` is on `PATH` (Git Bash), otherwise `python3`, otherwise `python`. They are
  executable and pinned to LF endings via `.gitattributes`.
- **Python imports are flat** (`from bc64 import …`, `from bc_ast import *`), so the
  working directory matters. See the commands below.
- The only dependency is `parsy`, used by the assembler and the compiler and by the tests that
  cover them. The root `pyproject.toml` (Python >= 3.10) declares it; `pip install -e .` (in a
  venv, from the repo root) installs it and the console commands `bc64`, `bc81asmc`, `bcc` and
  `ftool` (launchers in `src/bc64_toolchain.py`, editable install only). The commands work from
  any directory and take the scripts' arguments; `bcc path/name` takes the path without `.b` and
  compiles + assembles like `./bcc`. The `python3 path/script.py` forms below stay valid.
- Many sources use **CRLF** line endings (e.g. `bcos.basm`). Keep them when editing.
- Headless runs: `--disk-a`/`--disk-b` answer the disk prompts, piped stdin (or `--input FILE`)
  is typed as keys, `--output FILE` captures the printer output, `--max-instructions N` bounds
  the run and `--tape-dir DIR` sets the tape folder. `--random-seed N` makes the port 0x05 random numbers reproducible. `--no-floppy` starts bcOS with no floppy drive,
  straight to the monitor; it can't be combined with `--disk-a`/`--disk-b`. Options and exit codes are in
  `docs/01-emulator.md`. A trace run writes `cpudebug.log` to the working directory; it grows
  to gigabytes, so delete it afterwards.

```bash
cd src
./buildos && ./buildtools && ./buildapps && ./makedisc   # full rebuild of ROM, bdos, utilities, apps, os.bdd
python3 bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81            # run; enter "os.bdd" for disk A ("d" as 2nd arg = CPU trace)
printf 'ls\nhellowrd\nexit\n' | python3 bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81 --disk-a os.bdd --output out.txt   # headless; use a copy of os.bdd
```

Tests, from the repo root:

```bash
pip install -e .                                         # parsy, needed by the assembler and compiler tests, plus the console commands
python3 run_tests.py < /dev/null                         # all suites: emulator, ftool, assembler, compiler, e2e (exit 0 = pass)
python3 run_tests.py --group unit < /dev/null            # unit suites only: emulator, ftool, assembler, compiler
python3 run_tests.py --group e2e < /dev/null             # e2e suite only

cd src && python3 -m unittest discover -s . -t . -p "test_*.py"   # one suite: emulator (+ ftool, + e2e)
cd src/bc81asmc && python3 -m unittest discover -s . -t . -p "*_tests.py"   # one suite: assembler
cd src/bc && python3 -m unittest discover -s . -t . -p "*_tests.py"         # one suite: compiler
cd src && python3 -m unittest bc64.test_cpu.CpuTests.test_CLC16_opcodes    # one test (same form elsewhere)
```

Each suite uses flat imports, so run it from its own directory, as above.
`python3 run_tests.py` runs the e2e suite by default (`src/test_e2e_*.py` and `src/test_bc64_smoke.py`, see
`docs/01-emulator.md`), and `python3 run_tests.py --group e2e` runs only that suite. It is the check, also for `/grind`. After an intended change in bcOS or bdos output, regenerate the goldens with
`cd src && BC64_UPDATE_GOLDEN=1 python3 -m unittest test_e2e_bdos` (or another e2e module), then review them
by eye before committing.

The e2e suite's smoke test, `src/test_bc64_smoke.py`, boots a frozen disc
(`src/bc64/testdata/smoke.bdd`) and compares the session byte for byte with a committed transcript,
and it boots the current `src/os.bdd` and checks only output that survives a rebuild. For a
meaningful e2e run after rebuilding `os.bdd`, refresh `smoke.bdd` and its transcript first (see
`src/bc64/CLAUDE.md`).

There is no linter. `python3 run_tests.py` is the local check; CI runs it on GitHub (see CI below).

## CI

The `tests` workflow (`.github/workflows/tests.yml`) runs on every push and PR to `bc64`:
- both jobs install with `pip install -e .`; job `unit` also runs the four console commands from outside the checkout;
- job `unit` then runs `python run_tests.py --group unit` on Python 3.10 and 3.14;
- job `e2e` (Python 3.14, after `unit`) refreshes `smoke.bdd` from `os.bdd` and regenerates the smoke
  transcript, fails on any diff in `src/bc64/testdata/`, then runs `python run_tests.py --group e2e`.
  On failure it uploads the `e2e-golden-diff` artifact (regenerated goldens and their patch).

CI must be green before merge. For `/grind`, a PR is finished only when its `tests` checks pass; the PR
monitor watches those check runs. The e2e job fails on an unreviewed disc change, so commit a refreshed
`smoke.bdd` and its transcript with every `os.bdd` rebuild. Making `tests` a required status check on
`bc64` is a repo-owner setting.

## Cross-component contracts

The components are separate programs, but they share hard-coded numbers. Change one side
without the other and the system breaks silently.

- **Opcodes:** duplicated in `src/bc64/bc8183_cpu.py` (CPU) and
  `src/bc81asmc/bc81asmc_ast.py` (assembler). `src/bc81asmc/bc81asmc_opcode_agreement_tests.py` checks
  that the two agree.
- **bcOS system calls:** called via `F` = function number, then `cal :os_metacall`
  (`0x0008`). The `os_metatab` indices are an ABI used by the compiler runtime, bdos and
  apps.
- **The bdio hook:** bdos writes `bdio_call` into bcOS table slot `0x37` (`0x007a`) at
  start-up.
- **Memory map:**
  - bcOS: `0x0000–0x0d6b`
  - bdio variables: from `0x0d80`
  - shell command line: `0x0dd2`
  - boot sector: `0x0e00`
  - bdos: `0x0f00`
  - file buffers: `0x5d00`
  - user programs: `0x6000`
  - CPU stack: grows down from `0xfffe`
  - `0xffff`: `KIL` (reserved, written by the emulator at start-up)

  These values are spread over `boot.basm`, `bdioh.b`, `bdos.b`, and the `#code`/`#heap`
  line of every program. The map is asserted at build time: `boot.basm` and the compiler (image end
  below `#heap`, `bdos.b` via `#codelimit`); bcOS follows in #30.
- **Disk layout:** the boot loader range and the catalog location are requirements stated in
  `src/disc.bddmanifest`, and `ftool mkdisc` checks them. A file over its `max=` also fails the build.

Commit messages follow the existing style: `feat: …`, `fix: …`, `chore: …`, `docs: …`.
