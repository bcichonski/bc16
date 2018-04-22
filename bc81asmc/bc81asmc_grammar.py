from parsec import *

whitespace = regex(r'\s*', re.MULTILINE)
comment = regex(r';.*')
ignore = many((whitespace | comment))

lexeme = lambda p: p << ignore
colon = lexeme(string(':'))
comma = lexeme(string(','))
hexprefix = lexeme(string('0x'))
heximm8 = lexeme(regex(r'[0-9a-fA-F]{2}')).parsecmap(int)
heximm16 = lexeme(regex(r'[0-9a-fA-F]{4}')).parsecmap(int)

param_imm8 = hexprefix >> heximm8
