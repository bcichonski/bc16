I have always wanted to build 8bit computer, as i am to lazy to work with hardware, this is the closest thing to that. Ultimate goal is to have a language compiler working for it.

Detailed documentation of the current BC64 (emulator, assembler, compiler, bcOS, bdos) is in [docs/](docs/README.md).

[![tests](https://github.com/bcichonski/bc16/actions/workflows/tests.yml/badge.svg?branch=master)](https://github.com/bcichonski/bc16/actions/workflows/tests.yml)

# Getting started

Needs Python 3.10 or newer. From the repo root:

```bash
python3 -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .                                # installs parsy and the bc64, bc81asmc, bcc and ftool commands
cd src
bc64 bc81asmc/bcOS/bcos_v1_2_0.b81              # run the emulator; at the "Disk A name:" prompt enter: os.bdd, at "Disk B name:" enter: utils.bdd
bcc bdos/helloworld                             # build a program: helloworld.b -> .basm -> .btap
cd .. && python run_tests.py                    # run all the tests
```

Only sources are committed. The ROM (`bcos_v1_2_0.b81`), the discs (`src/os.bdd`, `src/utils.bdd`) and everything else the build
produces (`.basm`, `.btap`, `.sector(s)`, and `.genb` from `bc.py --verbose`) are ignored by git. A fresh clone must
build first, before `./run` or the tests (`./run` tells you so if something is missing):

```bash
cd src && ./buildos && ./buildtools && ./buildapps && ./makedisc
```

`python run_tests.py` builds the pipeline itself before the end-to-end tests (`--no-build` skips that). If you only
want to run the machine, use the `bc64` zip from the Release page: it has the built ROM, `os.bdd` and `utils.bdd`. Run it with disk A `os.bdd`, and answer `utils.bdd` at the `Disk B name:` prompt for the default two-disc session.

`debug`, `fddtest` and the programs in `src/bc/code/` aren't part of the pipeline. Build them on demand with
`./bcc <name>` (for example `./bcc bdos/debug`).

# Releases

Every machine generation is a tagged GitHub Release with a zip. The tags are:

| Tag | Generation | Commit |
|---|---|---|
| `bc16-v1.0` | BC16 (tape only) | `bd2498a` |
| `bc32-v1.0` | BC32 (adds clock, random generator, floppy drive) | `6304761` |
| `bc64-v*` | BC64 (the current machine, `bc64-v1.0` and later) | the tagged commit |
| `bc-v0.5` | an early tag that already existed | |

What the zips contain:

- **bc64** (`bc64-vX.Y.zip`, root folder `bc64-vX.Y/`): the tracked files of the emulator, the built ROM, `src/os.bdd` and `src/utils.bdd`, the
  toolchain (`bc`, `bc81asmc`, `bdos`, `ftool`, the shell scripts), `README.md`, `LICENSE`, `pyproject.toml` and the
  reference docs `docs/0*-*.md`. Tests, test data, CI files and planning docs are left out. Unpack it, then
  `cd bc64-vX.Y/src && ./run` starts the machine. At the prompts enter `os.bdd` for disk A and `utils.bdd` for disk B.
- **bc16** and **bc32** (`bc16-v1.0.zip`, `bc32-v1.0.zip`): the frozen `bc16_v1.0` / `bc32_v1.0` folders that used
  to live in `release/` (emulator, assembler, tapes or discs), plus a `rom/` folder with the bcOS ROM and a
  `RELEASE-NOTES.md`. The bc32 ROM is bcOS 1.1.1. The bc16 ROM (bcOS 1.0) is assembled at release time from
  commit `bd2498a`. The only change to the frozen files is that `run` picks the Python interpreter like `src/run`.

`scripts/make_release.py` builds the zips (standard library only, run it in a full clone with history, from
anywhere). Output goes to `dist/` unless `--out DIR` is given:

```bash
python3 scripts/make_release.py bc64 --tag bc64-v1.0      # dist/bc64-v1.0.zip, from HEAD
python3 scripts/make_release.py legacy bc16               # dist/bc16-v1.0.zip
python3 scripts/make_release.py legacy bc32               # dist/bc32-v1.0.zip
python3 scripts/make_release.py notes bc16                # prints the release notes (the README "# BC16" section)
```

The `legacy bc16` command needs `parsy` (`pip install -e .`), because it assembles the old ROM.

`.github/workflows/release.yml` publishes bc64: pushing a `bc64-v*` tag builds the intermediates, runs the tests,
builds the zip and creates the GitHub Release with the zip attached. Running the workflow by hand
(`workflow_dispatch`, input: zip name) does the same without publishing and uploads the zip as a workflow artifact.
GitHub only offers `workflow_dispatch` for a workflow file on the default branch (`master`), so the dry run is
available only after the file is there.

The two legacy releases are published once, by the repo owner:

```bash
git tag bc16-v1.0 bd2498a
git tag bc32-v1.0 6304761
git push origin bc16-v1.0 bc32-v1.0
python3 scripts/make_release.py legacy bc16
python3 scripts/make_release.py notes bc16 > dist/bc16-notes.md
gh release create bc16-v1.0 dist/bc16-v1.0.zip --title bc16-v1.0 --notes-file dist/bc16-notes.md
python3 scripts/make_release.py legacy bc32
python3 scripts/make_release.py notes bc32 > dist/bc32-notes.md
gh release create bc32-v1.0 dist/bc32-v1.0.zip --title bc32-v1.0 --notes-file dist/bc32-notes.md
```

# BC64
## roadmap
0. memory increased to 64kb
1. cpu 16bit arithmetic and binary operations, long relative jumps? improved cpu stack frames
2. related changes in basmc
2. related changes and optimizations in bcc (usage of new arithmetic)
2. bcos 1.2 (move from bcc stdlib, other improvements)
3. bdos 1.1 (buffered read and buffered writes)
4. texted and game new versions (done: TextEd v1.2 #1, theodore v1.1 #2)
5. bcc (new optimization to drop unused code and managing stacks inside subroutines)
6. bdos 1.1b (fcat with dates! and load addresses)
7. new discs (increase number of tracks and sectors 80 tracks by 32 sectors)
8. basm on bc64
9. bcc on bc64
10. networking?

## architectural notes
### OS
bcos v1.2
 - some procedures from b compiler stdlib incorporated
 - usage of new arithmetic for bc8083 cpu
 - minor fixes

bcos v1.1 
 - some procedures from b compiler stdlib incorporated
 - minor fixes
 - still tape-only suport with for .btap files
 - new code to recognize presence of floppy disk drive to boot their system

bdos v1
 - disk operation system
   - micromode (the os itself just knows how to load and run executables)
 - bfs file system
   - only files
   - but with some attributes

bdos v1.1
 - buffered reads and writes

bdos v2.0
 - support for the clock
 - fcat 2.0 extended to have file modification dates and program loading adresses and manifest
   - still no directories
   - still primitive allocation management

### CPU
microprocessor: bc8183 (cpu 16bit arithmetic and binary operations, long relative jumps? improved cpu stack frames)
64kb address space
16 in/out ports
no interrupts
one extension slot (basically allows a device to use memory directly)

## memory
memory: 64kb
~3.5kb bcos (0x0000-0x0d6b) + bdos with its buffers (0x0d80-0x5fff, ~21kb), user programs are loaded at 0x6000 leaving about 40kb free (up to the cpu stack at the top of memory)

### peripherals
same as BC32 plus
  - double drive for single side 3" floppy disks that has 64 tracks of 16 sectors of 128 bytes = 128 KB
  - planned monitor support later!

# BC32
## roadmap
0. smaller peripherals
1. fdd
2. memory extension
3. bcos upgrade
4. bdos development
5. new binary file format
6. new assembler
7. new blang compiler

## architectural notes
### OS
bcos v1.1 
 - some procedures from b compiler stdlib incorporated
 - minor fixes
 - still tape-only suport with for .btap files
 - new code to recognize presence of floppy disk drive to boot their system

bdos v1
 - disk operation system
   - micromode (the os itself just knows how to load and run executables)
 - bfs file system
   - only files
   - but with some attributes

### CPU
microprocessor: bc8182 (very small fixes regarding f register)
64kb address space
16 in/out ports
no interrupts
one extension slot (basically allows a device to use memory directly)

## memory
memory: 32kb
~6kb rom + 26kb ram with option to extend in future

### peripherals
same as BC16 plus
- real time clock 0x3
- random generator 0x5
- floppy disk drive 0x8
  - port 0x8 used for instructions and communication:
    - 0xf0 - ping with response with version of the drive: returns READY | FDVER1 (0x11)
    - 0xf1 <imm16> - configure DMA - sets where drive can put read sector, always 128 bytes returns READY
    - 0xfa - set active drive A returns READY
    - 0xfb - set active drive B returns READY
    - 0xf2 <imm8:t> <imm8:s> - reads sector s from track t returns READY or READERROR
    - 0xf3 <imm8:t> <imm8:s> - writes sector s from track t returns READY or READERROR
    - 0xf4 - eject active drive
    - response codes:
      - READY: 0x10
      - FDVER1: 0x01
      - DRIVEERROR: 0xe1
      - READERROR: 0xe2 (also returned for track/sector out of range, for reads and writes)
      - WRITEERROR: 0xe3 (defined, not used by the emulator)

  - uses direct memory access to read entire sector
  - double drive for single side 3" floppy disks that has 64 tracks of 16 sectors of 128 bytes = 128 KB


# BC16
## architectural notes
### OS
bcos v1.0
tape-only suport with for .btap files

### CPU
microprocessor: bc8181 - bc8182
64kb address space
16 in/out ports
no interrupts

### memory
memory: 16kb
4kb rom + 12kb ram with option to extend in future

### the bc8182 microprocessor
same as bc8181 but with some small errors fixed
some extentions like 16bit arithmetic? or 8bit div/mod/mul


### peripherals:
- terminal keyboard uses io ports 0x0
- terminal printer uses io ports 0x1
- cassette recorder uses io ports 0x2
  ports 0x2 are used for manipulating recorder:
    valid commands to sent via 0x2 output port:
    0x80 - load tape - set this bit and question for the name of the tape file to read will appear; only one of 0x80/0x40 flag can be set
    0x40 - save tape - set this bit and question for the name of the tape file to save will appear; only one of 0x80/0x40 flag can be set
    0x20 - start moving recorder engine, initiates read/write sequence
    0x10 - stop and go back to ready state (closes the tape file)
    0x02 - TX flag - has to be set in every command, otherwise the command is ignored
    0x01 - data bit for writing or reading bit to/from the device (when none of the above is set)
    status read from 0x2 port uses the same bits: 0x80 read mode, 0x40 write mode, 0x20 moving,
    0x10 ready, 0x08 error (ie wrong state or file not found), 0x02 bit available, 0x01 data bit

  example session for writing to the tape:
  read 0x2 port

### the bc8181 microprocessor
#### registers:
```
0xF 0xE PC - 16bit
0xD SS - address of STACK segment
0xC SI - 8 bit stack index goes down from memory top

0xB F - 8bit processor flags
 0x0 - ZERO
 0x1 - CARRY
 0x2 - NEGATIVE
 0x3 - OVERFLOW
0x1 A - 8bit accumulator
0x4 CI - 8bit register addressing C segment
0x5 DI - 8bit register addressing D segment
0x8 CS - 8bit register storing address of C segment
0x9 DS - 8bit register storing address of D segment
```
#### instuctions
```
instructions are 1,2 or more bytes long:
B0(HL)B1(HL)
bc8181 instruction set B0H:
0x0 - NOP               ;
0x1 - MOV rno,imm        ; r=imm
0x2 - MOV rno1,rno2      ; r1 = r2
0x3 - MOV rno1,(rno2, rno3)    ; r1 = mem(r2) , r2 can be CI or DI
0x4 - MOV (rno1,rno2), rno3   ; mem(r1) = r2
0x5 - CLC A
  0x0 - add imm          ; A += imm
  0x8 - add rno          ; A += r
  0x1 - sub imm
  0x9 - sub rno
  0x2 - and imm
  0xA - and rno
  0x3 - or imm
  0xB - or rno
  0x4 - xor imm
  0xC - xor rno
  0x5 - shl imm
  0x6 - shr imm
  0x7 - not A - only 1 byte
  0xD - inc A - only 1 byte!
  0xE - dec A - only 1 byte!
  0xF - 
      0xa - 16bit arithmetic
      - 0x0 add16 rno imm16
      - 0x8 add16 rno
      - 0x1 sub16 rno imm16
      - 0x9 sub16 rno
      - 0x2 mul16 rno imm16
      - 0xa mul16 rno
      - 0x3 div16 rno imm16
      - 0xb div16 rno
      - 0x4 mod16 rno imm16
      - 0xc mod16 rno
      - 0xd inc16 rno
      - 0xe dec16 rno
      0xb - 16bit binary
      - 0x2 and16 rno imm16
      - 0xa and16 rno
      - 0x3 or16 rno imm16
      - 0xb or16 rno
      - 0x4 xor16 rno imm16
      - 0xc xor16 rno
      - 0x5 shl16 rno imm16
      - 0xd shl16 rno
      - 0x6 shr16 rno imm16
      - 0xe shr16 rno
      - 0x7 not16 rno
      note: in the register forms the second operand is implied by the first one:
      csci is combined with dsdi, dsdi and af are combined with csci
0x6 - JMP t,(rno1,rno2)
  0x0 - if ZERO
  0x4 - if NOT ZERO
  0x1 - if CARRY
  0x5 - if NOT CARRY
  0x2 - if NEGATIVE
  0x6 - if NOT NEGATIVE
  0x3 - if OVERFLOW
  0x7 - if NOT OVERFLOW
  0x8-0xF is special mode where addres is CS:imm (its kind of short absolute jump)
0x7 - JMR t,imm7
  t like JMP, imm7 is 8bit sign-magnitude value (bit 7 = sign, bits 0-6 = distance)
  when t 0x8-0xF is special mode where rno is treated like imm7
0x8 - PSH rno
0x9 - POP rno
0xA - CAL(R) 
  0x0 (rno1,rno2)
  0x8 imm16 - call to address
  0x1 (rno1,rno2) - extended relative call
  0x9 imm15 - extended relative call
0xB - RET
0xC - IN
 0x0-0x7 - rno, #imm
 0x8-0xf - rno1, #rno2
0xD - OUT imm,rno
 0x0-0x7 - #rno1, imm  (not working: assembler and cpu disagree on encoding, unused)
 0x8-0xf - #rno1, rno2
0xE - EXT - extensions
    0x01 - JRX t, imm15 - extended relative jump (15bit sign-magnitude)
    0x02 - JRX t, regno - same
    note: negated conditions (nz, nc, nn, no) are currently evaluated as plain ones by the cpu
0xF - KIL
```
full and current reference: [docs/02-assembler.md](docs/02-assembler.md)
### software
external assembler bc81asmc up to 1.1 (240317) - currently v1.3 (240914) for bc8183
external compiler bc of b language for bc8181-bc8182 cpu v 1.0.0 (240317) - currently v1.3.1 (240927) for bc8183
calc - basic calculator (v1.1, a bdos app on `utils.bdd`, so run `b:` first)
texted - basic line editor (on `utils.bdd`)
theodore - simple game (v1.1, on `utils.bdd`, so run `b:` first)

