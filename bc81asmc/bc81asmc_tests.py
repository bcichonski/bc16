import unittest

from parsy import *
from bc81asmc_grammar import *

class TestGrammar(unittest.TestCase):
    '''Test the implementation of asm parser.'''

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
        self.assertEqual(
            directive.parse('org 0x0100'),
            ORG(0x0100))

    def test_line_with_spaces_and_comment(self):
        self.assertEqual(
            line.parse('   nop ;comment'),
            'nop')


if __name__ == '__main__':
    unittest.main()
