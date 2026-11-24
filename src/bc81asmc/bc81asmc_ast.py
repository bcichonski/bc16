from dataclasses import dataclass

import os
import sys

# The assembler runs with src/bc81asmc/ first on sys.path: append the parent src/ folder (never
# insert it at the front) so that the shared ISA table is found.
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.append(_SRC)

import bc8183_isa as isa


class Bc8183:
    """The assembler's view of the ISA: every attribute is a reference to bc8183_isa."""
    A = isa.REG_A
    CI = isa.REG_CI
    DI = isa.REG_DI
    CS = isa.REG_CS
    DS = isa.REG_DS
    F = isa.REG_F
    SI = isa.REG_SI
    SS = isa.REG_SS
    PC = isa.REG_PC

    CLC_ADD = isa.ALU_ADD
    CLC_SUB = isa.ALU_SUB
    CLC_AND = isa.ALU_AND
    CLC_OR  = isa.ALU_OR
    CLC_XOR = isa.ALU_XOR
    CLC_SHL = isa.ALU_SHL
    CLC_SHR = isa.ALU_SHR
    CLC_NOT = isa.ALU_NOT
    CLC_OP_RNO = isa.CLC_REGISTER_FORM
    CLC_INC = isa.ALU_INC
    CLC_DEC = isa.ALU_DEC
    CLC_EXT = isa.CLC_EXT

    CAL_EX_RNO = isa.CAL_RELATIVE
    CAL_EX_I16 = isa.CLR_DIRECT

    CLC_EXT_AR  = isa.ALU16_GROUP_ARITH
    CLC_EXT_BIN = isa.ALU16_GROUP_BINARY

    CLC_EXT_AR_RNO = isa.ALU16_REGISTER_FORM

    NOP     = isa.OP_NOP
    MOVRI8  = isa.OP_MOV_IMM
    MOVRR   = isa.OP_MOV_REG
    MOVRM   = isa.OP_MOV_REG_MEM
    MOVMR   = isa.OP_MOV_MEM_REG
    CLC     = isa.OP_CLC
    JMP     = isa.OP_JMP
    JMR     = isa.OP_JMR
    PSH     = isa.OP_PSH
    POP     = isa.OP_POP
    CAL     = isa.OP_CAL
    RET     = isa.OP_RET
    IN      = isa.OP_IN
    OUT     = isa.OP_OUT
    EXT     = isa.OP_EXT
    KIL     = isa.OP_KIL

    EXT_JRX_ADR = isa.EXT_JRX_ADDR
    EXT_JRX_REG = isa.EXT_JRX_REG

    CLC_ADD16 = isa.ALU16_OPS['add'][1]
    CLC_SUN16 = isa.ALU16_OPS['sub'][1]
    CLC_MUL16 = isa.ALU16_MUL
    CLC_DIV16 = isa.ALU16_DIV
    CLC_MOD16 = isa.ALU16_MOD
    CLC_INC16 = isa.ALU16_OPS['inc'][1]
    CLC_DEC16 = isa.ALU16_OPS['dec'][1]
    CLC_AND16 = isa.ALU16_OPS['and'][1]
    CLC_OR16  = isa.ALU16_OPS['or'][1]
    CLC_XOR16 = isa.ALU16_OPS['xor'][1]
    CLC_SHL16 = isa.ALU16_OPS['shl'][1]
    CLC_SHR16 = isa.ALU16_OPS['shr'][1]
    CLC_NOT16 = isa.ALU16_OPS['not'][1]

    def __init__(self):
        # register and pair names; a pair is its high register, `af` is a (see the CPU)
        self.registers_bin = dict(isa.REGISTERS)
        for name in isa.ALU16_PAIR_NAMES:
            self.registers_bin[name] = isa.PAIR_REGISTER[name]
        self.registers_bin['af'] = isa.PAIR_REGISTER['af']

        self.registers_str = dict(isa.REGISTER_NAMES_BY_NUMBER)

        self.oper_opcodes = {name: isa.ALU8_OPS[name] for name in isa.ALU8_BINARY_OP_NAMES}

        self.test_opcodes = dict(isa.CONDITIONS)

        self.oper_subcodes = {name: group for name, (group, op) in isa.ALU16_OPS.items()}

        self.oper16_opcodes = {name: op for name, (group, op) in isa.ALU16_OPS.items()}

    def REG2BIN(self, reg : str):
        return self.registers_bin[reg.lower()]

    def BIN2REG(self, reg : int):
        return self.registers_str[reg]

    def OPER2OPCODE(self, oper):
        if oper.endswith("16"):
            return Bc8183.CLC_EXT
        return self.oper_opcodes[oper]
    
    def OPER2SUBCODE(self, oper):
        return (self.oper_subcodes[oper], self.oper16_opcodes[oper])

    def TEST2OPCODE(self, test):
        return self.test_opcodes[test]

ASMCODES = Bc8183()

class LabelName(str):
    """A label name without its colon; `line`/`col` of the reference are kept when known."""
    line = 0
    col = 0

def label_name(ref):
    name = LabelName(ref[1:])
    name.line = getattr(ref, 'line', 0)
    name.col = getattr(ref, 'col', 0)
    return name

class CodeContext:
    def __init__(self):
        self.bytes = bytearray()
        self.startaddr = 0
        self.currbyte = None
        self.currhalf = 0
        self.curraddr = 0
        self.errors = []
        self.labels = []
        self.defs = {}
    def emit_byte(self, b):
        self.bytes.extend([b])
        self.currbyte = None
        self.currhalf = 0
        self.curraddr += 1
    def emit_byte_at(self, addr, b):
        self.bytes[addr-self.startaddr] = b
    def hi(self, b):
        return (b >> 8) & 0xff
    def lo(self, b):
        return b & 0xff
    def emit_4bit(self, bit4):
        if(self.currhalf == 0):
            self.currbyte = (bit4 & 0xf) << 4
            self.currhalf = 1
        else:
            byte = self.currbyte | (bit4 & 0xf)
            self.emit_byte(byte)
    def set_addr(self, addr):
        self.startaddr = addr
        self.curraddr = addr
    def add_error(self, message):
        self.errors.extend(message)
    def _emit_addr(self, label, type):
        if(self.currhalf == 1):
            raise Exception('cannot calculate label address if byte was halfly emitted')
        self.labels.append(tuple((self.curraddr,label,type)))
        self.emit_byte(0xfa)
        if(type == 'rel15'):
            self.emit_byte(0xfa)
    def emit_lo8addr(self, label):
        self._emit_addr(label, 'lo')
    def emit_hi8addr(self, label):
        self._emit_addr(label, 'hi')
    def emit_rel8addr(self, label):
        self._emit_addr(label, 'lorel')
    def emit_rel15addr(self, label):
        self._emit_addr(label, 'rel15')
    def set_const(self, label, value):
        self.defs[label] = value
    def emit_16bit(self, value):
        self.emit_byte(value >> 8)
        self.emit_byte(value & 0xff)

class Token:
    def __str__(self):
        return "token";
    def emit(self, context):
        pass
    def set_label(self, label):
        self.label = label
        self.label_col = getattr(label, 'col', None)
    def set_comment(self, comment):
        self.comment = comment

@dataclass
class LineComment(Token):
    comment:str
    def __str__(self):
       return self.comment;

class LabelOnly(Token):
    '''A line holding only a label (and maybe a comment): emits no bytes.'''
    def __str__(self):
        return "(label only)"
    def __eq__(self, other):
        return isinstance(other, LabelOnly)
    __hash__ = None

class ImmediateValue(Token):
    def __str__(self):
        return "imm";

@dataclass
class Value4(ImmediateValue):
    value : int
    def __str__(self):
        return "imm4({0:1x})".format(self.value)
    def emit(self, context):
        context.emit_4bit(self.value)

@dataclass
class Value8(ImmediateValue):
    value : int
    def __str__(self):
        return "imm8({0:2x})".format(self.value)
    def emit(self, context):
        context.emit_byte(self.value)

@dataclass
class Value16(ImmediateValue):
    value : int
    def __str__(self):
        return "imm16({0:04x})".format(self.value)
    def emit(self, context):
        context.emit_byte((self.value >> 8) & 0xff)
        context.emit_byte(self.value & 0xff)

class Instruction(Token):
    def __str__(self):
        return "instruction";
    def emit(self, context):
        self.addr = context.curraddr

@dataclass
class NOP(Instruction):
    _ : str
    def __str__(self):
        return "NOP";
    def emit(self, context):
        super().emit(context)
        context.emit_byte(ASMCODES.NOP);

@dataclass
class KIL(Instruction):
    _ : str
    def __str__(self):
        return "KIL";
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.KIL);
        context.emit_4bit(0);

@dataclass
class INC(Instruction):
    _ : str
    def __str__(self):
        return "INC a";
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC);
        context.emit_4bit(ASMCODES.CLC_INC);

# 16-bit register pairs and the implied second pair the CPU derives (bc8183_cpu.py)
PAIR16_IMPLIED = dict(isa.ALU16_IMPLIED_PAIR_NAME)

def check_pair16(reg, reg2=None):
    """Validate the pair operand(s) of a 16-bit instruction before anything is emitted."""
    if reg.lower() not in PAIR16_IMPLIED:
        raise ValueError("'{0}' is not a 16-bit pair (use csci or dsdi)".format(reg))
    if reg2 is not None:
        if reg2.lower() not in PAIR16_IMPLIED:
            raise ValueError("'{0}' is not a 16-bit pair (use csci or dsdi)".format(reg2))
        implied = PAIR16_IMPLIED[reg.lower()]
        if reg2.lower() != implied:
            raise ValueError("second operand must be {0} when the first is {1}".format(implied, reg.lower()))

def reject_af_alu(reg, mnemonic):
    """`af` is not a pair for the 16-bit ALU: the result would overwrite the flags in f (#66)."""
    if reg.lower() == 'af':
        raise ValueError("{0} af is not allowed: the 16-bit result would overwrite the flags in f "
                         "(use a pair csci or dsdi)".format(mnemonic))

def reject_af_incdec(reg, mnemonic):
    if reg.lower() == 'af':
        raise ValueError("{0} af is not allowed: the 16-bit result would overwrite the flags in f "
                         "(use {0} a, or a pair csci or dsdi)".format(mnemonic))

CLR_PAIRS = isa.MEMORY_PAIR_NAMES

def check_clr_pair(arg):
    """Validate the register operand of `clr` before anything is emitted (#67)."""
    if arg.lower() == 'af':
        raise ValueError("clr af is not allowed: the call offset would be read from a:f, "
                         "and f holds the flags (use a pair csci, dsdi or sssi)")
    if arg.lower() not in CLR_PAIRS:
        raise ValueError("'{0}' is not a pair for clr (use csci, dsdi or sssi)".format(arg))

@dataclass
class INC16(Instruction):
    reg : str
    def __str__(self):
        return "INC16 {0}".format(self.reg.upper());
    def emit(self, context):
        reject_af_incdec(self.reg, 'inc')
        check_pair16(self.reg)
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)
        context.emit_4bit(ASMCODES.CLC_EXT)
        context.emit_4bit(ASMCODES.CLC_EXT_AR)
        context.emit_4bit(ASMCODES.CLC_INC16)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))
        context.emit_4bit(0)

@dataclass
class DEC(Instruction):
    _ : str
    def __str__(self):
        return "DEC a";
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC);
        context.emit_4bit(ASMCODES.CLC_DEC);

@dataclass
class DEC16(Instruction):
    reg : str
    def __str__(self):
        return "DEC16 {0}".format(self.reg.upper());
    def emit(self, context):
        reject_af_incdec(self.reg, 'dec')
        check_pair16(self.reg)
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)
        context.emit_4bit(ASMCODES.CLC_EXT)
        context.emit_4bit(ASMCODES.CLC_EXT_AR)
        context.emit_4bit(ASMCODES.CLC_DEC16)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))
        context.emit_4bit(0)

@dataclass
class MOVRI8(Instruction):
    reg : str
    i8  : int
    def __str__(self):
        return "MOV {0}, 0x{1:02x}".format(self.reg, self.i8);
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.MOVRI8)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))
        context.emit_byte(self.i8)

@dataclass
class MOVRR(Instruction):
    reg1 : str
    reg2 : str
    def __str__(self):
        return "MOV {0}, {1}".format(self.reg1, self.reg2);
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.MOVRR)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg1))
        context.emit_4bit(ASMCODES.REG2BIN(self.reg2))
        context.emit_4bit(0);

def check_regs(regs, context):
    if regs != 'csci' and regs != 'dsdi' \
       and regs != 'sssi':
       context.add_error("{0} unsupported, only #csci, #dsdi or #sssi is allowed")
    if regs == 'csci':
        val = ASMCODES.CS
    elif regs == 'dsdi':
        val = ASMCODES.DS
    elif regs == 'sssi':
        val = ASMCODES.SS
    else:
        raise ValueError('Value {} unsupported'.format(regs))
    return val

@dataclass
class MOVRM(Instruction):
    reg1 : str
    regs2 : str
    def __str__(self):
        return "MOV {0}, #{1}".format(self.reg1, self.regs2);
    def emit(self, context):
        super().emit(context)
        val = check_regs(self.regs2, context)
        context.emit_4bit(ASMCODES.MOVRM)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg1))
        context.emit_4bit(val)
        context.emit_4bit(0);

@dataclass
class MOVMR(Instruction):
    regs1 : str
    reg2 : str
    def __str__(self):
        return "MOV #{0}, {1}".format(self.regs1, self.reg2);
    def emit(self, context):
        super().emit(context)
        val = check_regs(self.regs1, context)
        context.emit_4bit(ASMCODES.MOVMR)
        context.emit_4bit(val)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg2))
        context.emit_4bit(0);

@dataclass
class CLC_A_IMM(Instruction):
    oper : str
    imm : str
    def __str__(self):
        return "{0: <3} 0x{1:04x}".format(self.oper.upper(), self.imm)
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)
        opcode = ASMCODES.OPER2OPCODE(self.oper)
        context.emit_4bit(opcode)
        if opcode == ASMCODES.CLC_EXT:
            print("{0} {1} {2}".format(self.oper.upper(), self.imm[0], self.imm[1]))
            (kind, subcode) = ASMCODES.OPER2SUBCODE(self.oper)
            context.emit_4bit(kind)
            context.emit_4bit(subcode)
            context.emit_4bit(ASMCODES.REG2BIN(self.imm[0]))
            context.emit_16bit(self.imm[1])
        else:
            context.emit_byte(self.imm)

@dataclass
class CLC_A_R(Instruction):
    oper : str
    reg : str
    def __str__(self):
        return "{0: <3} {1}".format(self.oper.upper(), self.reg)
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)
        context.emit_4bit(ASMCODES.CLC_OP_RNO)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))
        context.emit_4bit(ASMCODES.OPER2OPCODE(self.oper))

@dataclass
class CLC16_R_IMM(Instruction):
    oper : str
    reg : str
    imm : list
    def __str__(self):
        return "{0: <3}16 {2}, 0x{1:04x}".format(self.oper.upper(), self.imm, self.reg)
    def emit(self, context):
        reject_af_alu(self.reg, self.oper.lower())
        check_pair16(self.reg)
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)  
        context.emit_4bit(ASMCODES.CLC_EXT)
        (kind, subcode) = ASMCODES.OPER2SUBCODE(self.oper)
        context.emit_4bit(kind)
        context.emit_4bit(subcode)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))
        context.emit_4bit(0)
        context.emit_16bit(self.imm)


@dataclass
class CLC16_R_R(Instruction):
    oper : str
    reg : str
    reg2 : str
    def __str__(self):
        return "{0: <3}16 {1}, {2}".format(self.oper.upper(), self.reg, self.reg2)
    def emit(self, context):
        reject_af_alu(self.reg, self.oper.lower())
        check_pair16(self.reg, self.reg2)
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)
        context.emit_4bit(ASMCODES.CLC_EXT)
        (kind, subcode) = ASMCODES.OPER2SUBCODE(self.oper)
        context.emit_4bit(kind)
        context.emit_4bit(subcode | ASMCODES.CLC_EXT_AR_RNO)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))
        context.emit_4bit(ASMCODES.REG2BIN(self.reg2))

@dataclass
class JMP(Instruction):
    test : str
    arg : str
    def __str__(self):
        return "JMP {0}, {1}".format(self.test.upper(), self.arg.upper())
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.JMP)

        if(self.arg.startswith(':')):
            context.emit_4bit(ASMCODES.TEST2OPCODE(self.test) | ASMCODES.CLC_OP_RNO)
            context.emit_lo8addr(label_name(self.arg))
        else:
            context.emit_4bit(ASMCODES.TEST2OPCODE(self.test))
            context.emit_4bit(0)
            context.emit_4bit(ASMCODES.REG2BIN(self.arg[0:2]))

@dataclass
class JMR(Instruction):
    test : str
    arg : str
    def __str__(self):
        return "JMR {0}, {1}".format(self.test.upper(), self.arg.upper())
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.JMR)

        if(self.arg.startswith(':')):
            context.emit_4bit(ASMCODES.TEST2OPCODE(self.test))
            context.emit_rel8addr(label_name(self.arg))
        else:
            context.emit_4bit(ASMCODES.TEST2OPCODE(self.test) | ASMCODES.CLC_OP_RNO)
            context.emit_4bit(ASMCODES.REG2BIN(self.arg[0:2]))
            context.emit_4bit(0)

@dataclass
class JRX(Instruction):
    test : str
    arg : str
    def __str__(self):
        return "JRX {0}, {1}".format(self.test.upper(), self.arg.upper())
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.EXT)

        if(self.arg.startswith(':')):
            context.emit_4bit(ASMCODES.EXT_JRX_ADR)
            context.emit_4bit(ASMCODES.TEST2OPCODE(self.test))
            context.emit_4bit(0)
            context.emit_rel15addr(label_name(self.arg))
        else:
            context.emit_4bit(ASMCODES.EXT_JRX_REG)
            context.emit_4bit(ASMCODES.TEST2OPCODE(self.test) | ASMCODES.CLC_OP_RNO)
            context.emit_4bit(ASMCODES.REG2BIN(self.arg[0:2]))

@dataclass
class NOT(Instruction):
    _ : str
    def __str__(self):
        return "NOT A"
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)
        context.emit_4bit(ASMCODES.CLC_NOT)

@dataclass
class NOT16(Instruction):
    reg : str
    def __str__(self):
        return "NOT16 {0}".format(self.reg.upper())
    def emit(self, context):
        reject_af_alu(self.reg, 'not')
        check_pair16(self.reg)
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)
        context.emit_4bit(ASMCODES.CLC_EXT)
        context.emit_4bit(ASMCODES.CLC_EXT_BIN)
        context.emit_4bit(ASMCODES.CLC_NOT16)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))
        context.emit_4bit(0)

@dataclass
class PSH(Instruction):
    reg : str
    def __str__(self):
        return 'PSH {0}'.format(self.reg.upper())
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.PSH)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))

@dataclass
class POP(Instruction):
    reg : str
    def __str__(self):
        return 'POP {0}'.format(self.reg.upper())
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.POP)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))

@dataclass
class CAL(Instruction):
    arg : str
    def __str__(self):
        return 'CAL {0}'.format(self.arg.upper())
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CAL)
        if(self.arg.startswith(':')):
            context.emit_4bit(ASMCODES.CLC_OP_RNO)
            context.emit_hi8addr(label_name(self.arg))
            context.emit_lo8addr(label_name(self.arg))
        else:
            context.emit_4bit(0)
            context.emit_4bit(ASMCODES.REG2BIN(self.arg[0:2]))
            context.emit_4bit(0)

@dataclass
class CLR(Instruction):
    arg : str
    def __str__(self):
        return 'CLR {0}'.format(self.arg.upper())
    def emit(self, context):
        if not self.arg.startswith(':'):
            check_clr_pair(self.arg)
        super().emit(context)
        context.emit_4bit(ASMCODES.CAL)
        if(self.arg.startswith(':')):
            context.emit_4bit(ASMCODES.CAL_EX_I16)
            context.emit_rel15addr(label_name(self.arg))
        else:
            context.emit_4bit(ASMCODES.CAL_EX_RNO)
            context.emit_4bit(ASMCODES.REG2BIN(self.arg[0:2]))
            context.emit_4bit(ASMCODES.REG2BIN(self.arg[2:4]))
        
@dataclass
class RET(Instruction):
    _ : str
    def __str__(self):
        return 'RET'
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.RET)
        context.emit_4bit(0)

@dataclass
class IN(Instruction):
    reg : str
    arg : str
    def __str__(self):
        return "IN {0}, #{1}".format(self.reg.upper(), self.arg)
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.IN)

        if(isinstance(self.arg, str)):
            context.emit_4bit(ASMCODES.CLC_OP_RNO)
            context.emit_4bit(ASMCODES.REG2BIN(self.reg))
            context.emit_4bit(ASMCODES.REG2BIN(self.arg))
        else:
            context.emit_4bit(0)
            context.emit_4bit(ASMCODES.REG2BIN(self.reg))
            context.emit_4bit(self.arg)

@dataclass
class OUT(Instruction):
    reg : str
    arg : str
    def __str__(self):
        return "OUT #{0}, {1}".format(self.reg.upper(), self.arg.upper())
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.OUT)

        if(isinstance(self.arg, str)):
            context.emit_4bit(ASMCODES.CLC_OP_RNO)
            context.emit_4bit(ASMCODES.REG2BIN(self.reg))
            context.emit_4bit(ASMCODES.REG2BIN(self.arg))
        else:
            # out #r, 0xHH -> D r HH: the port register number is a nibble, the value a full byte
            port = ASMCODES.REG2BIN(self.reg)
            if port > isa.OUT_PORT_MASK:
                raise ValueError("out #{0}, 0xHH takes the port in a, ci or di; "
                                 "load the value into a register and use out #{0}, <reg>".format(self.reg.lower()))
            context.emit_4bit(port)
            context.emit_byte(self.arg)

class Directive(Token):
    def __str__(self):
        return "directive";

@dataclass
class ORG(Directive):
    value : int
    def __str__(self):
        return ".ORG 0x{0:04x}".format(self.value);
    def emit(self, context):
        context.set_addr(self.value)

@dataclass
class DB(Directive):
    values : list
    def __str__(self):
        return ".DB {0}".format(", ".join(map(lambda x: str(x), self.values)));
    def emit(self, context):
        for val in self.values:
            if isinstance(val, str):
                if val.startswith(":"):
                    context.emit_hi8addr(label_name(val))
                    context.emit_lo8addr(label_name(val))
                else:
                    for char in val:
                        context.emit_byte(ord(char))
            else: context.emit_byte(val)

@dataclass
class MV(Directive):
    regs : str
    lbl : str
    def __str__(self):
        return ".MV {0}, {1} ;{2}".format(self.regs.upper(), self.lbl, getattr(self, 'comment', ''))
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.MOVRI8)
        context.emit_4bit(ASMCODES.REG2BIN(self.regs[0:2]))
        context.emit_hi8addr(label_name(self.lbl))
        context.emit_4bit(ASMCODES.MOVRI8)
        context.emit_4bit(ASMCODES.REG2BIN(self.regs[2:]))
        context.emit_lo8addr(label_name(self.lbl))

@dataclass
class DEF(Directive):
    lbl : str
    value : int
    def __str__(self):
        return ".DEF {0}, 0x{1:04x} ;{2}".format(self.lbl.upper(), self.value, getattr(self, 'comment', ''))
    def emit(self, context):
        super().emit(context)
        context.set_const(self.lbl, self.value)
        

@dataclass
class ASSERT(Directive):
    left : str
    op : str
    right : str
    def __str__(self):
        return ".ASSERT {0} {1} {2}".format(self.left, self.op, self.right)
    # emits nothing: evaluated by compile() in pass 2

def LINE(label, token, comment):
    if label:
        token.set_label(label)
    if comment:
        token.set_comment(comment)
    return token

def LABEL_ONLY(label, comment):
    return LINE(label, LabelOnly(), comment)

def DEBUG(*args):
    i = 0
    for a in args:
       print("arg{}={}".format(i,a))
       i += 1
