from array import array
from dataclasses import dataclass
from msilib.schema import Error

STACKHEAD = "sys_stackhead"

def hi(b):
    return (b >> 4) & 0xf

def lo(b):
    return b & 0xf

class Scope:
    def __init__(self, context, prev_scope = None):
        self.variables = {}
        self.funcparams = {}
        self.context = context
        self.offset = 2 if prev_scope is None else prev_scope.offset
        self.startoffset = self.offset
        self.prev_scope = prev_scope
        self.declaredOnly = False

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
                scopeoffset = self.startoffset - self.prev_scope.startoffset
                rescopy = {
                    'name' : res['name'],
                    'type' : res['type'],
                    'offset': res['startoffset'] - scopeoffset,
                    'startoffset': self.startoffset
                }
                
                res = rescopy

        if res is None:    
            self.context.add_error("Undeclared variable {0}".format(varname))
        return res

    def get_variable_declared_only(self):
        self.declaredOnly = True

    def get_variable_all(self):
        self.declaredOnly = False

class Context:
    def __init__(self):
        self.data = ''
        self.basm = ''
        self.errors = []
        self.code_segment_addr = 0x0000
        self.data_segment_addr = 0x2000
        self.stack_segment_addr = 0x3000
        self.scope = Scope(self)
        self.nextident = 0
        self.function_dict = { }

    def emit(self, code):
        self.basm += code

    def prepend(self, code):
        self.basm = code + self.basm

    def emit_data(self, data):
        label = self.get_next_data_label()
        self.data += """
{0}:      .db '{1}', 0x00""".format(label, data)
        return label

    def load16(self, i16):
        return """mov cs, 0x{0:02x}
                mov ci, 0x{1:02x}""".format(hi(i16), lo(i16))

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

    def push_scope(self):
        self.scope = Scope(self, self.scope)
        scopeoffset = self.scope.startoffset
        if self.scope.prev_scope is not None:
            scopeoffset = scopeoffset - self.scope.prev_scope.startoffset
        if scopeoffset < 0:
            raise Error('Scope push error')
        if scopeoffset > 0:
            self.scope.startoffset = scopeoffset
            self.scope.offset = 0
            self.emit("""
;STACKHEAD += {2}
                psh cs
                psh ci
                .mv dsdi, :{0}
                cal :peek16
                mov ds, cs
                mov di, ci
                {1}
                cal :add16
                .mv dsdi, :{0}
                cal :poke16
                pop ci
                pop cs""".format(STACKHEAD, self.load16(scopeoffset), scopeoffset))

    def pop_scope(self):
        oldscope = self.scope
        self.scope = self.scope.prev_scope
        if self.scope is None:
            raise Error('Scope none error')
        scopeoffset = oldscope.startoffset - self.scope.startoffset
        if scopeoffset < 0:
            raise Error('Scope pop error')
        if scopeoffset > 0:
            self.emit("""
;STACKHEAD -= {2}
                psh cs
                psh ci
                .mv dsdi, :{0}
                cal :peek16
                mov ds, cs
                mov di, ci
                {1}
                cal :sub16
                .mv dsdi, :{0}
                cal :poke16
                pop ci
                pop cs""".format(STACKHEAD, self.load16(scopeoffset), scopeoffset))

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
        self.emit("""
;>>>>>>>>>>COMPILER ASM LIB<<<<<<<<<<<<<
               mov a, 0xff
               mov a, 0xff
               mov a, 0xff
               mov a, 0xff
;=============
; FATAL(a) - prints error message and stops
; IN:   a - error code
;   stack - as error address
; OUT:  KILL, messed stack
;
fatal:         psh a
               cal :print_newline
               .mv dsdi, :data_fatal
               cal :printstr
               pop a
               cal :printhex8
               .mv dsdi, :data_at
               cal :printstr
               pop ci
               pop cs
               cal :printhex16
               kil
;=============
; PRINTHEX4(a) - prints hex number from 0 to f
; IN:    a - number to print
; OUT:   a - unchanged      10 -> 0 -> 41
;       cs - set to 1
printhex4:     mov cs, 0x01
               psh a
               sub 0x0a
               jmr no, :printhex4_af
printhex4_09:  pop a
               add 0x30
               out #cs, a
               ret
printhex4_af:  pop a
               add 0x37
               out #cs, a
               ret
;=============
; PRINTHEX8(a) - prints hex number 
; IN:    a - number to print
; OUT:   a - set to lower half
;     csci - unchanged
;     dsdi - unchanged
printhex8:     psh cs
               psh ci
               mov ci, a
               shr 0x04
               cal :printhex4
               mov a, ci
               and 0x0f
               cal :printhex4
               pop ci
               pop cs
               ret
;=============
; PRINTHEX16(csci) - prints hex number 4 digits
; IN:    csci - hex number 4 digits
; OUT:   csci - unchanged
;           a - ci
printhex16:    mov a, cs
               psh ci
               cal :printhex8
               pop a
               cal :printhex8
               ret
;=============
; INC16(dsdi) - increase 16bit number correctly
; IN:    dsdi - number 16bit, break if exceeds 16bit
; OUT:   dsdi - add 1
;           a - di + 1 or ds + 1
inc16:         mov a, di
               inc a
               mov di, a
               jmr c, :inc16_carry
               ret
inc16_carry:   mov a, ds
               inc a
               mov ds, a
               jmr c, :inc16_fail
inc16_ret:     ret
inc16_fail:    mov a, 0x10
               cal :fatal
;=============
; DEC16(dsdi) - decrease 16bit number correctly
; IN:    dsdi - number 16bit, break if lower than 0
; OUT:   dsdi - sub 1
;           a - di - 1 or ds - 1
dec16:         mov a, di
               dec a
               mov di, a
               jmr o, :dec16_ovfl
               ret
dec16_ovfl:    mov a, ds
               dec a
               mov ds, a
               jmr o, :dec16_fail
dec16_ret:     ret
dec16_fail:    mov a, 0x11
               cal :fatal
;=============
; POKE16(#dsdi, csci) - stores csci value under #dsdi address (2 bytes)
; IN:   dsdi - address to store
;       csci - value to store
; OUT:  dsdi - address to store + 1
;       csci - unchanged
;       a    - rubbish
poke16:        mov #dsdi, cs
               cal :inc16
               mov #dsdi, ci
poke16_ok:     ret             
;=============
; PEEK16(#dsdi) - returns value under dsdi address (2 bytes)
; IN:   dsdi - address to read
; OUT:  dsdi - address to read + 1
;       csci - value
;       a    - rubbish
peek16:        mov cs, #dsdi
               cal :inc16
               mov ci, #dsdi
peek16_ok:     ret
;=============
; ADD16(csci,dsdi) - returns value under csci address (2 bytes) 
;                    return os error 0x10 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - sum of csci and dsdi
;       a    - rubbish
add16:         mov a, ci
               add di
               mov ci, a
               jmr c, :add16_carry1
               mov a, cs
add16_cry_nxt: add ds
               mov cs, a
               jmr c, :add16_cry2err
add16_ok:      ret
add16_carry1:  mov a, cs
               inc a
               jmr nc, :add16_cry_nxt
add16_cry2err: mov a, 0x12
               cal :fatal
;=============
; SUB16(csci,dsdi) - returns value under csci address (2 bytes) 
;                    return os error 0x11 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - substracts dsdi from csci
;       a    - rubbish
sub16:         mov a, ci
               sub di
               mov ci, a
               jmr o, :sub16_ovr1
               mov a, cs
sub16_crynxt:  sub ds
               mov cs, a
               jmr o, :sub16_ovr2err
sub16_ok:      ret
sub16_ovr1:    mov a, cs
               dec a
               jmr no, :sub16_crynxt
sub16_ovr2err: mov a, 0x13
               cal :fatal
;=============
; PRINT_NEWLINE - prints new line
; IN:
; OUT:   a - rubbish
print_newline: psh cs
               mov cs, 0x01
               mov a, 0x0a
               out #cs, a
               mov a, 0x0d
               out #cs, a
               pop cs
               ret
;=============
; PRINTSTR(*dsdi) - sends chars to printer
; IN: dsdi - address of 0-ended char table
; OUT:   a - set to 0x00
;       ci - set to 0x01
;     dsdi - set to end of char table
printstr:      mov ci, 0x01
printstr_loop: mov a, #dsdi
               jmr z, :printstr_end
               out #ci, a
               cal :inc16
               xor a
               jmr z, :printstr_loop
printstr_end:  ret
data_fatal:    .db 'fatal '
data_error:    .db 'error ', 0x00
data_at:       .db ' at ', 0x00
{0}: nop
""".format(STACKHEAD))

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
                {0}""".format(context.load16(self.i16)))

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

    def emit(self, context):
        if isinstance(self.term, str):
            var = context.get_variable(self.term)
            offset = var['offset']
            oper = 'add16'
            if offset < 0:
                oper = 'sub16'
                offset = -offset
            context.emit("""
                .mv dsdi,:{0}""".format(STACKHEAD))
            if offset != 0:
                context.emit("""
                {0}
                cal :{1}
                mov ds, cs
                mov di, ci""".format(context.load16(offset), oper))
            context.emit("""
                cal :peek16""")
            return
        self.term.emit(context)        

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

    def emit(self, context, funcCall = False):
        print('{0}={1};'.format(self.varname, self.expr))
        variable_def = context.get_variable(self.varname)
        offset = variable_def['offset']
        oper = 'add16'
        if offset < 0:
            oper = 'sub16'
            offset = -offset
        if offset != 0:
            context.emit("""
;{3} offset {4}
                .mv dsdi, :{0}
                {1}
                cal :{2}
                psh cs
                psh ci""".format(STACKHEAD, context.load16(offset), oper, variable_def['name'], offset))
        try:
            if funcCall: context.get_variable_declared_only()
            self.expr.emit(context)
        finally:
            if funcCall: context.get_variable_all()
        if(variable_def['type'] == 'word'):
            if offset == 0:
                context.emit("""
                .mv dsdi, :{0}
                cal :poke16""".format(STACKHEAD))
            else:
                context.emit("""
                pop di
                pop ds
                cal :poke16""")
            return
        if offset == 0:
            context.emit("""
            .mv dsdi, :{0}
            mov #dsdi, ci""".format(STACKHEAD))
        else:
            context.emit("""
            pop di
            pop ds
            mov #dsdi, ci""")

@dataclass
class CODE_BLOCK(Instruction):
    statements:list

    def __str__(self):
        return "BLOCK({0})".format(self.statements)

    def emit(self, context):
        currscope = context.scope
        context.push_scope()
        for statement in self.statements:
            statement.emit(context)
        if currscope != context.scope:
            context.pop_scope()

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
        context.pop_scope()
        context.emit("""
                ret""")

@dataclass
class EXPRESSION_CALL(Instruction):
    function_name:str
    params:list

    def __str__(self):
        return "FUNCTION_CALL[{0}({1})]".format(self.function_name, self.params)

    def emit(self, context):
        function_data = context.get_function_data(self.function_name)
        if function_data is None:
            context.add_error("Undeclared function {0}".format(self.function_name))
            return

        context.push_scope()

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

        context.pop_scope()

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
        context.push_scope()
        if not function_data['paramstar']:
            self.add_func_params(context, function_data)

        self.code.emit(context)
        context.pop_scope()
        context.emit("""
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

        context.prepend(""";MAIN ENTRYPOINT
                .mv dsdi, :{1}
                mov cs, ds
                mov ci, di
                cal :poke16
                cal :{0}
                kil
;FUNCTIONS""".format(function_data['label'], STACKHEAD))

        