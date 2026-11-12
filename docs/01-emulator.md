# BC64 emulator

The BC64 is a made-up 8-bit computer that exists only as a Python emulator. It has the
**bc8183** CPU, 64 KB of RAM and a few peripherals on 16 I/O ports. The emulator is in
`src/bc64.py` (it wires the machine together) and `src/bc64/`:

| File | Contents |
|---|---|
| `bc64.py` | builds the machine, loads the ROM image, runs the CPU, dumps memory on exit |
| `bc64/bc8183_cpu.py` | the CPU: registers, flags, instruction decoder, ALU, call stack, debug trace |
| `bc64/bc64_mem.py` | `MemBus`, a flat `bytearray` memory |
| `bc64/bc64_io.py` | `IOBus` and the devices: keyboard, printer, tape recorder, clock, random generator, floppy drive |
| `bc64/bc64_env.py` | host abstraction: console I/O (raw `getch`), files, debug log |

Older generations are frozen as GitHub Releases, tagged `bc16-v1.0` (bc8181/8182 CPU, 16 KB, tape only) and
`bc32-v1.0` (bc8182 CPU, 32 KB, adds clock, random generator and floppy drive). See "Releases" in the README.

## Running it

From `src/`:

```bash
bc64 bc81asmc/bcOS/bcos_v1_2_0.b81                 # after `pip install -e .` (repo root), works from any directory
python bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81        # normal run (this is what ./run does)
python bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81 d      # any 2nd argument turns on CPU trace
```

- The first argument is a **raw binary ROM image**. It is loaded at address `0x0000`, and
  execution starts there. A `.b81` image is made from an assembler `.btap` file with
  `./ftool btap2bin <in.btap> <out.b81>`.
- With trace on, the CPU appends the registers after every instruction to `cpudebug.log` in
  the current directory. This file grows very large very fast.
- When the CPU halts (`KIL`, or a stack access outside memory, see Memory), the whole memory is
  written to `bc64.dmp`, 65,536 bytes.
- On a terminal, keyboard input reads one character at a time with no echo (`msvcrt.getch` on
  Windows, `termios` raw mode elsewhere). In headless mode the keys come from the input instead
  (see below). Printer output goes to stdout, or to `--output` when given.
- The repo's shell scripts call `winpty python …`, because they were written for Git Bash on
  Windows. On Linux or macOS, call `python` directly.

### Options

| Option | Meaning |
|---|---|
| `--disk-a FILE` | disk image answered to the `Disk A name:` prompt |
| `--disk-b FILE` | disk image answered to the `Disk B name:` prompt |
| `--no-floppy` | do not attach a floppy drive: port `0x08` reads `0x00` and writes are ignored, so bcOS skips the floppy boot. Cannot be combined with `--disk-a` or `--disk-b` (exit 2) |
| `--tape-dir DIR` | directory where `*.btap` tape files are read and written |
| `--input FILE` | file with the keystrokes to type; `-` reads stdin (the default when stdin is piped) |
| `--output FILE` | file that receives a copy of every printer byte |
| `--max-instructions N` | stop with exit code 3 after `N` instructions (at least 1) without a halt |
| `--random-seed N` | seed the port `0x5` random generator with `N` (decimal or `0x` hex, at least 0; a bad value is exit 2), so a run is reproducible. Without it the generator is seeded from the system |
| `-h`, `--help` | list the options |

All options are optional and can be combined.

### Console and headless mode

- **Console** (the default when stdin is a terminal and no option is given): the keyboard is
  read with raw `getch`, and the disk and tape names are asked on the console.
- **Headless** (any option other than `--help`, or stdin is not a terminal): keys come from
  `--input FILE`, or from stdin when it is piped or redirected (`< keys.txt`). Printer output
  goes to stdout, and also to `--output` when given.

### Monitor without a disc

- `--no-floppy` starts bcOS with no floppy drive. Port `0x08` reads `0x00` (no READY bit) and
  ignores writes, so bcOS skips the floppy boot and goes straight to its `> ` monitor prompt. Use it
  to test the monitor. It is a headless option. It cannot be combined with `--disk-a` or `--disk-b`:
  that is a usage error, exit 2.

### Keys and Enter

- Every line ending in the key input (`LF`, `CR LF` or `CR`) is sent as one **CR** (`0x0d`),
  which is what Enter sends. Other bytes are sent as they are. Keys arrive one at a time, not
  line by line.
- A script is therefore an ordinary text file with one command per line.

### Prompts in headless mode

- `--disk-a` and `--disk-b` answer the `Disk A name:` / `Disk B name:` prompt every time the
  drive asks, so the answer still works after `EJECT`. As in the console, `.bdd` is added when
  the name does not end with it.
- Any other prompt, and a disk prompt for a drive with no option, takes the next line of the
  input. So `printf 'os.bdd\nls\n' | python3 bc64.py ROM` mounts `os.bdd` and then types `ls`.

### End of input

- When the emulator needs a key or a prompt answer after the last line of the input, it stops
  cleanly: exit code 0, output file closed, no memory dump. A program that is still waiting for
  keys stops at that point.
- A session that ends with `exit` halts the CPU, so it still writes `bc64.dmp`.

### Tape files

- With `--tape-dir DIR`, every relative `.btap` name is opened inside `DIR`. The recorder adds
  `.btap` to the name typed at the prompt, so `test` means `DIR/test.btap`. Absolute names are
  used as they are, and disk images are not affected. Without the option, tape files are in
  the current directory.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | the CPU halted (`KIL`, or a stack access outside memory; memory is dumped to `bc64.dmp`), or the input ended (no dump) |
| 1 | an exception in the emulator (the CPU prints the address and stack, Python the traceback) |
| 2 | usage error (argparse message, e.g. `--max-instructions 0`) |
| 3 | `--max-instructions` reached without a halt (message on stderr, no dump) |

### Example session

From `src/`:

```bash
printf 'ls\nhellowrd\nexit\n' | python3 bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81 --disk-a os.bdd --output out.txt
```

This boots bcOS from the ROM, mounts `os.bdd` as drive A, runs `ls` and `hellowrd`, and exits. The ROM,
`os.bdd` and `utils.bdd` come from the build (`cd src && ./buildos && ./buildtools && ./buildapps && ./makedisc`); they are not committed.

The default two-disc session mounts `utils.bdd` as drive B too. From `src/`, on copies of the discs:

```bash
printf 'b:\ntexted\nq\nexit\n' | python3 bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81 --disk-a os.bdd --disk-b utils.bdd --output out.txt
```

This boots from `os.bdd` in A, makes B the active drive with `b:`, runs TextEd from `utils.bdd`, quits it with `q`
and stops the system. `--disk-b` answers the `Disk B name:` prompt the same way `--disk-a` answers the A prompt.
`out.txt` then holds the printer output, including the typed commands:

```
bcOS 1.2
booting from FDDlding
bDOS 1.1 shell
9FF5 bytes free
reading disc...
A>ls
........
listing files of drive A:
HELLOWRD.PRG -R-X 0780 11 00 0F
TEXTED  .PRG -R-X 3200 2D 00 64
TEST    .B   -RW- 0100 33 04 02
EB catalog entries free; 00D6 sectors free...
A>hellowrd
..
Hello world!
10
A>exit
bye!
```

The disc is opened read-write, so a session can change it. This example leaves `os.bdd`
unchanged, but a program may not. Use a copy of `os.bdd` for tests. `out.txt` and `bc64.dmp`
are written to the working directory too.

## End-to-end tests

The e2e tests boot the whole system on the headless emulator, type a script, and compare the
printer output with a golden file. They are the `test_e2e_*.py` modules in `src/tests/`:

| Module | What it covers |
| :--- | :--- |
| `test_e2e_bcos.py` | bcOS monitor, with `--no-floppy` |
| `test_e2e_bdos.py` | bdos shell (`ls`, `cat`, `hellowrd`, `rm`, error messages, `cp`) on a temp copy of the built `os.bdd` |
| `test_e2e_disc.py` | `os.bdd`: its catalog and positions against `disc.bddmanifest`, and a session on it |
| `test_e2e_texted.py`, `test_e2e_texted_commands.py`, `test_e2e_texted_flows.py` | TextEd on the default A/B setup: `os.bdd` in A, a temp copy of `utils.bdd` in B, `b:` then `texted`. Save and load happen on B |
| `test_e2e_utils_disc.py` | `utils.bdd`: its structure against `utils.bddmanifest`, its `BOOTSECT.BIN` and `BDOS.SYS` bytes equal to `os.bdd`'s, a reproducible build, and a solo boot in A |
| `test_e2e_toolchain.py` | a B program compiled, assembled, put on a disc and run |
| `test_e2e_harness.py` | self-tests of the harness |
| `test_e2e_layout_shift.py` | the bdos scenarios and the smoke session on a disc with a grown `HELLOWRD.PRG`; proves layout changes need no golden edit |

The harness is `src/tests/e2e_harness.py`. For each scenario it:

- reads the script `<scenario>.in.txt` and the golden `<scenario>.golden.txt` from `src/bc64/testdata/e2e/`;
- copies the disc to a temp dir and runs `bc64.py` with `--input`, `--output` and `--max-instructions`;
- fails on exit 3 (instruction limit), on any other non-zero exit, when the source disc changed, or
  when `cpudebug.log` appeared;
- checks that the marker strings appear in the output, so an empty output cannot pass;
- compares the output with the golden byte for byte.

Nothing is written into `src/`, and the built `src/os.bdd` is never changed (each test boots a temp copy).

### Running them

```bash
python3 run_tests.py < /dev/null              # from the repo root: all suites; builds first, then e2e
python3 run_tests.py --group e2e --no-build < /dev/null   # e2e only, no build (outputs must exist)
cd src && python3 -m unittest tests.test_e2e_bdos   # one module
```

Long scenarios are marked `@h.slow` and are skipped unless `BC64_E2E_SLOW=1` is set, for example
`cd src && BC64_E2E_SLOW=1 python3 -m unittest tests.test_e2e_bdos`. No scenario is slow yet.

### Regenerating goldens

After an intended change in output, regenerate all e2e goldens and the smoke transcript from the repo root:

```bash
python3 run_tests.py --update-golden < /dev/null
```

It builds first (add `--no-build` to skip the build) and runs the e2e suite with `BC64_UPDATE_GOLDEN=1`,
so the variable is set for the e2e suite only. To regenerate one module, run it from `src/` with the variable set:

```bash
BC64_UPDATE_GOLDEN=1 python3 -m unittest tests.test_e2e_bdos
```

With `BC64_UPDATE_GOLDEN=1` the test writes the golden and passes, so read the result before
committing: `git diff` for a changed golden, or the file itself for a new one. A run with no change
writes the same bytes. Then run `python3 run_tests.py` again; it should be green.

### Masks and derived positions

A system disc's file positions (track, sector, length) change when a program changes size, so the e2e
tests do not pin them:

- `test_e2e_disc` is the only test that checks the exact track, sector and length of system-disc files,
  against `plan_disc(src/disc.bddmanifest)`.
- Every other check that needs a position or an `ls` line gets it from `plan_disc()` through the harness
  (`planned_entry`, `ls_line` in `src/tests/e2e_harness.py`). `test_e2e_bdos` (`CATALOG_LINES`),
  `test_e2e_theodore` and the harness self-tests work this way.
- `DISC_MASKS` (in `e2e_harness.py`) is applied to both sides of each comparison for bdos sessions that load
  system-disc programs: `test_e2e_bdos`, `test_e2e_disc` (`disc_ls_all`, `disc_help`), `test_e2e_texted`
  (`texted_roundtrip`) and the smoke transcript in `test_bc64_smoke`. It masks:
  - the `SIZE TT SS LL` columns of an `ls` entry line, which become the placeholder `SIZE TT SS LL`;
  - the hex sector count in `; HHHH sectors free...`, which becomes `XXXX` (the entry count stays);
  - a progress line made only of dots, which becomes `<dots>`.

Names, attributes, the order of the lines and the presence of every line are never masked, so a missing
or renamed file still fails. Goldens and `smoke_transcript.txt` are stored masked, so they never contain a
position. Marker assertions run on the raw output, so they still check real positions. The bcos, toolchain
and bdio-buffered goldens are not masked: their output does not come from a system disc.

`test_e2e_layout_shift.py` checks the claim. It builds a disc whose `HELLOWRD.PRG` is grown by 8 sectors,
which moves every later program and changes the dots of `HELLOWRD`. It then asserts that the plan really
moved, runs the `ls`, `disc_ls_all`, `hellowrd` and smoke scenarios on that disc, and compares them with the
committed goldens and transcript under `DISC_MASKS`. It also checks that the `ls` lines from the shifted plan
appear in the output. The test only compares: it never writes a golden, even with `BC64_UPDATE_GOLDEN=1`.
So a program that changes size needs no test or golden edit.

### Discs

- Monitor scenarios use `--no-floppy` and no disc.
- Shell scenarios boot a temp copy of the freshly built `src/os.bdd`. `os.bdd` is not committed, so
  build it first (`python3 run_tests.py` does, unless `--no-build`). A change in bdos or a program shows
  in the goldens.
- TextEd scenarios boot a temp copy of `src/os.bdd` in A and a temp copy of `src/utils.bdd` in B. They
  run `b:` and then `texted`, so TextEd and its files are on B.
- The toolchain scenario also boots a temp copy of `src/os.bdd`. It compares only the program
  output, the section between `A>e2eprog` and the next `A>` prompt.
- Tests that boot the real ROM without a disc are in `test_e2e_rom.py`.

### Adding a scenario

1. Write the script `src/bc64/testdata/e2e/<name>.in.txt`: one command per line. A bdos script ends
   with `exit`; the monitor stops cleanly at the end of its input. `q` ends the session with
   `fatal error F0 at FF0C` and a bcOS `KIL` (exit 0). A bad-argument command such as `d 00` ends
   it with an empty-stack `RET` stop (exit 0, a line on stderr). Scripts may use either one only as
   the last command.
2. Add a test method to the module for that area. Call `check_golden` with the marker strings the
   output must contain, e.g. `A>ls` or `Hello world!`.
3. Generate the golden with `BC64_UPDATE_GOLDEN=1 python3 -m unittest tests.<module>`, then read it.
4. Run the module again without the variable, then `python3 run_tests.py < /dev/null`.

### Known failures

Known bugs are `expectedFailure` tests, so they show as expected failures, not failures:

- `test_tape_round_trip` (`test_e2e_bcos.py`): `s` writes a tape file, but `l` reads past the end of
  the tape and the run stops with a Python `TypeError`. Issues #32 and #62.

When a fix lands, the test reports an unexpected success: remove its decorator then.

## Memory

- One flat address space with 16-bit addresses: 65,536 bytes (`0x0000`–`0xffff`). Three
  constants in `bc64.py` name it: the memory size `0x10000`, the top address `0xffff` and the
  stack top `0xfffe`.
- There is no ROM write protection. The OS image is just loaded into RAM at `0x0000`.
- At startup the CPU stack pointer `SS:SI` is `0xfffe`, and the emulator writes `0xff` (`KIL`)
  at `0xffff` after the ROM load. Jumping to `0xffff`, or running into it, halts the CPU.
- The CPU stack grows downwards from `0xfffe`. A stack instruction (`PSH`, `POP`, `CAL`, `RET`)
  that would read past the top of memory (an empty stack) or write below `0x0000` (overflow)
  stops the CPU cleanly, like `KIL`: nothing is changed, the PC stays on the instruction, and one
  line goes to stderr. The exit code is 0 and `bc64.dmp` is written.
- One device (the floppy drive) writes to and reads from memory directly (DMA). Its addresses wrap
  at `0xffff`, so a transfer past the top continues at `0x0000`.

## The bc8183 CPU

There are no interrupts. Instructions are 1–5 bytes long. The high nibble of the first byte
is the opcode. The full instruction set and its encoding are in
[02-assembler.md](02-assembler.md).

### Registers

| No. | Name | Width | Purpose |
|---|---|---|---|
| `0x1` | `A` | 8 | accumulator; all 8-bit ALU ops work on it |
| `0xB` | `F` | 8 | flags |
| `0x8` / `0x4` | `CS` / `CI` | 8 + 8 | "C segment / C index"; together the `CS:CI` pair (`csci`) |
| `0x9` / `0x5` | `DS` / `DI` | 8 + 8 | "D segment / D index"; together the `DS:DI` pair (`dsdi`) |
| `0xD` / `0xC` | `SS` / `SI` | 8 + 8 | stack pointer `SS:SI`, grows downwards |
| `0xF` | `PC` | 16 | program counter |

Memory can only be reached through a register pair, which forms the address
`hi << 8 | lo`: `CS:CI`, `DS:DI`, `SS:SI` (and `A:F` inside the CPU). The 16-bit ALU works
on the pairs `csci`, `dsdi` and `af`.

### Flags (`F`)

| Bit | Flag | Set when |
|---|---|---|
| 0 | `Z` zero | result == 0 (`Z` is 1 after reset) |
| 1 | `C` carry | result > 0xff (or > 0xffff for 16-bit ops) |
| 2 | `N` negative | bit 7 (or bit 15 for 16-bit ops) of the result |
| 3 | `O` overflow | result > max **or result < 0**. A subtraction that borrows sets `O`, not `C` |

Bits 4–7 exist but the CPU doesn't use them. `MOV` into `A` also updates `Z` and `N`.
`OUT #r, r2` sets `C`/`O` from the value it sends.

### Stack frames

The CPU stack is tagged. Each push stores a type byte next to the data:

| Operation | Bytes written (downwards from `SS:SI`) |
|---|---|
| `PSH r` | `0x10` (push frame), value: 2 bytes |
| `CAL` | `0xC0` (call frame), return-hi, return-lo: 3 bytes |

`RET` looks at the frame type on top of the stack:
- a call frame returns normally;
- if the top is **two push frames**, `RET` uses them as the return address
  (`psh hi; psh lo; ret` works as an indirect jump).

`POP` doesn't check the frame type. When the CPU throws an exception it prints the decoded
stack (`CAL addr` / `VAL value` lines).

## I/O devices

All devices sit on the I/O bus, addressed by port number with `IN`/`OUT`. The port number
always comes from a register (`out #ci, a`) or a 4-bit immediate on `IN`.

### Port 0x0: terminal keyboard

- `IN` blocks until a key is pressed and returns its ASCII code. There is no echo; bcOS
  echoes keys itself.
- `OUT` is ignored.

### Port 0x1: terminal printer

- `OUT` prints the byte as a character.
- `IN` always returns `0x40` (ready).

### Port 0x2: cassette tape recorder

The tape is a host file `<name>.btap` in the current directory, or in the `--tape-dir` folder
(see [Running it](#running-it)). The recorder asks for the name when a tape is opened: on the
console, or from the next input line in headless mode. One tape bit is stored as one byte (`0x00`/`0x01`),
LSB first, so a `.btap` file is 8× the size of its data.

Command byte written to the port. The `TX` bit `0x02` must be set; the first matching bit
wins:

| Bit | Meaning |
|---|---|
| `0x40` | open a tape for **write** (asks for the file name) |
| `0x80` | open a tape for **read** (asks for the file name) |
| `0x20` | start the motor (begin the read/write sequence) |
| `0x10` | stop and go back to ready (closes the file) |
| `0x01` | data bit (when none of the above is set): written to the tape, or a read is triggered |

Status byte read from the port:

| Bit | Meaning |
|---|---|
| `0x80` | open for read |
| `0x40` | open for write |
| `0x20` | moving |
| `0x10` | ready |
| `0x08` | error (e.g. file not found, wrong state transition) |
| `0x02` | TX: a bit is available |
| `0x01` | data bit |

While moving in read mode, every `IN` reads the next bit from the file. bcOS wraps all of
this in `tape_write8/16`, `tape_read8` and `tape_*_blk` (see [04-bcos.md](04-bcos.md)).

### Port 0x3: real-time clock

The clock uses the host's local time.

| Write | Effect |
|---|---|
| `0x01` | latch the time; the next 3 reads return hour, minute, second |
| `0x02` | latch the date; the next 3 reads return year−2000, month, day |
| `0xff` | reset to ready |

Reading in the ready state returns `0x80`. Reading in any other state returns `0xff` (error).

### Port 0x5: random number generator

- `IN` returns a random byte `0x00`–`0xff`. With `--random-seed N` the sequence is the same on every run;
  without it the sequence differs per run.
- `OUT` is ignored.

### Port 0x8: floppy disk drive (FDD v1)

There are two drives, **A** and **B**, for single-sided 3" disks. Each disk has 64 tracks ×
16 sectors × 128 bytes = **128 KB**.

Each disk is a host file `<name>.bdd`. The drive asks for the name on the console the first
time a drive is used, and creates an empty (zeroed) disk file if it doesn't exist. Sectors
are moved by **DMA**, straight between the disk file and emulator memory.

| Command (OUT) | Extra bytes | Effect | Status afterwards |
|---|---|---|---|
| `0xf0` ping | – | detect the drive | `0x11` (`READY \| FDDv1`) |
| `0xf1` configure | addr-hi, addr-lo | set the DMA address for sector transfers | `0x10` |
| `0xfa` / `0xfb` | – | make drive A / B active | `0x10` |
| `0xf2` read | track, sector | copy 128 bytes from the disk to memory at the DMA address | `0x10` or `0xe2` |
| `0xf3` write | track, sector | copy 128 bytes from memory at the DMA address to the disk | `0x10` or `0xe2` |
| `0xf4` eject | – | close the active drive's disk file (the next access asks for a name again) | – |

Status codes (read with `IN`): `0x10` ready, `0x01` FDD v1 version bit, `0xe1` drive
failure, `0xe2` read failure (also used for a track or sector out of range), `0xe3` write
failure. Software checks for errors with `status & 0xe0`.

## Known quirks

Each quirk has an issue. Where the fix is decided, a test in `src/bc64/` asserts the
correct behaviour and is marked `expectedFailure`, so it reports as an expected failure
until the fix lands. Where the behaviour is still undecided, a test pins today's behaviour
and names the issue.

- In `JRX` (`op_EXT`) the CPU checks the negation bit in the wrong nibble, so
  `jrx nz/nc/nn/no` behave like `jrx z/c/n/o`. Only `jrx z` is used anywhere, so nothing
  breaks today (#4).
- `div`/`mod` by zero raises a Python exception, which stops the emulator (#4; behaviour
  undecided, pinned by a test).
- `FloppyDriveV1.write_byte` sets `self.setate` (a typo) on an unknown command, so the
  failure state is never actually set (#4).
