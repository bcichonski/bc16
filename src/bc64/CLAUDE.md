# Emulator (bc64 / bc8183 CPU)

Reference: `docs/01-emulator.md`. The entry point is `src/bc64.py`. It wires the bus, loads
the ROM image at `0x0000`, runs the CPU, and dumps memory to `bc64.dmp` on `KIL`. The tests
are in `src/tests/`.

## Commands (from `src/`)

```bash
python3 -m unittest                                              # all emulator tests (./run_tests)
python3 -m unittest tests.test_cpu.CpuTests.test_CLC16_opcodes   # a single test
python3 bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81 [d]                # run; "d" (any 2nd arg) = per-instruction trace
```

Current status: 22 of 23 tests pass. `test_CLR_opcodes` fails with an exception in `op_CAL`.

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

## Rules

- **Opcode or encoding changes must also be made in `src/bc81asmc/bc81asmc_ast.py`** (and in
  `README.md` / `docs/02-assembler.md`). Add a test in `tests/test_cpu.py` for any new opcode.
- Port numbers, FDD commands and status codes are part of bcOS and bdos code
  (`bcos.basm`, `bdioh.b`); changing them breaks booting.
- Known latent bugs that existing code depends on not hitting:
  - `op_EXT` checks the `JRX` negation bit in the wrong nibble;
  - the `OUT` immediate form is broken;
  - `FloppyDriveV1.write_byte` sets `self.setate` (a typo).

  If you fix one, check that the assembler and compiler output still matches.
- `TOPMEM = 0xffff` makes memory 65535 bytes, so `0xffff` itself is out of range.
