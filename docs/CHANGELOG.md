# Changelog

All notable changes to this project will be documented in this file.
Each entry corresponds to a completed story and is generated from the actual PR diff after
implementation — not from the spec plan.
Entries are ordered by merge date (newest first).

To add entries, run the `generate-changelog-entry` skill (or the `changelog-generator` agent).
It scans `docs/specs/plans/` for `FINAL` plans with no entry here yet, finds each one's merged
PR on GitHub, and drafts from the diff. The format for an entry is in
`docs/changelog-entry-template.md`.

---

## [38] bdos: clean up bdio error codes (duplicates and collisions) — 2026-11-23

Tags: `bdos` `abi` `tests` `docs`
PR: [#156](https://github.com/bcichonski/bc16/pull/156)
Builds on: #19, #82

### What was built
- `src/bdos/bdioh.b`: each bdio error value now has one meaning. `BDIO_FOPEN_FDD_NOT_READY` is `0xe1`, and `0xe5` is retired. `BDIO_FCLOSE_FCAT_SAVEERR` moved from `0xe7` to `0xef`, so `0xe7` now means only "exec: not executable". The never-produced `BDIO_FCREATE_FNAME_EXISTS` (`0xe6`) is removed, so `0xe6` means only "close: catalog read error". The defines are grouped by operation, with the free and retired values listed.
- `bdio_printexecres` gets a message for `0xef` (`cat save error`). Other codes print as before. Each program grows by 49 bytes, and bdos ends at `0x561e`, under its `0x5d00` limit.
- New unit test `src/tests/test_bdioh_codes.py`: no duplicate names or values, the changed codes are pinned, every changed code has a message, and the handle/error split at `0xe0` holds.
- New e2e `src/tests/test_e2e_bdio_errors.py` (`bdos_bdio_errors.in.txt`): `cha -x` then running the program gives `E7 execution not allowed`, `cha -r` then `cat -c` gives `E3 reading not allowed`, and an unknown command gives `E0 file not found`.
- Docs: the `docs/05-bdos.md` error table is rewritten, G7 in `design-decisions.md` now says "one value per meaning, a retired value is never reused", and problem 6 in `docs/analysis/05-bdos.md` is marked fixed. New rows in `src/bc/code_size.csv`.

### Key decisions reflected in the diff
- The owner chose `0xe1` for drive-not-ready on open, which settles the question left open in #19.
- Only changed codes get new messages ("only changes"), because `bdio_printexecres` is in `bdioh.b` and is linked into every program.
- Program sources didn't change: callers compare codes by name or with `< 0xe0`.

## [82] strings.b: one strnextword with a documented contract — 2026-11-23

Tags: `b-stdlib` `bdos` `apps` `tests` `docs`
PR: [#155](https://github.com/bcichonski/bc16/pull/155)
Builds on: #1

### What was built
- `src/bdos/strings.b`: the dead `strnextwordnull` copy (the one that returned 0) is deleted. `strnextword` has a comment stating its contract: it returns the address of the next word, or of the terminating NUL when there is none, never 0.
- Nine bdos programs are 24 bytes smaller each (bdos, cat, cha, cp, fddtest, format, ls, rm, texted), recorded in `src/bc/code_size.csv`.
- New `src/tests/test_e2e_bdos_args.py` (6 tests, one session): `ls`, `cp`, `rm`, `cha`, `cat` and `cat -c` with missing arguments print the expected errors, and both disc images are unchanged afterwards.
- Docs: the contract is in `docs/05-bdos.md` and in the new design decision D9. A6's note no longer mentions the dead copy.

### Key decisions reflected in the diff
- Option A of the issue: callers test the first byte for `NULLCHAR`, not for a 0 address. TextEd's side was already done by #1.

## [11] Assembler: `out #r, imm` encodes as `Dr HH` — 2026-11-23

Tags: `assembler` `abi` `tests` `docs`
PR: [#153](https://github.com/bcichonski/bc16/pull/153)
Builds on: #10, #65

### What was built
- `OUT.emit` in `src/bc81asmc/bc81asmc_ast.py` emits the CPU's 2-byte immediate form `D` + port register number, then the full 8-bit value: `out #ci, 0x41` → `D4 41`, `out #a, …` → `D1 HH`, `out #di, …` → `D5 HH`. The CPU is unchanged.
- Any other port register (`cs`, `ds`, `f`, `si`, `ss`, `pc`) is a positioned `cannot encode` error that names the fix. The rejected line emits no bytes, and assembly continues.
- The six `#11` expected-failure tests now run as normal tests; the cs/ds ones assert the exact message. New tests cover the allowed encodings with full-byte values, the rejected registers, and assembler↔CPU agreement (value reaches the port, PC + 2, flags unchanged).
- Docs: `docs/02-assembler.md` (I/O row, Errors table, quirk removed), `docs/01-emulator.md` (the immediate form changes no flags), both CLAUDE.md files, analysis docs 01, 02 and 07, and design decision A11.

### Key decisions reflected in the diff
- Fix, don't reject (owner decision). Registers numbered 8 and up are rejected because encoding them would set bit 3 and silently turn the instruction into the register form.
- After this story only one expected failure is left in the whole suite (the tape round trip, #32/#62).

## [69] Compiler: unknown binary operator raises CompilerError — 2026-11-23

Tags: `compiler` `tests`
PR: [#154](https://github.com/bcichonski/bc16/pull/154)
Builds on: #14

### What was built
- `EXPRESSION_BINARY.emit` in `src/bc/bc_ast.py` raises `CompilerError("Unknown binary operator '<op>'")` for an operator that is missing from `oper2lib`/`opercommutative`. The check runs before the table lookup, which used to raise a `KeyError`. It also raises when `logic()` can't handle a table operator, where the old code referenced a missing attribute and crashed with an `AttributeError`.
- `bc.py` reports it as `internal error: …`, exits 1 and writes no `.basm`.
- New `UnknownBinaryOperatorTests` in `src/bc/tests/bc_codegen_tests.py`. `docs/03-compiler.md` notes the error.

### Key decisions reflected in the diff
- The check also runs before the lookup, not just at the message line the issue names, so a new operator (for example from #18) gives the error instead of a `KeyError`. Generated code is unchanged (`code_size.py --check` delta +0).

## [65] Assembler: reject a second `.org` and a `.org` after code or a label — 2026-11-22

Tags: `assembler` `tests` `docs`
PR: [#151](https://github.com/bcichonski/bc16/pull/151)
Builds on: #10, #103

### What was built
- `src/bc81asmc/bc81asmc.py` reports `duplicate .org (first .org at line M); use .org once, at the top` and `.org must come before any code or label` (including a label on the `.org` line). Only comments and `.def` may come before `.org`, and a source with no `.org` still starts at 0x0000.
- A rejected `.org` doesn't change addresses, so later diagnostics are still reported in order. The run exits 1 and writes no `.btap`.
- The two pinned tests now assert the error (`…_is_rejected`). New `TestOrgPlacement` diagnostics tests and a CLI test (exit 1, caret block, no `.btap`).
- Docs: the `.org` row and an Errors row in `docs/02-assembler.md`, and design decision A10 (BASM must follow the same rule).

### Key decisions reflected in the diff
- Reject instead of fixing the fix-up offsets (owner choice, option 2). A fix would still have taken the `.btap` load address from the last `.org`. All built outputs are byte-identical.

## [103] Assembler: a label on a line of its own — 2026-11-22

Tags: `assembler` `tests` `docs`
PR: [#149](https://github.com/bcichonski/bc16/pull/149)
Builds on: #10

### What was built
- `bc81asmc_grammar.py`: `line` has a new `label, comment?` alternative, after `label? instruction comment?`, so labelled instructions parse as before.
- `bc81asmc_ast.py`: a no-byte `LabelOnly` node. The label gets the current address (the next emitted byte), and several label-only lines in a row share it. Duplicate checks, `--verbose` and `.assert` treat it like any labelled line.
- 22 new tests across the grammar, emit and diagnostics test files: references via `jmp`/`jmr`/`jrx`/`cal`/`clr`/`.db`/`.mv`/`.assert`, a label at EOF, duplicates, and inputs that are still errors.
- Docs: Source syntax in `docs/02-assembler.md` and `src/bc81asmc/CLAUDE.md`.

### Key decisions reflected in the diff
- The label takes the current address, like a label on `.assert`/`.def`, so it does not look past a following `.org` (#65 later made a late `.org` an error). All 16 build outputs are byte-identical. This prepares #104 (no `nop` at compiler labels).

## [73] bdos: cp regression tests (bug already fixed by #37) — 2026-11-22

Tags: `bdos` `apps` `tests` `docs`
PR: [#150](https://github.com/bcichonski/bc16/pull/150)
Builds on: #37, #92

### What was built
- No code change: #37 had already fixed it by taking catalog lengths from the real builds (the old catalog gave `CP.PRG` 56 sectors, but it builds to 57).
- New `BdosCpRegressionTests` in `src/tests/test_e2e_bdos.py`: `cp test.b copy.b` on the same drive and `cp test.b b:copy.b` across drives. Both have masked goldens and check that the copy's catalog length and sectors equal TEST.B's, that only `W` is dropped, and that other catalog entries are unchanged.
- New harness helper `e2e_harness.read_file(image, name)` (catalog entry + sector bytes), with a self-test.
- Docs: a root-cause note in `docs/05-bdos.md` (a too-short catalog length loads a truncated program) and the coverage row in `docs/01-emulator.md`.

## [67] Assembler: `clr af` is rejected with a clear message — 2026-11-22

Tags: `assembler` `tests` `docs`
PR: [#152](https://github.com/bcichonski/bc16/pull/152)
Builds on: #10, #66

### What was built
- `check_clr_pair` in `src/bc81asmc/bc81asmc_ast.py`, called from `CLR.emit`. `clr af` → `cannot encode 'clr af': clr af is not allowed: the call offset would be read from a:f, and f holds the flags (use a pair csci, dsdi or sssi)`. Any other non-pair operand → `'x' is not a pair for clr`.
- `clr csci`/`dsdi`/`sssi` and `clr :label` encode as before.
- The pinned test is renamed `test_clr_af_is_rejected_on_purpose` and asserts the message. New `TestClrRegisterForm` tests.
- Docs: Errors table and `clr pair` row in `docs/02-assembler.md`, design decision A9, `src/bc81asmc/CLAUDE.md`.

### Key decisions reflected in the diff
- `clr` is the relative call, not "clear". The owner withdrew the comment that asked to allow `clr af`. `cal af`, `jmp t, af` and `jrx t, af` still assemble (not in scope).

## [19] Compiler: token-based `#define` instead of substring replacement — 2026-11-22

Tags: `compiler` `bdos` `tests` `docs`
PR: [#148](https://github.com/bcichonski/bc16/pull/148)
Builds on: #14, #15

### What was built
- `bc.py` `parse_define`/`apply_defines`: the name is the first token and the value is the rest of the line, so values with spaces work. Only whole identifiers are replaced, in code and in the string right after `asm`. Other strings, char literals and `//` comments are left alone, numbers are scanned whole (`0x10` never matches `x10`), and a replaced value is not rescanned.
- A redefinition with a different value prints `<file>: warning: 'NAME' redefined`, and the last value still wins. A malformed `#define` is `<file>: error: …` with exit 1.
- New `src/bc/tests/bc_define_tests.py` (16 tests).
- `src/bdos/bdioh.b`: the dead first definition of `BDIO_FOPEN_FDD_NOT_READY` is removed, so behaviour is unchanged.
- Docs: Preprocessor table in `docs/03-compiler.md`, `src/bc/CLAUDE.md`, design decision C5.

### Key decisions reflected in the diff
- Every program compiles to byte-identical `.basm` (`code_size.py --check` delta 0). `bc_dbg.py` keeps its own old `preprocess()` (out of scope).

## [56] CPU/ISA: register-count shl/shr settled as `58 r5` / `58 r6` — 2026-11-22

Tags: `emulator` `assembler` `abi` `tests` `docs`
PR: [#147](https://github.com/bcichonski/bc16/pull/147)
Builds on: #55

### What was built
- No behaviour change: the assembler already emits every 8-bit register op as the long form `58 ro` (`shl ci` → `58 45`), and the CPU decodes it. The issue's `5d 40` came from the CPU-only short alias `5(o|8) r0` (sub/and/or/xor only).
- `src/bc64/bc8183_cpu.py`: comment only. The note in `op_CLC` now describes the long form and the short alias.
- The pinned `test_shl_shr_register_forms_are_unreachable` is replaced by `test_single_byte_5d_5e_are_inc_dec` and six `ShiftFlagTests` for `58 r5`/`58 r6`. New assembler tests `TestShiftRegisterForms` and `TestShiftRegisterGrammar`.
- Docs: a new "8-bit ALU encoding" subsection in `docs/01-emulator.md`, a note in `docs/02-assembler.md`, and design decision E15.

### Key decisions reflected in the diff
- Register-count shifts exist in the ISA, encoded as the long register form. BASM must emit the same bytes.

## [59] CPU: RET stops on a single push frame — 2026-11-20

Tags: `emulator` `abi` `tests` `docs`
PR: [#144](https://github.com/bcichonski/bc16/pull/144)
Builds on: #7

### What was built
- `op_RET` and a new `ret_stop()` in `src/bc64/bc8183_cpu.py`: a single push frame on top (no second push frame under it), or a top tag that is neither push nor call, stops the CPU like `KIL`. It prints `RET at XXXX: …, CPU stopped` to stderr and the trace, and leaves PC, registers and memory unchanged. A call frame returns as before, and two push frames still make a computed jump. The #7 bounds check still runs first.
- New `src/bc64/tests/test_cpu_ret_frames.py` (8 tests, including a headless `bc64.py` run).
- Docs: `docs/01-emulator.md` now gives the correct computed-jump order `psh lo; psh hi; ret` (the old text had it backwards), plus design decision E4, `src/bc64/CLAUDE.md` and roadmap step 10.

### Key decisions reflected in the diff
- An unknown top tag also stops, instead of being decoded as two push frames. A probe run showed no system or app code executes a non-call `RET`, so built programs are unaffected.

## [66] Assembler: every 16-bit ALU op on af is rejected with a clear error — 2026-11-20

Tags: `assembler` `tests` `docs`
PR: [#145](https://github.com/bcichonski/bc16/pull/145)
Builds on: #57, #10

### What was built
- `bc81asmc_grammar.py`: `mINC16`/`mDEC16` are tried before `mINC`/`mDEC`, so `inc af`/`dec af` parse.
- `bc81asmc_ast.py`: `inc af`, `dec af` and every 16-bit ALU op on `af` (`add sub mul div mod and or xor shl shr not`, both forms) are `cannot encode` errors that say why (the result would overwrite the flags in `f`) and suggest `csci`/`dsdi`. This check runs before the implied-pair rule, and `af` is gone from `PAIR16_IMPLIED`.
- Pinned test renamed `…_are_rejected_on_purpose`, and the `af` cases of `TestSixteenBitPairs` and the opcode-agreement table were updated. New grammar-order and diagnostics tests.
- Docs: `docs/02-assembler.md`, `docs/01-emulator.md`, design decision A8 (A7 no longer lists `add af, csci`), `src/bc81asmc/CLAUDE.md`, README known limitations.

### Key decisions reflected in the diff
- Owner's mid-run instruction "make other arithmetic blocked on af", read as every 16-bit ALU op. The CPU is unchanged, and all 29 build outputs are byte-identical.

## [58] CPU: 16-bit results on the A:F pair defined (docs + tests) — 2026-11-20

Tags: `emulator` `tests` `docs`
PR: [#140](https://github.com/bcichonski/bc16/pull/140)
Builds on: #53, #54

### What was built
- No CPU or assembler change. The behaviour is now documented: a 16-bit op with destination `af` reads `A:F` as one value, puts the high byte of the result in `A` and the flags in `F`, so the low byte is lost.
- `src/bc64/tests/test_cpu_alu.py`: `test_add16_on_a_f_pair` loses its `PINNED` note, and 5 new tests cover `F` as input low byte, `sub`/`mul` on `af` and the register form.
- Docs: `docs/01-emulator.md`, `docs/02-assembler.md`, design decision E14, roadmap step 9.

### Key decisions reflected in the diff
- Owner: "that is correct cpu behavior; af is not to be used in this context although allowed". The issue's two fix options were not taken. (#66 later made the assembler reject these forms.)

## [54] CPU: C is unsigned carry/borrow, O is signed overflow — 2026-11-20

Tags: `emulator` `bcos` `abi` `tests` `docs`
PR: [#143](https://github.com/bcichonski/bc16/pull/143)
Builds on: #53, #55

### What was built
- `src/bc64/bc8183_cpu.py`: `C` is the unsigned carry for `add`/`inc` and the borrow for `sub`/`dec` (borrow is new). `O` is two's-complement signed overflow. `mul16` sets `C` = `O` = product > 0xffff. Logic ops and a non-zero `div`/`mod` clear both, and `not` no longer sets `O`. Shift flags stay as #55 set them (E12).
- `src/bc81asmc/bcOS/bcos.basm`: the 9 `jmr o`/`jmr no` borrow tests after `sub` (`printhex4`, `upchar`, `prnt_fmt_char`, `gt16`, `gteq16`) are now `jmr c`/`jmr nc`. Instruction sizes are unchanged.
- 18 pinned tests in `test_cpu_alu.py` assert the new flags, plus new tests for signed overflow, borrow, `mul16` and logic ops, and `jmr c`/`nc`/`o` run as code in `test_cpu_control.py`.
- Docs: flags table in `docs/01-emulator.md`, design decision E13, README flag and jump-condition lists.

### Key decisions reflected in the diff
- The owner's mid-run note ("normal 'signed' behaviour") replaced the earlier "unsigned out of range" comment, and the usual 8-bit CPU meanings were adopted. Compiled programs are byte-identical; only the ROM changes.

## [64] Assembler: label or .def at address 0x0000 (regression tests, already fixed by #10) — 2026-11-20

Tags: `assembler` `tests` `docs`
PR: [#142](https://github.com/bcichonski/bc16/pull/142)
Builds on: #10

### What was built
- No assembler change: #10's pass-2 fix-up loop already resolves a name to 0x0000 and reports `undefined label` only when the result is `None`.
- New `TestAddressZeroTargets` in `src/bc81asmc/tests/bc81asmc_emit_tests.py` (9 tests): the issue's repro (`00 68 00`), `.def zero` through `jmp`/`cal`/`.mv`/`jrx`, and a label at 0 reached by `jmr`/`jrx`/`clr`/`.mv`. All 9 fail if the old falsy check is restored.
- `docs/02-assembler.md`: the Labels bullet and the `undefined label` row say a name may resolve to 0x0000.

## [55] CPU: shl/shr flags describe the shifted result — 2026-11-20

Tags: `emulator` `tests` `docs`
PR: [#141](https://github.com/bcichonski/bc16/pull/141)
Builds on: #53

### What was built
- `src/bc64/bc8183_cpu.py`: for `shl`/`shr` and `shl16`/`shr16`, `Z`/`N` come from the stored result, `C` is the last bit shifted out (0 for a count of 0 or more than the width), and `O` is 1 when `shl` shifts out a 1 bit (always 0 for `shr`). Large register counts are capped at the width. `set_flags` loses its `raw_zn` parameter.
- `test_cpu_alu.py`: 7 shift tests get new expectations, and new `ShiftFlagTests` cover the edge counts and `jmp c`/`jmp z` after a shift run as code.
- Docs: `docs/01-emulator.md`, design decision E12, roadmap step 6.

### Key decisions reflected in the diff
- A shift by 0 clears `C` and `O`. An audit of all 165 shifts in the built `.basm` files found nothing that reads their flags, so no program changed.

## [53] CPU: zero flag from the stored result after a wrap — 2026-11-19

Tags: `emulator` `tests` `docs`
PR: [#139](https://github.com/bcichonski/bc16/pull/139)

### What was built
- `set_flags`/`set_flags16` in `src/bc64/bc8183_cpu.py` compute `Z` and `N` from the stored value, so a wrap to `0x00`/`0x0000` sets `Z` (8-bit `add`/`inc`/`not`, 16-bit `add`/`inc`/`mul`/`shl`/`not`). `C`/`O` and the 8-bit shift flags are unchanged (left to #54/#55).
- The seven pinned tests now assert `Z = 1`, and new tests (`test_shl16_wrap_to_zero_sets_z`, `JumpOnZeroAfterWrapTests`) run `jmp z` after a wrap as code.
- Docs: flags table in `docs/01-emulator.md`, design decision E11.

### Key decisions reflected in the diff
- Only #53 was done; #54/#55 are separate roadmap steps. An audit of every `z`/`nz` jump in the built `.basm` files found none after a wrapping op, so built programs are byte-identical.

## [57] Assembler: enforce the implied second pair of 16-bit register-pair ops — 2026-11-19

Tags: `assembler` `abi` `tests` `docs`
PR: [#138](https://github.com/bcichonski/bc16/pull/138)
Builds on: #10

### What was built
- `check_pair16` in `src/bc81asmc/bc81asmc_ast.py`, called from `CLC16_R_R`, `CLC16_R_IMM`, `INC16`, `DEC16` and `NOT16` before anything is emitted. The register form accepts only the pairs the CPU implies (`csci, dsdi`, `dsdi, csci`, `af, csci`), and an unknown pair name gets its own message. Both are positioned `cannot encode` errors.
- New `TestSixteenBitPairs` in `bc81asmc_compile_diag_tests.py`. The pinned opcode-agreement test now runs the hand-encoded `5F A8 88` and asserts that `dsdi` is added.
- Docs: implied-pair table in `docs/02-assembler.md` and `docs/01-emulator.md`, design decision A7, roadmap step 8, `src/bc81asmc/CLAUDE.md`.

### Key decisions reflected in the diff
- The CPU keeps reading only the first pair, and the assembler enforces the convention (owner decision). BASM must apply the same rule. Valid lines encode as before.

## [15] Compiler: code-size and codegen tracking (`code_size.csv`) — 2026-11-19

Tags: `compiler` `build` `tests` `docs`
PR: [#135](https://github.com/bcichonski/bc16/pull/135)
Builds on: #90, #92

### What was built
- New `scripts/code_size.py`: builds every program (each `.b` with `main`: 13 in `src/bdos/`, 5 in `src/bc/code/`) in a temp copy and reports start address, size (`.btap` codelen) and a 12-digit SHA-256 of the `.basm`. With no flag it prints a Markdown table with Δ and always exits 0. `--check` exits 1 on any change, and `--record` appends changed rows.
- New append-only `src/bc/code_size.csv` (`date,program,start,bytes,basm_sha`, latest row per program wins), seeded with all programs.
- New `scripts/tests/test_code_size.py` tests the script on temp trees. In CI, `unit (3.14)` runs it with `continue-on-error` and puts the table in the job summary.
- Docs: `src/bc/CLAUDE.md`, `docs/03-compiler.md`, root `CLAUDE.md`, `docs/analysis/06-toolchain.md`, `history.txt`.

### Key decisions reflected in the diff
- Metrics only (owner): no golden `.basm` is tracked, and nothing fails CI when a program's size or code changes. The grammar-test repair was already done on master.

## [4] Emulator fixes: negated jrx, div/mod by zero, FDD failure state — 2026-11-19

Tags: `emulator` `devices` `tests` `docs`
PR: [#137](https://github.com/bcichonski/bc16/pull/137)
Builds on: #7

### What was built
- `op_EXT` in `src/bc64/bc8183_cpu.py`: `jrx` takes the negation bit from the test code (`t & 0x4`), so `jrx nz/nc/nn/no` work in both forms. An unknown EXT sub-opcode stops the CPU cleanly with one stderr line, instead of raising `UnboundLocalError`.
- 16-bit `div`/`mod` by zero (immediate and register forms) sets `O`, leaves the destination and `Z/N/C` unchanged and continues; a non-zero divisor clears `O`.
- `FloppyDriveV1.write_byte` in `src/bc64/bc64_io.py`: the `setate` typo is fixed, so an unhandled byte (including READSECT/WRITESECT outside READY) puts the drive in `STATE_DRIVE_FAILURE` until PING/CFG/SETDRV.
- The #4 expected-failure tests run as normal tests. New tests cover every negated/plain `jrx` flag in both forms, div/mod by zero, a headless CLI run and FDD recovery. The emulator suite has no expected failures left.
- Docs: `docs/01-emulator.md`, `docs/02-assembler.md`, `src/bc64/CLAUDE.md`, design decision E10, and the roadmap's owner-decision table (#4 → #136).

### Key decisions reflected in the diff
- Division by zero sets a flag instead of stopping the CPU (owner). In B, `x / 0` gives `x`; follow-up #136 decides the compiler side.

## [111] bdos: rm no longer lets a new file overwrite another file; ls free-sector count — 2026-11-19

Tags: `bdos` `filesystem` `apps` `tests` `docs`
PR: [#134](https://github.com/bcichonski/bc16/pull/134)
Builds on: #37, #89

### What was built
- `src/bdos/bdio.b`: `bdio_fcat_scanmem` now reads the free position back as `track << 8 | sector` (it was `<< 4`). After `rm` reordered the catalog, the old code could place a new file on top of an existing one.
- `src/bdos/ls.b`: free sectors are `1024 − (track × 16 + sector)` (the sector was added instead of subtracted).
- New `src/tests/test_e2e_rm_alloc.py` (rm a middle file, the last file on disc, and the last catalog entry, then `cp ls.prg new.prg`; checks that no other file changed and entries don't overlap). New `src/tests/test_e2e_ls_free.py` checks the free count against the manifest layout.
- Docs: Allocation in `docs/05-bdos.md`, prerequisites in `docs/analysis/07-self-hosted-compiler.md`.

## [109] Release bc64-v0.1: release notes and release docs — 2026-11-19

Tags: `build` `docs` `tests`
PR: [#110](https://github.com/bcichonski/bc16/pull/110)
Builds on: #90, #100

### What was built
- README `# BC64` opens with the `bc64-v0.1` (first preview) release notes, which `make_release.py notes bc64` prints as the Release body: running from the zip with `os.bdd` in A and `utils.bdd` in B, what is on each disc, and known limitations linked to open issues.
- README Releases section: a `bc64-v0.1` row (bc64 tags start at v0.1), the `--tag bc64-v0.1` example and the owner's dry-run/tag/push steps. CLAUDE.md and the `make_release.py` help text are updated to match.
- New `Bc64ReleaseNotesTests` in `scripts/tests/test_make_release.py`.

### Key decisions reflected in the diff
- Tagging and publishing are left to the owner; the PR changes no pipeline (`TAG_RE` and the `bc64-v*` trigger already accept the tag).

## [100] utils.bdd gets theodore, hellowrd and a bdos calc; release zip ships both discs — 2026-11-13

Tags: `apps` `build` `tests` `docs`
PR: [#101](https://github.com/bcichonski/bc16/pull/101)
Builds on: #85, #2, #90

### What was built
- `src/bdos/calc.b` is ported to bdos (`#code 0x6000`, `#heap 0xf000`, malloc'd input buffer) and ships as `CALC.PRG` on `utils.bdd`. It is calc v1.1: `h` help, `+ - * /` on unsigned 16-bit decimals (results wrap), `q` → `bye`. New errors: `error: bad number`, `error: division by zero`, `error: unknown command, type h for help`.
- `THEODORE.PRG` moves from `os.bdd` to `utils.bdd`. `HELLOWRD.PRG` is on both discs as the same build. `utils.bdd` holds TEXTED, CALC, HELLOWRD and THEODORE.
- `scripts/make_release.py bc64` also zips `src/utils.bdd`, and a test pins that `release.yml` runs `./makedisc` first.
- New `src/tests/test_e2e_calc.py` with six input scripts, theodore e2e tests moved to the A/B setup, and `test_e2e_utils_disc.py` extended. The goldens lose only the THEODORE row.
- Docs: `docs/05-bdos.md` (layout and program tables), `docs/01-emulator.md`, README, CLAUDE.md files.

### Key decisions reflected in the diff
- calc guards division by zero itself, because the emulator's `alu_div16` crashed on it at the time (before #4). HELLOWRD stays on `os.bdd` as the smoke-test program.

## [85] Separate bootable utils.bdd disc for applications (TextEd first) — 2026-11-12

Tags: `build` `apps` `tests` `docs`
PR: [#99](https://github.com/bcichonski/bc16/pull/99)
Builds on: #37, #89, #92

### What was built
- New `src/utils.bddmanifest`: `BOOTSECT.BIN` 0/0, `DISC.CAT` 0/1, `BDOS.SYS` 2/0 and `TEXTED.PRG` 12/0 (`RX`). It uses the same boot and bdos sectors as `os.bdd`. `./makedisc` builds both discs, and the build is reproducible.
- `TEXTED.PRG` is removed from `src/disc.bddmanifest`. The default session is `os.bdd` in A and `utils.bdd` in B, and TextEd runs after `b:`. `utils.bdd` also boots on its own.
- `run_tests.py` requires `utils.bdd` as a build output, and the `--no-build` hint checks its manifest sources.
- New `src/tests/test_e2e_utils_disc.py` (plan match, catalog, system files byte-identical to `os.bdd`, reproducible, boots alone). TextEd e2e tests run on B, and `os.bdd` tests check that TEXTED is gone. Goldens lose only the TEXTED row.
- Docs: `docs/05-bdos.md`, `docs/01-emulator.md`, README, CLAUDE.md files.

### Key decisions reflected in the diff
- `utils.bdd` is a build output, not committed (since #92), and its catalog comes from the manifest.

## [89] e2e tests: derive disc positions from the manifest instead of pinning tracks/sectors — 2026-11-12

Tags: `tests` `build`
PR: [#96](https://github.com/bcichonski/bc16/pull/96)
Builds on: #37, #92, #49

### What was built
- `src/tests/e2e_harness.py` has `DISC_MASKS` for sessions that load from the system disc. It masks only layout numbers: the `SIZE TT SS LL` of each `ls` line, the hex free-sector count in `catalog entries free; HHHH sectors free` and lines that are only progress dots. Names, attributes, line order and line presence are never masked.
- New harness helpers `planned_entries`, `planned_entry` and `ls_line` read positions from `ftool_mkdisc.plan_disc()` on `src/disc.bddmanifest`. Tests compute the expected `ls` line from them instead of pinning it. They are used by `test_e2e_bdos`, `test_e2e_theodore`, `test_e2e_texted`, `test_e2e_disc` and `test_bc64_smoke`.
- The disc-dependent goldens (8 files) and `smoke_transcript.txt` are now stored masked.
- `run_tests.py --update-golden` sets `BC64_UPDATE_GOLDEN=1` for the e2e suite only, and still builds first unless `--no-build` is given. The smoke transcript test has the same update mode. CI's golden-regeneration step now calls `run_tests.py --group e2e --no-build --update-golden`.
- New `src/tests/test_e2e_layout_shift.py` builds a disc in a temp dir with `HELLOWRD.PRG` grown by 8 zero sectors, which moves every later file. It runs the position-sensitive scenarios on that disc and compares them, masked, with the committed goldens. It only compares and never writes a golden.
- Harness self-tests for the masks and planned entries, and `test_run_tests.py` cases for `--update-golden`.
- Docs: "Masks and derived positions" in `docs/01-emulator.md`, plus the refresh command in `CLAUDE.md`/`src/bc64/CLAUDE.md`.

### Key decisions reflected in the diff
- `plan_disc()` is the single authority. Derived checks read the manifest, not the built disc's catalog, so a disc that disagrees with the manifest fails.
- `SIZE` is masked on every `ls` line, not on a list of "files that can grow", which would itself be pinned data.
- The toolchain, bdio-buffered and bcOS goldens stay unmasked because their output does not come from the system disc.

## [92] Build before test: stop committing the ROM, os.bdd and smoke.bdd (rest of #90) — 2026-11-12

Tags: `build` `tests`
PR: [#94](https://github.com/bcichonski/bc16/pull/94)
Builds on: #90, #37, #50

### What was built
- `src/bc81asmc/bcOS/bcos_v1_2_0.b81`, `src/os.bdd` and `src/bc64/testdata/smoke.bdd` are deleted. `.gitignore` now ignores all ROMs and discs.
- `run_tests.py` builds the ROM and discs before the e2e suite (`--group e2e` or `all`) by running `./buildos && ./buildtools && ./buildapps && ./makedisc` once in `src/`. `--group unit` never builds. `--no-build` skips the build, and a missing ROM, `os.bdd` or manifest source is then reported as FAIL with the path and the build command. If the build fails, e2e is reported FAIL and the other suites still run.
- Every e2e test boots a temp copy of the built `os.bdd`. `SMOKE_DISK` is removed from the harness, and `test_bc64_smoke` runs the transcript test on `os.bdd`.
- The real-ROM tests moved from `test_bc64_cli.py`/`test_bc64_toolchain.py` to the new `src/tests/test_e2e_rom.py`, which boots the freshly built ROM headless without a floppy.
- `src/run` checks for the ROM and `os.bdd` first and exits 1 naming what is missing and the build command. Tests are in the new `src/tests/test_run_script.py`.
- `scripts/make_release.py bc64` takes the ROM and `os.bdd` from the working-tree build (mode 0644) and fails with the build command when they are missing. The other files still come from git objects.
- CI: the e2e job runs `run_tests.py --group e2e`, which builds. The "refresh frozen smoke disc" and "check smoke disc is current" steps are gone, and a final guard step fails on any `git status` change after the build and tests. `release.yml` is simplified to match.
- Docs: design decision G12 is rewritten to "only sources are committed; build before test", and G3 is marked superseded. README, `CLAUDE.md` and component docs describe building after a fresh clone.

### Key decisions reflected in the diff
- The build is triggered by the e2e suite inside `run_tests.py`, so CI and local runs use the same code path.
- No hand-made `.bdd` fixtures remain. `smoke.bdd` was only a copy of `os.bdd`, so the harness uses the built disc everywhere.

## [14] Compiler: quiet output by default, debug prints behind --verbose — 2026-11-12

Tags: `compiler` `build` `tests`
PR: [#93](https://github.com/bcichonski/bc16/pull/93)
Builds on: #10, #12

### What was built
- New `src/bc/bc_log.py` holds the compiler's output channels. `trace` goes to stdout and only with `--verbose`. `info` always goes to stdout. `error`/`warning` go to stderr as `<file>: error: <message>`, or `<file>:<line>:<col>: error: …` once a location is known, and `error_context` prints the source line with a caret.
- `bc.py` and `bc_ast.py` route every trace print through `bc_log`. Without `--verbose`, a successful compile prints one line, `bc: <infile> -> <outfile>`. An error is one stderr line with exit code 1 and no `.basm` output; the traceback is printed only with `--verbose`.
- `--verbose` prints the old trace unchanged and still writes `<name>.genb`.
- `src/bcc` and the `bcc` console command (`bc64_toolchain.py`) no longer pass `--verbose` to the compiler, so a build prints one line per program and writes no `.genb`.
- New `src/bc/tests/bc_output_tests.py` covers quiet vs verbose output, the summary line, the error format and the exit code. There is also a `bcc` launcher test in `test_bc64_toolchain.py`.
- Docs: design decision C6, `docs/03-compiler.md` and `src/bc/CLAUDE.md`.

### Key decisions reflected in the diff
- A module-level helper is used rather than a `Context` attribute, because trace sites sit in `Scope`, `Context`, the AST nodes and the preprocessor. `bc.preprocess(…, verbose, …)` and `bc.compile(ast, verbose)` keep their signatures.
- The error header matches the assembler's (#10), so source locations (#28) only need to be added.
- There is one level, `--verbose`, with no separate `--trace`.

## [90] Build cleanup: GitHub Release zips instead of release/ folders, and rules for which build outputs are committed — 2026-11-12

Tags: `build` `tests` `docs`
PR: [#91](https://github.com/bcichonski/bc16/pull/91)
Builds on: #12, #37, #50

### What was built
- The whole `release/` folder is deleted: the frozen `bc16_v1.0` and `bc32_v1.0` emulators, SDKs, tapes and discs.
- New `scripts/make_release.py` (stdlib only):
  - `bc64 --tag NAME` zips the tracked files of the current machine into `NAME.zip`, leaving out tests, test data, CI and planning docs.
  - `legacy bc16|bc32` rebuilds `<gen>-v1.0.zip` from `release/<gen>_v1.0/` at `7d4cda9`, plus `rom/`. The bc32 ROM comes from the release commit `6304761`. The bc16 ROM is assembled from `bd2498a`'s `bcos.basm` with that commit's assembler.
  - `notes` prints a generation's release notes from the README.
  - Everything is read from git objects. Tests are in `scripts/tests/test_make_release.py`, run as the new unit suite `release`.
- New `.github/workflows/release.yml` runs on `bc64-v*` tags: install, build, tests, zip, upload and create the GitHub Release. README has a "Releases" section with the commands for the owner to publish the legacy zips.
- `.gitignore` is rewritten as one commented block. All `.btap` and `.sectors` files, compiler `.basm` under `src/bdos/` (except `boot.basm`), all `.b81` except the current ROM, and all `.bdd` except `os.bdd`, `utils.bdd` and the test fixtures are now ignored. `src/bdos/testb.sectors` stays tracked.
- 60 generated files are untracked: every `src/bdos` `.basm`/`.btap`/`.sector(s)`, `src/bc/code/*`, `bcos.btap`, the old ROMs `bcos_v1_1_0.b81`/`bcos_v1_1_1.b81` and `src/bdos.bdd`.
- `bc.py` writes a `; generated by bc from <file>.b - do not edit` header on every `.basm`. This is tested in `src/bc/tests/bc_header_tests.py`.
- Tests moved next to their tool: `src/bc/tests/`, `src/bc64/tests/`, `src/bc81asmc/tests/`, and `src/tests/` for the tools directly in `src/` (ftool, launcher, runner, whole-system e2e, `e2e_harness.py`). `run_tests.py` follows them. It reports a missing disc-manifest source as an e2e FAIL with the build command instead of running.
- CI: the unit job uses `fetch-depth: 0` for the release tests. The e2e job builds the ignored intermediates, restores the committed ROM/`os.bdd` with `git checkout`, and fails if the build leaves any status change.
- Docs: new design decision G12, G3 and G9 rewritten (generations are frozen as tagged GitHub Releases), and the component docs and `CLAUDE.md` files are updated for the new paths and build steps.

### Key decisions reflected in the diff
- Publishing is left to the owner: the PR adds the tooling and workflow but pushes no tags and creates no releases.
- The bc32 zip takes its ROM from `6304761`, not `7d4cda9`. The later copy crashes the bc32 emulator at start.
- CI rebuilds the intermediates but never compares rebuilt outputs with the committed ROM/disc. The owner ruled out a rebuild-equals-committed test.

## [37] bdos: build os.bdd from a disc manifest (ftool mkdisc) instead of a hand-made catalog — 2026-11-11

Tags: `bdos` `filesystem` `build` `tests`
PR: [#88](https://github.com/bcichonski/bc16/pull/88)
Builds on: #2, #47, #49

### What was built
- New `src/ftool_mkdisc.py`: `parse_manifest`, `plan_disc`, `encode_catalog`, `build_image` and `mkdisc`.
  - It reads a text manifest with one `NAME.EXT SOURCE ATTRIBS [role=boot|catalog|system] [at=T/S] [max=N]` per line, places the files back to back, numbers all 248 catalog entries and writes the `.bdd`.
  - Each role's hardware rules are enforced: boot is `at=0/0 max=1`, 128 bytes, with the `BD 05 01 01` signature; the catalog is `DISC.CAT -` at `0/1 max=31`; system is at `2/0`. `max=N` checks the size and reserves a slot.
  - All checks run before anything is written. On error it raises `MkdiscError`, and no output file is left behind.
- `ftool mkdisc MANIFEST OUT` dispatches to it and prints `mkdisc: error: …` with exit 1.
- New `src/disc.bddmanifest` holds the system disc layout: boot, catalog, `BDOS.SYS` at `2/0 max=160` (the whole boot-loader range), `LS.PRG` at `12/0`, then the other programs, `TEST.B` and `THEODORE.PRG` back to back.
- `makedisc` builds `os.bdd` with one `./ftool mkdisc disc.bddmanifest os.bdd` instead of 13 `importsector` calls. `src/fcat0800.sector` (the hand-made catalog) is deleted.
- `os.bdd`/`smoke.bdd` are rebuilt. Catalog lengths now come from the real builds: `CP.PRG` is 57 sectors, which fixes the truncation behind #49's `expectedFailure` cp test, now a normal test. HELLOWRD is 14 sectors, and later files moved.
- Tests:
  - `src/test_ftool.py` (≈550 lines) covers manifest parsing, placement, role rules, limits and validate-then-write.
  - New `src/test_e2e_disc.py` checks `os.bdd`/`smoke.bdd` against the manifest, that a corrupt length or source byte is detected, `ls -a` listing every file, and every utility printing its usage and returning to the shell. New goldens are `disc_help` and `disc_ls_all`.
  - `CATALOG_LINES` and the `bdos_ls`/`bdos_rm`/`bdos_hellowrd` goldens are updated.
- Docs: design decision D8. The layout requirements moved from `docs/05-bdos.md` and `src/bdos/bdos.md` into the manifest, and the docs now refer to it. There is also a caveat that discs copied before #37 number only catalog entries 0–15.

### Key decisions reflected in the diff
- The manifest is named `.bddmanifest` because `.gitignore` has `*.manifest`, so `.gitignore` is untouched.
- `BDOS.SYS` covers all 160 loader sectors, zero after the build, so the catalog says exactly what the loader reads.
- At most 247 of the 248 entries can be used. With all 248 in use, `bdio_fcat_read` would report end-of-catalog.
- The old `createbdd`/`importsector`/`exportsector`/`dumpsector` commands are kept.

## [2] Port "Looking for uncle Theodore" game to bdos system disc — 2026-11-11

Tags: `apps` `bdos` `abi` `emulator` `devices` `build` `tests`
PR: [#87](https://github.com/bcichonski/bc16/pull/87)
Builds on: #1, #49

### What was built
- New bdio call `BDIO_RANDOM` (`0x1a`) in `bdio.b`. `bdio_random(max)` reads two bytes from the RNG port `0x05` (`BDIO_RNG_PORT`) and returns the 16-bit word, or `word % max` when `max` isn't 0. Both constants are in `bdioh.b`.
- New opt-in include `src/bdos/random.b` with `random(max)`, a wrapper around `bdio_call(BDIO_RANDOM, …)`. It must be included after `bdosh.b`.
- `theodore.b` is v1.1. It includes `bdosh.b` + `random.b` instead of `stdio.b`, and the "What time is it?" seed prompt (`getRandomSeed`) is replaced by `random(MAXSTOPS)`. The stop numbers are `word`s, the prompt reads `(0..99) or 100 to quit`, and the title typo ("ucle") is fixed.
- `THEODORE.PRG` is on `os.bdd` at 53/0 (38 sectors). `buildapps` builds it, `makedisc` imports it, and `fcat0800.sector` has its catalog entry. `bdos.basm`/`.btap`/`.sector` are rebuilt for the new call.
- Emulator: `bc64.py --random-seed N` (decimal or `0x` hex, ≥ 0) seeds `RandomGenerator` so port `0x05` is reproducible. `run_session(seed=)` in `e2e_harness.py` passes it through.
- Tests:
  - New `src/test_e2e_random.py` with `testdata/e2e/random_prog.b` checks bounded values, same seed gives the same output, and different seeds give different output.
  - New `src/test_e2e_theodore.py` checks the catalog entry and `ls`, a seeded game played to "found", quitting with 100 or a value over 255, and different seeds giving different secret stops.
  - Seeded `RandomGenerator` unit tests and `--random-seed` CLI tests. The `bdos_ls`/`bdos_rm` goldens and the smoke transcript are updated.
- Docs: design decision D7 (optional services are opt-in includes), `BDIO_RANDOM` in `docs/05-bdos.md`, and `--random-seed` in `docs/01-emulator.md`.

### Key decisions reflected in the diff
- The RNG is a bdos call with its wrapper in its own include, not in `bdosh.b`. The compiler links every function of every include, so programs that don't use it don't grow.
- The seed comes from port `0x05`, not the RTC.
- The bdos version stays `bDOS 1.1`: a new call number doesn't change the existing ABI.

## [1] Complete TextEd v1.2 on bdos 1.1 (load/save, rebuild system disc) — 2026-11-11

Tags: `apps` `build` `tests`
PR: [#86](https://github.com/bcichonski/bc16/pull/86)
Builds on: #47, #49

### What was built
- `texted.b` checks for missing arguments by testing the word's first byte (`peek8(Pwstart)`, `peek8(Pwend)`) instead of the pointer. `s` without a name, `l` without a name, and `i`/`p`/`d` with missing numbers now print an error and do nothing.
- The build scripts `buildos`, `buildtools`, `buildapps`, `makedisc`, `ftool`, `run` and `run_tests` are now file mode `100755`. A new root `.gitattributes` keeps them and `bcc` LF. `buildos`, `ftool` and `run` pick `winpty python` on Git Bash, else `python3`, else `python`, so `cd src && ./buildos && ./buildtools && ./buildapps && ./makedisc` works on Linux.
- `texted.basm`/`.btap`/`.sectors` are rebuilt (TEXTED.PRG is 14334 of 14336 bytes in its 112-sector slot), `os.bdd`/`smoke.bdd` are refreshed, and `bcos.btap` is rebuilt (it was stale).
- New `src/test_e2e_texted_commands.py`: save or load without a name, a name over 12 characters, and insert/print/delete with missing numbers.
- New `src/test_e2e_texted_flows.py`: the start-up banner, insert/print/delete/save with the `ls` size check, and a large file that loads after a restart, with `m` still working.
- Docs: the `texted` row in `docs/05-bdos.md` and the build instructions in `CLAUDE.md`.

### Key decisions reflected in the diff
- Only TextEd is fixed. #82 (one `strnextword` for all tools) stays open, because changing `strings.b` rebuilds every program and TEXTED had almost no room left.
- The disc layout doesn't move: TEXTED stays at 45/0 with 112 sectors.
- The planned full-rebuild e2e check (`test_e2e_build.py`) was removed at the owner's request ("too rigid"). A full rebuild stays a manual check.

## [8] Assembler modernisation: .assert directive to enforce memory-map and ABI addresses — 2026-11-10

Tags: `assembler` `compiler` `bdos` `abi` `tests`
PR: [#84](https://github.com/bcichonski/bc16/pull/84)
Builds on: #10

### What was built
- New `.assert <a> <op> <b>` directive in bc81asmc (`ASSERT` node in `bc81asmc_ast.py`, `dASSERT` in the grammar).
  - Operands are a `:label`/`.def` name or an 8/16-bit hex literal. The operators are `=` `!=` `<` `<=` `>` `>=`.
  - It emits no bytes. `compile()` evaluates all asserts in pass 2 and reports `assertion failed: <l> <op> <r> (0xLLLL <op> 0xRRRR)` or `undefined label` through the #10 diagnostics.
- `boot.basm` ends with `bd_end: .assert :bd_end <= 0x0e80`, so the boot loader must fit its 128 bytes.
- The compiler (`bc_ast.py` `Context`) ends every program with `sys_codeend: .assert :sys_codeend < <heap>`.
- New preprocessor line `#codelimit 0xHHHH` (per compile) adds a second assert. `bdos.b` uses `#codelimit 0x5d00` so bdos ends below the file buffers (`BDIO_FDESCBUF_ADDR`).
- All built programs are regenerated with the end-of-image asserts (one line each in `bdos`, `ls`, `cp`, `format`, `rm`, `cha`, `cat`, `helloworld`, `texted`).
- Tests:
  - New `bc81asmc_assert_tests.py` covers the grammar, operators, failure and undefined-operand messages, and no bytes emitted.
  - New `bc81asmc_contract_tests.py` adds the bcOS contract asserts (`os_metacall = 0x0008`, `os_metatab = 0x000c`, `user_mem <= 0x0d80`) to `bcos.basm` and checks they hold and fail when broken.
  - New `bc_assert_tests.py` covers the compiler's emitted asserts and `#codelimit`.
- Docs: decisions A3 (the `.assert` exception to "no expressions"), A6 and G2, `docs/02-assembler.md` and `docs/03-compiler.md`.

### Key decisions reflected in the diff
- `.assert` is a check, not an expression language: no arithmetic, and `=` means equality.
- The end label sits on the assert line, so it takes the current address and costs no bytes.
- The bdos limit is a generic `#codelimit` preprocessor line rather than a special case in the compiler or inline `asm` in `bdos.b`.
- The bcOS asserts are added only in memory by the contract test. `bcos.basm` itself is left for #30.

## [12] Assembler modernisation: replace Python 3.7 Pipfile with a top-level pyproject.toml — 2026-11-10

Tags: `build` `tests`
PR: [#83](https://github.com/bcichonski/bc16/pull/83)
Builds on: #50, #13

### What was built
- New root `pyproject.toml` (setuptools ≥ 64): project `bc64` 1.0.0, `requires-python >=3.10`, `dependencies = ["parsy>=2.2,<3"]`, MIT license. It defines console scripts `bc64`, `bc81asmc`, `bcc` and `ftool`. Only the launcher module is packaged (`package-dir = src`, `py-modules = ["bc64_toolchain"]`).
- New `src/bc64_toolchain.py` launcher. It runs the existing scripts in-process with `runpy` (script directory first on `sys.path`, caller's cwd and arguments untouched). `bcc` runs `bc.py` then `bc81asmc.py` as child processes. A missing source tree prints the `pip install -e .` hint and exits 1.
- `src/bc81asmc/Pipfile`, `Pipfile.lock` and the root `requirements.txt` are deleted, and `run_tests.py`'s hint says `pip install -e .`.
- CI installs with `pip install -e .` with the pip cache keyed on `pyproject.toml`. The unit job runs `bc64`/`bc81asmc`/`bcc --help` and `ftool createbdd` from outside the checkout.
- New `src/test_bc64_toolchain.py` checks that each console command matches its script (run outside `src/`), help/usage, error exit codes, `bcc` stopping after a compile error, and the install hint without a traceback when the source tree is missing.
- Docs: install steps in `README.md`, `CLAUDE.md`, `docs/README.md` and the component docs. Design decisions are updated.

### Key decisions reflected in the diff
- A launcher module rather than package imports: flat imports and the per-directory test commands stay exactly as they were.
- Editable install (`pip install -e .`) is the only supported install, because the tools run from the source tree.
- The build scripts (`bcc`, `ftool`, `buildos`, …) are not changed.
- CI checks `ftool` with `createbdd`, because `ftool` with no arguments exits 1.

## [10] Assembler modernisation: error messages with file:line:column — 2026-11-10

Tags: `assembler` `bcos` `b-stdlib` `tests`
PR: [#81](https://github.com/bcichonski/bc16/pull/81)

### What was built
- New `src/bc81asmc/bc81asmc_diag.py` holds the `Diagnostic` record, the `AssemblerError` exception, `format_diagnostic`, `line_col_at` and `parse_error_to_diagnostic`. Diagnostics are 1-based `file:line:col: error: message`, followed by the source line and a `^` caret, with a tab counting as one column.
- The grammar records positions with a zero-width `pos` parser and `SourceName` (a `str` that carries `line`/`col`) for label definitions, references and `.def` names.
- `compile()` collects all diagnostics instead of raising on the first one:
  - undefined labels (one per use);
  - out-of-range 7-bit/15-bit relative jumps (the old wording is kept);
  - code past `0xffff`;
  - `cannot encode '<line>': …` for operands the encoder can't handle (the line emits no bytes);
  - duplicate labels, duplicate `.def` names and label/`.def` clashes, naming the line of the first definition.
- A label or `.def` at `0x0000` now counts as defined.
- `main()` prints parse errors (the first one only) and compile errors to stderr. It exits 1 without writing an output file, and adds the traceback with `--verbose`. Progress lines stay on stdout.
- The two duplicate definitions in committed sources are renamed. The first `exec_load_end` in `bcos.basm` is now `exec_load_err`, and the first `strnextword` in `strings.b` is now `strnextwordnull`. The bdos `.basm` files are regenerated, and all `.btap` files are byte-identical.
- New tests:
  - `bc81asmc_diag_tests.py` covers the formatter and parse-error conversion.
  - `bc81asmc_compile_diag_tests.py` covers the collected errors.
  - `bc81asmc_cli_tests.py` covers stderr, exit 1 and no output file.
  - The emit and opcode-agreement tests are adjusted.
- Docs: an "Errors" section in `docs/02-assembler.md`, design decision A6, and `src/bc81asmc/CLAUDE.md` (how new checks report).

### Key decisions reflected in the diff
- Parsing stops at the first syntax error, because parsy's `many()` cannot resume. The later passes run to the end, so all undefined labels show in one run.
- Duplicate definitions are now errors instead of "last one wins". The renamed first `strnextword` is kept as dead code because deleting it would change the size of every program.

## [7] Emulator memory must be the full 64 KB (0x0000-0xffff) — 2026-11-10

Tags: `emulator` `devices` `abi` `tests`
PR: [#80](https://github.com/bcichonski/bc16/pull/80)
Builds on: #3, #49

### What was built
- `bc64.py` replaces `TOPMEM` (`0xffff`, used as a size) with `MEMORY_SIZE = 0x10000`, `TOP_ADDRESS = 0xffff` and `STACK_TOP = 0xfffe`. Memory is the full 64 KB.
- A start-up step, `Bc64.write_top_kil()`, puts `KIL` at `0xffff`, so running or jumping to the end of memory halts. `dump_mem` writes all 65536 bytes.
- `Bc8183` takes `stack_top` from its owner. `Bc64` passes `0xfffe`, and a bare CPU keeps `membus.size - 1`.
- New `stack_fault` check in `PSH`, `POP`, `CAL` and `RET`. A stack access past the top of memory (empty stack) or below `0x0000` (overflow) stops the CPU like `KIL`, with registers and memory untouched. It prints `<op> at <pc>: <reason>, CPU stopped` on stderr and in the debug trace, and the exit code is 0. The stack dump handles an empty or incomplete stack.
- Floppy DMA addresses wrap at `0xffff` (`FloppyDriveV1` read and write).
- Monitor `q` and a bad-argument command (`d 00`) now stop cleanly instead of crashing. New e2e scenarios `bcos_quit` and `bcos_bad_arg` pin this in `test_e2e_bcos.py`.
- New tests:
  - `test_cpu_stack_bounds.py` covers empty-stack and overflow stops, round trips at the top of memory, and the stack dump.
  - `test_dma_wrap.py` covers sector reads and writes across `0xffff`.
  - `test_membus.py` covers the constants, both ends of memory, `KIL` at `0xffff` and PC wrap.
  - `test_bc64_cli.py` covers the 64 KB dump ending in `KIL` and a clean stop with exit 0.
- Docs: the memory map in `docs/01-emulator.md`/`docs/05-bdos.md` (stack from `0xfffe`, `0xffff` = `KIL`) and the design-decision memory map.

### Key decisions reflected in the diff
- The size, top address and stack top are three separate constants, and `TOPMEM` is removed rather than kept as an alias.
- The stack is the one place that fails. The PC, register pairs and DMA wrap modulo `0x10000`.
- `MemBus` stays a plain sized bytearray. The CPU and DMA handle bounds and wrap.
- bcOS is not changed: `q` and bad arguments were empty-stack `RET`s, and the clean stop is enough.

## [47] TextEd: file saved before a restart loads but shows no text — 2026-11-09

Tags: `apps` `build` `tests`
PR: [#77](https://github.com/bcichonski/bc16/pull/77)
Builds on: #76, #49

### What was built
- `texted.b` `l <file>` now actually loads: `loadFile` opens the file in buffered mode (was sector mode) and `readLines` parses `<number> <text>` records as it reads 128-byte chunks, so a record can span chunks. It inserts each one with `insertLineBuf`. Before, it only printed the raw lines. Records with no valid number (over 65535 or not digits) or no text are skipped, and text longer than `MAXLINELENGTH` is truncated.
- `l` replaces the buffer: the existing lines are freed only after the file opens. A missing file prints the bdio error and keeps the buffer.
- New `fileArg` helper shared by `s` and `l`: it parses `<file>`, normalises the name and prints `saving|loading <file>...`. It also fixes `poke16(Pwend, NULLCHAR)`, which wrote a byte too far, to `poke8`.
- TextEd list fixes: `findPreviousLine` handles reaching the end of the list (`PcurrLine = NULL`), and `insertLineBuf` appends after the last line without reading through a NULL `PnextLine`. The input buffer and `readsn` are `MAXLINELENGTH + 1`, and the `h` help says `l` replaces the buffer.
- `cat.b` `-c`: `printchars` carries the line length across sectors (`printbuf` and `printfile` pass `linelen` through), and the newline after each sector is now only printed in hex mode. A record that crosses a sector boundary is shown on one line.
- Every disc program is rebuilt from source (`boot`, `cat`, `cha`, `cp`, `format`, `helloworld`, `ls`, `rm`, plus the first committed `texted.basm`/`.btap`/`.sectors`). `fcat0800.sector` and `os.bdd` are updated: `CAT.PRG` is 62 sectors and `TEXTED.PRG` 112.
- `TEST.B` is now `src/bdos/testb.sectors`, which `makedisc` imports at 52/0, so a full `makedisc` gives a bootable disc.
- New `src/test_e2e_texted.py` (5 scenarios): save → restart → load, a file over one sector with 80-character lines, a missing file keeping the buffer, load replacing a non-empty buffer, and `cat -c` showing saved records whole. Golden `texted_roundtrip.golden.txt`.
- `smoke.bdd`/`smoke_transcript.txt` refreshed. The `bdos_cat`/`bdos_ls`/`bdos_rm` goldens and `CATALOG_LINES` in `test_e2e_bdos.py` are updated for the new catalog.
- Docs: a "TextEd file format" section and the updated catalog table in `docs/05-bdos.md`; design decision D6.

### Key decisions reflected in the diff
- The on-disc text format stays as it was: records end in `0x13` (the `CHAR_LF` of `texted.b` and `cat.b`), with one `0x00` after the last record and zero padding after that. Switching to `0x0a` was rejected because it would break existing files and `cat -c`.
- The committed build outputs were stale and gave an unbootable disc, so the whole program set was rebuilt rather than only TextEd.
- The `CP.PRG` catalog entry was deliberately left at 56 sectors (the build is 57). Fixing it flips #49's `expectedFailure` cp test, so the catalog was not synced to the builds wholesale.

## [76] bdos: buffered file I/O (bdio_fbinbufread / bdio_fbinbufwrite) loses and misreads data — 2026-11-09

Tags: `bdos` `build` `tests`
PR: [#78](https://github.com/bcichonski/bc16/pull/78)
Builds on: #49, #50

### What was built
- `bdio.b` `bdio_fbinbufread` was rewritten as one loop. It refills the handle's sector buffer when it is used up, copies `min(left in buffer, length)` from the buffer offset, and returns the bytes copied (a `word`, was `byte`). That count is less than `length` only at end of file, and `0` at EOF. The debug `printf`s are gone.
- `bdio_fbinbufwrite` was rewritten to match. It fills the buffer in chunks of any length and writes a sector to disc as soon as the buffer is full. It returns the bytes accepted (`word`), and `bdio_fclose` flushes the rest.
- Both calls check the handle's direction bit, its descriptor number and buffered mode before doing anything, and return `0` for a handle that isn't valid buffered I/O.
- `bdio_fbinopen_internal` sets up a buffer only for a valid handle, and starts a read handle's buffer counter at 128 (used up). `bdio_getfdesc_addr` moved above it.
- Rebuilt `bdos.basm`/`.btap`/`.sector`. `os.bdd` and `smoke.bdd` carry the new `BDOS.SYS`.
- New e2e test `src/test_e2e_bdio_buffered.py` with `testdata/e2e/bdio_buffered_prog.b`. It writes a 589-byte pattern in mixed chunk sizes, reads it back in other chunk sizes, and checks the file on the disc image (data + 51 zero padding bytes). Golden `bdio_buffered_run.golden.txt`. The CI golden-regeneration step includes the new module.
- Docs: the `0x18`/`0x19` return values and a new "Buffered I/O" section in `docs/05-bdos.md` (EOF, flush-on-full/flush-on-close, zero padding, buffer-counter meaning). `src/bdos/bdos.md` points there.

### Key decisions reflected in the diff
- The buffer counter means different things per direction: bytes already consumed on a read handle (128 = used up), bytes pending on a write handle (0..127 between calls).
- File length stays whole sectors. A buffered reader sees the zero padding after the last written byte before it gets `0` (EOF).

## [50] CI: GitHub Actions running the Python unit and e2e tests of all components — 2026-11-09

Tags: `build` `tests`
PR: [#74](https://github.com/bcichonski/bc16/pull/74)
Builds on: #48, #49

### What was built
- `.github/workflows/tests.yml` (`tests`) runs on pushes and PRs to `bc64`, with concurrency cancel and read-only permissions:
  - a `unit` job on a Python 3.10 / 3.14 matrix runs `run_tests.py --group unit`;
  - an `e2e` job (needs `unit`, Python 3.14) regenerates `smoke.bdd` and `smoke_transcript.txt` from `os.bdd`, fails if they differ from the committed copies (`git diff --exit-code src/bc64/testdata/`), then runs `run_tests.py --group e2e`;
  - when e2e fails, the job reruns the e2e modules with `BC64_UPDATE_GOLDEN=1` and uploads the golden patch and `testdata/` as the `e2e-golden-diff` artifact;
  - both jobs end with a guard that fails if a `cpudebug.log` appears or `release/` changes.
- `run_tests.py`:
  - `--group unit|e2e|all`;
  - the suites are chosen by rule (`select_src_modules`) rather than a fixed list: `emulator` (`bc64/test_*.py` and other `src/test_*.py`), `ftool`, `assembler`, `compiler`, and `e2e` (`test_e2e_*.py`, `test_bc64_smoke.py`);
  - `parse_counts` reads unittest's counts (failures, errors, skipped, expected failures);
  - when `GITHUB_STEP_SUMMARY` is set, a Markdown results table is appended to it;
  - a suite with no modules fails.
- New `src/test_run_tests.py` (17 tests): suite selection on a synthetic and the real tree, group filtering, parsing the counts, the summary table, and exit codes.
- Docs: a CI section in root `CLAUDE.md`, a README note, and an update to `docs/analysis/06-toolchain.md`.

### Key decisions reflected in the diff
- The per-component split and the summary are in `run_tests.py`, not in the YAML, so a local run and CI report the same thing from one command.
- The CI e2e artifact comes from regenerating the goldens after a failure, not from changes to the harness.
- Slow e2e scenarios (`BC64_E2E_SLOW`) stay off in CI.

## [49] End-to-end tests on the headless emulator (after #3) — 2026-11-09

Tags: `emulator` `devices` `tests`
PR: [#72](https://github.com/bcichonski/bc16/pull/72)
Builds on: #3, #48

### What was built
- `--no-floppy` option in `bc64.py`. It attaches the new `NoFloppyDrive` in `bc64_io.py` on port `0x08` (reads `0x00`, ignores writes), so bcOS goes straight to the monitor. It counts as a headless option and conflicts with `--disk-a`/`--disk-b` (usage error).
- New `src/e2e_harness.py`, a plain module rather than a test. It provides:
  - `run_session`: boots `bc64.py` on temp copies of the discs, fails on exit 3 or another non-zero exit, and checks that the source discs are untouched and no `cpudebug.log` appeared;
  - `check_golden`: a byte-exact compare with a unified diff, plus a `BC64_UPDATE_GOLDEN=1` update mode;
  - regex masks, marker assertions, and a `@slow` decorator (`BC64_E2E_SLOW`);
  - `read_catalog` / `disc_put`, a BFS catalog reader and a file writer that allocates the way bdos does.
- Scenarios in `src/test_e2e_bcos.py`, `test_e2e_bdos.py` and `test_e2e_toolchain.py`, with scripts and goldens in `src/bc64/testdata/e2e/`:
  - monitor: boot, unknown command, dump/write/print;
  - bdos shell on `smoke.bdd`: boot, `ls`, `cat`, `hellowrd`, `rm` (checked in `ls` and in the catalog), error paths;
  - toolchain: B source → `bc.py` → `bc81asmc.py` → `ftool btap2bin` → put on a disc → boot → run.
- Two bugs found by these tests are kept as `expectedFailure` scenarios with markers only, no golden: the tape `s`/`l` round trip, and `cp` swallowing all the remaining input.
- `src/test_e2e_harness.py` tests the harness itself (the session runner, goldens, masks, the slow decorator, the catalog helpers).
- Docs: an e2e section in `docs/01-emulator.md`, a note in `docs/05-bdos.md`, and design decisions E8 (`--no-floppy`) and E9 (e2e testing).

### Key decisions reflected in the diff
- `IOBus` raises `KeyError` on an unmapped port, so "no drive" is a stand-in device rather than a missing one.
- The disc depends on the scenario: monitor scenarios use `--no-floppy`, shell scenarios use the frozen `smoke.bdd`, and the toolchain scenario uses the live `os.bdd` and compares only the program output.
- Instruction limits are set at about 10x the measured need.
- No golden is ever written from broken output. A known bug is an `expectedFailure` that names its issue.

## [3] Emulator headless mode: disks, tape, keyboard and output from the command line — 2026-11-09

Tags: `emulator` `tests`
PR: [#71](https://github.com/bcichonski/bc16/pull/71)
Builds on: #48

### What was built
- `bc64.py` has an argparse CLI: `rom`, an optional `trace` word, `--disk-a`/`--disk-b`, `--tape-dir`, `--input` (`-` = stdin), `--output` and `--max-instructions`.
- The emulator runs headless when any of those options is given or stdin isn't a terminal. Piped stdin is then typed as keys. Without options and with a terminal, the console `Environment` is used as before.
- Exit codes: 0 for a halt or end of input, 2 for a usage error, 3 when the instruction limit is reached (with a message on stderr), and 1 for an exception.
- `Bc64.run(max_instructions)` is a limited run loop. Without a limit it still calls `cpu.run()`.
- New `ScriptedEnvironment` in `bc64_env.py`:
  - answers `Disk A/B name:` from the options without reading input;
  - reads keys from a file or stdin and folds LF, CR LF and CR into one CR;
  - raises `EndOfInput` when the input runs out, which ends the run cleanly with no memory dump;
  - resolves relative `.btap` names in `--tape-dir`;
  - copies every printer byte to `--output`.
- Tests:
  - `ScriptedEnvironmentTests` (12) in `test_env.py`;
  - `src/test_bc64_cli.py` (24): argument parsing, run and exit codes;
  - `src/test_bc64_smoke.py`: a byte-exact transcript of a bdos session on a frozen `testdata/smoke.bdd`, and a live check of `os.bdd` against markers that survive a rebuild.
  - Test data: `smoke_session.txt`, `smoke_live_session.txt`, `smoke_transcript.txt`, and `.gitattributes` `* -text`.
- Docs: a headless-mode section in `docs/01-emulator.md`, how to refresh the smoke disc and transcript in `src/bc64/CLAUDE.md`, and design decision E7.

### Key decisions reflected in the diff
- Headless mode is a separate environment class, so the console path is unchanged. The limited run loop repeats `cpu.run()` in `bc64.py`, so the two must be kept in step.
- End of input is a clean stop (exit 0, no dump). A script has to check its output as well as the exit code.
- Disk prompts are recognised by their text (`Disk X name:`).

## [48] Tests first: fix the current test suites, then add the missing unit tests — 2026-11-08

Tags: `tests`
PR: [#52](https://github.com/bcichonski/bc16/pull/52)
Builds on: #13

### What was built
- A single runner: `run_tests.py` at the repo root (standard library only). It runs the emulator, assembler and compiler suites as subprocesses, each in its own directory, and prints one PASS/FAIL line per suite. `requirements.txt` lists `parsy`, and `src/run_tests` became a thin wrapper around the runner.
- The emulator tests moved from `src/tests/` to `src/bc64/` (`test_cpu`, `test_io`, `test_mem`, `test_registers`). `test_CLR_opcodes` was fixed: its offsets were wrong, the CPU was right.
- New emulator tests:
  - `test_cpu_alu.py` (93): every `alu`/`alu16` operation, its flags and instruction length;
  - `test_cpu_control.py` (57): nop/kil, mov, jmp/jmr/jrx, stack, call/ret, I/O;
  - `test_devices.py` (45): floppy and tape recorder;
  - `test_membus.py` (13);
  - `test_env.py` (14).
- New assembler tests:
  - `bc81asmc_emit_tests.py` (70): labels, relative offsets, directives, `.btap` writer, error cases;
  - `bc81asmc_opcode_agreement_tests.py`: every grammar form is assembled and run for one instruction on the CPU, with a guard test that fails when a grammar form has no test case.
- New compiler tests: `bc_codegen_tests.py` (35), covering program shape, expressions, variables, control flow, functions, asm, the preprocessor and scope errors.
- New `src/test_ftool.py` (11): btap2bin, creating a `.bdd`, sector import/export, the CLI.
- Tests are silent on a passing run: the debug switches in the test modules are now off.
- Docs: the known quirks in `docs/01-emulator.md` are each linked to an issue (#4, #7), and design decision G11 records the runner and the known-bug policy.

### Key decisions reflected in the diff
- Known-bug policy. A bug whose fix is decided gets a test of the correct behaviour marked `@unittest.expectedFailure` with the issue number: #4 negated `jrx`, #11 `out #r, imm`. A bug whose behaviour is undecided gets a test that pins today's behaviour and names the issue: #4 div/mod by zero, #4 `setate` typo, #7 `TOPMEM`.
- A tests-only story: production defects found while testing were reported, not fixed.

## [13] Compiler: run on Linux/macOS and Python 3.13+ (remove the msilib import) — 2026-11-08

Tags: `compiler` `build`
PR: [#51](https://github.com/bcichonski/bc16/pull/51)

### What was built
- `bc_ast.py` drops the Windows-only `from msilib.schema import Error` (removed in Python 3.13), so the compiler imports on Linux, macOS and Python 3.13+. It defines `class CompilerError(Exception)` instead, used by the scope push/pop errors.
- `bc.py` and `bc_dbg.py` write `.basm`/`.genb` files as UTF-8, so the output no longer depends on the host's default encoding.
- `src/bcc` is now executable and picks `winpty python`, then `python3`, then `python`.
- `TestCompilerError` in `bc_tests.py` checks that `CompilerError` is an `Exception` and that `pop_scope` with no scope raises `Scope none error`.
- Docs: `docs/03-compiler.md`, `src/bc/CLAUDE.md`, root `CLAUDE.md` and `design-decisions.md` no longer describe the msilib workaround.

### Key decisions reflected in the diff
- Only `bcc` changed its interpreter choice, and it keeps `winpty` when present, so the owner's Git Bash workflow is unchanged. The other scripts still call `winpty`.
- Newline handling was left as is (native text mode). Only the encoding was pinned, and the committed outputs were not rebuilt.
