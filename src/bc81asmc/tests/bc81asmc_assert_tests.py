import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

import parsy

import bc81asmc
from bc81asmc_ast import ASSERT
from bc81asmc_diag import AssemblerError
from bc81asmc_grammar import program

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bc81asmc.py')


def compile_source(source):
    with contextlib.redirect_stdout(io.StringIO()):
        return bc81asmc.compile(program.parse(source), False)


def errors_of(source):
    with contextlib.redirect_stdout(io.StringIO()):
        with unittest.TestCase().assertRaises(AssemblerError) as cm:
            bc81asmc.compile(program.parse(source), False)
    return [(d.line, d.column, d.message) for d in cm.exception.diagnostics]


class TestAssertGrammar(unittest.TestCase):
    def parse_one(self, text):
        nodes = program.parse(text + "\n")
        self.assertEqual(len(nodes), 1)
        return nodes[0]

    def test_all_operators(self):
        for op in ['=', '!=', '<', '<=', '>', '>=']:
            node = self.parse_one(".assert :a {0} 0x0d80".format(op))
            self.assertIsInstance(node, ASSERT)
            self.assertEqual((node.left, node.op, node.right), (':a', op, '0x0d80'))

    def test_no_blanks_around_operator(self):
        node = self.parse_one(".assert :a<=0x0d80")
        self.assertEqual((node.left, node.op, node.right), (':a', '<=', '0x0d80'))

    def test_literal_widths(self):
        self.assertEqual(self.parse_one(".assert 0x0010 < 0x20").right, '0x20')
        self.assertEqual(self.parse_one(".assert 0x0010 < 0x20").left.value, 0x10)
        self.assertEqual(self.parse_one(".assert 0x10 < :b").left, '0x10')

    def test_label_and_comment(self):
        node = self.parse_one("end: .assert :end <= 0x0e80 ; check")
        self.assertEqual(node.label, 'end')
        self.assertEqual(node.comment, '; check')

    def test_rejected_forms(self):
        for text in [".assert :a == 0x0001", ".assert :a+0x01 < 0x0010", ".assert :a < 10",
                     ".assert :a", ".assert :a <", ".ASSERT :a < 0x0010", ".assert :a ! 0x0010"]:
            with self.assertRaises(parsy.ParseError, msg=text):
                program.parse(text + "\n")

    def test_str(self):
        self.assertEqual(str(self.parse_one(".assert :a <= 0x0d80")), ".ASSERT :a <= 0x0d80")


class TestAssertEmit(unittest.TestCase):
    def test_emits_no_bytes(self):
        ctx = compile_source("nop\n.assert 0x0001 = 0x0001\nnop\n")
        self.assertEqual(list(ctx.bytes), [0x00, 0x00])

    def test_same_output_with_and_without(self):
        plain = compile_source(".org 0x0e00\nstart: nop\ncal :start\n")
        asserted = compile_source(".org 0x0e00\nstart: nop\n.assert :start = 0x0e00\ncal :start\n.assert :start < 0x0e10\n")
        self.assertEqual(plain.bytes, asserted.bytes)
        self.assertEqual(plain.startaddr, asserted.startaddr)

    def test_label_on_assert_line_is_current_address(self):
        ctx = compile_source(".org 0x0e00\nnop\nnop\nend: .assert :end = 0x0e02\nnop\n.db :end\n")
        self.assertEqual(list(ctx.bytes), [0x00, 0x00, 0x00, 0x0e, 0x02])

    def test_nibble_state_untouched(self):
        ctx = compile_source("inc a\n.assert 0x0001 = 0x0001\ninc a\n")
        self.assertEqual(ctx.bytes, compile_source("inc a\ninc a\n").bytes)


class TestAssertCompile(unittest.TestCase):
    def test_passing_operand_kinds(self):
        compile_source(".def lim, 0x0d80\n.org 0x0e00\nend: nop\n"
                       ".assert :end = 0x0e00\n.assert :lim = 0x0d80\n.assert 0x0001 < 0x02\n"
                       ".assert :end > :lim\n")

    def test_forward_reference(self):
        compile_source(".assert :later = 0x0001\nnop\nlater: nop\n")

    def test_def_before_label_lookup_and_zero_defined(self):
        compile_source(".def zero, 0x0000\n.assert :zero = 0x0000\n")
        compile_source("start: nop\n.assert :start = 0x0000\n")

    def test_each_operator_true_and_false(self):
        cases = {'=': (1, 1, 1, 2), '!=': (1, 2, 1, 1), '<': (1, 2, 2, 2), '<=': (2, 2, 3, 2),
                 '>': (2, 1, 2, 2), '>=': (2, 2, 1, 2)}
        for op, (a, b, fa, fb) in cases.items():
            compile_source(".assert 0x{0:04x} {2} 0x{1:04x}\n".format(a, b, op))
            self.assertEqual(
                errors_of(".assert 0x{0:04x} {2} 0x{1:04x}\n".format(fa, fb, op)),
                [(1, 1, "assertion failed: 0x{0:04x} {2} 0x{1:04x} (0x{0:04x} {2} 0x{1:04x})".format(fa, fb, op))])

    def test_failure_message_and_position(self):
        source = ".org 0x0e00\nnop\n  .assert :user_mem <= 0x0d80\nuser_mem: nop\n"
        self.assertEqual(errors_of(source), [
            (3, 3, "assertion failed: :user_mem <= 0x0d80 (0x0e01 <= 0x0d80)")])

    def test_literals_shown_as_written(self):
        self.assertEqual(errors_of(".assert 0x10 > 0x0020\n"),
                         [(1, 1, "assertion failed: 0x10 > 0x0020 (0x0010 > 0x0020)")])

    def test_label_on_failing_line_column_is_first_nonblank(self):
        self.assertEqual(errors_of("  end: .assert :end = 0x0001\n"),
                         [(1, 3, "assertion failed: :end = 0x0001 (0x0000 = 0x0001)")])

    def test_all_failures_reported_sorted_with_other_errors(self):
        source = ".assert 0x0001 = 0x0002\ncal :nowhere\n.assert 0x0003 < 0x0001\n"
        self.assertEqual(errors_of(source), [
            (1, 1, "assertion failed: 0x0001 = 0x0002 (0x0001 = 0x0002)"),
            (2, 5, "undefined label ':nowhere'"),
            (3, 1, "assertion failed: 0x0003 < 0x0001 (0x0003 < 0x0001)")])

    def test_undefined_label_only_undefined_diagnostic(self):
        self.assertEqual(errors_of("nop\n  .assert :nope < 0x0010\n"),
                         [(2, 11, "undefined label ':nope'")])

    def test_both_operands_undefined(self):
        self.assertEqual(errors_of(".assert :a = :b\n"), [
            (1, 9, "undefined label ':a'"), (1, 14, "undefined label ':b'")])

    def test_one_undefined_one_failing_literal(self):
        self.assertEqual(errors_of(".assert 0x0001 = :b\n"), [(1, 18, "undefined label ':b'")])


class TestAssertCli(unittest.TestCase):
    def test_failed_assert_stderr_exit_and_no_btap(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'prog.basm'), 'w', encoding='utf8', newline='') as f:
                f.write("nop\n.assert 0x0001 = 0x0002\n")
            r = subprocess.run([sys.executable, SCRIPT, 'prog.basm'], cwd=d,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            lines = r.stderr.splitlines()
            self.assertEqual(lines[0],
                'prog.basm:2:1: error: assertion failed: 0x0001 = 0x0002 (0x0001 = 0x0002)')
            self.assertEqual(lines[1], '.assert 0x0001 = 0x0002')
            self.assertEqual(lines[2].strip(), '^')
            self.assertFalse(os.path.exists(os.path.join(d, 'prog.btap')))

    def test_passing_assert_writes_btap(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'prog.basm'), 'w', encoding='utf8', newline='') as f:
                f.write("nop\n.assert 0x0001 = 0x0001\n")
            r = subprocess.run([sys.executable, SCRIPT, '--verbose', 'prog.basm'], cwd=d,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('.ASSERT 0x0001 = 0x0001', r.stdout)
            self.assertTrue(os.path.exists(os.path.join(d, 'prog.btap')))


if __name__ == '__main__':
    unittest.main()
