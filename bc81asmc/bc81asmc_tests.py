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
            'nop')

    def test_directive_org(self):
        val = directive.parse('org 0x0100')
        if debug:
            print(val)
        self.assertEqual(
            val,
            ORG(0x0100))

    def test_line_with_spaces_and_comment(self):
        self.assertEqual(
            line.parse('   nop ;comment'),
            'nop')

    def test_inc_reg(self):
        self.assertEqual(
            mnemonic.parse('inc a'),
            INC('a'))

if __name__ == '__main__':
    unittest.main()
