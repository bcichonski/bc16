# bc81asmc: assembler for the bc8183 CPU

`src/bc81asmc/` is a two-pass assembler written with the
[parsy](https://pypi.org/project/parsy/) parser-combinator library. The current version is
**v1.3 (240914)**, for the bc8183 CPU described in [01-emulator.md](01-emulator.md).

| File | Contents |
|---|---|
| `bc81asmc.py` | CLI, the two passes (emit + label fix-ups), `.btap`, `.lst` and `.map` writers |
| `bc81asmc_grammar.py` | the parsy grammar (the real syntax reference) |
| `bc81asmc_ast.py` | one dataclass per instruction/directive, each with its own `emit()`; opcodes and encodings come from `src/bc8183_isa.py` |
| `bc81asmc_pre.py` | the pre-pass: `#include`, `#define` and `#link` lines, the header reader and the define table (see [`#include`, `#define` and `#link`](#include-define-and-link)) |
| `bc81asmc_diag.py` | error records (`Diagnostic`, `AssemblerError`), the `file:line:col` formatter, parsy `ParseError` conversion |
| `bc81asmc_obj.py` | object mode: `--obj` turns one parsed program into a BOF v1 module (see [Object files](#object-files---obj)); the BOF writer, reader and dump are in the shared `src/bof.py` |
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
bc81asmc --obj path/to/file.basm                  # write path/to/file.o (BOF v1) instead of the .btap
bc81asmc --dump path/to/file.o                    # print the records of an object file
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
- `--obj` writes a BOF v1 object file `path/to/file.o` **instead of** the `.btap` (no `.btap` is written). See
  [Object files](#object-files---obj). `--obj` cannot be combined with `--lst` or `--map` (usage error, exit status 2).
- `--dump FILE.o` reads an object file and prints one line per record on stdout (exit `0`). It takes the `.o` as
  the one input file and cannot be combined with `--obj`, `--lst` or `--map` (usage error, exit status 2). A file
  that is not valid BOF v1 gives one error line on stderr and exit status `1`. See [the dump format](#the-dump-format).
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
| `.db v, v, …` | emit bytes. Each `v` is `0xHH`, `'string'` (raw chars, add `0x00` yourself), `:label` (2 bytes, big-endian address), or `hi(:label)` / `lo(:label)` (1 byte: the high / low byte of the label's address; blanks inside the parentheses are allowed). A `.def` name works as a label, forward and backward, and an unknown label is the same positioned `undefined label` error as for `:label` |
| `.mv pair, :label` | load a 16-bit label address into a pair. Expands to `mov hi,imm8` + `mov lo,imm8` (4 bytes) |
| `.def name, 0xHHHH` | define a constant, used like a label (`:name`). Good for fixed addresses such as `bdos_bootaddr` |
| `.global name` | export `name`, a label or a `.def` constant of this module, to the linker. Only with `--obj`: without it the line emits nothing (a label on the line gets the current address, like on `.def`). See [Object files](#object-files---obj) |
| `.extern name` | import `name`, a label that another module defines. Only with `--obj`; without it the line emits nothing, so a name that is not defined in the file is the usual `undefined label` error |
| `.sect name` | start the section `name` (code and labels after it belong to it). Only with `--obj`; without it a no-op, so a source with `.sect` lines still assembles flat, in file order |
| `.assert :a OP :b` or `.assert :a OP 0xHHHH` (also `0xHH`) | check a comparison at build time. `OP` is one of `=`, `!=`, `<`, `<=`, `>`, `>=`; an operand is a `:name` (label or `.def`) or a literal. Emits no bytes; a label on the line gets the current address. A failure stops the build (see [Errors](#errors)) |

### `#include`, `#define` and `#link`

Three line kinds are handled by a pre-pass (`bc81asmc_pre.py`) before the parser runs:

```
#include NAME          ; the B header NAME (see below)
#define NAME value     ; NAME stands for value
#link NAME             ; the module NAME this file links to (recorded for --obj)
```

A directive line is a line whose first non-blank text is `#include`, `#define` or `#link`, followed by a blank or the
end of the line. Any other `#word` at the start of a line is still a syntax error.

- A directive line emits nothing and has no address. It is listed in the `.lst` with no address, and it is not in the
  `.map`. Line numbers do not change, so every diagnostic keeps its position in the main file.
- An included file is a **B header**. Its lines may be blank, `//` comments, `#define`, `#include`, `#link`, or
  one-line prototypes (`byte` or `word`, a name, a parenthesised parameter list), which are skipped. Any other line is
  an error, reported in the header's own file at its own line. A header contributes no code and no listing rows.
  The real headers are the `src/bdos/*.h` files of the shared B libraries (for example `#include bdioh.h` gives the
  bdio call numbers and error codes).
- The include path is relative to the directory of the **main** source file, at every level of nesting, and there is
  no depth limit. A file that is already open in the include chain is an `include cycle` error. Including the same
  header twice in a row is allowed.
- A `#define` takes effect from the next line in reading order, as in B. A name used before its define is
  `undefined name`. A define in a header takes effect from the line after the `#include` line.
- A defined name may stand wherever an operand takes a number. The name is replaced by its value with the width of
  the literal it stands for:
  - 4 bits: the `in` port (`in r, #NAME`);
  - 8 bits: 8-bit immediates (`mov a, NAME`), the count of `shl` and `shr` on a pair, and `.db` items;
  - 16 bits: 16-bit immediates (`add csci, NAME`), `.org`, the value of `.def`, and the literal of `.assert`.
- A value is one B number: decimal (`0` or a number without a leading zero), hex `0x` followed by one or more hex
  digits (any count, either case), or a character in single quotes (`'A'`). The size comes from the value, not from
  the digit count: `0x0f1` is 0xf1 and fits 8 bits. A value that is not a single number, or does not fit the operand,
  is an error at each use. Values are checked only where they are used, so a header may hold defines that the
  assembly never uses.
- Only whole identifiers are replaced. `BDIO` does not change `BDIO_FCAT`. Labels and `:references` are never
  replaced, even `:BDIO`, and nothing inside `'strings'` or `;` comments changes.
- Register and pair names (`a`, `ci`, `csci`, `af`, ...) cannot be defined: `'ci' is a register name and cannot be #defined`.
- Redefining a name with the same value is silent (a header included twice). With a different value it is a warning,
  and the new value applies from the next line.
- `#link NAME` is recorded in the order first seen, without duplicates. It changes no output until `--obj` (#115).

For example, a header and a `.basm` that uses it:

```
// device.h
#define LED 0x2a
#define BASE 0x1234
#link bdioh
```

```
#include device.h
.org BASE
mov a, LED
.db LED, 0xff
kil
```

The listing is:

```
                   #include device.h
1234               .org BASE
1234  11 2a        mov a, LED
1236  2a ff        .db LED, 0xff
1238  f0           kil
```

so the image is `11 2a 2a ff f0`, at 0x1234.

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

| pre-pass: malformed directive | `malformed #define (expected: #define NAME value)`, `malformed #include (expected: #include NAME)`, `malformed #link (expected: #link NAME)` | the `#` of the directive line | pre-pass errors are all reported, then the run stops before parsing, like a syntax error |
| pre-pass: register name | `'ci' is a register name and cannot be #defined` | the name in the `#define` line | see the register rule above |
| pre-pass: include cycle | `include cycle: 'device.h' includes itself` | the file name in the `#include` line | a file already open in the include chain is not read again |
| pre-pass: unreadable include | `cannot read include file 'device.h': No such file or directory` | the file name in the `#include` line | the reason is the OS error text |
| pre-pass: header line | `unexpected line in a header (only #define, #include, #link and prototypes are allowed)` | the first non-blank character of the line, in the header | the block names the header file and prints the header's line |
| undefined name | `undefined name 'NAME'` | the name in the operand | every use is reported; the line contributes no bytes and assembly goes on |
| name not a number | `'NAME' is not a number: 'value'` | the name in the operand | the value is not one B number literal |
| name too wide | `value of 'NAME' (0xNNNN) does not fit in N bits` | the name in the operand | N is 4, 8 or 16 (the width of the operand); the line contributes no bytes |
| redefinition (warning) | `'NAME' redefined: 'new' replaces 'old'` | the name in the redefining `#define` | a warning: the run does not fail and the new value applies from the next line |
| `--obj`: `.org` order | `.org must come before .sect, .global and .extern with --obj (first one at line n)` | the start of the `.org` line | |
| `--obj`: `.sect` in an `.org` file | `.sect is not allowed in an .org file with --obj (the file is one absolute section)` | the `.sect` line | |
| `--obj`: duplicate section | `duplicate section 'x' (first started at line n)` | the section name | |
| `--obj`: `.global` never defined | `'.global x' is never defined` | the name in the `.global` line | neither a label nor a `.def` has that name |
| `--obj`: `.extern` defined | `'x' is declared .extern (line n) and must not be defined in this module` | the name in the definition | a label or a `.def` |
| `--obj`: `.global` and `.extern` | `'x' is declared both .global and .extern (other declaration at line n)` | the name in the second declaration | the name keeps its first class |
| `--obj`: declaration too late | `'.global x' must come before the first use or definition of 'x' (line n)`, the same for `.extern` | the name in the declaration | see [Declarations come first](#symbol-classes) |
| `--obj`: `.def` too late | `'x' is used before its .def (line n); with --obj a .def must come first` | the `:` of the reference | |
| `--obj`: relative jump to a constant | `relative jump to the constant ':x' needs an .org file with --obj` | the `:` of the reference | a `jmr`, `jrx` or `clr` to a local `.def` in a relocatable module |
| `--obj`: `.assert` (warning) | `.assert not checked with --obj: ':x' is relocatable` | the `:` of the operand | a warning: exit status `0`, the `.o` is written |

Warnings are printed to stderr as `file:line:col: warning: <message>` blocks in the same three-line format. They
do not fail the run and do not suppress the output. A diagnostic in a header names the header file (its path as
resolved from the main file's directory) and prints that file's line, not the main file's.

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

## Object files (`--obj`)

`bc81asmc --obj file.basm` writes a relocatable object file `file.o` (beside the source) **instead of** the `.btap`.
The format is BOF v1, a stream of `tag, length, content` records, frozen in design decision
[G15](specs/memory/design-decisions.md#g15-object-files-are-bof-v1-a-record-stream-whose-layout-is-frozen). The worked
byte-exact example `HELLO.O` is in [the design page](analysis/07-self-hosted-compiler.md#object-file-format); the
assembler produces exactly those 99 bytes from the matching source. The decisions behind this mode are in
[A14](specs/memory/design-decisions.md#a14---obj-writes-bof-v1-object-files-names-are-classified-at-first-sight-declarations-come-first). The records are written by `src/bof.py`, the module that `blink.py` (#117)
and `bc --obj` (#121) share. Any error means no `.o` is written (exit status `1`). Without `--obj` nothing changes: every
source assembles to the same `.btap` as before.

### Names and sections

- The **module name** in the header is the source file stem in upper case (`hello.basm` gives `HELLO`). A `NEED`
  record (`de`) is written for each `#link` occurrence, with the name in upper case (`#link stdio` gives `STDIO`),
  repeats included, at the line where the `#link` stands. A `#link` inside a header belongs to the `#include` line.
  Symbol and section names keep their case.
- An **`.org` file is one `SECTABS` section** at the `.org` address, named after the module. `.sect` in an `.org`
  file is an error.
- Any other file is made of **`SECTSTAT` sections**. Each `.sect name` starts one. Code, data and labels before the
  first `.sect` go into an implicit section named after the module (a file that starts with `.sect` has none). A
  section name may be used once per module. A section may be empty. Every section starts at offset 0, and a label on
  a `.sect` line belongs to the new section.
- `.org` keeps its flat rules (once, before any code or label). With `--obj` it also has to come before any `.sect`,
  `.global` and `.extern`.

### Symbol classes

Every name is in exactly one class, fixed by the first time the assembler sees it.

| Class | How it is made | Record |
|---|---|---|
| global label | `.global x`, and `x:` defined in this module | `GLOBL` (`91`) at the definition, with the offset in its section |
| external | `.extern x`; it must not be defined here | `EXTRN` (`ee`) at the first use |
| exported constant | `.global x` and `.def x, value` | `ABS` (`ab`) at the `.def` line |
| local constant | `.def` without `.global` | none; every use is resolved in place by its value, like in a flat build |
| local label | any other label | `LABEL` (`1a`) at the definition, with its number |

- Symbol numbers (for `EXTRN`) count from 0 in order of first use. A call to a global of the same module also goes
  through an `EXTRN`.
- Local labels are numbered per module (0, 1, 2, ...) in order of **first appearance**, as a reference or as a
  definition, whichever comes first. A fix entry names a local label as `0x8000 | n`, a symbol as `k`.
- **Declarations come first.** `.global x` and `.extern x` have to stand before any use or definition of `x`, and a
  `.def` before its first use. Declaring a name twice the same way is harmless; `.global` and `.extern` on one name is an
  error. *Why:* BASM, the self-hosted assembler (phase 2), reads the source once. At a forward reference to a name it has
  not seen it must already write the target, and no record can turn local label `n` into a global or into a `.def`
  value later. With the declarations first, BASM decides a name's class at first sight and writes the same bytes as
  `bc81asmc --obj`. `#define` already works this way. Every `.def` in the repo stands before its uses.

### References and fix kinds

With `--obj` every reference to a label (global, external or local) becomes a fix entry. Nothing is patched in place
except the value of a local `.def`.

| Source form | Placeholder bytes | Fix | Entry offset |
|---|---|---|---|
| `cal :x`, `.db :x` | 2 bytes: the target, big-endian | `f1` `ABS16` | the high byte |
| `jrx t, :x`, `clr :x` | 2 bytes: the target, big-endian | `f2` `REL15` | the first placeholder byte |
| `.db hi(:x)` | `00` | `f8` `HI8` | the byte |
| `.db lo(:x)`, `jmp t, :x` | `00` | `f9` `LO8` | the byte |
| `jmr t, :x` | `00` | `fa` `REL7` | the byte |
| `.mv pair, :x` | `00` and `00` (the `hi` byte at +1, the `lo` byte at +3 of the 4 bytes) | `fb` `HILO` | the `hi` byte (the `lo` byte is at offset + 2) |

The 16-bit placeholders hold the target as the entry names it (`k` or `0x8000 | n`). The entry offset is relative to
the start of the `CODE` record. A relative jump to a **local `.def`** is not allowed in a relocatable module
(the constant has no address to be relative to); it works in an `.org` file, where it is resolved in place.

**Arithmetic for the linker.** Let `p` be the address of the placeholder (its first byte) and `t` the target address,
both after linking. `REL7` and `REL15` use the arithmetic of a flat build (sign-magnitude, [G5](specs/memory/design-decisions.md)):

- `REL7`: `d = t - p + 1`. It must be in `-127..127`. A negative `d` is stored as `(-d) | 0x80`. One byte.
- `REL15`: `d = t - p - 1`. It must be in `-32767..32767`. A negative `d` is stored as `(-d) | 0x8000`. Two bytes,
  high byte first, at `p` and `p + 1`.
- `ABS16` stores `t` big-endian; `HI8` the high byte of `t`; `LO8` the low byte; `HILO` the high byte at `p` and the
  low byte at `p + 2`.

The assembler does not check the range of a relative jump in an object (the linker does).

### Record order and flushing

The records follow the source lines in order. For each line:

1. a `NEED` for each `#link` that belongs to the line;
2. the section: `SECTSTAT` for a `.sect`, or for the implicit first section; `SECTABS` for an `.org` file (address and
   module name), written at the first line that needs a section;
3. `GLOBL` or `LABEL` for the label defined on the line;
4. `ABS` for a `.global` `.def`;
5. `EXTRN` for each global or external name first used on the line, in reference order;
6. the line's bytes, into the open `CODE` record, with their fix entries.

The open `CODE` record is written when it holds 255 bytes, before a line whose bytes would not fit whole, and before
every other record (`NEED`, `ADDR`, `ABS`, `LABEL`, `GLOBL`, `EXTRN`, `SECTSTAT`, `SECTABS`, `END`). A line longer
than 255 bytes (only a long `.db`) starts a new record and is split at 255-byte boundaries, moving a split back so that
a 2-byte `.db :x` item is never cut. The fix records of a `CODE` record follow it directly, in the order `f1 f2 f8 f9 fa
fb`, offsets ascending, empty lists not written. A list that does not fit one record continues in another record of the
same tag (85 three-byte entries or 255 one-byte entries at most). The output is deterministic: the same source gives
the same bytes.

`ad` (`ADDR`) records, for `#code`, `#heap` and `#codelimit`, are **not** written by the assembler yet: there is no
`.basm` syntax for them. `src/bof.py` can write and read them; `bc --obj` (#121), the first producer, adds the source
form it needs.

### `.assert` and `.org` files

- In an `.org` file every address is known, so `.assert` is evaluated as in a flat build (`bdos/boot.basm` assembles
  with `--obj` into one `SECTABS` section at `0x0e00`, its asserts checked).
- In a relocatable module an `.assert` that names a label cannot be evaluated (the address exists only after
  linking). It is skipped with a warning, `.assert not checked with --obj: ':x' is relocatable`; the `.o` is still
  written and the exit status is `0`. An `.assert` of `.def`s and literals is evaluated.

### The dump format

`bc81asmc --dump file.o` prints one line per record: the file offset (hex), the tag, the record name and the content.
Names are text, `GLOBL`, `LABEL` and `CODE` show their offset in the section (`@n`), `CODE` bytes are in hex, fix
entries show the offset and the target as `symbol k 'name'` or `label n`. Example (the `HELLO.O` source of doc 07):

```
0000  b0 HEADER   version 01 module 'HELLO'
0008  de NEED     'STDIO'
000f  55 SECTSTAT 'F_main'
0017  91 GLOBL    'F_main' @0000
001f  c0 CODE     @0000 6 bytes: 18 00 14 00 11 00
0027  fb HILO     offset 01 -> label 0
002c  ee EXTRN    symbol 0 'stackvar8st16'
003b  c0 CODE     @0006 3 bytes: a8 00 00
0040  f1 ABS16    offset 01 -> symbol 0 'stackvar8st16'
0043  ee EXTRN    symbol 1 'F_puts'
004b  c0 CODE     @0009 8 bytes: a8 00 01 18 00 14 00 b0
0055  f1 ABS16    offset 01 -> symbol 1 'F_puts'
0058  1a LABEL    label 0 @0011
005c  c0 CODE     @0011 3 bytes: 68 69 00
0061  ed END
```

A file that is not BOF v1 (wrong first tag, version other than `01`, a truncated record, an unknown tag, `END` not last)
gives one line on stderr, `FILE: error: at byte offset N: <message>`, and exit status `1`. A file that cannot be read
gives `FILE: error: cannot read the file: <reason>`, also exit status `1`.

## Known quirks

- `CLC_A_IMM` has a leftover branch for 16-bit opcodes that the grammar never reaches.
