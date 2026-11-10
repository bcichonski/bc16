# Emulator: analysis

Reference: [../01-emulator.md](../01-emulator.md). Decisions: E1–E6, G8 in
[../specs/memory/design-decisions.md](../specs/memory/design-decisions.md).

## Current state

- `src/bc64.py` plus `src/bc64/` (about 1,300 lines): the bc8183 CPU v1.2 (20240814), with
  6 devices on ports `0x0`, `0x1`, `0x2`, `0x3`, `0x5` and `0x8`, a flat 64 KB memory, and
  an `Environment` layer for host I/O.
- The structure is clean: a table-driven decoder, one class per device, and host access
  isolated behind `Environment`. It's the most solid part of the code base.
- Tests: `src/tests/` has 23 unit tests (CPU, I/O, memory, registers). 22 pass;
  `test_CLR_opcodes` fails with an exception in `op_CAL`.
- Speed: about 130k instructions/s. It is **intentionally slow**, and speed isn't a goal for
  now. Everything about performance is collected in [Performance (deferred)](#performance-deferred).

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

| # | Problem | Evidence | Impact | Issue |
|---|---|---|---|---|
| 1 | Interactive-only I/O | disk and tape names are read from stdin (`get_string`); the keyboard is raw `getch` | the real system can't be tested automatically | #3 |
| 2 | The trace is all-or-nothing | `d` arg → every instruction appended to `cpudebug.log` (27 MB seen) | traces are unusable for long runs | |
| 3 | Latent bugs | `op_EXT` checks the `JRX` negation bit in the wrong nibble; `FloppyDriveV1` `self.setate` typo; division by zero crashes Python; `OUT #r, imm` encoding mismatch (an assembler fix, #11) | a trap for the first program that uses these | #4 |
| 4 | Failing test | `test_CLR_opcodes` | the suite isn't green, so a regression can't be told apart from the known failure | #4 |
| 5 | Opcode constants duplicated in the assembler | `bc8183_cpu.py` vs `bc81asmc_ast.py` | encoding drift between the CPU and the tools | #5 |
| 6 | ~~**Memory was one byte short of 64 KB**~~ (done, #7) | `TOPMEM = 0xffff` was used as the size → `bytearray(0xffff)`; the stack starts at `0xfffe` | fixed: the memory is the full `0x0000–0xffff` (65,536 bytes) | #7 |
| 7 | Release copies diverge | `release/bc32_v1.0/bc32/` contains a full older copy | fixes aren't shared (by design, G9), but confusing | |

## Proposals

### Next steps (small, high value)

1. **Headless mode** (#3): `bc64.py ROM --disk-a os.bdd --disk-b x.bdd --tape-dir DIR
   --input script.txt --output out.txt`. Interactive mode stays the default. This is the
   prerequisite for end-to-end tests (see [06-toolchain.md](06-toolchain.md)) and for the
   web console.
2. **Fixes** (#4): `test_CLR_opcodes` (the test or `op_CAL`), the `JRX` negation bit, the FDD
   `setate` typo. Add tests for negated `jrx` and for `div`/`mod` by zero, which should set a
   flag or halt cleanly rather than crash.
3. ~~**Full 64 KB memory** (#7)~~ (done): 65,536 bytes, `0x0000–0xffff`. The stack starts at
   `0xfffe`, and `0xffff` holds `KIL` (`0xff`) as the ultimate stop; a `ret` or `pop` on an empty
   stack stops just as cleanly. No other address in the memory map moved.

### Improvements

4. **One shared opcode table** (#5, cross-component with the assembler), e.g.
   `src/bc8183_isa.py`, used by the CPU, the assembler, and a new **disassembler**. The
   disassembler gives readable traces and lets you inspect `.btap`/`.bdd` contents.
5. **Better tracing**:
   - a ring buffer of the last N instructions, dumped on exception or `KIL`;
   - trace filters (address range, on a `cal` to a label);
   - a symbol map from the assembler (see [02-assembler.md](02-assembler.md)) to show
     labels.
6. **Simple debugger**: breakpoints at addresses, single-step, memory dumps. `src/bc/bc_dbg.py`
   could grow into this.
7. **Configurable disc geometry** in `FloppyDriveV1` (tracks, sectors) for roadmap item 7.
   Keep 64×16 as the default so old discs still work.
8. **Display device** ("monitor"): a character-cell screen on a free port, rendered in the
   terminal (curses) or in a small window. Design it before networking, as both need the
   same port and protocol conventions.
9. **Interactive web console** (#6): run the BC64 in the browser. Recommended: the existing
   Python emulator on WebAssembly (Pyodide) with a terminal widget and a `WebEnvironment`,
   so there is still a single emulator source (G10). Needs headless mode (#3) first.

## Performance (deferred)

The emulator is **intentionally slow**, and speed is not critical for now. This section
keeps the findings for later; none of it is scheduled.

- **Measured:** about 130k instructions/s (a `dec csci / or / jmr` loop), roughly a quarter
  of a real 1980s 8-bit CPU.
- **Debug strings on every instruction:** `run_next_opcode` → `print_context()` formats 5
  strings even with tracing off, and `print_debug` throws them away. Calling `print_context`
  only `if self.debug` is a one-line change, measured at 1.6× (about 200k instructions/s).
- **General interpretation overhead:** `FlagsRegister.set_flag` rebuilds `F` from a dict of
  8 `Register` objects each time, and every register is an object with a `while val < 0`
  loop in `set`. This caps the speed at about 200k instructions/s even after the change above.
- **A performance pass**, if ever needed, could aim at about 1M instructions/s:
  - hold registers as plain ints in an array;
  - keep `F` as a bitfield int;
  - inline the `inc_pc`/`nextbyte` handling;
  - index the decode table by the full first byte.

  Keep the public class interface so the tests keep working.
- **When to revisit:** when CI end-to-end runs (#3) or the web console (#6) become too slow
  to be practical.

## Modernisation verdict

**Modernise lightly.** The architecture is sound and should stay. Do:
- headless mode (#3);
- the fixes and the full 64 KB memory (#4, #7);
- the shared ISA table (#5);
- type hints where they help.

Performance is deliberately left out (see above).

Don't replace it with a framework or a different language. Pure Python is part of the
project's simplicity (G10).
