import unittest

from parsy import *
from bc_grammar import *

Debug = True

class TestGrammar(unittest.TestCase):
    '''Test the implementation of ast b language parser.'''

    def test_expression_const_hex(self):
        val = constnumber.parse('0x8b')
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'CONST(0x008b)')

    def test_expression_const_dec(self):
        val = constnumber.parse('128')
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'CONST(0x0080)')

    def test_expression_const_char(self):
        val = constnumber.parse("'A'")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'CONST(0x0041)')

    def test_expression_unary_addr(self):
        val = expression_unary.parse("&0xabcd")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'CONST(0xabcd) &')

    def test_expression_binary_add(self):
        val = expression_sum.parse("10 + 0xf000")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'CONST(0x000a) CONST(0xf000) +')

    def test_expression_binary(self):
        val = expression_factor.parse("2 * 3")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'CONST(0x0002) CONST(0x0003) *')

    def test_expression_unary(self):
        val = expression_unary.parse("&2")
        if Debug: 
            print("val={0}".format(val))
            print(val)
        self.assertEqual(
            "{0}".format(val),
            'CONST(0x0002) &')

    def test_expression_full(self):
        val = expression.parse("1 + (2 * 3)")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'CONST(0x0001) CONST(0x0002) CONST(0x0003) * +')

    def test_expression_const(self):
        val = expression.parse("1")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'CONST(0x0001)')

if __name__ == '__main__':
    unittest.main()