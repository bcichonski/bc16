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
            'TERM(CONST(0xabcd)) &')

    def test_expression_binary_add(self):
        val = expression_sum.parse("10 + 0xf000")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'TERM(CONST(0x000a)) TERM(CONST(0xf000)) +')

    def test_expression_binary(self):
        val = expression_factor.parse("2 * 3")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'TERM(CONST(0x0002)) TERM(CONST(0x0003)) *')

    def test_expression_unary(self):
        val = expression_unary.parse("&2")
        if Debug: 
            print("val={0}".format(val))
            print(val)
        self.assertEqual(
            "{0}".format(val),
            'TERM(CONST(0x0002)) &')

    def test_expression_full(self):
        val = expression.parse("1 + (2 * 3)")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'TERM(CONST(0x0001)) TERM(TERM(CONST(0x0002)) TERM(CONST(0x0003)) *) +')

    def test_expression_const(self):
        val = expression.parse("1")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'TERM(CONST(0x0001))')

    def test_expression_variable(self):
        val = code_block.parse("""{
            word var;
            var <- var;
        }""")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            "BLOCK([VARIABLE_DECLARATION(vartype='word', varname='var'), VARIABLE_ASSIGNEMENT(varname='var', expr=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_TERM(term='var'), arguments=[]), arguments=[]), arguments=[]), arguments=[]))])")

    def test_variable_declaration(self):
        val = statement.parse("word variable;")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            'word variable;')

    def test_code_block(self):
        val = code_block.parse("""{
                byte variable;
            }""")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            "BLOCK([VARIABLE_DECLARATION(vartype='byte', varname='variable')])")

    def test_if(self):
        val = statement_if.parse("""if(1)
            {
                byte variable;
            }""")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            "IF(TERM(CONST(0x0001)))[BLOCK([VARIABLE_DECLARATION(vartype='byte', varname='variable')])]")

    def test_while(self):
        val = statement_while.parse("""while(1)
            {
                byte variable;
            }""")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            "WHILE(TERM(CONST(0x0001)))[BLOCK([VARIABLE_DECLARATION(vartype='byte', varname='variable')])]")

    def test_function_def(self):
        self.maxDiff = None
        val = function_declaration.parse("""word function(byte param1, word param2)
        { 
            byte var; 
            var <- 1;
            return var;
        }""")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual("{0}".format(val),
        "FUNCTION function([VARIABLE_DECLARATION(vartype='byte', varname='param1'), VARIABLE_DECLARATION(vartype='word', varname='param2')])->word[BLOCK([VARIABLE_DECLARATION(vartype='byte', varname='var'), VARIABLE_ASSIGNEMENT(varname='var', expr=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_TERM(term=EXPRESSION_CONSTANT(i16=1)), arguments=[]), arguments=[]), arguments=[]), arguments=[])), STATEMENT_RETURN(expr=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_TERM(term='var'), arguments=[]), arguments=[]), arguments=[]), arguments=[]))])]")

    def test_program(self):
        val = program.parse("""byte main() {
            word variable; 
            byte second;
        }""")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual(
            "{0}".format(val),
            "[FUNCTION_DECLARATION(return_type='byte', function_name='main', params=[], star=None, code=CODE_BLOCK(statements=[VARIABLE_DECLARATION(vartype='word', varname='variable'), VARIABLE_DECLARATION(vartype='byte', varname='second')]))]")

    def test_function_call(self):
        self.maxDiff = None
        val = expression.parse("""function(1, 2+3)""")
        if Debug: 
            print("val={0}".format(val))
        self.assertEqual("{0}".format(val),
        "TERM(FUNCTION_CALL[function([EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_TERM(term=EXPRESSION_CONSTANT(i16=1)), arguments=[]), arguments=[]), arguments=[]), arguments=[]), EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_BINARY(operand1=EXPRESSION_TERM(term=EXPRESSION_CONSTANT(i16=2)), arguments=[]), arguments=[['+', EXPRESSION_BINARY(operand1=EXPRESSION_TERM(term=EXPRESSION_CONSTANT(i16=3)), arguments=[])]]), arguments=[]), arguments=[])])])")


if __name__ == '__main__':
    unittest.main()