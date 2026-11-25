import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

import bc
from bc_grammar import code_block, program, statement_asm
from tests.bc_assert_tests import ASM
from tests.bc_codegen_tests import compile_source, function_lines

LOCKED_UNKNOWN = "raw asm: unknown item '{0}' (expected a number 0-255, :name, hi(:name) or lo(:name))"
LOCKED_RANGE = "raw asm: {0} is out of range (0-255)"


def db_lines(source):
    return [l.strip() for l in compile_source(source).splitlines() if l.strip().startswith('.db ')]


def compile_errors(source):
    '''Compile expecting failure; returns the stderr text (exit 1, nothing returned).'''
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        with unittest.TestCase().assertRaises(SystemExit) as caught:
            compile_source(source)
    assert caught.exception.code == 1
    return err.getvalue()


def main_src(body, prefix=''):
    return prefix + 'byte main() { ' + body + ' return 0; }\n'


class RawAsmGrammarTests(unittest.TestCase):
    def test_quoted_form_is_unchanged(self):
        self.assertEqual('ASM[quoted]', '{0}'.format(statement_asm.parse('asm "quoted";')))

    def test_quoted_form_with_tab_before_string(self):
        self.assertEqual('ASM[x]', '{0}'.format(statement_asm.parse('asm\t"x";')))

    def test_raw_form_items(self):
        val = statement_asm.parse('asm 0xd8, :f, hi(:f);')
        self.assertEqual('ASM_RAW[0xd8, :f, hi(:f)]', '{0}'.format(val))

    def test_raw_form_in_code_block(self):
        val = code_block.parse('{\n  asm 1, 2;\n}')
        self.assertIn('STATEMENT_ASM_RAW', '{0}'.format(val))

    def test_asm_without_items_is_not_raw(self):
        with self.assertRaises(Exception):
            statement_asm.parse('asm;')
        self.assertIn('EXPRESSION_TERM', '{0}'.format(program.parse('byte main() { asm; }')))

    def test_identifier_starting_with_asm_is_not_the_keyword(self):
        tree = '{0}'.format(program.parse('byte asmfoo(byte x) { return x; } byte main() { asmfoo(1); }'))
        self.assertNotIn('ASM', tree.replace('asmfoo', ''))
        with self.assertRaises(Exception):
            statement_asm.parse('asmfoo(1);')


class RawAsmCodegenTests(unittest.TestCase):
    def test_each_item_kind_is_one_db_line(self):
        src = main_src('asm 0xd8, 129, 0, :lbl, hi(:lbl), lo(:lbl);', 'byte f() { asm "lbl: nop"; }\n')
        self.assertEqual(['.db 0xd8, 0x81, 0x00, :lbl, hi(:lbl), lo(:lbl)'], db_lines(src))

    def test_hex_any_length_and_case(self):
        self.assertEqual(['.db 0x0a, 0xff, 0x01'], db_lines(main_src('asm 0x0A, 0xFF, 0x0001;')))

    def test_blanks_in_hi_lo_and_around_items(self):
        src = main_src('asm  hi ( :lbl ) ,lo( :lbl )\t;', 'byte f() { asm "lbl: nop"; }\n')
        self.assertEqual(['.db hi(:lbl), lo(:lbl)'], db_lines(src))

    def test_statement_is_in_place_with_asm_indent(self):
        lines = function_lines(compile_source(main_src('asm 1;')), 'main')
        self.assertIn('.db 0x01', lines)
        basm = compile_source(main_src('asm 1;\n asm "nop";'))
        raw = [l for l in basm.splitlines() if '.db 0x01' in l][0]
        txt = [l for l in basm.splitlines() if l.strip() == 'nop'][0]
        self.assertEqual(len(raw) - len(raw.lstrip()), len(txt) - len(txt.lstrip()))
        self.assertLess(basm.index('.db 0x01'), basm.index('\n' + txt + '\n'))

    def test_define_item(self):
        src = '#define OUTCS 0x81\n' + main_src('asm 0xd8, OUTCS;')
        self.assertEqual(['.db 0xd8, 0x81'], db_lines(src))

    def test_define_with_non_item_value(self):
        err = compile_errors('#define BAD foo\n' + main_src('asm BAD;'))
        self.assertIn(LOCKED_UNKNOWN.format('foo'), err)

    def test_decimal_out_of_range(self):
        self.assertIn(LOCKED_RANGE.format('256'), compile_errors(main_src('asm 256;')))

    def test_hex_out_of_range(self):
        self.assertIn(LOCKED_RANGE.format('0x100'), compile_errors(main_src('asm 0x100;')))
        self.assertIn(LOCKED_RANGE.format('0x0100'), compile_errors(main_src('asm 0x0100;')))

    def test_unknown_items(self):
        for item in ['foo', "'a'", '1 + 2', 'hi(foo)', 'hi(:x', '007', '0x', '-1', ':', 'HI(:x)']:
            with self.subTest(item=item):
                self.assertIn(LOCKED_UNKNOWN.format(item), compile_errors(main_src('asm {0};'.format(item))))

    def test_empty_item(self):
        self.assertIn(LOCKED_UNKNOWN.format(''), compile_errors(main_src('asm 1,,2;')))
        self.assertIn(LOCKED_UNKNOWN.format(''), compile_errors(main_src('asm 1,;')))

    def test_every_bad_item_is_reported(self):
        err = compile_errors(main_src('asm foo, 1, 300, bar;'))
        self.assertIn(LOCKED_UNKNOWN.format('foo'), err)
        self.assertIn(LOCKED_RANGE.format('300'), err)
        self.assertIn(LOCKED_UNKNOWN.format('bar'), err)

    def test_errors_in_several_statements_are_all_reported(self):
        err = compile_errors(main_src('asm 256; asm zz;'))
        self.assertIn(LOCKED_RANGE.format('256'), err)
        self.assertIn(LOCKED_UNKNOWN.format('zz'), err)

    def test_error_writes_no_basm(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, 'bad.b')
            with open(src, 'w', encoding='utf8') as f:
                f.write(main_src('asm 256;'))
            res = subprocess.run([sys.executable, bc.__file__, src], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(1, res.returncode)
            self.assertIn('error: ' + LOCKED_RANGE.format('256'), res.stderr)
            self.assertFalse(os.path.exists(os.path.join(tmp, 'bad.basm')))

    def test_quoted_asm_output_unchanged(self):
        basm = compile_source(main_src('asm "nop";'))
        self.assertNotIn('.db', basm.split(';FUNCTION main')[1].split(';END OF FUNCTION main')[0])


class RawAsmReachabilityTests(unittest.TestCase):
    HELPER = 'byte helper() { return "HELPERTEXT"; }\n'

    def test_unreferenced_helper_is_dropped(self):
        basm = compile_source(self.HELPER + main_src('asm 1;'))
        self.assertNotIn(';FUNCTION helper', basm)

    def test_kept_through_raw_label_item(self):
        basm = compile_source(self.HELPER + main_src('asm 0xd8, :FHELPER0001;'))
        self.assertIn(';FUNCTION helper', basm)
        self.assertIn('HELPERTEXT', basm)

    def test_kept_through_hi_item(self):
        basm = compile_source(self.HELPER + main_src('asm hi(:FHELPER0001);'))
        self.assertIn(';FUNCTION helper', basm)

    def test_kept_through_lo_item(self):
        basm = compile_source(self.HELPER + main_src('asm lo(:FHELPER0001);'))
        self.assertIn(';FUNCTION helper', basm)


class RawAsmAssembleTests(unittest.TestCase):
    def test_compiled_output_assembles_to_expected_bytes(self):
        src = ('#define OUTCS 0x81\n'
               'byte main() {\n'
               '  asm "mark: nop";\n'
               '  asm 0xd8, 0x0a, 0xFF, 0, 129, OUTCS, :mark, hi(:mark), lo(:mark), 0x7e;\n'
               '  return 0;\n'
               '}\n')
        basm = compile_source(src)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'prog.basm')
            with open(path, 'w', encoding='utf8') as f:
                f.write(basm)
            res = subprocess.run([sys.executable, ASM, path, '--map', 'prog.map'], cwd=tmp,
                                 capture_output=True, text=True)
            self.assertEqual(0, res.returncode, res.stdout + res.stderr)
            with open(os.path.join(tmp, 'prog.btap'), 'rb') as f:
                bits = f.read()
            with open(os.path.join(tmp, 'prog.map'), encoding='utf8') as f:
                mark = [int(l.split()[0], 16) for l in f if l.strip().endswith(' mark')][0]
        data = bytes(sum(bits[i + b] << b for b in range(8)) for i in range(0, len(bits) - 7, 8))
        hi, lo = mark >> 8, mark & 0xff
        expected = bytes([0xd8, 0x0a, 0xff, 0x00, 0x81, 0x81, hi, lo, hi, lo, 0x7e])
        self.assertIn(expected, data)


class LinkDirectiveTests(unittest.TestCase):
    PROG = 'byte main() { return 1; }\n'

    def pre(self, source, defaultdir='.'):
        with contextlib.redirect_stdout(io.StringIO()):
            return bc.preprocess(source, False, defaultdir)

    def test_accepted_and_recorded(self):
        self.pre('#link util\n#link std_a\n#link util\n' + self.PROG)
        self.assertEqual(['util', 'std_a'], bc.linkNames)

    def test_basm_unchanged(self):
        self.assertEqual(compile_source(self.PROG), compile_source('#link util\n' + self.PROG))

    def test_line_is_dropped_from_source(self):
        self.assertNotIn('link', self.pre('#link util\n' + self.PROG))

    def test_indented_and_tab_separated(self):
        self.pre('  #link\tutil  \n' + self.PROG)
        self.assertEqual(['util'], bc.linkNames)

    def test_no_define_substitution_in_name(self):
        self.pre('#define util other\n#link util\n' + self.PROG)
        self.assertEqual(['util'], bc.linkNames)

    def test_from_include(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'hdr.b'), 'w', encoding='utf8') as f:
                f.write('#link util\nbyte lib() { return 2; }\n')
            text = self.pre('#include hdr.b\n' + self.PROG, tmp)
        self.assertEqual(['util'], bc.linkNames)
        self.assertNotIn('#link', text)

    def test_reset_between_compiles(self):
        self.pre('#link util\n' + self.PROG)
        self.pre(self.PROG)
        self.assertEqual([], bc.linkNames)

    def test_traced_with_verbose(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            bc.preprocess('#link util\n' + self.PROG, True, '.')
        self.assertIn('util', out.getvalue())

    def test_malformed_forms(self):
        for line in ['#link', '#link   ', '#link a b', '#link 1a', '#link a-b', '#link "x"']:
            with self.subTest(line=line):
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                    with self.assertRaises(SystemExit) as caught:
                        bc.preprocess(line + '\n' + self.PROG, False, '.')
                self.assertEqual(1, caught.exception.code)
                self.assertIn('malformed #link (expected: #link NAME): ' + line.strip(), err.getvalue())


if __name__ == '__main__':
    unittest.main()
