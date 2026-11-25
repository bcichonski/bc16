import re
import bc_log
from bc_stdlib import runtime_banner, runtime_head, runtime_fragments, runtime_tail
from array import array
from dataclasses import dataclass

class CompilerError(Exception):
    pass

class UndeclaredVariableError(CompilerError):
    '''A variable is in no scope. The error is recorded through Context.add_error before this is raised.'''
    pass

STACKHEAD = "sys_stackhead"
HEAPHEAD = "sys_heaphead"

LABEL_DEF = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*):')
DEF_DIRECTIVE = re.compile(r'^\s*\.def\s+([A-Za-z_][A-Za-z0-9_]*)')
LABEL_REF = re.compile(r':([A-Za-z_][A-Za-z0-9_]*)')

def strip_asm_comment(line):
    '''One assembly line without its `;` comment; a `;` inside a quoted literal is not a comment.'''
    quote = None
    for i, c in enumerate(line):
        if quote is not None:
            if c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c == ';':
            return line[:i]
    return line

def asm_labels(text):
    '''(defined labels, referenced labels) of assembly text, comments excluded.

    A definition is `name:` at the start of a line (after whitespace; an instruction may follow)
    or `.def name, ...`; a reference is any `:name` token. Over-approximating references is safe.'''
    defined = set()
    referenced = set()
    for line in text.splitlines():
        line = strip_asm_comment(line)
        match = LABEL_DEF.match(line) or DEF_DIRECTIVE.match(line)
        if match is not None:
            defined.add(match.group(1))
        referenced.update(LABEL_REF.findall(line))
    return defined, referenced

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

    def add_variable(self, vartype, varname, funcparam = False, calltrace = ''):
        if funcparam:
            if self.funcparams.get(varname) is not None:
                self.context.add_error(
                    'Function parameter {0} was already defined in this scope {1}'.format(varname, calltrace))

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

    def _find_variable(self, varname):
        """Look the name up through this scope and the previous ones. Returns None when it is in no scope."""
        if not self.declaredOnly:
            res = self.funcparams.get(varname)
            if res is not None:
                return res

        res = self.variables.get(varname)
        if res is None and self.prev_scope is not None:
            res = self.prev_scope._find_variable(varname)
            if res is not None:
                scopeoffset = self.startoffset - self.prev_scope.startoffset
                res = {
                    'name' : res['name'],
                    'type' : res['type'],
                    'offset': res['offset'] - scopeoffset,
                    'startoffset': self.startoffset
                }
        return res

    def get_variable(self, varname):
        res = self._find_variable(varname)
        if res is None:
            self.context.add_error("Undeclared variable {0}".format(varname))
            raise UndeclaredVariableError("Undeclared variable {0}".format(varname))
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
    def __init__(self, codeaddr = 0x0000, heapaddr = 0x3000, hardkill = True, codelimit = None):
        self.data = ''
        self.basm = ''
        self.errors = []
        self.code_segment_addr = codeaddr
        self.heap_segment_addr = heapaddr
        self.code_limit_addr = codelimit
        self.scope = Scope(self)
        self.nextident = 0
        self.function_dict = { }
        self.hardkill = hardkill
        self.hint_loaddsdi = False
        self.chunks = []

    def emit(self, code):
        self.basm += code

    def prepend(self, code):
        self.basm = code + self.basm

    def emit_data(self, data):
        label = self.get_next_data_label()
        self.data += """
{0}:      .db '{1}', 0x00""".format(label, data)
        return label
    
    def load_a(self, i8):
        return """mov a, 0x{0:02x}""".format(i8)

    def load_csci(self, i16):
        return """mov cs, 0x{0:02x}
                mov ci, 0x{1:02x}""".format(hi(i16), lo(i16))

    def load_dsdi(self, i16):
        return """mov ds, 0x{0:02x}
                mov di, 0x{1:02x}""".format(hi(i16), lo(i16))

    def add_error(self, message):
        bc_log.error(message)
        self.errors.append(message)

    def add_variable(self, vartype, varname, funcparam = False, calltrace = ''):
        self.scope.add_variable(vartype, varname, funcparam, calltrace)

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
            raise CompilerError('Scope push error')
        if scopeoffset > 0:
            if scopeoffset < 127:
                self.emit("""
    ;depth {2}: STACKHEAD += {1}
                    {0}
                    cal :stackheadrll8""".format(self.load_a(scopeoffset & 0x7f), scopeoffset, self.scope.depth))
            else:
                self.emit("""
    ;depth {2}: STACKHEAD += {1}
                    psh cs
                    psh ci
                    {0}
                    xor a
                    cal :stackheadroll
                    pop ci
                    pop cs""".format(self.load_csci(scopeoffset), scopeoffset, self.scope.depth))
        bc_log.trace("PUSH SCOPE (startoffset={0}, depth={1}, caller={2})".format(self.scope.startoffset, self.scope.depth, caller))

    def pop_scope(self, caller):
        oldscope = self.scope
        self.scope = self.scope.prev_scope
        if self.scope is None:
            raise CompilerError('Scope none error')
        scopeoffset = oldscope.startoffset - self.scope.startoffset
        bc_log.trace("POP SCOPE (startoffset={0}, offset={1}, diff={2}, depth={3}, caller={4})".format(self.scope.startoffset, self.scope.offset, scopeoffset, self.scope.depth, caller))
        if scopeoffset < 0:
            raise CompilerError('Scope pop error')
        self.emit_stackhead_down(scopeoffset, self.scope.depth)

    def emit_stackhead_down(self, scopeoffset, depth):
        '''Emit STACKHEAD -= scopeoffset (nothing for 0). csci is preserved, so a return value survives.'''
        if scopeoffset > 0:
            if scopeoffset < 127:
                self.emit("""
    ;depth {2}: STACKHEAD -= {1}
                    {0}
                    cal :stackheadrll8""".format(self.load_a(scopeoffset | 0x80), scopeoffset, depth))
            else:
                self.emit("""
    ;depth {2}: STACKHEAD -= {1}
                    psh cs
                    psh ci
                    {0}
                    mov a, 0x01
                    cal :stackheadroll
                    pop ci
                    pop cs""".format(self.load_csci(scopeoffset), scopeoffset, depth))

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

    def begin_chunk(self, name):
        '''Starts the chunk of one function: its code and the strings created while emitting it.'''
        self.chunks.append({'name': name, 'code': [len(self.basm), None], 'data': [len(self.data), None]})

    def end_chunk(self):
        chunk = self.chunks[-1]
        chunk['code'][1] = len(self.basm)
        chunk['data'][1] = len(self.data)

    def link_functions(self, entry):
        '''Keeps only the function chunks reachable from the entry code by :label references.

        Every function was already emitted (label numbering and errors as without this step); a chunk
        is kept when kept text references a label it defines (its F... label, jump labels, strings or
        labels in its asm strings). Text outside the chunks is kept. Kept chunks stay in source order.'''
        if len(self.chunks) == 0:
            return
        code_parts = []  # (chunk index or None for text outside chunks, text)
        pos = 0
        for index, chunk in enumerate(self.chunks):
            start, end = chunk['code']
            code_parts.append((None, self.basm[pos:start]))
            code_parts.append((index, self.basm[start:end]))
            pos = end
        code_parts.append((None, self.basm[pos:]))

        owner = {}
        chunk_refs = []
        for index, chunk in enumerate(self.chunks):
            text = self.basm[chunk['code'][0]:chunk['code'][1]] + '\n' + self.data[chunk['data'][0]:chunk['data'][1]]
            defined, referenced = asm_labels(text)
            for label in defined:
                owner.setdefault(label, index)
            chunk_refs.append(referenced)

        pending = set(asm_labels(entry)[1])
        for index, text in code_parts:
            if index is None:
                pending |= asm_labels(text)[1]
        kept = set()
        while pending:
            label = pending.pop()
            index = owner.get(label)
            if index is None or index in kept:
                continue
            kept.add(index)
            pending |= chunk_refs[index]

        self.basm = ''.join(text for index, text in code_parts if index is None or index in kept)
        data = []
        pos = 0
        for index, chunk in enumerate(self.chunks):
            start, end = chunk['data']
            data.append(self.data[pos:start])
            if index in kept:
                data.append(self.data[start:end])
            pos = end
        data.append(self.data[pos:])
        self.data = ''.join(data)
        for index, chunk in enumerate(self.chunks):
            if index not in kept:
                bc_log.trace('Dropped unused function {0}'.format(chunk['name']))

    def add_data_segment(self):
        if len(self.data) > 0:
            self.emit("""
;>>>>>>>>>>DATA SEGMENT<<<<<<<<<<<<<""")
            self.emit(self.data)

    def add_stdlib(self):
        '''Appends the runtime: only the fragments referenced by the kept output plus the closure of
        their declared dependencies, in template order; then the heap/stack head data and sys_codeend.'''
        owner = {}
        fragments = {}
        for fragment in runtime_fragments:
            fragments[fragment.name] = fragment
            for label in asm_labels(fragment.text)[0]:
                owner.setdefault(label, fragment.name)
        pending = [owner[label] for label in asm_labels(self.basm)[1] if label in owner]
        kept = set()
        while pending:
            name = pending.pop()
            if name not in kept:
                kept.add(name)
                pending.extend(fragments[name].deps)
        self.emit(runtime_banner)
        self.emit(runtime_head)
        for fragment in runtime_fragments:
            if fragment.name in kept:
                self.emit(fragment.text.format(STACKHEAD, HEAPHEAD))
            else:
                bc_log.trace('Dropped unused runtime routine {0}'.format(fragment.name))
        self.emit(runtime_tail.format(STACKHEAD, HEAPHEAD, hi(self.heap_segment_addr), lo(self.heap_segment_addr)))
        # End-of-image label on the first assert line (costs no bytes), then the optional #codelimit assert
        self.emit('sys_codeend: .assert :sys_codeend < 0x{0:04x}\n'.format(self.heap_segment_addr))
        if self.code_limit_addr is not None:
            self.emit('.assert :sys_codeend < 0x{0:04x}\n'.format(self.code_limit_addr))
        
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
        if context.hint_loaddsdi:
            context.emit("""
                {0}""".format(context.load_dsdi(self.i16)))
        else:
            context.emit("""
                {0}""".format(context.load_csci(self.i16)))

@dataclass
class EXPRESSION_CONST_STR(Instruction):
    value: str

    def __str__(self):
        return 'CONST("{0}")'.format(self.value)

    def emit(self, context):
        label = context.emit_data(self.value)
        if context.hint_loaddsdi:
            context.emit("""
                .mv dsdi, :{0}""".format(label))
        else:
            context.emit("""
                .mv csci, :{0}""".format(label))
        
@dataclass
class EXPRESSION_TERM(Instruction):
    term : object

    def __str__(self):
        return "TERM({})".format(self.term)

    def emit(self, context: Context):
        bc_log.trace('TERM {0}'.format(self.term))
        if isinstance(self.term, str):
            var = context.get_variable(self.term)
            bc_log.trace('TERM {0} IS VAR {1}'.format(self.term, var))
            offset = var['offset']

            if abs(offset) < 127:
                offs8 = offset
                if (offset < 0):
                    offs8 = -offs8 | 0x80

                varget = 'stackvar8gt16'
                if var['type'] == 'byte':
                    varget = 'stackvar8gt8'
                
                context.emit("""
                {0}
                cal :{1}""".format(context.load_a(offs8), varget))
                return
            
            varget = 'stackvarget16'
            if var['type'] == 'byte':
                varget = 'stackvarget8'
            
            oper = 'xor a'
            if offset < 0:
                oper = 'mov a, 0x01'
                offset = -offset

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
                mov ci, f
                and csci, 0x0001""")
        elif self.operator == '~':
            self.operand.emit(context)
            context.emit("""
                not csci""")
        else:
            context.add_error(
                "Unknown unary operator '{0}'".format(self.operator))


oper2lib = {
    '+': 'add',
    '-': 'sub',
    '*': 'mul',
    '/': 'div',
    '%': 'mod',
    '=': None,
    '>=': None,
    '!=': None,
    '<=': None,
    '>': None,
    '<': None,
    '&&': None,
    '||': None,
    '&' : None,
    '|' : None,
    '<<': None,
    '>>': None
}

opercommutative = {
    '+': True,
    '-': False,
    '*': True,
    '/': False,
    '%': False,
    '=': True,
    '>=': False,
    '!=': True,
    '<=': False,
    '>': False,
    '<': False,
    '&&': True,
    '||': True,
    '&' : True,
    '|' : True,
    '<<': False,
    '>>': False
}

def isTermWithConst(obj):
    if hasattr(obj, 'operand1'):
        return len(obj.arguments)==0 and isTermWithConst(obj.operand1)
    elif hasattr(obj, 'term'):
        return isTermWithConst(obj.term)
    elif hasattr(obj, 'i16'):
        return True
    elif hasattr(obj, 'value') and obj.__str__().startswith('CONST("'):
        return True
    return False

def isTermWithConstNumber(obj, value):
    if hasattr(obj, 'operand1'):
        return len(obj.arguments)==0 and isTermWithConstNumber(obj.operand1, value)
    elif hasattr(obj, 'term'):
        return isTermWithConstNumber(obj.term, value)
    elif hasattr(obj, 'i16'):
        return obj.i16 == value
    return False

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
            if elem[0] not in oper2lib or elem[0] not in opercommutative:
                raise CompilerError("Unknown binary operator '{0}'".format(elem[0]))
            if opercommutative[elem[0]]:
                if(isTermWithConst(elem[1])):
                    context.hint_loaddsdi = True
                    elem[1].emit(context)
                    context.hint_loaddsdi = False
                else:
                    context.emit("""
                        psh cs
                        psh ci""")
                    elem[1].emit(context)
                    context.emit("""
                        pop di
                        pop ds""")
            else:
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
                if not self.logic(context, elem[0], elem[1]):
                    raise CompilerError("Unknown binary operator '{0}'".format(elem[0]))
                continue
            context.emit("""
                {0} csci, dsdi""".format(lib))

    def logic(self, context, oper, arg):
        if oper == '=':
            context.emit("""
                cal :eq16
                mov cs, 0x00
                mov ci, a""")
            return True
        if oper == '>=':
            if isTermWithConstNumber(arg, 0):
                context.emit("""
                    mov cs, 0x00
                    mov ci, 0x01""")
            else:
                context.emit("""
                    cal :gteq16
                    mov cs, 0x00
                    mov ci, a""")
            return True
        if oper == '!=':
            if not isTermWithConstNumber(arg, 0):
                context.emit("""
                    cal :eq16
                    mov cs, 0x00
                    dec a
                    mov ci, a""")
            return True
        if oper == '<': # a < b    = !(a >= b)
            context.emit("""
                cal :gteq16
                dec a
                mov cs, 0x00
                mov ci, a""")
            return True
        if oper == '>': 
            if not isTermWithConstNumber(arg, 0):
                context.emit("""
                    cal :gt16
                    mov cs, 0x00
                    mov ci, a""")
            return True
        if oper == '<=': # a <= b    = !(a > b)
            context.emit("""
                cal :gt16
                dec a
                mov cs, 0x00
                mov ci, a""")
            return True
        if oper == '&&':
            context.emit("""
                mov a, cs
                or ci
                mov ci, f
                mov a, ds
                or di
                mov a, f
                or ci
                not a
                and 0x01
                mov cs, 0x00
                mov ci, a""")
            return True
        if oper == '||':
            context.emit("""
                or csci, dsdi""")
            return True
        if oper == '&':
            context.emit("""
                and csci, dsdi""")
            return True
        if oper == '|':
            context.emit("""
                or csci, dsdi""")
            return True
        if oper == '<<':
            context.emit("""
                shl csci, dsdi""")
            return True
        if oper == '>>':
            context.emit("""
                shr csci, dsdi""")
            return True
        return False

@dataclass
class VARIABLE_DECLARATION(Instruction):
    vartype: str
    varname: str

    def __str__(self):
        return '{0} {1};'.format(self.vartype, self.varname)

    def emit(self, context):
        bc_log.trace('{0} {1};'.format(self.vartype, self.varname))
        context.add_variable(self.vartype, self.varname, 'VAR DECL')

@dataclass
class VARIABLE_ASSIGNEMENT(Instruction):
    varname: str
    expr: object

    def __str__(self):
        return '{0}={1};'.format(self.varname, self.expr)

    def emit(self, context: Context, funcCall = False):
        bc_log.trace('{0}={1};'.format(self.varname, self.expr))
        variable_def = context.get_variable(self.varname)
        bc_log.trace('{0}'.format(variable_def))
        offset = variable_def['offset']

        if(variable_def['type'] != 'word' and variable_def['type'] != 'byte'):
            self.context.add_error('Unknown type {0} in assignment'.format(variable_def['type']))
        
        try:
            if funcCall: context.get_variable_declared_only()
            self.expr.emit(context)
        finally:
            if funcCall: context.get_variable_all()

        if abs(offset) < 127:
            offs8 = offset
            if (offset < 0):
                offs8 = -offs8 | 0x80

            varset = 'stackvar8st16'
            if(variable_def['type'] == 'byte'):
                varset = 'stackvar8st8'
            
            context.emit("""
            {0}
            cal :{1}""".format(context.load_a(offs8), varset))
            return
        
        oper = 'xor a'
        if offset < 0:
            oper = 'mov a, 0x01'
            offset = -offset

        varset = 'stackvarset16'
        if(variable_def['type'] == 'byte'):
            varset = 'stackvarset8'
        
        context.emit("""
;{2} offset {3} OPER {1}
            {0}
            {1}
            cal :{4}""".format(context.load_dsdi(offset), oper, variable_def['name'], offset, varset))



@dataclass
class CODE_BLOCK(Instruction):
    statements:list

    def __str__(self):
        return "BLOCK({0})".format(self.statements)

    def emit(self, context):
        # currscope = context.scope
        # context.push_scope('BLOCK')
        for statement in self.statements:
            statement.emit(context)
        # if currscope != context.scope:
            # context.pop_scope('BLOCK')

@dataclass
class STATEMENT_IFELSE(Instruction):
    expr:object
    code:object
    last:object

    def __str__(self):
        if self.last is None:
            return "IF({0})[{1}]".format(self.expr, self.code)
        return "IF({0})[{1}]else[{2}]".format(self.expr, self.code, self.last)

    def emit(self, context):
        self.expr.emit(context)
        label = context.get_next_label()

        context.emit("""
                mov a, cs
                or ci
                jrx z, :{0}""".format(label))
        self.code.emit(context)

        if self.last is None:
            context.emit("""
{0}:""".format(label))
        else:
            label2 = context.get_next_label()
            context.emit("""
                xor a
                jrx z, :{0}""".format(label2))
            context.emit("""
{0}:""".format(label))
            self.last.emit(context)
            context.emit("""
{0}:""".format(label2))

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
{0}:""".format(label1))
        self.expr.emit(context)
        context.emit("""
                mov a, cs
                or ci
                jrx z, :{0}""".format(label2))
        self.code.emit(context)
        context.emit("""
                xor a
                jrx z, :{0}
{1}:""".format(label1, label2))

@dataclass
class STATEMENT_ASM(Instruction):
    expr:object

    def __str__(self):
        return "ASM[{0}]".format(self.expr)

    def emit(self, context):
        context.emit("""
                {0}""".format(self.expr))

ASM_RAW_NUMBER = re.compile(r'0|[1-9][0-9]*|0x[0-9a-fA-F]+')
ASM_RAW_LABEL = re.compile(r':[A-Za-z_][A-Za-z0-9_]*')
ASM_RAW_HILO = re.compile(r'(hi|lo)[ \t]*\([ \t]*(:[A-Za-z_][A-Za-z0-9_]*)[ \t]*\)')

@dataclass
class STATEMENT_ASM_RAW(Instruction):
    """asm item, item, ...;  one .db line; items are numbers 0-255, :name, hi(:name), lo(:name)."""
    items:list

    def __str__(self):
        return "ASM_RAW[{0}]".format(", ".join(self.items))

    def emit(self, context):
        out = []
        ok = True
        for raw in self.items:
            item = raw.strip()
            if ASM_RAW_NUMBER.fullmatch(item):
                value = int(item, 16) if item.startswith('0x') else int(item)
                if value > 255:
                    context.add_error("raw asm: {0} is out of range (0-255)".format(item))
                    ok = False
                else:
                    out.append("0x{0:02x}".format(value))
            elif ASM_RAW_LABEL.fullmatch(item):
                out.append(item)
            elif ASM_RAW_HILO.fullmatch(item):
                m = ASM_RAW_HILO.fullmatch(item)
                out.append("{0}({1})".format(m.group(1), m.group(2)))
            else:
                context.add_error("raw asm: unknown item '{0}' (expected a number 0-255, :name, hi(:name) or lo(:name))".format(item))
                ok = False
        if ok:
            context.emit("""
                .db {0}""".format(", ".join(out)))

@dataclass
class STATEMENT_RETURN(Instruction):
    expr:object

    def __str__(self):
        return "RETURN({0})".format(self.expr)

    def emit(self, context):
        self.expr.emit(context)
        # Unwind every inner scope still open (depth 1 is the function's own FUNC scope, which
        # moves nothing): one STACKHEAD -= for all of them, after the value is in csci (C8).
        # Blocks open no scope today, so this emits nothing yet; it keeps return valid under #24.
        funcscope = context.scope
        while funcscope.depth > 1:
            funcscope = funcscope.prev_scope
        context.emit_stackhead_down(context.scope.startoffset - funcscope.startoffset, funcscope.depth)
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
        bc_log.trace(function_data)
        paramdata = function_data['params']
        paramstar = function_data['paramstar']
        funcname = function_data['name']

        if paramstar:
            paramname = funcname
            if len(paramname) > 10: 
                paramname = paramname[:10]
            paramname = "{0}PLEN".format(paramname)
            context.add_variable('word', paramname, True, 'FCALL PARAMSTAR')
            varassignement = VARIABLE_ASSIGNEMENT(paramname, EXPRESSION_CONSTANT(len(self.params)))
            varassignement.emit(context, True)

        paramno = 0
        for param in self.params:
            try:
                param_name = "?"
                param_data = paramdata[paramno]
                param_name = param_data['name']
                paramtype = param_data['type']
            except:
                if not paramstar:
                    context.add_error('Unrecognized function {0} parameter {1}'.format(self.function_name, param_name))
                paramtype = 'word';
                param_name = 'P{0}'.format(paramno);

            context.add_variable(paramtype, param_name, True, 'FCALL PARAM')
            varassignement = VARIABLE_ASSIGNEMENT(param_name, param)
            varassignement.emit(context, True)
            paramno += 1

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
        if function_data['paramstar']:
            paramname = function_data['name']
            if len(paramname) > 10: 
                paramname = paramname[:10]
            paramname = "{0}PLEN".format(paramname)
            context.add_variable('word', paramname, True, 'FUNC DEF PARAMSTAR')

        for param in function_data['params']:
            context.add_variable(param['type'], param['name'], True, 'FUNC DEF')

    def add_code(self, function_data, context):
        context.begin_chunk(function_data['name'])
        context.emit("""
;FUNCTION {0}
{1}""".format(function_data['name'], function_data['label'] + ":"))
        context.push_scope('FUNC')
        self.add_func_params(context, function_data)

        self.code.emit(context)
        context.pop_scope('FUNC')
        statements = self.code.statements
        if len(statements) > 0 and isinstance(statements[-1], STATEMENT_RETURN):
            context.emit("""
;END OF FUNCTION {0}""".format(function_data['name']))
        else:
            context.emit("""
                ret
;END OF FUNCTION {0}""".format(function_data['name']))
        context.end_chunk()

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

        entry = (""";MAIN ENTRYPOINT
;&STACKHEAD <- STACKHEAD + 2
                .mv dsdi, :{1}
                mov cs, 0x00
                mov ci, 0x02
                add csci, dsdi
                .mv dsdi, :{1}
                cal :poke16
;&HEAPHEAD <- {5}
                .mv dsdi, :{2}
                {4}
                cal :poke16
                cal :{0}
                {3}
;FUNCTIONS""".format(function_data['label'], STACKHEAD, HEAPHEAD, last_command, context.load_csci(context.heap_segment_addr), context.heap_segment_addr))
        context.link_functions(entry)
        context.prepend(entry)

        