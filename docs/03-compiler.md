# bc: compiler for the B language

`src/bc/` compiles **B**, a small C-like language, into bc81asmc assembly (`.basm`) for the
bc8183 CPU. The current version is **v1.3.1 (240927)**. It is written in Python with
[parsy](https://pypi.org/project/parsy/). bdos, all of its utilities and the user apps are
written in B.

| File | Contents |
|---|---|
| `bc.py` | CLI, preprocessor, top-level compile step |
| `bc_grammar.py` | parsy grammar for expressions, statements and functions |
| `bc_ast.py` | AST node classes, each with `emit()`: scopes, variables, code generation, constant-operand optimisations |
| `bc_stdlib.py` | assembly runtime library appended to every program |
| `bc_dbg.py`, `bc_tests.py` | debug helper, unit tests |
| `grammar.txt`, `history.txt`, `bugs.txt` | design notes, code-size optimisation history, known bugs |
| `code/` | small test programs (`declarations.b`, `functions.b`, `funrec.b`, `stdmemtest.b`, …) |

## Usage

From `src/`:

```bash
./bcc bdos/helloworld          # compile helloworld.b -> .basm, then assemble -> .btap
bcc bdos/helloworld            # the same console command (after `pip install -e .`), any directory;
                               # the path is given without .b, relative to the current directory
```

That is the same as running:

```bash
python bc/bc.py --verbose bdos/helloworld.b       # -> bdos/helloworld.basm (+ .genb)
python bc81asmc/bc81asmc.py bdos/helloworld.basm  # -> bdos/helloworld.btap
```

- `--verbose` also writes the preprocessed source to `<name>.genb`. `--btap` is obsolete.
- On a parse error the compiler prints the lines around the failure, numbered as in the
  preprocessed source.
- Python dependency: `parsy`, the only one. The compiler runs on Python >= 3.10 on Linux,
  macOS and Windows (tested on 3.10, 3.13 and 3.14). Output files are written as UTF-8.

## Preprocessor

The preprocessor works line by line, before parsing:

| Directive | Effect |
|---|---|
| `#include file.b` | paste the file in (path relative to the **main** source file's directory) |
| `#define NAME value` | plain text replacement in every later line. `value` is the last space-separated token. Longer names are replaced first, and replacement also applies inside strings and `asm` text |
| `#code 0xHHHH` | address of the code (`.org`). Default `0x1000`; bdos programs use `0x6000` |
| `#heap 0xHHHH` | start of the heap used by `malloc`. Default `0x3000` |
| `#codelimit 0xHHHH` | optional second limit: the program's image must end below this address. Reset for every compile, so it has no default. `bdos.b` uses `0x5d00` |
| `// …` | a line starting with `//` is dropped |

## Language

### Types

| Type | Meaning |
|---|---|
| `word` | 16-bit unsigned |
| `byte` | 8-bit unsigned |

Every expression is evaluated as 16 bits. The type only decides how many bytes a variable
takes; assigning to a `byte` stores the low byte. Types aren't checked otherwise.

### Literals

- decimal `123`, hex `0x1f`, `0xABCD`, character `'A'`
- `"string"`: there are no escapes. The string goes into the data segment with a `0x00`
  terminator, and the expression evaluates to its address.
- There are no negative literals and no unary minus.

### Operators

From tightest to loosest binding. Operators on the same level evaluate left to right.

| Level | Operators | Notes |
|---|---|---|
| 1 | `#e`, `!e`, `~e` | `#` reads the 16-bit big-endian word at address e; `!` is logical not (result 0/1); `~` is bitwise not. **A unary operator applies to the whole rest of the expression**, so `!a = b` means `!(a = b)` |
| 2 | `*` `/` `%` | 16-bit hardware mul/div/mod |
| 3 | `+` `-` | |
| 4 | `&` `\|` | bitwise |
| 5 | `<<` `>>` | |
| 6 | `&&` `\|\|` | `&&` gives 0/1; `\|\|` is a bitwise OR (truthy, not normalised to 1) |
| 7 | `<` `<=` `>` `>=` | unsigned, result 0/1 |
| 8 | `=` `!=` | `=` is **equality**, result 0/1 |

> The precedence is unusual: comparisons bind *looser* than `&&`/`||`, and shifts bind
> looser than `&`/`|`. Write `(a > 0) && (b = 1)` with parentheses; that's what the bdos
> sources do.

Function calls are written `name(arg, arg, …)`. The argument list can span several lines.

### Statements

| Statement | Syntax |
|---|---|
| variable declaration | `word name;` / `byte name;` |
| assignment | `name <- expression;` |
| expression | `expression;`: a call, or a bare variable to load its value into `csci` for the next `asm` |
| if / else | `if (e) { … } else { … }`. `else` may be followed by a single statement, so `else if (…) {…}` works |
| while | `while (e) { … }` |
| return | `return expression;` |
| inline asm | `asm "mov a, #csci";`: the text is copied verbatim into the output |
| comment | `// …` |

There is no `for`, `break`, `continue`, arrays, structs or pointer types. Memory is accessed
through `#addr` and the `peek8/peek16/poke8/poke16` library functions.

### Functions

```c
byte add(word a, word b)        // definition
{
    return a + b;
}

byte later(word x);             // forward declaration (no body)

byte printf(word PformatStr)*** // variadic: extra args become word params P1, P2, …
{ … }                           // and "<name>PLEN" holds the argument count
```

- The program must define `main`. It is called from the generated entry point, and the
  program ends with `ret` (so it returns to bcOS `r` or to the bdos shell).
- A function's return value is whatever is in `csci` when it returns: the value of
  `return e`, or the last evaluated expression. `peek8` and similar functions rely on this.
- `bugs.txt` says `return` should be the last statement in a function and doesn't work inside
  nested blocks. The bdos code follows this by assigning a `result` variable and returning
  it at the end.
- Blocks don't open a new scope: all locals of a function share one scope, so names must be
  unique within a function.
- Recursion works, because every call gets its own frame (see `code/funrec.b`).
- Top-level `word x;` / `byte x;` declarations are accepted as globals, stored in the base
  frame.
- Assembly labels are `F<NAME up to 10 chars><id>`. Data labels are `DATAxxxx` and jump
  labels `LABELxxxx`.

## How the generated code works

- **Registers:** an expression's result is left in `csci`, and the right-hand operand of a
  binary operator in `dsdi`. Intermediate values are pushed on the CPU stack. If the right
  operand of a commutative operator is a constant, it is loaded straight into `dsdi`, which
  skips a push/pop. Comparisons with constant `0` are shortened.
- **Variables:** variables don't live on the CPU stack. They live in a separate **software
  stack** whose pointer is `sys_stackhead`, placed just after the program image and growing
  upwards. A call moves `sys_stackhead` forward by the caller's frame size, stores the
  arguments as the callee's first locals, `cal`s the function, then moves it back. Variables
  are read and written relative to `sys_stackhead` through runtime helpers
  (`stackvar8gt8/16`, `stackvar8st8/16` for offsets up to 127, `stackvarget/set8/16` for
  larger ones). The CPU stack (from the top of memory downwards) holds only return addresses
  and temporaries.
- **Heap:** `sys_heaphead` is set to the `#heap` address at start-up. `stdmem.b`
  implements `malloc`/`mfree` on top of it.
- **Program layout:** the output is laid out in this order: `.org #code`, the entry point
  (init stackhead and heaphead, `cal main`, `ret`), the functions, the data segment
  (strings), the runtime stdlib, `sys_heaphead`, then `sys_stackhead`, then the `sys_codeend` label.
- **Build-time checks:** the last line is `sys_codeend: .assert :sys_codeend < 0x<heap>`, so the
  assembler fails the build if the image reaches the `#heap` address. The label costs no bytes.
  With `#codelimit 0xHHHH`, a second line `.assert :sys_codeend < 0xHHHH` checks the same label
  against that limit. A failure is reported as `assertion failed` (see [02-assembler.md](02-assembler.md)).

### Runtime stdlib (`bc_stdlib.py`, assembly)

| Group | Routines |
|---|---|
| OS bridge | `os_metacall`-based calls into bcOS (see [04-bcos.md](04-bcos.md)) |
| Printing / errors | `fatal`, `printhex4/8/16`, `print_newline`, `printstr` |
| Memory | `poke16`, `peek16`, `mfill`, `mem_cpy`, `mseek` |
| Strings and parsing | `readstr`, `nextword`, `nextval8`, `upchar`, `str_cpy`, `str_len8`, `strncpy`, `parsehex4/8/16` |
| Comparisons | `gt16`, `gteq16`, `eq16` |
| Variable stack | `stackoffscalc`, `stackoffsclc8`, `stackheadroll`, `stackheadrll8`, `stackvarget8/16`, `stackvarset8/16`, `stackvar8gt8/16`, `stackvar8st8/16` |
| Runtime data | `sys_stdprntf`, `sys_seektmp`, `sys_heaphead`, `sys_stackhead` |

## B libraries (in `src/bdos/`)

| File | Functions |
|---|---|
| `std.b` | `TRUE/FALSE`, `peek8`, `peek16`, `poke8`, `poke16`, `parsedecw`, `mfill`, `mzero`, `memcpy` |
| `stdio.b` | `putc`, `putb`, `putw`, `putwnl`, `putnl`, `puts`, `putsnl`, `putdigit`, `putdecw`, `putdecwnl`, `readsn`, `printf` |
| `stdmem.b` | `malloc`, `mfree`, `mcompact`, `mhead`, `mtotal` (`NULL`) |
| `strings.b` | `strpeek8`, `strpoke8`, `strnlen8`, `strcpy`, `strncpy`, `strncmp` (`STRCMP_EQ/LT/GT`), `strnposc`, `strnextword`, `upchar`, `upstring`, `strndecw` |
| `bdosh.b` + `bdioh.b` | bdos system-call wrappers and constants (see [05-bdos.md](05-bdos.md)) |
| `bdostools.b` | `bdio_fnormalize`: `name.ext` → the space-padded 8+3 catalog form |

`printf` format codes: `%s` string, `%w` hex word, `%x` hex byte, `%n` newline.

## Example

```c
#code 0x6000
#heap 0xf000

#include std.b
#include stdio.b

byte main()
{
    putsnl("Hello world!");

    word a;
    a <- 10;

    putdecwnl(a);
}
```

## Code-size history

From `bc/history.txt`:
- dedicated stack-head subroutines cut code size by 38% (v0.6);
- in v1.2.0, commutative-operand and constant-loading optimisations shrank bdos from 14339
  to 13063 bytes;
- the bc8183 port replaced library calls for `+ - * / %` and the bitwise operators with
  native 16-bit instructions.
