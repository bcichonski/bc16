import unittest

from parsy import *
from bc81asmc_grammar import *

debug = False

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

    def test_directive_org(self):
        val = directive.parse('org 0x0100')
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

    def test_inc_reg(self):
        self.assertEqual(
            mnemonic.parse('inc a'),
            INC('a'))

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

if __name__ == '__main__':
    unittest.main()
