# bcOS: analysis

Reference: [../04-bcos.md](../04-bcos.md). Decisions: O1–O5, G1, G7 in
[../specs/memory/design-decisions.md](../specs/memory/design-decisions.md).

## Current state

- bcOS 1.2 (20241102): about 1,570 lines of assembly, a 3,435-byte image at `0x0000`. It
  holds the monitor (single-letter commands), terminal and tape routines, hex parsing,
  comparisons, the FDD boot hand-off, and the `os_metacall` system-call table (56 slots).
- It's stable and does its job; the most recent change was adopting the bc8183
  instructions (1.2).
- The comment numbering of the table was fixed and documented in this session.

## Development direction (roadmap)

- History: 1.1 took over routines from the B compiler runtime; 1.2 adopted the bc8183
  instructions. The README lists no further bcOS items.
- Implied by other items:
  - **display device** support (a "monitor": print routines would gain a second output);
  - **bigger discs** (item 7): the boot hand-off reads track 0 sector 0 only, which is
    unaffected;
  - possibly a **version query** so bdos and apps can check compatibility.
- Principle O1: the ROM stays minimal, and features go to bdos or libraries.

## Problems

| # | Problem | Evidence | Impact | Issue |
|---|---|---|---|---|
| 1 | **21 bytes of headroom** | the image ends at `0x0d6b`; bdio variables start at `0x0d80` (`bdioh.b`) | nearly any new routine forces bdos addresses and every program to move | #30, #31 |
| 2 | No build-time check of the fixed addresses | `os_metacall` (`0x0008`) and the table at `0x000c` are hard-coded in `boot.basm`, `bdosh.b` and `bc_stdlib.py` | a code change in front of them breaks every caller silently | #30 |
| 3 | Duplicated code with the compiler runtime | `printhex*`, `poke16`/`peek16`, `readstr`, `nextword`, `upchar`, `str_cpy`, `strncpy`, `gt16`/`gteq16`/`eq16`, `mfill` exist both in the ROM and in `bc_stdlib.py` | wasted RAM in every program; two implementations to keep in sync | #33, #34 |
| 4 | Odd register load in the dispatcher | `.mv dsci, :var_promptbuf` in the `s/l/r/e` command paths (sets `DS`+`CI`) | works only because `DS:DI` still points at the buffer; fragile | #32 |
| 5 | Tape-only monitor storage | `s`/`l` use the tape; disc access needs bdos | fine by design, but there's no way to load a disc sector from the monitor for recovery | |
| 6 | Cryptic errors | `error 03` without text | needs the docs at hand | |
| 7 | ROM isn't write-protected | the emulator loads it into RAM | a stray write can corrupt the OS until a restart | #36 |

## Proposals

### Next steps

1. **Contract asserts** (#30; needs `.assert` in the assembler, #8, see
   [02-assembler.md](02-assembler.md)):
   - `:os_metacall = 0x0008`
   - `:os_metatab = 0x000c`
   - `:os_bdiocall_slot = 0x007a` (a new label in front of slot `0x37`)
   - `:user_mem <= 0x0d80`

   This turns the headroom problem into a build error instead of a crash.
2. **Win back bytes without moving the memory map** (#31):
   - replace `.mv csci, :x` + `xor a` + `jmp z, csci` with `jrx z, :x` (4 bytes) or `jmr`
     (2 bytes) where in range; there are 14 such jumps;
   - deduplicate the error-message strings.

   Measure with the listing output (#9). The stub at `0x0000` must stay 8 bytes so
   `os_metacall` stays at `0x0008`, and `os_metatab`, slot `0x37` and `os_vartab` (`0x007c`)
   must not move. Routine addresses after the table may move, because callers only use
   table indices (no source hard-codes another ROM address).
3. **Fix `.mv dsci`** → `.mv dsdi` (#32), and check that the binary changes only there.

### Improvements

4. **Where the shared routines live** (O1). The options were:
   - (a) the compiler runtime calls the ROM through `os_metacall` (smaller programs, slower
     calls), or
   - (b) the ROM drops routines only the monitor needs.

   **Decided: (a)** (#33). The hot paths (`poke16`/`peek16`, comparisons) are settled
   separately by a spike (#34): ROM call, private copy or inline sequence.
5. **Version query call** (#35) in a free slot (`0x34`; `0x34`–`0x36` are free): it returns
   the bcOS version in `csci`.
   bdos can check it at boot and print a clear message instead of failing obscurely.
6. **Monitor command `b`** to rerun `os_boot` (slot `0x2b` exists, but no command does
   this). Useful after inserting a disc.
7. **Display device support**, when the emulator gets one: route `print_*` through one
   output routine and choose printer vs screen with a variable. Do it after the space
   problem is solved.
8. **Optional ROM write protection** in the emulator (#36; a memory region flag), off by
   default, to catch wild writes during development. It must leave slot `0x37` and the
   bcOS variables writable, since they are written at run time.

## Modernisation verdict

**No modernisation.** bcOS is meant to be period-style hand-written assembly. Improve it
through the assembler (asserts, listings) and through careful byte recovery. The strategic
question of item 4 (who owns the shared routines) is now decided: (a), the ROM (#33, with
the hot paths in #34). Recover bytes (#31) before adding any new ROM feature such as the
version call (#35), because the 21-byte limit leaves no room otherwise.
