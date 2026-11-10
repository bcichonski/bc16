import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bc81asmc.py')


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def run_asm(self, source, *flags, name='prog.basm'):
        with open(os.path.join(self.dir, name), 'w', encoding='utf8', newline='') as f:
            f.write(source)
        result = subprocess.run([sys.executable, SCRIPT, *flags, name], cwd=self.dir,
                                capture_output=True, text=True)
        return result

    def btap_exists(self, name='prog.btap'):
        return os.path.exists(os.path.join(self.dir, name))


class TestValidRun(CliCase):
    def test_valid_source_quiet_stderr_and_btap(self):
        r = self.run_asm("start: nop\nnop\n")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, '')
        self.assertIn('Done!', r.stdout)
        self.assertTrue(self.btap_exists())


class TestParseError(CliCase):
    def test_parse_error_block(self):
        r = self.run_asm("nop\nmov a, 0x100\n")
        self.assertEqual(r.returncode, 1)
        lines = r.stderr.splitlines()
        self.assertTrue(lines[0].startswith('prog.basm:2:'), lines[0])
        self.assertIn(': error: ', lines[0])
        self.assertEqual(lines[1], 'mov a, 0x100')
        self.assertTrue(lines[2].endswith('^'))
        self.assertEqual(lines[2].strip(), '^')
        self.assertNotIn('Traceback', r.stderr)
        self.assertFalse(self.btap_exists())

    def test_parse_error_verbose_traceback_follows(self):
        r = self.run_asm("nop\nmov a, 0x100\n", '--verbose')
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith('prog.basm:2:'))
        self.assertIn('Traceback', r.stderr)
        self.assertLess(r.stderr.index('error:'), r.stderr.index('Traceback'))
        self.assertFalse(self.btap_exists())


class TestUndefinedLabels(CliCase):
    def test_all_reported_sorted_with_caret(self):
        r = self.run_asm("nop\ncal :b\nnop\n.db :a\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.splitlines(), [
            "prog.basm:2:5: error: undefined label ':b'",
            "cal :b",
            "    ^",
            "prog.basm:4:5: error: undefined label ':a'",
            ".db :a",
            "    ^"])
        self.assertFalse(self.btap_exists())

    def test_verbose_appends_traceback(self):
        r = self.run_asm("cal :b\n", '--verbose')
        self.assertEqual(r.returncode, 1)
        self.assertIn("prog.basm:1:5: error: undefined label ':b'", r.stderr)
        self.assertIn('Traceback', r.stderr)
        self.assertIn('AssemblerError', r.stderr)


class TestDuplicateLabel(CliCase):
    def test_duplicate_label(self):
        r = self.run_asm("a: nop\nnop\n  a: nop\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.splitlines()[0],
                         "prog.basm:3:3: error: duplicate label 'a' (first defined at line 1)")
        self.assertNotIn('Traceback', r.stderr)
        self.assertFalse(self.btap_exists())


class TestRangeError(CliCase):
    def test_relative_jump_out_of_range(self):
        r = self.run_asm("jmr z, :far\n" + "nop\n" * 200 + "far: nop\n")
        self.assertEqual(r.returncode, 1)
        first = r.stderr.splitlines()[0]
        self.assertTrue(first.startswith('prog.basm:1:'), first)
        self.assertIn('too far away for relative 7bit jump', first)
        self.assertNotIn('Traceback', r.stderr)
        self.assertFalse(self.btap_exists())


class TestOverflow(CliCase):
    def test_code_past_0xffff(self):
        r = self.run_asm(".org 0xffff\nnop\n nop\nnop\n")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr.splitlines()[0], r'^prog\.basm:3:2: error: code exceeds')
        self.assertNotIn('Traceback', r.stderr)
        self.assertFalse(self.btap_exists())


class TestFileNameAsGiven(CliCase):
    def test_path_in_header_is_as_given(self):
        os.mkdir(os.path.join(self.dir, 'sub'))
        with open(os.path.join(self.dir, 'sub', 'x.basm'), 'w') as f:
            f.write("cal :zz\n")
        r = subprocess.run([sys.executable, SCRIPT, 'sub/x.basm'], cwd=self.dir,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("sub/x.basm:1:5: error:"))


if __name__ == '__main__':
    unittest.main()
