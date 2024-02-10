from parsy import forward_declaration, regex, Parser, string, seq, letter, digit
from bc_ast import *

chr2int = lambda x: ord(x)
str2int = lambda x: int(x)
hexstr2int = lambda x: int(x, 16)
comment = regex(r'//[^\r\n]*').desc('comment')
whitespace = regex(r'[ \t]').desc('whitespace')
whitespaces = regex(r'[ \t]*').desc('whitespaces')
ignore = whitespaces
sep = whitespace.at_least(1)
nl = regex(r'(\r\n|\r|\n)').desc('new line')

lexeme = lambda p: p << ignore
colon = lexeme(string(':'))
comma = lexeme(string(','))
semicolon = lexeme(string(';'))
hash = string('#')
underscore = string('_')
hexprefix = string('0x')
singlequote = string("'")
doublequote = string('"')
assignement = lexeme(string('<-'))
leftbrace = lexeme(string('{'))
rightbrace = lexeme(string('}'))
leftpar = lexeme(string('('))
rightpar = lexeme(string(')'))

ident = lexeme(letter + (letter | digit | underscore).many().concat())
quotedstr = lexeme(doublequote >> regex(r'[^"]*') << doublequote).desc('quoted string')
anychar = regex(r'.').desc('any single character')

decnumber = regex(r'[1-9][0-9]*|0').map(str2int).desc('byte')
hexnumber = hexprefix >> regex(r'[0-9a-fA-F]*').map(hexstr2int).desc('word')
singlechar = lexeme(singlequote >> anychar << singlequote).map(chr2int).desc('char')

constnumber = lexeme(hexnumber | decnumber | singlechar)\
    .map(EXPRESSION_CONSTANT)\
    .desc("Constant expression")

conststring = lexeme(quotedstr)\
    .map(EXPRESSION_CONST_STR)\
    .desc("Constant string")

unary_operator = lexeme(string('#') | string('!'))
binary_factor = lexeme(string('*') | string('/'))
binary_sum = lexeme(string('+') | string('-'))
binary_comp = lexeme(string('<=') | string('>=') | string('>') | string('<'))
binary_eq = lexeme(string('=') | string('!='))
expression = forward_declaration()
expression_functioncall = seq(function_name = ident, params = ignore >> leftpar >> ignore >> nl.optional() >> ignore >> expression.sep_by(comma) << ignore << nl.optional() << ignore << rightpar << ignore).combine_dict(EXPRESSION_CALL).desc("function call")
expression_nested = string('(') >> ignore >> expression << ignore << string(')').desc('nested expression')
expression_term = (conststring | constnumber | expression_functioncall | ident | expression_nested).map(EXPRESSION_TERM).desc('term expression')
expression_unary_act = seq(unary_operator, expression).combine(EXPRESSION_UNARY).desc('unary expression')
expression_unary = expression_unary_act | expression_term
expression_factor = seq(operand1 = expression_unary, arguments = seq(binary_factor, expression_unary).many()).combine_dict(EXPRESSION_BINARY).desc('binary expression factor')
expression_sum = seq(operand1 = expression_factor, arguments = seq(binary_sum, expression_factor).many()).combine_dict(EXPRESSION_BINARY).desc('binary expression sum')
expression_comparision = seq(operand1 = expression_sum, arguments = seq(binary_comp, expression_factor).many()).combine_dict(EXPRESSION_BINARY).desc('binary expression comparision')
expression_equality = seq(operand1 = expression_comparision, arguments = seq(binary_eq, expression_comparision).many()).combine_dict(EXPRESSION_BINARY).desc('binary expression equality')
expression.become(expression_equality)

type = lexeme(string('word') | string('byte'))
variable_declaration = seq(vartype = type, varname = ident).combine_dict(VARIABLE_DECLARATION).desc('variable declaration')
variable_assignement = seq(varname = ident << assignement, expr = expression).combine_dict(VARIABLE_ASSIGNEMENT).desc('variable assignement')

statement = forward_declaration()
code_block = (leftbrace >> nl.optional() >> ignore >> statement.many() << nl.optional() << ignore << rightbrace << nl.optional()).map(CODE_BLOCK).desc('code block')
statement_comment = comment.map(STATEMENT_COMMENT).desc('comment')
statement_expression = expression << semicolon << nl.optional()
statement_variables = (variable_declaration | variable_assignement) << semicolon << nl.optional()
statement_if = seq(expr = lexeme(string('if')) >> leftpar >> expression << rightpar << nl.optional(), code = ignore >> code_block).combine_dict(STATEMENT_IF).desc('if statement')
statement_while = seq(expr = lexeme(string('while')) >> leftpar >> expression << rightpar << nl.optional(), code = ignore >> code_block).combine_dict(STATEMENT_WHILE).desc('while statement')
statement_return = (lexeme(string('return')) >> expression << semicolon << nl.optional()).map(STATEMENT_RETURN).desc('return statement')
statement_asm = (lexeme(string('asm')) >> quotedstr << semicolon << nl.optional()).map(STATEMENT_ASM).desc('asm statement')
statement.become(ignore >> (statement_variables | statement_if | statement_while | statement_return | statement_asm | statement_expression | statement_comment) << nl.optional())
function_params = variable_declaration.sep_by(comma)
function_declaration = seq(return_type = type, function_name = ident, params = leftpar >> function_params << rightpar << semicolon.optional() << nl.optional() << ignore, \
    star = lexeme(string('***')).optional() << semicolon.optional() << nl.optional() << ignore, code = nl.optional() >> ignore >> code_block.optional()) \
    .combine_dict(FUNCTION_DECLARATION).desc("function declaration")
globalvar_declaration = variable_declaration.desc("global variable declaration")

global_item = function_declaration | globalvar_declaration

program = global_item.many().map(PROGRAM).desc("b program")