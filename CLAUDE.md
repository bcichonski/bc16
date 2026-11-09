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
.b ──bc──► .basm ──bc81asmc──► .btap ──ftool btap2bin──► .b81 (ROM) / .sector(s) ──makedisc──► src/os.bdd
```

- **Generated files are committed:** `.genb`, `.basm`, `.btap`, `.sector(s)`, `.b81` and
  `os.bdd`. After changing a source file, rebuild it and commit the outputs together with
  the source. Keep unrelated rebuild churn in a separate commit.
- **Shell scripts:** all of them live in `src/` and must be run from there (`bcc`,
  `buildos`, `buildtools`, `buildapps`, `makedisc`, `run`, `run_tests`, `ftool`; `run_tests` only wraps the root `run_tests.py`). The others
  call `winpty python …` because they were written for Git Bash on Windows; on Linux, run the
  same commands with `python3`. `bcc` picks the interpreter itself: `winpty python` when
  `winpty` is on `PATH`, otherwise `python3`.
- **Python imports are flat** (`from bc64 import …`, `from bc_ast import *`), so the
  working directory matters. See the commands below.
- The only dependency is `parsy` (`pip install -r requirements.txt`), used by the assembler and
  the compiler and by the tests that cover them.
- Many sources use **CRLF** line endings (e.g. `bcos.basm`). Keep them when editing.
- Headless runs: `--disk-a`/`--disk-b` answer the disk prompts, piped stdin (or `--input FILE`)
  is typed as keys, `--output FILE` captures the printer output, `--max-instructions N` bounds
  the run and `--tape-dir DIR` sets the tape folder. Options and exit codes are in
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
pip install -r requirements.txt                          # parsy, needed by the assembler and compiler tests
python3 run_tests.py                                     # all suites: emulator, assembler, compiler (exit 0 = pass)

cd src && python3 -m unittest discover -s . -t . -p "test_*.py"   # one suite: emulator (+ ftool)
cd src/bc81asmc && python3 -m unittest discover -s . -t . -p "*_tests.py"   # one suite: assembler
cd src/bc && python3 -m unittest discover -s . -t . -p "*_tests.py"         # one suite: compiler
cd src && python3 -m unittest bc64.test_cpu.CpuTests.test_CLC16_opcodes    # one test (same form elsewhere)
```

Each suite uses flat imports, so run it from its own directory, as above.
The emulator suite also runs `src/test_bc64_smoke.py`. It boots a frozen disc
(`src/bc64/testdata/smoke.bdd`) and compares the session byte for byte with a committed transcript,
and it boots the current `src/os.bdd` and checks only output that survives a rebuild. Rebuilding
`os.bdd` doesn't require a new transcript.

There is no linter. Test status is not recorded in the docs; `python3 run_tests.py` is the check.

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

  These values are spread over `boot.basm`, `bdioh.b`, `bdos.b`, and the `#code`/`#heap`
  line of every program.
- **Disk layout:** the boot loader's sector range, the hand-made catalog
  `src/fcat0800.sector` and the fixed program tracks in `src/makedisc` must agree.

Commit messages follow the existing style: `feat: …`, `fix: …`, `chore: …`, `docs: …`.
