# bcOS (ROM monitor)

Reference: `doc/04-bcos.md` has the boot sequence, commands and the full `os_metatab`
table. `bcos.md` holds the short notes and error codes.

## Build (from `src/`)

```bash
python3 bc81asmc/bc81asmc.py --verbose bc81asmc/bcOS/bcos.basm             # -> bcos.btap
python3 ftool.py btap2bin bc81asmc/bcOS/bcos.btap bc81asmc/bcOS/bcos_v1_2_0.b81
# or ./buildos, which also rebuilds the bdos boot loader and shell
```

`bcos_v1_2_0.b81` is the ROM image that `./run` uses. `bcos_v1_1_*.b81` are older builds;
keep them.

## Rules

- **`os_metatab` indices are an ABI.** The compiler runtime (`src/bc/bc_stdlib.py`), bdos
  (`bdosh.b` slot `0x37`; `bdos.b` `eject()` uses `0x2d`), the boot loader (`0x02`, `0x2e`) and the
  apps call by index.
  - Never reorder or remove entries. Append new ones in the free slots `0x34–0x36` or after
    `0x37`.
  - Point retired routines at `os12_comperror`.
  - Keep the `; #NN:` comment above each routine equal to its real table index.
- Slot `0x37` (`0x007a`) must stay empty in the ROM, because bdos writes `bdio_call` there.
  The fixed addresses `os_metacall = 0x0008` and `os_metatab = 0x000c` are hard-coded in
  `boot.basm` and `bdosh.b`, so code in front of them must not change size.
- Each routine's header comment lists its IN/OUT registers. Callers rely on which
  registers are preserved, so update the header when the register use changes.
- The image ends at `user_mem` (about `0x0d6b`). bdos variables start at `0x0d80`, so
  bcOS can grow only by about 20 bytes before bdos addresses have to move.
- The boot sequence (`os_init` → `os_boot`) loads track 0 sector 0 to `bdos_bootaddr`
  (`0x0e00`). That must match `.org` in `src/bdos/boot.basm`.
- The file has CRLF line endings. After an edit that should only touch comments, check that
  the output is unchanged: assemble before and after, then `cmp` the two `.btap` files.
- There is no "always" condition: unconditional jumps are `xor a` followed by `jmp z, …` or
  `jmr z, …`. Long jumps are `.mv csci, :label` + `xor a` + `jmp z, csci`.
