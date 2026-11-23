# bdos: the disk operating system

bdos is the BC64's disk operating system. It boots from floppy drive A and has three parts:
- a 128-byte **boot loader**;
- **bdio**, the resident disk and file I/O layer;
- a small command **shell** that loads and runs `.PRG` programs. Every system command
  (`ls`, `cp`, …) is such a program.

Everything except the boot loader is written in B (see [03-compiler.md](03-compiler.md)).
The current version is **bdos 1.1** (buffered reads and writes).

Sources are in `src/bdos/`:

| File | Contents |
|---|---|
| `boot.basm` | boot loader (assembly, loaded at `0x0e00`) |
| `bdos.b` | the shell (`main`) plus start-up |
| `bdio.b` | the disk/file I/O layer and the `bdio_call` dispatcher |
| `bdioh.b` | constants, memory addresses, error codes, call numbers |
| `bdosh.b` | wrappers that user programs include to call bdio |
| `bdostools.b` | `bdio_fnormalize` (converts `name.ext` to the catalog form) |
| `bdosargs.b` | argument helpers of the utilities (`getdrive`, `getswitch`, `argfile`, `printusage`, …); opt-in, see "Argument library" |
| `random.b` | `random(max)`: opt-in wrapper for `BDIO_RANDOM` (`0x1a`); include it after `bdosh.b` |
| `ls.b`, `cp.b`, `rm.b`, `cat.b`, `cha.b`, `format.b` | system utilities |
| `helloworld.b` | app on both discs: `HELLOWRD.PRG` is the smoke program on `os.bdd`, and the same build is on `utils.bdd` |
| `texted.b`, `theodore.b`, `calc.b` | apps on the utilities disc (`utils.bdd`, run `b:` first) |
| `fddtest.b`, `debug.b` | older or test programs, not on the disc |
| `bdos.md` | short design notes: disk format, bdio call list, memory map |

Building a program creates generated files next to it: `*.genb` (preprocessed), `*.basm`,
`*.btap` and `*.sector(s)` (raw sectors). They are ignored by git and must be rebuilt after a fresh
clone (the pipeline command is below). Only `boot.basm` (hand-written) and `testb.sectors` (sample
data) are committed. `os.bdd`, `utils.bdd` and the ROM are build outputs too and are not committed.

## Boot

1. bcOS finds the drive, loads **track 0 sector 0** to `0x0e00` and jumps there (see
   [04-bcos.md](04-bcos.md)).
2. The boot loader prints `lding`. It reads sectors `0x20`…`0xbf` (track 2 sector 0 to
   track 11 sector 15, 160 sectors = 20 KB) sector by sector through DMA into `0x0f00…`,
   then jumps to `0x0f00`. On error it prints `err.` and halts. The boot sector ends with
   the disc signature `BD 05 01 01`.
3. bdos start-up:
   1. writes the address of `bdio_call` into bcOS `os_metatab[0x37]` (`0x007a`), so programs
      can call bdio through `os_metacall`;
   2. prints `bDOS 1.1 shell`, `<free> bytes free`, `reading disc...`;
   3. selects drive A and reads its catalog.

## Memory map (BC64, bdos 1.1)

| Address | Contents |
|---|---|
| `0x0000–0x0d6b` | bcOS 1.2 |
| `0x0d80–0x0dd1` | bdio variables: last error, active drive, catalog scan state, free entry/track/sector (`0x0d84`–`0x0d86`), disc-full flag (`0x0d87`), gap end (`0x0d8a`, word), free sectors for `ls` (`0x0d8c`, word), `PMEMBUF_LEN` (`0x0d92`), file descriptor tables (write `0x0d94`, read `0x0da4`) |
| `0x0dd2–0x0dfe` | shell command-line buffer (45 bytes). **Programs read their arguments from here** |
| `0x0e00–0x0e7f` | temporary sector buffer (the boot sector is loaded here at boot) |
| `0x0e80–0x0eff` | catalog scan sector buffer |
| `0x0f00–0x5b4c` | `BDOS.SYS`: shell + bdio code (`0x4c4d` bytes), followed by its B variable stack |
| `0x5d00–0x5eff` | per-handle 128-byte buffers for buffered I/O (write handle, then 3 read handles) |
| `0x5f00–0x5f7f` | used-sector map built by `fcreate`, 128 bytes, one bit per sector (see Allocation) |
| `0x5fd0` | bdos heap; `0x5fe0` is a temporary file-name buffer |
| `0x6000` | **user memory**: `.PRG` programs are loaded and run here (`#code 0x6000`) |
| `… 0xfffe` | CPU stack, growing downwards from `0xfffe` |
| `0xffff` | `KIL` (reserved, written by the emulator at start-up): running into it halts the CPU |

Free memory, as reported by `bdio_freemem()`, is `SS:SI − 0x6000`, a little under 40 KB.

## Disk format (BFS)

A disk has 64 tracks × 16 sectors × 128 bytes (128 KB). The file system is flat, with no
directories. Each file is one **contiguous** run of sectors.

### Layout of the system disc (`src/os.bdd`, built by `./makedisc`)

The layout of the system disc and its requirements are stated in `src/disc.bddmanifest`, and
`ftool mkdisc` enforces them. `ls -a` lists the actual positions and lengths. The system disc holds the
system, the system utilities (`LS`, `CP`, `FORMAT`, `RM`, `CHA`, `CAT`) and the sample programs `HELLOWRD.PRG`
and `TEST.B`. `HELLOWRD.PRG` is also on the utilities disc, from the same build. The applications `TEXTED.PRG`,
`CALC.PRG` and `THEODORE.PRG` are on the utilities disc (below), not on this one.

It has eleven entries:

| File | Source | Attributes | Start (track/sector) | Length (sectors) |
|---|---|---|---|---|
| `BOOTSECT.BIN` | `bdos/boot.sector` | SR | 0/0 | 1 |
| `DISC.CAT` | (written by the tool) | SR | 0/1 | 31 |
| `BDOS.SYS` | `bdos/bdos.sector` | SR | 2/0 | 160 |
| `LS.PRG` | `bdos/ls.sectors` | SRX | 12/0 | 58 |
| `HELLOWRD.PRG` | `bdos/helloworld.sectors` | RX | 15/10 | 14 |
| `CP.PRG` | `bdos/cp.sectors` | SRX | 16/8 | 57 |
| `FORMAT.PRG` | `bdos/format.sectors` | SRX | 20/1 | 82 |
| `RM.PRG` | `bdos/rm.sectors` | SRX | 25/3 | 63 |
| `CHA.PRG` | `bdos/cha.sectors` | SRX | 29/2 | 56 |
| `CAT.PRG` | `bdos/cat.sectors` | SRX | 32/10 | 62 |
| `TEST.B` | `bdos/testb.sectors` | RW | 36/8 | 2 |

The positions and lengths are those of a build at the time of writing; `ls -a` shows the actual values.

The catalog itself is a file: `DISC.CAT`, from track 0 sector 1 to the end of track 1.

### Layout of the utilities disc (`src/utils.bdd`, built by `./makedisc`)

The utilities disc holds the applications and games that are not on the system disc. As for `os.bdd`, the
layout and its requirements are stated in `src/utils.bddmanifest`, which is the authority, and `ftool mkdisc`
enforces them. Its first three entries are the same boot, catalog and system files as on `os.bdd`, so the boot
loader and the shell work from either disc. It has seven entries:

| File | Source | Attributes | Start (track/sector) | Length (sectors) |
|---|---|---|---|---|
| `BOOTSECT.BIN` | `bdos/boot.sector` | SR | 0/0 | 1 |
| `DISC.CAT` | (written by the tool) | SR | 0/1 | 31 |
| `BDOS.SYS` | `bdos/bdos.sector` | SR | 2/0 | 160 |
| `TEXTED.PRG` | `bdos/texted.sectors` | RX | 12/0 | 112 |
| `CALC.PRG` | `bdos/calc.sectors` | RX | 19/0 | 50 |
| `HELLOWRD.PRG` | `bdos/helloworld.sectors` | RX | 22/2 | 14 |
| `THEODORE.PRG` | `bdos/theodore.sectors` | RX | 23/0 | 38 |

The positions and lengths are those of a build at the time of writing; `ls -a` shows the actual values. The
application and game entries have no `S` attribute. Only `TEXTED.PRG` is pinned, with `at=12/0`, the first sector
after the BDOS slot; the others follow it back to back. `HELLOWRD.PRG` is the same build as on `os.bdd`.

A disc made from `utils.bddmanifest` can also boot alone in drive A. It then shows the bdos shell with `A>` and
its built-in commands (`help`, `a:`, `b:`, `bcos`, `exit`), but none of the system utilities: `ls` gives
`error: E0 file not found`. The applications and games on it (`texted`, `calc`, `hellowrd`, `theodore`) run from it.

#### Default session: `--disk-a os.bdd --disk-b utils.bdd`

The default session has the system disc in A and the utilities disc in B. In headless mode these are the
`--disk-a` and `--disk-b` options; on the console, answer `os.bdd` and `utils.bdd` at the disk prompts.

1. The system boots from A and shows the `A>` prompt.
2. `b:` makes B the active drive, and the prompt becomes `B>`.
3. `texted`, `calc`, `theodore` and `hellowrd` run from B, and each returns to the `B>` prompt. TextEd's `s` and
   `l` save and load files on B, so a file saved in one session is loaded from B in the next one.
4. After `b:`, `ls` and the other utilities are **not found** (`error: E0 file not found`). The shell looks a
   `.PRG` up only on the active drive, and the system utilities are on A. This is by design: there is no shell
   change for running programs across drives. Go back with `a:`.
5. From A, file names take a drive prefix, so the utilities work on B: `ls b:` lists drive B, and
   `cat -c b:note.txt` prints a file on B.

### Catalog entry (16 bytes, 8 per sector, up to 248 entries)

| Offset | Size | Field |
|---|---|---|
| `0x00` | 1 | entry number |
| `0x01` | 1 | start track |
| `0x02` | 1 | start sector |
| `0x03` | 1 | length in sectors (so a file is at most 255 × 128 B ≈ 32 KB) |
| `0x04` | 1 | attributes |
| `0x05` | 8 | name, space-padded, upper case |
| `0x0d` | 3 | extension (stored without the dot) |

### Attributes

| Bit | Attribute |
|---|---|
| `0x01` | R: readable |
| `0x02` | W: writable |
| `0x04` | X: executable (required to run a file from the shell) |
| `0x80` | S: system (`rm` refuses without `-f`) |

### Allocation

Sectors are numbered linearly (track × 16 + sector, 0..1023). The reserved part is never allocated;
the rest is the allocatable area:

| Sectors | Use | Constants (`bdioh.b`) |
|---|---|---|
| `0/0` | boot sector | `BDIO_DISC_BOOTSECT` (`0x00`) |
| `0/1`–`1/15` | catalog (31 sectors, 248 entries) | `BDIO_DISC_FCATFIRSTSECT`–`BDIO_DISC_FCATLASTSECT` (`0x01`–`0x1f`) |
| `2/0`–`11/15` | BDOS.SYS range that `boot.basm` loads | `BDIO_DISC_BDOSFIRSTSECT`–`BDIO_DISC_BDOSLASTSECT` (`0x20`–`0xbf`) |
| `12/0`–`63/15` | allocatable: 832 sectors | `BDIO_DISC_ALLOCFIRSTSECT` (`0xc0`) up to the disc end `BDIO_DISC_SECTORS` (`0x0400`, exclusive) |

The reserved sectors count as used whatever the catalog says: if `BOOTSECT.BIN`, `DISC.CAT` or `BDOS.SYS` was
removed with `rm -f`, or `BDOS.SYS` is shorter than its slot, those sectors are still never allocated.

When the catalog is read (`bdio_fcat_read`, run on every drive change), bdio finds:

- **First free entry:** the first catalog entry with length 0. The scan stops there. `rm` keeps the catalog
  compact by moving the last entry into the hole, so the first empty entry is the end.
- **Free sectors:** the number of free sectors in the allocatable area, kept as a word
  (`BDIO_VAR_FCAT_TOTALFREE`, `0x0d8c`). `ls` prints this figure.
- **Append position:** the maximum of start + length over all used entries, in linear sectors, as bdio keeps it
  as track/sector bytes. A write handle opened without `fcreate` (a program appending to an existing file)
  may write up to the disc end.

**New file (`fcreate`):** bdio builds the used-sector map at `0x5f00` (`BDIO_USEDMAP_ADDR`, 128 bytes, one bit
per sector) from a fresh scan of the catalog, so a file removed by another program is seen. The reserved
sectors are marked used; every catalog entry with a length marks its extent, clipped to the disc. The scan
stops at the first empty entry, as before. The new file goes into the **largest free gap**: the longest run
of free sectors in the allocatable area. The tail of the disc counts as a gap, and on a tie the gap with the
lowest start wins. The entry starts at the gap start with length 1, and the gap end becomes the limit of the
write handle. If no sector is free, `fcreate` returns `disc full` (`0xf3`) and writes no catalog entry.

**Growing a file (write and `fclose`):** the write handle writes the sectors of its file in order and never at
or past the gap end. When a write needs such a sector, it writes nothing more and the handle is marked disc
full. `fclose` saves the catalog entry with the sectors that were actually written, and returns `disc full`
(`0xf3`) instead of the handle. The file keeps the sectors that fit: it is never moved, no other file is
touched, and the user can `rm` it to free them.

**`ls`:** the free figure is the total number of free sectors in the allocatable area (832 minus the used
sectors there), so gaps count too. On a disc without gaps it equals 1024 minus the end of the last used
sector, as before #41.

Not part of #41: `DEFRAG` (moving files to close the gaps) is a follow-up. Creating a file while the write
handle is open is not supported; no caller does it, and it is not guarded.

**Discs made before #37.** `os.bdd` discs copied before #37 number only catalog entries 0–15, and entries 16–247 hold 0. bdio takes the first empty entry's number byte as the slot for a new file, so on such a disc the 17th file gets entry number 0 and overwrites the entry of `BOOTSECT.BIN`. The disc still boots, but its catalog is corrupted. Re-make the disc (`format` from a new system disc, or a copy of the new `os.bdd`), or keep it at 16 files or fewer. Discs made by `format` and the `src/os.bdd` built now number all 248 entries and are not affected.

## bdio: the system call API

User programs call bdio through the bcOS meta-call: `F = 0x37`, `A` = function,
`CSCI` = param1, `DSDI` = param2, then `cal :os_metacall`. The result comes back in `CSCI`.
In B, `#include bdosh.b` and use the wrappers:

| No. | Wrapper (bdosh.b) | Parameters | Returns |
|---|---|---|---|
| `0x00` | `bdio_readsect(track, sector, Pbuf)` | 128 bytes from disk to `Pbuf` | FDD status (`0` = ok) |
| `0x01` | `bdio_writesect(track, sector, Pbuf)` | 128 bytes from `Pbuf` to disk | FDD status |
| `0x02` | `bdio_setdrive(drive, silent)` | `0` = A, `1` = B; if not silent, re-reads the catalog | status |
| `0x03` | `bdio_getdrive()` | | active drive |
| `0x10` | `bdio_fbinopenr(Pname, mode)` | open for reading (needs R). Mode `0` = sector, `1` = buffered | handle, or error ≥ `0xe0` |
| `0x11` | `bdio_fbinopenw(Pname, mode)` | open for appending (needs W) | handle or error |
| `0x12` | `bdio_fbinread(h, Pbuf, sectors)` | read whole sectors | sectors read |
| `0x13` | `bdio_fbinwrite(h, Pbuf, sectors)` | write whole sectors | sectors written |
| `0x14` | `bdio_fcreate(Pname, attribs)` | new catalog entry | `0` or error |
| `0x15` | `bdio_fclose(h)` | flushes and updates the catalog entry | status |
| `0x16` | `bdio_fdelete(Pname)` | remove the catalog entry | status |
| `0x17` | `bdio_fsetattr(Pname, attribs)` | change attributes | status |
| `0x18` | `bdio_fbinbufread(h, Pbuf, bytes)` | buffered byte-count read (the length goes through `0x0d92`) | bytes copied, `1..length` (`0` = EOF, `length` 0, or not buffered) |
| `0x19` | `bdio_fbinbufwrite(h, Pbuf, bytes)` | buffered byte-count write | bytes accepted (`length`; `0` = not buffered) |
| `0x1a` | `random(max)` (`random.b`, needs `bdosh.b` first; see below) | hardware random number: reads port `0x05` twice (first byte high) | word in `0..max-1` (`max` = 0: the whole 16-bit word); never fails |

- **`0x1a` random:** `BDIO_RANDOM` reads the emulator RNG port `0x05` twice and joins the bytes into a
  16-bit word. The word modulo `max` is returned (slight modulo bias), or the whole word when
  `max` = 0. It does not touch `BDIO_VAR_LASTERROR` or the disc. The wrapper `random(max)` lives in
  `random.b`, not `bdosh.b`, so programs that do not include it do not grow. `random.b` includes
  nothing itself, so put `#include bdosh.b` before it.
- **File names:** `Pname` is the 11-character catalog form `NAME    EXT` (space-padded, no
  dot). `bdio_fnormalize` (bdostools.b) converts `name.ext` to that form.
- **Handles:** there is 1 write descriptor (handle `0x10|n`) and 3 read descriptors
  (`0x20|n`). Each descriptor is 10 bytes: number, catalog entry, current track/sector,
  current/total sequence, catalog track/sector, buffer counter, access mode (`0x0d`
  direct / `0x0b` buffered).
- **Shell-only functions:** `bdio_ffindfile`, `bdio_getfreesect`, `bdio_execute` and
  `bdio_freemem` are used by the shell and are not reachable through `bdio_call`.

### Buffered I/O

Buffered handles (`0x18` / `0x19`, open mode `1`) work on byte counts, not whole sectors.

- **Read (`0x18`)**: returns the bytes copied, `1..length`. It returns fewer than `length` only
  when the end of the file is reached during the call. It returns `0` at the end of the file, for
  `length = 0`, or for a handle that is not buffered. Read chunks may be `1..128` bytes (any `word`
  value works).
- **Write (`0x19`)**: returns the bytes accepted, which is `length` on success, or `0` for a handle
  that is not buffered. Write chunks may be any length.
- **Caller buffer**: must hold `length` bytes.
- **Flush**: data reaches the disc as each 128-byte sector fills (flush-on-full). The rest is written
  by `bdio_fclose` (flush-on-close), and the final sector is zero-padded.
- **File length** is whole sectors. A buffered reader gets the zero padding bytes after the last
  written byte, before the `0` at the end of the file.
- **Buffer counter** (one byte per handle): on a read handle, the bytes of the current buffer
  already consumed (`128` = used up; a freshly opened read handle starts at `128`). On a write
  handle, the bytes pending (`0..127` between calls).

### Result and error codes (bdioh.b)

A result byte below `0xe0` is a file handle. `0xe0` and above is an error: callers test
`result < 0xe0` to tell the two apart. Each value has one meaning, and a retired value is
never reused. The codes are grouped by the operation that returns them. The last column is
the text `bdio_printexecres` prints after `error: XX`. Only the codes listed with a message
have one; every other code prints `unknown error` with its code.

| Code | Operation | Meaning | Printed by `bdio_printexecres` |
|---|---|---|---|
| `0x00` | any | ok | — (not an error) |
| `0xc0` | catalog scan | end of catalog | — (not an error) |
| `0xe0` | open, exec | file not found | `file not found` |
| `0xe1` | open, exec | drive (fdd) not ready | `fdd not ready` |
| `0xe2` | close | file handle not found | `unknown error` |
| `0xe3` | open, exec | reading not allowed | `reading not allowed` |
| `0xe4` | open | writing not allowed | `unknown error` |
| `0xe5` | - | retired (was open: drive not ready; `0xe1` is used instead, not reused) | `unknown error` |
| `0xe6` | close | catalog read error | `unknown error` |
| `0xe7` | exec | execution not allowed | `execution not allowed` |
| `0xe8` | exec | catalog and file handle mismatch | `cat and file handle mismatch` |
| `0xe9` | exec | not enough user memory | `not enough user memory` |
| `0xea` | exec | not all sectors loaded (sector read failed) | `not all sectors loaded` |
| `0xeb` | create | catalog read error | `unknown error` |
| `0xec` | create | catalog save error | `unknown error` |
| `0xed` | create | drive (fdd) not ready | `unknown error` |
| `0xee` | create | file name already exists | `unknown error` |
| `0xef` | close | catalog save error | `cat save error` |
| `0xf0` | delete, setattr | catalog save error | `unknown error` |
| `0xf1` | delete, setattr | drive (fdd) not ready | `unknown error` |
| `0xf2` | delete, setattr | file not found | `unknown error` |
| `0xf3` | fcreate, close | disc full: no free sector for a new file, or a write hit the end of the file's gap | `disc full` |
| `0xf4`-`0xfe` | - | free (not assigned) | `unknown error` |
| `0xff` | open | no free file handle (`BDIO_FDESCRIPTOR_NUMBERFULL`) | `unknown error` |

Close codes are not contiguous (`0xe2`, `0xe6`, `0xef`): `0xe7` stays the exec code, so the
close save error moved to `0xef`.

## Shell

The prompt shows the active drive, e.g. `A>`.

| Input | Effect |
|---|---|
| `help` | list the commands |
| `a:` / `b:` | change the active drive (reads its catalog) |
| `bcos` | leave bdos and go back to the bcOS prompt |
| `exit` | stop the whole system (CPU halt) |
| *anything else* | run a program: `NAME args…` |

A program is looked up on the active drive only (see the default session above).

To run a program, the shell takes the first word, upper-cases it, pads it to 8 characters
and adds `PRG`. It then:
1. looks the file up in the catalog;
2. checks the **X** attribute;
3. checks that the file fits in free memory;
4. loads it to `0x6000` and `cal`s it.

The program returns to the shell with `ret`. The whole command line stays in the buffer at
`0x0dd2`, and programs parse it with `strnextword(BDIO_CMDPROMPTADDR)`. `strnextword(P)` returns the
address of the next word, or of the terminating NUL when there is none. It never returns `0`,
so a program finds a missing argument by testing the first byte of the result for NUL.

## Argument library (`bdosargs.b`)

The six utilities (`ls`, `cp`, `rm`, `cha`, `cat`, `format`) share their argument helpers in `src/bdos/bdosargs.b`
(issue #43, D11). `bdosargs.b` contains no `#include`. Each utility includes these files in this order:

```
#include std.b
#include bdosh.b
#include strings.b
#include bdostools.b
#include bdosargs.b
```

`bdostools.b` comes before `bdosargs.b` because `argfile` calls `bdio_fnormalize`. The command line is upper-cased
(`upstring`) before any helper reads it.

`texted` does not use the library. It takes no command-line arguments, and its `l` and `s` file names are interactive
commands with no drive prefix, so it keeps `bdostools.b` alone (D11).

| Helper | Contract |
|---|---|
| `getdriveletter(drive)` | `"A"`, `"B"`, or `"?"` for any other drive |
| `getdrive(Pword)` | a word starting with `A:` gives `BDIO_DRIVEA \| DRIVEPRESENT`, `B:` gives `BDIO_DRIVEB \| DRIVEPRESENT`; otherwise the active drive (`bdio_getdrive()`) without the flag |
| `changeDriveIfNeeded(current, target, silent)` | switches to `target` when it differs from `current`; returns the drive that is now active |
| `getswitch(Pword, Pletters)` | the `-x` option matcher: returns the 1-based position of the word's second character in the NUL-terminated list `Pletters` when the word starts with `-`, else 0. Only the first two characters are read, so a bare `-` gives 0. Each tool maps the position to its own mode and keeps its own precedence |
| `argfile(Pword, Pcatname)` | parses one `[d:]name.ext` word: returns the `getdrive` result, skips the `d:` prefix, ends the word in place at its first space (the rest of the line stays in the buffer), and writes the 11-character catalog name with `bdio_fnormalize`. A caller that needs a later word takes its address with `strnextword` before calling `argfile` on the earlier one |
| `printusage(Ptitle, Pline1, Pline2)` | prints each non-zero string followed by a newline, title first; `0` skips a line |

`DRIVEPRESENT` (`0x0100`) is defined once, in `bdosargs.b`.

**Size trade-off.** The compiler links every function of every included file, and dead-code elimination is still open
(#16). Each tool therefore pays for all six helpers, including those it does not call (`ls` and `format` also pay for
`argfile` and `bdio_fnormalize`). The library removes the duplicated helpers, but the ported tools are **larger** today,
not smaller. The table is from `src/bc/code_size.csv`: the "before" rows are the sources before the port, the "after"
rows are the ported sources, both dated 2026-11-23. Compare with `python3 scripts/code_size.py`. The saving is expected
once #16 lands.

| Tool | Before (bytes) | After (bytes) | Change |
|---|---:|---:|---:|
| `ls` | 7318 | 8296 | +978 |
| `cp` | 7095 | 7708 | +613 |
| `rm` | 7915 | 8410 | +495 |
| `cha` | 7029 | 7565 | +536 |
| `cat` | 7767 | 8224 | +457 |
| `format` | 10307 | 11263 | +956 |
| **six tools** | **47431** | **51466** | **+4035** |

## Programs and the discs they are on

Use `-h` for help in each tool. File arguments accept a drive prefix: `[d:]name.ext`.

| Program | Usage | What it does |
|---|---|---|
| `ls` | `ls [-a] [d:]`; `ls -h` prints help | lists files: name, `SRWX` attributes, size in bytes, start track/sector, length in sectors; then free catalog entries and the free sectors of the allocatable area (see Allocation). `-a` includes system files |
| `cp` | `cp [d:]src.ext [d:]dst.ext` | copy a file, also between drives |
| `rm` | `rm [-f] [d:]name.ext` | delete a file; `-f` is needed for system files |
| `cat` | `cat [-b\|-c] [d:]name.ext` | print a file as a hex dump (`-b`) or as characters (`-c`) |
| `cha` | `cha [+-][SRWX] [d:]name.ext` | set or clear attributes |
| `format` | `format [-q] d:` | `-q` (quick) writes an empty `DISC.CAT` on a disc that already has the system layout. A full format makes the target a **system disc**: wipes it, copies the boot sector, creates the catalog and copies `BDOS.SYS`, `LS`, `CP`, `FORMAT`, … from the source system disc |
| `hellowrd` | `hellowrd` | prints "Hello world!" and a number. On `os.bdd` and on `utils.bdd` (same build) |
| `texted` | `texted` | TextEd v1.2 (on `utils.bdd`, so run `b:` first), a line editor: `i <n> <s>` insert lines from `n` in steps of `s`, `p <n> <m>` print, `d <n> <m>` delete, `l <file>` load (replaces the buffer; a missing file prints the bdio error and keeps it), `s <file>` save (a missing file name or number prints an error and does nothing), `m` memory stats, `h` help, `q` quit |
| `theodore` | `theodore` | On `utils.bdd`, so run `b:` first. Looking for uncle Theodore v1.1, a guessing game: find uncle Theodore among train stops 0..99 with north/south hints; the start stop comes from the hardware random generator; 100 (or more) quits |
| `calc` | `calc` | On `utils.bdd`, so run `b:` first. Calculator v1.1, a bdos program (v1.1 adds input validation and the error messages): `h` help, `q` quit, and `+`, `-`, `*`, `/` on two operands (asked for with `1>` and `2>`, the result is printed after `res>`). An operand is a decimal number from 0 to 65535; anything else prints `error: bad number` and the operation stops there. Results are unsigned 16-bit and wrap modulo 65536 (`3-5` gives 65534), and `/` truncates (`100/7` gives 14). Dividing by 0 prints `error: division by zero`. Any other command prints `error: unknown command, type h for help` |

`fddtest` and `debug` are in the sources but are not built onto the disc.

### TextEd file format

`s <file>` writes, and `l <file>` reads, a text file of records (`saveLines` / `readLines` in
`texted.b`):

- one record per line: `<decimal line number> <text>`, followed by `0x13`. This is the
  `CHAR_LF` of `texted.b` and `cat.b`, not `0x0a`;
- after the last record, one `0x00`;
- then zero padding to the end of the sector (buffered write, flush-on-close).

`l` replaces the buffer. It reads the file in buffered chunks, so records may span sectors; it
stops at the first `0x00` or at the end of the file. A record with no valid number or no text
is skipped, and text longer than the line length is truncated. `cat -c` shows each record
ending with ` !ln`.

For host text files (`ftool importtext` and `ftool exporttext`), see "Host text files" under "Building the system disc".

## Building the system disc

From `src/` (the scripts pick the interpreter themselves: `winpty python` on Git Bash, else `python3`):

```bash
./buildos      # bcOS ROM + boot loader + bdos shell
./buildtools   # ls cp format rm cha cat
./buildapps    # helloworld texted theodore calc
./makedisc     # convert each .btap to sectors, then build a fresh os.bdd (src/disc.bddmanifest) and utils.bdd (src/utils.bddmanifest)
./run          # start the emulator; enter "os.bdd" when asked for the disk name
```

A fresh clone must build first. Run the whole pipeline once: `cd src && ./buildos && ./buildtools && ./buildapps && ./makedisc`.
It recreates every ignored file that `disc.bddmanifest` and `utils.bddmanifest` use, the ROM, `os.bdd` and `utils.bdd`. `./run` prints this command
when the ROM or `os.bdd` is missing. `python3 run_tests.py` runs it before the e2e tests.
`debug`, `fddtest` and the programs in `src/bc/code/` are not part of the pipeline; build them on demand
with `./bcc` (for example `./bcc bdos/debug`).

A single program can also be built with the console command `bcc bdos/ls` (after
`pip install -e .`), and the emulator started with `bc64 bc81asmc/bcOS/bcos_v1_2_0.b81`.

`makedisc` uses `ftool.py`:

| Command | Effect |
|---|---|
| `btap2bin in.btap out.bin` | drop the tape preamble and decode bits to bytes |
| `createbdd file.bdd` | make an empty 128 KB disk |
| `importsector in.bin disk.bdd track sector` | write a file to the disk starting at that sector |
| `exportsector disk.bdd out.bin track sector` | read one sector out |
| `dumpsector disk.bdd track sector count` | hex dump sectors |
| `mkdisc disc.bddmanifest out.bdd` | build a disc from a manifest: places the files, writes the catalog. Any error stops it before anything is written (see below). `makedisc` runs it for `disc.bddmanifest` (`os.bdd`) and for `utils.bddmanifest` (`utils.bdd`) |
| `importtext DISC.bdd host.txt NAME.EXT` | add a host text file to an existing disc as the TextEd file `NAME.EXT` (line numbers 10, 20, 30 …). See "Host text files" |
| `exporttext DISC.bdd NAME.EXT host.txt [--numbers]` | write the text of the TextEd file `NAME.EXT` to a host file, without line numbers; `--numbers` keeps the `<number> ` prefix of each record |

### Disc manifest

`src/disc.bddmanifest` lists the files of `os.bdd`, and it states the layout requirements of the system
disc. `./makedisc` runs `ftool mkdisc disc.bddmanifest os.bdd`, which writes the catalog and every file.
`src/utils.bddmanifest` is the manifest of `utils.bdd` and works the same way (`./makedisc` runs
`ftool mkdisc utils.bddmanifest utils.bdd`). The catalog lengths are the source sizes, so a program that grows
gets its new length, and the files after it move, unless it has a fixed slot (`max=`). A new system utility is
one line in `disc.bddmanifest`; a new application or game is one line in `utils.bddmanifest`. A catalog length shorter than the real program loads a truncated program that never returns to the shell. That is what made `cp` hang before #37 (issue #73): it ate the keyboard input and created no copy.

One file per line. `#` starts a comment, and blank lines are ignored:

```
NAME.EXT  SOURCE  ATTRIBS  [OPTIONS]
```

| Column | Meaning |
|---|---|
| `NAME.EXT` | 1–8 characters, plus an optional extension of 0–3. `A–Z` and `0–9` only, upper-cased. `DISC.CAT` is reserved |
| `SOURCE` | file path, relative to the manifest's directory. `-` for `DISC.CAT`, which the tool writes |
| `ATTRIBS` | letters `R W X S`, in any order |
| `OPTIONS` | `key=value` tokens, in any order, each at most once (see below) |

| Option | Meaning |
|---|---|
| `role=boot\|catalog\|system` | the three special entries. They are the first three lines, in this order: `BOOTSECT.BIN` (boot), `DISC.CAT` (catalog), `BDOS.SYS` (system). No other line has a role |
| `at=T/S` | exact start (decimal). It may not be before the end of the previous slot, and must be on the disc |
| `max=N` | at most N sectors. It reserves an N-sector slot, so the next file without `at=` starts after it. Without `max`, the slot is the file's own size |

The roles keep their hardware rules:

- `role=boot` needs `at=0/0 max=1`, and a 128-byte file ending with the signature `BD 05 01 01`.
- `role=catalog` needs source `-`, `at=0/1 max=31` (catalog v1).
- `role=system` needs `at=2/0` and `max` up to 160 (the boot loader range). Its catalog length is `max`, and the file is zero-padded.

Files without `at=` follow back to back after the previous slot.

Any error stops the build with a message on stderr (`mkdisc: error: ...`), exit status 1, and no output file:

- a source file is missing or empty;
- a file is over its `max=`, or over 255 sectors (the length is one byte);
- `max` is over 255;
- a role rule is broken, or the three role lines are missing or out of order;
- an unknown or malformed option, or an option given twice;
- a file would end past sector 1024 (the disc is full);
- more than 247 catalog entries are used (one must stay empty);
- an explicit start is before the previous slot ends, or outside the disc;
- a bad or duplicate name, an unknown attribute letter, or empty attributes;
- a malformed line.

### Host text files

`ftool importtext` and `ftool exporttext` (`src/ftool_text.py`) copy text between a host file and a
TextEd file on a disc image. They work on any disc image of exactly 131072 bytes (`.bdd`), and they change
only the one catalog entry and the sectors of the new file (`importtext`), or only the host file (`exporttext`).

```bash
ftool importtext DISC.bdd host.txt NAME.EXT
ftool exporttext DISC.bdd NAME.EXT host.txt [--numbers]
```

`importtext`:

- numbers the host lines 10, 20, 30 …, and writes them in the TextEd format (see "TextEd file format");
- adds a catalog entry with attributes R W (`0x03`), and places the file in the largest free gap, the same rule
  bdio uses for a file that TextEd saves (see Allocation; #41). If the text needs more sectors than the largest gap,
  the command fails with `disc full` before it writes anything;
- never overwrites: a name that already exists on the disc is refused. The name follows the manifest rules
  (1–8 characters, plus 0–3 for the extension; `A–Z` and `0–9`, upper-cased). `DISC.CAT` is refused.

Host text rules:

| Item | Rule |
|---|---|
| line endings | host input may use LF or CRLF (the CR is dropped); a missing last newline is accepted; each record on the disc ends in 0x13; exporttext writes LF line endings (every line, including the last, ends with LF) |
| characters | tab (`0x09`) and printable ASCII (`0x20`–`0x7e`) only; any other byte is an error |
| line length | at most 80 bytes, the TextEd limit |
| line count | at most 6553, so that line numbers fit in 16 bits |
| empty line | stored as one space, because `readLines` skips a record with no text. A host line of exactly one space cannot be told apart from an empty line, so it is refused |
| file size | at most 255 sectors (the catalog length is one byte) |

`exporttext`:

- finds the entry by name, and reads its sectors up to the first `0x00`;
- writes one LF-terminated host line per record. Without `--numbers` the line is the record text only (a
  one-space text becomes an empty line). With `--numbers` the line is the whole record, `<number> <text>`;
- is strict: a malformed record (no number, a number above 65535, no space after it) is an error, so that no
  line is lost without notice. `--numbers` must be the last argument; any other extra argument is an error;
- replaces the host file only when the whole export succeeded.

Both commands check everything before they write. On an error the disc image (`importtext`) or the host file
(`exporttext`) is left unchanged, and the command prints one line on stderr and exits with status 1:

```
importtext: error: NAME.TXT already exists on the disc (it is never overwritten)
exporttext: error: NAME.TXT not found on the disc
```

Other messages name the limit that was broken, for example `line 3: 81 characters, at most 80 (TextEd limit)`,
`line 2: byte 0x0b is not allowed (only tab and printable ASCII)`, `catalog full`, or `disc full`.

## Testing

The shell is tested end to end in `src/tests/test_e2e_bdos.py`. The scripts `src/bc64/testdata/e2e/bdos_*.in.txt`
boot a temp copy of the freshly built system disc (`os.bdd`) and check the output of `ls`, `cat`, `hellowrd`, `rm`
and the error messages. `cp` copies a file (`cp test.b copy.b`), and `cat` checks the copy. See `docs/01-emulator.md`,
End-to-end tests.

`src/tests/test_e2e_bdos_cmdtable.py` pins the command lines the six utilities accept. It runs a table of example
command lines (`-h` of each tool, `ls` and `ls -a` with and without `b:`, `cat`, `cp`, `cha`, `rm` and `format -q b:`)
on `os.bdd` in A and a temp copy of `utils.bdd` in B, and compares the masked transcript with the golden
`src/bc64/testdata/e2e/bdos_cmdtable.*`. The golden must not change with the library (see "Argument library").

The TextEd tests (`src/tests/test_e2e_texted*.py`) boot `os.bdd` in A with a temp copy of `utils.bdd` in B, and
run `b:` then `texted`, so the save and load happen on B.

The calculator and theodore tests (`src/tests/test_e2e_calc.py`, `src/tests/test_e2e_theodore.py`) use the same
setup: `os.bdd` in A, a temp copy of `utils.bdd` in B, and `b:` before the program.

The utilities disc is tested in
`src/tests/test_e2e_utils_disc.py`: its structure against `utils.bddmanifest`, that its `BOOTSECT.BIN` and
`BDOS.SYS` bytes equal those on `os.bdd`, that the build is reproducible, and that it boots alone in A.

## Roadmap (from README / bdos.md)

- **bdos 1.1b / 2.0:** use the real-time clock for file dates in the catalog, store load
  addresses and a manifest in it (still no directories, still simple allocation).
- relocatable executables and memory management, script execution, pipes between
  programs.
- bigger discs (80 tracks × 32 sectors).
