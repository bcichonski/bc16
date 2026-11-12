import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BC = os.path.join(HERE, '..', 'bc.py')
sys.path.insert(0, os.path.join(HERE, '..'))

import bc_log
from bc_ast import Context

PROGRAM = 'byte main() { word a; a <- 1; return a; }\n'


class OutputTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def run_bc(self, source, *flags):
        src = os.path.join(self.tmp, 'prog.b')
        with open(src, 'w', encoding='utf8') as f:
            f.write(source)
        return subprocess.run([sys.executable, BC, 'prog.b'] + list(flags), cwd=self.tmp,
                              capture_output=True, text=True)

    def path(self, name):
        return os.path.join(self.tmp, name)

    def read(self, name):
        with open(self.path(name), encoding='utf8') as f:
            return f.read()

    def test_quiet_success_prints_one_summary_line(self):
        res = self.run_bc(PROGRAM)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout, 'bc: prog.b -> prog.basm\n')
        self.assertEqual(res.stderr, '')
        self.assertFalse(os.path.exists(self.path('prog.genb')))

    def test_verbose_prints_trace_and_writes_genb(self):
        res = self.run_bc(PROGRAM, '--verbose')
        self.assertEqual(res.returncode, 0, res.stderr)
        for text in ('PUSH SCOPE', 'Parsing code', 'Done!', 'Reading input file prog.b'):
            self.assertIn(text, res.stdout)
        self.assertNotIn('bc: prog.b -> prog.basm', res.stdout)
        self.assertTrue(os.path.exists(self.path('prog.genb')))

    def test_same_basm_with_and_without_verbose(self):
        self.run_bc(PROGRAM)
        quiet = self.read('prog.basm')
        self.run_bc(PROGRAM, '--verbose')
        self.assertEqual(quiet, self.read('prog.basm'))

    def test_undeclared_variable_reported_once_on_stderr(self):
        res = self.run_bc('byte main() { x <- 1; return 1; }\n')
        self.assertEqual(res.returncode, 1)
        self.assertEqual(res.stderr.count('prog.b: error: Undeclared variable x'), 1)
        self.assertNotIn('Traceback', res.stderr)
        self.assertNotIn('Undeclared', res.stdout)
        self.assertFalse(os.path.exists(self.path('prog.basm')))

    def test_undeclared_variable_verbose_keeps_traceback(self):
        res = self.run_bc('byte main() { x <- 1; return 1; }\n', '--verbose')
        self.assertEqual(res.returncode, 1)
        self.assertEqual(res.stderr.count('prog.b: error: Undeclared variable x'), 1)
        self.assertIn('Traceback', res.stderr)

    def test_syntax_error_reports_position_source_line_and_caret(self):
        res = self.run_bc('byte main() { return 1; }\n@@@\n')
        self.assertEqual(res.returncode, 1)
        lines = res.stderr.splitlines()
        self.assertRegex(lines[0], r'^prog\.b: error: syntax error at preprocessed line 2, column \d+: expected ')
        self.assertEqual(lines[1], '@@@')
        self.assertEqual(lines[2], '^')
        self.assertEqual(len(lines), 3)
        self.assertNotIn('Traceback', res.stderr)
        self.assertEqual(res.stdout, '')
        self.assertFalse(os.path.exists(self.path('prog.basm')))

    def test_syntax_error_on_first_line(self):
        res = self.run_bc('@@@\nbyte main() { return 1; }\n')
        self.assertEqual(res.returncode, 1)
        lines = res.stderr.splitlines()
        self.assertRegex(lines[0], r'^prog\.b: error: syntax error at preprocessed line 1, column 1: expected ')
        self.assertEqual(lines[1], '@@@')
        self.assertEqual(lines[2], '^')
        self.assertNotIn('Traceback', res.stderr)

    def test_syntax_error_on_first_line_verbose_does_not_crash(self):
        res = self.run_bc('@@@\nbyte main() { return 1; }\n', '--verbose')
        self.assertEqual(res.returncode, 1)
        self.assertIn('ERR 0: @@@', res.stderr)
        self.assertNotIn('ERR -', res.stderr)
        self.assertIn('Traceback', res.stderr)

    def test_context_add_error_writes_to_stderr_only(self):
        context = Context()
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            context.add_error('boom')
        self.assertEqual(out.getvalue(), '')
        self.assertIn(': error: boom', err.getvalue())
        self.assertEqual(context.errors, ['boom'])

    def test_trace_is_silent_unless_verbose(self):
        try:
            bc_log.set_verbose(False)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                bc_log.trace('hello')
            self.assertEqual(out.getvalue(), '')
        finally:
            bc_log.set_verbose(False)


if __name__ == '__main__':
    unittest.main()
