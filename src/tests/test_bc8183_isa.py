"""Unit tests of src/bc8183_isa.py, the single definition of the bc8183 encoding.

The expected numbers are written out here on purpose, so a changed value in the module fails
a test.
"""
import dataclasses
import os
import subprocess
import sys
import unittest

import bc8183_isa as isa

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RegisterTests(unittest.TestCase):
    def test_register_numbers(self):
        self.assertEqual(isa.REGISTERS, {
            'a': 0x1, 'ci': 0x4, 'di': 0x5, 'cs': 0x8, 'ds': 0x9,
            'f': 0xB, 'si': 0xC, 'ss': 0xD, 'pc': 0xF})
        self.assertEqual((isa.REG_A, isa.REG_CI, isa.REG_DI, isa.REG_CS, isa.REG_DS,
                          isa.REG_F, isa.REG_SI, isa.REG_SS, isa.REG_PC),
                         (0x1, 0x4, 0x5, 0x8, 0x9, 0xB, 0xC, 0xD, 0xF))

    def test_register_names_in_grammar_order(self):
        self.assertEqual(isa.REGISTER_NAMES,
                         ('pc', 'ss', 'si', 'f', 'a', 'ci', 'cs', 'di', 'ds'))

    def test_register_numbers_are_unique_and_map_back(self):
        self.assertEqual(len(set(isa.REGISTERS.values())), len(isa.REGISTERS))
        for name, number in isa.REGISTERS.items():
            self.assertEqual(isa.REGISTER_NAMES_BY_NUMBER[number], name)

    def test_pairs(self):
        self.assertEqual(isa.PAIRS, {
            'csci': (0x8, 0x4), 'dsdi': (0x9, 0x5), 'sssi': (0xD, 0xC), 'af': (0x1, 0xB)})
        self.assertEqual(isa.PAIR_REGISTER, {'csci': 0x8, 'dsdi': 0x9, 'sssi': 0xD, 'af': 0x1})
        self.assertEqual(isa.PAIR_LOW_REGISTER, {0x8: 0x4, 0x9: 0x5, 0xD: 0xC, 0x1: 0xB})

    def test_pair_names_are_two_register_names(self):
        for name, (high, low) in isa.PAIRS.items():
            self.assertEqual(name, isa.REGISTER_NAMES_BY_NUMBER[high]
                             + isa.REGISTER_NAMES_BY_NUMBER[low])

    def test_either_register_of_a_pair_selects_it(self):
        self.assertEqual(isa.ADDRESS_PAIR[0x4], (0x8, 0x4))
        self.assertEqual(isa.ADDRESS_PAIR[0x8], (0x8, 0x4))
        self.assertEqual(isa.ADDRESS_PAIR[0xC], (0xD, 0xC))
        self.assertEqual(isa.ADDRESS_PAIR[0xB], (0x1, 0xB))
        self.assertNotIn(0xF, isa.ADDRESS_PAIR)

    def test_assembler_pair_sets(self):
        self.assertEqual(isa.MEMORY_PAIR_NAMES, ('csci', 'dsdi', 'sssi'))
        self.assertEqual(isa.ALU16_PAIR_NAMES, ('csci', 'dsdi'))
        self.assertEqual(isa.ALU16_IMPLIED_PAIR_NAME, {'csci': 'dsdi', 'dsdi': 'csci'})

    def test_cpu_implied_second_pair(self):
        self.assertEqual(isa.ALU16_IMPLIED_PAIR, {0x8: 0x9, 0x9: 0x8, 0x1: 0x8})


class ConditionTests(unittest.TestCase):
    def test_flag_bits(self):
        self.assertEqual((isa.FLAG_ZERO, isa.FLAG_CARRY, isa.FLAG_NEGATIVE, isa.FLAG_OVERFLOW),
                         (0, 1, 2, 3))

    def test_condition_codes(self):
        self.assertEqual(isa.CONDITIONS, {
            'z': 0, 'c': 1, 'n': 2, 'o': 3, 'nz': 4, 'nc': 5, 'nn': 6, 'no': 7})
        self.assertEqual(isa.COND_NEGATE, 0x4)
        self.assertEqual(isa.COND_FLAG_MASK, 0x3)

    def test_negated_condition_is_code_or_4(self):
        for name in ('z', 'c', 'n', 'o'):
            self.assertEqual(isa.CONDITIONS['n' + name], isa.CONDITIONS[name] | 4)

    def test_condition_tests_its_flag(self):
        flags = {'z': isa.FLAG_ZERO, 'c': isa.FLAG_CARRY,
                 'n': isa.FLAG_NEGATIVE, 'o': isa.FLAG_OVERFLOW}
        for name, code in isa.CONDITIONS.items():
            flag = flags[name[-1]]
            self.assertEqual(code & isa.COND_FLAG_MASK, flag, name)
            self.assertEqual(bool(code & isa.COND_NEGATE), len(name) == 2, name)

    def test_condition_names_in_grammar_order(self):
        self.assertEqual(isa.CONDITION_NAMES, ('nz', 'z', 'nc', 'c', 'nn', 'o', 'no', 'n'))
        self.assertEqual(set(isa.CONDITION_NAMES), set(isa.CONDITIONS))

    def test_condition_names_are_longest_match_first(self):
        names = isa.CONDITION_NAMES
        for i, earlier in enumerate(names):
            for later in names[i + 1:]:
                self.assertFalse(later.startswith(earlier),
                                 '{0} shadows {1}'.format(earlier, later))

    def test_condition_names_by_code(self):
        for name, code in isa.CONDITIONS.items():
            self.assertEqual(isa.CONDITION_NAMES_BY_CODE[code], name)


class OpcodeTests(unittest.TestCase):
    def test_opcode_nibbles(self):
        self.assertEqual(
            (isa.OP_NOP, isa.OP_MOV_IMM, isa.OP_MOV_REG, isa.OP_MOV_REG_MEM, isa.OP_MOV_MEM_REG,
             isa.OP_CLC, isa.OP_JMP, isa.OP_JMR, isa.OP_PSH, isa.OP_POP, isa.OP_CAL, isa.OP_RET,
             isa.OP_IN, isa.OP_OUT, isa.OP_EXT, isa.OP_KIL),
            tuple(range(16)))

    def test_each_nibble_has_exactly_one_group_name(self):
        self.assertEqual(sorted(isa.OPCODE_NAMES), list(range(16)))
        self.assertEqual(len(set(isa.OPCODE_NAMES.values())), 16)

    def test_group_names_are_the_cpu_handler_suffixes(self):
        self.assertEqual(isa.OPCODE_NAMES, {
            0x0: 'NOP', 0x1: 'MOV_imm', 0x2: 'MOV_reg', 0x3: 'MOV_reg_mem', 0x4: 'MOV_mem_reg',
            0x5: 'CLC', 0x6: 'JMP', 0x7: 'JMR', 0x8: 'PSH', 0x9: 'POP', 0xA: 'CAL', 0xB: 'RET',
            0xC: 'IN', 0xD: 'OUT', 0xE: 'EXT', 0xF: 'KIL'})

    def test_mode_bits(self):
        self.assertEqual(isa.CLC_REGISTER_FORM, 0x8)
        self.assertEqual(isa.CLC_EXT, 0xF)
        self.assertEqual(isa.JMP_SHORT, 0x8)
        self.assertEqual(isa.JMR_REGISTER, 0x8)
        self.assertEqual(isa.JRX_REGISTER_MARK, 0x8)
        self.assertEqual(isa.CAL_DIRECT, 0x8)
        self.assertEqual(isa.CAL_RELATIVE, 0x1)
        self.assertEqual(isa.CLR_DIRECT, 0x9)
        self.assertEqual(isa.IN_REGISTER, 0x8)
        self.assertEqual(isa.OUT_REGISTER, 0x8)
        self.assertEqual(isa.OUT_PORT_MASK, 0x7)

    def test_ext_subops(self):
        self.assertEqual((isa.EXT_JRX_ADDR, isa.EXT_JRX_REG), (0x1, 0x2))
        self.assertEqual(isa.EXT_SUBOPS, (0x1, 0x2))

    def test_stack_tags(self):
        self.assertEqual(isa.STACKFRAME_PUSH, 0x10)
        self.assertEqual(isa.STACKFRAME_CALL, 0xC0)

    def test_kil_bytes(self):
        self.assertEqual(isa.KIL_BYTE, 0xF0)
        self.assertEqual(isa.TOP_OF_MEMORY_KIL, 0xFF)
        self.assertEqual(isa.TOP_OF_MEMORY_KIL >> 4, isa.OP_KIL)
        self.assertEqual(isa.KIL_BYTE >> 4, isa.OP_KIL)


class AluTests(unittest.TestCase):
    def test_alu8_ops(self):
        self.assertEqual(isa.ALU8_OPS, {
            'add': 0x0, 'sub': 0x1, 'and': 0x2, 'or': 0x3, 'xor': 0x4, 'shl': 0x5, 'shr': 0x6,
            'not': 0x7, 'inc': 0xD, 'dec': 0xE})

    def test_alu8_name_lists(self):
        self.assertEqual(isa.ALU8_BINARY_OP_NAMES, ('add', 'sub', 'and', 'or', 'xor', 'shl', 'shr'))
        self.assertEqual(isa.ALU8_UNARY_OP_NAMES, ('not', 'inc', 'dec'))
        self.assertEqual(isa.ALU8_SHORT_ALIAS_OP_NAMES, ('sub', 'and', 'or', 'xor'))

    def test_short_alias_does_not_collide(self):
        # 5(o|8) for o = 1..4 is 9..C; 8 is the long form, D/E/F are inc/dec/EXT (E15)
        codes = [isa.ALU8_OPS[n] | isa.CLC_REGISTER_FORM for n in isa.ALU8_SHORT_ALIAS_OP_NAMES]
        self.assertEqual(codes, [0x9, 0xA, 0xB, 0xC])

    def test_alu16_groups(self):
        self.assertEqual(isa.ALU16_GROUP_ARITH, 0xA)
        self.assertEqual(isa.ALU16_GROUP_BINARY, 0xB)
        self.assertEqual(isa.ALU16_REGISTER_FORM, 0x8)

    def test_alu16_ops(self):
        self.assertEqual(isa.ALU16_OPS, {
            'add': (0xA, 0x0), 'sub': (0xA, 0x1), 'mul': (0xA, 0x2), 'div': (0xA, 0x3),
            'mod': (0xA, 0x4), 'inc': (0xA, 0xD), 'dec': (0xA, 0xE),
            'and': (0xB, 0x2), 'or': (0xB, 0x3), 'xor': (0xB, 0x4), 'shl': (0xB, 0x5),
            'shr': (0xB, 0x6), 'not': (0xB, 0x7)})

    def test_alu16_codes_are_group_and_op(self):
        self.assertEqual(isa.ALU16_CODES, {
            'add': 0xA0, 'sub': 0xA1, 'mul': 0xA2, 'div': 0xA3, 'mod': 0xA4, 'inc': 0xAD,
            'dec': 0xAE, 'and': 0xB2, 'or': 0xB3, 'xor': 0xB4, 'shl': 0xB5, 'shr': 0xB6,
            'not': 0xB7})
        self.assertEqual(isa.alu16_code(0xB, 0x7), 0xB7)
        self.assertEqual(len(set(isa.ALU16_CODES.values())), len(isa.ALU16_CODES))

    def test_alu16_name_lists(self):
        self.assertEqual(isa.ALU16_BINARY_OP_NAMES,
                         ('add', 'sub', 'mul', 'div', 'mod', 'and', 'or', 'xor', 'shl', 'shr'))
        self.assertEqual(isa.ALU16_SHIFT_OP_NAMES, ('shl', 'shr'))
        self.assertEqual(isa.ALU16_UNARY_OP_NAMES, ('inc', 'dec', 'not'))
        self.assertEqual(set(isa.ALU16_BINARY_OP_NAMES) | set(isa.ALU16_UNARY_OP_NAMES),
                         set(isa.ALU16_OPS))

    def test_alu16_register_form_keeps_the_op(self):
        # 5F k8 pq: bit 3 of the op nibble is free for every two-operand op
        for name in isa.ALU16_BINARY_OP_NAMES:
            self.assertEqual(isa.ALU16_OPS[name][1] & isa.ALU16_REGISTER_FORM, 0, name)


class FormTableTests(unittest.TestCase):
    def test_forms_are_immutable(self):
        form = isa.FORMS[0]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            form.length = 9
        self.assertIsInstance(isa.FORMS, tuple)
        for form in isa.FORMS:
            self.assertIsInstance(form.operands, tuple, form.key)

    def test_keys_are_unique(self):
        keys = [form.key for form in isa.FORMS]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(set(isa.FORMS_BY_KEY), set(keys))

    def test_layout_length_equals_byte_length(self):
        for form in isa.FORMS:
            groups = form.layout.split(' ')
            self.assertEqual(len(groups), form.length, form.key)
            for group in groups:
                self.assertEqual(len(group), 2, form.key)

    def test_layout_uses_only_known_characters(self):
        for form in isa.FORMS:
            for char in form.nibbles:
                self.assertIn(char, isa.LAYOUT_FIELDS + '0123456789ABCDEF', form.key)

    def test_first_nibble_is_the_opcode(self):
        for form in isa.FORMS:
            self.assertEqual(int(form.layout[0], 16), form.opcode, form.key)
            self.assertIn(form.opcode, isa.OPCODE_NAMES)

    def test_operand_count_matches_syntax(self):
        for form in isa.FORMS:
            rest = form.syntax[len(form.mnemonic):].strip()
            count = len(rest.split(',')) if rest else 0
            self.assertEqual(count, len(form.operands), form.key)
            self.assertTrue(form.syntax.startswith(form.mnemonic), form.key)

    def test_only_the_short_alias_is_not_emitted(self):
        hidden = sorted(form.key for form in isa.FORMS if not form.emitted)
        self.assertEqual(hidden, ['and.reg_short', 'or.reg_short', 'sub.reg_short',
                                  'xor.reg_short'])

    def test_pinned_layouts(self):
        expected = {
            'nop': '00', 'mov.imm8': '1r ii', 'mov.reg': '2r s0', 'mov.reg_mem': '3r p0',
            'mov.mem_reg': '4p r0', 'psh': '8r', 'pop': '9r',
            'add.imm8': '50 ii', 'shr.imm8': '56 ii', 'add.reg': '58 r0', 'shl.reg': '58 r5',
            'shr.reg': '58 r6', 'not': '57', 'inc': '5D', 'dec': '5E',
            'sub.reg_short': '59 r0', 'xor.reg_short': '5C r0',
            'add16.imm16': '5F A0 p0 hh ll', 'mod16.imm16': '5F A4 p0 hh ll',
            'and16.imm16': '5F B2 p0 hh ll', 'shl16.imm8': '5F B5 p0 00 ii',
            'shr16.imm8': '5F B6 p0 00 ii', 'add16.reg': '5F A8 pq', 'shr16.reg': '5F BE pq',
            'inc16': '5F AD p0', 'dec16': '5F AE p0', 'not16': '5F B7 p0',
            'jmp.pair': '6t 0p', 'jmp.label': '6T ll', 'jmr.label': '7t dd', 'jmr.reg': '7T r0',
            'jrx.label': 'E1 t0 hh ll', 'jrx.pair': 'E2 Tp', 'cal.label': 'A8 hh ll',
            'cal.pair': 'A0 p0', 'clr.label': 'A9 hh ll', 'clr.pair': 'A1 pw', 'ret': 'B0',
            'kil': 'F0', 'in.imm4': 'C0 rx', 'in.reg': 'C8 rs', 'out.reg': 'D8 rs',
            'out.imm8': 'Du ii',
        }
        for key, layout in expected.items():
            self.assertEqual(isa.FORMS_BY_KEY[key].layout, layout, key)

    def test_form_count_per_family(self):
        def count(prefix_test):
            return sum(1 for form in isa.FORMS if prefix_test(form))
        self.assertEqual(count(lambda f: f.encoding == '5o ii'), 7)
        self.assertEqual(count(lambda f: f.encoding == '58 ro'), 7)
        self.assertEqual(count(lambda f: f.encoding == '5F kk p0 hh ll'), 8)
        self.assertEqual(count(lambda f: f.encoding == '5F kk p0 00 ii'), 2)
        self.assertEqual(count(lambda f: f.encoding == '5F k8 pq'), 10)
        self.assertEqual(count(lambda f: f.encoding == '5F kk p0'), 3)
        self.assertEqual(len(isa.FORMS), 67)

    def test_fixed_nibbles_and_bits(self):
        self.assertEqual(isa.FORMS_BY_KEY['add16.reg'].fixed,
                         ((0, 0xF, 0x5), (1, 0xF, 0xF), (2, 0xF, 0xA), (3, 0xF, 0x8)))
        self.assertEqual(isa.FORMS_BY_KEY['jmp.label'].fixed, ((0, 0xF, 0x6), (1, 0x8, 0x8)))
        self.assertEqual(isa.FORMS_BY_KEY['jmp.pair'].fixed,
                         ((0, 0xF, 0x6), (1, 0x8, 0x0), (2, 0xF, 0x0)))
        self.assertEqual(isa.FORMS_BY_KEY['out.imm8'].fixed, ((0, 0xF, 0xD), (1, 0x8, 0x0)))
        self.assertEqual(isa.FORMS_BY_KEY['shl16.imm8'].fixed,
                         ((0, 0xF, 0x5), (1, 0xF, 0xF), (2, 0xF, 0xB), (3, 0xF, 0x5),
                          (5, 0xF, 0x0), (6, 0xF, 0x0), (7, 0xF, 0x0)))

    def test_emitted_first_bytes_decode_to_one_form_per_layout(self):
        # No two emitted forms have the same fixed nibbles and bits, so a disassembler can tell
        # them apart by their layout.
        seen = {}
        for form in isa.FORMS:
            if form.emitted:
                self.assertNotIn(form.fixed, seen, (form.key, seen.get(form.fixed)))
                seen[form.fixed] = form.key


class ImportTests(unittest.TestCase):
    def run_python(self, cwd, code):
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        return subprocess.run([sys.executable, '-I', '-c', code], cwd=cwd, env=env,
                              capture_output=True, text=True, timeout=60)

    def test_imports_with_only_src_on_the_path(self):
        code = ('import sys; sys.path[:] = [p for p in sys.path if "site-packages" not in p]; '
                'sys.path.insert(0, {0!r}); import bc8183_isa; '
                'print(sorted(m for m in sys.modules if m.startswith(("bc64", "bc81asmc", "parsy"))))'
                ).format(SRC_DIR)
        result = self.run_python(SRC_DIR, code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '[]')
        self.assertEqual(result.stderr, '')

    def test_imports_from_the_assembler_folder_with_src_appended(self):
        asm_dir = os.path.join(SRC_DIR, 'bc81asmc')
        code = ('import sys; sys.path.insert(0, {0!r}); sys.path.append({1!r}); '
                'import bc8183_isa; print(len(bc8183_isa.FORMS))').format(asm_dir, SRC_DIR)
        result = self.run_python(asm_dir, code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(len(isa.FORMS)))

    def test_module_imports_only_the_standard_library(self):
        with open(os.path.join(SRC_DIR, 'bc8183_isa.py'), encoding='utf-8') as f:
            source = f.read()
        import ast
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertEqual(imported, {'dataclasses'})


if __name__ == '__main__':
    unittest.main()
