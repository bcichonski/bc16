import unittest
from parsy import ParseError

from bc81asmc_grammar import program, mnemonic, paramdb
from bc81asmc_diag import (Diagnostic, AssemblerError, format_diagnostic,
                           format_diagnostics, parse_error_to_diagnostic, line_col_at)


def parse_error(text):
    with_error = None
    try:
        program.parse(text)
    except ParseError as e:
        with_error = e
    assert with_error is not None
    return parse_error_to_diagnostic(with_error, text)


class TestSourcePositions(unittest.TestCase):
    def test_line_numbers_across_comments(self):
        ast = program.parse("; first\nnop\n   ; third\n\tkil ; four\n")
        self.assertEqual([n.lineno for n in ast], [1, 2, 3, 4])

    def test_first_non_blank_column(self):
        ast = program.parse("nop\n  nop\n\tnop\n  lbl: nop\n")
        self.assertEqual([n.col for n in ast], [1, 3, 2, 3])

    def test_label_definition_column(self):
        ast = program.parse("start: nop\n   mid: nop\n\tend: nop\n")
        self.assertEqual([n.label_col for n in ast], [1, 4, 2])
        self.assertEqual([n.label for n in ast], ['start', 'mid', 'end'])
        self.assertEqual(ast[1].label.line, 2)

    def test_label_reference_columns_per_form(self):
        ast = program.parse(
            "cal :f\n"
            "  jmr z, :l\n"
            "jrx nz, :l2\n"
            "clr :f\n"
            ".mv dsdi, :x\n"
            ".db :a, 'q', 0x01, :b\n")
        cal, jmr, jrx, clr, mv, db = ast
        self.assertEqual((cal.arg, cal.arg.col, cal.arg.line), (':f', 5, 1))
        self.assertEqual((jmr.arg, jmr.arg.col), (':l', 10))
        self.assertEqual((jrx.arg, jrx.arg.col), (':l2', 9))
        self.assertEqual((clr.arg, clr.arg.col), (':f', 5))
        self.assertEqual((mv.lbl, mv.lbl.col, mv.lbl.line), (":x", 11, 5))
        refs = [v for v in db.values if hasattr(v, 'col')]
        self.assertEqual([(str(r), r.col) for r in refs], [(':a', 5), (':b', 20)])

    def test_positions_do_not_change_equality(self):
        ast = program.parse("  nop\ncal :f\n")
        self.assertEqual(ast[0], mnemonic.parse('nop'))
        self.assertEqual(ast[1].arg, ':f')
        self.assertEqual(paramdb.parse(':ab'), ':ab')

    def test_line_col_at(self):
        text = "ab\r\ncd\ref\n"
        self.assertEqual(line_col_at(text, 0), (1, 1))
        self.assertEqual(line_col_at(text, 4), (2, 1))
        self.assertEqual(line_col_at(text, 7), (3, 1))
        self.assertEqual(line_col_at(text, 10), (4, 1))


class TestFormatter(unittest.TestCase):
    def test_spaces(self):
        out = format_diagnostic(Diagnostic(2, 5, 'boom'), "nop\n    cal :x\n", 'a.basm')
        self.assertEqual(out, "a.basm:2:5: error: boom\n    cal :x\n    ^")

    def test_tabs_kept_in_caret_line(self):
        out = format_diagnostic(Diagnostic(1, 4, 'm'), "\t\t cal\n", 'f')
        self.assertEqual(out.split("\n"), ["f:1:4: error: m", "\t\t cal", "\t\t ^"])

    def test_crlf_and_cr_sources(self):
        for term in ("\r\n", "\r"):
            out = format_diagnostic(Diagnostic(2, 1, 'm'), "nop" + term + "kil" + term, 'f')
            self.assertEqual(out, "f:2:1: error: m\nkil\n^")

    def test_past_end_of_line(self):
        out = format_diagnostic(Diagnostic(1, 4, 'm'), "nop\r\nkil\r\n", 'f')
        self.assertEqual(out, "f:1:4: error: m\nnop\n   ^")

    def test_past_end_of_file(self):
        out = format_diagnostic(Diagnostic(2, 4, 'm'), "nop\nkil", 'f')
        self.assertEqual(out, "f:2:4: error: m\nkil\n   ^")

    def test_format_many(self):
        out = format_diagnostics([Diagnostic(1, 1, 'a'), Diagnostic(2, 1, 'b')], "x\ny\n", 'f')
        self.assertEqual(out, "f:1:1: error: a\nx\n^\nf:2:1: error: b\ny\n^\n")


class TestAssemblerError(unittest.TestCase):
    def test_carries_diagnostics_and_lists_messages(self):
        diags = [Diagnostic(1, 1, 'first'), Diagnostic(3, 2, 'second')]
        err = AssemblerError(diags)
        self.assertEqual(err.diagnostics, diags)
        self.assertIn('first', str(err))
        self.assertIn('second', str(err))
        self.assertIsInstance(err, Exception)


class TestParseErrorConversion(unittest.TestCase):
    def test_unknown_mnemonic(self):
        d = parse_error("nop\n  foo r\n")
        self.assertEqual((d.line, d.column, d.severity), (2, 6, 'error'))  # parsy's furthest failure: after 'foo', where a ':' was expected
        self.assertTrue(d.message.startswith('syntax error:'))

    def test_three_digit_immediate(self):
        d = parse_error("nop\n\tmov a, 0x100\n")
        self.assertEqual((d.line, d.column), (2, 13))
        self.assertTrue(d.message.startswith('syntax error:'))

    def test_small_expected_set_is_listed(self):
        d = parse_error("jmr z, :l\njmp q, :x\n")
        self.assertEqual(d.line, 2)
        self.assertTrue(d.message.startswith('syntax error: expected'))

    def test_missing_final_newline(self):
        d = parse_error("nop\nkil")
        self.assertEqual((d.line, d.column), (2, 4))
        self.assertTrue(d.message.startswith('syntax error:'))

    def test_end_of_line_found(self):
        d = parse_error("nop\n  \n")
        self.assertEqual(d.line, 2)
        self.assertIn('end of line', d.message)


if __name__ == '__main__':
    unittest.main()
