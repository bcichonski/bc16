from array import array
from dataclasses import dataclass

STACKHEAD = "__STACKHEAD"

class Scope:
    def __init__(self, context):
        self.variables = {}
        self.context = context
        self.offset = 0

    def add_variable(self, vartype, varname):
        if self.variables.get(varname) is not None:
            self.context.add_error(
                'Variable {0} was already defined in this scope'.format(varname))

        self.variables[varname] = {
            'name': varname,
            'type': vartype,
            'offset': self.offset
        }

        self.offset += self.length(vartype)

    def length(self, vartype):
        if vartype == 'word': return 2
        elif vartype == 'byte': return 1
        
        self.context.add_error('Unknown type {0}'.format(vartype))

    def get_variable(self, varname):
        res = self.variables.get(varname)
        if res is None:
            self.context.add_error("Undeclared variable {0}".format(varname))
        return res

class Context:
    def __init__(self):
        self.basm = ''
        self.errors = []
        self.code_segment_addr = 0x1000
        self.data_segment_addr = 0x2000
        self.stack_segment_addr = 0x3000
        self.scope = Scope(self)

    def emit(self, code):
        self.basm += code

    def add_error(self, message):
        print('ERROR: {0}'.format(message))
        self.errors.append(message)

    def add_variable(self, vartype, varname):
        self.scope.add_variable(vartype, varname)

    def get_variable(self, varname):
        return self.scope.get_variable(varname)

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

        for elem in self.arguments:
            context.emit("""
            psh cs
            psh ci""")

            elem[1].emit(context)

            context.emit("""
            pop di
            pop ds""")

            lib = oper2lib[elem[0]]
            if not lib:
                context.add_error(
                    "Unknown binary operator '{0}'".format(self.operator))
            context.emit("""
            cal :{0}""".format(lib))


@dataclass
class VARIABLE_DECLARATION(Instruction):
    vartype: str
    varname: str

    def __str__(self):
        return '{0} {1};'.format(self.vartype, self.varname)

    def emit(self, context):
        print('{0} {1};'.format(self.vartype, self.varname))
        context.add_variable(self.vartype, self.varname)

@dataclass
class VARIABLE_ASSIGNEMENT(Instruction):
    varname: str
    expr: object

    def __str__(self):
        return '{0}={1};'.format(self.varname, self.expr)

    def emit(self, context):
        print('{0}={1};'.format(self.varname, self.expr))
        variable_def = context.get_variable(self.varname)
        context.emit("""
            .mv dsdi, :{0}
            .mv csci, 0x{1:04x}
            cal :add16
            mov ds,cs
            mov di,ci
            cal :peek16
            psh cs
            psh ci""".format(STACKHEAD, variable_def['offset']))
        self.expr.emit(context)
        if(variable_def['type'] == 'word'):
            context.emit("""
            pop di
            pop ds
            cal :poke16""")
            return
        context.emit("""
            pop di
            pop ds
            mov #dsdi, ci""")