from dataclasses import dataclass

#from bc16_cpu.py
class Bc8183:
    A = 0x1
    CI = 0x4
    DI = 0x5
    CS = 0x8
    DS = 0x9
    F = 0xB
    SI = 0xC
    SS = 0xD
    PC = 0xF

    CLC_ADD = 0x0
    CLC_SUB = 0x1
    CLC_AND = 0x2
    CLC_OR  = 0x3
    CLC_XOR = 0x4
    CLC_SHL = 0x5
    CLC_SHR = 0x6
    CLC_NOT = 0x7
    CLC_OP_RNO = 0x8
    CLC_INC = 0xD
    CLC_DEC = 0xE
    CLC_EXT = 0xF
    
    CAL_EX_RNO = 0x1
    CAL_EX_I16 = 0x9

    CLC_EXT_AR  = 0x0a
    CLC_EXT_BIN = 0x0b

    NOP     = 0x0
    MOVRI8  = 0x1
    MOVRR   = 0x2
    MOVRM   = 0x3
    MOVMR   = 0x4
    CLC     = 0x5
    JMP     = 0x6
    JMR     = 0x7
    PSH     = 0x8
    POP     = 0x9
    CAL     = 0xa
    RET     = 0xb
    IN      = 0xc
    OUT     = 0xd
    KIL     = 0xf

    TEST_Z  = 0x0
    TEST_NZ = 0x4
    TEST_CY = 0x1
    TEST_NC = 0x5
    TEST_NG = 0x2
    TEST_NN = 0x6
    TEST_OF = 0x3
    TEST_NO = 0x7

    CLC_ADD16 = 0x0,
    CLC_SUN16 = 0x1,
    CLC_MUL16 = 0x2,
    CLC_DIV16 = 0x3,
    CLC_MOD16 = 0x4,
    CLC_INC16 = 0xd,
    CLC_DEC16 = 0xe,
    CLC_AND16 = 0x2,
    CLC_OR16  = 0x3,
    CLC_XOR16 = 0x4,
    CLC_SHL16 = 0x5,
    CLC_SHR16 = 0x6,
    CLC_NOT16 = 0x7,

    def __init__(self):
        self.registers_bin = {
          'pc' : Bc8183.PC,
          'ss' : Bc8183.SS,
          'si' : Bc8183.SI,
          'f'  : Bc8183.F,
          'a'  : Bc8183.A,
          'ci' : Bc8183.CI,
          'cs' : Bc8183.CS,
          'di' : Bc8183.DI,
          'ds' : Bc8183.DS,
          'af' : Bc8183.A,
          'csci' : Bc8183.CS,
          'dsdi' : Bc8183.DS
        }

        self.registers_str = {
          Bc8183.PC : 'pc',
          Bc8183.SS : 'ss',
          Bc8183.SI : 'si',
          Bc8183.F  : 'f',
          Bc8183.A  : 'a',
          Bc8183.CI : 'ci',
          Bc8183.CS : 'cs',
          Bc8183.DI : 'di',
          Bc8183.DS : 'ds',
        }

        self.oper_opcodes = {
          'add' : Bc8183.CLC_ADD,
          'sub' : Bc8183.CLC_SUB,
          'and' : Bc8183.CLC_AND,
          'or'  : Bc8183.CLC_OR,
          'xor' : Bc8183.CLC_XOR,
          'shl' : Bc8183.CLC_SHL,
          'shr' : Bc8183.CLC_SHR
        }

        self.test_opcodes = {
          'z' : Bc8183.TEST_Z,
          'nz': Bc8183.TEST_NZ,
          'c': Bc8183.TEST_CY,
          'nc': Bc8183.TEST_NC,
          'n': Bc8183.TEST_NG,
          'nn': Bc8183.TEST_NN,
          'o': Bc8183.TEST_OF,
          'no': Bc8183.TEST_NO
        }

        self.oper_subcodes = {
            'add' : Bc8183.CLC_EXT_AR,
            'sub' : Bc8183.CLC_EXT_AR,
            'mul' : Bc8183.CLC_EXT_AR,
            'div' : Bc8183.CLC_EXT_AR,
            'mod' : Bc8183.CLC_EXT_AR,
            'inc' : Bc8183.CLC_EXT_AR,
            'dec' : Bc8183.CLC_EXT_AR,
            'and' : Bc8183.CLC_EXT_BIN,
            'or' : Bc8183.CLC_EXT_BIN,
            'xor' : Bc8183.CLC_EXT_BIN,
            'shl' : Bc8183.CLC_EXT_BIN,
            'shr' : Bc8183.CLC_EXT_BIN,
            'not' : Bc8183.CLC_EXT_BIN,
        }

        self.oper16_opcodes = {
            'add' : Bc8183.CLC_ADD16,
            'sub' : Bc8183.CLC_SUN16,
            'mul' : Bc8183.CLC_MUL16,
            'div' : Bc8183.CLC_DIV16,
            'mod' : Bc8183.CLC_MOD16,
            'inc' : Bc8183.CLC_INC16,
            'dec' : Bc8183.CLC_DEC16,
            'and' : Bc8183.CLC_AND16,
            'or' : Bc8183.CLC_OR16,
            'xor' : Bc8183.CLC_XOR16,
            'shl' : Bc8183.CLC_SHL16,
            'shr' : Bc8183.CLC_SHR16,
            'not' : Bc8183.CLC_NOT16,
        }

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
    def set_comment(self, comment):
        self.comment = comment

@dataclass
class LineComment(Token):
    comment:str
    def __str__(self):
       return self.comment;

class ImmediateValue(Token):
    def __str__(self):
        return "imm";

@dataclass
class Value4(ImmediateValue):
    value : int
    def __str__(self):
        return "imm4({0:1x})".format(self.value)
    def emit(self, context):
        context.emit_4bit(value)

@dataclass
class Value8(ImmediateValue):
    value : int
    def __str__(self):
        return "imm8({0:2x})".format(self.value)
    def emit(self, context):
        context.emit_byte(value)

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

@dataclass
class INC16(Instruction):
    reg : str
    def __str__(self):
        return "INC16 {0}".format(self.reg.upper());
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)
        context.emit_4bit(ASMCODES.CLC_EXT)
        context.emit_4bit(ASMCODES.CLC_EXT_AR)
        context.emit_4bit(ASMCODES.CLC_INC16)
        context.emit_4bit(0)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))

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
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)
        context.emit_4bit(ASMCODES.CLC_EXT)
        context.emit_4bit(ASMCODES.CLC_EXT_AR)
        context.emit_4bit(ASMCODES.CLC_DEC16)
        context.emit_4bit(0)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))

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
            context.emit_16bit(imm[1])
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
        return "{0: <3} {2}, 0x{1:04x}".format(self.oper.upper(), self.imm, self.reg)
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)  
        context.emit_4bit(Bc8183.CLC_EXT)
        (kind, subcode) = ASMCODES.OPER2SUBCODE(self.oper)
        context.emit_4bit(kind)
        context.emit_4bit(subcode)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))
        context.emit_16bit(self.imm)


@dataclass
class CLC16_R_R(Instruction):
    oper : str
    reg : str
    reg2 : str
    def __str__(self):
        return "{0: <3} {1}, {2}".format(self.oper.upper(), self.reg, self.reg2)
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)
        context.emit_4bit(Bc8183.CLC_EXT)
        (kind, subcode) = ASMCODES.OPER2SUBCODE(self.oper)
        context.emit_4bit(kind)
        context.emit_4bit(subcode)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))

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
            context.emit_lo8addr(self.arg[1:])
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
            context.emit_rel8addr(self.arg[1:])
        else:
            context.emit_4bit(ASMCODES.TEST2OPCODE(self.test) | ASMCODES.CLC_OP_RNO)
            context.emit_4bit(ASMCODES.REG2BIN(self.arg[0:2]))
            context.emit_4bit(0)

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
            context.emit_hi8addr(self.arg[1:])
            context.emit_lo8addr(self.arg[1:])
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
        super().emit(context)
        context.emit_4bit(ASMCODES.CAL)
        if(self.arg.startswith(':')):
            context.emit_4bit(ASMCODES.CAL_EX_I16)
            context.emit_hi8addr(self.arg[1:])
            context.emit_lo8addr(self.arg[1:])
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
            context.emit_4bit(0)
            context.emit_4bit(ASMCODES.REG2BIN(self.reg))
            context.emit_4bit(self.arg)

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
                    context.emit_hi8addr(val[1:])
                    context.emit_lo8addr(val[1:])
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
        context.emit_hi8addr(self.lbl[1:])
        context.emit_4bit(ASMCODES.MOVRI8)
        context.emit_4bit(ASMCODES.REG2BIN(self.regs[2:]))
        context.emit_lo8addr(self.lbl[1:])

@dataclass
class DEF(Directive):
    lbl : str
    value : int
    def __str__(self):
        return ".DEF {0}, 0x{1:04x} ;{2}".format(self.lbl.upper(), self.value, getattr(self, 'comment', ''))
    def emit(self, context):
        super().emit(context)
        context.set_const(self.lbl, self.value)
        

def LINE(label, token, comment):
    if label:
        token.set_label(label)
    if comment:
        token.set_comment(comment)
    return token

def DEBUG(*args):
    i = 0
    for a in args:
       print("arg{}={}".format(i,a))
       i += 1
