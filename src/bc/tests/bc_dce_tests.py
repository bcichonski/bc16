import contextlib
import io
import unittest

import bc
from bc_ast import asm_labels
from bc_grammar import program
from tests.bc_assert_tests import assemble
from tests.bc_codegen_tests import compile_source, function_lines


def compile_verbose(source):
    '''Compile with --verbose; returns (basm, trace output).'''
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        text = bc.preprocess(source, True, '.')
        basm = bc.compile(program.parse(text), True)
    return basm, out.getvalue()


class FunctionSelectionTests(unittest.TestCase):
    def test_unused_function_and_its_string_are_absent(self):
        basm = compile_source(
            'byte unused() { return "UNUSEDTEXT"; }\n'
            'byte main() { return "MAINTEXT"; }\n')
        self.assertNotIn(';FUNCTION unused', basm)
        self.assertNotIn('UNUSEDTEXT', basm)
        self.assertIn(';FUNCTION main', basm)
        self.assertIn("'MAINTEXT'", basm)
        self.assertIn(';>>>>>>>>>>DATA SEGMENT<<<<<<<<<<<<<', basm)
        self.assertIn('COMPILER ASM STDLIB', basm)

    def test_no_data_segment_banner_when_only_unused_function_has_strings(self):
        basm = compile_source(
            'byte unused() { return "UNUSEDTEXT"; }\n'
            'byte main() { return 1; }\n')
        self.assertNotIn('UNUSEDTEXT', basm)
        self.assertNotIn('DATA SEGMENT', basm)

    def test_transitive_call_is_kept(self):
        basm = compile_source(
            'byte leaf() { return 3; }\n'
            'byte middle() { return leaf(); }\n'
            'byte other() { return 4; }\n'
            'byte main() { return middle(); }\n')
        self.assertIn(';FUNCTION middle', basm)
        self.assertIn(';FUNCTION leaf', basm)
        self.assertNotIn(';FUNCTION other', basm)

    def test_kept_functions_stay_in_source_order(self):
        basm = compile_source(
            'byte leaf() { return 3; }\n'
            'byte dead() { return 5; }\n'
            'byte middle() { return leaf(); }\n'
            'byte main() { return middle(); }\n')
        self.assertLess(basm.index(';FUNCTION leaf'), basm.index(';FUNCTION middle'))
        self.assertLess(basm.index(';FUNCTION middle'), basm.index(';FUNCTION main'))

    def test_recursion_and_mutual_recursion_kept_once(self):
        basm = compile_source(
            'byte even(byte n);\n'
            'byte odd(byte n) { if (n) { return even(n - 1); } return 0; }\n'
            'byte even(byte n) { if (n) { return odd(n - 1); } return 1; }\n'
            'byte self(byte n) { if (n) { return self(n - 1); } return 0; }\n'
            'byte main() { self(2); return even(4); }\n')
        for name in ('odd', 'even', 'self', 'main'):
            self.assertEqual(basm.count(';FUNCTION {0}\n'.format(name)), 1, name)

    def test_function_kept_via_label_defined_in_its_asm(self):
        # the bdos/bdio pattern: main loads the address of a label defined inside another function
        basm = compile_source(
            'word hook() {\n'
            '    asm "myhook: psh a";\n'
            '    asm "pop a";\n'
            '}\n'
            'byte main() {\n'
            '    asm ".mv csci, :myhook";\n'
            '    return 1;\n'
            '}\n')
        self.assertIn(';FUNCTION hook', basm)
        self.assertIn('myhook: psh a', basm)

    def test_function_kept_via_def_in_its_asm(self):
        basm = compile_source(
            'word holder() { asm ".def myconst, 0x1234"; }\n'
            'byte main() { asm ".mv csci, :myconst"; return 1; }\n')
        self.assertIn(';FUNCTION holder', basm)

    def test_function_kept_via_f_label_in_asm(self):
        # helper is declared first, so its call label is FHELPER0001
        basm = compile_source(
            'byte helper() { return 7; }\n'
            'byte main() { asm "cal :FHELPER0001"; return 1; }\n')
        self.assertIn('FHELPER0001:', basm)
        self.assertIn(';FUNCTION helper', basm)

    def test_reference_in_comment_keeps_nothing(self):
        basm = compile_source(
            'byte helper() { return 7; }\n'
            'word hook() { asm "myhook: psh a"; }\n'
            'byte main() { asm "nop ; cal :FHELPER0001 and :myhook"; return 1; }\n')
        self.assertNotIn(';FUNCTION helper', basm)
        self.assertNotIn(';FUNCTION hook', basm)

    def test_kept_code_unchanged_vs_compiled_without_unused(self):
        kept = ('byte leaf() { return "LEAF"; }\n'
                'byte main() { return leaf(); }\n')
        # the unused function comes after, so label numbering of the kept ones is the same
        full = compile_source(kept + 'byte unused() { return "UNUSED"; }\n')
        alone = compile_source(kept)
        self.assertEqual(full, alone)

    def test_kept_function_text_unchanged_with_unused_before(self):
        # an unused function before main shifts nothing in main's text other than via its labels;
        # main's text is cut verbatim from what was emitted
        basm = compile_source(
            'byte unused() { return 9; }\n'
            'byte main() { return 1; }\n')
        lines = function_lines(basm, 'main')
        self.assertEqual(lines[1], 'FMAIN0002:')
        self.assertIn('cal :FMAIN0002', basm)

    def test_error_in_unused_function_still_fails(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                compile_source(
                    'byte unused() { return nosuchfunction(); }\n'
                    'byte main() { return 1; }\n')

    def test_no_blank_lines_in_output(self):
        basm = compile_source(
            'byte a() { return "A"; }\n'
            'byte b() { return "B"; }\n'
            'byte c() { return a(); }\n'
            'byte main() { return c(); }\n')
        self.assertNotIn('\n\n', basm.strip('\n'))

    def test_verbose_traces_dropped_function(self):
        basm, out = compile_verbose(
            'byte unused() { return 9; }\n'
            'byte main() { return 1; }\n')
        self.assertIn('unused', [line.split()[-1] for line in out.splitlines() if 'Dropped' in line])
        self.assertNotIn('Dropped unused function main', out)

    def test_quiet_compile_prints_nothing_new(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            text = bc.preprocess('byte unused() { return 9; }\nbyte main() { return 1; }\n', False, '.')
            bc.compile(program.parse(text), False)
        self.assertEqual(out.getvalue(), '')

    def test_output_assembles(self):
        basm = compile_source(
            '#heap 0x3000\n'
            'byte leaf() { return "LEAF"; }\n'
            'byte dead() { return "DEAD"; }\n'
            'word hook() { asm "myhook: psh a"; asm "pop a"; }\n'
            'byte main() { asm ".mv csci, :myhook"; return leaf(); }\n')
        code, out = assemble(basm)
        self.assertEqual(code, 0, out)


class AsmLabelScanTests(unittest.TestCase):
    def test_definitions_and_references(self):
        defined, referenced = asm_labels(
            'FMAIN0001:\n'
            '    bdio_call: psh a\n'
            '.def myconst, 0x10\n'
            '    cal :FOO0002 ; cal :BAR0003\n'
            "    mov a, ';'\n"
            "DATA0004:      .db 'x', 0x00\n"
            '; OUT:csci - comment\n')
        self.assertEqual(defined, {'FMAIN0001', 'bdio_call', 'myconst', 'DATA0004'})
        self.assertEqual(referenced, {'FOO0002'})


if __name__ == '__main__':
    unittest.main()
