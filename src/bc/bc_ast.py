from bc_stdlib import stdlib_template
from array import array
from dataclasses import dataclass
from msilib.schema import Error
from pickle import TRUE

STACKHEAD = "sys_stackhead"
HEAPHEAD = "sys_heaphead"

def hi(b):
    return (b >> 8) & 0xff

def lo(b):
    return b & 0xff

class Scope:
    def __init__(self, context, prev_scope = None):
        self.variables = {}
        self.funcparams = {}
        self.context = context
        self.offset = 0
        self.startoffset = 0 if prev_scope is None else prev_scope.startoffset + prev_scope.offset
        self.prev_scope = prev_scope
        self.declaredOnly = False
        self.depth = 0 if prev_scope is None else prev_scope.depth + 1

    def add_variable(self, vartype, varname, funcparam = False):
        if funcparam:
            if self.funcparams.get(varname) is not None:
                self.context.add_error(
                    'Function parameter {0} was already defined in this scope'.format(varname))

            self.funcparams[varname] = {
                'name': varname,
                'type': vartype,
                'offset': self.offset,
                'startoffset': self.startoffset
            }
        else:
            if self.variables.get(varname) is not None:
                self.context.add_error(
                    'Variable {0} was already defined in this scope'.format(varname))

            self.variables[varname] = {
                'name': varname,
                'type': vartype,
                'offset': self.offset,
                'startoffset': self.startoffset
            }

        self.offset += self.length(vartype)

    def length(self, vartype):
        if vartype == 'word': return 2
        elif vartype == 'byte': return 1
        
        self.context.add_error('Unknown type {0}'.format(vartype))

    def get_variable(self, varname):
        if not self.declaredOnly:
            res = self.funcparams.get(varname)
            if res is not None:
                return res

        res = self.variables.get(varname)
        if res is None:
            if self.prev_scope is not None:
                res = self.prev_scope.get_variable(varname)

                #print('1VAR {0} data is {1}'.format(varname, res))
                #print('PREV SCOPE start offset is {0}'.format(self.prev_scope.startoffset))
                #print('CURR SCOPE start offset is {0}'.format(self.startoffset))

                scopeoffset = self.startoffset - self.prev_scope.startoffset
                rescopy = {
                    'name' : res['name'],
                    'type' : res['type'],
                    'offset': res['offset'] - scopeoffset,
                    'startoffset': self.startoffset
                }
                
                res = rescopy

                #print('2VAR {0} data is {1}'.format(varname, res))

        if res is None:    
            self.context.add_error("Undeclared variable {0}".format(varname))
        return res

    def get_variable_declared_only(self):
        self.declaredOnly = True

    def get_variable_all(self):
        self.declaredOnly = False

    def offset_sum(self):
        sum=0
        curr_scope=self
        while(curr_scope is not None):
            sum+=curr_scope.offset
            curr_scope = curr_scope.prev_scope
        return sum

class Context:
    def __init__(self, codeaddr = 0x0000, heapaddr = 0x2000, hardkill = True):
        self.data = ''
        self.basm = ''
        self.errors = []
        self.code_segment_addr = codeaddr
        self.heap_segment_addr = heapaddr
        self.scope = Scope(self)
        self.nextident = 0
        self.function_dict = { }
        self.hardkill = hardkill

    def emit(self, code):
        self.basm += code

    def prepend(self, code):
        self.basm = code + self.basm

    def emit_data(self, data):
        label = self.get_next_data_label()
        self.data += """
{0}:      .db '{1}', 0x00""".format(label, data)
        return label

    def load_csci(self, i16):
        return """mov cs, 0x{0:02x}
                mov ci, 0x{1:02x}""".format(hi(i16), lo(i16))

    def load_dsdi(self, i16):
        return """mov ds, 0x{0:02x}
                mov di, 0x{1:02x}""".format(hi(i16), lo(i16))

    def add_error(self, message):
        print('ERROR: {0}'.format(message))
        self.errors.append(message)

    def add_variable(self, vartype, varname, funcparam = False):
        self.scope.add_variable(vartype, varname, funcparam)

    def get_variable(self, varname):
        return self.scope.get_variable(varname)

    def get_variable_declared_only(self):
        self.scope.get_variable_declared_only()

    def get_variable_all(self):
        self.scope.get_variable_all()

    def get_next_label(self):
        self.nextident += 1
        return "LABEL{0:04x}".format(self.nextident)

    def get_next_data_label(self):
        self.nextident += 1
        return "DATA{0:04x}".format(self.nextident)

    def add_preamble(self):
        self.prepend(""";
                .org 0x{0:04x}
""".format(self.code_segment_addr))

    def push_scope(self, caller):
        self.scope = Scope(self, self.scope)
        startoffset = self.scope.startoffset
        scopeoffset = startoffset
        if self.scope.prev_scope is not None:
            scopeoffset = scopeoffset - self.scope.prev_scope.startoffset
        if scopeoffset < 0:
            raise Error('Scope push error')
        if scopeoffset > 0:
            # self.scope.startoffset = scopeoffset
            self.emit("""
;depth {2}: STACKHEAD += {1}
                psh cs
                psh ci
                {0}
                xor a
                cal :stackheadroll
                pop ci
                pop cs""".format(self.load_csci(scopeoffset), scopeoffset, self.scope.depth))
        print("PUSH SCOPE (startoffset={0}, depth={1}, caller={2})".format(self.scope.startoffset, self.scope.depth, caller))

    def pop_scope(self, caller):
        oldscope = self.scope
        self.scope = self.scope.prev_scope
        if self.scope is None:
            raise Error('Scope none error')
        scopeoffset = oldscope.startoffset - self.scope.startoffset
        print("POP SCOPE (startoffset={0}, offset={1}, diff={2}, depth={3}, caller={4})".format(self.scope.startoffset, self.scope.offset, scopeoffset, self.scope.depth, caller))
        if scopeoffset < 0:
            raise Error('Scope pop error')
        if scopeoffset > 0:
            self.emit("""
;depth {2}: STACKHEAD -= {1}
                psh cs
                psh ci
                {0}
                mov a, 0x01
                cal :stackheadroll
                pop ci
                pop cs""".format(self.load_csci(scopeoffset), scopeoffset, self.scope.depth))

    def get_function_call_label(self, function_name):
        if len(function_name) > 10:
            function_name = function_name[:10]
        function_name = function_name.upper()
        self.nextident += 1

        return "F{0}{1:04x}".format(function_name, self.nextident)

    def get_function_data(self, function_name):
        return self.function_dict.get(function_name)

    def set_function_data(self, function_name, data):
        self.function_dict[function_name] = data

    def add_data_segment(self):
        if len(self.data) > 0:
            self.emit("""
;>>>>>>>>>>DATA SEGMENT<<<<<<<<<<<<<""")
            self.emit(self.data)

    def add_stdlib(self):
        self.emit(stdlib_template.format(STACKHEAD, HEAPHEAD, hi(self.heap_segment_addr), lo(self.heap_segment_addr)))
        
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
                {0}""".format(context.load_csci(self.i16)))

@dataclass
class EXPRESSION_CONST_STR(Instruction):
    value: str

    def __str__(self):
        return 'CONST("{0}")'.format(self.value)

    def emit(self, context):
        label = context.emit_data(self.value)
        context.emit("""
                .mv csci, :{0}""".format(label))

@dataclass
class EXPRESSION_TERM(Instruction):
    term : object

    def __str__(self):
        return "TERM({})".format(self.term)

    def emit(self, context: Context):
        print('TERM {0}'.format(self.term))
        if isinstance(self.term, str):
            var = context.get_variable(self.term)
            print('TERM {0} IS VAR {1}'.format(self.term, var))
            offset = var['offset']
            oper = 'xor a'
            if offset < 0:
                oper = 'mov a, 0x01'
                offset = -offset
            varget = 'stackvarget16'
            if var['type'] == 'byte':
                varget = 'stackvarget8'

            context.emit("""
            {0}
            {1}
            cal :{2}""".format(context.load_dsdi(offset), oper, varget))
            return
        
        self.term.emit(context)        

@dataclass
class EXPRESSION_UNARY(Instruction):
    operator: str
    operand: object

    def __str__(self):
        return "{0} {1}".format(self.operand, self.operator)

    def emit(self, context):
        if self.operator == '#':
            self.operand.emit(context)
            context.emit("""
                mov ds, cs
                mov di, ci
                cal :peek16""")
        elif self.operator == '!':
            self.operand.emit(context)
            context.emit("""
                mov a, cs
                or  ci
                mov a, f
                and 0x01
                mov cs,0x00
                mov ci, a""")
        else:
            context.add_error(
                "Unknown unary operator '{0}'".format(self.operator))


oper2lib = {
    '+': 'add16',
    '-': 'sub16',
    '*': 'mul16',
    '/': 'div16',
    '=': None,
    '>=': None,
    '!=': None
}

@dataclass
class EXPRESSION_BINARY(Instruction):
    operand1: object
    arguments: array

    def __str__(self):
        if len(self.arguments) == 0:
            return self.operand1.__str__()

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
                mov ds, cs
                mov di, ci
                pop ci
                pop cs""")
            lib = oper2lib[elem[0]]
            if not lib:
                if not self.logic(context, elem[0]):
                    context.add_error(
                        "Unknown binary operator '{0}'".format(self.operator))
                continue
            context.emit("""
                cal :{0}""".format(lib))

    def logic(self, context, oper):
        if oper == '=':
            context.emit("""
                cal :eq16
                mov cs, 0x00
                mov ci, a""")
            return True
        if oper == '>=':
            context.emit("""
                cal :gteq16
                mov cs, 0x00
                mov ci, a""")
            return True
        if oper == '!=':
            context.emit("""
                cal :eq16
                mov cs, 0x00
                dec a
                mov ci, a""")
            return True
        return False

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

    def emit(self, context: Context, funcCall = False):
        print('{0}={1};'.format(self.varname, self.expr))
        variable_def = context.get_variable(self.varname)
        print('{0}'.format(variable_def))
        offset = variable_def['offset']
        oper = 'xor a'
        if offset < 0:
            oper = 'mov a, 0x01'
            offset = -offset
        varset = 'stackvarset16'
        if(variable_def['type'] == 'byte'):
            varset = 'stackvarset8'
        
        try:
            if funcCall: context.get_variable_declared_only()
            self.expr.emit(context)
        finally:
            if funcCall: context.get_variable_all()
        
        context.emit("""
;{2} offset {3} OPER {1}
            {0}
            {1}
            cal :{4}""".format(context.load_dsdi(offset), oper, variable_def['name'], offset, varset))

        if(variable_def['type'] == 'word' or variable_def['type'] == 'byte'):
            return
        self.context.add_error('Unknown type {0} in assignment'.format(variable_def['type']))

@dataclass
class CODE_BLOCK(Instruction):
    statements:list

    def __str__(self):
        return "BLOCK({0})".format(self.statements)

    def emit(self, context):
        currscope = context.scope
        context.push_scope('BLOCK')
        for statement in self.statements:
            statement.emit(context)
        if currscope != context.scope:
            context.pop_scope('BLOCK')

@dataclass
class STATEMENT_IF(Instruction):
    expr:object
    code:object

    def __str__(self):
        return "IF({0})[{1}]".format(self.expr, self.code)

    def emit(self, context):
        self.expr.emit(context)
        label = context.get_next_label()
        context.emit("""
                mov a, cs
                or ci
                .mv csci, :{0}
                jmp z, csci""".format(label))
        self.code.emit(context)
        context.emit("""
{0}:      nop""".format(label))

@dataclass
class STATEMENT_WHILE(Instruction):
    expr:object
    code:object

    def __str__(self):
        return "WHILE({0})[{1}]".format(self.expr, self.code)

    def emit(self, context):
        label1 = context.get_next_label()
        label2 = context.get_next_label()
        context.emit("""
{0}:      nop""".format(label1))
        self.expr.emit(context)
        context.emit("""
                mov a, cs
                or ci
                .mv csci, :{0}
                jmp z, csci""".format(label2))
        self.code.emit(context)
        context.emit("""
                .mv csci, :{0}
                xor a
                jmp z, csci
{1}:      nop""".format(label1, label2))

@dataclass
class STATEMENT_ASM(Instruction):
    expr:object

    def __str__(self):
        return "ASM[{0}]".format(self.expr)

    def emit(self, context):
        context.emit("""
                {0}""".format(self.expr))

@dataclass
class STATEMENT_RETURN(Instruction):
    expr:object

    def __str__(self):
        return "RETURN({0})".format(self.expr)

    def emit(self, context):
        self.expr.emit(context)
        context.pop_scope('RET')
        context.emit("""
                ret""")

@dataclass
class EXPRESSION_CALL(Instruction):
    function_name:str
    params:list

    def __str__(self):
        return "FUNCTION_CALL[{0}({1})]".format(self.function_name, self.params)

    def emit(self, context: Context):
        function_data = context.get_function_data(self.function_name)
        if function_data is None:
            context.add_error("Undeclared function {0}".format(self.function_name))
            return

        context.push_scope('CALL')

        paramdata = function_data['params']
        paramstar = function_data['paramstar']
        funcname = function_data['name']
        paramno = 0
        for param in self.params:
            param_data = paramdata[paramno]
            param_name = param_data['name']
            paramtype = param_data['type']
            if(param_data is None):
                if not paramstar:
                    context.add_error('Unrecognized function {0} parameter {1}'.format(self.function_name, param_name))

            context.add_variable(paramtype, param_name, True)
            varassignement = VARIABLE_ASSIGNEMENT(param_name, param)
            varassignement.emit(context, True)
            paramno += 1

        if paramstar:
            paramname = funcname
            if len(paramname) > 10: 
                paramname = paramname[:10]
            paramname = "__SLN{0}".format(paramname)
            paramtype = 'byte'
            context.add_variable('byte', paramname, True)
            varassignement = VARIABLE_ASSIGNEMENT(paramname, EXPRESSION_CONSTANT(paramno - 1))
            varassignement.emit(context)

        context.emit("""
                cal :{0}""".format(function_data['label']))

        context.pop_scope('CALL')

@dataclass
class STATEMENT_COMMENT(Instruction):
    comment:str

    def __str__(self):
        return "COMMENT[{0}]".format(self.comment)

    def emit(self, context):
        context.emit("""
;{0}""".format(self.comment))
        
        
@dataclass
class FUNCTION_DECLARATION(Instruction):
    return_type:str
    function_name:str
    params:list
    star:str
    code:object

    def __str__(self):
        return "FUNCTION {0}({1})->{2}[{3}]".format(self.function_name, self.params, self.return_type, self.code)

    def emit(self, context):
        function_data = context.get_function_data(self.function_name)

        if function_data is None:
            function_data = self.add_declaration(context)

        if self.code is not None:
            self.add_code(function_data, context)
            function_data['code'] = True

    def add_declaration(self, context):
        params = []
        for param in self.params:
            params.append({
                'name' : param.varname,
                'type' : param.vartype
            })

        function_data = {
            'name': self.function_name,
            'label': context.get_function_call_label(self.function_name),
            'type': self.return_type,
            'params': params,
            'paramstar': False if self.star is None else len(self.star) > 0,
            'code': False
        }

        context.set_function_data(self.function_name, function_data)
        return function_data

    def add_func_params(self, context, function_data):
        for param in function_data['params']:
            context.add_variable(param['type'], param['name'], True)

    def add_code(self, function_data, context):
        context.emit("""
;FUNCTION {0}
{1:<16}nop""".format(function_data['name'], function_data['label'] + ":"))
        context.push_scope('FUNC')
        if not function_data['paramstar']:
            self.add_func_params(context, function_data)

        self.code.emit(context)
        context.pop_scope('FUNC')
        context.emit("""
                ret
;END OF FUNCTION {0}""".format(function_data['name']))

@dataclass
class PROGRAM(Instruction):
    functions:list

    def __str__(self):
        return "PROGRAM==>{0}".format(self.functions)

    def emit(self, context):
        mainfunc = next((x for x in self.functions if x.function_name == 'main'), None)

        if mainfunc is None:
            context.add_error('Main entry point not found')
            return

        for function in self.functions:
            function.emit(context)

        function_data = context.get_function_data(mainfunc.function_name)

        if context.hardkill:
            last_command = 'kil'
        else:
            last_command = 'ret'

        context.prepend(""";MAIN ENTRYPOINT
;&STACKHEAD <- STACKHEAD + 2
                .mv dsdi, :{1}
                mov cs, 0x00
                mov ci, 0x02
                cal :add16
                .mv dsdi, :{1}
                cal :poke16
;&HEAPHEAD <- {5}
                .mv dsdi, :{2}
                {4}
                cal :poke16
                cal :{0}
                {3}
;FUNCTIONS""".format(function_data['label'], STACKHEAD, HEAPHEAD, last_command, context.load_csci(context.heap_segment_addr), context.heap_segment_addr))

        