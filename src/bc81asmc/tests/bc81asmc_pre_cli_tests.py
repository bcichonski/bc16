import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bc81asmc.py')


class PreCliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def write(self, name, text):
        with open(os.path.join(self.dir, name), 'w', encoding='utf8', newline='') as f:
            f.write(text)

    def run_asm(self, source, *flags):
        self.write('prog.basm', source)
        return subprocess.run([sys.executable, SCRIPT, *flags, 'prog.basm'], cwd=self.dir,
                              capture_output=True, text=True)

    def btap(self):
        return os.path.join(self.dir, 'prog.btap')


class TestPreCli(PreCliCase):
    def test_header_error_block_names_header_path_and_line(self):
        self.write('hdr.h', "#define A 1\nbyte main() { return 0; }\n")
        r = self.run_asm("#include hdr.h\nnop\n")
        self.assertEqual(r.returncode, 1)
        lines = r.stderr.splitlines()
        self.assertTrue(lines[0].startswith('hdr.h:2:1: error: '), r.stderr)
        self.assertEqual(lines[1], 'byte main() { return 0; }')
        self.assertEqual(lines[2], '^')
        self.assertFalse(os.path.exists(self.btap()))

    def test_all_pre_errors_reported(self):
        r = self.run_asm("#define\n#link\n#include nope.h\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.count('error:'), 3)
        self.assertIn('prog.basm:3:10: error: cannot read include file', r.stderr)

    def test_warning_block_and_exit_zero(self):
        r = self.run_asm("#define X 1\n#define X 2\nnop\n")
        self.assertEqual(r.returncode, 0)
        lines = r.stderr.splitlines()
        self.assertEqual(lines[0], "prog.basm:2:9: warning: 'X' redefined: '2' replaces '1'")
        self.assertEqual(lines[1], '#define X 2')
        self.assertTrue(os.path.exists(self.btap()))

    def test_directives_give_identical_btap(self):
        plain = self.run_asm("start: nop\nmov a, 0x01\ncal :start\n")
        self.assertEqual(plain.returncode, 0)
        with open(self.btap(), 'rb') as f:
            expected = f.read()
        os.remove(self.btap())
        r = self.run_asm("#define X 1\n#link foo\nstart: nop\nmov a, 0x01\ncal :start\n")
        self.assertEqual(r.returncode, 0)
        with open(self.btap(), 'rb') as f:
            self.assertEqual(f.read(), expected)


if __name__ == '__main__':
    unittest.main()
