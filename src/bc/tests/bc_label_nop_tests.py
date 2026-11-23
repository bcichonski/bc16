import os
import re
import unittest

from tests.bc_codegen_tests import compile_source, main_lines
from tests.bc_assert_tests import assemble, ASM

LABEL_ONLY = re.compile(r'^(LABEL\d+|F[A-Z0-9_]*\d{4}):$')

SOURCE = '''
byte helper(byte x) {
    if (x) { x <- 2; } else { x <- 3; }
    return x;
}
byte main() {
    word a;
    a <- 3;
    if (a) { if (a) { a <- 1; } }
    while (a) { a <- a - 1; }
    if (a) { a <- 5; } else { a <- helper(a); }
    return a;
}
'''


def image_size(basm):
    import subprocess, sys, tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'prog.basm')
        with open(path, 'w', encoding='utf8') as f:
            f.write(basm)
        res = subprocess.run([sys.executable, ASM, path], cwd=tmp, capture_output=True, text=True)
        assert res.returncode == 0, res.stdout + res.stderr
        return os.path.getsize(os.path.join(tmp, 'prog.btap'))


class LabelWithoutNopTests(unittest.TestCase):
    def test_function_start_is_label_only(self):
        lines = main_lines('byte main() { }')
        self.assertEqual('FMAIN0001:', lines[1])
        self.assertNotIn('nop', lines)

    def test_if_without_else_label_only(self):
        lines = main_lines('byte main() { word a; a <- 1; if (a) { a <- 2; } return a; }')
        self.assertEqual(1, sum(1 for l in lines if LABEL_ONLY.match(l) and l.startswith('LABEL')))
        self.assertFalse([l for l in lines if 'nop' in l])

    def test_if_else_label_only(self):
        lines = main_lines('byte main() { word a; a <- 1; if (a) { a <- 2; } else { a <- 3; } return a; }')
        self.assertEqual(2, sum(1 for l in lines if l.startswith('LABEL') and LABEL_ONLY.match(l)))
        self.assertFalse([l for l in lines if 'nop' in l])

    def test_while_label_only(self):
        lines = main_lines('byte main() { word a; a <- 3; while (a) { a <- a - 1; } return a; }')
        self.assertEqual(2, sum(1 for l in lines if l.startswith('LABEL') and LABEL_ONLY.match(l)))
        self.assertFalse([l for l in lines if 'nop' in l])

    def test_no_label_line_has_nop_except_stackhead(self):
        basm = compile_source(SOURCE)
        for line in basm.splitlines():
            if re.match(r'^\w+:', line) and re.search(r'\bnop\b', line):
                self.assertTrue(line.startswith('sys_stackhead:'), line)

    def test_consecutive_labels_assemble_and_save_bytes(self):
        basm = compile_source(SOURCE)
        labels = [l for l in basm.splitlines() if LABEL_ONLY.match(l)]
        self.assertGreater(len(labels), 5)
        # consecutive label-only lines exist (nested ifs ending together)
        lines = [l.strip() for l in basm.splitlines() if l.strip()]
        self.assertTrue(any(LABEL_ONLY.match(a) and LABEL_ONLY.match(b) for a, b in zip(lines, lines[1:])))
        code, out = assemble(basm)
        self.assertEqual(code, 0, out)
        with_nops = '\n'.join(l + '      nop' if LABEL_ONLY.match(l.strip()) else l for l in basm.splitlines()) + '\n'
        self.assertGreater(image_size(with_nops), image_size(basm))
