# Compiler (bc, B language): analysis

Reference: [../03-compiler.md](../03-compiler.md). Decisions: C1–C5, G4 in
[../specs/memory/design-decisions.md](../specs/memory/design-decisions.md).

## Current state

- About 1,800 lines: a text preprocessor, a parsy grammar, an AST that emits assembly
  text, and an assembly runtime of about 560 lines. v1.3.1 (240927) uses the native bc8183
  16-bit ALU and relative calls and jumps.
- It compiles about 5,100 lines of real B code: bdos (18.5 KB) plus 8 programs on the disc.
  The project's central goal ("a language compiler working for it") is reached for the host
  side.
- **It doesn't run on Linux or Python ≥ 3.13 as committed**, because of
  `from msilib.schema import Error` in `bc_ast.py`.
- Tests: `bc_tests.py` has 21 grammar tests; **15 pass, 6 fail** (with a stand-in for
  `msilib`). The failing tests expect older AST shapes and names (`statement_if`,
  pre-precedence `EXPRESSION_TERM`). **There are no code-generation tests.**

## Development direction (roadmap)

- **Item 5:**
  - "new optimization to drop unused code": dead-code elimination;
  - "managing stacks inside subroutines": cheaper variable and frame handling.
- **Item 9:** a compiler running on the BC64. This needs much smaller output and a
  compiler written in B. It's a long way off.
- The code-size work in `history.txt` (38% in v0.6, then commutative and constant
  optimisations) shows the direction: **size first**.

## Problems

| # | Problem | Evidence | Impact |
|---|---|---|---|
| 1 | Windows-only import | `bc_ast.py:4` `from msilib.schema import Error` | the compiler and its tests don't start on Linux/macOS or Python 3.13+ |
| 2 | Large output, no dead-code elimination | "Hello world" is **1,665 bytes**; all functions of every `#include`d library and the full runtime are emitted | bdos and apps waste memory; blocks item 9 |
| 3 | Every variable access is a subroutine call | `cal :stackvar8gt16` and friends for each read and write | size and speed overhead in all generated code |
| 4 | Stale tests, no codegen tests | 6/21 grammar tests fail; nothing checks the output `.basm` | any optimisation is a blind change |
| 5 | Surprising semantics | comparisons bind looser than `&&`/`\|\|`; a unary operator applies to the whole rest of the expression; `\|\|` is bitwise | bugs in user code; every comparison must be parenthesised |
| 6 | `return` only reliable at the end of a function | `bugs.txt`; the bdos code works around it with a `result` variable | verbose code |
| 7 | `#define` is substring replacement | `newline.replace(key, val)` on every line, including strings and identifiers (`NULL` vs `NULLCHAR` is only safe thanks to the reverse sort) | silent corruption when names overlap |
| 8 | Missing language features | no `for`/`break`/`continue`, arrays/indexing, structs, signed numbers, negative literals, block scopes, type checking | verbose `peek`/`poke` code; locals must be unique per function |
| 9 | Noisy output | `print('TERM …')`, `print("PUSH SCOPE …")` etc. are printed on every compile regardless of `--verbose` | real errors are hard to spot |
| 10 | Stale runtime definitions | `.def var_promptbuf 0x0bcf`, `var_user_mem 0x0bcb` (bcOS 1.1 addresses) in `bc_stdlib.py` | a trap for future runtime code |
| 11 | Diagnostics | errors print preprocessed-line numbers (the `.genb` file), not the original file and line | hard to map back to the source |

## Proposals

### Next steps

1. **Replace the `msilib` import** (`Error = Exception`), and gate the debug prints behind
   `--verbose`. This is part of issue #1.
2. **Repair the grammar tests**, and add **golden code-generation tests**: compile
   `src/bc/code/*.b` and the bdos programs and compare against committed `.basm`. Also
   **track code size** per program in CI, so optimisations are measured the way
   `history.txt` already does by hand.
3. **Dead-code elimination (item 5a):**
   1. build a call graph from `main`, including calls made inside `asm` strings to
      `:F…` labels and the runtime;
   2. emit only reachable functions and data;
   3. split `bc_stdlib.py` into per-routine fragments with declared dependencies, and emit
      only the ones used.

   Expect "hello world" to drop well below 1 KB and every app to shrink.

### Improvements

4. **Cheaper frames (item 5b):** read and write variables with an inline sequence, e.g.
   keep the frame base in `dsdi` and use `add`/`mov #dsdi` directly, instead of calling
   `stackvar*`. Do it for short offsets first, and measure with the size tracking from
   step 2.
5. **C-like precedence and unary scope**, behind a check. Every existing program is
   parenthesised already, so compile all sources before and after and require identical
   `.basm`. Bump the language version.
6. **Token-based `#define`**: replace only whole identifiers, outside string literals. The
   `asm` strings need a decision: keep replacing inside them, since bdos relies on it
   (`asm "mov ci, PRINTF_FORMATCHAR"`).
7. **Language additions, in order of payoff:**
   1. `return` anywhere;
   2. `break`/`continue`;
   3. `for`;
   4. byte/word indexing `p[i]` (sugar for `peek`/`poke`);
   5. block scopes.

   Signed arithmetic and structs only if a real program needs them.
8. **Source-mapped diagnostics**: keep `(file, line)` through `#include`, and report errors
   and `.basm` comments with original positions.
9. **Clean up the runtime**: remove the stale `.def`s, and decide per routine whether to
   call bcOS through `os_metacall` (smaller) or carry a private copy (faster). Today the
   choice looks accidental.

## Modernisation verdict

**Keep the architecture, modernise the engineering:**
- portability (`msilib`);
- tests (golden and size);
- diagnostics.

The single-pass emit-to-text design is right for the project's size. The big gains come
from dead-code elimination and the frame model (roadmap item 5), not from a rewrite. A
self-hosted compiler (item 9) should be a separate, much smaller B implementation, not a
port of this one.
