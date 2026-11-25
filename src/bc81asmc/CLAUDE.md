# Assembler (bc81asmc)

Reference: `docs/02-assembler.md` has the syntax and full instruction encoding.
`bc81asmc_grammar.py` is the real grammar; `grammar.txt` is an early sketch.

## Commands

```bash
cd src && python3 bc81asmc/bc81asmc.py --verbose path/file.basm   # -> path/file.btap (always btap)
cd src && python3 bc81asmc/bc81asmc.py --lst path/file.lst --map path/file.map path/file.basm   # also the listing and the symbol map (both optional)
bc81asmc --verbose path/file.basm                                 # same via the console command (`pip install -e .`), any directory
cd src/bc81asmc && python3 -m unittest discover -s tests -t . -p "*_tests.py"   # grammar and emit tests (silent)
cd src/bc81asmc && python3 -m unittest tests.bc81asmc_tests.TestGrammar.test_hex_imm8
```

The diagnostics tests are `tests/bc81asmc_diag_tests.py` (records, formatter, parse-error conversion),
`tests/bc81asmc_compile_diag_tests.py` (errors raised by `compile()`) and `tests/bc81asmc_cli_tests.py`
(stderr, exit codes and `--verbose`, run as subprocesses).
The listing and map tests are `tests/bc81asmc_listing_tests.py` (the formats, `read_map`, the real bcOS and boot images,
and the `--lst`/`--map` flags as subprocesses).

## How it works

- `bc81asmc_grammar.py` turns each line into one AST dataclass from `bc81asmc_ast.py`.
  Every instruction class has its own `emit(context)`, which writes nibbles/bytes into
  `CodeContext`.
  A label-only line becomes a no-byte node that carries just the label; in pass 1 its address is
  the current address.
- **Two passes:**
  1. emit, with a `0xfa` placeholder wherever a label is used, recorded in
     `context.labels` as `(addr, label, kind)`. A repeated label or `.def` name is an error
     (one per repeated definition), and a line whose emit raises becomes a `cannot encode`
     error;
  2. `compile()` in `bc81asmc.py` patches each placeholder by kind (`hi`, `lo`, `lorel`
     7-bit, `rel15`). An undefined label (one error per use) and an out-of-range relative jump
     are collected as positioned errors; references that resolve are patched as before;
  3. `.assert` lines (no bytes) are evaluated after patching, so forward references work. A failed
     assert is an `assertion failed` diagnostic; an undefined operand is an `undefined label` error
     and no assertion diagnostic.

  `.def` constants and labels share one namespace, so a clash is a duplicate error. A reference
  looks up `.def` first, then the label. A symbol is undefined only when it is in neither table,
  so an address or value of `0x0000` counts as defined.
- **Errors go through `bc81asmc_diag.py`.** It holds `Diagnostic` (1-based line and column,
  message), `AssemblerError` (carries every diagnostic; `compile()` raises it), the formatter
  (`file:line:col: error: ...`, source line, caret) and the conversion of a parsy `ParseError`.
  Node positions are attributes (`lineno`, `col`), not dataclass fields, so node equality is
  unchanged. A new check (e.g. the `.assert` evaluation, #8) must append a `Diagnostic` and raise through
  this module, never `print` or raise a bare exception. Only `main()` prints and exits.
- **Pre-pass (#114)**, `bc81asmc_pre.py`, before the parser. `assemble_text(text, path)` in `bc81asmc.py` runs
  `prepass()` first. It replaces each `#include`, `#define` and `#link` line in the text handed to the parser with a bare
  `;` comment line (blank lines are a syntax error in bc81asmc), so line numbers stay the same;
  it reads B headers in the directory of the main file, and records the define table (`context.define_table`, a `DefineTable`), the `#link` names (`context.link_names`) and the non-fatal warnings
  (`context.warnings`). Any pre-pass error stops the run before parsing. Name resolution is not in the pre-pass: a
  name in a numeric operand is resolved in `bc81asmc_ast.py` (`CodeContext.number`, through `NameRef` in the grammar),
  so the width comes from the operand. Tests: `tests/bc81asmc_pre_tests.py` (the pre-pass),
  `tests/bc81asmc_pre_cli_tests.py` (the CLI, as subprocesses) and `tests/bc81asmc_define_operand_tests.py` (names in
  operands).
- Output is a `.btap` file: a 24-byte preamble (`00 ff 00 ff bc 05`, org, length, name),
  then every byte expanded to 8 bit-bytes, LSB first.
- `--lst FILE` and `--map FILE` (#9). `compile()` keeps a `LineRecord` (line number, start and end address) per
  source line in `context.line_records`, and the labels and `.def`s in `context.label_addresses` and `context.defs`.
  The formatters in `bc81asmc_listing.py` (`format_listing`, `format_map`) read the bytes after pass 2, so the
  listing shows the patched values. The module does no I/O: `main()` writes the files, after the `.btap` and only
  on success.

## Rules

- Opcodes and encodings live in `src/bc8183_isa.py` (shared with `src/bc64/bc8183_cpu.py`; G14). Change them there only,
  never write an opcode value in the assembler, and add tests
  on both sides (`tests/bc81asmc_tests.py`, `tests/bc81asmc_emit_tests.py`, `src/bc64/tests/test_cpu_*.py`).
  `tests/bc81asmc_opcode_agreement_tests.py` checks that the two sides agree; extend it for new forms, together with
  the ISA form-table and source-guard tests.
- In the grammar, more specific alternatives must come first in the `|` chains
  (`mnemonic`, `mCLC`). For example, the 16-bit forms are listed before the 8-bit ones; a
  shorter match first would swallow the longer form.
- The syntax is strict: lowercase only, hex only (`0xHH`, `0xHHHH`, `#0xH` for an `IN`
  port), and a newline at the end of every line, including the last. Generated `.basm` from
  the compiler must follow the same rules.
- `emit_4bit` packs nibbles. A label reference can't start on a half-emitted byte, so the
  instruction layout has to keep label operands byte-aligned.
- The immediate form `out #r, 0xHH` encodes `Dr HH` (`D0 | n`, then the full value; `n` is 1 for `a`, 4 for `ci`, 5 for `di`). The port register must be `a`, `ci` or `di`; any other one is rejected in `emit` with a `cannot encode` error (A11 in `docs/specs/memory/design-decisions.md`). Keep that check. The `CLC_A_IMM` 16-bit branch is dead code.
- The register-register 16-bit forms take an implied second pair (`csci`→`dsdi`, `dsdi`→`csci`). `emit` rejects any other second operand; the CPU ignores the written one. Keep that check (see `docs/02-assembler.md`, Errors).
- Every 16-bit ALU op with destination `af` (`add sub mul div mod and or xor shl shr not inc dec`, immediate
  and register forms) is rejected in `emit` with a `cannot encode` error (A8 in
  `docs/specs/memory/design-decisions.md`). Keep that check; `af` is not a 16-bit pair.
- `clr pair` (the relative call) takes only the pairs `csci`, `dsdi` and `sssi`. `clr af` and any other non-pair are rejected in `emit` with a `cannot encode` error, because the offset from `af` would include the flags (A9 in `docs/specs/memory/design-decisions.md`). Keep that check.
