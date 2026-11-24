"""The bc8183 instruction set: the single source of its encoding.

Every number that encodes a bc8183 instruction is written here and nowhere else: register
numbers, condition codes and the flag bits they test, the 16 opcode nibbles, the mode bits and
sub-opcodes, the 8-bit and 16-bit ALU operation numbers, the CPU stack-frame tags and the KIL
byte. The CPU (src/bc64/bc8183_cpu.py), the emulator (src/bc64.py) and the assembler
(src/bc81asmc/) import these names; they never write an opcode value themselves.

`FORMS` describes every instruction form (one record per mnemonic and operand form) with its
opcode nibble, length and nibble layout, so a disassembler can decode with it (#178).

The module is plain data: it imports nothing from the tools and has no side effects.
"""
from dataclasses import dataclass

# ---------------------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------------------
REG_A = 0x1
REG_CI = 0x4
REG_DI = 0x5
REG_CS = 0x8
REG_DS = 0x9
REG_F = 0xB
REG_SI = 0xC
REG_SS = 0xD
REG_PC = 0xF

# Register name -> number, in the order the assembler grammar tries the names.
REGISTERS = {
    'pc': REG_PC,
    'ss': REG_SS,
    'si': REG_SI,
    'f': REG_F,
    'a': REG_A,
    'ci': REG_CI,
    'cs': REG_CS,
    'di': REG_DI,
    'ds': REG_DS,
}
REGISTER_NAMES = tuple(REGISTERS)
REGISTER_NAMES_BY_NUMBER = {number: name for name, number in REGISTERS.items()}

# Register pairs: name -> (high register, low register). A pair is encoded as the number of
# its high register (`csci` -> CS); the CPU forms the address `hi << 8 | lo`.
PAIRS = {
    'csci': (REG_CS, REG_CI),
    'dsdi': (REG_DS, REG_DI),
    'sssi': (REG_SS, REG_SI),
    'af': (REG_A, REG_F),
}
PAIR_NAMES = tuple(PAIRS)
PAIR_REGISTER = {name: regs[0] for name, regs in PAIRS.items()}
PAIR_LOW_REGISTER = {regs[0]: regs[1] for regs in PAIRS.values()}
# Either register of a pair selects that pair for a memory address (CPU `get_addr`).
ADDRESS_PAIR = {reg: regs for regs in PAIRS.values() for reg in regs}

# Pairs the assembler accepts for memory access (`mov r, #pair`) and for `clr pair`.
MEMORY_PAIR_NAMES = ('csci', 'dsdi', 'sssi')
# Pairs of the assembler's 16-bit ALU, with the implied second pair of the register form.
ALU16_PAIR_NAMES = ('csci', 'dsdi')
ALU16_IMPLIED_PAIR_NAME = {'csci': 'dsdi', 'dsdi': 'csci'}
# The second pair the CPU derives from the first one in the 16-bit register form.
ALU16_IMPLIED_PAIR = {REG_CS: REG_DS, REG_DS: REG_CS, REG_A: REG_CS}

# ---------------------------------------------------------------------------------------
# Flags and condition codes
# ---------------------------------------------------------------------------------------
FLAG_ZERO = 0x0
FLAG_CARRY = 0x1
FLAG_NEGATIVE = 0x2
FLAG_OVERFLOW = 0x3

COND_FLAG_MASK = 0x3    # the flag bit a condition tests
COND_NEGATE = 0x4       # the condition is true when the flag is clear

COND_Z = FLAG_ZERO
COND_C = FLAG_CARRY
COND_N = FLAG_NEGATIVE
COND_O = FLAG_OVERFLOW
COND_NZ = COND_NEGATE | FLAG_ZERO
COND_NC = COND_NEGATE | FLAG_CARRY
COND_NN = COND_NEGATE | FLAG_NEGATIVE
COND_NO = COND_NEGATE | FLAG_OVERFLOW

CONDITIONS = {
    'z': COND_Z,
    'c': COND_C,
    'n': COND_N,
    'o': COND_O,
    'nz': COND_NZ,
    'nc': COND_NC,
    'nn': COND_NN,
    'no': COND_NO,
}
# The grammar tries these in order: a name never comes after a shorter name that is its prefix.
CONDITION_NAMES = ('nz', 'z', 'nc', 'c', 'nn', 'o', 'no', 'n')
CONDITION_NAMES_BY_CODE = {code: name for name, code in CONDITIONS.items()}

# ---------------------------------------------------------------------------------------
# Opcodes: the high nibble of the first byte
# ---------------------------------------------------------------------------------------
OP_NOP = 0x0
OP_MOV_IMM = 0x1        # mov r, 0xHH
OP_MOV_REG = 0x2        # mov r1, r2
OP_MOV_REG_MEM = 0x3    # mov r, #pair
OP_MOV_MEM_REG = 0x4    # mov #pair, r
OP_CLC = 0x5            # 8-bit and 16-bit ALU
OP_JMP = 0x6
OP_JMR = 0x7
OP_PSH = 0x8
OP_POP = 0x9
OP_CAL = 0xA            # cal and clr
OP_RET = 0xB
OP_IN = 0xC
OP_OUT = 0xD
OP_EXT = 0xE            # bc8183 extension: jrx
OP_KIL = 0xF

# Opcode nibble -> group name; the CPU's handler for nibble n is `op_<OPCODE_NAMES[n]>`.
OPCODE_NAMES = {
    OP_NOP: 'NOP',
    OP_MOV_IMM: 'MOV_imm',
    OP_MOV_REG: 'MOV_reg',
    OP_MOV_REG_MEM: 'MOV_reg_mem',
    OP_MOV_MEM_REG: 'MOV_mem_reg',
    OP_CLC: 'CLC',
    OP_JMP: 'JMP',
    OP_JMR: 'JMR',
    OP_PSH: 'PSH',
    OP_POP: 'POP',
    OP_CAL: 'CAL',
    OP_RET: 'RET',
    OP_IN: 'IN',
    OP_OUT: 'OUT',
    OP_EXT: 'EXT',
    OP_KIL: 'KIL',
}

# ---------------------------------------------------------------------------------------
# Mode bits and sub-opcodes (the low nibble of the first byte, unless noted)
# ---------------------------------------------------------------------------------------
CLC_REGISTER_FORM = 0x8     # 58 ro: A = A op reg[r]
CLC_EXT = 0xF               # 5F: the 16-bit ALU
JMP_SHORT = 0x8             # 6(t+8) ll: jump to CS:ll
JMR_REGISTER = 0x8          # 7(t+8) r0: relative jump by reg[r]
JRX_REGISTER_MARK = 0x8     # E2 (t+8)p: set in the condition nibble of the register form
CAL_DIRECT = 0x8            # A8 hh ll: absolute address follows
CAL_RELATIVE = 0x1          # A1 / A9: clr, the address is a 15-bit sign-magnitude offset
CLR_DIRECT = CAL_DIRECT | CAL_RELATIVE
IN_REGISTER = 0x8           # C8 r r2: port in a register
OUT_REGISTER = 0x8          # D8 r r2: port and value in registers
OUT_PORT_MASK = 0x7         # Dr HH: the port register is a 3-bit field (a, ci or di)
EXT_JRX_ADDR = 0x1          # E1 t0 hh ll
EXT_JRX_REG = 0x2           # E2 (t+8)p
EXT_SUBOPS = (EXT_JRX_ADDR, EXT_JRX_REG)

# ---------------------------------------------------------------------------------------
# 8-bit ALU: operation numbers (CLC low nibble, or the low nibble of byte 2 in 58 ro)
# ---------------------------------------------------------------------------------------
ALU_ADD = 0x0
ALU_SUB = 0x1
ALU_AND = 0x2
ALU_OR = 0x3
ALU_XOR = 0x4
ALU_SHL = 0x5
ALU_SHR = 0x6
ALU_NOT = 0x7
ALU_INC = 0xD
ALU_DEC = 0xE

ALU8_OPS = {
    'add': ALU_ADD,
    'sub': ALU_SUB,
    'and': ALU_AND,
    'or': ALU_OR,
    'xor': ALU_XOR,
    'shl': ALU_SHL,
    'shr': ALU_SHR,
    'not': ALU_NOT,
    'inc': ALU_INC,
    'dec': ALU_DEC,
}
# Ops with an immediate (5o ii) and a register form (58 ro), in grammar order.
ALU8_BINARY_OP_NAMES = ('add', 'sub', 'and', 'or', 'xor', 'shl', 'shr')
# One-byte ops on A: `not a`, `inc a`, `dec a`.
ALU8_UNARY_OP_NAMES = ('not', 'inc', 'dec')
# The CPU-only short register alias 5(o|8) r0 exists for these ops only (E15).
ALU8_SHORT_ALIAS_OP_NAMES = ('sub', 'and', 'or', 'xor')

# ---------------------------------------------------------------------------------------
# 16-bit ALU (5F kk ...): group nibble + operation nibble
# ---------------------------------------------------------------------------------------
ALU16_GROUP_ARITH = 0xA
ALU16_GROUP_BINARY = 0xB
ALU16_REGISTER_FORM = 0x8   # set in the operation nibble: 5F k8 pq

ALU16_MUL = 0x2
ALU16_DIV = 0x3
ALU16_MOD = 0x4

# name -> (group, op)
ALU16_OPS = {
    'add': (ALU16_GROUP_ARITH, ALU_ADD),
    'sub': (ALU16_GROUP_ARITH, ALU_SUB),
    'mul': (ALU16_GROUP_ARITH, ALU16_MUL),
    'div': (ALU16_GROUP_ARITH, ALU16_DIV),
    'mod': (ALU16_GROUP_ARITH, ALU16_MOD),
    'inc': (ALU16_GROUP_ARITH, ALU_INC),
    'dec': (ALU16_GROUP_ARITH, ALU_DEC),
    'and': (ALU16_GROUP_BINARY, ALU_AND),
    'or': (ALU16_GROUP_BINARY, ALU_OR),
    'xor': (ALU16_GROUP_BINARY, ALU_XOR),
    'shl': (ALU16_GROUP_BINARY, ALU_SHL),
    'shr': (ALU16_GROUP_BINARY, ALU_SHR),
    'not': (ALU16_GROUP_BINARY, ALU_NOT),
}
# Ops with a register form 5F k8 pq and an immediate form, in grammar order.
ALU16_BINARY_OP_NAMES = ('add', 'sub', 'mul', 'div', 'mod', 'and', 'or', 'xor', 'shl', 'shr')
# Ops whose immediate is one byte, encoded as the 16-bit value 00 ii.
ALU16_SHIFT_OP_NAMES = ('shl', 'shr')
# One-pair ops: 5F kk p0.
ALU16_UNARY_OP_NAMES = ('inc', 'dec', 'not')


def alu16_code(group, op):
    """The CPU's combined dispatch key of a 16-bit op: group << 4 | op."""
    return group << 4 | op


ALU16_CODES = {name: alu16_code(group, op) for name, (group, op) in ALU16_OPS.items()}

# ---------------------------------------------------------------------------------------
# CPU stack-frame tags and KIL
# ---------------------------------------------------------------------------------------
STACKFRAME_PUSH = 0x10      # psh: tag + value (2 bytes)
STACKFRAME_CALL = 0xC0      # cal/clr: tag + return address (3 bytes)

KIL_BYTE = OP_KIL << 4                  # F0: what `kil` assembles to
TOP_OF_MEMORY_KIL = OP_KIL << 4 | 0xF   # FF: KIL with every low bit set, written at 0xffff

# ---------------------------------------------------------------------------------------
# Instruction forms
# ---------------------------------------------------------------------------------------
# A form's `layout` has one character per nibble and a space between bytes:
#   0-9 A-F  a fixed nibble
#   r        a register number              s  the second register number
#   p        a pair (its high register)     q  the second pair (its high register)
#   w        the low register of the pair named by p (clr pair)
#   t        a condition code (bit 3 clear) T  a condition code with bit 3 set (t+8)
#   u        a register number 0-7 (bit 3 clear: out #r, 0xHH)
#   x        a 4-bit port number            i  an 8-bit immediate
#   h l      high and low byte of a 16-bit immediate, address or 15-bit offset
#   d        a 7-bit sign-magnitude displacement (jmr t, :label)
# `encoding` is the same form in the notation of the docs' Encoding column.
LAYOUT_FIELDS = 'rspqwtTuxihld'
# Fields that fix bit 3 of their nibble: field -> (mask, value).
LAYOUT_FIXED_BITS = {'t': (0x8, 0x0), 'T': (0x8, 0x8), 'u': (0x8, 0x0)}

# Operand forms: 'a' (the accumulator), 'reg', 'pair', '#pair', '#reg', '#imm4', 'imm8',
# 'imm16', 'cond', 'label'.


@dataclass(frozen=True)
class InstructionForm:
    key: str            # unique, e.g. 'add.imm8', 'add16.reg', 'jmp.label'
    mnemonic: str
    operands: tuple     # operand forms
    syntax: str         # as written in the docs, e.g. 'mov r, #pair'
    opcode: int         # the high nibble of the first byte
    length: int         # bytes
    layout: str         # nibble layout, see above
    encoding: str       # the docs' Encoding column
    emitted: bool = True  # False: the CPU decodes it, the assembler never emits it

    @property
    def nibbles(self):
        """The layout as one character per nibble (spaces removed)."""
        return self.layout.replace(' ', '')

    @property
    def fixed(self):
        """(nibble index, mask, value) for every fixed nibble or fixed bit of the layout."""
        result = []
        for index, char in enumerate(self.nibbles):
            if char in LAYOUT_FIXED_BITS:
                mask, value = LAYOUT_FIXED_BITS[char]
                result.append((index, mask, value))
            elif char not in LAYOUT_FIELDS:
                result.append((index, 0xF, int(char, 16)))
        return tuple(result)


def _hex(n):
    return '{0:X}'.format(n)


def _form(key, mnemonic, operands, syntax, opcode, layout, encoding, emitted=True):
    return InstructionForm(key, mnemonic, tuple(operands), syntax, opcode,
                           len(layout.split(' ')), layout, encoding, emitted)


def _build_forms():
    clc = _hex(OP_CLC)
    ext = _hex(CLC_EXT)
    forms = [
        # data movement
        _form('nop', 'nop', (), 'nop', OP_NOP, _hex(OP_NOP) + '0', '00'),
        _form('mov.imm8', 'mov', ('reg', 'imm8'), 'mov r, 0xHH', OP_MOV_IMM,
              _hex(OP_MOV_IMM) + 'r ii', '1r ii'),
        _form('mov.reg', 'mov', ('reg', 'reg'), 'mov r1, r2', OP_MOV_REG,
              _hex(OP_MOV_REG) + 'r s0', '2r1 r20'),
        _form('mov.reg_mem', 'mov', ('reg', '#pair'), 'mov r, #pair', OP_MOV_REG_MEM,
              _hex(OP_MOV_REG_MEM) + 'r p0', '3r p0'),
        _form('mov.mem_reg', 'mov', ('#pair', 'reg'), 'mov #pair, r', OP_MOV_MEM_REG,
              _hex(OP_MOV_MEM_REG) + 'p r0', '4p r0'),
        _form('psh', 'psh', ('reg',), 'psh r', OP_PSH, _hex(OP_PSH) + 'r', '8r'),
        _form('pop', 'pop', ('reg',), 'pop r', OP_POP, _hex(OP_POP) + 'r', '9r'),
    ]
    # 8-bit ALU
    for name in ALU8_BINARY_OP_NAMES:
        op = ALU8_OPS[name]
        forms.append(_form(name + '.imm8', name, ('imm8',), name + ' 0xHH', OP_CLC,
                           clc + _hex(op) + ' ii', '5o ii'))
        forms.append(_form(name + '.reg', name, ('reg',), name + ' r', OP_CLC,
                           clc + _hex(CLC_REGISTER_FORM) + ' r' + _hex(op), '58 ro'))
    for name in ALU8_UNARY_OP_NAMES:
        forms.append(_form(name, name, ('a',), name + ' a', OP_CLC,
                           clc + _hex(ALU8_OPS[name]), clc + _hex(ALU8_OPS[name])))
    for name in ALU8_SHORT_ALIAS_OP_NAMES:
        forms.append(_form(name + '.reg_short', name, ('reg',), name + ' r', OP_CLC,
                           clc + _hex(ALU8_OPS[name] | CLC_REGISTER_FORM) + ' r0',
                           '5(o|8) r0', emitted=False))
    # 16-bit ALU
    for name in ALU16_BINARY_OP_NAMES:
        group, op = ALU16_OPS[name]
        if name in ALU16_SHIFT_OP_NAMES:
            forms.append(_form(name + '16.imm8', name, ('pair', 'imm8'), name + ' pair, 0xHH',
                               OP_CLC, clc + ext + ' ' + _hex(group) + _hex(op) + ' p0 00 ii',
                               '5F kk p0 00 ii'))
        else:
            forms.append(_form(name + '16.imm16', name, ('pair', 'imm16'),
                               name + ' pair, 0xHHHH', OP_CLC,
                               clc + ext + ' ' + _hex(group) + _hex(op) + ' p0 hh ll',
                               '5F kk p0 hh ll'))
        forms.append(_form(name + '16.reg', name, ('pair', 'pair'), name + ' pair, pair2',
                           OP_CLC,
                           clc + ext + ' ' + _hex(group) + _hex(op | ALU16_REGISTER_FORM) + ' pq',
                           '5F k8 pq'))
    for name in ALU16_UNARY_OP_NAMES:
        group, op = ALU16_OPS[name]
        forms.append(_form(name + '16', name, ('pair',), name + ' pair', OP_CLC,
                           clc + ext + ' ' + _hex(group) + _hex(op) + ' p0', '5F kk p0'))
    # jumps and calls
    forms += [
        _form('jmp.pair', 'jmp', ('cond', 'pair'), 'jmp t, pair', OP_JMP,
              _hex(OP_JMP) + 't 0p', '6t 0p'),
        _form('jmp.label', 'jmp', ('cond', 'label'), 'jmp t, :label', OP_JMP,
              _hex(OP_JMP) + 'T ll', '6(t+8) ll'),
        _form('jmr.label', 'jmr', ('cond', 'label'), 'jmr t, :label', OP_JMR,
              _hex(OP_JMR) + 't dd', '7t dd'),
        _form('jmr.reg', 'jmr', ('cond', 'reg'), 'jmr t, r', OP_JMR,
              _hex(OP_JMR) + 'T r0', '7(t+8) r0'),
        _form('jrx.label', 'jrx', ('cond', 'label'), 'jrx t, :label', OP_EXT,
              _hex(OP_EXT) + _hex(EXT_JRX_ADDR) + ' t0 hh ll', 'E1 t0 hh ll'),
        _form('jrx.pair', 'jrx', ('cond', 'pair'), 'jrx t, pair', OP_EXT,
              _hex(OP_EXT) + _hex(EXT_JRX_REG) + ' Tp', 'E2 (t+8)p'),
        _form('cal.label', 'cal', ('label',), 'cal :label', OP_CAL,
              _hex(OP_CAL) + _hex(CAL_DIRECT) + ' hh ll', 'A8 hh ll'),
        _form('cal.pair', 'cal', ('pair',), 'cal pair', OP_CAL,
              _hex(OP_CAL) + '0 p0', 'A0 p0'),
        _form('clr.label', 'clr', ('label',), 'clr :label', OP_CAL,
              _hex(OP_CAL) + _hex(CLR_DIRECT) + ' hh ll', 'A9 hh ll'),
        _form('clr.pair', 'clr', ('pair',), 'clr pair', OP_CAL,
              _hex(OP_CAL) + _hex(CAL_RELATIVE) + ' pw', 'A1 pq'),
        _form('ret', 'ret', (), 'ret', OP_RET, _hex(OP_RET) + '0', 'B0'),
        _form('kil', 'kil', (), 'kil', OP_KIL, '{0:02X}'.format(KIL_BYTE), 'F0'),
        # I/O
        _form('in.imm4', 'in', ('reg', '#imm4'), 'in r, #0xH', OP_IN,
              _hex(OP_IN) + '0 rx', 'C0 rH'),
        _form('in.reg', 'in', ('reg', '#reg'), 'in r, #r2', OP_IN,
              _hex(OP_IN) + _hex(IN_REGISTER) + ' rs', 'C8 r r2'),
        _form('out.reg', 'out', ('#reg', 'reg'), 'out #r, r2', OP_OUT,
              _hex(OP_OUT) + _hex(OUT_REGISTER) + ' rs', 'D8 r r2'),
        _form('out.imm8', 'out', ('#reg', 'imm8'), 'out #r, 0xHH', OP_OUT,
              _hex(OP_OUT) + 'u ii', 'Dr HH'),
    ]
    return tuple(forms)


FORMS = _build_forms()
FORMS_BY_KEY = {form.key: form for form in FORMS}
