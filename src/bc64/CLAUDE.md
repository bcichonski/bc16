# Emulator (bc64 / bc8183 CPU)

Reference: `docs/01-emulator.md`. The entry point is `src/bc64.py`. It wires the bus, loads
the ROM image at `0x0000`, runs the CPU, and dumps memory to `bc64.dmp` on `KIL`. The tests
live next to the code: `src/bc64/test_*.py` (`src/test_ftool.py` for `ftool.py`).

## Commands (from `src/`)

```bash
python3 -m unittest discover -s . -t . -p "test_*.py"             # all emulator tests (all suites: ../run_tests.py)
python3 -m unittest bc64.test_cpu.CpuTests.test_CLC16_opcodes    # a single test
python3 bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81 [d]                # run; "d" (any 2nd arg) = per-instruction trace
printf 'ls\nhellowrd\nexit\n' | python3 bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81 --disk-a os.bdd --output out.txt   # headless (keys from stdin); use a copy of os.bdd
```

`src/bc81asmc/bc81asmc_opcode_agreement_tests.py` checks the CPU against the assembler for every opcode form.
Known bugs are `expectedFailure` tests that name their issue; they show as expected failures,
not failures. See `docs/01-emulator.md`, Known quirks.

## End-to-end (smoke) tests

`src/test_bc64_smoke.py` boots bdos headless. Its byte-exact test runs on a **frozen** disc,
`src/bc64/testdata/smoke.bdd`, not on `src/os.bdd`, and the live-disc test checks only a few
markers. So after `os.bdd` is rebuilt (bdos, utilities, apps), the e2e tests say little about
the current system until the frozen disc is refreshed. **For now, to run the e2e tests
meaningfully, refresh `smoke.bdd` and regenerate the transcript first** (from `src/`):

```bash
cp os.bdd bc64/testdata/smoke.bdd
d=$(mktemp -d) && cp bc64/testdata/smoke.bdd $d/os.bdd && (cd $d && \
  python3 "$OLDPWD/bc64.py" "$OLDPWD/bc81asmc/bcOS/bcos_v1_2_0.b81" --disk-a os.bdd \
  --input "$OLDPWD/bc64/testdata/smoke_session.txt" --output "$OLDPWD/bc64/testdata/smoke_transcript.txt" \
  --max-instructions 200000000 < /dev/null); rm -rf $d   # runs in the temp dir: bc64.dmp lands there
python3 -m unittest test_bc64_smoke
```

Check the transcript diff by eye: it should show only the intended changes. Commit `smoke.bdd` and
`smoke_transcript.txt` together with the rebuilt `os.bdd`. The session runs on a temp copy, so
`smoke.bdd` itself is never written by the emulator.

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
  - `0x8` floppy

  The floppy writes and reads `MemBus` directly (DMA).
- All host access (console, files, logging) goes through `bc64_env.Environment`. Keep
  devices free of direct `open`/`print` calls.
- `bc64_env.ScriptedEnvironment` is the headless environment. `bc64.py` (`make_env`) picks it when
  any headless option is given or stdin is not a terminal. It answers `Disk A/B name:` from
  `--disk-a`/`--disk-b` without reading input, reads keys from the input with each line ending
  as one CR, raises `EndOfInput` at the end (caught in `main`, exit 0), resolves `.btap` names in
  `--tape-dir`, and copies printer bytes to `--output`. The console `Environment` is unchanged.

## Rules

- **Opcode or encoding changes must also be made in `src/bc81asmc/bc81asmc_ast.py`** (and in
  `README.md` / `docs/02-assembler.md`). Add a test for any new opcode to `test_cpu_alu.py` or `test_cpu_control.py`, and
  extend `src/bc81asmc/bc81asmc_opcode_agreement_tests.py` so the assembler and the CPU agree on it.
- Port numbers, FDD commands and status codes are part of bcOS and bdos code
  (`bcos.basm`, `bdioh.b`); changing them breaks booting.
- Known latent bugs that existing code depends on not hitting:
  - `op_EXT` checks the `JRX` negation bit in the wrong nibble;
  - the `OUT` immediate form is broken;
  - `FloppyDriveV1.write_byte` sets `self.setate` (a typo).

  If you fix one, check that the assembler and compiler output still matches.
- `TOPMEM = 0xffff` makes memory 65535 bytes, so `0xffff` itself is out of range.
