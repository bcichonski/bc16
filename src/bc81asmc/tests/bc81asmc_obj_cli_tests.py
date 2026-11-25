"""The `--obj` and `--dump` command line (#115), run as subprocesses."""
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bc81asmc.py')

SOURCE = (".global main\n"
          ".extern helper\n"
          ".sect main\n"
          "main:   .mv csci, :text\n"
          "        cal :helper\n"
          "        jmr z, :main\n"
          "        ret\n"
          "text:   .db 'ok', 0x00\n")


class ObjCliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def write(self, name, data):
        mode = 'wb' if isinstance(data, bytes) else 'w'
        with open(os.path.join(self.dir, name), mode) as f:
            f.write(data)

    def run_asm(self, *args, env=None):
        return subprocess.run([sys.executable, SCRIPT, *args], cwd=self.dir, capture_output=True, text=True,
                              env=env)

    def exists(self, name):
        return os.path.exists(os.path.join(self.dir, name))

    def read(self, name):
        with open(os.path.join(self.dir, name), 'rb') as f:
            return f.read()


class TestObj(ObjCliCase):
    def test_writes_o_and_no_btap(self):
        self.write('prog.basm', SOURCE)
        r = self.run_asm('--obj', 'prog.basm')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, '')
        self.assertIn('Done!', r.stdout)
        self.assertTrue(self.exists('prog.o'))
        self.assertFalse(self.exists('prog.btap'))
        self.assertEqual(self.read('prog.o')[:7], b'\xb0\x05\x01PROG')

    def test_error_writes_nothing(self):
        self.write('prog.basm', "nop\n.global nowhere\n")
        r = self.run_asm('--obj', 'prog.basm')
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("prog.basm:2:9: error: '.global nowhere' is never defined"), r.stderr)
        self.assertFalse(self.exists('prog.o'))
        self.assertFalse(self.exists('prog.btap'))

    def test_relocatable_assert_warning(self):
        self.write('prog.basm', "nop\nend: .assert :end <= 0x0010\n")
        r = self.run_asm('--obj', 'prog.basm')
        self.assertEqual(r.returncode, 0)
        lines = r.stderr.splitlines()
        self.assertEqual(lines[0], "prog.basm:2:14: warning: .assert not checked with --obj: ':end' is relocatable")
        self.assertEqual(lines[1], "end: .assert :end <= 0x0010")
        self.assertTrue(self.exists('prog.o'))

    def test_obj_with_lst_or_map_is_usage_error(self):
        self.write('prog.basm', SOURCE)
        for flag in ('--lst', '--map'):
            r = self.run_asm('--obj', flag, 'x.txt', 'prog.basm')
            self.assertEqual(r.returncode, 2, flag)
            self.assertIn('--obj cannot be combined with --lst or --map', r.stderr)
            self.assertFalse(self.exists('prog.o'))

    def test_deterministic_across_processes(self):
        self.write('prog.basm', SOURCE)
        outputs = []
        for seed in ('1', '12345'):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            r = self.run_asm('--obj', 'prog.basm', env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            outputs.append(self.read('prog.o'))
            os.remove(os.path.join(self.dir, 'prog.o'))
        self.assertEqual(outputs[0], outputs[1])

    def test_plain_run_still_writes_btap(self):
        self.write('prog.basm', SOURCE.replace('        cal :helper\n', ''))
        r = self.run_asm('prog.basm')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.exists('prog.btap'))
        self.assertFalse(self.exists('prog.o'))
        self.assertEqual(r.stdout.splitlines(), [
            'Reading input file prog.basm', 'Parsing code', 'Generating code', 'Code length: 10 labels: 2',
            'Saving output file prog.btap...', 'Creating btap file from 0000 for 000a', 'Done!'])


class TestDump(ObjCliCase):
    def test_dump_prints_records(self):
        self.write('prog.basm', SOURCE)
        self.assertEqual(self.run_asm('--obj', 'prog.basm').returncode, 0)
        r = self.run_asm('--dump', 'prog.o')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, '')
        self.assertEqual(r.stdout.splitlines(), [
            "0000  b0 HEADER   version 01 module 'PROG'",
            "0007  55 SECTSTAT 'main'",
            "000d  91 GLOBL    'main' @0000",
            "0013  c0 CODE     @0000 4 bytes: 18 00 14 00",
            "0019  fb HILO     offset 01 -> label 0",
            "001e  ee EXTRN    symbol 0 'helper'",
            "0026  c0 CODE     @0004 3 bytes: a8 00 00",
            "002b  f1 ABS16    offset 01 -> symbol 0 'helper'",
            "002e  ee EXTRN    symbol 1 'main'",
            "0034  c0 CODE     @0007 3 bytes: 70 00 b0",
            "0039  fa REL7     offset 01 -> symbol 1 'main'",
            "003e  1a LABEL    label 0 @000a",
            "0042  c0 CODE     @000a 3 bytes: 6f 6b 00",
            "0047  ed END",
        ])

    def test_malformed_file(self):
        self.write('bad.o', b'\xb0\x02\x02X\xed\x00')
        r = self.run_asm('--dump', 'bad.o')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, '')
        self.assertEqual(r.stderr, 'bad.o: error: at byte offset 0: unsupported BOF version 02, expected 01\n')

    def test_truncated_file(self):
        self.write('bad.o', b'\xb0\x02\x01X\xc0\x05\x00')
        r = self.run_asm('--dump', 'bad.o')
        self.assertEqual(r.returncode, 1)
        self.assertIn('bad.o: error: at byte offset 4: truncated record', r.stderr)

    def test_missing_file(self):
        r = self.run_asm('--dump', 'none.o')
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith('none.o: error: cannot read the file'), r.stderr)


if __name__ == '__main__':
    unittest.main()
