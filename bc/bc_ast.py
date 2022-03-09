from array import array
from dataclasses import dataclass


class Context:
    def __init__(self):
        self.basm = ''
        self.errors = []

    def emit(self, code):
        self.basm += code

    def add_error(self, message):
        self.errors.append(message)


class Instruction:
    def __str__(self):
        return "instruction"

    def emit(self, context):
        pass


@dataclass
class EXPRESSION_CONSTANT(Instruction):
    i16: int

    def __str__(self):
        return "CONST(0x{0:04x})".format(self.i16)

    def emit(self, context):
        context.emit("""
            .mv csci, 0x{0:04x}""".format(self.i16))


@dataclass
class EXPRESSION_UNARY(Instruction):
    operator: str
    operand: object

    def __str__(self):
        return "{0} {1}".format(self.operand, self.operator)

    def emit(self, context):
        if self.operator == '&':
            self.operand.emit(context)
            context.emit("""
            mov a, #csci
            mov ds,a
            cal :inc16
            mov a, #csci
            mov cs,ds
            mov ci,a""")
        else:
            context.add_error(
                "Unknown unary operator '{0}'".format(self.operator))


oper2lib = {
    '+': 'add16',
    '-': 'sub16',
    '*': 'mul16',
    '/': 'div16'
}

@dataclass
class EXPRESSION_BINARY(Instruction):
    operand1: object
    arguments: array

    def __str__(self):
        ret = '{0}'.format(self.operand1)
        for elem in self.arguments:
            ret += ' {1} {0}'.format(elem[0], elem[1])
        return ret

    def emit(self, context):
        self.operand1.emit(context)

        context.emit("""
            psh cs
            psh ci""")

        for elem in self.arguments:
            elem[1].emit(context)

            context.emit("""
            pop ci
            pop cs""")

            lib = oper2lib[elem[0]]
            if not lib:
                context.add_error(
                    "Unknown binary operator '{0}'".format(self.operator))
            context.emit("""
            cal :{0}""".format(lib))
