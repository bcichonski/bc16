import os
import subprocess
import sys
import tempfile
import unittest

from tests.bc_codegen_tests import compile_source

ASM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'bc81asmc', 'bc81asmc.py')
PROGRAM = 'byte main() { return 1; }\n'


def asserts(basm):
    return [line for line in basm.splitlines() if '.assert' in line]


def assemble(basm):
    '''Run the real assembler on basm in a temp dir; returns (exit code, stderr+stdout).'''
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'prog.basm')
        with open(path, 'w', encoding='utf8') as f:
            f.write(basm)
        res = subprocess.run([sys.executable, ASM, path], cwd=tmp, capture_output=True, text=True)
        return res.returncode, res.stdout + res.stderr


class HeapAssertTests(unittest.TestCase):
    def test_default_heap_assert_is_last_line(self):
        basm = compile_source(PROGRAM)
        lines = [l for l in basm.splitlines() if l.strip()]
        self.assertEqual(lines[-2].strip(), 'sys_stackhead: nop')
        self.assertEqual(lines[-1], 'sys_codeend: .assert :sys_codeend < 0x3000')
        self.assertEqual(len(asserts(basm)), 1)

    def test_explicit_heap_assert(self):
        basm = compile_source('#heap 0x5fd0\n' + PROGRAM)
        self.assertEqual(asserts(basm), ['sys_codeend: .assert :sys_codeend < 0x5fd0'])
        compile_source('#heap 0x3000\n' + PROGRAM)  # restore the module default for other tests


class CodeLimitTests(unittest.TestCase):
    def test_codelimit_adds_second_assert_and_does_not_leak(self):
        basm = compile_source('#heap 0x3000\n#codelimit 0x2000\n' + PROGRAM)
        self.assertEqual(asserts(basm), [
            'sys_codeend: .assert :sys_codeend < 0x3000',
            '.assert :sys_codeend < 0x2000'])
        self.assertNotIn('codelimit', basm)
        again = compile_source('#heap 0x3000\n' + PROGRAM)
        self.assertEqual(asserts(again), ['sys_codeend: .assert :sys_codeend < 0x3000'])


class AssembleTests(unittest.TestCase):
    def test_output_assembles_and_asserts_pass(self):
        code, out = assemble(compile_source('#heap 0x3000\n#codelimit 0x2800\n' + PROGRAM))
        self.assertEqual(code, 0, out)

    def test_heap_below_image_end_fails(self):
        code, out = assemble(compile_source('#code 0x1000\n#heap 0x1010\n' + PROGRAM))
        compile_source('#heap 0x3000\n' + PROGRAM)
        self.assertNotEqual(code, 0)
        self.assertIn('assertion failed', out)

    def test_codelimit_below_image_end_fails(self):
        code, out = assemble(compile_source('#code 0x1000\n#heap 0x3000\n#codelimit 0x1010\n' + PROGRAM))
        self.assertNotEqual(code, 0)
        self.assertIn('assertion failed', out)


if __name__ == '__main__':
    unittest.main()
