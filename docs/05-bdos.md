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
| `0x0d80–0x0dd1` | bdio variables: last error, active drive, catalog scan state, free entry/track/sector, `PMEMBUF_LEN` (`0x0d92`), file descriptor tables (write `0x0d94`, read `0x0da4`) |
| `0x0dd2–0x0dfe` | shell command-line buffer (45 bytes). **Programs read their arguments from here** |
| `0x0e00–0x0e7f` | temporary sector buffer (the boot sector is loaded here at boot) |
| `0x0e80–0x0eff` | catalog scan sector buffer |
| `0x0f00–0x5721` | `BDOS.SYS`: shell + bdio code (`0x4822` bytes), followed by its B variable stack |
| `0x5d00–0x5eff` | per-handle 128-byte buffers for buffered I/O (write handle, then 3 read handles) |
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

When the catalog is read (`bdio_fcat_read`, run on every drive change), bdio remembers the
first free catalog entry and the first free sector after the used area. New data is always
allocated from that point onwards (`bdio_getfreesect`), and files are written
append-only. Deleted space is not reused or compacted.

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

| Code | Meaning |
|---|---|
| `0x00` | ok |
| `0xc0` | end of catalog |
| `0xe0` | file not found (open) |
| `0xe1` / `0xe5` | drive not ready (open) |
| `0xe2` | close: descriptor not found |
| `0xe3` / `0xe4` | no read / no write attribute |
| `0xe6` | create: name exists (also close: catalog read error) |
| `0xe7` | exec: not executable (also close: catalog save error) |
| `0xe8` | exec: descriptor/catalog mismatch |
| `0xe9` | exec: out of memory |
| `0xea` | exec: sector read failed |
| `0xeb` / `0xec` / `0xed` | create: read error / save error / drive not ready |
| `0xf0` / `0xf1` / `0xf2` | delete/setattr: save error / drive not ready / not found |

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
`0x0dd2`, and programs parse it with `strnextword(BDIO_CMDPROMPTADDR)`.

## Programs and the discs they are on

Use `-h` for help in each tool. File arguments accept a drive prefix: `[d:]name.ext`.

| Program | Usage | What it does |
|---|---|---|
| `ls` | `ls [-a] [-h]` | lists files: name, `SRWX` attributes, size in bytes, start track/sector, length in sectors; then free entries and free sectors. `-a` includes system files |
| `cp` | `cp [d:]src.ext [d:]dst.ext` | copy a file, also between drives |
| `rm` | `rm [-f] [d:]name.ext` | delete a file; `-f` is needed for system files |
| `cat` | `cat [-b\|-c] [d:]name.ext` | print a file as a hex dump (`-b`) or as characters (`-c`) |
| `cha` | `cha [+-][SRWX] [d:]name.ext` | set or clear attributes |
| `format` | `format d: [-q]` | `-q` (quick) writes an empty `DISC.CAT` on a disc that already has the system layout. A full format makes the target a **system disc**: wipes it, copies the boot sector, creates the catalog and copies `BDOS.SYS`, `LS`, `CP`, `FORMAT`, … from the source system disc |
| `hellowrd` | `hellowrd` | prints "Hello world!" and a number. On `os.bdd` and on `utils.bdd` (same build) |
| `texted` | `texted` | TextEd v1.2 (on `utils.bdd`, so run `b:` first), a line editor: `i <n> <s>` insert lines from `n` in steps of `s`, `p <n> <m>` print, `d <n> <m>` delete, `l <file>` load (replaces the buffer; a missing file prints the bdio error and keeps it), `s <file>` save (a missing file name or number prints an error and does nothing), `m` memory stats, `h` help, `q` quit |
| `theodore` | `theodore` | On `utils.bdd`, so run `b:` first. Looking for uncle Theodore v1.1, a guessing game: find uncle Theodore among train stops 0..99 with north/south hints; the start stop comes from the hardware random generator; 100 (or more) quits |
| `calc` | `calc` | On `utils.bdd`, so run `b:` first. Calculator v1.0, a bdos program: `h` help, `q` quit, and `+`, `-`, `*`, `/` on two operands (asked for with `1>` and `2>`, the result is printed after `res>`). An operand is a decimal number from 0 to 65535; anything else prints `error: bad number` and the operation stops there. Results are unsigned 16-bit and wrap modulo 65536 (`3-5` gives 65534), and `/` truncates (`100/7` gives 14). Dividing by 0 prints `error: division by zero`. Any other command prints `error: unknown command, type h for help` |

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

### Disc manifest

`src/disc.bddmanifest` lists the files of `os.bdd`, and it states the layout requirements of the system
disc. `./makedisc` runs `ftool mkdisc disc.bddmanifest os.bdd`, which writes the catalog and every file.
`src/utils.bddmanifest` is the manifest of `utils.bdd` and works the same way (`./makedisc` runs
`ftool mkdisc utils.bddmanifest utils.bdd`). The catalog lengths are the source sizes, so a program that grows
gets its new length, and the files after it move, unless it has a fixed slot (`max=`). A new system utility is
one line in `disc.bddmanifest`; a new application or game is one line in `utils.bddmanifest`.

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

## Testing

The shell is tested end to end in `src/tests/test_e2e_bdos.py`. The scripts `src/bc64/testdata/e2e/bdos_*.in.txt`
boot a temp copy of the freshly built system disc (`os.bdd`) and check the output of `ls`, `cat`, `hellowrd`, `rm`
and the error messages. `cp` copies a file (`cp test.b copy.b`), and `cat` checks the copy. See `docs/01-emulator.md`,
End-to-end tests.

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
