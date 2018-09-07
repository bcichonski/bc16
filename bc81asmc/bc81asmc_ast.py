class CodeContext:
    def __init__(self):
        self.bytes = bytearray()
        self.startaddr = 0
    def emit_byte(self, b):
        self.bytes.extend(b)
        self.currbyte = None
        self.currhalf = 0
    def emit_4bit(self, bit4):
        if(self.currhalf = 0):
            self.currbyte = (bit4 & 0xf) << 4
            self.currhalf = 1
        else:
            byte = self.currbyte | (bit4 & 0xf)
            self.emit_byte(byte)

class Token:
    def __str__(self):
        return "token";
    def emit(context):
        pass

class ImmediateValue:
    def __str__(self):
        return "imm";
    def emit(context):
        pass

class Value4(ImmediateValue):
    def __init__(self, value4):
        self.value = value4;
    def __str__(self):
        return "imm4({0:1x})".format(self.value)
    def emit(self, context):
        context.emit_4bit(value)

class Value8(ImmediateValue):
    def __init__(self, value):
        self.value = value;
    def __str__(self):
        return "imm8({0:2x})".format(self.value)
    def emit(self, context):
        context.emit_byte(value)

class Value16(ImmediateValue):
    def __str__(self):
        return "imm16({0:04x})".format(self.value)
    def emit(self, context):
        context.emit_byte((self.value >> 8) & 0xff)
        context.emit_byte(self.value & 0xff)

class Instruction(Token):
    def __str__(self):
        return "instruction";
    def emit(context):
        pass

class Directive(Token):
    def __str__(self):
        return "directive";
    def emit(context):
        pass

class ORG(Directive):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return "ORG {0x04}".format(value);
    def emit(context):
        context.startaddr = self.value
