# Changelog

All notable changes to this project will be documented in this file.
Each entry corresponds to a completed story and is generated from the actual PR diff after
implementation — not from the spec plan.
Entries are ordered by merge date (newest first).

To add entries, run the `generate-changelog-entry` skill (or the `changelog-generator` agent).
It scans `docs/specs/plans/` for `FINAL` plans with no entry here yet, finds each one's merged
PR on GitHub, and drafts from the diff. The format for an entry is in
`docs/changelog-entry-template.md`.

---

## [47] TextEd: file saved before a restart loads but shows no text — 2026-11-09

Tags: `apps` `build` `tests`
PR: [#77](https://github.com/bcichonski/bc16/pull/77)
Builds on: #76, #49

### What was built
- `texted.b` `l <file>` now actually loads: `loadFile` opens the file in buffered mode (was sector mode) and `readLines` parses `<number> <text>` records as it reads 128-byte chunks, so a record can span chunks. It inserts each one with `insertLineBuf`. Before, it only printed the raw lines. Records with no valid number (over 65535 or not digits) or no text are skipped, and text longer than `MAXLINELENGTH` is truncated.
- `l` replaces the buffer: the existing lines are freed only after the file opens. A missing file prints the bdio error and keeps the buffer.
- New `fileArg` helper shared by `s` and `l`: it parses `<file>`, normalises the name and prints `saving|loading <file>...`. It also fixes `poke16(Pwend, NULLCHAR)`, which wrote a byte too far, to `poke8`.
- TextEd list fixes: `findPreviousLine` handles reaching the end of the list (`PcurrLine = NULL`), and `insertLineBuf` appends after the last line without reading through a NULL `PnextLine`. The input buffer and `readsn` are `MAXLINELENGTH + 1`, and the `h` help says `l` replaces the buffer.
- `cat.b` `-c`: `printchars` carries the line length across sectors (`printbuf` and `printfile` pass `linelen` through), and the newline after each sector is now only printed in hex mode. A record that crosses a sector boundary is shown on one line.
- Every disc program is rebuilt from source (`boot`, `cat`, `cha`, `cp`, `format`, `helloworld`, `ls`, `rm`, plus the first committed `texted.basm`/`.btap`/`.sectors`). `fcat0800.sector` and `os.bdd` are updated: `CAT.PRG` is 62 sectors and `TEXTED.PRG` 112.
- `TEST.B` is now `src/bdos/testb.sectors`, which `makedisc` imports at 52/0, so a full `makedisc` gives a bootable disc.
- New `src/test_e2e_texted.py` (5 scenarios): save → restart → load, a file over one sector with 80-character lines, a missing file keeping the buffer, load replacing a non-empty buffer, and `cat -c` showing saved records whole. Golden `texted_roundtrip.golden.txt`.
- `smoke.bdd`/`smoke_transcript.txt` refreshed. The `bdos_cat`/`bdos_ls`/`bdos_rm` goldens and `CATALOG_LINES` in `test_e2e_bdos.py` are updated for the new catalog.
- Docs: a "TextEd file format" section and the updated catalog table in `docs/05-bdos.md`; design decision D6.

### Key decisions reflected in the diff
- The on-disc text format stays as it was: records end in `0x13` (the `CHAR_LF` of `texted.b` and `cat.b`), with one `0x00` after the last record and zero padding after that. Switching to `0x0a` was rejected because it would break existing files and `cat -c`.
- The committed build outputs were stale and gave an unbootable disc, so the whole program set was rebuilt rather than only TextEd.
- The `CP.PRG` catalog entry was deliberately left at 56 sectors (the build is 57). Fixing it flips #49's `expectedFailure` cp test, so the catalog was not synced to the builds wholesale.

## [76] bdos: buffered file I/O (bdio_fbinbufread / bdio_fbinbufwrite) loses and misreads data — 2026-11-09

Tags: `bdos` `build` `tests`
PR: [#78](https://github.com/bcichonski/bc16/pull/78)
Builds on: #49, #50

### What was built
- `bdio.b` `bdio_fbinbufread` was rewritten as one loop. It refills the handle's sector buffer when it is used up, copies `min(left in buffer, length)` from the buffer offset, and returns the bytes copied (a `word`, was `byte`). That count is less than `length` only at end of file, and `0` at EOF. The debug `printf`s are gone.
- `bdio_fbinbufwrite` was rewritten to match. It fills the buffer in chunks of any length and writes a sector to disc as soon as the buffer is full. It returns the bytes accepted (`word`), and `bdio_fclose` flushes the rest.
- Both calls check the handle's direction bit, its descriptor number and buffered mode before doing anything, and return `0` for a handle that isn't valid buffered I/O.
- `bdio_fbinopen_internal` sets up a buffer only for a valid handle, and starts a read handle's buffer counter at 128 (used up). `bdio_getfdesc_addr` moved above it.
- Rebuilt `bdos.basm`/`.btap`/`.sector`. `os.bdd` and `smoke.bdd` carry the new `BDOS.SYS`.
- New e2e test `src/test_e2e_bdio_buffered.py` with `testdata/e2e/bdio_buffered_prog.b`. It writes a 589-byte pattern in mixed chunk sizes, reads it back in other chunk sizes, and checks the file on the disc image (data + 51 zero padding bytes). Golden `bdio_buffered_run.golden.txt`. The CI golden-regeneration step includes the new module.
- Docs: the `0x18`/`0x19` return values and a new "Buffered I/O" section in `docs/05-bdos.md` (EOF, flush-on-full/flush-on-close, zero padding, buffer-counter meaning). `src/bdos/bdos.md` points there.

### Key decisions reflected in the diff
- The buffer counter means different things per direction: bytes already consumed on a read handle (128 = used up), bytes pending on a write handle (0..127 between calls).
- File length stays whole sectors. A buffered reader sees the zero padding after the last written byte before it gets `0` (EOF).

## [50] CI: GitHub Actions running the Python unit and e2e tests of all components — 2026-11-09

Tags: `build` `tests`
PR: [#74](https://github.com/bcichonski/bc16/pull/74)
Builds on: #48, #49

### What was built
- `.github/workflows/tests.yml` (`tests`) runs on pushes and PRs to `bc64`, with concurrency cancel and read-only permissions:
  - a `unit` job on a Python 3.10 / 3.14 matrix runs `run_tests.py --group unit`;
  - an `e2e` job (needs `unit`, Python 3.14) regenerates `smoke.bdd` and `smoke_transcript.txt` from `os.bdd`, fails if they differ from the committed copies (`git diff --exit-code src/bc64/testdata/`), then runs `run_tests.py --group e2e`;
  - when e2e fails, the job reruns the e2e modules with `BC64_UPDATE_GOLDEN=1` and uploads the golden patch and `testdata/` as the `e2e-golden-diff` artifact;
  - both jobs end with a guard that fails if a `cpudebug.log` appears or `release/` changes.
- `run_tests.py`:
  - `--group unit|e2e|all`;
  - the suites are chosen by rule (`select_src_modules`) rather than a fixed list: `emulator` (`bc64/test_*.py` and other `src/test_*.py`), `ftool`, `assembler`, `compiler`, and `e2e` (`test_e2e_*.py`, `test_bc64_smoke.py`);
  - `parse_counts` reads unittest's counts (failures, errors, skipped, expected failures);
  - when `GITHUB_STEP_SUMMARY` is set, a Markdown results table is appended to it;
  - a suite with no modules fails.
- New `src/test_run_tests.py` (17 tests): suite selection on a synthetic and the real tree, group filtering, parsing the counts, the summary table, and exit codes.
- Docs: a CI section in root `CLAUDE.md`, a README note, and an update to `docs/analysis/06-toolchain.md`.

### Key decisions reflected in the diff
- The per-component split and the summary are in `run_tests.py`, not in the YAML, so a local run and CI report the same thing from one command.
- The CI e2e artifact comes from regenerating the goldens after a failure, not from changes to the harness.
- Slow e2e scenarios (`BC64_E2E_SLOW`) stay off in CI.

## [49] End-to-end tests on the headless emulator (after #3) — 2026-11-09

Tags: `emulator` `devices` `tests`
PR: [#72](https://github.com/bcichonski/bc16/pull/72)
Builds on: #3, #48

### What was built
- `--no-floppy` option in `bc64.py`. It attaches the new `NoFloppyDrive` in `bc64_io.py` on port `0x08` (reads `0x00`, ignores writes), so bcOS goes straight to the monitor. It counts as a headless option and conflicts with `--disk-a`/`--disk-b` (usage error).
- New `src/e2e_harness.py`, a plain module rather than a test. It provides:
  - `run_session`: boots `bc64.py` on temp copies of the discs, fails on exit 3 or another non-zero exit, and checks that the source discs are untouched and no `cpudebug.log` appeared;
  - `check_golden`: a byte-exact compare with a unified diff, plus a `BC64_UPDATE_GOLDEN=1` update mode;
  - regex masks, marker assertions, and a `@slow` decorator (`BC64_E2E_SLOW`);
  - `read_catalog` / `disc_put`, a BFS catalog reader and a file writer that allocates the way bdos does.
- Scenarios in `src/test_e2e_bcos.py`, `test_e2e_bdos.py` and `test_e2e_toolchain.py`, with scripts and goldens in `src/bc64/testdata/e2e/`:
  - monitor: boot, unknown command, dump/write/print;
  - bdos shell on `smoke.bdd`: boot, `ls`, `cat`, `hellowrd`, `rm` (checked in `ls` and in the catalog), error paths;
  - toolchain: B source → `bc.py` → `bc81asmc.py` → `ftool btap2bin` → put on a disc → boot → run.
- Two bugs found by these tests are kept as `expectedFailure` scenarios with markers only, no golden: the tape `s`/`l` round trip, and `cp` swallowing all the remaining input.
- `src/test_e2e_harness.py` tests the harness itself (the session runner, goldens, masks, the slow decorator, the catalog helpers).
- Docs: an e2e section in `docs/01-emulator.md`, a note in `docs/05-bdos.md`, and design decisions E8 (`--no-floppy`) and E9 (e2e testing).

### Key decisions reflected in the diff
- `IOBus` raises `KeyError` on an unmapped port, so "no drive" is a stand-in device rather than a missing one.
- The disc depends on the scenario: monitor scenarios use `--no-floppy`, shell scenarios use the frozen `smoke.bdd`, and the toolchain scenario uses the live `os.bdd` and compares only the program output.
- Instruction limits are set at about 10x the measured need.
- No golden is ever written from broken output. A known bug is an `expectedFailure` that names its issue.

## [3] Emulator headless mode: disks, tape, keyboard and output from the command line — 2026-11-09

Tags: `emulator` `tests`
PR: [#71](https://github.com/bcichonski/bc16/pull/71)
Builds on: #48

### What was built
- `bc64.py` has an argparse CLI: `rom`, an optional `trace` word, `--disk-a`/`--disk-b`, `--tape-dir`, `--input` (`-` = stdin), `--output` and `--max-instructions`.
- The emulator runs headless when any of those options is given or stdin isn't a terminal. Piped stdin is then typed as keys. Without options and with a terminal, the console `Environment` is used as before.
- Exit codes: 0 for a halt or end of input, 2 for a usage error, 3 when the instruction limit is reached (with a message on stderr), and 1 for an exception.
- `Bc64.run(max_instructions)` is a limited run loop. Without a limit it still calls `cpu.run()`.
- New `ScriptedEnvironment` in `bc64_env.py`:
  - answers `Disk A/B name:` from the options without reading input;
  - reads keys from a file or stdin and folds LF, CR LF and CR into one CR;
  - raises `EndOfInput` when the input runs out, which ends the run cleanly with no memory dump;
  - resolves relative `.btap` names in `--tape-dir`;
  - copies every printer byte to `--output`.
- Tests:
  - `ScriptedEnvironmentTests` (12) in `test_env.py`;
  - `src/test_bc64_cli.py` (24): argument parsing, run and exit codes;
  - `src/test_bc64_smoke.py`: a byte-exact transcript of a bdos session on a frozen `testdata/smoke.bdd`, and a live check of `os.bdd` against markers that survive a rebuild.
  - Test data: `smoke_session.txt`, `smoke_live_session.txt`, `smoke_transcript.txt`, and `.gitattributes` `* -text`.
- Docs: a headless-mode section in `docs/01-emulator.md`, how to refresh the smoke disc and transcript in `src/bc64/CLAUDE.md`, and design decision E7.

### Key decisions reflected in the diff
- Headless mode is a separate environment class, so the console path is unchanged. The limited run loop repeats `cpu.run()` in `bc64.py`, so the two must be kept in step.
- End of input is a clean stop (exit 0, no dump). A script has to check its output as well as the exit code.
- Disk prompts are recognised by their text (`Disk X name:`).

## [48] Tests first: fix the current test suites, then add the missing unit tests — 2026-11-08

Tags: `tests`
PR: [#52](https://github.com/bcichonski/bc16/pull/52)
Builds on: #13

### What was built
- A single runner: `run_tests.py` at the repo root (standard library only). It runs the emulator, assembler and compiler suites as subprocesses, each in its own directory, and prints one PASS/FAIL line per suite. `requirements.txt` lists `parsy`, and `src/run_tests` became a thin wrapper around the runner.
- The emulator tests moved from `src/tests/` to `src/bc64/` (`test_cpu`, `test_io`, `test_mem`, `test_registers`). `test_CLR_opcodes` was fixed: its offsets were wrong, the CPU was right.
- New emulator tests:
  - `test_cpu_alu.py` (93): every `alu`/`alu16` operation, its flags and instruction length;
  - `test_cpu_control.py` (57): nop/kil, mov, jmp/jmr/jrx, stack, call/ret, I/O;
  - `test_devices.py` (45): floppy and tape recorder;
  - `test_membus.py` (13);
  - `test_env.py` (14).
- New assembler tests:
  - `bc81asmc_emit_tests.py` (70): labels, relative offsets, directives, `.btap` writer, error cases;
  - `bc81asmc_opcode_agreement_tests.py`: every grammar form is assembled and run for one instruction on the CPU, with a guard test that fails when a grammar form has no test case.
- New compiler tests: `bc_codegen_tests.py` (35), covering program shape, expressions, variables, control flow, functions, asm, the preprocessor and scope errors.
- New `src/test_ftool.py` (11): btap2bin, creating a `.bdd`, sector import/export, the CLI.
- Tests are silent on a passing run: the debug switches in the test modules are now off.
- Docs: the known quirks in `docs/01-emulator.md` are each linked to an issue (#4, #7), and design decision G11 records the runner and the known-bug policy.

### Key decisions reflected in the diff
- Known-bug policy. A bug whose fix is decided gets a test of the correct behaviour marked `@unittest.expectedFailure` with the issue number: #4 negated `jrx`, #11 `out #r, imm`. A bug whose behaviour is undecided gets a test that pins today's behaviour and names the issue: #4 div/mod by zero, #4 `setate` typo, #7 `TOPMEM`.
- A tests-only story: production defects found while testing were reported, not fixed.

## [13] Compiler: run on Linux/macOS and Python 3.13+ (remove the msilib import) — 2026-11-08

Tags: `compiler` `build`
PR: [#51](https://github.com/bcichonski/bc16/pull/51)

### What was built
- `bc_ast.py` drops the Windows-only `from msilib.schema import Error` (removed in Python 3.13), so the compiler imports on Linux, macOS and Python 3.13+. It defines `class CompilerError(Exception)` instead, used by the scope push/pop errors.
- `bc.py` and `bc_dbg.py` write `.basm`/`.genb` files as UTF-8, so the output no longer depends on the host's default encoding.
- `src/bcc` is now executable and picks `winpty python`, then `python3`, then `python`.
- `TestCompilerError` in `bc_tests.py` checks that `CompilerError` is an `Exception` and that `pop_scope` with no scope raises `Scope none error`.
- Docs: `docs/03-compiler.md`, `src/bc/CLAUDE.md`, root `CLAUDE.md` and `design-decisions.md` no longer describe the msilib workaround.

### Key decisions reflected in the diff
- Only `bcc` changed its interpreter choice, and it keeps `winpty` when present, so the owner's Git Bash workflow is unchanged. The other scripts still call `winpty`.
- Newline handling was left as is (native text mode). Only the encoding was pinned, and the committed outputs were not rebuilt.
