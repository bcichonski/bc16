import contextlib
import io
import os
import tempfile
import unittest

import bc
from bc_ast import CompilerError, Context, Scope
from bc_grammar import program


def compile_source(source, defaultdir='.'):
    '''Preprocess, parse and compile source in-process; compiler printing is captured.'''
    with contextlib.redirect_stdout(io.StringIO()):
        text = bc.preprocess(source, False, defaultdir)
        return bc.compile(program.parse(text), False)


def function_lines(basm, name):
    '''Instruction lines (stripped, no blanks) of one generated function.'''
    start = basm.index(';FUNCTION {0}\n'.format(name))
    end = basm.index(';END OF FUNCTION {0}'.format(name))
    return [line.strip() for line in basm[start:end].splitlines() if line.strip()]


def main_lines(source, defaultdir='.'):
    return function_lines(compile_source(source, defaultdir), 'main')


class CodegenTestCase(unittest.TestCase):
    def assertSequence(self, lines, expected):
        '''expected items occur in lines in the given order (gaps allowed).'''
        pos = 0
        for item in expected:
            try:
                pos = lines.index(item, pos) + 1
            except ValueError:
                self.fail('{0!r} not found (in order) in {1}'.format(item, lines[pos:]))

    def assertContiguous(self, lines, expected):
        n = len(expected)
        for i in range(len(lines) - n + 1):
            if lines[i:i + n] == expected:
                return
        self.fail('{0} not found as a contiguous block in {1}'.format(expected, lines))


class TestProgramShape(CodegenTestCase):
    def test_preamble_entry_and_stdlib(self):
        basm = compile_source('byte main() { return 1; }')
        self.assertTrue(basm.lstrip().startswith(';'))
        self.assertIn('.org 0x{0:04x}'.format(bc.codeSegment), basm)
        self.assertLess(basm.index(';MAIN ENTRYPOINT'), basm.index(';FUNCTION main'))
        self.assertIn('cal :FMAIN0001', basm)
        self.assertLess(basm.index(';FUNCTION main'), basm.index(';END OF FUNCTION main'))
        self.assertLess(basm.index(';END OF FUNCTION main'), basm.index('COMPILER ASM STDLIB'))
        self.assertIn('stackheadrll8:', basm)

    def test_function_label_and_trailing_ret(self):
        lines = main_lines('byte main() { }')
        self.assertTrue(lines[1].startswith('FMAIN0001:'))
        self.assertTrue(lines[1].endswith('nop'))
        self.assertEqual('ret', lines[-1])

    def test_missing_main_is_compile_error(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                bc.compile(program.parse('byte other() { }'), False)


class TestExpressions(CodegenTestCase):
    def test_constant_loaded_into_csci(self):
        lines = main_lines('byte main() { return 0x1234; }')
        self.assertContiguous(lines, ['mov cs, 0x12', 'mov ci, 0x34', 'ret'])

    def test_char_constant(self):
        lines = main_lines("byte main() { return 'A'; }")
        self.assertContiguous(lines, ['mov cs, 0x00', 'mov ci, 0x41', 'ret'])

    def test_binary_add_constants_not_folded(self):
        lines = main_lines('byte main() { return 1 + 2; }')
        self.assertContiguous(lines, [
            'mov cs, 0x00', 'mov ci, 0x01',
            'mov ds, 0x00', 'mov di, 0x02',
            'add csci, dsdi', 'ret'])

    def test_binary_sub_non_commutative_uses_stack(self):
        lines = main_lines('byte main() { return 5 - 3; }')
        self.assertContiguous(lines, [
            'mov cs, 0x00', 'mov ci, 0x05',
            'psh cs', 'psh ci',
            'mov cs, 0x00', 'mov ci, 0x03',
            'mov ds, cs', 'mov di, ci',
            'pop ci', 'pop cs',
            'sub csci, dsdi'])

    def test_binary_operators_use_library_instruction(self):
        for oper, instr in (('+', 'add'), ('-', 'sub'), ('*', 'mul'), ('/', 'div'), ('%', 'mod')):
            with self.subTest(oper=oper):
                lines = main_lines('byte main() {{ return 8 {0} 2; }}'.format(oper))
                self.assertIn('{0} csci, dsdi'.format(instr), lines)

    def test_bitwise_and_shift_operators(self):
        for oper, instr in (('&', 'and'), ('|', 'or'), ('<<', 'shl'), ('>>', 'shr')):
            with self.subTest(oper=oper):
                lines = main_lines('byte main() {{ return 8 {0} 2; }}'.format(oper))
                self.assertIn('{0} csci, dsdi'.format(instr), lines)

    def test_comparison_operators_call_library(self):
        for oper, call in (('=', 'cal :eq16'), ('>', 'cal :gt16'), ('<', 'cal :gteq16'),
                           ('>=', 'cal :gteq16'), ('<=', 'cal :gt16'), ('!=', 'cal :eq16')):
            with self.subTest(oper=oper):
                lines = main_lines('byte main() {{ return 8 {0} 2; }}'.format(oper))
                self.assertIn(call, lines)

    def test_non_constant_right_operand_saved_on_stack(self):
        lines = main_lines('byte main() { word a; a <- 1; return 2 + a; }')
        self.assertSequence(lines, [
            'psh cs', 'psh ci', 'cal :stackvar8gt16', 'pop di', 'pop ds', 'add csci, dsdi'])

    def test_unary_not_and_logical_not(self):
        lines = main_lines('byte main() { return ~5; }')
        self.assertContiguous(lines, ['mov cs, 0x00', 'mov ci, 0x05', 'not csci', 'ret'])
        lines = main_lines('byte main() { return !5; }')
        self.assertContiguous(lines, [
            'mov cs, 0x00', 'mov ci, 0x05', 'mov a, cs', 'or  ci', 'mov ci, f', 'and csci, 0x0001'])

    def test_unary_peek(self):
        lines = main_lines('byte main() { return #0xabcd; }')
        self.assertContiguous(lines, [
            'mov cs, 0xab', 'mov ci, 0xcd',
            'mov ds, cs', 'mov di, ci', 'cal :peek16', 'ret'])

    def test_string_constant_goes_to_data_segment(self):
        basm = compile_source('byte main() { return "hi"; }')
        self.assertIn('.mv csci, :DATA0002', basm)
        self.assertIn(".db 'hi', 0x00", basm)
        self.assertLess(basm.index('DATA SEGMENT'), basm.index('COMPILER ASM STDLIB'))


class TestVariables(CodegenTestCase):
    def test_assign_word_local_then_read(self):
        lines = main_lines('byte main() { word a; a <- 0x0102; return a; }')
        self.assertContiguous(lines, [
            'mov cs, 0x01', 'mov ci, 0x02',
            'mov a, 0x00', 'cal :stackvar8st16',
            'mov a, 0x00', 'cal :stackvar8gt16',
            'ret'])

    def test_byte_local_uses_byte_accessors(self):
        lines = main_lines('byte main() { byte b; b <- 3; return b; }')
        self.assertSequence(lines, ['cal :stackvar8st8', 'cal :stackvar8gt8', 'ret'])

    def test_second_local_has_offset_after_first(self):
        lines = main_lines('byte main() { word a; byte b; b <- 1; return b; }')
        self.assertSequence(lines, ['mov a, 0x02', 'cal :stackvar8st8', 'mov a, 0x02', 'cal :stackvar8gt8'])

    def test_undeclared_variable_reported_by_context(self):
        context = Context(0x1000, 0x3000, False)
        ast = program.parse('byte main() { x <- 1; return 1; }')
        with contextlib.redirect_stdout(io.StringIO()) as out:
            try:
                ast.emit(context)
            except TypeError:
                pass  # D7: the failed lookup returns None and the caller then indexes it
        self.assertTrue(any('Undeclared variable x' in e for e in context.errors))
        self.assertIn('ERROR: Undeclared variable x', out.getvalue())


class TestControlFlow(CodegenTestCase):
    def test_if_without_else(self):
        lines = main_lines('byte main() { word a; a <- 1; if (a) { a <- 2; } return a; }')
        jump = next(l for l in lines if l.startswith('jrx z, :'))
        label = jump.split(':')[1]
        self.assertSequence(lines, ['mov a, cs', 'or ci', jump, 'mov ci, 0x02', label + ':      nop'])
        self.assertEqual(1, sum(1 for l in lines if l.startswith('jrx')))

    def test_if_else(self):
        lines = main_lines('byte main() { word a; a <- 1; if (a) { a <- 2; } else { a <- 3; } return a; }')
        jumps = [l for l in lines if l.startswith('jrx z, :')]
        self.assertEqual(2, len(jumps))
        else_label, end_label = [j.split(':')[1] for j in jumps]
        self.assertNotEqual(else_label, end_label)
        self.assertSequence(lines, [
            'mov a, cs', 'or ci', jumps[0],
            'mov ci, 0x02', 'xor a', jumps[1],
            else_label + ':      nop', 'mov ci, 0x03',
            end_label + ':      nop', 'ret'])

    def test_while(self):
        lines = main_lines('byte main() { word a; a <- 3; while (a) { a <- a - 1; } return a; }')
        start = next(l for l in lines if l.startswith('LABEL') and l.endswith('nop'))
        start_label = start.split(':')[0]
        exit_jump = next(l for l in lines if l.startswith('jrx z, :') and l != 'jrx z, :' + start_label)
        exit_label = exit_jump.split(':')[1]
        self.assertSequence(lines, [
            start, 'mov a, cs', 'or ci', exit_jump,
            'sub csci, dsdi', 'xor a', 'jrx z, :' + start_label,
            exit_label + ':      nop', 'ret'])


class TestFunctions(CodegenTestCase):
    SOURCE = '''
byte func(byte param) { return param; }
byte main() { word a; a <- func(7); return a; }
'''

    def test_callee_reads_parameter_and_returns(self):
        basm = compile_source(self.SOURCE)
        lines = function_lines(basm, 'func')
        self.assertTrue(lines[1].startswith('FFUNC0001:'))
        self.assertSequence(lines, ['mov a, 0x00', 'cal :stackvar8gt8', 'ret'])

    def test_call_sets_up_scope_argument_and_calls_label(self):
        lines = function_lines(compile_source(self.SOURCE), 'main')
        self.assertSequence(lines, [
            'mov a, 0x02', 'cal :stackheadrll8',      # push scope: stackhead += 2
            'mov cs, 0x00', 'mov ci, 0x07',           # argument value
            'mov a, 0x00', 'cal :stackvar8st8',       # stored as callee parameter
            'cal :FFUNC0001',
            'mov a, 0x82', 'cal :stackheadrll8',      # pop scope: stackhead -= 2
            'mov a, 0x00', 'cal :stackvar8st16',      # result assigned to a
            'ret'])

    def test_call_to_undeclared_function_is_error(self):
        context = Context(0x1000, 0x3000, False)
        ast = program.parse('byte main() { return nothing(1); }')
        with contextlib.redirect_stdout(io.StringIO()):
            ast.emit(context)
        self.assertEqual(['Undeclared function nothing'], context.errors)

    def test_call_with_wrong_argument_count_is_error(self):
        context = Context(0x1000, 0x3000, False)
        ast = program.parse('byte f(byte p) { return p; } byte main() { return f(1, 2); }')
        with contextlib.redirect_stdout(io.StringIO()):
            ast.emit(context)
        self.assertEqual(1, len(context.errors))
        self.assertIn('Unrecognized function f parameter', context.errors[0])


class TestAsm(CodegenTestCase):
    def test_asm_block_passed_through(self):
        lines = main_lines('byte main() { asm "mov a, 0x55"; asm "nop"; return 1; }')
        self.assertSequence(lines, ['mov a, 0x55', 'nop', 'mov ci, 0x01', 'ret'])


class TestPreprocessor(CodegenTestCase):
    def test_define_substitution(self):
        lines = main_lines('#define ANSWER 0x2a\nbyte main() { return ANSWER; }')
        self.assertContiguous(lines, ['mov cs, 0x00', 'mov ci, 0x2a', 'ret'])

    def test_define_prefers_longest_name(self):
        lines = main_lines('#define AB 1\n#define ABC 2\nbyte main() { return ABC; }')
        self.assertIn('mov ci, 0x02', lines)

    def test_comment_lines_are_dropped(self):
        text = bc.preprocess('// hello\nbyte main() { }', False, '.')
        self.assertEqual('byte main() { }', text)

    def test_include_from_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'inc.b'), 'w', encoding='utf8') as handle:
                handle.write('#define VALUE 0x07\nbyte helper() { return VALUE; }\n')
            source = '#include inc.b\nbyte main() { return helper(); }'
            basm = compile_source(source, tmp)
        self.assertIn(';FUNCTION helper', basm)
        self.assertIn('mov ci, 0x07', function_lines(basm, 'helper'))
        self.assertLess(basm.index(';FUNCTION helper'), basm.index(';FUNCTION main'))
        self.assertIn('cal :FHELPER0001', function_lines(basm, 'main'))


class TestScopeErrors(unittest.TestCase):
    def test_pop_scope_without_parent_raises(self):
        context = Context()
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(CompilerError) as caught:
                context.pop_scope('TEST')
        self.assertEqual('Scope none error', str(caught.exception))

    def test_push_scope_with_negative_offset_raises(self):
        context = Context()
        context.scope.offset = -1
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(CompilerError) as caught:
                context.push_scope('TEST')
        self.assertEqual('Scope push error', str(caught.exception))

    def test_pop_scope_with_negative_difference_raises(self):
        context = Context()
        with contextlib.redirect_stdout(io.StringIO()):
            context.push_scope('TEST')
            context.scope.startoffset = -1
            with self.assertRaises(CompilerError) as caught:
                context.pop_scope('TEST')
        self.assertEqual('Scope pop error', str(caught.exception))

    def test_duplicate_variable_and_unknown_type_are_recorded(self):
        context = Context()
        with contextlib.redirect_stdout(io.StringIO()):
            context.add_variable('word', 'a')
            context.add_variable('word', 'a')
        self.assertEqual(['Variable a was already defined in this scope'], context.errors)

    def test_nested_scope_variable_offset_is_relative(self):
        context = Context()
        context.add_variable('word', 'a')
        context.add_variable('byte', 'b')
        scope = Scope(context, context.scope)
        self.assertEqual(3, scope.startoffset)
        self.assertEqual(-3, scope.get_variable('a')['offset'])
        self.assertEqual(-1, scope.get_variable('b')['offset'])


if __name__ == '__main__':
    unittest.main()
