# A B compiler running on the BC64: feasibility and design (analysis, 2026-11-09, updated 2026-11-13)

Roadmap item 9 is "compiler running on the BC64". This page checks how realistic that is on
the machine as it is today (bcOS 1.2, bdos 1.1, 64 KB RAM, 128 KB discs), and proposes a
design: a disc-based compiler that writes object files, a separate linker that writes the
executable, and `#include`. Every number here was measured on the `bc64` branch on
2026-11-09; the [appendix](#appendix-measurements) says how.

Related pages: [03-compiler.md](03-compiler.md) (host compiler analysis),
[05-bdos.md](05-bdos.md), and the references [../03-compiler.md](../03-compiler.md) and
[../05-bdos.md](../05-bdos.md).

## Short answers

| Question | Answer |
|---|---|
| Can a simple B compiler fit in user memory? | **Yes, as a 3-pass compiler** (decided: n passes are fine, so the compiler is split to stay well below the 32 KB file limit). As one program it would be about 29 KB of code plus 8–12 KB of data: too close to both limits. Split into lexer → parser → code generator, each pass is about 8–15 KB of code and needs at most about 5 KB of data, **even with today's code generator and no dead-code elimination**. |
| Is `#include` feasible? | **Yes.** bdos has 3 buffered read handles, so the main file plus two nested levels can be open at once. The real problem is that today's `#include` pastes whole library *bodies*. On the machine that means compiling about 6 KB of library code and about 200 `#define`s for every program. Split them: headers (`.h`, declarations and `#define`s) are included as text; bodies are compiled once to `.o` files and linked. |
| Can programs be longer than user memory? | **Not today, and not by much without work.** The catalog stores a file's length in one byte, so a `.PRG` is at most 255 sectors (32,640 bytes): *less* than user memory. Plan A keeps the file system as it is: bigger programs use overlays (the linker writes extra files, each under 32 KB, that the runtime loads into a fixed area) or chaining (one program asks the shell to run the next). Both work with today's file API plus one small bdos addition. Plan B, only if plan A isn't enough, is a 2-byte file length in catalog v2. |
| What about linking? | **It is the easiest part, and the most useful.** A two-pass linker over object files needs a few KB of tables. It can also drop unused functions, which is roadmap item 5a ("drop unused code", #16), and that shrinks every program on the disc, not only the compiled ones. Build it on the host first (Python), then port it to B. |
| Does the "reads lines, emits tokens to disc" model work? | **Yes, it's plan A.** bdos has only **one write handle**, so the rule is: each pass reads one intermediate file and writes exactly one. The cost is disc space for intermediate files. Deleted space isn't reused today, so a `pack` utility (or reuse of freed space) becomes part of the plan; see [disc prerequisites](#disc-and-bdos-prerequisites). |
| Should the compiler write assembly text, like the host one? | **No.** `texted.basm` is 208 KB and `bdos.basm` 256 KB, both bigger than a whole disc (128 KB). The compiler writes machine code for its own templates directly: it uses only about 30 fixed instruction templates. An assembler still runs on the machine, as a separate tool (next row). |
| How is assembly code handled, and is there an assembler on the BC64? | **Assembly lives in its own modules** (decided 2026-11-11). `.basm` → assembler → `.o` and `.b` → compiler → `.o` write the same object format, and the linker joins them. Assembly routines follow the B calling convention, so B calls them like B functions, and they can call B. The compiler keeps only a **raw-byte `asm`** statement for a few inline instructions (`asm 0xa8, :poke16;`), so it contains no assembler. `BASM` runs on the BC64 as its own tool, **after** the compiler. See [mixing B and assembly](#mixing-b-and-assembly) and [the assembler](#the-assembler-basm). |

**Verdict:** a B compiler and linker on the BC64 are feasible on today's machine, without
hardware or file-system changes, as a 3-pass compiler, a 2-pass linker and an assembler. The order that makes it work is: fix
the disc allocation bug → object format, linker and the move of library assembly into
`.basm` modules on the host → linker on the BC64 → compiler on the BC64 → assembler on the
BC64. The
[phases](#phased-plan) below have exit criteria for each step. Self-hosting (the compiler
compiling its own source on the BC64) is a later, optional step.

## What the machine gives us today

| Resource | Value | Consequence |
|---|---|---|
| User memory | `0x6000–0xfffe` = 40,958 bytes (the shell prints `9FF5 bytes free`) | the CPU stack (from `0xfffe` down) and the B variable stack (after the program image, up) share it with the program |
| Largest file | 255 sectors × 128 B = 32,640 bytes (1-byte length in the catalog) | a `.PRG` can never fill user memory; the same limit applies to sources and objects |
| Disc | 64 × 16 × 128 B = 128 KB, 1,024 sectors | the system disc uses 834; **190 sectors (23.75 KB) are free** |
| File handles | 1 write handle, 3 read handles (`BDIO_FDESCRIPTOR_*_MAX`) | each program writes one file at a time; at most 3 inputs open at once |
| Allocation | contiguous files; new data always goes after the last used sector; no seek; no rewrite | outputs are written strictly sequentially, so there is no back-patching in a file |
| Program start | the shell loads `NAME.PRG` to `0x6000` and `cal`s it; the program `ret`s to the shell | "loading a program destroys the previous one" is already how it works |
| Running another program from a program | not possible: `bdio_execute` is shell-only, and it `cal`s the new program, which would return into overwritten code | chaining needs a new bdos call (see [chaining](#chaining)) |
| Emulator speed | about 130k instructions/s | a compile is seconds to a minute per file; see [speed](#speed) |
| Inline `asm` in B sources | 347 `asm "…"` lines in 41 functions, **all** in libraries and bdos (`stdio.b` 135, `stdmem.b` 72, `bdio.b` 48, `strings.b` 43, `std.b` 31, `bdosh.b` 9, `bdos.b` 9); none in the apps (`texted`, `ls`, `cp`, …) | 30 of the 41 functions are assembly routines with a B header and move to `.basm` modules as they are; 11 mix assembly with B control flow and are rewritten (see [moving today's `asm`](#moving-todays-asm)) |

### Code density of the current compiler

| Program | Size | Notes |
|---|---|---|
| empty `main` | 560 B | the runtime appended to every program |
| empty `main` + `std`, `bdosh`, `stdmem`, `strings`, `bdostools` | 5,981 B | the libraries `texted` includes, with no dead-code elimination |
| `texted` (702 lines) | 14,310 B | 8,329 B of its own code: **about 12 bytes per source line**, comments and blank lines included |
| `BDOS.SYS` (`bdos.b` + `bdio.b` + libraries) | 17,403 B | 72 functions, 181 jump labels, 27 string labels |

12 bytes per line is the number used for every estimate below.

## The proposed model, checked point by point

**1. "`.b` text files on the disc, created with texted."** Feasible, but texted files are not
plain text. A texted file is a list of records, `<decimal line number> <text>` ending in
`0x13`, then a `0x00` and zero padding (see `docs/05-bdos.md`, TextEd file format). The
compiler's reader must parse that format. This is an advantage: errors can be reported
with **texted's own line numbers**, so `p 120 130` in texted shows the failing line. The
reader should also accept plain lines ending in `0x0a`, `0x0d` or `0x13`, for files put on
the disc from the host. The host needs a matching `ftool importtext` that writes a text
file in texted format.

texted keeps the whole file in its heap (`#heap 0xa000`, lines of at most 80 characters),
so one source file is limited to roughly 15–20 KB of text. Bigger programs are split into several files and compiled separately.
Separate compilation is needed anyway.

**2. "One or more files, with `#include` semantics."** Feasible; see
[`#include` on the machine](#include-on-the-machine). The change is to include
*declarations*, not *code*.

**3. "The compiler reads some lines, emits tokens, stores metadata into `.o` files."**
Agreed. It's the plan: a 3-pass compiler, where each pass is its own program, reads one
file and writes one file. See [the compiler](#the-compiler-bcc-bcc2-bcc3). Two
constraints shape it:
- **One write handle.** Each pass writes exactly one file, so all the "metadata" a later
  pass needs must travel *inside* that file. For example, identifier names go into the
  token stream the first time they appear, not into a separate name file.
- **Disc space.** Intermediate files cost space while the compile runs. Freed space isn't
  reused today, so a `pack` utility is part of phase 0.

**4. "A separate linker assembles the full executable straight on the disc."** Yes. Use a
two-pass design: read all objects once for symbols, then read them again and stream the
patched code to the single write handle. See [linking](#linking).

**5. "Running the program loads it from the disc and destroys what was running."** That
is exactly what the shell does today. Two things are missing for comfortable use:
- **chaining**, so `bc hello` can run the compiler, then the linker, then the program,
  without typing three commands;
- **no-return programs**: a program can't start another program itself.

See [chaining](#chaining).

**6. "Follow the current compiler, or something even cruder."** Agreed for the
*language*. The compiler on the BC64 should accept the **same language as the host `bc`**,
quirks included (precedence, `=` for equality, unary scope). Then the same sources and
libraries work in both, and the host compiler is a test oracle. The *output* should not
follow the host compiler: assembly text is impossible on a 128 KB disc (see the short
answers).

## Proposed architecture

```
 drive A: development system disc            drive B: work disc
 ┌──────────────────────────────────┐        ┌──────────────────────────────┐
 │ BDOS.SYS, LS, CP, RM, TEXTED     │        │ HELLO.B   (texted)           │
 │ BCC.PRG     lexer                │──────► │ HELLO.TOK (BCC, temporary)   │
 │ BCC2.PRG    parser               │        │ HELLO.IR  (BCC2, temporary)  │
 │ BCC3.PRG    code generator       │        │ HELLO.O   (BCC3 output)      │
 │ BASM.PRG    assembler            │        │ HELLO.PRG (BLINK output)     │
 │ BLINK.PRG   linker               │        │ UTIL.B UTIL.H UTIL.O  (more) │
 │ RUNTIME.O STD.O STDIO.O STRINGS.O│        │ FAST.BAS → FAST.O  (BASM)    │
 │ STDMEM.O BDOSH.O                 │        └──────────────────────────────┘
 │ STD.H STDIO.H BDIOH.H …          │
 └──────────────────────────────────┘

 A>b:
 B>texted                 (write HELLO.B)
 B>bcc hello              HELLO.B (+ #include *.H) ──► HELLO.TOK
 B>bcc2 hello             HELLO.TOK ──► HELLO.IR
 B>bcc3 hello             HELLO.IR  ──► HELLO.O     (deletes .TOK and .IR)
 B>blink hello            HELLO.O + A:RUNTIME.O + A:STD.O … ──► HELLO.PRG
 B>hello                  shell loads HELLO.PRG to 0x6000 and runs it
```

With `bdio_chain` (phase 5), `bcc hello` is the only command: each pass chains to the next
when it succeeds.

- The tools live on drive A and the work on drive B. The system disc has 190 free sectors,
  which isn't enough for the tools *and* their output. Repeated compiles also eat space,
  because deleted space is not reused (see [disc prerequisites](#disc-and-bdos-prerequisites)).
- The shell finds programs only on the active drive. Either add a search path (active
  drive, then A), or work from A with `b:` prefixes on the file names, which every
  utility already accepts. A search path is a small change in `bdos.b` and much nicer to use.

### Components

| Component | Written in | Runs on | Role |
|---|---|---|---|
| object format "BOF" | – | – | the contract between all the tools below; see [object format](#object-file-format) |
| `bc81asmc --obj` | Python | host | assembles `.basm` to `.o`; new directives `.global`, `.extern` and `.sect`; reads `#include`d `.h` files for their `#define`s |
| `bc --obj` | Python | host | compiles one `.b` to `.o` (through `.basm` and the assembler); a declaration without a body becomes an external reference; functions get stable `F_name` symbols; raw-byte `asm` |
| `blink.py` | Python | host | the reference linker: the same algorithm as BLINK, used to test the format, the libraries and dead-code elimination |
| `RUNTIME.O`, `STD.O`, `STDIO.O`, `STRINGS.O`, `STDMEM.O`, `BDOSH.O`, `BDOSTOOLS.O` | B for the B parts, `.basm` modules for the assembly parts (`runtime.basm` from `bc_stdlib.py`, `printf` and the `peek`/`poke`/`put*` routines, …) | – | the libraries: built on the host first. On the BC64 the B parts can be rebuilt from phase 3 (compiler), the assembly parts from phase 4 (BASM) |
| `*.H` | B | – | declarations (`#define`s and prototypes) split out of the library sources; read by the compiler and by the assembler |
| `BLINK.PRG` | B, built on the host | BC64 | the linker |
| `BASM.PRG` | B, built on the host | BC64 | the assembler: one assembly file in (texted format, extension `.BAS` because names are 8+3), one `.o` out. Not needed to compile B programs |
| shared modules: `RDR` (texted-format reader), `PRE` (`#include`/`#define`), `BOFW` (object writer) | B | BC64 | written once for the compiler and linked into BASM too. The instruction encoder `ENC` belongs to BASM alone |
| `BCC.PRG`, `BCC2.PRG`, `BCC3.PRG` | B, built on the host | BC64 | the compiler, in three passes: `.b` → `.TOK` → `.IR` → `.o`. The last pass writes machine code for its templates directly and copies raw `asm` bytes. It contains no assembler |
| `ftool importtext` / `exporttext` | Python | host | move text files between the host and texted format on a `.bdd` |

### The compiler (BCC, BCC2, BCC3)

Three passes, each its own `.PRG`, each reading one file and writing one file. The first
pass is named `BCC`, not `BCC1`: it's the command the user types, and with chaining
(phase 5) it starts the other two.

| Pass | Reads | Writes | Holds in memory | Does |
|---|---|---|---|---|
| **BCC** lexer | `NAME.B` + `#include`d `.H` files (texted format) | `NAME.TOK` | `#define` table, include stack, one line | parses texted records, handles `#include`/`#define`/`//`, turns the text into tokens |
| **BCC2** parser | `NAME.TOK` | `NAME.IR` | function table (names, parameter types), locals of the current function | recursive-descent parsing, scopes and frame offsets, checks declarations, writes stack-machine IR |
| **BCC3** code generator | `NAME.IR` | `NAME.O` | external symbol list, local label counter | expands each IR operation into the host compiler's code template, copies raw `asm` bytes and their fixups, writes the object records |

#### `.TOK`: token stream (BCC → BCC2)

The source with everything the parser doesn't need removed: no comments, no blanks, no
`#define`s, no `#include` lines, no texted record framing. What is left is one byte per
token, and a few tokens with a payload. The file starts with `'T'` and a version byte.

| Byte | Token | Payload | Notes |
|---|---|---|---|
| `00` | `EOF` | – | end of the stream |
| `01` | `LINE` | `n(2)` | the tokens that follow are from texted line n. Written before the first token of every line that has tokens |
| `02` | `FILE` | `len name` | the tokens that follow are from this file. Written at the start, when an `#include` is entered and when it ends; always followed by a `LINE` |
| `03` | `LINK` | `len name` | a `#link name` line |
| `08` | `ADDR` | `kind(1) value(2)` | a `#code` (kind 0), `#heap` (1) or `#codelimit` (2) line |
| `04` | `NEWID` | `len text` | an identifier seen for the first time. It gets the next number (0, 1, 2…) and counts as a use |
| `05` | `IDW` | `n(2)` | identifier number n, for n ≥ 128 |
| `06` | `NUM` | `value(2)` | a number: decimal, hex or `'c'`. All constants are 16-bit in B, so the spelling isn't kept |
| `07` | `STR` | `len bytes` | a string literal, without the quotes (B strings have no escapes) |
| `10`–`16` | keywords | – | `word` `byte` `if` `else` `while` `return` `asm` |
| `20`–`28` | punctuation | – | `(` `)` `{` `}` `,` `;` `:` `<-` `***` |
| `30`–`32` | unary operators | – | `#` `!` `~` |
| `40`–`4f` | binary operators | – | `*` `/` `%` `+` `-` `&` `\|` `<<` `>>` `<=` `>=` `>` `<` `&&` `\|\|` `=` `!=` |
| `80`–`ff` | `ID` | – | identifier number (byte − `0x80`): the first 128 names take one byte per use |

- **Identifiers are interned inside the stream.** BCC2 rebuilds the same name table from
  the `NEWID` tokens as it reads. This puts the name table into the one file BCC is
  allowed to write. Function names, parameters and locals are all just identifiers here:
  BCC doesn't know which is which.
- **`#define` values are already replaced.** BCC2 never sees a defined name, so those names
  get no `NEWID`. The replacement is lexed like source text, so it can be any token.
- **Prototypes from headers are in the stream** as ordinary tokens, with `FILE` and `LINE`
  markers, so BCC2 reports an error in a header by its own file name and line.
- **Raw `asm` needs no token of its own:** the keyword, numbers, `:` + identifier, `hi` /
  `lo` (ordinary identifiers) and commas.
- **`#code`, `#heap` and `#codelimit` are passed through** as `ADDR` tokens, like `#link`.
  They describe the finished program, so only the linker can apply them.
- **BCC's own errors:** a character that starts no token, an unterminated string or
  `'c'`, an `#include` that isn't found or is nested too deep, a full `#define` table.

`word main() { puts("hi"); return 0; }` on texted line 10 of `HELLO.B`:

```
54 01                   'T', version 1
02 07 'HELLO.B'         FILE
01 00 0a                LINE 10
10                      word
04 04 'main'            NEWID: identifier 0
20 21 22                ( ) {
04 04 'puts'            NEWID: identifier 1
20 07 02 'hi' 21 25     ( "hi" ) ;
15 06 00 00 25          return 0 ;
23                      }
00                      EOF
```

That is 44 bytes against 41 for the texted record: a one-line file gains nothing, because
of the header, the file name and two new names. A later `puts` in the same file is the
single byte `81`. Expected size for real sources: about half of the source text, because
comments, indentation and repeated names go away.

#### `.IR`: stack-machine IR (BCC2 → BCC3)

The program after parsing: no names of variables, no types, no syntax. What is left is a
list of operations, **each of which is exactly one code template of the host compiler**
(`bc_ast.py`). BCC2 makes every decision; BCC3 only looks up a template, fills in a number
and writes bytes. The file starts with `'I'` and a version byte, then one byte per
operation plus a fixed payload.

| Byte | Operation | Payload | Code it becomes (host template) |
|---|---|---|---|
| `00` | `END` | – | end of the file |
| `01` | `SYM` | `len name` | no code. Declares B function symbol number k (0, 1, 2… in order): the object symbol `F_name`. Written when a function is first called or defined, so an unused prototype costs nothing |
| `02` | `SYMA` | `len name` | no code. Declares an assembly label used by raw `asm` (`:poke16`), numbered in the same sequence |
| `03` | `LINK` | `len name` | no code: becomes a `de` record |
| `04` | `ADDR` | `kind(1) value(2)` | no code: becomes an `ad` record |
| `10` | `FUNC` | `sym(2)` | starts a section with its global symbol; `nop` |
| `11` | `ENDF` | – | `ret`, then the function's strings |
| `12` | `RET` | – | `ret` |
| `20` | `LDC` | `value(2)` | `mov cs, hi` + `mov ci, lo` |
| `21` | `LDCD` | `value(2)` | the same into `dsdi`: a constant right operand of a commutative operator |
| `22` | `LDS` | `len bytes` | `.mv csci, :string`; the bytes go to the string pool |
| `23` | `LDSD` | `len bytes` | the same into `dsdi` |
| `24` / `25` | `LDVB` / `LDVW` | `offset(2)` | load a byte / word variable: `mov a, off` + `cal :stackvar8gt8` / `…gt16`, or the long form through `stackvarget8` / `…16` when the offset is ±127 or more |
| `26` / `27` | `STVB` / `STVW` | `offset(2)` | store `csci` into a byte / word variable (`stackvar8st*`, `stackvarset*`) |
| `30` | `PUSH` | – | `psh cs` + `psh ci`: keep the left operand |
| `31` | `POPD` | – | `pop di` + `pop ds`: left operand into `dsdi` (commutative operators) |
| `32` | `SWAP` | – | `mov ds, cs` + `mov di, ci` + `pop ci` + `pop cs`: right operand into `dsdi`, left back into `csci` (the others) |
| `40`–`4f` | `BIN` | – | the operator's code; the low digit is the operator, as in `.TOK` (`add csci, dsdi`, `cal :eq16` + …, …) |
| `50`–`5f` | `BINZ` | – | the same operator when the right operand is the constant 0. The host has shorter code for `>= 0`, `!= 0` and `> 0` |
| `60` | `DEREF` | – | `#`: `mov ds, cs` + `mov di, ci` + `cal :peek16` |
| `61` | `NOT` | – | `!` |
| `62` | `INV` | – | `~`: `not csci` |
| `70` | `ENTER` | `n(2)` | before a call: move `sys_stackhead` forward by n (`stackheadrll8`, or the long form from 127) |
| `71` | `LEAVE` | `n(2)` | after a call: move it back |
| `72` | `CALL` | `sym(2)` | `cal :F_name` |
| `80` | `LABEL` | `n(2)` | local label n is here; `nop` |
| `81` | `JZ` | `n(2)` | `mov a, cs` + `or ci` + `jrx z, :n` |
| `82` | `JMP` | `n(2)` | `xor a` + `jrx z, :n` |
| `90` | `ASMB` | `count item…` | raw `asm`. An item is `00 byte`, or `01` / `02` / `03` + `sym(2)` for `:name` / `hi(:name)` / `lo(:name)` |

What BCC2 has already done, so BCC3 doesn't have to:
- **Variables are offsets.** Every local and parameter is an offset from `sys_stackhead`,
  with its size in the operation (`LDVB` / `LDVW`). The offset is negative while the
  arguments of a call are being evaluated, because `sys_stackhead` has moved by then.
  Declarations leave nothing in the IR.
- **A call is spelled out.** `f(a, b)` is `ENTER n`, then for each argument its expression
  and a store into the callee's parameter slot, then `CALL`, then `LEAVE n`. n is the size
  of the caller's locals declared so far; if it is 0, `ENTER` and `LEAVE` aren't written.
  For a variadic function the argument count is stored first, as a constant.
- **Operators are sequenced.** `a + b` is: a, `PUSH`, b, `POPD`, `BIN +`. `a - b` is: a,
  `PUSH`, b, `SWAP`, `BIN -`. `a + 5` is: a, `LDCD 5`, `BIN +`. This is where the host's
  constant shortcuts are decided, and the precedence quirks are in the order of the
  operations.
- **Control flow is labels and jumps.** `if` is the condition, `JZ n`, the block, `LABEL n`;
  with `else` a `JMP` and a second label. `while` is `LABEL a`, the condition, `JZ b`, the
  block, `JMP a`, `LABEL b`. Labels are numbered per module.
- **All checks are done:** undeclared names, wrong argument counts, duplicate locals. BCC3
  reports only its own limits.

What is left for BCC3:
- **Choosing the short or long form** of a variable access and of `ENTER` / `LEAVE`, from
  the number in the payload.
- **Jump offsets.** A `JMP` or `JZ` to a label already seen gets its final `jrx` offset; a
  forward one gets a placeholder and a fix entry.
- **Runtime helpers.** `stackvar8gt16`, `peek16`, `eq16` and the others aren't in the IR.
  BCC3 knows which helper each template calls and writes an `ee` record at its first use.
- **Strings.** BCC3 keeps the strings of the current function in memory and writes them at
  `ENDF`, each with a local label. The limit is one function's strings, not the file's.
- **Symbol numbers.** IR symbol numbers aren't object symbol numbers, because the object
  also has the helpers. BCC3 keeps a small table from one to the other.

`word main() { puts("hi"); return 0; }`:

```
49 01              'I', version 1
03 05 'STDIO'      LINK, from STDIO.H
01 04 'main'       SYM 0
10 00 00           FUNC 0
01 04 'puts'       SYM 1, at its first call
22 02 'hi'         LDS "hi"
27 00 00           STVW 0        the string's address into puts' first parameter
72 00 01           CALL 1        (no ENTER / LEAVE: main has no locals)
20 00 00           LDC 0
12                 RET
11                 ENDF
00                 END
```

Expected size: 0.5–1 × the source text. The IR has no `LINE` markers: BCC3's few errors
name the function.

- BCC3 is almost table-driven: a template per operation, plus the object writer. That's
  the reason to split BCC2 from BCC3. The parser needs the symbol tables, the template
  expander doesn't, and the expander is where the byte-identical test is decided.
- Instruction templates have fixed lengths, so BCC3 always knows its code offset without
  an assembler.

#### Rules shared by the passes

- **Byte-identical output as the main test.** With the host's templates and constant
  shortcuts, BCC–BCC3 on the emulator and `bc --obj` on the host should give the **same `.o`
  bytes** for the same source. That's a much stronger test than comparing program output.
  It needs the host compiler's quirks fixed or frozen first; see
  [host prerequisites](#host-prerequisites). Each intermediate format can also be tested on
  its own: write `.TOK` and `.IR` from Python too (`bc --tok`, `bc --ir`) and compare.
- **Jumps.** A backward jump (`while`) targets a label BCC3 has already seen, so it writes
  the final `jrx` offset itself. A forward jump writes a placeholder plus a *local fixup*
  record, and the linker patches it. There's no back-patching, because a file can't be
  rewritten.
- **Strings** go into the current function's section, after its code. Their addresses
  (`.mv` = two `mov`s) get an absolute relocation.
- **Calls** to another function get a symbol relocation, so the callee can be in any
  object. The caller needs the callee's parameter types (byte parameters take 1 byte of the
  frame, word parameters 2), so every function must be declared before it's called. That's
  the rule today already. Prototypes come from the `.H` files.
- **Assembly:** only the raw-byte `asm` statement. Real assembly code lives in `.basm`
  modules; see [mixing B and assembly](#mixing-b-and-assembly).
- **No globals in phase 3**, unless they turn out to be cheap. A top-level `word x;` is an
  error, like any unsupported feature.
- **Errors:** every pass prints `file:line message` from the `LINE` markers, stops at the
  first error, and doesn't chain to the next pass. Don't try to recover: on this machine
  the second error message is rarely worth the code.
- **Clean-up:** BCC3 deletes `.TOK` and `.IR` when it succeeds. BCC2 deletes `.TOK`. A
  failed pass leaves its input in place for inspection.
- **More passes are allowed.** If a pass grows past about 16 KB, split it again. The
  formats above make that cheap: an expression pass between BCC2 and BCC3 would only add
  one more IR-to-IR step.

### Memory budget of the compiler

Code size uses the measured 12 bytes per source line. Each pass is compiled by today's host
`bc`, so it carries the libraries it includes (up to 6 KB) as long as there's no dead-code
elimination.

| Pass | B lines (estimate) | Own code | + libraries today | Data at run time | Total |
|---|---|---|---|---|---|
| BCC | reader 200 + preprocessor 150 + lexer 250 + driver 50 = **650** | 8 KB | + 4–6 KB | `#define` table 3–5 KB (a header the size of `bdioh.b`, 116 defines; all sources have 198, 26 B each on average), stacks 2 KB | **17–21 KB** |
| BCC2 | expressions 350 + statements 300 + symbols 250 + IR writer 100 + driver 50 = **1,050** | 12.5 KB | + 4–6 KB | function table about 2.5 KB (126 different functions in `src/bdos`, names 11 chars on average), identifier table 1–2 KB, locals 0.5 KB, stacks 2–3 KB (recursion) | **23–27 KB** |
| BCC3 | templates 200 + object writer 150 + raw `asm` 30 + driver 50 = **430** | 5 KB | + 4–6 KB | symbol list 1 KB, stacks 1 KB | **11–13 KB** |

Every pass fits in 40.9 KB with room to spare, and every program file is well under 32 KB.
For comparison, one single-pass program would be about 29 KB of code plus 8–12 KB of data:
37–41 KB, too close to both limits to plan on.

- **BCC2 is the biggest.** If the spike shows it larger than estimated, the first lever is
  dead-code elimination (phase 1 of this plan: −4 KB of libraries). The second is splitting
  off an expression pass.
- **Smaller tables** if needed: names in one string pool on the heap with no fixed-size
  slots, and optionally precompiled headers (`bcc -h BDIOH.H` writes `BDIOH.HP`, a binary
  `#define` table that loads with no parsing).
- Roadmap item 5b (#17, inline variable access) makes code **faster, not smaller**: today a
  variable access is 5 bytes (`mov a, off` + `cal`), and an inline sequence can't be that
  short. It matters for [speed](#speed), not for fitting.

### Disc cost of a compile

For a source of S bytes: `.TOK` is about 0.5 S, `.IR` about 0.5–1 S, and `.O` about
1.2–1.3 × the size of the code (see [object format](#object-file-format)). A 20 KB source takes about 20–30 KB of temporary space at the peak, and
freed space isn't reused today. On a 128 KB work disc that's a handful of compiles before
`pack` is needed. Phase 0 therefore includes `pack`. Deleting the *last* file on a disc
already frees its space (the free pointer is computed from the live files, once the
allocation bug is fixed). That doesn't help here: `.O` is written after `.TOK` and `.IR`,
so deleting them leaves a hole in front of it.

### Speed

An estimate, to be measured in phase 3. The passes, compiled by today's `bc`, spend most of
their time in runtime helper calls (every variable access is a call). Assume
1,000–3,000 instructions per source line over all passes. A 700-line file like `texted.b`
is then 0.7–2.1 M instructions, which is **5–16 seconds** at 130k instructions/s, plus a
program load per pass. Headers add to that on every compile (`bdioh.b` alone is 188 lines),
which is a reason for precompiled headers. Disc I/O is cheap (DMA, 128 B per command). For
the e2e tests, the `--max-instructions` limits have to grow to tens of millions.

## Working with the tools: discs, commands and steps

### Which disc holds what

There are two drives. **Drive A holds the development disc and is only read. Drive B holds
the work disc, and everything a project reads or writes is on it:** sources, headers of
the project, temporary files, `.O` files and the `.PRG`.

| | Drive A: development disc | Drive B: work disc |
|---|---|---|
| Content | boot, `BDOS.SYS`, `LS`, `CP`, `RM`, `TEXTED`, `PACK`, `BCC`–`BCC3`, `BLINK`, library `.O` files, library `.H` files | `*.B`, the project's own `*.H`, `*.TOK` and `*.IR` (temporary), `*.O`, `*.PRG` |
| Written during a build | never | always |
| Free space | about 170 of 1,024 sectors after dead-code elimination | nearly the whole disc (about 125 KB) |

Why this way, and not sources on the compiler disc or objects on a third disc:
- **Space.** The development disc has about 21 KB free. One compile of a 20 KB source
  needs 20–30 KB of temporary files plus the `.O`.
- **Deleted space isn't reused.** Every build leaks sectors until `pack` runs. On B that
  costs a `pack b:` now and then; on A it would slowly fill the system disc.
- **One write handle** means one output file at a time, but it can be on either drive. So
  nothing forces the output onto a different disc than the input.
- **The program runs where it is built:** `B>hello`.
- **The linker needs no disc of its own.** `BLINK` (about 110 sectors) and the libraries
  are on the development disc. Only `BASM` goes on a separate assembler disc, used in
  drive A when assembly modules are built.
- **A finished program** is copied with `cp` to whatever disc should carry it.

The rule the tools follow: **an output file goes to the drive of the main input file**. A
file named without a drive is looked up on the active drive. `#include` files and library
objects are searched on the main file's drive first, then on A.

With the shell search path (phase 2) the user works on B and the tools are found on A:
`B>bcc hello`. Without it the same works from A with a prefix: `A>bcc b:hello`.

A project of two source files, start to finish:

```
B>texted                    write HELLO.B and UTIL.B (and UTIL.H)
B>bcc util                  UTIL.B ──► UTIL.TOK
B>bcc2 util                 UTIL.TOK ──► UTIL.IR
B>bcc3 util                 UTIL.IR ──► UTIL.O
B>bcc hello                 … the same three passes ──► HELLO.O
B>bcc2 hello
B>bcc3 hello
B>blink hello               HELLO.O + what it needs (UTIL.O, libraries from A) ──► HELLO.PRG
B>hello
B>pack                      when the disc fills up
```

From phase 5, `bcc hello` alone runs the three passes.

A very small program can be built on the development disc alone, in its free space. It's
a fallback, not the way to work.

### What the compiler does

**Command line:** `bcc [drive:]name`, then `bcc2` and `bcc3` with the same argument. The
name has no extension. One call compiles **one main file**, `NAME.B`. A project with
several source files compiles each one separately and links the `.O` files.

**Input:** `NAME.B` and the `.H` files it includes, all in texted format. Including is
nested at most 3 levels deep, the main file counted (3 read handles).

**Output:** `NAME.O` on the drive of `NAME.B`. `NAME.TOK` and `NAME.IR` exist only during
the compile.

BCC (lexer):
1. Read the name from the command line. No name: print the usage line and stop.
2. Open `NAME.B` for reading. Not found: error.
3. Delete an old `NAME.TOK`, then create `NAME.TOK`.
4. Read the source record by record. Keep the texted line number of each record.
5. For `#include file.h`: open the file (main file's drive, then A), push it on the
   include stack and continue reading from it. At its end, close it and continue the file
   below. A fourth level is the error `include too deep`.
6. For `#define NAME value`: store it in the table. Elsewhere, replace whole identifiers
   that are in the table.
   For `#link name`: write a `LINK name` token. BCC2 copies it into the IR and BCC3
   writes it as a `de` record. `#code`, `#heap` and `#codelimit` travel the same way, as
   `ADDR` tokens and `ad` records.
7. Write every other line as tokens, with a `LINE` marker when the line or file changes.
8. At the end of the main file: write the end token, close, print `ok`.

BCC2 (parser):
1. Open `NAME.TOK`; delete an old `NAME.IR` and create `NAME.IR`.
2. Read tokens and rebuild the identifier table from the `NEWID` tokens.
3. For a prototype: store the function's name and parameter sizes.
4. For a function: parse it, give every local its frame offset, check that every called
   function is declared, and write its IR.
5. At the end: close both files, delete `NAME.TOK`, print `ok`.

BCC3 (code generator):
1. Open `NAME.IR`; delete an old `NAME.O` and create `NAME.O`; write the header record.
2. For each function: write `SECT` and `GLOBL`, then expand each IR operation into its
   template in the code buffer, with fix entries. A symbol used for the first time gets
   its `ee` record then. Flush by the [writing rules](#object-file-format).
3. Write the function's strings after its code, each with its local label.
4. At the end: write `ed 00`, close, delete `NAME.IR`, print `ok` and the code size.

On an error, every pass prints `FILE.EXT:line message`, closes and deletes its unfinished
output, leaves its input in place, and stops. Nothing is chained after an error.

### What the linker does

**Command line:** `blink [drive:]name`. One name, without the extension: the main object,
which also names the program. There are no address options: `#code`, `#heap` and
`#codelimit` stay in the source and reach the linker inside the objects.
The command line is too short for a list of objects, so **the linker finds the other
objects from the content of the ones it reads.**

**How it finds them: `#link`.** A source line `#link util` means "a program that contains
this module also needs `UTIL.O`". The compiler and the assembler copy it into the object as
a `de` (`NEED`) record. The line sits in the header, next to the prototypes it belongs to.
**Every object is named by a `#link`; nothing is derived from a header's file name.**

```
// UTIL.H                         // STD.H
#link util                        #link std        (the B bodies)
word util_sum(word a, word b);    #link stda       (the assembly routines)
                                  byte peek8(word Paddr);
```

- A program that includes `UTIL.H` gets the `NEED` without knowing which objects implement
  the header. A header with only `#define`s (`BDIOH.H`) has no `#link`.
- One header can name several objects (`STD.H`: a B module and an assembly module).
- Needs are followed through: if `UTIL.O` needs `STRINGS.O`, the program gets it too.
- A needed object that is missing is an error. One that is linked but not used costs only
  link time: dead-code elimination drops its sections.
- `RUNTIME.O` is always linked, first, without a `#link`.

**Input:** `NAME.O`, `RUNTIME.O`, and every object reached through `NEED` records. Each is
searched on the main object's drive, then on A.

**Output:** one file, `NAME.PRG`, on the main object's drive. It is a raw image for
`0x6000`, as today.

1. Read the name from the command line. Start the module list with `RUNTIME` and `NAME`.
2. **Pass 1.** Take the next module from the list that hasn't been read. Open its object
   (not found: error naming the module that needs it), check the `b0` record and the
   version, and read the records:
   - `de`: add the module to the end of the list, unless it's there already;
   - `ad`: store the address. A different value for one already stored is an error;
   - store every section (size), every global (section, offset) and which symbols each
     section refers to. Skip `CODE` contents.

   Close it. Repeat until every module in the list has been read.
3. Report a symbol defined twice, naming both modules.
4. Mark the sections reachable from the runtime entry point and `F_main`. Report every
   undefined symbol that a marked section uses, with the module that uses it.
5. Give each marked section its address, from the `#code` address (default `0x6000`), in
   list order. The runtime entry
   section is first.
6. **Check the size before writing anything:**
   - the image is over 32,640 bytes (255 sectors, the file-system limit): error
     `program too big`, with the size;
   - the image reaches the `#heap` or `#codelimit` address, or leaves too little room for
     the stacks: error;
   - the output disc has fewer free sectors than the image needs: error `disc full`.
7. Delete an old `NAME.PRG` and create `NAME.PRG`.
8. **Pass 2.** For each module in the list again, for each marked section: read each
   `CODE` record into the buffer, apply the fix records that follow it, and write the bytes.
9. Close. Print the program size and how many sections were kept and dropped.

All errors are found in steps 1–6, so a failed link never leaves a partial `.PRG`, and
never deletes the old one. The module list costs 8 bytes per module.

## Mixing B and assembly

```
.basm ──BASM (bc81asmc --obj on the host)──► .o ─┐
.b    ──BCC–BCC3 (bc --obj on the host)────► .o ─┼──BLINK (blink.py)──► .PRG
library .o files ────────────────────────────────┘
```

The assembler and the compiler write the same object format ([BOF](#object-file-format)),
and the linker doesn't know or care which language a module came from. Assembly code goes
into `.basm` modules, as whole routines that follow the B calling convention. B calls them
through prototypes like any B function, and they can call B. There's no assembly text
inside B sources any more, only a [raw-byte `asm`](#raw-asm-in-b) for a few inline
instructions. This replaces the 2026-11-10 plan (inline `asm "…"` text assembled by the
compiler); see [why](#why-not-inline-asm-text).

### The calling convention becomes an ABI

Today it's written down only as how the compiler happens to work (design decision C2,
[../03-compiler.md](../03-compiler.md)). Assembly modules depend on it, so it becomes a
frozen ABI, recorded as a new design decision:

- **Arguments.** The caller moves `sys_stackhead` forward by the size of the locals it has
  declared so far (`Context.push_scope` in `bc_ast.py`), stores the
  arguments as the callee's first locals, `cal`s, then moves `sys_stackhead` back. In the
  callee, an argument's offset is the sum of the sizes of the arguments before it (byte 1,
  word 2): `poke8(word Paddr, byte value)` finds `Paddr` at 0 and `value` at 2. An assembly
  routine reads them as the compiler does: `mov a, 0x02` + `cal :stackvar8gt8`.
- **Variadic functions** (`printf(word PformatStr)***`): a hidden word with the number of
  arguments comes first (offset 0), then the fixed arguments, then the extra ones as
  words. For `printf`: the count at 0, `PformatStr` at 2, the extra arguments at 4, 6, …
- **Return value** in `csci`. A byte result is in `ci`, with `cs` = 0.
- **Registers:** the callee may change all of them, `A` and `F` included. Callers keep live
  values on the CPU stack, as generated code already does. The CPU stack is balanced on
  return.
- **Calling B from assembly:** move `sys_stackhead` forward past the routine's own frame
  (`stackheadrll8`, as in generated code), store the arguments, `cal`, move it back. A leaf
  routine that keeps nothing on the software stack doesn't touch `sys_stackhead`.
- **Entry from outside B.** Code entered by something other than a B call is an assembly
  stub that builds a frame and calls B. Examples: bcOS calling `bdio_call` through slot
  `0x37`, and the program entry point in `runtime.basm`.

Roadmap item 5b (#17, inline variable access) changes how generated code *reads*
variables, not where they are, so it stays compatible with this ABI.

### Symbol names

- **A B function `name` is the global symbol `F_name`.** Today the host makes numbered
  labels (`FPOKE80003`), which another module can't know. The prefix is needed because
  there is one namespace: today B's `peek16` (`std.b`) and the runtime's `peek16` both
  exist, and so do bdosh's B function `bdio_call` and bdio's assembly label `bdio_call`.
- **An assembly routine callable from B** defines `F_name` and exports it with
  `.global F_name`. B sees it through a prototype in a `.h` file, which gives the
  argument sizes the caller needs: `byte poke8(word Paddr, byte value);`.
- **Other assembly labels** (`poke16`, `os_metacall`, `sys_stackhead`) aren't callable from
  B by name. B reaches them through an `F_` routine or raw `asm`.
- **B globals**, if they come, would be `G_name`. Jump and string labels inside a B
  function stay local to the module and never reach the symbol table.
- Assembler identifiers are a letter, then letters, digits and `_` (`bc81asmc_grammar.py`),
  so `F_name` is valid as it is.

### Shared constants

Assembly needs the same constants as B: `bdioh.b` alone has 116 `#define`s. To keep one
source of truth, BASM (and `bc81asmc`) accept `#include file.h` and `#define NAME value`
lines with the same meaning as in B, and skip a header's prototype lines. A defined name
can be used wherever an operand takes a number (`mov a, BDIO_FREAD`); the value is written
in any form B accepts and sized by the operand. Without this, the constants would be
copied by hand into `.def` lines and drift. BCC and BASM share this code (`PRE`).

<a id="raw-asm-in-b"></a>
### Raw `asm` in B

For the few places where a call costs too much, or one or two instructions sit between B
statements:

```
asm 0xd8, 0x81;                                  // out #cs, a
asm 0xa8, :poke16;                               // cal :poke16
asm 0x18, hi(:bdio_call), 0x14, lo(:bdio_call);  // .mv csci, :bdio_call
```

- **Items:** a number 0–255 or a `#define` name (1 byte); `:name` (2 bytes, high byte
  first, `ABS16` fixup); `hi(:name)` / `lo(:name)` (1 byte, `HI8` / `LO8` fixup). Nothing
  else: no mnemonics, no labels, no relative jumps to symbols.
- **Context:** as with today's `asm`, a B statement before it leaves its value in `csci`,
  and the bytes run in order with the generated code.
- **Relative jumps** inside the bytes are encoded by hand (sign-magnitude, design decision
  G5) and must stay inside the statement.
- **Cost in the compiler:** about 30 lines per pass, and no encoder.
- **Use it rarely.** Anything with a label, or more than a few instructions, belongs in a
  `.basm` module. The bytes come from the assembler's output, not from memory: the encodings
  above were checked with `bc81asmc` (`cal :x` = `a8 hh ll`, `mov cs, n` = `18 n`,
  `mov ci, n` = `14 n`, `out #cs, a` = `d8 81`).

<a id="moving-todays-asm"></a>
### Moving today's `asm`

41 functions in `src/bdos` contain `asm "…"`, with 347 lines in all:

| Group | Functions | `asm` lines | After the move |
|---|---|---|---|
| assembly with a B header: the body is only "load a parameter into `csci`" statements, declarations and `asm` | 30, for example `peek8`, `poke16`, `memcpy` (`std`), `putc`, `puts`, `readsn` (`stdio`), `strcpy`, `upchar` (`strings`), `bdio_call` (`bdosh`), `bdio_getstate` (`bdio`), `eject` (`bdos`) | 127 | `.basm` modules, almost line for line. Each parameter statement becomes the `mov a, off` + `cal :stackvar8gt*` pair the compiler emits for it today, so sizes stay the same |
| `printf` (`stdio`) | 1 | 111 | all assembly. 111 of its 122 lines are already `asm`, and its `while` loop and pointer increment are a few instructions. It reads its extra arguments by the variadic rule, instead of from the address that reading `PformatStr` leaves in `dsdi` |
| allocator: `malloc`, `mfree`, `mcompact`, `mtotal` (`stdmem`) | 4 | 70 | B plus small assembly helpers that return one value each. Today `asm` stores the two results of the runtime's `mseek` into locals through a side effect: reading a local leaves its address + 1 in `dsdi`. That depends on compiler internals and breaks with any change to the helpers |
| bdio entry: `bdio_call` (`bdio`) | 1 | 17 | an assembly stub `bdio_call:` saves A, CSCI and DSDI, builds a frame and calls B's `bdio_dispatch(regA, regCSCI, regDSDI)`. The dispatcher is plain B |
| device and program control: `bdio_iosec`, `bdio_setdrive`, `bdio_execute`, the shell `main`, `putdecwnl` | 5 | 22 | small assembly helpers, or raw `asm` for one or two instructions (for example the shell installing `bdio_call` in slot `0x37`) |

The move is done on the host in phase 1, with the host tools, and the e2e scenarios must
pass unchanged. The linker's dead-code elimination works per section, so splitting the
routines into sections costs nothing in the programs that don't use them.

### What it costs

- **A call where inline code used to be:** `cal`/`ret` plus storing the arguments. Only the
  last group in the table has `asm` inside B control flow, and none of it is on a hot path.
- **The calling convention is frozen.** Changing argument offsets or the stack discipline
  later means changing every assembly module.
- **The host language changes:** `bc` keeps `asm "…"` until the libraries are moved, then
  drops it, so B 1.4 has only raw `asm`. Keeping it as a host-only extension would mean the
  byte-identical test never covers it.
- **Design decisions:** a new one for the ABI and symbol names. C5 ("modularity is
  textual: `#include`/`#define`, one image, no linker") is replaced.

<a id="why-not-inline-asm-text"></a>
### Why not inline `asm "…"` text

That was the 2026-11-10 plan. Compared with it:
- **BCC3 needed the full encoder:** about 400 lines, 5 KB, which made it 16–18 KB instead of
  11–13 KB.
- **`#define` had to be replaced inside `asm` text** but not inside other strings: a
  special case in both preprocessors (#19).
- **`asm` text depends on compiler internals** (the `dsdi` side effect above), and the
  byte-identical test would have frozen those internals for good.
- **BASM had to exist on the BC64 before the compiler,** and it had to be on the
  development disc, which is the tightest space number in this plan.

## The assembler (BASM)

A separate program, roadmap item 8, and a phase of its own **after** the compiler. It reads
one assembly source and writes one `.o`, in the same object format as the compiler, so
assembly and B modules link together.

- **One pass.** A reference to a label already defined (behind) gets its final value
  straight away. A forward reference writes a placeholder plus a fix entry, and the
  linker patches it. The assembler needs a label name table, but no second read of the
  source.
- **The syntax is easy to parse in B:** lowercase mnemonics, hex-only immediates with a
  fixed number of digits, `:label` references, `;` comments, four directives (`.org`,
  `.db`, `.mv`, `.def`). See [../02-assembler.md](../02-assembler.md).
- **New directives** for object output (the host `bc81asmc --obj` gets the same ones):
  - `.global name` / `.extern name`: export and import symbols. Without `.global`, labels
    stay local to the module;
  - `.sect name`: start a new section. It lets the runtime be split per routine so the
    linker drops what's unused (part 3 of #16). Routines that fall through into the next
    one stay in one section.
- **`#include` and `#define`** from `.h` files, as described under
  [shared constants](#shared-constants).
- **`.org`** is accepted only as the first line, and makes the whole file an absolute
  section at that address (the boot sector, `0x0e00`). Elsewhere it's an error.
- **Known quirks:** `out #r, imm` is broken on the host (#11) and unused. BASM rejects it,
  instead of copying the broken encoding.
- **Size estimate:** reader 200 (shared `RDR`) + `#include`/`#define` 150 (shared `PRE`) +
  operand parser 250 + encoder 400 (`ENC`) + label table 100 + object writer 150 (shared
  `BOFW`) + driver 50 = about **1,300 lines**, 15.5 KB of code + 4–6 KB of libraries +
  2–3 KB of label names (`bdos.basm` has about 300 labels) + 3–5 KB of `#define` table.
  That's **25–30 KB**: it fits as one program. If the measurement says otherwise, the
  levers are precompiled headers (see the [memory budget](#memory-budget-of-the-compiler))
  or a split into a parser pass and an encoder pass.
- **Test:** for the same source, `BASM` on the emulator gives `.o` bytes identical to
  `bc81asmc --obj` on the host. The inputs are `runtime.basm` and every library `.basm`
  module from phase 1.

**Why after the compiler.** The compiler doesn't need it. The assembly library modules are
built on the host and copied to the disc as `.o` files, like the B ones. The compiler phase
builds and tests the reader, `PRE` and the object writer, so BASM then adds only the
encoder and the label table. Until BASM exists, assembly modules are written on the host;
once it exists, the whole library set can be rebuilt on the BC64. BASM also doesn't have to
be on the development disc for B work, which is the tightest space number in this plan.

**Why not inside the compiler's pipeline.** The compiler doesn't write assembly text for
BASM to read. Its own code is about 30 fixed templates that BCC3 writes as bytes, and
assembly text for a whole program is far bigger than the disc (see the short answers). Raw
`asm` bytes are copied as they are, so the compiler has no encoder at all.

## `#include` on the machine

- **Handles.** The main file takes one read handle, so at most two nested levels of
  `#include` can be open at the same time. Headers rarely nest (`bdosh` includes `bdioh`,
  and that's all). Allow depth 3 in total and report `include too deep` beyond that. The
  write handle is the `.o` file and isn't affected.
- **Semantics.** Keep textual inclusion, as on the host: the reader keeps a stack of
  (handle, file name, line number) and switches handles. Error messages name the file.
- **File names.** `#include stdio.h` searches the drive of the main source first, then A.
  An explicit `a:stdio.h` works too. Today the host resolves paths relative to the main
  file's directory, so this is the same rule.
- **What changes in the sources.** Today `#include stdio.b` pastes the whole library body
  into every program. That's 6 KB of code compiled again and again: on the machine it
  multiplies compile time and doesn't fit in memory. The split:

  | Today | After the split |
  |---|---|
  | `bdioh.b` (only `#define`s) | `BDIOH.H`, unchanged content |
  | `std.b`, `stdio.b`, `strings.b`, `stdmem.b`, `bdostools.b` | `X.H` (`#define`s + prototypes) + `X.B` (B bodies) + `X.BAS` (assembly routines, where it has any) → `.O` files, built on the host first and on the BC64 from phases 3 and 4 |
  | `bdosh.b` (`#include bdioh.b` + wrappers) | `BDOSH.H`; `bdio_call` moves to an assembly module and the B wrappers stay B; both are linked in |
  | a program `#include`s the `.b` files | the program `#include`s the `.h` files; the linker adds the `.o` files |

  The host build keeps working during the transition: `bc` without `--obj` can still paste
  bodies until the assembly parts move to `.basm` modules. From then on, every program is
  linked.
- **`#define` semantics.** BCC replaces whole identifiers only (#19), in code but not
  inside string literals. That's simpler to write in B than substring replacement. With no
  `asm` text left, there's no exception to make. BASM applies the same rule to its operands.
  The host preprocessor must change to the same rule first, so both compilers stay
  identical.

## Linking

### Object file format

A proposal, "BOF v1" (record layout decided 2026-11-13). It is a record stream in a normal
BFS file, written through the buffered write call and read strictly in order: there is no
index, because bdos has no seek and the writer can't know sizes before it writes. All
16-bit values are big-endian (design decision G6).

**Every record is `tag(1) length(1) content[length]`**, so the content is at most 255
bytes. A reader that doesn't need a record skips it by its length.

| Tag | Record | Content | Meaning |
|---|---|---|---|
| `b0` | header | `version(1) module-name` | always the first record, so the tag is also the magic number |
| `ee` | `EXTRN` | `name` | declares symbol number k (k = 0, 1, 2… in order of the `ee` records). The symbol may be defined in another module or in this one |
| `de` | `NEED` | `module-name` | from `#link module-name`: `module-name.O` must be linked too; missing is an error |
| `ad` | `ADDR` | `kind(1) value(2)` | from `#code` (kind 0), `#heap` (1) or `#codelimit` (2): an address of the finished program |
| `5e` | `SECT` | `flags(1) name` | starts a section: one function, plus its strings. The section offset starts at 0 |
| `91` | `GLOBL` | `name` | the global symbol `name` is at the current section offset |
| `c0` | `CODE` | `bytes` | code/data bytes appended to the current section, placeholders included |
| `1a` | `LABEL` | `n(2)` | local label n is at the current section offset |
| `ab` | `ABS` | `value(2) name` | an absolute global symbol (from `.def`) |
| `f1` | fix `ABS16` | `offset(1)…` | 16-bit absolute address at each offset; the target is in the placeholder |
| `f2` | fix `REL15` | `offset(1)…` | 15-bit relative offset (`jrx`, `clr`); the target is in the placeholder |
| `f8` | fix `HI8` | `(offset(1) target(2))…` | high byte of the target's address |
| `f9` | fix `LO8` | `(offset(1) target(2))…` | low byte of the target's address |
| `fa` | fix `REL7` | `(offset(1) target(2))…` | 7-bit relative offset (`jmr`) |
| `fb` | fix `HILO` | `(offset(1) target(2))…` | high byte at `offset`, low byte at `offset + 2`: the two `mov`s of `.mv csci, :x` (`18 hh 14 ll`) in one entry |
| `ed` | `END` | – | end of the module: `ed 00` |

A name is the rest of its record, so it carries no length of its own.

**Fix records.** They don't interrupt the code. A `CODE` record holds up to 255 bytes, and
the fix records that follow it patch bytes inside it; each `offset` is a position in that
`CODE` record.
- **Target encoding:** a 16-bit value. Top bit clear = symbol number k (from an `ee`
  record); top bit set = local label n in the low 15 bits.
- **16-bit kinds** (`f1`, `f2`) keep the target in the two placeholder bytes, so an entry is
  only the offset: 1 byte per call or jump.
- **8-bit kinds** (`f8`, `f9`, `fa`) have a 1-byte placeholder, which can't hold a target,
  so the entry carries it. `fb` does a `.mv` in 3 bytes instead of 6. `f8` and `f9` remain for
  a lone `hi(:name)` or `lo(:name)` in raw `asm`.
- There is no addend: the assembler has no `:label+n` expressions.

**Writing rules.** They make the output deterministic, which the byte-identical test needs.
- The writer flushes the `CODE` record when it is full, before a `LABEL`, `GLOBL`, `SECT`
  or `END`, and before a template (or raw `asm` item) that wouldn't fit whole. A
  placeholder never straddles two records.
- The fix records follow their `CODE` record directly, in tag order (`f1`, `f2`, `f8`,
  `f9`, `fa`, `fb`), with offsets ascending. Empty lists aren't written. A list longer than
  255 bytes continues in another record with the same tag.
- Every symbol a fix refers to is declared by an `ee` record before the `CODE` record that
  uses it. `91` only defines a name; it doesn't allocate a number. A call to a function in
  the same module therefore also goes through an `ee` record, and the linker resolves it by
  name like any other.

- A `de` record is written for every `#link` line and an `ad` record for every `#code`,
  `#heap` or `#codelimit` line, where they appear, repeats included. The linker ignores a
  module it already has.
- An `ee` record also flushes the `CODE` record, so symbols can be declared at their
  first use.

`word main() { puts("hi"); return 0; }` with `#include stdio.h` gives roughly:

```
b0 06 01 'HELLO'               header, version 1
de 05 'STDIO'                  from '#link stdio' in STDIO.H
ee 06 'F_puts'                 symbol 0
ee 0d 'stackheadrll8'          symbol 1 (runtime helpers are symbols too)
5e 07 00 'F_main'              section
91 06 'F_main'                 global at offset 0
c0 nn  … 18 00 14 00 …         .mv csci, <string>
       … a8 00 00 …            cal F_puts: the placeholder holds symbol 0
       … a8 00 01 … ret        cal stackheadrll8: the placeholder holds symbol 1
f1 02  oo oo                   two ABS16 fixes: just their offsets
fb 03  oo 80 00                HILO fix to local label 0
1a 02 00 00                    local label 0 = the string
c0 03 68 69 00                 "hi"
ed 00
```

**Size.** A variable access is 5 bytes of code (`mov a, off` + `cal`) plus 1 fix byte. With
one fix record per patch it would be 11–12 bytes, because each fix would also split the
`CODE` record. The estimate for a whole `.o` is about 1.2–1.3 × the code size, to be
measured in phase 1.

**Still open:** the `SECT` flags. At least "always keep" (the runtime entry point) and
"absolute at address X" (the `.org` boot sector) are needed.

- **One section per function.** That makes dead-code elimination exact: the linker keeps a
  section only if something it keeps refers to it, starting from `main`.
- **`REL15`** is the sign-magnitude 15-bit encoding used by `jrx` and `clr`, and **`REL7`**
  the 7-bit one used by `jmr` (design decision G5). The linker must encode them the same way
  the assembler does, and reports a target out of range by the symbol's name.
- **Local labels** are numbered per module (a module like `bdos` has 181). The linker keeps
  them in an array of `2 × n` bytes while it handles that module.
- **Symbols the linker defines:** `__end` (the end of the image: today's `sys_stackhead`
  sits there and the variable stack grows from it) and `__heap` (the `#heap` address).
- **Program addresses** come from the `ad` records of all linked objects: `#code` is the
  base address (default `0x6000`), `#heap` the heap address, `#codelimit` an upper limit
  for the end of the image. Two objects that give different values for the same one are a
  link error naming both modules.
- **Libraries.** First version: plain `.o` files on the development disc, found through
  `NEED` records. Later: `LIBB.L`, the concatenated objects with an index of their
  global names at the start, so the linker reads only the members it needs.

### Linker algorithm (BLINK)

1. **Pass 1, symbols.** For each object in order, read the records. Note every section's
   size, its globals and what it refers to. Build:
   - a global symbol table (name in a string pool → section, offset);
   - a reference list per section: each external symbol it uses. Today's whole system has
     only a few hundred of these, at 2 bytes each.
2. **Mark** the sections reachable from `main` and from the runtime entry point, following
   the reference lists. Report undefined symbols that are reachable.
3. **Lay out** the live sections from `0x6000` in order. Each one gets its address.
4. **Pass 2, emit.** For each object, read it again. For each live section, keep its local
   label offsets (the module's array from pass 1), apply the fix records, and write the bytes to
   the single write handle. The output is today's `.PRG` format: a raw image loaded at
   `0x6000`. The shell needs no change.

Memory: about 3 KB of tables for a program the size of `BDOS.SYS`. The linker itself is
estimated at 600–900 lines of B, about 8–11 KB plus libraries. **It fits easily.** It
reads one object at a time (one read handle) and writes one file (the one write handle).

A two-pass design is needed because the output can't be patched afterwards: all addresses
must be known before the first byte is written.

### What the linker gives the rest of the project

- **Roadmap item 5a / #16 (drop unused code) on the host:** link every disc program with
  `blink.py`. Each of the 8 programs on the disc carries most of the 6 KB of libraries, so
  dead-code elimination should save 2–4 KB per program, about **20 KB on the system disc**.
  That space is what the development disc needs.
- **Smaller `BDOS.SYS`**, which leaves more room before the file buffers at `0x5d00`. Today
  the margin is 1.5 KB.
- **The relocatable executables** from the bdos roadmap become a linker option: link at
  another base address.

## Programs bigger than memory

The limits are 32,640 bytes per file and about 38 KB of usable memory (40.9 KB minus the
stacks). Three ways past them, from simplest:

<a id="chaining"></a>
**1. Chaining: several programs, run one after another.** This is how the toolchain itself
works (BCC, BCC2, BCC3, then BLINK, then the program). Data passes between them in disc files.
- **What's missing:** a program can't start another one. The proposal is a new bdio call,
  `bdio_chain(Pcmdline)` (`0x1b`; `0x1a` is `random` now). It copies a command line into a small *next command*
  buffer and returns. When the current program returns to the shell, the shell runs that
  command line as if it had been typed.
- No stack tricks are needed: the program ends normally, and only the shell loop changes.
  The program loader (`bdio_execute`) stays shell-only.
- **Extensions:** the buffer can hold several commands (`bcc hello; blink hello; hello`),
  and a batch file with one command per line is the "script execution" item on the bdos
  roadmap.
- The shell command line (`0x0dd2`, 45 bytes) must survive until the next program reads
  it. It already does.

**2. Overlays: one program, with parts loaded on demand.** This is the classic CP/M and
Turbo Pascal technique.
- The program is split into a **root**, which is always loaded at `0x6000`, and
  **overlays**, which share one region after the root. Each overlay is its own file
  (`PROG.OV1`, `PROG.OV2`, …), linked at the overlay region's base address.
- The linker generates a stub for each overlay entry point. The stub loads the overlay if
  it isn't the current one, then jumps.
- Loading needs **no new bdos call**: `bdio_fbinopenr` + `bdio_fbinread` already read
  whole sectors to any address.
- **Rules:**
  - overlays call only the root, or their own functions;
  - data shared between overlays lives in the root;
  - the user picks the overlay groups (`blink -o parse.o,expr.o -o gen.o`).
- Program size is then limited by the disc, not by memory. An overlay switch costs one
  file open plus a few KB of DMA: cheap.
- For the compiler, adding a pass is simpler than overlays. Overlays are for programs that
  can't be split into steps with a file between them, like an editor or a game.

**3. Data in files, not in memory.** For the data side: a compiler keeps its symbol tables
in memory but streams everything else, and texted could page its buffer. This is a
per-program design choice, not infrastructure.

**4. Plan B: extend the file system.** Use a 2-byte file length in catalog v2 (bdos 1.1b,
already on the bdos roadmap). It removes the 32 KB file limit, but not the 40 KB memory
limit, so overlays are still needed above that. It changes the catalog format, which
touches `bdio.b`, `ls`, `cp`, `rm`, `cha`, `format`, `makedisc` and the e2e catalog reader.
That's why it's plan B: worth it only if plan A turns out not to be enough.

**5. Hardware options** (not part of either plan; they change the machine): bank-switched
memory behind an I/O port, or the bigger 80 × 32 discs of roadmap item 7. The bigger discs
would remove the development-disc squeeze described under [risks](#risks-and-open-questions).

## Disc and bdos prerequisites

Found while preparing this page. These are real problems today, and a compiler that
creates and deletes files on every run makes them much worse.

| # | Problem | Evidence | Fix |
|---|---|---|---|
| 1 | **A new file overwrites an existing file after `rm`** | Reproduced on a copy of `os.bdd`: `rm hellowrd.prg`, then texted `s new.txt`. `NEW.TXT` is allocated at 34/00, the start of `TEST.B`, and `cat -c test.b` then shows the new text. `rm` moves the last catalog entry into the hole, and `bdio_fcat_scanmem` then computes a free pointer that goes *backwards*. One cause found by reading the code: the free position is read back as `(freetrack << 4) \| freesector` (`bdio.b:192`), while `bdio_tracksector_add` uses `track << 8 \| sector`. From the second catalog sector on, the comparison uses mixed encodings. | file a bug; fix the free-pointer computation and add an e2e test (rm, then create, then cat the old file). **This blocks everything else here** |
| 2 | `ls` reports 4 sectors too many free | `(FDD_TRACKS - freeTrack) * FDD_SECTORS + freeSector` (`ls.b:186`) adds the sector; it should subtract it. 52/02 shows `00C2` (194) free; 190 is right | one-character fix |
| 3 | Deleted space is never reused | allocation always continues after the last file | a `pack` utility that moves files down and rewrites the catalog (simple, because files are contiguous). Every edit–compile–link cycle leaks space until then |
| 4 | Only one write handle, and only one growing file at a time | `BDIO_FDESCRIPTOR_WRITE_MAX 0x00` | **keep it**: the design above writes one file per program. Raise it only if a later tool truly needs two |
| 5 | A program can't start another program | `bdio_execute` is shell-only and uses `cal` | the `bdio_chain` call ([chaining](#chaining)) |
| 6 | Programs run only from the active drive | the shell looks up `NAME.PRG` in the current catalog | a search path: active drive, then A |
| 7 | The `CP.PRG` catalog entry is 56 sectors, the build 57 | known since #47 | fix it when #49's cp bug is fixed |

## Host prerequisites

The BC64 compiler must match the host compiler, and the host compiler is the test oracle.
So these host changes come first:

1. **Freeze the language as "B 1.4" for both compilers.** Fix the issues that would
   otherwise be implemented twice, or implemented differently on the BC64:
   - #19, token-based `#define`: whole identifiers, not inside strings;
   - #20, `return` anywhere: simpler for BCC2 to implement correctly than to copy the bug;
   - #18, precedence: **don't** change it before BCC. Keeping today's quirks is cheaper
     than migrating all the sources;
   - raw-byte `asm` added; `asm "…"` removed once the libraries are moved;
   - `#link name` added, in `bc` and in `bc81asmc`;
   - the `nop` the host writes at every label and function start removed (176 bytes in
     `texted`, 220 in `bdos`). The assembler must first accept a label on a line of its
     own. BCC3's `LABEL` and `FUNC` templates follow the host, so the outputs stay
     byte-identical.
2. **Object output on the host:** `.global` / `.extern` / `.sect`, `#include` / `#define`
   and `--obj` in `bc81asmc`; external references for prototypes and `F_name` symbols in
   `bc`. Move the runtime from `bc_stdlib.py` into `runtime.basm`, so the host and BASM
   assemble the same file.
3. **`blink.py`**, then link all disc programs with it: the size win and the test of the
   format.
4. **The ABI and symbol names** written down as a design decision, then
   [today's `asm` moved](#moving-todays-asm) into `.basm` modules.
5. **Split the libraries** into `.h` + `.b` / `.basm` → `.o`.
6. **`ftool importtext` / `exporttext`**, so tests can put B sources on a disc in texted
   format.

## Phased plan

| Phase | Content | Exit criterion |
|---|---|---|
| 0 | disc bugs 1–2, `pack` (3), `ftool importtext` | e2e: `rm` then create keeps other files intact; `pack` reclaims space |
| 1 | BOF format, `bc81asmc --obj` with `.global`/`.extern`/`.sect` and `#include`/`#define`, `bc --obj` with `F_name` symbols and raw `asm`, `runtime.basm`, `blink.py`; the ABI design decision; today's `asm` moved into `.basm` modules; library split | every disc program built through `blink.py` from B and `.basm` modules runs its e2e scenarios unchanged; no `asm "…"` left in `src/bdos`; sizes recorded per program |
| 2 | `BLINK.PRG` (B, built on the host), development disc layout, shell search path | e2e: host-built `HELLO.O` + libraries linked **on the BC64** gives the same bytes as `blink.py` |
| 3 | first a spike: BCC built and measured. Then `BCC`–`BCC3`: the B 1.4 language with raw `asm`, without globals; the shared modules `RDR`, `PRE`, `BOFW`; host `bc --tok`/`--ir` to test each format | e2e: `.TOK`, `.IR` and `.o` byte-identical to the host's for `helloworld`, `ls`, `cp`, `rm`, `cha`, `cat`, `texted` and the B parts of the libraries; linked with the host-built assembly objects, the programs run |
| 4 | `BASM.PRG`: `ENC` and the label table, on top of the shared modules from phase 3 | e2e: `runtime.basm` and every library `.basm` module assembled **on the BC64** give `.o` files byte-identical to `bc81asmc --obj`; an assembly program goes texted → `basm` → `blink` → run. From here the whole library set can be rebuilt on the BC64 |
| 5 | `bdio_chain` + chained commands in the shell, `bcc NAME` chains through `bcc2`, `bcc3` and the linker | one command from source to a running program |
| 6 (optional) | self-hosting: BASM, BCC–BCC3 and BLINK build their own sources on the BC64; overlays in the linker | the tools built on the BC64 are byte-identical to the host-built ones |

Phases 0–2 are worth doing even if the BC64 compiler is never finished. They fix a
data-loss bug, deliver roadmap item 5a (#16) and free about 20 KB on the system disc.

## Risks and open questions

- **The pass sizes are estimates.** BLINK (phase 2) is the first real measurement of a B
  tool's size. The first step of phase 3 is a spike: BCC (reader, lexer and `#define`
  table) built and measured, before the parser is written. If it's far
  over 8 KB of own code, BCC2's estimate is wrong too: plan a fourth pass from the start.
- **Byte-identical output** means BCC3 and BASM must copy every host code-generation and
  encoding quirk (the
  constant shortcuts, the order of operands for commutative operators). If that proves too
  costly, fall back to comparing program output, which is a weaker test.
- **Disc space for the development disc.** Boot, catalog and `BDOS.SYS` take 184 sectors;
  `LS`, `CP`, `RM`, `TEXTED` and `CAT` 358 more; BCC–BCC3 about 335 (about 42 KB of code
  with today's libraries); BASM about 165; BLINK about 110; libraries and headers about
  150. That's about 1,300 sectors: **well over** a 1,024-sector disc. After phase 1,
  dead-code elimination removes about 4 KB of libraries from each tool and about 20 KB from
  the utilities, giving about 980 sectors: it **only just fits**. BASM isn't needed to
  compile B, so it can go on a separate assembler disc: the development disc is then about
  850 sectors after dead-code elimination, with room to spare. Leaving `CAT` off (62
  sectors) gives a little more. The bigger discs of roadmap item 7 would remove the problem.
  Each tool and pass carries its own copy of the libraries, so phase 1 matters a lot here.
- **Decided (2026-11-09):**
  - the compiler may have 2 or more passes, whatever keeps each one well under 32 KB;
  - the file system isn't extended for this plan. A 2-byte file length (catalog v2) is
    plan B, not plan A.
- **Decided (2026-11-10), replaced on 2026-11-11:** the compiler handles `asm "…"` text
  with an encoder it shares with BASM, and BASM comes before the compiler.
- **Decided (2026-11-11):**
  - assembly code lives in `.basm` modules. The assembler and the compiler write the same
    object format, and the linker joins them;
  - assembly routines follow the B calling convention, which becomes a frozen ABI, with
    `F_name` symbols for B functions;
  - the compiler keeps only a raw-byte `asm` statement and contains no assembler;
  - BASM runs on the BC64 as its own phase, after the compiler.
- **Decided (2026-11-13):** the object format is a stream of `tag, length, content`
  records of at most 255 content bytes, with no index. Fixes are offset lists after each
  `CODE` record, one tag per kind, with 16-bit targets kept in the placeholder and a
  combined `HILO` kind for `.mv`. See [object format](#object-file-format).
- **Decided (2026-11-13):** work discs: drive A holds the tools and libraries and is only
  read; sources, objects and the program are all on drive B. `blink` takes one name; the
  other objects come from `#link` lines, stored as `NEED` records. Every object needs a
  `#link`; a header's name implies nothing.
- **Decided (2026-11-13):** `#code`, `#heap` and `#codelimit` stay in the source and are
  passed through the compiler to the linker (`ad` records). `blink` has no address options.
- **Decisions still open for the owner:**
  1. Is texted's record format the official source format (recommended: yes, and the
     reader also accepts plain lines)?
  2. Keep today's precedence quirks in B 1.4 (recommended)?
  3. Is self-hosting (phase 6) a goal, or is compiling user programs and libraries enough?
  4. Does the host `bc` drop `asm "…"` once the libraries are moved (recommended), or keep
     it as a host-only extension?

## Appendix: measurements

All on the `bc64` branch at `c433c1e`, 2026-11-09, from `src/`:

- **Program sizes:** sizes of the committed `src/bdos/*.sector(s)`. The empty program and
  the library-only program were compiled with `bc.py`, assembled with `bc81asmc.py`, and
  converted with `ftool.py btap2bin`.
- **Assembly sizes:** `wc -c src/bdos/texted.basm src/bdos/bdos.basm`.
- **Labels and functions:** counted in `src/bdos/bdos.basm` (`F…`, `LABEL…`, `DATA…`).
- **`asm` lines:** `grep -c 'asm "' src/bdos/*.b`. The functions were classified by a
  script: a function counts as "assembly with a B header" when every statement that isn't
  `asm` is a bare variable, a declaration or a `return`.
- **Raw `asm` encodings:** a test file assembled with `bc81asmc.py --btap` and converted with
  `ftool.py btap2bin`.
- **`#define`s and function names:** `grep` over `src/bdos/*.b`.
- **Allocation bug:** reproduced on a copy of `os.bdd`. Run `cat -c test.b`, then
  `rm hellowrd.prg`, then texted (`i 10 10`, `hello`, an empty line, `s new.txt`, `q`),
  then `ls -a` and `cat -c test.b` on the headless emulator. `NEW.TXT` is at 34/00, the
  first sector of `TEST.B`, and `TEST.B` starts with the record `10 hello`.
- **Emulator speed:** from [README.md](README.md) (key numbers).
