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

Older generations are frozen in `release/bc16_v1.0` (bc8181/8182 CPU, 16 KB, tape only) and
`release/bc32_v1.0` (bc8182 CPU, 32 KB, adds clock, random generator and floppy drive).

## Running it

From `src/`:

```bash
python bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81        # normal run (this is what ./run does)
python bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81 d      # any 2nd argument turns on CPU trace
```

- The first argument is a **raw binary ROM image**. It is loaded at address `0x0000`, and
  execution starts there. A `.b81` image is made from an assembler `.btap` file with
  `./ftool btap2bin <in.btap> <out.b81>`.
- With trace on, the CPU appends the registers after every instruction to `cpudebug.log` in
  the current directory. This file grows very large very fast.
- When the CPU halts (`KIL`), the whole memory is written to `bc64.dmp`.
- Keyboard input reads one character at a time with no echo (`msvcrt.getch` on Windows,
  `termios` raw mode elsewhere). Printer output goes to stdout.
- The repo's shell scripts call `winpty python …`, because they were written for Git Bash on
  Windows. On Linux or macOS, call `python` directly.

## Memory

- One flat address space with 16-bit addresses. `TOPMEM = 0xffff`, so the bytearray holds
  65535 bytes (addresses `0x0000`–`0xfffe`).
- There is no ROM write protection. The OS image is just loaded into RAM at `0x0000`.
- At startup the CPU stack pointer `SS:SI` is `0xfffe`, and the emulator writes `0xff` at
  `0xfffe`.
- One device (the floppy drive) writes to and reads from memory directly (DMA).

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

The tape is a host file `<name>.btap` in the current directory. The recorder asks for the
name on the console when a tape is opened. One tape bit is stored as one byte (`0x00`/`0x01`),
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

- `IN` returns a random byte `0x00`–`0xff`.
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

Each quirk has an issue. Where the fix is decided, a test in `src/tests/` asserts the
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
- The emulator memory is `TOPMEM = 0xffff` bytes, not 64 KB, so `0xffff` is not addressable
  (#7).
