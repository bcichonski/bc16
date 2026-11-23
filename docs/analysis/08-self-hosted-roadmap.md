# Self-hosted toolchain: delivery order (roadmap, 2026-11-19)

The step-by-step order of work for roadmap items 8 and 9: an assembler, a linker and a B
compiler running on the BC64. The design and the reasons are in
[07-self-hosted-compiler.md](07-self-hosted-compiler.md); this page is only the order, and
each step is a GitHub issue. All new issues carry the `self-compiler` label.

The order is: **fixes** (emulator, assembler, compiler, bdos) → **host assembler writes `.o`**
→ **assembler on the BC64** → **linker on the BC64** → **compiler passes** → chaining.

The "Done" column marks finished steps with the PR that closed the issue (status on
2026-11-23: steps 1–17, 21 and 26–28 are done; phase 0 still has 18–20, 22–25, 29 and 30).

Work one step at a time, top to bottom. Steps inside the same phase and track can sometimes
run in parallel (the "Track" column), but every step depends only on steps above it.

## Phase 0: fixes

Settle the machine, the assembler's encodings and the B language **before** anything is
frozen: the runtime in `runtime.basm`, the encoder that BASM copies, and the code templates
that BCC3 copies.

| Step | Done | Issue | Track | What | Why it comes first |
|---|:-:|---|---|---|---|
| 1 | ✅ #134 | #111 | bdos | a new file overwrites an existing one after `rm`; `ls` free count | data loss; every compile creates and deletes files |
| 2 | ✅ #135 | #15 | compiler | golden code-generation tests and size tracking | the safety net for every later host change |
| 3 | ✅ #137 | #4 | emulator | `jrx` negation bit, division by zero, FDD state typo | every `if`/`while` uses `jrx`; the linker encodes it |
| 4 | ✅ #139 | #53 | emulator | zero flag from the unwrapped result | runtime comparison helpers depend on flags |
| 5 | ✅ #143 | #54 | emulator | overflow/carry semantics, borrow. **Decided (2026-11-20):** `C` = unsigned carry/borrow, `O` = signed overflow ([E13](../specs/memory/design-decisions.md)) | same |
| 6 | ✅ #141 | #55 | emulator | `shl`/`shr` flags. **Decided (2026-11-20):** `Z`/`N` from the stored result, `C` = last bit shifted out, `O` = a 1 bit shifted out for `shl` and 0 for `shr`; the same for 16-bit (E12) | same |
| 7 | ✅ #147 | #56 | emulator + assembler | register forms of `shl`/`shr`. **Settled (2026-11-22):** no code change; register counts use the long form `58 ro` ([E15](../specs/memory/design-decisions.md)) | an encoding decision BASM must copy |
| 8 | ✅ #138 | #57 | emulator + assembler | 16-bit pair ops ignore the second operand. **Decided (2026-11-19):** the CPU keeps the implied second pair (`csci`→`dsdi`, `dsdi`→`csci`, `af`→`csci`) and the assembler enforces it; BASM must apply the same rule | same |
| 9 | ✅ #140 | #58 | emulator + assembler | 16-bit results in `A:F`. **Decided (2026-11-20):** `af` stays allowed as a 16-bit destination and the CPU is unchanged: `A` gets the high byte of the result, `F` the flags, and the low byte is lost. Use `csci` or `dsdi` for 16-bit arithmetic ([E14](../specs/memory/design-decisions.md)) | same |
| 10 | ✅ #144 | #59 | emulator | confirm `RET` behaviour with push frames. **Decided (2026-11-20):** two push frames on top make a computed jump (`psh lo; psh hi; ret`); a single push frame or an unknown tag stops the CPU like `KIL` (E4) | before the ABI is frozen |
| 11 | ✅ #142 | #64 | assembler | a label at address `0x0000` is "not defined" | **blocker for `--obj`**: every section starts at offset 0 |
| 12 | ✅ #151 | #65 | assembler | fix-ups after a second `.org`. **Decided (2026-11-22):** a second `.org`, or one after code or a label, is an error (A10) | object files allow `.org` only on the first line |
| 13 | ✅ #145 | #66 | assembler | `inc af` / `dec af` don't parse | BASM copies the grammar |
| 14 | ✅ #152 | #67 | assembler | `clr af` crashes. `clr` is a relative call; `clr af` is rejected with a clear message (A9) | same |
| 15 | ✅ #153 | #11 | assembler | `out #r, imm` encoding (owner decided: fix): `Dr HH`, port register `a`, `ci` or `di` only (A11) | same |
| 16 | ✅ #149 | #103 | assembler | a label on a line of its own | needed by #104 |
| 17 | ✅ #148 | #19 | compiler | token-based `#define` | PRE (shared by BASM and BCC) uses the same rule |
| 18 |  | #20 | compiler | `return` anywhere | implemented once, the same in BCC2 |
| 19 |  | #104 | compiler | no `nop` at labels and function starts | the template set BCC3 copies |
| 20 |  | #68 | compiler | undeclared variable crashes | errors, not crashes, in the oracle |
| 21 | ✅ #154 | #69 | compiler | unknown-operator error crashes | same |
| 22 |  | #29 | compiler | runtime clean-up | before the runtime moves to `runtime.basm` |
| 23 |  | #16 | compiler | **host `bc` drops unused functions and runtime routines** | BASM and BLINK are built by `bc`; BASM's 25–30 KB estimate is close to the 32,640-byte file limit. Split the runtime so each piece becomes one `.sect` in #116 |
| 24 |  | #34 | compiler | spike: hot-path helpers inline, private or ROM | if inlined, the templates change; must be before #131 |
| 25 |  | #41 | bdos | reuse freed disc space (first fit, largest gap) | every compile leaves 20–30 KB of holes; replaces the `pack` utility of the earlier plan |
| 26 | ✅ #150 | #73 | bdos | `cp` never makes the copy (already fixed by #37; regression tests added) | needed to move `.O` and `.PRG` files between discs |
| 27 | ✅ #155 | #82 | bdos | `strnextword` never returns 0. One `strnextword` that returns the NUL address, never 0 (D9) | every new tool's "no name → usage" check |
| 28 | ✅ #156 | #38 | bdos | bdio error codes. One code per meaning; `BDIO_FOPEN_FDD_NOT_READY` = `0xe1`, `0xe5` retired | the new tools report them; it's an ABI |
| 29 |  | #43 | bdos | shared argument parsing (`[d:]name`) | BASM, BLINK and BCC parse the same arguments |
| 30 |  | #112 | ftool | `importtext` / `exporttext` | e2e tests put sources on a disc in texted format |

Optional in this phase: #61 (DMA address `0xf0xx` read as PING), #5 (shared ISA table and a
disassembler: helps test BASM's encoder), #9 (listing and symbol map: helps read
byte-identical diffs).

Not in this plan: #18 (precedence; today's quirks stay in B 1.4), #21–#26 (language
features: each would have to be built twice), #17, #27, #28, #33.

**Exit:** the e2e suite passes; `rm` then create keeps other files intact and reuses the
freed space; every program is smaller after #16 and the sizes are recorded.

## Phase 1: the host assembler writes object files

| Step | Done | Issue | What |
|---|:-:|---|---|
| 31 |  | #113 | BOF v1 object format and the ABI recorded as design decisions; `SECT` flags decided |
| 32 |  | #114 | `bc81asmc`: `#include` / `#define` from `.h` files, `#link` |
| 33 |  | #115 | `bc81asmc --obj`: `.global`, `.extern`, `.sect`, every fix-up kind, a `.o` dump |
| 34 |  | #116 | `runtime.basm`: the runtime as an assembly source, one section per routine |
| 35 |  | #117 | `blink.py`, the reference linker |

**Exit:** an assembly-only program (`runtime.basm` + `hello.basm`) assembled with `--obj`,
linked by `blink.py`, runs on the emulator.

## Phase 2: the assembler on the BC64

| Step | Done | Issue | What |
|---|:-:|---|---|
| 36 |  | #118 | shared B modules: texted reader (RDR), preprocessor (PRE), object writer (BOFW) |
| 37 |  | #119 | `BASM.PRG`, starting with a size spike |

**Exit:** `runtime.basm` and sample modules assembled on the BC64 are byte-identical to
`bc81asmc --obj`; an assembly program goes texted → `basm` → `blink.py` → runs.

## Phase 3: B objects on the host, then the linker on the BC64

Steps 38–45 don't depend on phase 2 and can run in parallel with it.

| Step | Done | Issue | What |
|---|:-:|---|---|
| 38 |  | #120 | `bc`: raw-byte `asm` statement and `#link` |
| 39 |  | #121 | `bc --obj`: `F_name` symbols, externals from prototypes, a section per function |
| 40 |  | #122 | the 30 assembly routines with a B header move to `.basm` modules |
| 41 |  | #123 | `printf` as an assembly module (variadic ABI) |
| 42 |  | #124 | `stdmem` allocator without the `dsdi` side effect |
| 43 |  | #125 | bdio entry stub + B dispatcher, the rest of the `asm` in bdos |
| 44 |  | #126 | libraries split into `.h` + `.o`; every disc program and `BDOS.SYS` linked by `blink.py` |
| 45 |  | #127 | remove `asm "…"` from `bc` (owner decision first) |
| 46 |  | #128 | shell search path: active drive, then A |
| 47 |  | #129 | development disc and assembler disc |
| 48 |  | #105 | **`BLINK.PRG`**, the linker on the BC64 |

**Exit:** host-built `HELLO.O` + library objects linked on the BC64 give the same bytes as
`blink.py`.

## Phase 4: the compiler on the BC64

| Step | Done | Issue | What |
|---|:-:|---|---|
| 49 |  | #130 | `bc --tok`, the oracle for BCC |
| 50 |  | #106 | **`BCC.PRG`**, pass 1: lexer and preprocessor (spike first) |
| 51 |  | #131 | `bc --ir`, the oracle for BCC2 |
| 52 |  | #107 | **`BCC2.PRG`**, pass 2: parser |
| 53 |  | #108 | **`BCC3.PRG`**, pass 3: code generator |

**Exit:** `.TOK`, `.IR` and `.o` from the BC64 are byte-identical to the host's for
`helloworld`, `ls`, `cp`, `rm`, `cha`, `cat`, `texted` and the B parts of the libraries.

## Phase 5 and later

| Step | Done | Issue | What |
|---|:-:|---|---|
| 54 |  | #132 | `bdio_chain`; `bcc NAME` runs all passes and `blink` |
| 55 |  | #44 | batch files in the shell (optional) |
| 56 |  | – | self-hosting: the tools build their own sources on the BC64 (optional; no issue yet) |

## Decisions the owner still has to make

| Where | Decision | Needed before |
|---|---|---|
| #136 | `div`/`mod` by zero: keep the destination and set `O` (decided in #4, E10; the owner confirms it), and whether the B `/` and `%` check `O` | step 31 |
| #113 | `SECT` flags | step 33 |
| #41 | placement of a new file (proposed: largest gap; writing past it is `disc full`); defrag later | step 25 |
| #127 | drop `asm "…"` (recommended) or keep it host-only | step 45 |
| [07](07-self-hosted-compiler.md#risks-and-open-questions) | texted records as the official source format; keep precedence quirks; is self-hosting a goal | phase 4 |
