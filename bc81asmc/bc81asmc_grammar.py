from parsy import regex, Parser, whitespace, string
from bc81asmc_ast import ORG

hexstr2int = lambda x: int(x, 16)
comment = regex(r';.*[^\n]').desc('comment')
ignore = Parser.many(whitespace).desc('whitespaces')
sep = whitespace.at_least(1)

lexeme = lambda p: p << ignore
colon = lexeme(string(':'))
comma = lexeme(string(','))
hexprefix = string('0x')

heximm8 = lexeme((hexprefix >> regex(r'[0-9a-fA-F]{2}')).map(hexstr2int))
heximm16 = lexeme((hexprefix >> regex(r'[0-9a-fA-F]{4}')).map(hexstr2int))

mNOP = lexeme(string('nop'))
dORG = (lexeme(string('org') >> sep >> heximm16)).map(lambda x: ORG(x))

mnemonic = mNOP
directive = dORG
instruction = mnemonic | directive
line = (ignore >> instruction) << comment
program = Parser.many(line)
