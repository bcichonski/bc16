import unittest

from bc_ast import CompilerError, Context, EXPRESSION_CONSTANT, STATEMENT_RETURN
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


class TestReturnGuard(unittest.TestCase):
    def test_return_in_inner_scope_raises(self):
        context = Context()
        context.push_scope('FUNC')
        context.push_scope('INNER')
        with self.assertRaises(CompilerError):
            STATEMENT_RETURN(EXPRESSION_CONSTANT(1)).emit(context)
        self.assertTrue(context.errors)

    def test_return_in_function_scope_is_fine(self):
        context = Context()
        context.push_scope('FUNC')
        STATEMENT_RETURN(EXPRESSION_CONSTANT(1)).emit(context)
        self.assertFalse(context.errors)


if __name__ == '__main__':
    unittest.main()
