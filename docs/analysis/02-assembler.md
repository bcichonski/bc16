# Assembler (bc81asmc): analysis

Reference: [../02-assembler.md](../02-assembler.md). Decisions: A1–A5, G5 in
[../specs/memory/design-decisions.md](../specs/memory/design-decisions.md).

## Current state

- About 1,250 lines: a parsy grammar, an AST with an `emit()` per instruction, and a
  two-pass fix-up. v1.3 (240914) supports the full bc8183 set, including 16-bit ALU ops,
  `jrx` and `clr`.
- **75/75 grammar tests pass.** It is the most reliable tool in the chain: it assembles
  bcOS, the boot loader, bdos and every app.
- It is a deliberately minimal language: `.org`, `.db`, `.mv`, `.def`; no expressions,
  macros or includes (A3).

## Development direction (roadmap)

- **Item 8:** an assembler running on the BC64 itself. That requires a version written in B
  (or assembly) that reads source from disc via bdio and writes a `.PRG`. The host
  assembler's simple syntax is an asset here; keep it that way.
- Any new CPU feature (e.g. the "improved stack frames" of item 1) lands here first.

## Problems

| # | Problem | Evidence | Impact |
|---|---|---|---|
| 1 | No guards for the address contracts | bcOS must end below `0x0d80` (21 bytes left); `os_metacall` must stay at `0x0008`; `bdos` must end below `0x5d00` | an overflow corrupts memory silently at run time |
| 2 | No listing or symbol output | only `.btap` is written | addresses of labels have to be read from `--verbose` console output; traces can't show symbols |
| 3 | Poor error messages | a parse error is a raw parsy `ParseError` with a character index (the compiler prints line context; the assembler doesn't); an undefined label raises a `KeyError` | slow debugging, especially of generated `.basm` |
| 4 | Opcodes duplicated with the CPU | `Bc8183` constants in `bc81asmc_ast.py` vs `bc8183_cpu.py`. There's even a typo'd constant name (`CLC_SUN16`) | drift risk |
| 5 | `out #r, imm` emits 1.5 bytes | `OUT.emit` with an integer argument emits 3 nibbles | silent corruption if anyone uses it |
| 6 | No label arithmetic | `:label+1` and `hi(:label)` aren't possible; `.def` only takes a literal | workarounds in hand-written asm (e.g. `.mv` + `inc`) |
| 7 | Single `.org`, output is always `.btap` | ROM and disc images need the extra `ftool btap2bin` step | longer pipeline; the `--btap` flag does nothing |
| 8 | Pipfile pins Python 3.7 | `src/bc81asmc/Pipfile` | outdated, and only this tool declares dependencies at all |

## Proposals

### Next steps

1. **`.assert` directive**, e.g. `.assert :user_mem < 0x0d80` and
   `.assert :os_metacall = 0x0008`, evaluated in pass 2. Add asserts to `bcos.basm` and
   `boot.basm`, and let the compiler emit one for `#code`-based programs (code end <
   `#heap`). This enforces design decisions G1/G2 cheaply.
2. **Listing and map output** (`--lst`, `--map`): address, bytes and source per line, and a
   sorted symbol table. Useful for the emulator debugger and for checking ABI addresses in
   review.
3. **Error reporting with file:line:column** and the offending line, for both parse errors
   and undefined labels.

### Improvements

4. **Shared ISA table** with the emulator (see [01-emulator.md](01-emulator.md)). Drive the
   grammar's mnemonic list and the encoders from it, and add a round-trip test: assemble →
   disassemble → assemble.
5. **Fix or remove `out #r, imm`**: either implement a proper 3-byte encoding together with
   the CPU, or reject it in the grammar with a clear error.
6. **Minimal expressions**: `:label+0xNN`, `:label-0xNN`, `hi(:x)`, `lo(:x)`. Nothing more.
   Keep the language simple for the self-hosted version.
7. **`--bin` output** with optional padding, so ROMs and disc sectors come straight out of
   the assembler. `ftool btap2bin` stays for tapes.
8. **`.include`** for shared constants between `bcos.basm` and `boot.basm` (e.g. a
   `bc64_abi.inc` with `os_metacall`, `bdos_bootaddr` and the FDD commands).

## Modernisation verdict

**Keep and improve incrementally.** The parsy design is appropriate. Drop the Pipfile in
favour of a top-level `pyproject.toml` (see [06-toolchain.md](06-toolchain.md)), and add
diagnostics and the contract assertions. Resist adding a macro language: the compiler is
the place for higher-level features, and roadmap item 8 benefits from a small assembler.
