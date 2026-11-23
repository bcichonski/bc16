# Spike #34: hot-path runtime routines (ROM call, private copy or inline)

Owner-facing notes. Size comes first, speed only breaks ties (E6: the emulator is intentionally slow). No production change was made (see the last section).

## 1. Question

For `poke16`, `peek16`, `gt16`, `gteq16` and `eq16`, which delivery option is best?

| option | what it is |
| :--- | :--- |
| 1 ROM call | a stub in the runtime loads the `os_metatab` index and calls `os_metacall` (`0x0008`) |
| 2 private copy | the routine body sits in `bc_stdlib.py`, every use is `cal :routine` |
| 3 inline | the body (without `ret`) is emitted at every use |

Calling a ROM body by its direct address is excluded: only `os_metacall`, `os_metatab` and `os_vartab` are stable (`docs/analysis/04-bcos.md`).

## 2. Today's state (the issue text is only half right)

| routine | today | how |
| :--- | :--- | :--- |
| `poke16`, `peek16` | **option 2, private copy** | 8-byte body in `bc_stdlib.py` |
| `gt16`, `gteq16`, `eq16` | **option 1, ROM call, already** | 8-byte stub loading index `0x21`/`0x22`/`0x23` |

So "keep today" means two different things: for the pair it keeps a private copy (against the wording of #33 decision (a)), for the three comparisons it keeps the ROM call (what #33 asks for).

## 3. Method

Nothing is built in the repo tree. Every variant is built in a temp copy of the sources; byte lengths come from the real assembler, instruction counts from the real emulator (in-process hook).

| step | command (repo root) | runtime | writes |
| :--- | :--- | ---: | :--- |
| static census and byte model | `python3 docs/specs/plans/34-hot-path/census.py` | about 10 s | `34-hot-path/census.md` |
| built prototypes, sizes, smoke + e2e per variant | `python3 docs/specs/plans/34-hot-path/prototypes.py` | 1442 s (about 24 min) | `34-hot-path/prototypes.md` |
| instructions per call, dynamic counts | `python3 docs/specs/plans/34-hot-path/dyncount.py` | about 24 s | `34-hot-path/dyncount.md` |

census.py and dyncount.py were re-run for this write-up and reproduce the tables below; prototypes.py was not re-run (24 min), its numbers are quoted from the committed `prototypes.md`.

Built variants (all on the unchanged bcOS ROM): `pp_rom` (peek16/poke16 as ROM stubs), `pp_inline` (peek16/poke16 inline), `cmp_copy` (the three comparisons as private copies), `cmp_inline` (the three comparisons inline). Option 2 for the pair and option 1 for the three are `today`.

## 4. How often the routines are used

### 4.1 Static (call sites in the generated `.basm`; codegen / runtime-internal / library+app)

| routine | bdos | texted | ls | what the uses are |
| :--- | :--- | :--- | :--- | :--- |
| poke16 | 2 / 5 / 9 = 16 | 2 / 5 / 18 = 25 | 2 / 5 / 5 = 12 | prologue (2), `stackvar*`/`stackhead*`/`mseek` (5), `std.b` and app `asm` |
| peek16 | 1 / 8 / 8 = 17 | 43 / 8 / 8 = 59 | 0 / 8 / 7 = 15 | unary `#` (codegen), `stackvar*`/`stackoffs*` (4) and `mseek` (4), `asm` |
| gt16 | 2 / 0 / 0 = 2 | 13 / 0 / 0 = 13 | 1 / 0 / 0 = 1 | codegen only |
| gteq16 | 18 / 1 / 0 = 19 | 13 / 1 / 0 = 14 | 7 / 1 / 0 = 8 | codegen, plus `mseek` (1) |
| eq16 | 85 / 0 / 0 = 85 | 31 / 0 / 0 = 31 | 28 / 0 / 0 = 28 | codegen only |

Of the runtime-internal uses, 4 per program of poke16 and 4 of peek16 come from the `stackvar*`/`stackoffs*`/`stackhead*` helpers (the ones #17 would inline). Every program carries the runtime, so the runtime-internal uses are constant (5 poke16, 8 peek16, 1 gteq16). All 18 programs are in `census.md` section 4.

### 4.2 Dynamic (calls from loaded programs in a scripted session)

| routine | boot (68,263 instr) | `ls` session (444,454) | `texted` session (979,048) |
| :--- | ---: | ---: | ---: |
| poke16 | 626 | 3,970 | 8,698 |
| peek16 | 2,234 | 14,347 | 31,962 |
| gt16 | 7 | 36 | 136 |
| gteq16 | 40 | 278 | 620 |
| eq16 | 30 | 628 | 1,422 |

peek16 and poke16 dominate by an order of magnitude (about 95% of the calls in the `ls` session: 18,317 of 19,259; computed from the table).

## 5. Bytes

### 5.1 Model per use (assembler bytes)

| routine | runtime bytes opt 1 | opt 2 | per use opt 1 and 2 (`cal`) | per use opt 3 (model) |
| :--- | ---: | ---: | ---: | ---: |
| poke16 | 8 | 8 (today) | 3 | 7 |
| peek16 | 8 | 8 (today) | 3 | 7 |
| gt16 | 8 (today) | 22 | 3 | 21 |
| gteq16 | 8 (today) | 22 | 3 | 19 |
| eq16 | 8 (today) | 18 | 3 | 17 |

Inline beats a call only when `4 x uses < 8` (pair) i.e. fewer than 2 uses; for the comparisons only at 0 uses (it just drops the stub). Every program has 3 or more uses of each pair routine.

### 5.2 Real builds (headline programs, bytes; delta vs today)

| variant | bdos | texted | ls | bdos+texted+ls | delta | % of 39,805 | all 18 programs | delta |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `today` | 17359 | 14150 | 8296 | 39805 | 0 | 0 | 103100 | 0 |
| `pp_rom` (pair as option 1) | 17359 | 14150 | 8296 | 39805 | 0 | 0 | 103100 | 0 |
| `pp_inline` (pair as option 3) | 17475 | 14470 | 8388 | 40333 | +528 | +1.33% | 104908 | +1808 |
| `cmp_copy` (three as option 2) | 17397 | 14188 | 8334 | 39919 | +114 | +0.29% | 103784 | +684 |
| `cmp_inline` (three as option 3) | 19009 | 15104 | 8863 | 42976 | +3171 | +7.97% | 110460 | +7360 |

`pp_rom` is byte for byte the same as today: the ROM stub and the private body assemble to the same 8 bytes, and each use is 3 bytes either way. The percentages are computed from the table.

### 5.3 Per routine (model, headline sum over bdos+texted+ls, delta vs today)

| routine | opt 1 | opt 2 | opt 3 |
| :--- | ---: | ---: | ---: |
| poke16 | 0 | 0 (today) | +188 |
| peek16 | 0 | 0 (today) | +340 |
| gt16 | 0 (today) | +42 | +264 |
| gteq16 | 0 (today) | +42 | +632 |
| eq16 | 0 (today) | +30 | +1992 |

(Computed from the per-program totals in `census.md` section 3; each is the sum of the three programs' deltas.)

### 5.4 Model versus build

| variant | model (headline) | build (headline) | difference |
| :--- | ---: | ---: | :--- |
| `pp_rom` | 0 | 0 | none |
| `pp_inline` | +528 (188 + 340) | +528 | none; also exact per program (+116, +320, +92) |
| `cmp_copy` | +114 (42 + 42 + 30) | +114 | none; +38 in every program |
| `cmp_inline` | +2888 (bdos 1506, texted 868, ls 514) | +3171 | build is +283 larger (bdos +144, texted +86, ls +53) |

Why `cmp_inline` differs: the model uses hand-compacted bodies (21 / 19 / 17 bytes per use for gt16 / gteq16 / eq16). The build inlines the real ROM bodies, which keep one exit jump per original `ret`. Solving the four build deltas (bdos, texted, ls, debug) for the three per-use sizes gives 22 / 22 / 18 bytes (computed here from the numbers in `prototypes.md`; it also reproduces helloworld, +10). That is 1 / 3 / 1 bytes more per use than the model; the cause is a layout difference, not a count difference (the inlined site counts in `prototypes.md` equal the census totals). The conclusion does not depend on it: inline loses by a wide margin in either reading.

After #17 the model shows the same ordering (section 7); there is no build of that view because #17 is not implemented.

## 6. Instructions per call (emulator, measured)

`*` = today's option.

| routine | 1 ROM call | 2 private copy | 3 inline |
| :--- | :--- | :--- | :--- |
| poke16 | 43 | 5* | 3 |
| peek16 | 43 | 5* | 3 |
| gt16 | 44-49* | 6-11 | 5-10 |
| gteq16 | 44-49* | 6-11 | 4-10 |
| eq16 | 44-47* | 6-9 | 4-8 |

The ROM path costs 38 more instructions than a private copy (the stub, `os_metacall`, `os_call` saving 5 registers and looking up `os_metatab`, `var_oscall`).

Session-level delta vs today, instructions (negative = faster), with the share of the session total:

| session | pair as ROM call (`pp_rom`) | three as copy (`cmp_copy`) | pair inline + three inline (all inline) |
| :--- | ---: | ---: | ---: |
| boot (68,263) | +108,680 (+159%) | -2,926 (-4.3%) | -8,766 (-12.8%) |
| `ls` (444,454) | +696,046 (+157%) | -35,796 (-8.1%) | -73,865 (-16.6%) |
| `texted` (979,048) | +1,545,080 (+158%) | -82,764 (-8.5%) | -167,555 (-17.1%) |

The first column is only the pair (the three comparisons are already ROM calls, delta 0); the second only the three comparisons (the pair stays as today). The third column is all five routines inline at once. Percentages computed from the table. In the e2e suite, `pp_rom` took 1344 s against 655 s for today (about 2x).

## 7. Interaction with #17

#17 (cheaper variable access) is **open and not implemented**; the "after #17" view is a model that removes the `stackvar*`/`stackoffs*`/`stackhead*` runtime-internal uses (4 of poke16's and 4 of peek16's per program, each at 3 bytes) and keeps everything else. Whatever #17 puts in their place is not modelled.

| view | headline delta of the pair at opt 1 / opt 2 | at opt 3 | comparisons |
| :--- | ---: | ---: | :--- |
| today | 0 / 0 | poke16 +188, peek16 +340 | unchanged (no stackvar uses) |
| after #17 (model) | -36 / -36 for each routine (-12 per program) | poke16 +104, peek16 +256 | unchanged |

What changes: the pair loses most of its internal uses, so the whole pair gets smaller under every option, and the runtime-internal share of the dynamic calls drops. What does not change: the remaining uses per program are still 3 or more for poke16 (2 prologue + 1 `mseek` + app code) and 4 or more for peek16 (4 `mseek`, plus codegen `#` and library uses), so inline still costs more than a call (`4 x uses > 8`; smallest case `debug`: poke16 inline is +4 bytes). The recommendation for every routine is **the same** after #17. If #17 ever removes all remaining uses of one routine, its body could go, but codegen `#`, the prologue and the B `asm` uses keep both alive.

## 8. Recommendation per routine

Rule: pick the option with the smallest bdos+texted+`ls` total. Two options **tie** when they are within **0.05% of the headline total (39,805 bytes), i.e. about 20 bytes**; among tied options pick fewer instructions per call.

| routine | recommendation | reason |
| :--- | :--- | :--- |
| `poke16` | **option 2, private copy (keep today)** | options 1 and 2 are exactly equal in size (0 bytes), so speed decides: 5 against 43 instructions per call (the pair costs +157-159% session instructions as ROM call). Inline costs +188 bytes. |
| `peek16` | **option 2, private copy (keep today)** | same as poke16; inline costs +340 bytes. |
| `gt16` | **option 1, ROM call (keep today)** | smallest: private copy +42, inline +264 bytes. The 38 instructions saved per call by a copy do not outweigh size. |
| `gteq16` | **option 1, ROM call (keep today)** | private copy +42, inline +632 bytes. |
| `eq16` | **option 1, ROM call (keep today)** | private copy +30, inline +1992 bytes. |

Same result after #17 (section 7). The three comparisons are not recommended as inline in any case: it is the largest option for each of them in the headline programs.

Margin sensitivity (the owner's call): the plan suggested up to 1% (about 398 bytes). At that margin the three comparisons as private copies (+114 bytes, 0.29%) would count as a tie with the ROM call and win on speed (-4.3% / -8.1% / -8.5% of the boot / `ls` / `texted` session instructions). At 0.05% they do not. The pair as inline (+528, 1.33%) loses at both. Side note derived from the model: the comparison stubs (8 bytes each) are emitted in every program even when unused (debug, helloworld, the `code/*` programs); emitting a stub only when used would save up to 24 bytes there. That is outside the three options and was not built.

## 9. Register and flag side effects

| option | what the caller sees |
| :--- | :--- |
| 1 ROM call | the stub loads `a` = index, `psh a / pop f`; `os_call` saves and restores a, csci, dsdi, then calls the body with `a` = index. After the call **`a` = index (0x09/0x0a for the pair) and `f` is overwritten** (index, then the body's flags). The documented contract already says `a - rubbish`; `stackoffscalc`/`stackoffsclc8` push `a` before the call. `pp_rom` passed boot, `ls`, `hellowrd` and the whole e2e suite (Ran 123 tests, OK, expected failures=1), so no B `asm` caller relied on `a` or `f`. |
| 2 private copy | `a` and flags exactly as the body leaves them (the same as today for the pair; for the comparisons: result in `a`, flags from the body, `f` is no longer the index on entry). |
| 3 inline | same `a` and flags as the body, because only `ret` is dropped. Comparisons need unique labels per site and a jump to the end after each former `ret` (`jmr nz` after `mov a, 0x01`, `jmr z` after `xor a`; relative jumps keep the flags). `mseek`'s `clr :gteq16` / `jmr nz` relies on the result flags, which inline keeps. |

Smoke (boot, `ls`, `hellowrd`) passed for all four variants. e2e: `today` and `pp_rom` pass (Ran 123 tests, OK, expected failures=1; the one expected failure is a pinned known bug, the same in today, not a pass). `pp_inline`, `cmp_copy` and `cmp_inline` fail exactly one test, `tests.test_e2e_toolchain::test_compile_assemble_put_on_disc_and_run`, whose golden pins bdio's load progress dots (one per 8 sectors, so a larger program prints one extra dot): a size artefact, not a malfunction.

## 10. For #33 (what the owner has to decide)

1. **Peek16/poke16.** Decision (a) says "ROM call, no private copies". The numbers say the ROM call for this pair is exactly size-neutral (0 bytes) but roughly 2.6 times the session instructions (+157-159%) and a 2x slower e2e suite. Decide: add an explicit exception "peek16/poke16 stay private copies" (recommended), or follow (a) and accept the slowdown for a size gain of zero.
2. **gt16/gteq16/eq16.** Already ROM calls; recommended to keep. Decide whether the 0.05% tie margin is right; at the plan's 1% they would become private copies for speed (+114 bytes headline).
3. **#17.** The recommendation does not change whether or not #17 lands; no rework of this decision is needed if it does.
4. Optional follow-up (not measured): emit the comparison stubs only when used.

## 11. No production change

This spike changes only `docs/specs/plans/` (this file and the `34-hot-path/` scripts and tables). `src/`, `scripts/`, `.github/` and `src/bc/code_size.csv` are untouched; all prototypes were built in temp copies. No contradiction was found in `census.md`, `prototypes.md` or `dyncount.md`, so none was edited by hand (census.md and dyncount.md were regenerated by their scripts with identical numbers).
