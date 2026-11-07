# bc81asmc: assembler for the bc8183 CPU

`src/bc81asmc/` is a two-pass assembler written with the
[parsy](https://pypi.org/project/parsy/) parser-combinator library. The current version is
**v1.3 (240914)**, for the bc8183 CPU described in [01-emulator.md](01-emulator.md).

| File | Contents |
|---|---|
| `bc81asmc.py` | CLI, the two passes (emit + label fix-ups), `.btap` writer |
| `bc81asmc_grammar.py` | the parsy grammar (the real syntax reference) |
| `bc81asmc_ast.py` | one dataclass per instruction/directive, each with its own `emit()`; opcode constants |
| `bc81asmc_tests.py` | unit tests (need `parsy`) |
| `grammar.txt` | early informal grammar sketch |
| `examples/` | `hello.basm`, `first.basm` |
| `bcOS/` | the bcOS source, see [04-bcos.md](04-bcos.md) |

## Usage

```bash
pip install parsy
python bc81asmc/bc81asmc.py [--verbose] path/to/file.basm
```

- The output is always `path/to/file.btap`, a tape image. The `--btap` flag is accepted but
  has no effect.
- `--verbose` prints every line with its address in pass 1, plus the relative-jump
  fix-ups.
- To get a raw binary (ROM image or disk sectors), run `./ftool btap2bin file.btap file.bin`.

### `.btap` output format

The file holds a 24-byte preamble followed by the code, **one byte per bit, LSB first**
(the format the tape recorder uses):

```
00 ff 00 ff  bc 05  ADDR-hi ADDR-lo  LEN-hi LEN-lo  00  name[13, zero padded]
```

`ADDR` is the `.org` address and `name` is the source file name without its extension.

## Source syntax

```
label:   mnemonic operands   ; comment
```

- **Mnemonics and register names must be lowercase.**
- A label is an identifier followed by `:` at the start of a line. To refer to a label,
  prefix it with a colon: `:label`.
- Immediates are **hex only** and the digit count is fixed:
  - `0xHH`: 8-bit
  - `0xHHHH`: 16-bit
  - `#0xH`: 4-bit (only as the `IN` port)
- Strings use single quotes: `'text'`. There are no escapes.
- `;` starts a comment, which can sit on its own line or after an instruction.
- Every line, including the last, must end with a newline.
- Registers: `a f ci cs di ds si ss pc`. Pairs: `csci dsdi sssi` (memory addressing) and
  `csci dsdi af` (16-bit ALU).

### Directives

| Directive | Effect |
|---|---|
| `.org 0xHHHH` | set the load/start address. Use it once at the top: code is emitted contiguously, so a second `.org` only shifts addresses |
| `.db v, v, …` | emit bytes. Each `v` is `0xHH`, `'string'` (raw chars, add `0x00` yourself) or `:label` (2 bytes, big-endian address) |
| `.mv pair, :label` | load a 16-bit label address into a pair. Expands to `mov hi,imm8` + `mov lo,imm8` (4 bytes) |
| `.def name, 0xHHHH` | define a constant, used like a label (`:name`). Good for fixed addresses such as `bdos_bootaddr` |

### How the two passes work

Pass 1 emits code and writes placeholder bytes (`0xfa`) wherever a label address is needed.
Pass 2 patches the placeholders with the high byte, low byte, 7-bit relative or 15-bit
relative value. If a `jmr` target is more than ±127 bytes away, or a `jrx`/`clr` target is
more than ±32767 bytes away, the assembler raises an error.

Relative offsets are stored as **sign-magnitude**: bit 7 (or bit 15) is the sign and the
other bits are the magnitude. They are not two's complement.

## Instruction set

Condition codes `t` for `jmp`/`jmr`/`jrx`:

| `z` | `c` | `n` | `o` | `nz` | `nc` | `nn` | `no` |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |

They test zero, carry, negative and overflow (or their negation). There is no "always"
condition. Unconditional jumps are written as `xor a` followed by `jmp z, …` or `jmr z, …`.

The encoding column uses nibbles: `r`/`p` is a register number, `t` a condition code,
`ii` an 8-bit immediate and `hhll` a 16-bit immediate.

### Data movement

| Syntax | Encoding | Bytes | Effect |
|---|---|---|---|
| `nop` | `00` | 1 | nothing |
| `mov r, 0xHH` | `1r ii` | 2 | r = imm8 |
| `mov r1, r2` | `2r1 r20` | 2 | r1 = r2 |
| `mov r, #pair` | `3r p0` | 2 | r = mem[pair] |
| `mov #pair, r` | `4p r0` | 2 | mem[pair] = r |
| `psh r` | `8r` | 1 | push r (2-byte tagged frame) |
| `pop r` | `9r` | 1 | pop into r |

### 8-bit ALU (always on `A`)

| Syntax | Encoding | Bytes | Effect |
|---|---|---|---|
| `add 0xHH` / `sub` / `and` / `or` / `xor` / `shl` / `shr` | `5o ii` (o = 0…6) | 2 | A = A op imm |
| `add r` / `sub r` / … / `shr r` | `58 ro` | 2 | A = A op r |
| `not a` | `57` | 1 | A = ~A |
| `inc a` | `5D` | 1 | A = A + 1 |
| `dec a` | `5E` | 1 | A = A − 1 |

Operation numbers `o`: add 0, sub 1, and 2, or 3, xor 4, shl 5, shr 6. `xor a` is the usual
way to clear `A` and set `Z`.

### 16-bit ALU (bc8183 extension, on `csci`, `dsdi` or `af`)

| Syntax | Encoding | Bytes |
|---|---|---|
| `add pair, 0xHHHH` (`sub mul div mod and or xor`) | `5F kk p0 hh ll` | 5 |
| `shl pair, 0xHH` / `shr pair, 0xHH` | `5F kk p0 00 ii` | 5 |
| `add pair, pair2` (same set plus `shl`/`shr`) | `5F k8 pq` | 3 |
| `inc pair` / `dec pair` / `not pair` | `5F kk p0` | 3 |

`kk` is a group nibble followed by an operation nibble:
- **arithmetic group `A`**: add 0, sub 1, mul 2, div 3 (integer), mod 4, inc D, dec E
- **binary group `B`**: and 2, or 3, xor 4, shl 5, shr 6, not 7

The register form sets bit 3 of the operation nibble.

Results are truncated to 16 bits and set `Z/N/C/O` from the 16-bit value.

> **In the register form the CPU ignores the written second operand and picks it from the
> first one:** `csci` always combines with `dsdi`, while `dsdi` and `af` combine with
> `csci`. So `add csci, dsdi` and `sub dsdi, csci` do what they say, but `add csci, af`
> actually adds `dsdi`.

### Jumps and calls

| Syntax | Encoding | Bytes | Effect |
|---|---|---|---|
| `jmp t, pair` | `6t 0p` | 2 | if t: PC = pair |
| `jmp t, :label` | `6(t+8) ll` | 2 | if t: PC = `CS:ll`. Only the low byte is encoded, so `CS` must already hold the target's high byte |
| `jmr t, :label` | `7t dd` | 2 | if t: relative jump, 7-bit sign-magnitude |
| `jmr t, r` | `7(t+8) r0` | 2 | if t: relative jump by the value in r |
| `jrx t, :label` | `E1 t0 hh ll` | 4 | if t: relative jump, 15-bit sign-magnitude (bc8183) |
| `jrx t, pair` | `E2 (t+8)p` | 2 | if t: relative jump by the pair value |
| `cal :label` | `A8 hh ll` | 3 | call an absolute address |
| `cal pair` | `A0 p0` | 2 | call the address in the pair |
| `clr :label` | `A9 hh ll` | 3 | relative call, 15-bit sign-magnitude (bc8183) |
| `clr pair` | `A1 pq` | 2 | relative call by the pair value |
| `ret` | `B0` | 1 | return (see the stack frames section in [01-emulator.md](01-emulator.md)) |
| `kil` | `F0` | 1 | halt the CPU (the emulator then dumps memory) |

The usual long-jump idiom is `.mv csci, :target` then `xor a` then `jmp z, csci`.

### I/O

| Syntax | Encoding | Bytes | Effect |
|---|---|---|---|
| `in r, #0xH` | `C0 rH` | 2 | r = port H |
| `in r, #r2` | `C8 r r2` | 2 | r = port[r2] |
| `out #r, r2` | `D8 r r2` | 2 | port[r] = r2 |
| `out #r, 0xHH` | `D0 rH` (emitted) | 2 | **broken**: the CPU expects `Dr HH` (port register in the low nibble, full 8-bit value), so it reads the port from register 0, which doesn't exist, and the assembler keeps only the low 4 bits of the value. Unused; always load the value into a register first (#11) |

## Example

```asm
                .org 0x0000
start:          .mv dsdi, :msg
                mov ci, 0x01        ; printer port
loop:           mov a, #dsdi
                jmr z, :done
                out #ci, a
                inc dsdi
                xor a
                jmr z, :loop
done:           kil
msg:            .db 'Hello!', 0x0a, 0x0d, 0x00
```

## Known quirks

- `out #r, imm` and `jrx` with a negated condition don't work (see above and
  [01-emulator.md](01-emulator.md)).
- `CLC_A_IMM` has a leftover branch for 16-bit opcodes that the grammar never reaches.
