# Emulator: analysis

Reference: [../01-emulator.md](../01-emulator.md). Decisions: E1–E5, G8 in
[../specs/memory/design-decisions.md](../specs/memory/design-decisions.md).

## Current state

- `src/bc64.py` plus `src/bc64/` (about 1,300 lines): the bc8183 CPU v1.2 (20240814), with
  6 devices on ports `0x0`, `0x1`, `0x2`, `0x3`, `0x5` and `0x8`, a flat 64 KB memory, and
  an `Environment` layer for host I/O.
- The structure is clean: a table-driven decoder, one class per device, and host access
  isolated behind `Environment`. It's the most solid part of the code base.
- Tests: `src/tests/` has 23 unit tests (CPU, I/O, memory, registers). 22 pass;
  `test_CLR_opcodes` fails with an exception in `op_CAL`.
- Speed: **about 130k instructions/s** (a measured `dec csci / or / jmr` loop). That is
  roughly a quarter of a real 1980s 8-bit CPU.

## Development direction (roadmap)

- **Item 1 leftover:** "improved CPU stack frames". The tagged 2/3-byte frames (E4) are
  still in place.
- **Item 7:** discs with 80 tracks × 32 sectors (320 KB). `FloppyDriveV1` geometry is a set
  of class constants.
- README: "planned monitor support later", i.e. a display device next to the printer.
- **Item 10:** networking: a new port device, polled (G8).
- "One extension slot" (direct memory access for a device) is described in the README but
  only the floppy uses DMA.

## Problems

| # | Problem | Evidence | Impact |
|---|---|---|---|
| 1 | Debug strings are built on every instruction, even with tracing off | `run_next_opcode` → `print_context()` formats 5 strings, which `print_debug` then discards. Measured 1.6× slowdown | every run is slower than needed |
| 2 | General interpretation overhead | `FlagsRegister.set_flag` rebuilds `F` from a dict of 8 `Register` objects each time; every register is an object with a `while val < 0` loop in `set` | caps the speed at about 200k instructions/s even after #1 |
| 3 | Interactive-only I/O | disk and tape names are read from stdin (`get_string`); the keyboard is raw `getch` | the real system can't be tested automatically |
| 4 | The trace is all-or-nothing | `d` arg → every instruction appended to `cpudebug.log` (27 MB seen) | traces are unusable for long runs |
| 5 | Latent bugs | `op_EXT` checks the `JRX` negation bit in the wrong nibble; `OUT #r, imm` encoding mismatch; `FloppyDriveV1` `self.setate` typo; division by zero crashes Python | a trap for the first program that uses these |
| 6 | Failing test | `test_CLR_opcodes` | the suite isn't green, so a regression can't be told apart from the known failure |
| 7 | Opcode constants duplicated in the assembler | `bc8183_cpu.py` vs `bc81asmc_ast.py` | encoding drift between the CPU and the tools |
| 8 | Memory is 65,535 bytes | `TOPMEM = 0xffff` → `bytearray(0xffff)` | address `0xffff` can't be used; off-by-one with the docs |
| 9 | Release copies diverge | `release/bc32_v1.0/bc32/` contains a full older copy | fixes aren't shared (by design, G9), but confusing |

## Proposals

### Next steps (small, high value)

1. **Headless mode**: `bc64.py ROM --disk-a os.bdd --disk-b x.bdd --tape-dir DIR
   --input script.txt --output out.txt`. Interactive mode stays the default. This is the
   prerequisite for end-to-end tests (see [06-toolchain.md](06-toolchain.md)).
2. **Only build debug strings when tracing**: call `print_context` only `if self.debug`. A
   one-line change for 1.6×.
3. **Fix `test_CLR_opcodes`** (the test or `op_CAL`) and the `JRX` negation bit. Add tests
   for negated `jrx` and for `div`/`mod` by zero, which should set a flag or halt cleanly
   rather than crash.

### Improvements

4. **Performance pass**, aiming at about 1M instructions/s:
   - hold registers as plain ints in an array;
   - keep `F` as a bitfield int;
   - inline `inc_pc`/`nextbyte` handling;
   - decode table indexed by the full first byte.

   Keep the public class interface so the tests keep working.
5. **One shared opcode table** (e.g. `src/bc8183_isa.py`) used by the CPU, the assembler,
   and a new **disassembler**. The disassembler gives readable traces and lets you inspect
   `.btap`/`.bdd` contents.
6. **Better tracing**:
   - a ring buffer of the last N instructions, dumped on exception or `KIL`;
   - trace filters (address range, on a `cal` to a label);
   - a symbol map from the assembler (see [02-assembler.md](02-assembler.md)) to show
     labels.
7. **Simple debugger**: breakpoints at addresses, single-step, memory dumps. `src/bc/bc_dbg.py`
   could grow into this.
8. **Configurable disc geometry** in `FloppyDriveV1` (tracks, sectors) for roadmap item 7.
   Keep 64×16 as the default so old discs still work.
9. **Display device** ("monitor"): a character-cell screen on a free port, rendered in the
   terminal (curses) or in a small window. Design it before networking, as both need the
   same port and protocol conventions.

## Modernisation verdict

**Modernise lightly.** The architecture is sound and should stay. Do:
- the performance pass;
- headless mode;
- the shared ISA table;
- type hints where they help.

Don't replace it with a framework or a different language. Pure Python is part of the
project's simplicity (G10).
