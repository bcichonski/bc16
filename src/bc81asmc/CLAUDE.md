# Assembler (bc81asmc)

Reference: `docs/02-assembler.md` has the syntax and full instruction encoding.
`bc81asmc_grammar.py` is the real grammar; `grammar.txt` is an early sketch.

## Commands

```bash
cd src && python3 bc81asmc/bc81asmc.py --verbose path/file.basm   # -> path/file.btap (always btap)
cd src/bc81asmc && python3 -m unittest discover -s . -t . -p "*_tests.py"   # grammar and emit tests (silent)
cd src/bc81asmc && python3 -m unittest bc81asmc_tests.TestGrammar.test_hex_imm8
```

## How it works

- `bc81asmc_grammar.py` turns each line into one AST dataclass from `bc81asmc_ast.py`.
  Every instruction class has its own `emit(context)`, which writes nibbles/bytes into
  `CodeContext`.
- **Two passes:**
  1. emit, with a `0xfa` placeholder wherever a label is used, recorded in
     `context.labels` as `(addr, label, kind)`;
  2. `compile()` in `bc81asmc.py` patches each placeholder by kind (`hi`, `lo`, `lorel`
     7-bit, `rel15`).

  `.def` constants are looked up before labels.
- Output is a `.btap` file: a 24-byte preamble (`00 ff 00 ff bc 05`, org, length, name),
  then every byte expanded to 8 bit-bytes, LSB first.

## Rules

- Opcode constants are duplicated in `src/bc64/bc8183_cpu.py`. Change both, and add tests
  on both sides (`bc81asmc_tests.py`, `bc81asmc_emit_tests.py`, `src/bc64/test_cpu_*.py`).
  `bc81asmc_opcode_agreement_tests.py` checks that the two sides agree; extend it for new forms.
- In the grammar, more specific alternatives must come first in the `|` chains
  (`mnemonic`, `mCLC`). For example, the 16-bit forms are listed before the 8-bit ones; a
  shorter match first would swallow the longer form.
- The syntax is strict: lowercase only, hex only (`0xHH`, `0xHHHH`, `#0xH` for an `IN`
  port), and a newline at the end of every line, including the last. Generated `.basm` from
  the compiler must follow the same rules.
- `emit_4bit` packs nibbles. A label reference can't start on a half-emitted byte, so the
  instruction layout has to keep label operands byte-aligned.
- Known broken and unused: `out #r, imm`. It emits `D0 rH`, but the CPU expects `Dr HH` (#11). The `CLC_A_IMM` 16-bit branch is
  dead code.
