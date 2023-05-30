from parsy import regex, Parser, string, seq, letter, digit
from bc81asmc_ast import *

hexstr2int = lambda x: int(x, 16)
comment = regex(r';[^\r\n]*').desc('comment')
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
accumulator = string('a').desc('accumulator')
quote = string("'")

ident = letter + (letter | digit | underscore).many().concat()
quotedstr = lexeme(quote >> regex(r"[^']*") << quote).desc('quoted string')

heximm4 = lexeme(
  (hexprefix >> regex(r'[0-9a-fA-F]'))
  .map(hexstr2int)
  .desc('hex immediate 4bit value')
)

heximm16 = lexeme(
  (hexprefix >> regex(r'[0-9a-fA-F]{4}'))
  .map(hexstr2int)
  .desc('hex immediate 16bit value')
)

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

paramdb = lexeme(quotedstr | heximm8)

mNOP = lexeme(string('nop')).map(NOP).desc('nop instruction')
mINC = lexeme(string('inc') >> sep >> accumulator)\
    .map(INC)\
    .desc('inc instruction')
mDEC = lexeme(string('dec') >> sep >> accumulator)\
    .map(DEC)\
    .desc('dec instruction')
mNOT = lexeme(string('not') >> sep >> accumulator)\
    .map(NOT)\
    .desc('not instruction')
mMOVri8 = \
    lexeme(string('mov') >> sep >>
        seq(
            lexeme(paramreg << comma),
            heximm8
        ).combine(MOVRI8)
    )\
    .desc('mov r,i8 instruction')
mMOVrr = \
    lexeme(string('mov') >> sep >>
        seq(
            lexeme(paramreg << comma),
            paramreg
        ).combine(MOVRR)
    )\
    .desc('mov r,r instruction')
mMOVrm = \
    lexeme(string('mov') >> sep >>
        seq(
            lexeme(paramreg << comma),
            hash >> (paramreg * 2).concat()
        ).combine(MOVRM)
    )\
    .desc('mov r,#r instruction')
mMOVmr = \
    lexeme(string('mov') >> sep >>
        seq(
            lexeme(hash >> (paramreg * 2).concat() << comma),
            paramreg
        ).combine(MOVMR)
    )\
    .desc('mov #r,r instruction')

mADDi8 = \
    lexeme(string('add') >> sep >> heximm8)\
    .map(lambda x: CLC_A_IMM('add', x))\
    .desc('add i8 instruction')

mADDr = \
    lexeme(string('add') >> sep >> paramreg)\
    .map(lambda x: CLC_A_R('add', x))\
    .desc('add r instruction')

mSUBi8 = \
    lexeme(string('sub') >> sep >> heximm8)\
    .map(lambda x: CLC_A_IMM('sub', x))\
    .desc('sub i8 instruction')

mSUBr = \
    lexeme(string('sub') >> sep >> paramreg)\
    .map(lambda x: CLC_A_R('sub', x))\
    .desc('sub r instruction')

mANDi8 = \
    lexeme(string('and') >> sep >> heximm8)\
    .map(lambda x: CLC_A_IMM('and', x))\
    .desc('and i8 instruction')

mANDr = \
    lexeme(string('and') >> sep >> paramreg)\
    .map(lambda x: CLC_A_R('and', x))\
    .desc('and r instruction')

mORi8 = \
    lexeme(string('or') >> sep >> heximm8)\
    .map(lambda x: CLC_A_IMM('or', x))\
    .desc('or i8 instruction')

mORr = \
    lexeme(string('or') >> sep >> paramreg)\
    .map(lambda x: CLC_A_R('or', x))\
    .desc('or r instruction')

mXORi8 = \
    lexeme(string('xor') >> sep >> heximm8)\
    .map(lambda x: CLC_A_IMM('xor', x))\
    .desc('xor i8 instruction')

mXORr = \
    lexeme(string('xor') >> sep >> paramreg)\
    .map(lambda x: CLC_A_R('xor', x))\
    .desc('xor r instruction')

mSHLi8 = \
    lexeme(string('shl') >> sep >> heximm8)\
    .map(lambda x: CLC_A_IMM('shl', x))\
    .desc('shl i8 instruction')

mSHLr = \
    lexeme(string('shl') >> sep >> paramreg)\
    .map(lambda x: CLC_A_R('shl', x))\
    .desc('shl r instruction')

mSHRi8 = \
    lexeme(string('shr') >> sep >> heximm8)\
    .map(lambda x: CLC_A_IMM('shr', x))\
    .desc('shr i8 instruction')

mSHRr = \
    lexeme(string('shr') >> sep >> paramreg)\
    .map(lambda x: CLC_A_R('shr', x))\
    .desc('shr r instruction')

logictest = lexeme(string('nz') | string('z') | string('nc') | string('c') |  \
     string('nn') | string('o') | string('no') | string('n'))

labelarg = colon + ident
jmpregargs = ((paramreg * 2)).concat()

jmpaddrarg = lexeme(jmpregargs | labelarg)
jmraddrarg = lexeme(paramreg | labelarg)

mJMP = \
    lexeme(seq(
        string('jmp') >> sep >> logictest << comma,
        jmpaddrarg).combine(JMP))\
    .desc('jmp instruction') 

mJMR = \
    lexeme(seq(
        string('jmr') >> sep >> logictest << comma,
        jmraddrarg).combine(JMR))\
    .desc('jmr instruction')

mPSH = lexeme(string('psh') >> sep >> paramreg)\
    .map(PSH)\
    .desc('psh instruction')

mPOP = lexeme(string('pop') >> sep >> paramreg)\
    .map(POP)\
    .desc('pop instruction')

mCAL = lexeme(string('cal') >> sep >> jmpaddrarg)\
    .map(CAL)\
    .desc('cal instruction')

mRET = lexeme(string('ret'))\
    .map(RET)\
    .desc('ret instruction')

inreg = lexeme(hash >> (heximm4 | paramreg))

outreg = lexeme(heximm8 | paramreg)

mIN = \
    lexeme(seq(
        string('in') >> sep >> paramreg << comma << ignore,
        inreg).combine(IN))\
    .desc('in instruction')

mOUT = \
    lexeme(seq(
        string('out') >> sep >> hash >> paramreg << comma << ignore,
        outreg).combine(OUT))\
    .desc('out instruction')

mKIL = lexeme(string('kil'))\
        .map(KIL)\
        .desc('kil instruction')

mCLC = mADDi8 | mADDr | mSUBi8 | mSUBr | mANDi8 | mANDr | mORi8 | mORr | \
       mXORi8 | mXORr | mSHLi8 | mSHLr | mSHRi8 | mSHRr

dORG = (lexeme(string('.org')) >> heximm16)\
    .map(ORG)\
    .desc('.org directive')

dDB  = (lexeme(string('.db')) >> paramdb.sep_by(comma))\
    .map(DB)\
    .desc('.db directive')

dMV  = lexeme(seq(lexeme(string('.mv')) >> lexeme((paramreg * 2).concat()) << comma,
            labelarg).combine(MV))\
        .desc('.mv directive')

dDEF = lexeme(seq(lexeme(string('.def')) >> lexeme(ident) << comma,
            heximm16).combine(DEF))\
        .desc('.def directive')

mnemonic = mNOP | mINC | mDEC | mNOT | mMOVri8 | mMOVrr | mMOVrm | mMOVmr | mCLC | mJMP | mJMR | mKIL | mCAL | mRET | mIN | mOUT | mPSH | mPOP
directive = dORG | dDB | dMV | dDEF
label = lexeme(ident << colon)
instruction = mnemonic | directive
linecomment = (ignore >> comment).map(LineComment)
line = (linecomment | (ignore >> seq(label.optional(), instruction, comment.optional()).combine(LINE))) << nl
program = Parser.many(line)
