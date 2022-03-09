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
hash = string('#')
underscore = string('_')
hexprefix = string('0x')
singlequote = string("'")
doublequote = string('"')

ident = letter + (letter | digit | underscore).many().concat()
quotedstr = lexeme(doublequote >> regex(r'[^"]*') << doublequote).desc('quoted string')
anychar = regex(r'.').desc('any single character')

decnumber = regex(r'[1-9][0-9]*').map(str2int).desc('byte')
hexnumber = hexprefix >> regex(r'[1-9a-fA-F][0-9a-fA-F]*').map(hexstr2int).desc('word')
singlechar = lexeme(singlequote >> anychar << singlequote).map(chr2int).desc('char')

constnumber = lexeme(decnumber | hexnumber | singlechar)\
    .map(EXPRESSION_CONSTANT)\
    .desc("Constant expression")


unary_operator = lexeme(string('&') | string('!'))
binary_factor = lexeme(string('*') | string('/'))
binary_sum = lexeme(string('+') | string('-'))
binary_comp = lexeme(string('>') | string('<'))
binary_eq = lexeme(string('=') | string('!='))
expression = forward_declaration()
expression_nested = string('(') >> ignore >> expression << ignore << string(')').desc('nested expression')
expression_term = constnumber | ident | expression_nested
expression_unary_act = seq(unary_operator, expression).combine(EXPRESSION_UNARY).desc('unary expression')
expression_unary = expression_unary_act | expression_term
expression_factor = seq(operand1 = expression_unary, arguments = seq(binary_factor, expression_unary).many()).combine_dict(EXPRESSION_BINARY).desc('binary expression factor')
expression_sum = seq(operand1 = expression_factor, arguments = seq(binary_sum, expression_factor).many()).combine_dict(EXPRESSION_BINARY).desc('binary expression sum')
expression_comparision = seq(operand1 = expression_sum, arguments = seq(binary_comp, expression_factor).many()).combine_dict(EXPRESSION_BINARY).desc('binary expression comparision')
expression_equality = seq(operand1 = expression_comparision, arguments = seq(binary_eq, expression_comparision).many()).combine_dict(EXPRESSION_BINARY).desc('binary expression equality')
expression.become(expression_equality)

program = expression