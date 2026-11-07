# BC64 documentation

BC64 is an imaginary 8-bit computer that exists only as an emulator, with its own complete
software stack, all in this repository. The pages below describe the current `bc64` branch.

| Page | Covers |
|---|---|
| [01-emulator.md](01-emulator.md) | the Python emulator, the bc8183 CPU (registers, flags, stack frames) and the emulated devices: keyboard, printer, tape recorder, clock, random generator, floppy drives |
| [02-assembler.md](02-assembler.md) | `bc81asmc`: assembly syntax, directives, full instruction set with encodings, `.btap` output |
| [03-compiler.md](03-compiler.md) | `bc`: the B language (types, operators, statements, functions), preprocessor, code generation model, libraries |
| [04-bcos.md](04-bcos.md) | bcOS 1.2 ROM monitor: boot, command line, tape format, `os_metacall` system call table |
| [05-bdos.md](05-bdos.md) | bdos 1.1: boot loader, memory map, BFS disk format, bdio API, shell, disc utilities, building `os.bdd` |

## How the pieces fit

```
  B source (.b) ──bc──► .basm ──bc81asmc──► .btap ──ftool──► .b81 ROM / disk sectors
                                                               │
  bc64.py emulator ◄── bcOS ROM at 0x0000 ──boots──► bdos from os.bdd ──runs──► .PRG at 0x6000
```

Quick start, from `src/` (needs Python 3 and `pip install parsy`):

```bash
python bc64.py bc81asmc/bcOS/bcos_v1_2_0.b81    # at the "Disk A name:" prompt enter: os.bdd
```
