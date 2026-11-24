# bc81asmc: assembler for the bc8183 CPU

`src/bc81asmc/` is a two-pass assembler written with the
[parsy](https://pypi.org/project/parsy/) parser-combinator library. The current version is
**v1.3 (240914)**, for the bc8183 CPU described in [01-emulator.md](01-emulator.md).

| File | Contents |
|---|---|
| `bc81asmc.py` | CLI, the two passes (emit + label fix-ups), `.btap`, `.lst` and `.map` writers |
| `bc81asmc_grammar.py` | the parsy grammar (the real syntax reference) |
| `bc81asmc_ast.py` | one dataclass per instruction/directive, each with its own `emit()`; opcodes and encodings come from `src/bc8183_isa.py` |
| `bc81asmc_diag.py` | error records (`Diagnostic`, `AssemblerError`), the `file:line:col` formatter, parsy `ParseError` conversion |
| `bc81asmc_listing.py` | the `.lst` listing and `.map` symbol map text (no I/O); `read_map` parses a map for other tools |
| `tests/bc81asmc_tests.py` | unit tests (need `parsy`) |
| `grammar.txt` | early informal grammar sketch |
| `examples/` | `hello.basm`, `first.basm` |
| `bcOS/` | the bcOS source, see [04-bcos.md](04-bcos.md) |

## Usage

```bash
pip install -e .                                  # once, from the repo root: parsy + the console commands
bc81asmc [--verbose] path/to/file.basm           # from any directory
python bc81asmc/bc81asmc.py [--verbose] path/to/file.basm   # the same, from src/
```

- The output is always `path/to/file.btap`, a tape image. The `--btap` flag is accepted but
  has no effect.
- `--verbose` prints every line with its address in pass 1, plus the relative-jump
  fix-ups.
- `--lst FILE` writes a listing (every source line with its address and bytes) and `--map FILE`
  writes a symbol map (labels and `.def` constants with their values). Both are optional and
  are described in [`.lst` and `.map` output formats](#lst-and-map-output-formats). They are
  written only when assembly succeeds, after the `.btap`. The `.btap` is the same with or
  without them. The build scripts write `<name>.lst` and `<name>.map` next to each `.btap`.
- To get a raw binary (ROM image or disk sectors), run `./ftool btap2bin file.btap file.bin`.

### `.btap` output format

The file holds a 24-byte preamble followed by the code, **one byte per bit, LSB first**
(the format the tape recorder uses):

```
00 ff 00 ff  bc 05  ADDR-hi ADDR-lo  LEN-hi LEN-lo  00  name[13, zero padded]
```

`ADDR` is the `.org` address and `name` is the source file name without its extension.

### `.lst` and `.map` output formats

Both files are UTF-8 with `\n` line endings.

**The listing (`--lst`)** has one row per source line, in source order. Blank and comment-only
lines are kept, so the listing reads like the source. A row is:

```
HHHH  HH HH HH HH  source line
```

- `HHHH` is the address in lowercase hex, without `0x`. It is shown when the line emits bytes,
  carries a label, or is an `.org`. Otherwise the column is blank: comments, blank lines and
  `.def` and `.assert` lines have no location of their own.
- The bytes are the final values, read after pass 2, so a forward reference shows its real
  address and not `fa`. The bytes column holds up to 4 bytes and is padded to a fixed width.
- A `.db` longer than 4 bytes goes on in extra rows that hold only an address and bytes. The
  longest instruction (`.mv`) is 4 bytes, so only `.db` wraps.
- Trailing spaces are removed from the source text.

An excerpt of `src/bdos/boot.lst`:

```
0e00                                  .org 0x0e00
                                      .def bd_shell, 0x0f00
...
                   ;bd_dstart 0x0001
0e00  11 02        bd_bootstrap:      mov a, 0x02
0e02  19 0e 15 59                     .mv dsdi, :bd_boot_loadmsg
...
0e55  65 72 72 00  bd_boot_errmsg:    .db 'err', 0x00
...
0e5d  67 00
...
0e80               bd_end:            .assert :bd_end <= 0x0e80
```

**The map (`--map`)** has two header lines and then one line per symbol:

```
; bc81asmc map <source file name>
; org 0xHHHH end 0xHHHH
0xHHHH <kind> <name>
```

- `org` is the `.org` address. `end` is the first address past the image (org plus the code
  length). A label-only line at the end of the file gets this address.
- `kind` is `label` for a label and `def` for a `.def` constant. A `.def` is listed at its
  value even when that value is not an address in the image (for example `os_metacall`).
- The symbols are sorted by value, then by name. Labels and `.def`s share one namespace, so
  each name appears once. There is no by-name section.

An excerpt of `src/bdos/boot.map`:

```
; bc81asmc map boot.basm
; org 0x0e00 end 0x0e80
0x0008 def os_metacall
0x0080 def bd_sectsize
0x0e00 label bd_bootstrap
0x0e0f label bd_loop
0x0e11 label bd_dmaconfig
0x0e23 label bd_readsect
0x0e55 label bd_boot_errmsg
0x0e59 label bd_boot_loadmsg
0x0e5f label bd_boot_oscall
0x0e65 label bd_boot_run
0x0e6d label bd_boot_error
0x0e7c label bd_diskver
0x0e80 label bd_end
0x0f00 def bd_shell
```

`read_map(text)` in `src/bc81asmc/bc81asmc_listing.py` is the reader for other tools. It returns
a `SymbolMap` (`source`, `org`, `end` and `symbols`, each with `name`, `value` and `kind`), and
raises `ValueError` on a malformed line or a missing header.

## Source syntax

## Source syntax

```
label:   mnemonic operands   ; comment
```

- **Mnemonics and register names must be lowercase.**
- A label is an identifier followed by `:` at the start of a line. To refer to a label,
  prefix it with a colon: `:label`. A label or `.def` may resolve to 0x0000.
- A label may also stand alone on a line, optionally followed by a `; comment`. Such a line
  emits no bytes. The label gets the address of the next emitted byte. Several label-only lines
  in a row share that address. A label-only line at the end of the file gets the end address
  (org + code length). This lets generated code skip a filler `nop` at every label (the
  compiler change is #104).

  ```
  loop:
  done:          ; both labels = address of the kil
          kil
  end:           ; end address
  ```

- Immediates are **hex only** and the digit count is fixed (a wider value is a syntax error, see [Errors](#errors)):
  - `0xHH`: 8-bit
  - `0xHHHH`: 16-bit
  - `#0xH`: 4-bit (only as the `IN` port)
- Strings use single quotes: `'text'`. There are no escapes.
- `;` starts a comment, which can sit on its own line or after an instruction.
- Every line, including the last, must end with a newline.
- Registers: `a f ci cs di ds si ss pc`. Pairs: `csci dsdi sssi` (memory addressing) and
  `csci dsdi` (16-bit ALU).

### Directives

| Directive | Effect |
|---|---|
| `.org 0xHHHH` | set the load/start address. Use it once, before any code or label (comments and `.def` may come first). A second `.org`, or a `.org` after code or a label, is an error (see [Errors](#errors)) |
| `.db v, v, …` | emit bytes. Each `v` is `0xHH`, `'string'` (raw chars, add `0x00` yourself) or `:label` (2 bytes, big-endian address) |
| `.mv pair, :label` | load a 16-bit label address into a pair. Expands to `mov hi,imm8` + `mov lo,imm8` (4 bytes) |
| `.def name, 0xHHHH` | define a constant, used like a label (`:name`). Good for fixed addresses such as `bdos_bootaddr` |
| `.assert :a OP :b` or `.assert :a OP 0xHHHH` (also `0xHH`) | check a comparison at build time. `OP` is one of `=`, `!=`, `<`, `<=`, `>`, `>=`; an operand is a `:name` (label or `.def`) or a literal. Emits no bytes; a label on the line gets the current address. A failure stops the build (see [Errors](#errors)) |

### How the two passes work

Pass 1 emits code and writes placeholder bytes (`0xfa`) wherever a label address is needed.
Pass 2 patches the placeholders with the high byte, low byte, 7-bit relative or 15-bit
relative value. If a `jmr` target is more than ±127 bytes away, or a `jrx`/`clr` target is
more than ±32767 bytes away, the assembler reports an error at that reference. Pass 1 and
pass 2 keep going after such an error, so every problem is reported in one run (see [Errors](#errors)).
Pass 2 then evaluates every `.assert` line, after all placeholders are patched, so an assert may
name a label defined later in the file. Asserts emit nothing, so they never move an address.

Relative offsets are stored as **sign-magnitude**: bit 7 (or bit 15) is the sign and the
other bits are the magnitude. They are not two's complement.

## Errors

A user error is reported as one block per diagnostic on **stderr**, and the run exits with
status `1`:

```
two.basm:1:8: error: label ':far' too far away for relative 7bit jump (207 bytes)
jmr z, :far
       ^
two.basm:2:5: error: undefined label ':nowhere'
cal :nowhere
    ^
```

- The header is `<file>:<line>:<col>: error: <message>`. `<file>` is the path as given on the
  command line. Lines and columns are **1-based**; a tab counts as one column.
- The next line is the source line as written. The caret line puts `^` under the column
  (tabs are kept, so the caret lines up).
- Exit status `0` means success, `1` any error. Progress lines (`Reading input file`,
  `Code length`, ...) still go to stdout; only the diagnostics go to stderr.
- On error no `.btap` is written, so an old output file is never mistaken for a new one.
- No Python traceback is printed for a user error. `--verbose` prints the traceback of the
  exception that ended the run, after the diagnostics, for debugging the assembler itself.
  `bcc` and `buildos` always pass `--verbose`, so their builds show that traceback too.

| Class | Message (abridged) | Column points at | Notes |
| :--- | :--- | :--- | :--- |
| syntax | `syntax error: expected ...` or `syntax error: unexpected '...'` | the first character the parser cannot accept | only the first syntax error is reported; parsing stops and nothing is assembled |
| undefined label | `undefined label ':name'` | the `:` of the reference | every use is reported, not every name. Only a name defined neither as a label nor as a `.def` is undefined; a label or `.def` at 0x0000 is defined |
| duplicate label | `duplicate label 'name' (first defined at line n)` | the first character of the repeated name | one per repeated definition; the first definition is not reported |
| duplicate symbol | `duplicate symbol 'name' (first defined at line n)` | the first character of the repeated name | `.def` names and labels share one namespace, so a `.def` and a label with the same name clash |
| `.org` placement | `duplicate .org (first .org at line n); use .org once, at the top`, or `.org must come before any code or label` | the start of the `.org` line (column 1 when a label is on that line) | a rejected `.org` has no effect, so later diagnostics are still reported. A source with no `.org` starts at 0x0000 |
| relative range, 7-bit | `label ':name' too far away for relative 7bit jump (n bytes)` | the `:` of the target | `jmr` only (±127 bytes) |
| relative range, 15-bit | `label ':name' too far away for relative 15bit jump (n bytes)` | the `:` of the target | `jrx` and `clr` (±32767 bytes) |
| overflow | `code exceeds the 64 KB address space (past 0xffff)` | the first non-blank character of the line that crosses the limit | reported once per run |
| unencodable line | `cannot encode 'line': reason` | the first non-blank character of the line | the line contributes no bytes and assembly goes on |
| `inc af` / `dec af` | `cannot encode 'inc af': inc af is not allowed: the 16-bit result would overwrite the flags in f (use inc a, or a pair csci or dsdi)` | the first non-blank character of the line | an unencodable line, with `dec` for `dec af`. No bytes are emitted. See [A8](specs/memory/design-decisions.md#a8-every-16-bit-alu-op-on-af-is-rejected-the-assembler-says-why) |
| `out #cs, 0x41` (port register other than `a`, `ci`, `di`) | `cannot encode 'out #cs, 0x41': out #cs, 0xHH takes the port in a, ci or di; load the value into a register and use out #cs, <reg>` | the first non-blank character of the line | an unencodable line, for `out #r, 0xHH` with `r` one of `cs`, `ds`, `f`, `si`, `ss`, `pc`. No bytes are emitted. See [A11](specs/memory/design-decisions.md#a11-out-r-imm-encodes-dr-hh-the-port-register-must-be-a-ci-or-di) |
| `clr af` / other non-pair `clr` | `cannot encode 'clr af': clr af is not allowed: the call offset would be read from a:f, and f holds the flags (use a pair csci, dsdi or sssi)`; `cannot encode 'clr aci': 'aci' is not a pair for clr (use csci, dsdi or sssi)` | the first non-blank character of the line | an unencodable line, for a register operand of `clr` that is not one of the pairs `csci`, `dsdi`, `sssi`. No bytes are emitted. See [A9](specs/memory/design-decisions.md#a9-clr-af-is-rejected-the-call-offset-would-include-the-flags) |
| other 16-bit ALU op on `af` | `cannot encode 'add af, csci': add af is not allowed: the 16-bit result would overwrite the flags in f (use a pair csci or dsdi)` | the first non-blank character of the line | an unencodable line, for `add sub mul div mod and or xor shl shr not` (the mnemonic as written, immediate or register form). No bytes are emitted. See [A8](specs/memory/design-decisions.md#a8-every-16-bit-alu-op-on-af-is-rejected-the-assembler-says-why) |
| implied pair | `cannot encode 'line': second operand must be dsdi when the first is csci`, or `cannot encode 'line': 'sssi' is not a 16-bit pair (use csci or dsdi)` | the first non-blank character of the line | 16-bit ops only (`add`, `sub`, `mul`, `div`, `mod`, `and`, `or`, `xor`, `shl`, `shr` in register form, and `inc`, `dec`, `not`). The second operand of the register form must be the implied pair. No bytes are emitted |
| assertion failed | `assertion failed: <left> <op> <right> (0xLLLL <op> 0xRRRR)`, e.g. `assertion failed: :os_metacall = 0x0008 (0x0009 = 0x0008)` | the first non-blank character of the `.assert` line | the operands as written, then their resolved values. Every failed assert is reported. An undefined operand gives `undefined label` at its `:` instead, and that assert is not evaluated |

Pass 1 and pass 2 keep going after an error and report every problem they find, sorted by
position. The syntax error is the exception: parsing is all-or-nothing, so only the first one
is shown.

Over-wide immediates are syntax errors, not range errors, because the grammar is fixed-width.
For example, `mov a, 0x100` gives `syntax error: expected comment or new line`, with the column
on the first extra digit. The same goes for `0x10000` and `#0x10`. `jmp cond, :label` is not
range-checked either: it encodes only the low byte, and `CS` supplies the page at run time.

## Instruction set

The encoding below is defined once, in `src/bc8183_isa.py`, which the assembler and the CPU both import (G14).
The module also holds a table of every form listed here; the disassembler that will decode with it is #178.

Condition codes `t` for `jmp`/`jmr`/`jrx`:

| `z` | `c` | `n` | `o` | `nz` | `nc` | `nn` | `no` |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |

They test zero, carry, negative and overflow (or their negation). There is no "always"
condition. Unconditional jumps are written as `xor a` followed by `jmp z, …` or `jmr z, …`.

The encoding column uses nibbles: `r`/`p` is a register number, `t` a condition code,
`ii` an 8-bit immediate and `hhll` a 16-bit immediate.

### Data movement

| Syntax | Encoding | Bytes | Effect |
|---|---|---|---|
| `nop` | `00` | 1 | nothing |
| `mov r, 0xHH` | `1r ii` | 2 | r = imm8 |
| `mov r1, r2` | `2r1 r20` | 2 | r1 = r2 |
| `mov r, #pair` | `3r p0` | 2 | r = mem[pair] |
| `mov #pair, r` | `4p r0` | 2 | mem[pair] = r |
| `psh r` | `8r` | 1 | push r (2-byte tagged frame) |
| `pop r` | `9r` | 1 | pop into r |

### 8-bit ALU (always on `A`)

| Syntax | Encoding | Bytes | Effect |
|---|---|---|---|
| `add 0xHH` / `sub` / `and` / `or` / `xor` / `shl` / `shr` | `5o ii` (o = 0…6) | 2 | A = A op imm |
| `add r` / `sub r` / … / `shr r` | `58 ro` | 2 | A = A op r |
| `not a` | `57` | 1 | A = ~A |
| `inc a` | `5D` | 1 | A = A + 1 |
| `dec a` | `5E` | 1 | A = A − 1 |

Operation numbers `o`: add 0, sub 1, and 2, or 3, xor 4, shl 5, shr 6. `xor a` is the usual
way to clear `A` and set `Z`.

The register form `58 ro` is the encoding of every 8-bit op, including `shl r` and `shr r`, which are `58 r5` and `58 r6`. There is no `5(o|8)` short form for `shl`, `shr` or `not`: that nibble is `inc`, `dec` or EXT. See [E15](specs/memory/design-decisions.md#e15-register-count-shifts-use-the-long-register-form-58-ro).

### 16-bit ALU (bc8183 extension, on `csci` or `dsdi`)

| Syntax | Encoding | Bytes |
|---|---|---|
| `add pair, 0xHHHH` (`sub mul div mod and or xor`) | `5F kk p0 hh ll` | 5 |
| `shl pair, 0xHH` / `shr pair, 0xHH` | `5F kk p0 00 ii` | 5 |
| `add pair, pair2` (same set plus `shl`/`shr`) | `5F k8 pq` | 3 |
| `inc pair` / `dec pair` / `not pair` | `5F kk p0` | 3 |

`kk` is a group nibble followed by an operation nibble:
- **arithmetic group `A`**: add 0, sub 1, mul 2, div 3 (integer), mod 4, inc D, dec E
- **binary group `B`**: and 2, or 3, xor 4, shl 5, shr 6, not 7

The register form sets bit 3 of the operation nibble.

Results are truncated to 16 bits and set `Z/N/C/O` from the 16-bit value. A zero divisor in `div` or
`mod` leaves the destination unchanged and sets `O` = 1 (`Z/N/C` unchanged), and the CPU goes on; see
[01-emulator.md](01-emulator.md).

With destination `af`, the 16-bit input is `A:F` (`F` is the low byte). The result's high byte goes to `A`
and the low byte is dropped: `F` gets the `Z/N/C/O` flags of the op. `af` is accepted, but it is not
meant for 16-bit arithmetic; use `csci` or `dsdi` ([E14](specs/memory/design-decisions.md)).

The register form has an implied second pair. The CPU reads only the first pair and derives the
second one from it, so the second operand must be written as the implied pair:

| First operand | Second operand (the only one accepted) |
|---|---|
| `csci` | `dsdi` |
| `dsdi` | `csci` |

So `add csci, dsdi` and `sub dsdi, csci` are the valid forms. Any other second
operand (`add csci, csci`, `add csci, af`) is an assembler error and no bytes are emitted; see
the `implied pair` row in [Errors](#errors). An unknown pair name in any 16-bit form
(`add csci, sssi`, `inc sssi`) is an error too.

`af` is not a valid operand of any 16-bit ALU instruction. Every 16-bit ALU op with destination
`af` is an assembler error and no bytes are emitted: `add`, `sub`, `mul`, `div`, `mod`, `and`, `or`,
`xor`, `shl`, `shr`, `not`, `inc` and `dec`, in immediate and register forms. The 16-bit result would
overwrite the flags in `F`. Write `inc a` / `dec a` for the 8-bit form, or a pair `csci` or `dsdi`. The
decision is [A8](specs/memory/design-decisions.md#a8-every-16-bit-alu-op-on-af-is-rejected-the-assembler-says-why).
The CPU still executes a hand-encoded 16-bit op on `af` (for example `5F AD 10`, pair nibble 1); only
the assembler refuses to produce it.

### Jumps and calls

| Syntax | Encoding | Bytes | Effect |
|---|---|---|---|
| `jmp t, pair` | `6t 0p` | 2 | if t: PC = pair |
| `jmp t, :label` | `6(t+8) ll` | 2 | if t: PC = `CS:ll`. Only the low byte is encoded, so `CS` must already hold the target's high byte |
| `jmr t, :label` | `7t dd` | 2 | if t: relative jump, 7-bit sign-magnitude |
| `jmr t, r` | `7(t+8) r0` | 2 | if t: relative jump by the value in r |
| `jrx t, :label` | `E1 t0 hh ll` | 4 | if t: relative jump, 15-bit sign-magnitude (bc8183) |
| `jrx t, pair` | `E2 (t+8)p` | 2 | if t: relative jump by the pair value |
| `cal :label` | `A8 hh ll` | 3 | call an absolute address |
| `cal pair` | `A0 p0` | 2 | call the address in the pair |
| `clr :label` | `A9 hh ll` | 3 | relative call, 15-bit sign-magnitude (bc8183) |
| `clr pair` | `A1 pq` | 2 | relative call by the pair value: the pair is csci, dsdi or sssi (see Errors) |
| `ret` | `B0` | 1 | return (see the stack frames section in [01-emulator.md](01-emulator.md)) |
| `kil` | `F0` | 1 | halt the CPU (the emulator then dumps memory) |

The usual long-jump idiom is `.mv csci, :target` then `xor a` then `jmp z, csci`.

### I/O

| Syntax | Encoding | Bytes | Effect |
|---|---|---|---|
| `in r, #0xH` | `C0 rH` | 2 | r = port H |
| `in r, #r2` | `C8 r r2` | 2 | r = port[r2] |
| `out #r, r2` | `D8 r r2` | 2 | port[r] = r2 |
| `out #r, 0xHH` | `Dr HH` | 2 | port[r] = HH. `r` must be `a`, `ci` or `di` (the 3-bit field can name only those; see [Errors](#errors)). No flags change. See [A11](specs/memory/design-decisions.md#a11-out-r-imm-encodes-dr-hh-the-port-register-must-be-a-ci-or-di) |

## Example

```asm
                .org 0x0000
start:          .mv dsdi, :msg
                mov ci, 0x01        ; printer port
loop:           mov a, #dsdi
                jmr z, :done
                out #ci, a
                inc dsdi
                xor a
                jmr z, :loop
done:           kil
msg:            .db 'Hello!', 0x0a, 0x0d, 0x00
```

## Known quirks

- `CLC_A_IMM` has a leftover branch for 16-bit opcodes that the grammar never reaches.
