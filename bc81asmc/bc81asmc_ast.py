from dataclasses import dataclass

#from bc16_cpu.py
class Bc8181:
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

    NOP    = 0x0
    MOVRI8 = 0x1
    MOVRR  = 0x2
    MOVRM  = 0x3
    MOVMR  = 0x4
    CLC    = 0x5

    def __init__(self):
        self.registers_bin = {
          'pc' : Bc8181.PC,
          'ss' : Bc8181.SS,
          'si' : Bc8181.SI,
          'f'  : Bc8181.F,
          'a'  : Bc8181.A,
          'ci' : Bc8181.CI,
          'cs' : Bc8181.CS,
          'di' : Bc8181.DI,
          'ds' : Bc8181.DS,
        }

        self.registers_str = {
          Bc8181.PC : 'pc',
          Bc8181.SS : 'ss',
          Bc8181.SI : 'si',
          Bc8181.F  : 'f',
          Bc8181.A  : 'a',
          Bc8181.CI : 'ci',
          Bc8181.CS : 'cs',
          Bc8181.DI : 'di',
          Bc8181.DS : 'ds',
        }

        self.oper_opcodes = {
          'add' : Bc8181.CLC_ADD,
          'sub' : Bc8181.CLC_SUB,
          'and' : Bc8181.CLC_AND,
          'or'  : Bc8181.CLC_OR,
          'xor' : Bc8181.CLC_XOR,
          'shl' : Bc8181.CLC_SHL,
          'shr' : Bc8181.CLC_SHR
        }

    def REG2BIN(self, reg : str):
        return self.registers_bin[reg.lower()]

    def BIN2REG(self, reg : int):
        return self.registers_str[reg]

    def OPER2OPCODE(self, oper):
        return self.oper_opcodes[oper]

ASMCODES = Bc8181()

class CodeContext:
    def __init__(self):
        self.bytes = bytearray()
        self.startaddr = 0
        self.currbyte = None
        self.currhalf = 0
        self.curraddr = 0
        self.errors = []
    def emit_byte(self, b):
        self.bytes.extend([b])
        self.currbyte = None
        self.currhalf = 0
        self.curraddr += 1
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

class Token:
    def __str__(self):
        return "token";
    def emit(self, context):
        pass
    def set_label(self, label):
        self.label = label

class ImmediateValue(Token):
    def __str__(self):
        return "imm";
    def emit(self, context):
        pass

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
class INC(Instruction):
    _ : str
    def __str__(self):
        return "INC a";
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC);
        context.emit_4bit(ASMCODES.CLC_INC);

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
class MOVRI8(Instruction):
    reg : str
    i8  : int
    def __str__(self):
        return "MOV {0}, 0x{1:02x}".format(self.reg, self.i8);
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.MOVRI8);
        context.emit_4bit(ASMCODES.REG2BIN(self.reg));
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
    imm : int
    def __str__(self):
        return "{0: <3} 0x{1:04x}".format(self.oper.upper(), self.imm)
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC)
        context.emit_4bit(ASMCODES.OPER2OPCODE(self.oper))
        context.emit_byte(self.imm)

@dataclass
class CLC_A_R(Instruction):
    oper : str
    reg : str
    def __str__(self):
        return "{0: <3} {1}".format(self.oper.upper(), self.reg)
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC);
        context.emit_4bit(ASMCODES.OPER2OPCODE(self.oper) | ASMCODES.CLC_OP_RNO)
        context.emit_4bit(ASMCODES.REG2BIN(self.reg))
        context.emit_4bit(0)

@dataclass
class NOT(Instruction):
    def __str__(self):
        return "NOT A"
    def emit(self, context):
        super().emit(context)
        context.emit_4bit(ASMCODES.CLC);
        context.emit_4bit(ASMCODES.CLC_NOT)

class Directive(Token):
    def __str__(self):
        return "directive";
    def emit(self, context):
        pass

@dataclass
class ORG(Directive):
    value : int
    def __str__(self):
        return "ORG 0x{0:04x}".format(self.value);
    def emit(self, context):
        context.set_addr(self.value)

def LINE(label, token):
    if label:
        token.set_label(label)
    return token

def DEBUG(*args):
    i = 0
    for a in args:
       print("arg{}={}".format(i,a))
       i += 1
