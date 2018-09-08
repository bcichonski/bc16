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

    NOP = 0x0
    CLC = 0x5

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

    @staticmethod
    def REG2BIN(reg : str):
        return registers_bin[reg.lower()]

    @staticmethod
    def REG2BIN(reg : int):
        return registers_str[reg]

ASMCODES = Bc8181()

class CodeContext:
    def __init__(self):
        self.bytes = bytearray()
        self.startaddr = 0
        self.currbyte = None
        self.currhalf = 0
    def emit_byte(self, b):
        self.bytes.extend([b])
        self.currbyte = None
        self.currhalf = 0
    def emit_4bit(self, bit4):
        if(self.currhalf == 0):
            self.currbyte = (bit4 & 0xf) << 4
            self.currhalf = 1
        else:
            byte = self.currbyte | (bit4 & 0xf)
            self.emit_byte(byte)

class Token:
    def __str__(self):
        return "token";
    def emit(self, context):
        pass

class ImmediateValue:
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
        pass

@dataclass
class INC(Instruction):
    _ : str
    def __str__(self):
        return "INC a";
    def emit(self, context):
        context.emit_4bit(ASMCODES.CLC);
        context.emit_4bit(ASMCODES.CLC_INC);

class Directive(Token):
    def __str__(self):
        return "directive";
    def emit(self, context):
        pass

@dataclass
class ORG(Directive):
    value : int
    def __str__(self):
        return "ORG {0x04}".format(value);
    def emit(self, context):
        context.startaddr = self.value
