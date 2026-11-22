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

import bc
import bc_log


def pre(source):
    return bc.preprocess(source, False, '.')


class TestDefineTokens(unittest.TestCase):
    def test_whole_token_in_code_is_replaced(self):
        self.assertEqual('x <- 10 + y;', pre('#define MAX 10\nx <- MAX + y;'))

    def test_longer_identifier_is_untouched(self):
        self.assertEqual('MAXLINE + MY_MAX + 10', pre('#define MAX 10\nMAXLINE + MY_MAX + MAX'))

    def test_non_asm_string_is_untouched(self):
        self.assertEqual('puts("MAX"); 10', pre('#define MAX 10\nputs("MAX"); MAX'))

    def test_char_literals_are_untouched(self):
        self.assertEqual('c <- \'"\'; d <- 10; e <- \'/\'; f <- 10;',
                         pre('#define MAX 10\nc <- \'"\'; d <- MAX; e <- \'/\'; f <- MAX;'))
        self.assertEqual("c <- 'M'; 10", pre("#define M 10\nc <- 'M'; M"))

    def test_trailing_comment_is_untouched(self):
        self.assertEqual('x <- 10; // MAX stays', pre('#define MAX 10\nx <- MAX; // MAX stays'))

    def test_slash_in_string_does_not_start_comment(self):
        self.assertEqual('puts("//"); 10', pre('#define MAX 10\nputs("//"); MAX'))

    def test_asm_string_replaces_whole_tokens_only(self):
        self.assertEqual('asm "mov ci, 0x41 ; MAXX";', pre('#define MAX 0x41\nasm "mov ci, MAX ; MAXX";'))
        self.assertEqual('asm  "mov ci, 7";', pre('#define MAX 7\nasm  "mov ci, MAX";'))

    def test_string_after_other_identifier_is_not_asm(self):
        self.assertEqual('xasm "MAX"', pre('#define MAX 7\nxasm "MAX"'))

    def test_hex_number_is_untouched(self):
        self.assertEqual('y <- 0x10 + 0xFF; 5', pre('#define x10 5\n#define xFF 6\ny <- 0x10 + 0xFF; x10'))

    def test_hex_digits_with_define_name_letters(self):
        self.assertEqual('a <- 0xAB; 9', pre('#define AB 9\na <- 0xAB; AB'))
        self.assertEqual('a <- 0xAB; 9', pre('#define xAB 3\n#define AB 9\na <- 0xAB; AB'))

    def test_value_with_spaces(self):
        self.assertEqual('x <- (1 + 2) * 3;', pre('#define EXPR (1 + 2)\nx <- EXPR * 3;'))

    def test_value_is_not_rescanned(self):
        self.assertEqual('B', pre('#define A B\n#define B 1\nA'))

    def test_redefinition_warns_and_last_wins(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            text = pre('#define V 1\n#define V 2\nV')
        self.assertEqual('2', text)
        self.assertIn('warning', err.getvalue())
        self.assertIn('V', err.getvalue())

    def test_same_value_redefinition_is_silent(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            text = pre('#define V 1\n#define V 1\nV')
        self.assertEqual('1', text)
        self.assertEqual('', err.getvalue())

    def test_malformed_define_is_an_error(self):
        for source in ('#define\nx', '#define ONLY\nx', '#define 1BAD 2\nx', '#define A-B 2\nx'):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
                pre(source)
            self.assertEqual(1, cm.exception.code, source)
            self.assertIn('error:', err.getvalue(), source)


class TestDefineCli(unittest.TestCase):
    def test_malformed_define_has_no_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'prog.b'), 'w', encoding='utf8') as f:
                f.write('#define NAME\nbyte main() { return 0; }\n')
            res = subprocess.run([sys.executable, BC, 'prog.b'], cwd=tmp, capture_output=True, text=True)
        self.assertEqual(1, res.returncode)
        self.assertIn('prog.b: error:', res.stderr)
        self.assertNotIn('Traceback', res.stderr)


if __name__ == '__main__':
    unittest.main()
