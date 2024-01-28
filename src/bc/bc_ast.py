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
        self.emit("""
;>>>>>>>>>>COMPILER ASM LIB - BCOS 1.0<<<<<<<<<<<<<
            mov a, 0xff
            mov a, 0xff
            mov a, 0xff
            mov a, 0xff
;=============
; FATAL(a) - prints error message and stops
; IN:   a - error code
;   stack - as error address
; OUT:  KILL, messed stack
            .def fatal, 0x04ea
;=============
; PRINTHEX4(a) - prints hex number from 0 to f
; IN:    a - number to print
; OUT:   a - unchanged      10 -> 0 -> 41
;       cs - set to 1
            .def printhex4, 0x0349
;=============
; PRINTHEX8(a) - prints hex number 
; IN:    a - number to print
; OUT:   a - set to lower half
;     csci - unchanged
;     dsdi - unchanged
            .def printhex8, 0x035c
;=============
; PRINTHEX16(csci) - prints hex number 4 digits
; IN:    csci - hex number 4 digits
; OUT:   csci - unchanged
;           a - ci
            .def printhex16, 0x036f
;=============
; INC16(dsdi) - increase 16bit number correctly
; IN:    dsdi - number 16bit, break if exceeds 16bit
; OUT:   dsdi - add 1
;           a - di + 1 or ds + 1
            .def inc16, 0x037a
;=============
; DEC16(dsdi) - decrease 16bit number correctly
; IN:    dsdi - number 16bit, break if lower than 0
; OUT:   dsdi - sub 1
;           a - di - 1 or ds - 1
            .def dec16, 0x038f
;=============
; POKE16(#dsdi, csci) - stores csci value under #dsdi address (2 bytes)
; IN:   dsdi - address to store
;       csci - value to store
; OUT:  dsdi - address to store + 1
;       csci - unchanged
;       a    - rubbish
            .def poke16, 0x03b0            
;=============
; PEEK16(#dsdi) - returns value under dsdi address (2 bytes)
; IN:   dsdi - address to read
; OUT:  dsdi - address to read + 1
;       csci - value
;       a    - rubbish
            .def peek16, 0x03b8
;=============
; ADD16(csci,dsdi) - returns value
;                    return os error 0x12 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - sum of csci and dsdi
;       a    - rubbish
            .def add16, 0x03c0
;=============
; SUB16(csci,dsdi) - returns value 
;                    return os error 0x13 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - substracts dsdi from csci
;       a    - rubbish
            .def sub16, 0x03db
;=============
; MUL16(csci,dsdi) - returns value 
;                    return os error 0x12 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - mutiplies csci by dsdi
;       dsdi - unchanged
;       a    - rubbish
mul16:       psh ds
             psh di
             cal :gteq16
             jmr nz, :mul16_swpskp
             psh cs
             mov cs, ds
             pop ds
             psh ci
             mov ci, di
             pop di
mul16_swpskp:mov a,ds
             or di
             jmr nz,:mul16_isone
             xor a
             mov cs, a
             mov ci, a
             jmr z,:mul16_ret
mul16_isone: mov a, ds
             jmr nz, :mul16_calc
             mov a, di
             dec a
             jmr nz, :mul16_calc
             jmr z, :mul16_ret
mul16_calc:  xor a
             psh a
             psh a
mul16_loop:  mov a, di
             and 0x01
             jmr z, :mul16_by2
             psh cs
             psh ci
mul16_by2:   mov a, cs
             shl 0x01
             mov cs, a
             mov a, ci
             shl 0x01
             jmr no, :mul16_by2nst
             psh a
             mov a, cs
             or 0x01
             mov cs, a
             pop a
mul16_by2nst:mov ci, a
             mov a, di
             shr 0x01
             mov di, a
             mov a, ds
             and 0x01
             jmr z, :mul16_by2nmt
             mov a, di
             or 0x80
             mov di, a
mul16_by2nmt:mov a, ds
             shr 0x01
             mov ds, a
             or  di
             dec a
             jmr nz, :mul16_loop
mul16_addlp: pop di
             pop ds
             mov a, di
             or  ds
             jmr z, :mul16_ret
             cal :add16
             xor a
             jmr z, :mul16_addlp
mul16_ret:   pop di
             pop ds
             ret
;=============
; DIV16(csci,dsdi) - returns value 
;                    return os error 0x13 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - divides csci by dsdi
;       dsdi - unchanged
;       a    - rubbish
div16:       psh cs
             psh ci
             mov cs, ds
             mov ci, di
             .mv dsdi, :sys_div16tmp
             cal :poke16
             mov ds, cs
             mov di, ci
             pop ci
             pop cs
             cal :gteq16
             jmr z, :div16_zero
             mov a, 0x80
             and ds
             jmr nz, :div16_one
             xor a
             psh a
             inc a
             psh a
div16_loop:  psh ds
             psh di
             cal :sub16
             pop di
             pop ds
             cal :gteq16
             jmr z, :div16_end
             pop di
             pop ds
             cal :inc16
             psh ds
             psh di
             psh cs
             psh ci
             .mv dsdi, :sys_div16tmp
             cal :peek16
             mov ds, cs
             mov di, ci
             pop ci
             pop cs        
             xor a
             jmr z, :div16_loop
div16_end:   pop ci
             pop cs
             ret          
div16_one:   mov cs, 0x00
             mov ci, 0x01
             jmr nz, :div16_ret
div16_zero:  xor a
             mov cs, a
             mov ci, a
div16_ret:   ret
;=============
; READSTR(#dsdi, ci) - reads characters to the buffer
; IN:   dsdi - buffer address for chars
;         ci - length of the buffer (since last char has to be 0x00 we can enter one less)
; OUT:  dsdi - preserved
;         ci - preserved
;         cs - how many chars can we could still add
            .def readstr, 0x03f6
;=============
; PARSEHEX4(#dsdi) - parses single char to hex number chars 0-9 and a-z and A-Z are supported
; IN:   dsdi - buffer address for char-hex
; OUT:     a - 0 if ok, 0xff if parse error
;         ci - hexval of a char
            .def parsehex4, 0x0448
;=============
; PARSEHEX8(#dsdi) - parses two char to hex number
; IN:   dsdi - buffer address for char
; OUT:    a - success = 0 or >0 error
;        ci - hex value for byte
;      dsdi - moved + 2 if ok
            .def parsehex8, 0x0476
;=============
; PARSEHEX16(#dsdi) - parses four char to hex number
; IN:   dsdi - buffer address for char
; OUT:  csci - hex value for value
;          a - success = 0 or error code
;       dsdi - moved + 4 if ok
            .def parsehex16, 0x0497
;=============
; PRINT_NEWLINE - prints new line
; IN:
; OUT:   a - rubbish
            .def print_newline, 0x0323
;=============
; PRINTSTR(*dsdi) - sends chars to printer
; IN: dsdi - address of 0-ended char table
; OUT:   a - set to 0x00
;       ci - set to 0x01
;     dsdi - set to end of char table
            .def printstr, 0x0339
;=============
; GTEQ16(csci,dsdi) - compares csci with dsdi            
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  a - 1 if csci >= dsdi
;       a - 0 otherwise
gteq16:      mov a, cs
             sub ds
             jmr o, :gteq16_false
             jmr nz, :gteq16_true
             mov a, ci
             sub di
             jmr o, :gteq16_false
             jmr nz, :gteq16_true
gteq16_true: mov a, 0x01
             ret
gteq16_false:xor a
             ret
;=============
; EQ16(csci,dsdi) - compares csci with dsdi            
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  a - 1 if csci == dsdi
;       a - 0 otherwise
eq16:       mov a, cs
            sub ds
            jmr nz, :gteq16_false
            mov a, ci
            sub di
            jmr nz, :gteq16_false
eq16_true:  mov a, 0x01
            ret
eq16_false: xor a
            ret
;=============
; STACKOFFSCALC(csci,a) - modifies SYS_STACKHEAD by csci and stores new value back in csci
; IN: csci - value to increase
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value of SYS_STACKHEAD with offset
;     dsdi - address of SYS_STACKHEAD
;        a - rubbish
stackoffscalc: psh a
               psh cs
               psh ci
               .mv dsdi, :{0}
               cal :peek16
               pop di
               pop ds
               pop a
               and a
               jmr nz, :stoffclc_sub
               cal :add16
               xor a
               jmr z, :stoffclc_end
stoffclc_sub:  cal :sub16  
stoffclc_end:  .mv dsdi, :{0}
               ret
;=============
; STACKHEADROLL(csci, a) - modifies SYS_STACKHEAD by csci and saves new value
; IN: csci - value to increase
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value of SYS_STACKHEAD
;     dsdi - address of SYS_STACKHEAD
;        a - rubbish
stackheadroll: cal :stackoffscalc
               cal :poke16
               .mv dsdi, :{0}
               ret
;=============
; STACKVARGET8(dsdi, a) - loads value of the variable of given offset dsdi from SYS_STACKHEAD to csci
; IN: dsdi - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x01 - sub
; OUT:ci - value of variable
;     cs - set to 0
;     dsdi - address of SYS_STACKHEAD
;        a - rubbish
stackvarget8:  mov cs, ds
               mov ci, di
               cal :stackoffscalc   
               mov a, #csci
               mov cs, 0x00
               mov ci, a
               ret
;=============
; STACKVARGET16(dsdi, a) - loads value of the variable of given offset dsdi from SYS_STACKHEAD to csci
; IN: dsdi - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value of variable
;     dsdi - address of variable + 1
;        a - rubbish
stackvarget16: mov cs, ds
               mov ci, di
               cal :stackoffscalc
               mov ds, cs
               mov di, ci   
               cal :peek16
               ret
;=============
; STACKVARSET8(ci,dsdi, a) - loads value of the variable of given offset from SYS_STACKHEAD to csci
; IN: ci - value
;     dsdi - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value of variable
;     dsdi - address of SYS_STACKHEAD
;        a - ci
stackvarset8:  psh ci
               mov cs, ds
               mov ci, di
               cal :stackoffscalc   
               pop a
               mov #csci, a
               ret
;=============
; STACKVARSET16(csci,dsdi, a) - loads value of the variable of given offset from SYS_STACKHEAD to csci
; IN: csci - value
;     dsdi - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value
;     dsdi - address of variable + 1
;        a - ci
stackvarset16: psh cs
               psh ci
               mov cs, ds
               mov ci, di
               cal :stackoffscalc   
               mov ds, cs
               mov di, ci
               pop ci
               pop cs
               cal :poke16
               ret
;=============
; MALLOC(csci) - allocates csci bytes on the program heap
; IN: csci - size of the block
; OUT:csci - address of the block
malloc:        psh cs
            psh ci
            .mv dsdi, :{1}
            cal :peek16
            ret
;=============
; SEEK(csci, dsdi) - finds address of first free block of given size
; IN: csci - wanted size of the block
; OUT:dsdi - address of the block after which is enough free memory
;     csci - address after which free memory begins
seek:          psh cs
            psh ci
            .mv dsdi, :{1}
            cal :peek16
            mov ds, cs
            mov di, ci
            psh cs
            psh ci
seek_loop:     cal :peek16
            mov a, ci
            xor cs
            jmr z, :seek_end
            cal :dec16
            cal :sub16
            pop di
            pop ds
            psh cs
            psh ci
            cal :inc16
            cal :inc16
            cal :peek16
            mov ds, cs
            mov di, ci
            pop ci
            pop cs
            cal :sub16
            pop di
            pop ds
            cal :gteq16
            jmr nz, :seek_end
;               ...
            jmr z, :seek_loop
seek_end:      pop di
            pop ds
            pop ci
            pop cs
            ret  
;=============
;SYS DATA
            .def var_promptbuf, 0x0bcf
            .def var_user_mem, 0x0bcb
sys_div16tmp: .db 0x00, 0x00
{1}:  .db 0x{2:02x}, 0x{3:02x}
{0}: nop
""".format(STACKHEAD, HEAPHEAD, hi(self.heap_segment_addr), lo(self.heap_segment_addr)))
        
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
        if self.operator == '&':
            self.operand.emit(context)
            context.emit("""
                mov a, #csci
                mov ds,a
                cal :inc16
                mov a, #csci
                mov cs,ds
                mov ci,a""")
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

        