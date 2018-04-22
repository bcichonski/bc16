import unittest

from parsec import *
from bc81asmc_grammar import *

class TestGrammar(unittest.TestCase):
    '''Test the implementation of asm parser.'''

    '''def test_param_imm8(self):
        self.assertEqual(
            param_imm8.parse('0x8b'),
            0x8b)'''

    def test_param_heximm8(self):
        self.assertEqual(
            heximm8.parse('8b'),
            0x8b)

if __name__ == '__main__':
    unittest.main()
