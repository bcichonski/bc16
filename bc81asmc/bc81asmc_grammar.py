from parsy import regex, Parser, whitespace, string

hexstr2int = lambda x: int(x, 16)
comment = regex(r';.*').desc('comment')
ignore = Parser.many(whitespace | comment).desc('ignored string')

lexeme = lambda p: p << ignore
colon = lexeme(string(':'))
comma = lexeme(string(','))
hexprefix = string('0x')

heximm8 = lexeme(hexprefix >> regex(r'[0-9a-fA-F]{2}')).map(hexstr2int)
heximm16 = lexeme(hexprefix >> regex(r'[0-9a-fA-F]{4}')).map(hexstr2int)
