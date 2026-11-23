import unittest

from bc_ast import Context, EXPRESSION_CONSTANT, STATEMENT_RETURN
from tests.bc_codegen_tests import CodegenTestCase, compile_source, function_lines


def lines_of(source, name='f'):
    return function_lines(compile_source(source), name)


class TestSingleTrailingRet(CodegenTestCase):
    def test_function_ending_in_return_has_one_ret(self):
        lines = lines_of('byte f() { return 1; } byte main() { return f(); }')
        self.assertEqual(lines[-1], 'ret')
        self.assertNotEqual(lines[-2], 'ret')
        self.assertEqual(lines.count('ret'), 1)

    def test_function_without_return_ends_with_ret(self):
        lines = lines_of('byte f() { byte a; a <- 1; } byte main() { f(); return 0; }')
        self.assertEqual(lines[-1], 'ret')

    def test_empty_function_ends_with_ret(self):
        lines = lines_of('byte f() { } byte main() { f(); return 0; }')
        self.assertEqual(lines[-1], 'ret')

    def test_if_else_returns_still_get_trailing_ret(self):
        lines = lines_of('byte f(byte a) { if (a) { return 1; } else { return 2; } } '
                         'byte main() { return f(1); }')
        self.assertEqual(lines[-1], 'ret')
        self.assertEqual(lines.count('ret'), 3)


class TestReturnFromNestedBlocks(CodegenTestCase):
    def test_nested_return_is_direct_ret_without_stackhead_moves(self):
        src = ('byte f(byte a) { byte b; b <- 2; '
               'while (a) { if (a) { if (b) { return a; } } a <- a - 1; } '
               'return 0; } byte main() { return f(1); }')
        lines = lines_of(src)
        rets = [i for i, l in enumerate(lines) if l == 'ret']
        self.assertEqual(len(rets), 2)
        self.assertEqual(lines[-1], 'ret')
        self.assertNotEqual(lines[rets[0] - 1], 'ret')
        self.assertFalse([l for l in lines if 'stackheadrll8' in l or 'stackheadroll' in l])


class TestReturnUnwindsInnerScopes(unittest.TestCase):
    '''No B source opens an inner scope yet (blocks open none, #24); these build one by hand.'''

    def return_lines(self, context):
        start = len(context.basm)
        STATEMENT_RETURN(EXPRESSION_CONSTANT(0x1234)).emit(context)
        self.assertFalse(context.errors)
        return [l.strip() for l in context.basm[start:].splitlines()
                if l.strip() and not l.strip().startswith(';')]

    def function_context(self, locals_bytes):
        context = Context()
        context.push_scope('FUNC')
        for n in range(locals_bytes):
            context.add_variable('byte', 'v{0}'.format(n))
        return context

    def test_return_in_function_scope_moves_nothing(self):
        lines = self.return_lines(self.function_context(3))
        self.assertEqual(lines, ['mov cs, 0x12', 'mov ci, 0x34', 'ret'])

    def test_return_in_inner_scope_moves_stackhead_back_then_rets(self):
        context = self.function_context(3)
        context.push_scope('INNER')
        lines = self.return_lines(context)
        self.assertEqual(lines, ['mov cs, 0x12', 'mov ci, 0x34',
                                 'mov a, 0x83', 'cal :stackheadrll8', 'ret'])
        self.assertEqual(context.scope.depth, 2, 'return must not change the compile-time scope chain')

    def test_two_inner_scopes_unwind_in_one_move(self):
        context = self.function_context(3)
        context.push_scope('INNER')
        context.add_variable('word', 'w')
        context.push_scope('INNER2')
        lines = self.return_lines(context)
        self.assertEqual(lines, ['mov cs, 0x12', 'mov ci, 0x34',
                                 'mov a, 0x85', 'cal :stackheadrll8', 'ret'])

    def test_large_inner_offset_keeps_csci(self):
        context = self.function_context(200)
        context.push_scope('INNER')
        lines = self.return_lines(context)
        self.assertEqual(lines, ['mov cs, 0x12', 'mov ci, 0x34', 'psh cs', 'psh ci',
                                 'mov cs, 0x00', 'mov ci, 0xc8', 'mov a, 0x01',
                                 'cal :stackheadroll', 'pop ci', 'pop cs', 'ret'])


if __name__ == '__main__':
    unittest.main()
