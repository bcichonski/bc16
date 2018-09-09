from parsy import regex, Parser, whitespace, string, seq
from bc81asmc_ast import ORG, INC, DEC, MOVRI8, DEBUG

hexstr2int = lambda x: int(x, 16)
comment = regex(r';.*[^\r\n]').desc('comment')
ignore = Parser.many(whitespace).desc('whitespaces')
sep = whitespace.at_least(1)
nl = regex(r'(\r\n|\r|\n)').desc('new line')

lexeme = lambda p: p << ignore
colon = lexeme(string(':'))
comma = lexeme(string(','))
hexprefix = string('0x')
accumulator = string('a').desc('accumulator')

heximm8 = lexeme(
  (hexprefix >> regex(r'[0-9a-fA-F]{2}'))
  .map(hexstr2int)
  .desc('hex immediate 8bit value')
)

heximm16 = lexeme(
  (hexprefix >> regex(r'[0-9a-fA-F]{4}'))
  .map(hexstr2int)
  .desc('hex immediate 16bit value')
)

paramreg = (
  string('pc') | string('ss') | string('si') | string('f') | string('a') |
  string('ci') | string('cs') | string('di') | string('ds')
 ).desc('register name')

mNOP = lexeme(string('nop')).desc('nop instruction')
mINC = lexeme(string('inc') >> sep >> accumulator)\
    .map(INC)\
    .desc('inc instruction')
mDEC = lexeme(string('dec') >> sep >> accumulator)\
    .map(DEC)\
    .desc('dec instruction')
mMOVri8 = \
    lexeme(string('mov') >> sep >>
        seq(
            lexeme(paramreg << comma),
            heximm8
        ).combine(MOVRI8)
    )#\
    #.desc('mov r,i8 instruction')
dORG = lexeme(string('org') >> sep >> heximm16)\
    .map(ORG)\
    .desc('org directive')

mnemonic = mNOP | mINC | mDEC | mMOVri8
directive = dORG
instruction = mnemonic | directive
line = ignore >> instruction << comment.optional()
program = Parser.many(line)
