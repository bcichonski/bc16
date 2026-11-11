# bdos, utilities and apps: analysis

Reference: [../05-bdos.md](../05-bdos.md). Decisions: D1–D5, G2, G7 in
[../specs/memory/design-decisions.md](../specs/memory/design-decisions.md).

## Current state

- **bdos 1.1:**
  - a 128-byte boot loader;
  - an 18.5 KB shell plus bdio layer (in B) at `0x0f00`;
  - BFS: a flat catalog, contiguous files, buffered and sector I/O.
- **The system disc `os.bdd`** holds `LS`, `CP`, `RM`, `CAT`, `CHA`, `FORMAT`, `HELLOWRD`
  and `TEXTED`. It is built by `ftool mkdisc` from `src/disc.bddmanifest` (#37).
- **In progress:** TextEd v1.2 load and save (#1); the Theodore game (#2).
- **The disc is stale:** `BDOS.SYS` and `CAT.PRG` were built before the 2025-01-04 changes
  (#1 fixes this).

## Development direction (roadmap)

From the README and `bdos.md`:
- **1.1b:** catalog with file dates (the RTC on port `0x3` exists) and load addresses.
- **2.0:**
  - catalog extended with dates, load address and a manifest;
  - still no directories, still primitive allocation.
- **Relocatable executables and memory management.**
- **Script execution**, then **pipes between programs**.
- **New discs**, 80 tracks × 32 sectors (item 7).
- **Networking?** (item 10).

## Problems

| # | Problem | Evidence | Impact | Issue |
|---|---|---|---|---|
| 1 | Stale system disc | `BDOS.SYS`/`CAT.PRG` built 2024-11-03; the sources changed on 2025-01-04 | the disc doesn't match the source (#1) | #1 |
| 2 | **Disc geometry is hard-wired to 16 sectors per track** | the boot loader packs track and sector into one byte (`ci`: high nibble track, low nibble sector, range `0x20..0xbf`); `bdio_getfreesect` masks with `& 0x0f`; `FDD_SECTORS 0x10` | roadmap item 7 (32 sectors) needs a redesign of the boot loader and the bdio addressing, not just constants | #40 |
| 3 | Hand-maintained disc build | before #37, `fcat0800.sector` was a binary edited by hand and `makedisc` hard-coded the start tracks | adding or growing a program is error-prone; nothing checks the sizes | #37 |
| 4 | Allocation never reuses space | new data always goes after the last used sector; `rm` doesn't free anything | the disc fills up permanently; only a reformat recovers it | #41 |
| 5 | File size limited to 255 sectors (32 KB) | the length is one byte in the catalog entry | `bdos.md` claimed 64 KB until now; large texts and bigger apps don't fit | #39 |
| 6 | Colliding error codes | `BDIO_FOPEN_FDD_NOT_READY` is defined twice (`0xe1`, then `0xe5`; the last one wins); `0xe6` and `0xe7` each mean two things | wrong messages; `bdio_printexecres` can't tell the cases apart | #38 |
| 7 | Kernel size and memory | bdos uses `0x0d80–0x6000` (about 21 KB); 1.5 KB left before the file buffers; the boot loader always reads 160 sectors, and its rebuilt sector is already 128 of 128 bytes | little room for 1.1b/2.0 features without compiler improvements | #45 |
| 8 | Fixed resources | 1 write handle, 3 read handles; one program at a time at `0x6000` | `cp`-style tools work, but pipes and scripts need more | #44 |
| 9 | Debug leftovers | the `iowrite` printf (fixed in source, not on disc); commented-out printfs in `rm`/`cha` | noise; easy to reintroduce | #46 |
| 10 | Argument parsing duplicated in every program | each tool repeats `upstring`/`strnextword`/option parsing and `getdriveletter` | larger programs; inconsistent options | #43 |

## Proposals

### Next steps

1. **#1, then #2**: get a correct, current disc with texted and the game.
2. **Disc manifest instead of a hand-made catalog** (#37):
   - a text file (e.g. `src/disc.manifest`: name, source `.sectors`, attributes) read by
     a new `ftool mkdisc`;
   - it allocates tracks automatically, writes the boot sector, the catalog entries and the
     files, and fails if anything overflows;
   - this replaces `makedisc` and `fcat0800.sector`.
3. **Clean up the error codes** (#38) in `bdioh.b`: one value per meaning, grouped by operation,
   with `bdio_printexecres` updated and the table in `docs/05-bdos.md` regenerated.

### Improvements

4. **Catalog v2, designed once for 1.1b + 2.0 + item 7** (#39):
   - 2-byte start sector (a linear sector number instead of track/sector);
   - 2-byte length (64 KB files);
   - creation and modification date from the RTC;
   - load address.

   A 16-byte entry is too small for all of that: go to 32 bytes per entry (4 per sector).

   Version the format with the existing disc signature `BD 05 01 01`, and keep a read path
   for v1 discs so old images still boot or can be converted by a tool.
5. **Linear sector addressing in bdio** (#40):
   - `bdio_tracksector_add` and friends work on a 16-bit sector number;
   - only `bdio_iosec` converts it to a track/sector pair for the drive;
   - the boot loader gets a 16-bit counter.

   This unblocks the 80×32 geometry.
6. **Free-space reuse** (#41): a first-fit search over the gaps between catalog entries when
   creating a file, plus a `defrag` utility. Without it, item 7's bigger disc only delays
   the problem.
7. **Load addresses (1.1b) as the first step to relocation** (#42). Programs declare their load
   address (from `#code`) in the catalog, and `bdio_execute` uses it. Real relocation
   (a relocation table emitted by the compiler) only after that works.
8. **Shared program library** (#43), extending the existing `bdostools.b` or a new `bdosargs.b`: argument tokenising, `-x` options, `[d:]`
   prefixes, drive letters, usage printing. Use it in all tools; it also shrinks them once
   dead-code elimination exists.
9. **Scripts before pipes** (#44, scripts only). A `.BAT`-like script runner is a small shell feature (read a
   file line by line and execute it). Pipes need multiple handles and buffering between
   programs; do them after relocation.
10. **Kernel diet** (#45): measure bdos after the compiler's dead-code elimination (see
    [03-compiler.md](03-compiler.md)); then read only `BDOS.SYS`'s real length in the boot
    loader instead of a fixed 160 sectors.

Problem 9 (debug leftovers) is #46. The boot loader has no spare bytes (128 of 128), so
#40 and #45 must free or budget bytes before adding code to it.

## Modernisation verdict

**No modernisation of the OS concept**: a flat, contiguous file system and a tiny shell are
the intended design. **Modernise the disc build** (manifest-driven, checked) and **design
the next disc format properly**, because the current track/sector packing is the main
technical blocker of the roadmap (item 7) and of catalog v2 (1.1b/2.0).
