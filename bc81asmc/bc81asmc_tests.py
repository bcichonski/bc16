import unittest

from parsy import *
from bc81asmc_grammar import *

debug = True

class TestGrammar(unittest.TestCase):
    '''Test the implementation of ast parser.'''

    def test_hex_imm8(self):
        self.assertEqual(
            heximm8.parse('0x8b'),
            0x8b)

    def test_comment(self):
        self.assertEqual(
            comment.parse('; everything can have comment'),
            '; everything can have comment')

    def test_ignore_spaces(self):
        self.assertEqual(
            ignore.parse('   '),
            ['   '])

    def test_mnemonic_nop(self):
        self.assertEqual(
            mnemonic.parse('nop'),
            NOP('nop'))

    def test_paramdb_string(self):
        val = paramdb.parse("'quotedstring'")
        if debug:
            print(val)
        self.assertEqual(
            val,
            "quotedstring")

    def test_paramdb_heximm8(self):
        val = paramdb.parse("0xaf")
        if debug:
            print(val)
        self.assertEqual(
            val,
            0xaf)

    def test_directive_db(self):
        val = dDB.parse(".db 'quoted', 0xff, 'new', 0x00")
        if debug:
            print(val)
        self.assertEqual(
            val,
            DB(['quoted', 0xff, 'new', 0x00]))

    def test_directive_org(self):
        val = directive.parse('.org 0x0100')
        if debug:
            print(val)
        self.assertEqual(
            val,
            ORG(0x0100))

    def test_line_with_label_spaces_and_comment(self):
        res = line.parse(' label:  nop ;comment')
        self.assertEqual(
            res,
            NOP('nop'))
        self.assertEqual(res.label, 'label')

    def test_line_with_spaces_and_comment(self):
        res = line.parse('         nop ;comment')
        self.assertEqual(
            res,
            NOP('nop'))
        self.assertFalse(hasattr(res, 'label'))

    def test_inc_a(self):
        self.assertEqual(
            mnemonic.parse('inc a'),
            INC('a'))

    def test_dec_a(self):
        self.assertEqual(
            mnemonic.parse('dec a'),
            DEC('a'))

    def test_not_a(self):
        self.assertEqual(
            mnemonic.parse('not a'),
            NOT('a'))

    def test_mov_r_i8(self):
        self.assertEqual(
            mMOVri8.parse('mov si, 0xff'),
            MOVRI8('si',0xff))

    def test_mov_r_r(self):
        self.assertEqual(
            mMOVrr.parse('mov cs, di'),
            MOVRR('cs','di'))

    def test_mov_r_m(self):
        self.assertEqual(
            mMOVrm.parse('mov ss, #dsdi'),
            MOVRM('ss','dsdi'))

    def test_mov_m_r(self):
        self.assertEqual(
            mMOVmr.parse('mov #dsdi, a'),
            MOVMR('dsdi', 'a'))

    def test_add_i8(self):
        self.assertEqual(
            mADDi8.parse('add 0xad'),
            CLC_A_IMM('add', 0xad))

    def test_add_r(self):
        self.assertEqual(
            mADDr.parse('add cs'),
            CLC_A_R('add', 'cs'))

    def test_sub_i8(self):
        self.assertEqual(
            mSUBi8.parse('sub 0xaf'),
            CLC_A_IMM('sub', 0xaf))

    def test_sub_r(self):
        self.assertEqual(
            mSUBr.parse('sub a'),
            CLC_A_R('sub', 'a'))

    def test_and_i8(self):
        self.assertEqual(
            mANDi8.parse('and 0xaa'),
            CLC_A_IMM('and', 0xaa))

    def test_and_r(self):
        self.assertEqual(
            mANDr.parse('and di'),
            CLC_A_R('and', 'di'))

    def test_or_i8(self):
        self.assertEqual(
            mORi8.parse('or 0x1d'),
            CLC_A_IMM('or', 0x1d))

    def test_or_r(self):
        self.assertEqual(
            mORr.parse('or ds'),
            CLC_A_R('or', 'ds'))

    def test_xor_i8(self):
        self.assertEqual(
            mXORi8.parse('xor 0x10'),
            CLC_A_IMM('xor', 0x10))

    def test_xor_r(self):
        self.assertEqual(
            mXORr.parse('xor cs'),
            CLC_A_R('xor', 'cs'))

    def test_shl_i8(self):
        self.assertEqual(
            mSHLi8.parse('shl 0x05'),
            CLC_A_IMM('shl', 0x05))

    def test_shl_r(self):
        self.assertEqual(
            mSHLr.parse('shl cs'),
            CLC_A_R('shl', 'cs'))

    def test_shr_i8(self):
        self.assertEqual(
            mSHRi8.parse('shr 0x04'),
            CLC_A_IMM('shr', 0x04))

    def test_shr_r(self):
        self.assertEqual(
            mSHRr.parse('shr ci'),
            CLC_A_R('shr', 'ci'))

if __name__ == '__main__':
    unittest.main()
