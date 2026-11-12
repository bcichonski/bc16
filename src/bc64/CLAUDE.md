# Emulator (bc64 / bc8183 CPU)

Reference: `docs/01-emulator.md`. The entry point is `src/bc64.py`. It wires the bus, loads
the ROM image at `0x0000`, runs the CPU, and dumps memory to `bc64.dmp` on `KIL`. The tests
live in `src/bc64/tests/` (`src/tests/test_ftool.py` for `ftool.py`).

## Commands (from `src/`)

```bash
python3 -m unittest discover -s bc64/tests -t . -p "test_*.py"     # emulator package tests (all suites: ../run_tests.py)
python3 -m unittest bc64.tests.test_cpu.CpuTests.test_CLC16_opcodes   # a single test
python3 bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81 [d]                # run; "d" (any 2nd arg) = per-instruction trace
bc64 bc81asmc/bcOS/bcos_v1_2_0.b81 [d]                           # same via the console command (`pip install -e .`), any directory
printf 'ls\nhellowrd\nexit\n' | python3 bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81 --disk-a os.bdd --output out.txt   # headless (keys from stdin); use a copy of os.bdd; ROM and os.bdd come from the build
```

`src/bc81asmc/tests/bc81asmc_opcode_agreement_tests.py` checks the CPU against the assembler for every opcode form.
Known bugs are `expectedFailure` tests that name their issue; they show as expected failures,
not failures. See `docs/01-emulator.md`, Known quirks.

## End-to-end (smoke) tests

`src/tests/test_bc64_smoke.py` boots bdos headless on a temp copy of the freshly built `src/os.bdd`. Its
byte-exact test compares the session with `smoke_transcript.txt`, and the live test checks only a few
markers. `os.bdd` and the ROM are not committed: build first (`cd src && ./buildos && ./buildtools &&
./buildapps && ./makedisc`); `python3 run_tests.py` does that for the e2e suite unless `--no-build`.
After an intended change in bcOS, bdos or the emulator, regenerate the transcript (from `src/`):

```bash
d=$(mktemp -d) && cp os.bdd $d/os.bdd && (cd $d && \
  python3 "$OLDPWD/bc64.py" "$OLDPWD/bc81asmc/bcOS/bcos_v1_2_0.b81" --disk-a os.bdd \
  --input "$OLDPWD/bc64/testdata/smoke_session.txt" --output "$OLDPWD/bc64/testdata/smoke_transcript.txt" \
  --max-instructions 200000000 < /dev/null); rm -rf $d   # runs in the temp dir: bc64.dmp lands there
python3 -m unittest tests.test_bc64_smoke
```

Check the transcript diff by eye: it should show only the intended changes, then commit
`smoke_transcript.txt`. The session runs on a temp copy, so `os.bdd` itself is never written by the
emulator. CI's `e2e` job builds, runs the tests on the fresh outputs and fails if the transcript or a golden
differs or the tree is not clean. Tests that boot the real ROM are in `src/tests/test_e2e_rom.py`.

## End-to-end scenarios

The e2e modules boot the emulator headless and compare the printer output with goldens:
`src/tests/test_e2e_bcos.py` (monitor, `--no-floppy`), `src/tests/test_e2e_bdos.py` (shell on a temp copy
of the built `os.bdd`), `src/tests/test_e2e_toolchain.py` (B program to disc and run, on a copy of `os.bdd`)
and `src/tests/test_e2e_harness.py` (harness self-tests). The harness is `src/tests/e2e_harness.py`, a plain module
and not a test. Scripts and goldens are in `src/bc64/testdata/e2e/` (`<scenario>.in.txt`,
`<scenario>.golden.txt`). Regenerate with `BC64_UPDATE_GOLDEN=1`, e.g. `cd src && BC64_UPDATE_GOLDEN=1
python3 -m unittest tests.test_e2e_bdos`, then review the diff. Long scenarios need `BC64_E2E_SLOW=1`. Scripts
must not use `q` or a bad-argument command followed by more commands. `q` ends the session with
`fatal error F0 at FF0C` and a bcOS `KIL` (exit 0); a bad-argument command such as `d 00` ends it with an
empty-stack `RET` stop (exit 0, a stderr line). Either one may only be the last command. The known
failure (tape round trip) is an `expectedFailure` test; see `docs/01-emulator.md`.

## How it works

- `bc8183_cpu.py` decodes on the **high nibble** of the first byte (`create_instructions`).
  Sub-operations are in the low nibble and the following bytes. `CLC` with low nibble `F` is
  the bc8183 16-bit ALU (group `A` arithmetic, group `B` binary).
- The registers are 8-bit and addressed by number (`A=1, CI=4, DI=5, CS=8, DS=9, F=B,
  SI=C, SS=D, PC=F`). Memory is reached only through pairs (`get_addr`). 16-bit ALU results
  are written back via `alu_setval16`.
- The CPU stack is **tagged**: a `PSH` frame is `0x10` plus the value (2 bytes); a `CAL`
  frame is `0xC0` plus the return address (3 bytes). `RET` reads the tag, so two push frames
  on top work as an indirect jump. `print_cpu_stack` relies on the tags.
- Relative offsets (`JMR` 7-bit, `JRX`/`CLR` 15-bit) are **sign-magnitude**.
- Devices in `bc64_io.py` subclass `IODevice`: they set `io_port` and implement
  `read_byte()`/`write_byte()`, and are registered on `IOBus` in `bc64.py`. The ports are:
  - `0x0` keyboard
  - `0x1` printer
  - `0x2` tape
  - `0x3` clock
  - `0x5` random generator
  - `0x8` floppy (`FloppyDriveV1`; with `--no-floppy`, `NoFloppyDrive` reads `0x00` and ignores writes)

  The floppy writes and reads `MemBus` directly (DMA).
- All host access (console, files, logging) goes through `bc64_env.Environment`. Keep
  devices free of direct `open`/`print` calls.
- `bc64_env.ScriptedEnvironment` is the headless environment. `bc64.py` (`make_env`) picks it when
  any headless option is given (`--no-floppy` is one) or stdin is not a terminal. It answers `Disk A/B name:` from
  `--disk-a`/`--disk-b` without reading input, reads keys from the input with each line ending
  as one CR, raises `EndOfInput` at the end (caught in `main`, exit 0), resolves `.btap` names in
  `--tape-dir`, and copies printer bytes to `--output`. The console `Environment` is unchanged.

## Rules

- **Opcode or encoding changes must also be made in `src/bc81asmc/bc81asmc_ast.py`** (and in
  `README.md` / `docs/02-assembler.md`). Add a test for any new opcode to `tests/test_cpu_alu.py` or `tests/test_cpu_control.py`, and
  extend `src/bc81asmc/tests/bc81asmc_opcode_agreement_tests.py` so the assembler and the CPU agree on it.
- Port numbers, FDD commands and status codes are part of bcOS and bdos code
  (`bcos.basm`, `bdioh.b`); changing them breaks booting.
- Known latent bugs that existing code depends on not hitting:
  - `op_EXT` checks the `JRX` negation bit in the wrong nibble;
  - the `OUT` immediate form is broken;
  - `FloppyDriveV1.write_byte` sets `self.setate` (a typo).

  If you fix one, check that the assembler and compiler output still matches.
- Memory is 65,536 bytes (`0x0000–0xffff`): `MEMORY_SIZE = 0x10000`, `TOP_ADDRESS = 0xffff`
  holds `KIL` (written by `Bc64.write_top_kil()` after the ROM load), `STACK_TOP = 0xfffe`. A stack access
  outside memory stops the CPU like `KIL` (stderr line, exit 0); floppy DMA wraps with `& 0xffff`.
