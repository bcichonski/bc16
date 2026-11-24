"""The assembler takes its numbers and name lists from the shared ISA table (src/bc8183_isa.py)."""
import unittest

import parsy

import bc8183_isa as isa
import bc81asmc_ast as asm_ast
import bc81asmc_grammar as grammar


def names_matching(parser, names, suffix=''):
    return [name for name in names if _parses(parser, name + suffix)]


def _parses(parser, text):
    try:
        return parser.parse(text) == text
    except parsy.ParseError:
        return False


class TestGrammarNamesAreTheIsaLists(unittest.TestCase):
    def test_every_register_name_parses(self):
        for name in isa.REGISTER_NAMES:
            self.assertEqual(grammar.paramreg.parse(name), name)

    def test_register_parser_accepts_nothing_else(self):
        for name in ('b', 'x', 'csci', 'af'):
            with self.assertRaises(parsy.ParseError):
                grammar.paramreg.parse(name)

    def test_every_condition_name_parses(self):
        for name in isa.CONDITION_NAMES:
            self.assertEqual(grammar.logictest.parse(name), name)

    def test_conditions_are_the_isa_conditions(self):
        self.assertEqual(sorted(isa.CONDITION_NAMES), sorted(isa.CONDITIONS))

    def test_condition_longest_first(self):
        names = isa.CONDITION_NAMES
        for i, name in enumerate(names):
            for shorter in names[:i]:
                self.assertFalse(name.startswith(shorter),
                                 '{0} comes after its prefix {1}'.format(name, shorter))

    def test_every_8bit_alu_op_parses_both_forms(self):
        for name in isa.ALU8_BINARY_OP_NAMES:
            imm = grammar.mCLC.parse(name + ' 0x12')
            self.assertEqual((imm.oper, imm.imm), (name, 0x12))
            reg = grammar.mCLC.parse(name + ' ci')
            self.assertEqual((reg.oper, reg.reg), (name, 'ci'))

    def test_every_16bit_alu_op_parses(self):
        for name in isa.ALU16_BINARY_OP_NAMES:
            node = grammar.mCLC.parse(name + ' csci, dsdi')
            self.assertEqual((node.oper, node.reg, node.reg2), (name, 'csci', 'dsdi'))
            operand = '0x12' if name in isa.ALU16_SHIFT_OP_NAMES else '0x1234'
            node = grammar.mCLC.parse(name + ' csci, ' + operand)
            self.assertEqual((node.oper, node.reg), (name, 'csci'))

    def test_unary_ops_parse(self):
        for name in isa.ALU8_UNARY_OP_NAMES:
            self.assertEqual(grammar.mnemonic.parse(name + ' a'), grammar.mnemonic.parse(name + ' a'))
            self.assertEqual(type(grammar.mnemonic.parse(name + ' a')).__name__, name.upper())
        for name in isa.ALU16_UNARY_OP_NAMES:
            self.assertEqual(type(grammar.mnemonic.parse(name + ' csci')).__name__, name.upper() + '16')


class TestNamesResolveToIsaNumbers(unittest.TestCase):
    def test_register_numbers(self):
        for name, number in isa.REGISTERS.items():
            self.assertEqual(asm_ast.ASMCODES.REG2BIN(name), number)
            self.assertEqual(asm_ast.ASMCODES.BIN2REG(number), name)

    def test_pair_numbers(self):
        for name in isa.ALU16_PAIR_NAMES + ('af',):
            self.assertEqual(asm_ast.ASMCODES.REG2BIN(name), isa.PAIR_REGISTER[name])

    def test_condition_codes(self):
        for name, code in isa.CONDITIONS.items():
            self.assertEqual(asm_ast.ASMCODES.TEST2OPCODE(name), code)

    def test_alu_numbers(self):
        for name in isa.ALU8_BINARY_OP_NAMES:
            self.assertEqual(asm_ast.ASMCODES.OPER2OPCODE(name), isa.ALU8_OPS[name])
        for name, (group, op) in isa.ALU16_OPS.items():
            self.assertEqual(asm_ast.ASMCODES.OPER2SUBCODE(name), (group, op))

    def test_opcode_nibbles_are_the_first_nibble(self):
        for name, opcode in (('nop', isa.OP_NOP), ('kil', isa.OP_KIL), ('ret', isa.OP_RET)):
            context = asm_ast.CodeContext()
            grammar.mnemonic.parse(name).emit(context)
            self.assertEqual(context.bytes[0] >> 4, opcode)

    def test_every_condition_assembles_to_its_code(self):
        for name, code in isa.CONDITIONS.items():
            context = asm_ast.CodeContext()
            grammar.mnemonic.parse('jmp ' + name + ', csci').emit(context)
            self.assertEqual(bytes(context.bytes), bytes([isa.OP_JMP << 4 | code, isa.REG_CS]))

    def test_helper_tables(self):
        self.assertEqual(asm_ast.PAIR16_IMPLIED, isa.ALU16_IMPLIED_PAIR_NAME)
        self.assertEqual(tuple(asm_ast.CLR_PAIRS), isa.MEMORY_PAIR_NAMES)


if __name__ == '__main__':
    unittest.main()
