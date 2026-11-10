# Assembler Modernisation: `.assert` Directive to Enforce Memory-Map and ABI Addresses — Plan

**Plan Status**: `FINAL`

**Story Type**: `Internal`

**Plan Revision**: `A0`

> This plan captures **what** to build and **why**. It deliberately does **not** contain
> implementation code, pseudocode, line numbers or test bodies. The implementation agent
> discovers the **how** against live code.

---

## 1. Problem Statement

*   **Context**: nothing checks the address contracts of design decisions G1 (ABI: `os_metacall`
    at `0x0008`, `os_metatab` at `0x000c`) and G2 (fixed memory map). Today bcOS ends at `0x0d6b`
    (`user_mem` at `0x0d6a`), 21 bytes below the bdio variables at `0x0d80`. The boot loader is
    exactly 128 bytes (`0x0e00`–`0x0e7f`), the full boot sector. bdos ends at `0x52fb`, below the
    file buffers at `0x5d00`. Every program image ends below its `#heap`. An overflow assembles
    fine and corrupts memory silently at run time.
*   **Goal**: an `.assert` directive in `bc81asmc`, evaluated in pass 2, that stops the build
    with a positioned diagnostic (the #10 reporting) when a contract is broken. `boot.basm` and
    every compiler-generated `.basm` carry asserts.
*   **In scope**: the directive (grammar, AST node, pass-2 evaluation, diagnostics); asserts in
    `boot.basm`; compiler-emitted asserts (image end < `#heap`, and for bdos image end <
    `0x5d00`); a test that shows that moving `os_metacall` or growing bcOS past `0x0d80` fails
    the build; docs.
*   **Out of scope**: committing asserts into `bcos.basm` (that is #30, which builds on this);
    any expression language (labels ± offsets, `hi()`/`lo()`, analysis improvement 6); `.include`.

### 1.1 Technical Summary

*   New directive `.assert <operand> <op> <operand>`. An operand is `:name` (a label or a `.def`
    constant, resolved like any reference) or a hex literal (`0xHHHH` or `0xHH`). The operators
    are `=`, `!=`, `<`, `<=`, `>`, `>=`. Nothing else.
*   It emits no bytes and does not move the address. It is evaluated in pass 2, after every label
    is known, so it may reference labels defined later in the file.
*   A false assert is a positioned `error` diagnostic. All diagnostics are collected, the run exits `1`
    and no `.btap` is written, like every other assembler error since #10.
*   The compiler appends an end-of-image label and asserts after the runtime. A new optional
    `#codelimit 0xHHHH` preprocessor line adds a second limit; `bdos.b` uses it for `0x5d00`.
*   All binaries stay byte-identical. Only the generated `.basm` files gain lines.

---

## 2. Architecture & Design

### 2.1 Architecture Overview

#### Involved services & owners

| Component | Technical Owner |
| :--- | :--- |
| assembler `bc81asmc` (`src/bc81asmc/`) | bcichonski |
| compiler `bc` (`src/bc/`) | bcichonski |
| bdos boot loader / bdos (`src/bdos/`) | bcichonski |

#### C2 diagram

```
 .b ──bc (preprocess #code/#heap/#codelimit; emit … runtime … end label + .assert lines)──► .basm
 .basm ──bc81asmc pass 1 (ASSERT node: no bytes, records itself)──► pass 2 (patch refs, then
        evaluate every recorded ASSERT)──► .btap   |  any false/undefined ──► diagnostics, exit 1, no .btap
```

#### Flow diagram

```
pass 1: line ─► ASSERT? ─► remember (node, address context) ; emit nothing
pass 2: patch label refs (unchanged)
        for each ASSERT: resolve both operands (.def first, then label; literal as is)
           ├─ an operand undefined ─► "undefined label ':x'" at the operand's ':'  (no evaluation)
           ├─ comparison true      ─► nothing
           └─ comparison false     ─► "assertion failed: …" at the line
        diagnostics? ─► sort by position, raise AssemblerError
```

### 2.2 External Contracts & Evidence

N/A — Internal story.

### 2.3 Affected Areas

| Area / File (pointer) | Role in this change | Likely action |
| :--- | :--- | :--- |
| `src/bc81asmc/bc81asmc_grammar.py` (`directive`, `dDEF`, `labelarg`, `heximm16`/`heximm8`, `pos`/`sourcename`) | parses directives; operand references carry `.line`/`.col` | Change: add `dASSERT` to `directive` |
| `src/bc81asmc/bc81asmc_ast.py` (`Directive`, `DEF`, `CodeContext`, `label_name`) | AST node per directive, `emit(context)` | New: `ASSERT` dataclass, emits nothing |
| `src/bc81asmc/bc81asmc.py` (`compile()`) | pass 1 / pass 2, symbol tables, diagnostics | Change: evaluate asserts after the pass-2 patching |
| `src/bc81asmc/bc81asmc_diag.py` | `Diagnostic`, `AssemblerError` | Reference: report through it |
| `src/bc81asmc/*_tests.py` | assembler suites (`bc81asmc_compile_diag_tests.py`, `bc81asmc_cli_tests.py` are the models) | New test file(s) |
| `src/bc81asmc/bcOS/bcos.basm` (`os_metacall`, `os_metatab`, `user_mem`) | the ROM whose contract the AC test exercises; **not edited** (#30) | Reference (read by a test) |
| `src/bdos/boot.basm` | boot loader, `.org 0x0e00`, 128 bytes | Change: end label + asserts |
| `src/bc/bc.py` (`preprocess()`, `#code`/`#heap` module globals, `compile()`) | preprocessor, compile driver | Change: `#codelimit` |
| `src/bc/bc_ast.py` (`Context`, `add_stdlib`, `PROGRAM.emit`), `src/bc/bc_stdlib.py` (template ends with `sys_stackhead: nop`) | where the generated `.basm` ends | Change: emit end label + asserts last |
| `src/bc/bc_codegen_tests.py` | compiler codegen tests | Add tests |
| `src/bdos/bdos.b` | bdos source (`#code 0x0f00`, `#heap 0x5fd0`) | Change: add `#codelimit 0x5d00` |
| `src/bdos/{bdos,ls,cp,format,rm,cha,cat,helloworld,texted}.basm` | committed generated outputs of `buildos`/`buildtools`/`buildapps` | Regenerate (asserts appear; `.btap`/`.sector(s)`/`os.bdd` unchanged) |
| `docs/02-assembler.md`, `docs/03-compiler.md`, `docs/specs/memory/design-decisions.md` (A2, A3, A6, G2), `src/bc81asmc/CLAUDE.md`, `src/bc/CLAUDE.md`, `src/bdos/CLAUDE.md`, `docs/analysis/02-assembler.md` | reference docs and decision records | Update |

### 2.4 Key Algorithms & Behaviour

*   **Syntax**: `.assert` then left operand, operator, right operand, separated by optional blanks
    (`.assert :user_mem <= 0x0d80` and `.assert :a<=0x0d80` both parse). An optional label before
    `.assert` and a trailing comment are allowed, as on any line. Lowercase only, like the rest
    of the language. The operator alternatives are ordered longest first (`<=` before `<`,
    `>=` before `>`, `!=`), per the grammar rule in `src/bc81asmc/CLAUDE.md`. A 16-bit literal is
    tried before an 8-bit one. Anything else (`==`, `:a+0x01`, a decimal number) is a syntax error.
*   **Operands**: `:name` resolves exactly like a pass-2 reference: `.def` table first, then the
    label table. A symbol whose value is `0x0000` is defined. A literal is its integer value.
    Comparison is unsigned on plain integers (all values are 0..0xffff).
*   **Emission**: the node emits no bytes and leaves the address and nibble state untouched. A
    label on an `.assert` line gets the current address, which makes "end of image" labels
    possible without emitting anything. Assembling a file with and without asserts gives the
    identical `.btap`.
*   **Evaluation timing**: pass 2, after all placeholders are patched. Forward references work.
    Every assert is evaluated even when other errors were found, so one run reports everything.
*   **Undefined operand**: one `undefined label ':name'` diagnostic per undefined operand, at the
    operand's `:`, the same message and placement as other references. The assert is then not
    evaluated (no second "assertion failed" diagnostic for it).
*   **Failure diagnostic**: message
    `assertion failed: <left> <op> <right> (0xLLLL <op> 0xRRRR)`, where `<left>`/`<right>` are
    the operands as written (`:name` or the literal) and the parenthesised part shows the
    resolved values as 4-digit hex. Column = the first non-blank character of the line (the
    same as `cannot encode` and the overflow error). It goes through `bc81asmc_diag.py`
    (`Diagnostic` + `AssemblerError`); `main()` prints it and exits `1`, and no `.btap` is
    written.
*   **`--verbose`**: pass 1 prints the node like other directives, via a readable `__str__`.
*   **Compiler end label**: after the runtime's last line (`sys_stackhead: nop`), the compiler
    emits a line labelled `sys_codeend` that carries the heap assert, so the label is the first
    address after the image:
    *   always: `.assert :sys_codeend < 0xHHHH` with the `#heap` address (default `0x3000`);
    *   when the source has `#codelimit 0xHHHH`: a second line `.assert :sys_codeend < 0xHHHH` with that
        address.
    Strict `<` as in the issue ("code end < `#heap`").
*   **`#codelimit`**: parsed like `#code`/`#heap` (the line is consumed and doesn't reach the
    `.genb`), with a progress print in the same style. A source without it gets no limit
    assert, even when an earlier compile in the same Python process set one. Tests call
    `bc.compile`/`preprocess` repeatedly, so it must not leak through the module global.
*   **`boot.basm`**: a label for the first address after the loader (after `bd_diskver`), on an
    `.assert` line checking it is `<= 0x0e80` (the 128-byte sector from `.org 0x0e00`;
    `bd_sectsize` is `0x0080`). The loader currently ends exactly at `0x0e80`, so `<=` is
    required. Asserting `.def` constants against their own literal (`os_metacall`, `bd_shell`) would
    be a tautology, so none are added.
*   **AC-4 test (bcOS contract)**: a test reads the committed `bcos.basm`, appends the issue's
    three asserts (`:os_metacall = 0x0008`, `:os_metatab = 0x000c`, `:user_mem <= 0x0d80`) **in
    memory**, and shows:
    *   unmodified: it assembles with no diagnostics;
    *   one extra byte (e.g. a `nop`) inserted before `os_metacall`: an assertion failure for
        `os_metacall` (and `os_metatab`);
    *   enough padding inserted before `user_mem` to push it past `0x0d80` (it is at `0x0d6a`
        today, so 23 bytes): an assertion failure for `user_mem`.
    The test derives positions from labels, not line numbers. `bcos.basm` stays unedited.

---

## 3. Key Decisions & Assumptions

*   **D1 — Operand set**: `:name` (label or `.def`) and hex literals of 8 or 16 bits. No
    expressions. This is the exception to A3, and the only one: A3 gains a note that `.assert`
    is a check, not an expression language, and emits no bytes.
*   **D2 — `=` is equality** (not assignment, and `==` isn't accepted), as written in the issue.
*   **D3 — Failure column** = first non-blank character of the line, consistent with
    the line-level diagnostics of #10. An undefined operand reports at its `:`, consistent with
    every other reference.
*   **D4 — End-of-image label on the assert line.** A label on a directive line takes the current
    address, so the end label costs no bytes and needs no `nop`. Names: `sys_codeend`
    (compiler; checked unused in `src/` and `docs/`) and a `bd_`-prefixed name in `boot.basm`
    (the agent picks one unused in that file).
*   **D5 — bdos limit via `#codelimit 0xHHHH`** (Assumption A-1, closed below). The issue asks
    the compiler to emit "for bdos, code end < `0x5d00`". bdos's `#heap` is `0x5fd0`, so the
    heap assert does not cover it. Two alternatives were rejected. Special-casing
    `#code 0x0f00` in the compiler hides a memory-map fact in the compiler. An inline
    `asm ".assert …"` in `bdos.b` would couple B source to the compiler-internal
    `sys_codeend` name and sit mid-function. A per-program preprocessor line next to `#code`/`#heap`
    is explicit, generic and matches the existing style. `bdos.b` has `BDIO_FDESCBUF_ADDR`
    (`0x5d00`) in `bdioh.b`, but `#` lines are handled before `#define` replacement, so the
    literal `0x5d00` is used, with a comment naming the constant.
*   **D6 — Strict `<` for the compiler asserts**, `<=` for the boot sector and `user_mem`, as in the
    issue. All current programs pass with margin (largest: texted ends `0x97e6` vs heap
    `0xa000`; bdos ends `0x52fb` vs `0x5d00`).
*   **D7 — Generated `.basm` regeneration**: only the programs the build scripts build
    (`bdos` via `buildos`; `ls cp format rm cha cat` via `buildtools`; `helloworld texted` via
    `buildapps`). `debug.basm`/`fddtest.basm` are not built by any script and are stale (org
    `0x1000`); leave them untouched.
*   **Assumption A-1** (no correctness risk): the owner accepts a new compiler preprocessor
    directive for the bdos limit. Resolution: the issue text puts the bdos limit under "the
    compiler emits", and the analysis doc's minimal-language concern (A3) is about the
    assembler. The directive is optional, so existing programs are unaffected. Recorded so the
    reviewer can veto it in the PR. It does not block.

### 3.1 Decision Lock (Constants & Policies)

| Constant / Policy | Selected Value | Why | Where it lives |
| :--- | :--- | :--- | :--- |
| Directive keyword | `.assert` | issue | grammar |
| Operators | `=` `!=` `<` `<=` `>` `>=` | issue | grammar |
| Failure message | `assertion failed: <l> <op> <r> (0xLLLL <op> 0xRRRR)` | shows the contract and the actual values | `compile()` |
| Compiler end label | `sys_codeend` | unused name, `sys_` runtime prefix | generated `.basm` |
| Heap assert | `.assert :sys_codeend < 0x<heap>` | issue | generated `.basm` |
| bdos limit | `#codelimit 0x5d00` in `bdos.b` | D5 | `bdos.b` |
| Boot assert | end label `<= 0x0e80` | 128-byte sector, loader is 128 bytes today | `boot.basm` |
| bcOS contract (test only here) | `:os_metacall = 0x0008`, `:os_metatab = 0x000c`, `:user_mem <= 0x0d80` | issue; committing them is #30 | assembler test |

### 3.2 Open Questions

No open questions.

---

## 4. Task Breakdown

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| `T1` | `.assert` directive in the assembler | — | `Medium` |
| `T2` | Boot-loader asserts and the bcOS contract test | `T1` | `Medium` |
| `T3` | Compiler-emitted asserts, `#codelimit`, regenerated `.basm` | `T1` | `Medium` |
| `T4` | Documentation and decision records | `T2`, `T3` | `Low` |

### T1 — `.assert` directive in the assembler

*   **Goal**: `bc81asmc` parses `.assert`, emits nothing for it, and evaluates it in pass 2
    with positioned diagnostics (§2.4).
*   **Depends on**: —
*   **Complexity**: `Medium`
*   **Pointers**: `src/bc81asmc/bc81asmc_grammar.py`, `bc81asmc_ast.py`, `bc81asmc.py`
    (`compile()`), `bc81asmc_diag.py`; `src/bc81asmc/CLAUDE.md` (grammar ordering, diagnostics
    rule).
*   **Definition of Done**:
    *   the grammar accepts the §2.4 syntax with all six operators, both literal widths, `:name`
        operands, optional label and comment; it rejects `==` and expressions as syntax errors;
    *   the node emits no bytes, and a label on its line gets the current address;
    *   pass-2 evaluation as in §2.4 (forward refs, `.def` before label, undefined-operand
        diagnostic, failure message/column, every assert evaluated, sorted diagnostics, exit 1 and
        no `.btap` from the CLI);
    *   every committed `.basm` still assembles to an identical `.btap` (none contain `.assert` yet).
*   **Tests expected** (assembler suite, new `*_tests.py` file in `src/bc81asmc/`): grammar
    (each operator, both literal widths, label + comment on the line, rejected forms); emit (no
    bytes; same output with/without asserts; label on the assert line = current address);
    `compile()` (passing asserts with label/`.def`/literal operands, forward reference, each
    operator true and false, failure message and position, several failures all reported and
    sorted with other errors, undefined label in an assert → one `undefined label` at the `:`
    and no assertion diagnostic, `0x0000`-valued symbol counts as defined); CLI (failed assert →
    stderr block, exit 1, no `.btap`).
    Commands that must pass before returning:
    `cd src/bc81asmc && python3 -m unittest discover -s . -t . -p "*_tests.py"` and
    `python3 run_tests.py < /dev/null` from the repo root.
*   **Tests to modify**: None

### T2 — Boot-loader asserts and the bcOS contract test

*   **Goal**: `boot.basm` carries its sector-size assert. A test proves that the bcOS ABI and
    memory-map asserts from the issue catch a moved `os_metacall` and a bcOS grown past
    `0x0d80` (AC-4).
*   **Depends on**: `T1`
*   **Complexity**: `Medium`
*   **Pointers**: `src/bdos/boot.basm` (CRLF, keep it); `src/bdos/boot.btap`;
    `src/bc81asmc/bcOS/bcos.basm` (read-only here); `src/buildos` (how boot is assembled).
*   **Definition of Done**:
    *   `boot.basm` has an end label on an `.assert` line checking it is `<= 0x0e80` (§2.4/D4);
    *   reassembling `boot.basm` gives a `boot.btap` byte-identical to the committed one, and
        `boot.sector`/`os.bdd` are unchanged;
    *   `bcos.basm`, `bcos.btap` and `bcos_v1_2_0.b81` are untouched.
*   **Tests expected** (assembler suite, `src/bc81asmc/`): the committed `boot.basm` assembles
    with no diagnostics. Adding one byte to the loader fails its assert. The committed
    `bcos.basm` plus the three issue asserts (in memory) assembles. One byte inserted before
    `os_metacall` fails with an assertion diagnostic naming `os_metacall`. Padding before
    `user_mem` that pushes it past `0x0d80` fails with one naming `user_mem`. Read the files
    relative to the test file, not the cwd. Commands that must pass before returning: the
    assembler suite command and `python3 run_tests.py < /dev/null`.
*   **Tests to modify**: None

### T3 — Compiler-emitted asserts, `#codelimit`, regenerated `.basm`

*   **Goal**: every compiled program ends with `sys_codeend` and its heap assert. `#codelimit`
    adds a second limit, and `bdos.b` uses it for `0x5d00`. The committed generated `.basm`
    files are regenerated and every binary is byte-identical.
*   **Depends on**: `T1` (the assembler must accept the new lines).
*   **Complexity**: `Medium`
*   **Pointers**: `src/bc/bc.py` (`preprocess`, globals `codeSegment`/`heapSegment`, `compile`),
    `src/bc/bc_ast.py` (`Context.add_stdlib`, `PROGRAM.emit`), `src/bc/bc_stdlib.py` (template
    tail), `src/bc/bc_codegen_tests.py` (patterns), `src/bdos/bdos.b`, `src/buildos`,
    `src/buildtools`, `src/buildapps`, `src/bcc` (CRLF; run `python3 bc/bc.py` +
    `python3 bc81asmc/bc81asmc.py` from `src/` instead).
*   **Definition of Done**:
    *   generated `.basm` ends with the `sys_codeend` heap-assert line, plus the `#codelimit` line
        when the source sets it (§2.4). It follows bc81asmc syntax (lowercase, fixed-width
        hex);
    *   `#codelimit` doesn't leak between compiles in one process; the `.genb` output is unchanged
        by it;
    *   `bdos.b` has `#codelimit 0x5d00` with a comment naming `BDIO_FDESCBUF_ADDR`;
    *   `bdos ls cp format rm cha cat helloworld texted` `.basm` are regenerated. Their diff
        against the base is only the added assert lines. Their `.btap`, `.sector(s)` and
        `src/os.bdd` are byte-identical to the committed ones (not re-committed if unchanged).
        If a regenerated `.basm` shows any other change, stop and report it instead of
        committing that churn. `debug`/`fddtest` stay untouched (D7);
    *   a program whose image would reach its `#heap` (or `#codelimit`) fails to assemble with the
        assertion diagnostic.
*   **Tests expected** (compiler suite, `src/bc/`): the generated `.basm` ends with the heap
    assert using the default heap address and a `#heap` address. `#codelimit` adds the second
    assert, and a following compile without it has none. The output assembles with the real
    assembler and its asserts pass. A program with `#heap` set below its image end fails to
    assemble with an assertion diagnostic. Commands that must pass before returning: `cd src/bc && python3
    -m unittest discover -s . -t . -p "*_tests.py"` and `python3 run_tests.py < /dev/null`.
*   **Tests to modify**: None

### T4 — Documentation and decision records

*   **Goal**: the docs describe `.assert`, `#codelimit` and the enforced contracts (AC-5).
*   **Depends on**: `T2`, `T3`
*   **Complexity**: `Low`
*   **Pointers**: `docs/02-assembler.md` (Directives table, How the two passes work, Errors
    table: new `assertion failed` row), `docs/03-compiler.md` (Preprocessor table: `#codelimit`;
    generated-code section: the end label + asserts), `docs/specs/memory/design-decisions.md`
    (A3: "the only directives…" plus the `.assert` exception note; A2/A6 where pass-2 checks and
    diagnostics are listed; G2: the map is now asserted by `boot.basm`, the compiler, and
    bcOS once #30 lands), `src/bc81asmc/CLAUDE.md` (two passes; the `.assert` note already
    there), `src/bc/CLAUDE.md` (preprocessor list), `src/bdos/CLAUDE.md` (memory map: the
    `0x5d00` limit is now checked at build time), `docs/analysis/02-assembler.md` (problem 1 /
    next step 1: done in #8, bcOS asserts in #30).
*   **Definition of Done**: every pointer above reflects the behaviour as built (check names and
    messages against the code, don't copy from this plan blindly). No other content is rewritten.
    CRLF files keep CRLF.
*   **Tests expected**: none (docs). `python3 run_tests.py < /dev/null` still exits 0.
*   **Tests to modify**: None

---

## 5. Verification

*   **Unit tests**: the assembler and compiler suite commands above, all green. The known
    `expectedFailure` tests (#11, #4) still report as expected failures.
*   **All suites**: `python3 run_tests.py < /dev/null` from the repo root, exit 0.
*   **Byte-identical rebuild (AC-3)**: in a temp copy of `src/`, run the python3 equivalent of
    `buildos`, `buildtools`, `buildapps` and `makedisc` (the scripts are CRLF and call
    `winpty python`; see the repo notes). Compare every `.btap`, `.sector(s)`, `.b81` and
    `os.bdd` with the committed ones. All are identical except `bcos.btap`, which has been stale
    since 2024 (its `.b81` is identical; pre-existing drift, not caused by this change).
*   **Observable behaviour**: in a temp dir, `bcos.basm` + the three asserts with a `nop` inserted
    before `os_metacall` prints `…: error: assertion failed: :os_metacall = 0x0008 (0x0009 = 0x0008)`
    with the source line and caret on stderr, exits 1 and writes no `.btap`.

---

## 6. Fact-Integrity Checklist

| Check | Yes / No / N/A | Notes |
| :--- | :--- | :--- |
| External contracts verified from producer/contract source | N/A | Internal story |
| Evidence sources are reproducible | N/A | Internal story |
| Identifier directionality / ordering / freshness meaning evidenced | N/A | Internal story |
| Every `Assumption` is linked to an Open Question (§3.2) | Yes | A-1 has no correctness impact (optional directive, reviewer can veto); closed from the issue text |
| No unresolved Open Questions (for `FINAL`) | Yes | |
| Each Decision states a single committed approach | Yes | |
| Tasks are independent, each with a Definition of Done and test expectations | Yes | T2 and T3 run in parallel after T1 |
| Required infra reflected (toggle / bicep) | N/A | No toggle key, no infra |

**Self-review note**: the addresses in §1 were measured by assembling the committed sources in a temp dir
(`os_metacall` `0x0008`, `os_metatab` `0x000c`, `user_mem` `0x0d6a`, boot loader exactly
`0x80` bytes, bdos end `0x52fb`) and from the committed `.btap` preambles (program ends vs
`#heap`). Because the boot loader fills its sector exactly, its assert must be `<=`. The main
risk is T3's regeneration: the agent must prove the binaries are byte-identical and that the
`.basm` diffs only add assert lines. `bcos.btap` is known to be stale, so compare
`.b81`/`.sector(s)`/`os.bdd`, not that file. D5 (`#codelimit`) is the one design choice not
spelled out in the issue.

---

## 7. Amendment Log

| Revision | Request | Decision | Plan changes |
| :--- | :--- | :--- | :--- |
