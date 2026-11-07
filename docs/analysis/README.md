# BC64: state, roadmap and direction (analysis, 2026-11-07)

This is an analysis of every component of the `bc64` branch: where each one stands, where
the roadmap takes it, what is wrong, and what to do next. It is based on reading the code,
running the test suites, compiling and assembling the programs, and benchmarking the
emulator. The measurements below were taken on 2026-11-07.

| Component | Analysis |
|---|---|
| Emulator: bc8183 CPU + devices | [01-emulator.md](01-emulator.md) |
| Assembler `bc81asmc` | [02-assembler.md](02-assembler.md) |
| Compiler `bc` (B language) | [03-compiler.md](03-compiler.md) |
| bcOS ROM monitor | [04-bcos.md](04-bcos.md) |
| bdos, utilities, apps | [05-bdos.md](05-bdos.md) |
| Toolchain, build, tests, repository | [06-toolchain.md](06-toolchain.md) |

Each file has the same sections: current state, development direction, problems,
proposals, and a modernisation verdict.

## Roadmap status (BC64, from the README)

| # | Roadmap item | Status |
|---|---|---|
| 0 | memory increased to 64 KB | **done** |
| 1 | CPU 16-bit arithmetic/binary ops, long relative jumps | **done** (bc8183). The "improved CPU stack frames" part is not done |
| 2 | matching changes in the assembler | **done** (v1.3) |
| 2 | matching changes and optimisations in the compiler | **done** (v1.3.1: native 16-bit ops, `jrx`/`clr`) |
| 2 | bcOS 1.2 | **done** |
| 3 | bdos 1.1 (buffered reads/writes) | **done** in code, but the system disc is **stale** (#1) |
| 4 | texted and game new versions | **in progress**: texted almost done (#1), game not started (#2) |
| 5 | compiler: drop unused code, manage stacks inside subroutines | not started |
| 6 | bdos 1.1b: catalog with dates and load addresses | not started |
| 7 | new discs, 80 tracks × 32 sectors | not started. **Blocked by design**: track/sector packing assumes ≤ 16 sectors (see bdos) |
| 8 | assembler running on the BC64 | not started; far off |
| 9 | compiler running on the BC64 | not started; far off |
| 10 | networking? | idea only |

Development stopped on 2025-01-04, in the middle of item 4.

## Key numbers

| Metric | Value | Why it matters |
|---|---|---|
| Emulator speed | about 130k instructions/s; about 200k (1.6×) without the debug strings it builds and throws away on every instruction | a full disc boot and an app session take seconds; an automated test run will be slow |
| bcOS headroom | **21 bytes** (image ends at `0x0d6b`, bdio variables start at `0x0d80`) | almost any bcOS change forces the memory map to move |
| bdos kernel | 18,466 bytes (`0x0f00–0x5722`); 1.5 KB left before the file buffers | bdos growth soon collides with fixed buffers |
| User memory | 40,958 bytes (`0x6000–0xfffe`) | fine today; the limit for self-hosting (items 8–9) |
| "Hello world" | **1,665 bytes** | every program carries the whole runtime and every included library; item 5 is the fix |
| B source | about 5,100 lines in `src/bdos/` | bdos and its apps are the compiler's biggest test case |
| Tests | emulator 22/23; assembler 75/75; compiler 15/21 (with a stand-in for the missing `msilib` module; on Linux without it, 0 run) | there are no code-generation or end-to-end tests at all |
| Committed build outputs | 61 of 207 tracked files | nothing checks they are current; `BDOS.SYS` and `CAT.PRG` were found stale |

## Problems that cut across components

1. **Nothing checks the build.** Build outputs are committed (design decision G3), but no
   script or CI verifies that they match the sources. That's how the current disc ended up
   with stale `BDOS.SYS` and `CAT.PRG`.
2. **Contracts are kept only by discipline.** The bcOS table, memory map, opcodes and disc
   layout are now documented (`docs/specs/memory/design-decisions.md`), but none of them is
   enforced by a tool. The 21-byte bcOS headroom and the duplicated opcode tables are the
   riskiest.
3. **The toolchain only works as-is on Windows.** It relies on `winpty` scripts, the
   Windows-only `msilib` import, a Python 3.7 Pipfile and mixed CRLF/LF line endings. A fresh
   Linux or macOS checkout can't build or test without workarounds.
4. **There is no automated run of the real system.** The emulator asks for disk names and
   keyboard input interactively, so boot → shell → app can only be tested by hand.
5. **Generated code is large**: no dead-code elimination, and every variable access is a
   subroutine call. This limits bdos growth, app size and the self-hosting goals.

## Does anything need modernisation?

**The tooling does; the machine doesn't.** The BC64 is deliberately an 8-bit design: no
interrupts, fixed memory map, sign-magnitude offsets, tape and floppy. Those constraints are
the point of the project and should only change through the roadmap.

The host side, on the other hand, is behind current practice and that slows every change:

| Area | Verdict | Main reason |
|---|---|---|
| Build scripts (bash + `winpty`) | **modernise** | they aren't cross-platform, have no dependency tracking, and need a manual build order |
| Python packaging (Pipfile with Python 3.7, no `pyproject.toml`) | **modernise** | Python 3.7 has been end-of-life since 2023; `msilib` breaks on 3.13+ |
| CI | **add** | none today; needed to keep committed build outputs honest |
| Tests | **extend** | compiler tests are stale; there are no golden-output or end-to-end tests |
| Line endings | **normalise** | add a `.gitattributes`, and mark `.btap`/`.bdd`/`.b81` as binary |
| Emulator code | **modernise lightly** | performance and a headless mode; the structure is sound |
| Assembler and compiler code | **keep, improve incrementally** | the parsy-based design is fine; add diagnostics and tests |
| bcOS / bdos code | **no modernisation, evolve via the roadmap** | it is meant to be period-style code |

## Recommended order of work

1. **#1 Complete TextEd v1.2**, including the `msilib` fix: unblocks a clean baseline.
2. **Toolchain baseline:**
   - a cross-platform build script (`build.py` or a Makefile);
   - `pyproject.toml`;
   - `.gitattributes`;
   - CI that runs all tests, rebuilds everything, and fails if committed outputs differ.
3. **Emulator headless mode** (disk/tape names from the command line, scripted keyboard
   input) and an end-to-end smoke test in CI: boot `os.bdd`, then run `ls`, `cat` and
   texted.
4. **#2 Port the Theodore game.**
5. **Compiler roadmap item 5**: dead-code elimination, then cheaper variable access. This
   frees memory for everything that follows.
6. **Assembler `.assert` and listing/map output**, to enforce the memory-map and ABI
   contracts at build time.
7. **bdos 1.1b / 2.0**: catalog v2 (dates, load address, 2-byte length), designed together
   with the disc geometry of roadmap item 7, and a disc built from a manifest instead of a
   hand-made catalog.
8. **Self-hosting (items 8–9)**, only after items 5–7. It needs smaller code and a richer
   file API.

Each of steps 2, 3, 5, 6 and 7 is a good candidate for its own GitHub issue in the format
of #1/#2.
