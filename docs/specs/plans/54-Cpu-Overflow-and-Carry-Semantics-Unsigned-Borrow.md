# CPU Overflow and Carry Semantics (Unsigned Borrow) Plan

**Plan Status**: `FINAL`

**Story Type**: `Internal`

**Plan Revision**: `A0`

> This plan captures **what** to build and **why**: domain, architecture, decisions, and verified facts.
> It does **not** contain implementation code. The implementation agent discovers the **how** against live code.

Slug note: the slug was fixed from the issue title before the owner's final decision. The story now gives `C` the
unsigned carry/borrow and `O` the signed overflow (D1). The slug stays, because the state file is named after it.

---

## 1. Problem Statement

*   **Context**: `set_flags` / `set_flags16` in `src/bc64/bc8183_cpu.py` set `C = result > max` and
    `O = result > max or result < 0`, both from the unwrapped result. So a subtraction that borrows never sets `C`, and
    `O` works as a borrow flag. `0x7f + 1` does not set `O`, `0xff + 1` does, and `not` always sets `O` (`~x` is
    negative before masking). Z/N were fixed in #53 (E11). The 8-bit shift flags are #55.
*   **Goal**: the flags get the usual 8-bit CPU meaning. `C` is the unsigned carry/borrow and `O` is two's-complement
    signed overflow. The docs and a design decision record this. Every program that relied on the old `O`-as-borrow is
    moved to `C`, so it behaves the same.
*   **In scope**: 8-bit `add sub inc dec and or xor not`, 16-bit `add sub inc dec mul div mod and or xor not`, the bcOS
    code that tests `o`/`no`, the pinned tests, and the docs.
*   **Out of scope**: 8-bit `shl`/`shr` and 16-bit `shl16`/`shr16` flags (#55: their `C`/`O` stay bit for bit as today).
    `div`/`mod` by zero (E10: `O = 1`, other flags unchanged). The compiler's handling of `/ 0` (#136). Signed numbers in
    the compiler (#25).

### 1.1 Technical Summary

*   **Touched**: emulator CPU (`src/bc64/bc8183_cpu.py`), bcOS ROM source (`src/bc81asmc/bcOS/bcos.basm`, 9 branch
    conditions), emulator ALU tests, docs (`docs/01-emulator.md`, `README.md` flag lists, design decisions).
*   **New patterns**: the ALU operations work out `O` from their operands and the result, not from the result alone.
*   **Infrastructure changes**: none.
*   **End-state**: `0x7f + 1` → `O = 1`, `C = 0`. `0xff + 1` → `C = 1`, `O = 0`. `0x00 - 1` → `C = 1`, `O = 0`.
    `0x80 - 1` → `O = 1`, `C = 0`. `not` → `C = O = 0`. bcOS comparisons, `upchar` and the hex/char printing behave as
    before.

---

## 2. Architecture & Design

### 2.1 Architecture Overview

| Component | Owner |
| :--- | :--- |
| emulator CPU `bc8183` | repo owner (bcichonski) |
| bcOS ROM monitor | repo owner |

```mermaid
flowchart LR
  bcos[bcos.basm: sub + jmr c/nc] -->|runs on| cpu[bc8183 CPU flags]
  bdos[bdos, utilities, apps (.b → .basm)] -->|os_metacall gt16/gteq16/upchar| bcos
  compiler[bc compiler runtime] -->|os_metacall| bcos
```

Programs reach the borrow tests only through bcOS calls (`gt16`, `gteq16`, `upchar`, `printhex4`, `prnt_fmt`).
No compiled program, `asm` block or compiler template tests `C` or `O` directly (audit in §2.3).

### 2.2 External Contracts & Evidence

N/A — Internal story.

#### Source Conflict Log

| Topic | Source A | Source B | Conflict | Chosen Handling |
| :--- | :--- | :--- | :--- | :--- |
| Meaning of `O` | Owner comment on #54 (2026-11-19): "it is meant to be 'unsigned out of range'", "this cpu does not handle signed values at all" | Owner note (2026-11-20, during this run): "it was a bug in the cpu, let's add normal 'signed' behaviour to C" | The later note reverses the earlier reading | The later note wins (D1): `C` = unsigned carry/borrow, `O` = signed overflow. Posted as a comment on #54 (issuecomment-7035952722) and flagged in the PR. |

### 2.3 Affected Areas

| Area / File (pointer) | Role in this change | Likely action |
| :--- | :--- | :--- |
| `src/bc64/bc8183_cpu.py` (`set_flags`, `set_flags16`, `alu_setval16`, the 8-bit `alu_*`, the 16-bit `alu_*16`) | The flag rules live here | Change |
| `src/bc81asmc/bcOS/bcos.basm` (`printhex4`, `upchar`, `prnt_fmt_char`, `gt16`, `gteq16`) | The only code that tests `o`/`no`: 9 `jmr` after a `sub`, used as "borrowed" | Change `o` → `c`, `no` → `nc` (same instruction length; CRLF kept) |
| `src/bc64/tests/test_cpu_alu.py` | Pins today's `C`/`O` (docstring, `flags_from_raw`, 18 tests) | Change listed tests, add new ones |
| `src/bc64/tests/test_cpu_control.py` | Style model for conditional-jump tests | Reference / add tests |
| `docs/01-emulator.md` ("Flags (`F`)") | Flag definitions | Change |
| `README.md` (flag bit list and jump conditions, near "CARRY"/"OVERFLOW") | User-facing flag names | Change where it describes meaning |
| `docs/specs/memory/design-decisions.md` (E10, E11, new E12) | Standing decisions | Add E12, update E11's "until #54" text |
| `docs/04-bcos.md`, `src/bc81asmc/bcOS/bcos.md` | Describe bcOS routines | Change only if they say `O`/overflow is used as borrow |
| `docs/analysis/08-self-hosted-roadmap.md` | Phase 0, step 5 | Reference (change only if it has a status column) |

**Dependency audit (verified 2026-11-20 on the built tree at `origin/master` 378c69c):** every conditional
`jmp/jmr/jrx/clr/cal/ret` on `c`, `nc`, `o`, `no` in all 15 `.basm` files (bcOS, boot, bdos, all utilities and apps,
examples) and in `src/bc/*.py`. Result: 9 hits, all in `bcos.basm`, all `sub` followed by `jmr o`/`jmr no`. Nothing
tests `c`/`nc`. Nothing tests `o` after `add`, `inc`, `not`, `mul` or a shift.

**Trial run (scratch copy, not committed):** the §2.4 rules alone fail 18 emulator tests (listed in T1) and 57 e2e tests
plus 2 errors (bcOS comparisons and printing break). The same rules plus the 9 `o`→`c` / `no`→`nc` edits give: emulator
only the 18 listed tests failing, assembler OK (6 expected failures), compiler OK, ftool OK, e2e OK (1 expected
failure). Both changes must land together (one task).

### 2.4 Key Behaviour

Let `max` be `0xff` (8-bit, destination `A`) or `0xffff` (16-bit, destination pair), `sign` its top bit, and `r` the
unwrapped result. Z and N stay as E11 (from the stored value).

| Operation | `C` | `O` |
| :--- | :--- | :--- |
| `add` (8/16) | `r > max` | operands have the same sign and the stored result's sign differs |
| `sub` (8/16) | `r < 0` (borrow) | operands' signs differ and the stored result's sign differs from the first operand's |
| `inc` (8/16) | `r > max` | operand was `0x7f` / `0x7fff` |
| `dec` (8/16) | `r < 0` (borrow) | operand was `0x80` / `0x8000` |
| `mul` (16) | product `> 0xffff` | same as `C` (unsigned multiply, as x86 `MUL`) |
| `div`, `mod` (16), divisor ≠ 0 | 0 | 0 |
| `div`, `mod` (16), divisor = 0 | unchanged | 1 (E10, unchanged) |
| `and`, `or`, `xor`, `not` (8/16) | 0 | 0 |
| 8-bit `shl`, `shr`; 16-bit `shl`, `shr` | exactly as today (#55) | exactly as today (#55) |
| `MOV` into `A` | unchanged | unchanged |
| `OUT #r, r2` | as today: 0 (the value sent is 0..0xff) | as today: 0 |

The "operands" of the register forms are the register values. For the 16-bit forms, the second operand is the
immediate or the implied pair, as today.

---

## 3. Key Decisions & Assumptions

*   **D1 (owner decision, interpreted)**: the owner wrote during this run "it was a bug in the cpu, let's add normal
    'signed' behaviour to C and comment it in the issue". Read as: the flags get the normal 8-bit CPU meaning, with
    `C` = unsigned carry/borrow and `O` = two's-complement signed overflow (the issue's "If it is signed overflow"
    branch). The words "to C" are read as "to the CPU flags". Signed overflow belongs in `O`, and a `C` that is not
    carry/borrow would leave borrow without a flag. This supersedes the owner's earlier "unsigned out of range" comment.
    The interpretation is posted on #54 and flagged in the PR so the owner can correct it.
*   **D2**: `sub`/`dec` borrow sets `C` (the issue title's bug). bcOS's 9 borrow tests move from `o`/`no` to `c`/`nc`.
    That is the same condition under D1, so bcOS behaves as before. The ROM changes, but its size and addresses don't.
*   **D3**: logic ops (`and or xor not`) clear `C` and `O`. `not` no longer sets `O`.
*   **D4**: 16-bit `mul` sets `C = O = (product > 0xffff)`. Unsigned `div`/`mod` with a non-zero divisor cannot
    overflow, so they clear both. That keeps E10's "sets `O` from its result (so clears it)".
*   **D5**: shifts are out of scope (#55). All four of their flags stay bit for bit, 8- and 16-bit. Their existing tests
    pass untouched.
*   **D6**: `inc`/`dec` set `C` like `add 1`/`sub 1` (unlike x86, where INC/DEC keep CF). `inc` already set `C` on
    `0xff + 1`, and keeping one rule for all arithmetic is simpler.
*   **D7**: a new design decision **E12** records §2.4. E11's text loses its "until #54" caveats and points to E12.
    `docs/01-emulator.md` flags table: `C` "carry / borrow (unsigned)", `O` "signed overflow (two's complement)".
*   **D8**: the pinned tests become correct-behaviour tests (the issue says so). The `flags_from_raw` helper and the
    module docstring of `test_cpu_alu.py` change with them.
*   **D9**: no compiler, bdos, app or assembler change. Compiled programs are byte-identical. Only the ROM changes, in
    9 condition bytes. Goldens and the smoke transcript do not change (trial run: e2e green with no golden update).
    No `code_size.csv` row changes (bcOS is not measured).
*   **Scope note**: the issue says "fix together with #53, #55". #53 is merged (PR #139). #55 stays separate (roadmap
    step order, D5). The issue's own test list names `src/bc64/test_cpu_alu.py`, which moved to `src/bc64/tests/` in #90.

### 3.1 Decision Lock

| Item | Value |
| :--- | :--- |
| `C` | unsigned carry (add/inc/mul) or borrow (sub/dec) |
| `O` | two's-complement signed overflow (add/sub/inc/dec); mul = `C`; div/mod by 0 = 1 (E10) |
| logic ops | `C = O = 0` |
| shifts | unchanged (#55) |
| bcOS borrow tests | `jmr c` / `jmr nc` |
| new design decision id | `E12` |

### 3.2 Open Questions

No open questions. D1 is the owner's instruction with a recorded interpretation, which the PR flags for confirmation.

---

## 4. Task Breakdown

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| T1 | CPU carry/borrow and signed overflow + bcOS borrow tests + ALU tests | — | Medium |
| T2 | Document the flag definitions (E12, emulator docs, README) | — | Low |

### T1 — CPU carry/borrow and signed overflow + bcOS borrow tests + ALU tests

*   **Goal**: §2.4 holds for every listed ALU operation, bcOS's 9 borrow tests use `C`, and the pinned tests assert
    the new flags.
*   **Depends on**: —
*   **Complexity**: `Medium`. The change is small, but the CPU is the reference for everything. The CPU and bcOS edits
    must land in this one task, because either one alone breaks the e2e suite (trial: 57 failures).
*   **Pointers**: §2.3. `src/bc64/bc8183_cpu.py` (`set_flags` and its `raw_zn` shift path, `set_flags16`,
    `alu_setval16`, `alu_add/sub/inc/dec/and/or/xor/not`, `alu_*16`); `src/bc81asmc/bcOS/bcos.basm` (CRLF file: keep CRLF;
    the 9 `jmr o`/`jmr no` in `printhex4`, `upchar`, `prnt_fmt_char`, `gt16`, `gteq16`);
    `src/bc64/tests/test_cpu_alu.py` (helpers `flags_of`, `flags_from_raw`, `check`, `check16`).
*   **Definition of Done**:
    *   Every row of §2.4 holds, for the immediate and register forms (8-bit) and the immediate and pair forms (16-bit).
    *   8- and 16-bit shift flags and `div`/`mod`-by-zero behave bit for bit as before (their existing tests pass untouched).
    *   `bcos.basm` has no `jmr o`/`jmr no` left. The 9 conditions are `c`/`nc`. The ROM is the same size.
    *   No change to the assembler, the compiler, bdos or app sources, the e2e goldens or the smoke transcript.
*   **Tests expected** (unit, emulator; added to `test_cpu_alu.py` / `test_cpu_control.py`):
    *   signed overflow: `0x7f + 1` (O=1, C=0), `0x80 + 0x80` (O=1, C=1), `0x80 - 1` (O=1, C=0), `0x7f - 0xff`
        (8-bit: O=1, C=1), `inc 0x7f`, `dec 0x80`, and the 16-bit equivalents (`0x7fff + 1`, `0x8000 - 1`, inc/dec);
    *   borrow: `0x00 - 1` → C=1, O=0 (8 and 16-bit); no borrow → C=0;
    *   `mul16` product over `0xffff` → C=O=1; within range → C=O=0;
    *   logic ops clear a preset `C` and `O`;
    *   a conditional jump on `c` after a borrowing `sub` and on `o` after `add 0x7f+1`, run as real code;
    *   bcOS behaviour is covered by the existing e2e suite. The task must run it (see below).
*   **Must-run before returning** (no `git stash`, `checkout` or `restore`; to prove a test fails, temporarily revert
    the change in the file): from `src/`: `python3 -m unittest discover -s bc64/tests -t . -p "test_*.py"`. Then from
    the repo root: `python3 run_tests.py < /dev/null`, which builds the ROM and discs and runs e2e. It must exit 0, with
    expected failures only assembler 6 and e2e 1. After that run, `git status` shows only intended files.
*   **Tests to modify** (all in `src/bc64/tests/test_cpu_alu.py`, verified by the trial run in §2.3; each changes only
    its `C`/`O` expectation per D1–D4, and Z/N stay):
    *   `src/bc64/tests/test_cpu_alu.py :: Alu8Tests.test_add_imm_sign_bit_no_overflow` — 0x7f+1 now O=1 (D1); rename allowed
    *   `src/bc64/tests/test_cpu_alu.py :: Alu8Tests.test_add_imm_wrap_at_0xff` — 0xff+1: O 1→0 (D1)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu8Tests.test_sub_imm_wrap_below_zero` — borrow: C 0→1, O 1→0 (D1/D2)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu8Tests.test_sub_reg_borrow` — borrow: C 0→1, O 1→0 (D1/D2)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu8Tests.test_inc_into_sign_bit` — inc 0x7f: O 0→1 (D1)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu8Tests.test_inc_wrap_at_0xff` — O 1→0 (D1)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu8Tests.test_dec_wrap_below_zero` — C 0→1, O 1→0 (D1/D2)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu8Tests.test_not` — O 1→0 (D3)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu8Tests.test_not_ff_gives_zero` — O 1→0 (D3)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu8Tests.test_not_zero_gives_ff` — O 1→0 (D3)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu16Tests.test_add16_into_sign_bit` — 0x7fff+1: O 0→1 (D1)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu16Tests.test_add16_wrap_at_0xffff` — O 1→0 (D1)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu16Tests.test_sub16_wrap_below_zero` — C 0→1, O 1→0 (D1/D2)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu16Tests.test_inc16_wrap_at_0xffff` — O 1→0 (D1)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu16Tests.test_dec16_wrap_below_zero` — C 0→1, O 1→0 (D1/D2)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu16Tests.test_not16` — O 1→0 (D3)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu16Tests.test_not16_ffff` — O 1→0 (D3)
    *   `src/bc64/tests/test_cpu_alu.py :: Alu16Tests.test_not16_zero` — O 1→0 (D3)
    *   the module docstring, `flags_from_raw` (docstring and logic) and the `PINNED` comments of the same file. They
        describe the old `C`/`O` (D8). The helper may change to compute the new `C`/`O` or be replaced by explicit
        expectations, as long as every other test still asserts the same values it does today.

### T2 — Document the flag definitions

*   **Goal**: the docs state §2.4 as the CPU's flag definition.
*   **Depends on**: —
*   **Complexity**: `Low`.
*   **Pointers**: `docs/01-emulator.md` ("Flags (`F`)" table and the paragraphs below it: `C` and `O` rows per D7; drop
    the "#54" sentence; keep the #55 shift note and E10 text; one sentence on `OUT #r, r2`);
    `docs/specs/memory/design-decisions.md` (new `### E12` after E11, Purpose / Rationale / Usage / Trade-offs, citing
    #54 and D1's owner note; E11's "until #54" wording → "see E12"); `README.md` (the bit list `0x1 - CARRY`,
    `0x3 - OVERFLOW` and the jump-condition list: add the meaning in a few words; the "Known issues" line mentioning
    #54 drops #54); `docs/04-bcos.md` and `src/bc81asmc/bcOS/bcos.md` only if they say a routine uses `O` as borrow
    (the legacy error codes `0x10–0x13` "overflow in …" are names, leave them).
*   **Definition of Done**: no doc says a subtraction borrow sets `O`, or that `C`/`O` wait for #54. E12 exists and
    matches §3.1.
*   **Tests expected**: none (docs only).
*   **Tests to modify**: None.

---

## 5. Verification

1.  From `src/`: `python3 -m unittest discover -s bc64/tests -t . -p "test_*.py"` → OK.
2.  From the repo root: `python3 run_tests.py < /dev/null` → exit 0. Report the expected failures by name (assembler 6,
    e2e 1, the tape round trip), never as "all passed".
3.  `git status` after the run: only the intended source, doc and test files changed. The build must not change tracked
    files.
4.  `grep -nE "jmr n?o," src/bc81asmc/bcOS/bcos.basm` → nothing.
5.  Headless check: boot `os.bdd` and run `ls`, `cat`, `hellowrd`, and `b:` + `texted`/`calc` with `utils.bdd`. The e2e
    suite covers these; output is unchanged.

---

## 6. Fact-Integrity Checklist

| Check | Yes / No / N/A | Notes |
| :--- | :--- | :--- |
| External contracts verified | N/A | Internal |
| Evidence sources reproducible | N/A | Internal |
| Meaning evidenced separately | N/A | Internal |
| Every `Assumption` linked to an Open Question | Yes | D1 is an owner instruction with a posted interpretation, not an open assumption |
| No unresolved Open Questions | Yes | |
| Each Decision states a single committed approach | Yes | |
| Tasks independent, each with DoD and test expectations | Yes | T1 and T2 touch disjoint files |
| Required infra reflected | N/A | |

**Self-review note**: the main risk is D1's interpretation of the owner's note ("signed behaviour to C"). It is posted
on #54 and must be named in the PR. The trial run gave the exact `Tests to modify` list and proved that the CPU and bcOS
changes must ship together. The implementer should keep shifts and division by zero untouched, and must run the full
`run_tests.py` (e2e), because only e2e exercises bcOS.

---

## 7. Amendment Log

| Revision | Request | Source | Decision | Plan changes |
| :--- | :--- | :--- | :--- | :--- |
