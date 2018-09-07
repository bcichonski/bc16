import unittest

from parsy import *
from bc81asmc_grammar import heximm8

class TestGrammar(unittest.TestCase):
    '''Test the implementation of asm parser.'''

    def test_hex_imm8(self):
        self.assertEqual(
            heximm8.parse('0x8b'),
            0x8b)

    '''def test_param_heximm8(self):

        self.assertEqual(
            heximm8_sequence().parse('8b,00'),
            0x8b)'''

if __name__ == '__main__':
    unittest.main()
