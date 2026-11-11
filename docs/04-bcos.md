# bcOS: the ROM operating system

bcOS is the "ROM" monitor the BC64 starts from. It is written in assembly
(`src/bc81asmc/bcOS/bcos.basm`, about 1.6k lines), is loaded at `0x0000`, and is about
3.4 KB. The current version is **1.2** (`bcos.basm` header: 1.2.20241102), built for the
bc8183 CPU.

| File | Contents |
|---|---|
| `bcos.basm` | source |
| `bcos.btap` | assembled tape image (build output, ignored by git) |
| `bcos_v1_2_0.b81` | raw ROM image used by `./run`; the only ROM committed. The older ROMs are gone from the tree (the bc32 ROM, v1.1.1, ships in the `bc32-v1.0` release zip) |
| `bcos.md` | short feature notes, command list and error codes |

To build: `./buildos` from `src/` assembles bcOS, converts it with
`ftool btap2bin` → `bcos_v1_2_0.b81`, and then builds the bdos boot loader and shell.

## Version history

| Version | Changes |
|---|---|
| 1.0 (BC16) | tape-only monitor |
| 1.1 (BC32) | more library routines (some moved in from the B compiler stdlib); detects the floppy drive at boot and starts bdos from it |
| 1.2 (BC64) | uses the bc8183 16-bit instructions. The software `inc16/dec16/add16/sub16/mul16/div16` routines are removed; their table slots now point to `os12_comperror` (fatal error `0xce`) |

## Boot sequence

1. Jump from `0x0000` to `os_init`.
2. Save `SS:SI` as `var_top_mem` and the end of the bcOS image (`user_mem`) as
   `var_user_mem`. Together these give the free RAM range.
3. Print `bcOS 1.2`.
4. **Floppy check:** send ping `0xf0` to port `0x08`. If the status has the READY bit
   (`0x10`):
   1. print `booting from FDD`;
   2. select drive A (`0xfa`);
   3. set DMA to `0x0e00`;
   4. read **track 0, sector 0** (the bdos boot sector);
   5. jump to `0x0e00`. See [05-bdos.md](05-bdos.md).

   If any of these steps returns an error status (`0xeX`), bcOS prints the error and falls
   back to its own prompt.
5. Without a floppy (or after a failed boot): print `free XXXX from YYYY to ZZZZ`, then
   `type h for help`, then the `> ` prompt.

## Command line

The input buffer `var_promptbuf` holds up to 32 characters. Only the **first letter** of a
line selects the command. Addresses and lengths are **exactly 4 hex digits** (`h4`).

| Command | Effect |
|---|---|
| `d addr len` | hex dump of `len` bytes from `addr`, 16 bytes per line |
| `p addr len` | print `len` bytes from `addr` as characters |
| `w addr` | type text lines and store them in memory from `addr`; an empty line stops (prints the address of each line) |
| `x addr` | same as `w`, but you type hex bytes (`h2`) |
| `s addr len name.ext` | save the memory block to tape (asks for the tape file name) |
| `l [addr]` | load a file from tape, to `addr` or to the address stored in the file |
| `r addr` | run code at `addr` as a subroutine (`cal`); the program ends with `ret` |
| `e addr` | jump to `addr` (`jmp`); the program jumps back to `os_prompt`/`os_parse`, or to `0x0000` to reset |
| `h` | help |
| `q` | quit: fatal `0xf0`, CPU halts, emulator dumps memory |

Example session: `s 1000 1000 filename.txt` saves 4 KB from `0x1000`.

## Tape file format

What `s` writes and `l` reads, before the tape's one-byte-per-bit encoding:

```
00 FF 00 FF   BC 05   addr-hi addr-lo   len-hi len-lo   00   file name (13 bytes, 0-padded)
<len bytes of data>
```

`l` checks the preamble (`load error bad preamble`) and the data (`load error bad data`).
The assembler's `.btap` output has the same format, so assembled programs can be loaded
with `l`.

## System call interface (`os_metacall`)

Programs don't call bcOS routines at fixed addresses. They go through a jump table, which
keeps them working across OS versions:

```asm
                mov a, 0x02          ; function number (here: PRINTSTR)
                psh a
                pop f                ; the function number goes in F
                .mv dsdi, :message   ; arguments as the routine expects
                cal :os_metacall     ; os_metacall lives at 0x0008
```

`os_call` saves `A`, `CS:CI`, `DS:DI` and `F`, and looks up `os_metatab[F]`. It writes the
target address into a 4-byte self-modifying trampoline in RAM
(`var_oscall: cal hhll / ret`), restores the registers and calls the trampoline. Arguments
and results pass through unchanged. `F` is overwritten by almost every instruction, so load
it just before the call.

### Memory layout

| Address | Contents |
|---|---|
| `0x0000` | `os_start`: jump to `os_init` |
| `0x0008` | `os_metacall` (the entry point for system calls) |
| `0x000c` | `os_metatab`: 56 × 2-byte addresses |
| `0x007a` | table entry `0x37`, the `bdio_call` slot that bdos fills in |
| after the table | `os_vartab`: pointers to `var_param16`, `var_user_mem`, `var_top_mem`, `var_promptbuf`, `var_oscall`, `var_oscalladdr`, `user_mem` |
| … | strings, routines, variables |
| ~`0x0d6b` | `user_mem`: end of the image, start of free RAM |

### Function table

Register notation: `csci`/`dsdi` are 16-bit pairs, and `#dsdi` means "the buffer at
`dsdi`". Routines that return a status put `0` in `A` on success.

| # | Routine | In → Out |
|---|---|---|
| `00` | `print_newline` | prints LF CR |
| `01` | `print_space` | prints a space |
| `02` | `printstr` | `dsdi` = 0-terminated string |
| `03` | `printhex4` | `a` = 0..f |
| `04` | `printhex8` | `a` = byte |
| `05` | `printhex16` | `csci` = word |
| `06`, `07` | *(removed: inc16, dec16)* | → `os12_comperror` |
| `08` | `setvarparam16` | `csci` → `var_param16` |
| `09` | `poke16` | mem[`dsdi`] = `csci` (big-endian); `dsdi` += 1 |
| `0a` | `peek16` | `csci` = mem[`dsdi`]; `dsdi` += 1 |
| `0b`, `0c` | *(removed: add16, sub16)* | → `os12_comperror` |
| `0d` | `readstr` | `dsdi` = buffer, `ci` = size; reads a line with echo |
| `0e` / `0f` / `10` | `parsehex4` / `parsehex8` / `parsehex16` | `#dsdi` → `ci` / `ci` / `csci`; `a` = 0 if ok; `dsdi` moves past the digits |
| `11` | `upchar` | `a` → upper-case `a` |
| `12` | `nextword` | moves `dsdi` to the next word; `a` > 0 if one exists |
| `13` | `nextval8` | scans `dsdi` for the value `ci`, at most `cs` bytes |
| `14` | `fatal` | `a` = code; prints `fatal error XX at addr` and halts |
| `15` | `error` | `a` = code; prints `error XX` and continues |
| `16` | `print_format` | `a` = byte; printed as hex or as a character depending on `var_param16` |
| `17` | `str_cpy` | copy the string at `dsdi` to `csci` |
| `18` | `str_len8` | `ci` = length of `#dsdi` (at most `cs`) |
| `19` | `tape_check` | `ci` = expected recorder state, `dsdi` = error message |
| `1a` / `1b` | `tape_write8` / `tape_read8` | the byte is in `ci` |
| `1c` | `tape_write16` | `csci` |
| `1d` / `1e` | `tape_write_blk` / `tape_read_blk` | `dsdi` = memory, `csci` = length |
| `1f`, `20` | *(removed: mul16, div16)* | → `os12_comperror` |
| `21` / `22` / `23` | `gt16` / `gteq16` / `eq16` | `a` = 1 if `csci` > / >= / == `dsdi` (unsigned) |
| `24`–`2a` | `exec_dump`, `exec_write`, `exec_xwrite`, `exec_save`, `exec_load`, `exec_run`, `exec_exe` | the command-line commands; `dsdi` = argument buffer |
| `2b` | `os_boot` | re-run the floppy boot check |
| `2c` | `os_init` | cold start |
| `2d` | `os_hello_nxt` | print free memory and go back to the bcOS prompt (bdos `bcos` uses this) |
| `2e` / `2f` | `os_prompt` / `os_parse` | prompt loop entry points |
| `30` | `os_end` | fatal `0xff` |
| `31` | `mfill` | fill memory |
| `32` | `mem_xcpy` | copy memory |
| `33` | `strncpy` | copy a string with a length limit |
| `34`–`36` | *(empty)* | |
| `37` | **`bdio_call`** | written here by bdos at start-up (address `0x007a`) so that user programs can reach bdos through the same mechanism |

### System variables

| Variable | Meaning |
|---|---|
| `var_param16` | 2-byte parameter for `print_format`/`exec_dump` (0 = hex, 1 = characters) |
| `var_user_mem` | first free byte after bcOS |
| `var_top_mem` | `SS:SI` at boot (top of usable RAM) |
| `var_promptbuf` | 33-byte command line buffer |
| `var_oscall`, `var_oscalladdr` | the `os_call` trampoline |

## Error codes

| Code | Meaning |
|---|---|
| `01` | unrecognized command |
| `02` / `04` / `07` | argument 1 / 2 / 3 missing |
| `03` / `05` | failed to parse argument 1 / 2 as 4-digit hex |
| `06` | failed to parse a 2-digit hex value (`x`) |
| `10`–`13` | overflow in inc16/dec16/add16/sub16 (legacy) |
| `ce` | compatibility error: a routine removed in 1.2 was called |
| `eX` | floppy drive errors (passed through from the drive status) |
| `f0` | user quit (`q`) |
| `ff` | unexpected system exception |

## Known quirks

- The command dispatch for `s`, `l`, `r` and `e` uses `.mv dsci, :var_promptbuf` (sets
  `DS` and `CI`) where `dsdi` was probably meant. It works because `DS:DI` still points at
  the buffer from `readstr`.
