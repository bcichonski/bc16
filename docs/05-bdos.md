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
| `ls.b`, `cp.b`, `rm.b`, `cat.b`, `cha.b`, `format.b` | system utilities |
| `helloworld.b`, `texted.b` | apps on the system disc |
| `calc.b`, `theodore.b`, `fddtest.b`, `debug.b` | older or test programs, not on the disc |
| `bdos.md` | short design notes: disk format, bdio call list, memory map |

For each program the repo also keeps generated files: `*.genb` (preprocessed), `*.basm`,
`*.btap` and `*.sector(s)` (raw sectors).

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
| `… 0xfffe` | CPU stack, growing downwards from the top of memory |

Free memory, as reported by `bdio_freemem()`, is `SS:SI − 0x6000`, a little under 40 KB.

## Disk format (BFS)

A disk has 64 tracks × 16 sectors × 128 bytes (128 KB). The file system is flat, with no
directories. Each file is one **contiguous** run of sectors.

### Layout of the system disc (`src/os.bdd`, built by `./makedisc`)

| # | File | Start (track/sector) | Sectors | Attributes |
|---|---|---|---|---|
| 0 | `BOOTSECT.BIN` | 0/0 | 1 | S R |
| 1 | `DISC.CAT` | 0/1 | 31 | S R |
| 2 | `BDOS.SYS` | 2/0 | 152 | S R |
| 3 | `LS.PRG` | 13/0 | 64 | S R X |
| 4 | `HELLOWRD.PRG` | 17/0 | 15 | R X |
| 5 | `CP.PRG` | 21/0 | 56 | S R X |
| 6 | `FORMAT.PRG` | 25/0 | 82 | S R X |
| 7 | `RM.PRG` | 31/0 | 63 | S R X |
| 8 | `CHA.PRG` | 37/0 | 56 | S R X |
| 9 | `CAT.PRG` | 41/0 | 61 | S R X |
| 10 | `TEXTED.PRG` | 45/0 | 112 | R X |

The catalog itself is a file: `DISC.CAT`, from track 0 sector 1 to the end of track 1.

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
| `0x18` | `bdio_fbinbufread(h, Pbuf, bytes)` | buffered byte-count read (the length goes through `0x0d92`) | bytes read (`0` = error/EOF) |
| `0x19` | `bdio_fbinbufwrite(h, Pbuf, bytes)` | buffered byte-count write | bytes written |

- **File names:** `Pname` is the 11-character catalog form `NAME    EXT` (space-padded, no
  dot). `bdio_fnormalize` (bdostools.b) converts `name.ext` to that form.
- **Handles:** there is 1 write descriptor (handle `0x10|n`) and 3 read descriptors
  (`0x20|n`). Each descriptor is 10 bytes: number, catalog entry, current track/sector,
  current/total sequence, catalog track/sector, buffer counter, access mode (`0x0d`
  direct / `0x0b` buffered).
- **Shell-only functions:** `bdio_ffindfile`, `bdio_getfreesect`, `bdio_execute` and
  `bdio_freemem` are used by the shell and are not reachable through `bdio_call`.

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

To run a program, the shell takes the first word, upper-cases it, pads it to 8 characters
and adds `PRG`. It then:
1. looks the file up in the catalog;
2. checks the **X** attribute;
3. checks that the file fits in free memory;
4. loads it to `0x6000` and `cal`s it.

The program returns to the shell with `ret`. The whole command line stays in the buffer at
`0x0dd2`, and programs parse it with `strnextword(BDIO_CMDPROMPTADDR)`.

## Programs on the system disc

Use `-h` for help in each tool. File arguments accept a drive prefix: `[d:]name.ext`.

| Program | Usage | What it does |
|---|---|---|
| `ls` | `ls [-a] [-h]` | lists files: name, `SRWX` attributes, size in bytes, start track/sector, length in sectors; then free entries and free sectors. `-a` includes system files |
| `cp` | `cp [d:]src.ext [d:]dst.ext` | copy a file, also between drives |
| `rm` | `rm [-f] [d:]name.ext` | delete a file; `-f` is needed for system files |
| `cat` | `cat [-b\|-c] [d:]name.ext` | print a file as a hex dump (`-b`) or as characters (`-c`) |
| `cha` | `cha [+-][SRWX] [d:]name.ext` | set or clear attributes |
| `format` | `format d: [-q]` | `-q` (quick) writes an empty `DISC.CAT` on a disc that already has the system layout. A full format makes the target a **system disc**: wipes it, copies the boot sector, creates the catalog and copies `BDOS.SYS`, `LS`, `CP`, `FORMAT`, … from the source system disc |
| `hellowrd` | `hellowrd` | prints "Hello world!" and a number |
| `texted` | `texted` | TextEd v1.2, a line editor: `i <n> <s>` insert lines from `n` in steps of `s`, `p <n> <m>` print, `d <n> <m>` delete, `l <file>` load, `s <file>` save, `m` memory stats, `h` help, `q` quit |

`calc` (calculator), `theodore` (a "find uncle Theodore" guessing game), `fddtest` and
`debug` are in the sources but are not built onto the disc.

## Building the system disc

From `src/` (the scripts use `winpty`; drop it outside Git Bash for Windows):

```bash
./buildos      # bcOS ROM + boot loader + bdos shell
./buildtools   # ls cp format rm cha cat
./buildapps    # helloworld texted
./makedisc     # convert each .btap to sectors, then write everything into a fresh os.bdd
./run          # start the emulator; enter "os.bdd" when asked for the disk name
```

`makedisc` uses `ftool.py`:

| Command | Effect |
|---|---|
| `btap2bin in.btap out.bin` | drop the tape preamble and decode bits to bytes |
| `createbdd file.bdd` | make an empty 128 KB disk |
| `importsector in.bin disk.bdd track sector` | write a file to the disk starting at that sector |
| `exportsector disk.bdd out.bin track sector` | read one sector out |
| `dumpsector disk.bdd track sector count` | hex dump sectors |

The catalog isn't generated. It comes from the hand-made `src/fcat0800.sector`, written to
track 0 sector 1, and the start tracks are hard-coded in `makedisc`. If a program grows past
its slot, both have to be edited by hand.

## Testing

The shell is tested end to end in `src/test_e2e_bdos.py`. The scripts `src/bc64/testdata/e2e/bdos_*.in.txt`
boot a frozen copy of the system disc (`smoke.bdd`) and check the output of `ls`, `cat`, `hellowrd`, `rm`
and the error messages. `cp` is a known failure: `cp test.b copy.b` reads keys until the input runs out,
so the test is marked `expectedFailure` (found by #49, issue not filed yet). See `docs/01-emulator.md`,
End-to-end tests.

## Roadmap (from README / bdos.md)

- **bdos 1.1b / 2.0:** use the real-time clock for file dates in the catalog, store load
  addresses and a manifest in it (still no directories, still simple allocation).
- relocatable executables and memory management, script execution, pipes between
  programs.
- bigger discs (80 tracks × 32 sectors).
