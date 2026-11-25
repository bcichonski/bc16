"""Defined names (#define) in numeric operands (#114): every operand kind, value forms, widths, diagnostics."""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

import bc81asmc
from bc81asmc_diag import AssemblerError

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bc81asmc.py')


def assemble(text, path='prog.basm'):
    with contextlib.redirect_stdout(io.StringIO()):
        return bc81asmc.assemble_text(text, path)


def bytes_of(text, path='prog.basm'):
    return bytes(assemble(text, path).bytes)


def errors_of(text, path='prog.basm'):
    try:
        assemble(text, path)
    except AssemblerError as e:
        return [(d.line, d.column, d.message) for d in e.diagnostics if d.severity == 'error']
    raise AssertionError('assembly succeeded')


class TestOperandKinds(unittest.TestCase):
    # (define value, line using NAME, the same line with the literal)
    CASES = [
        ('0x12', 'mov a, NAME', 'mov a, 0x12'),
        ('0x12', 'mov ci, NAME', 'mov ci, 0x12'),
        ('0x12', 'add NAME', 'add 0x12'),
        ('0x12', 'sub NAME', 'sub 0x12'),
        ('0x12', 'and NAME', 'and 0x12'),
        ('0x12', 'or NAME', 'or 0x12'),
        ('0x12', 'xor NAME', 'xor 0x12'),
        ('0x12', 'shl NAME', 'shl 0x12'),
        ('0x12', 'shr NAME', 'shr 0x12'),
        ('0x12', 'out #a, NAME', 'out #a, 0x12'),
        ('0x12', 'out #ci, NAME', 'out #ci, 0x12'),
        ('0x1234', 'add csci, NAME', 'add csci, 0x1234'),
        ('0x1234', 'sub dsdi, NAME', 'sub dsdi, 0x1234'),
        ('0x1234', 'mul csci, NAME', 'mul csci, 0x1234'),
        ('0x1234', 'div csci, NAME', 'div csci, 0x1234'),
        ('0x1234', 'mod csci, NAME', 'mod csci, 0x1234'),
        ('0x1234', 'and csci, NAME', 'and csci, 0x1234'),
        ('0x1234', 'or csci, NAME', 'or csci, 0x1234'),
        ('0x1234', 'xor csci, NAME', 'xor csci, 0x1234'),
        ('0x12', 'shl csci, NAME', 'shl csci, 0x12'),
        ('0x12', 'shr dsdi, NAME', 'shr dsdi, 0x12'),
        ('0x9', 'in a, #NAME', 'in a, #0x9'),
        ('0x12', '.db NAME', '.db 0x12'),
        ('0x12', '.db 0x01, NAME, \'s\', NAME', '.db 0x01, 0x12, \'s\', 0x12'),
        ('0x12', '.db :x, NAME, lo(:x), hi(:x)\nx: nop', '.db :x, 0x12, lo(:x), hi(:x)\nx: nop'),
    ]

    def test_each_operand_kind_matches_literal(self):
        for value, with_name, literal in self.CASES:
            with self.subTest(line=with_name):
                self.assertEqual(bytes_of('#define NAME {0}\n{1}\n'.format(value, with_name)),
                                 bytes_of(literal + '\n'))

    def test_org(self):
        self.assertEqual(bytes_of('#define BASE 0x6000\n.org BASE\nnop\n'),
                         bytes_of('.org 0x6000\nnop\n'))
        self.assertEqual(assemble('#define BASE 0x6000\n.org BASE\nnop\n').startaddr, 0x6000)

    def test_def_value(self):
        text = '#define V 4660\n.def K, V\nmov a, 0x00\n.db lo(:K), hi(:K)\n'
        self.assertEqual(bytes_of(text), bytes_of('.def K, 0x1234\nmov a, 0x00\n.db lo(:K), hi(:K)\n'))

    def test_assert_literal(self):
        assemble('#define V 4660\n.assert V = 0x1234\n.assert :a < V\na: nop\n')
        with self.assertRaises(AssemblerError) as ctx:
            assemble('#define V 4660\n.assert V = 0x1235\n')
        self.assertIn('assertion failed', ctx.exception.diagnostics[0].message)

    def test_org_rules_still_apply(self):
        self.assertEqual([m for _, _, m in errors_of('#define B 0x10\nnop\n.org B\n')],
                         ['.org must come before any code or label'])
        self.assertEqual([m for _, _, m in errors_of('#define B 0x10\n.org B\n.org B\n')][0][:14],
                         'duplicate .org')


class TestValueForms(unittest.TestCase):
    def test_forms(self):
        for value, expected in [('0', 0), ('7', 7), ('255', 255), ('0x8', 8), ('0x0f1', 0xf1), ('0x0008', 8),
                                ('0xAB', 0xab), ('0xab', 0xab), ("'x'", ord('x')), ("' '", 32)]:
            with self.subTest(value=value):
                out = bytes_of('#define N {0}\nmov a, N\n'.format(value))
                self.assertEqual(out, bytes_of('mov a, 0x{0:02x}\n'.format(expected)))

    def test_trailing_comment_stripped(self):
        self.assertEqual(bytes_of('#define N 0x05 ; five\nmov a, N\n'), bytes_of('mov a, 0x05\n'))

    def test_header_defines_used(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'a.h'), 'w') as f:
                f.write('#include b.h\n#define A 2\n')
            with open(os.path.join(d, 'b.h'), 'w') as f:
                f.write('// consts\n#define B 0x30\nbyte f(byte x);\n')
            path = os.path.join(d, 'prog.basm')
            self.assertEqual(bytes_of('#include a.h\nmov a, B\nadd A\n', path), bytes_of('mov a, 0x30\nadd 0x02\n'))


class TestWidths(unittest.TestCase):
    def test_too_big(self):
        self.assertEqual(errors_of('#define N 0x100\nmov a, N\n'),
                         [(2, 8, "value of 'N' (0x0100) does not fit in 8 bits")])
        self.assertEqual(errors_of('#define N 256\nadd N\n'),
                         [(2, 5, "value of 'N' (0x0100) does not fit in 8 bits")])
        self.assertEqual(errors_of('#define N 0x10\nin a, #N\n'),
                         [(2, 8, "value of 'N' (0x0010) does not fit in 4 bits")])
        self.assertEqual(errors_of('#define N 0x10000\nadd csci, N\n'),
                         [(2, 11, "value of 'N' (0x10000) does not fit in 16 bits")])
        self.assertEqual(errors_of('#define N 0x100\nshl csci, N\n'),
                         [(2, 11, "value of 'N' (0x0100) does not fit in 8 bits")])
        self.assertEqual(errors_of('#define N 0x100\n.db 0x01, N\n'),
                         [(2, 11, "value of 'N' (0x0100) does not fit in 8 bits")])
        self.assertEqual(errors_of('#define N 0x10000\n.org N\n'),
                         [(2, 6, "value of 'N' (0x10000) does not fit in 16 bits")])
        self.assertEqual(errors_of('#define N 0x10000\n.def K, N\n'),
                         [(2, 9, "value of 'N' (0x10000) does not fit in 16 bits")])
        self.assertEqual(errors_of("#define N 'a'\n#define M 0x10000\n.assert N = M\n"),
                         [(3, 13, "value of 'M' (0x10000) does not fit in 16 bits")])

    def test_boundaries_fit(self):
        self.assertEqual(bytes_of('#define N 0xff\nmov a, N\n'), bytes_of('mov a, 0xff\n'))
        self.assertEqual(bytes_of('#define N 0xf\nin a, #N\n'), bytes_of('in a, #0xf\n'))
        self.assertEqual(bytes_of('#define N 0xffff\nadd csci, N\n'), bytes_of('add csci, 0xffff\n'))
        self.assertEqual(bytes_of('#define N 0x000000ff\nmov a, N\n'), bytes_of('mov a, 0xff\n'))
        self.assertEqual(bytes_of('#define N 0\nin a, #N\n'), bytes_of('in a, #0x0\n'))


class TestDiagnostics(unittest.TestCase):
    def test_undefined_before_define(self):
        self.assertEqual(errors_of('mov a, N\n#define N 0x01\n'), [(1, 8, "undefined name 'N'")])

    def test_undefined_never_defined(self):
        self.assertEqual(errors_of('nop\n  out #a, FOO\n'), [(2, 11, "undefined name 'FOO'")])

    def test_not_a_number(self):
        self.assertEqual(errors_of('#define X Y\nmov a, X\n'), [(2, 8, "'X' is not a number: 'Y'")])
        self.assertEqual(errors_of('#define X 1+2\nmov a, X\n'), [(2, 8, "'X' is not a number: '1+2'")])
        self.assertEqual(errors_of('#define X 0x\nmov a, X\n'), [(2, 8, "'X' is not a number: '0x'")])
        self.assertEqual(errors_of('#define X 007\nmov a, X\n'), [(2, 8, "'X' is not a number: '007'")])
        self.assertEqual(errors_of('#define X "s"\nmov a, X\n'), [(2, 8, "'X' is not a number: '\"s\"'")])

    def test_redefinition_takes_effect_from_next_line(self):
        self.assertEqual(bytes_of('#define X 1\nmov a, X\n#define X 2\nmov a, X\n'),
                         bytes_of('mov a, 0x01\nmov a, 0x02\n'))

    def test_every_bad_use_reported_and_line_emits_nothing(self):
        text = '#define BIG 0x100\n#define S x\nmov a, BIG\nmov a, NOPE\nadd S\n.db BIG, S\nnop\n'
        self.assertEqual(errors_of(text), [
            (3, 8, "value of 'BIG' (0x0100) does not fit in 8 bits"),
            (4, 8, "undefined name 'NOPE'"),
            (5, 5, "'S' is not a number: 'x'"),
            (6, 5, "value of 'BIG' (0x0100) does not fit in 8 bits"),
            (6, 10, "'S' is not a number: 'x'"),
        ])

    def test_bad_line_emits_no_bytes_for_following_addresses(self):
        # the failed line takes no space: the label after it sits at the address right after the first nop
        text = '#define BIG 0x100\nnop\nmov a, BIG\nl: nop\n.assert :l = 0x0001\n'
        # the bad line is the only error; had it emitted bytes the assertion would fail as well
        self.assertEqual(len(errors_of(text)), 1)

    def test_org_bad_name_does_not_move_address(self):
        self.assertEqual(len(errors_of('#define B 0x10000\n.org B\nl: nop\n.assert :l = 0x0000\n')), 1)


class TestWholeIdentifiers(unittest.TestCase):
    def test_longer_names_labels_refs_strings_comments_untouched(self):
        text = ('#define BDIO 0x05\n'
                'BDIO_FCAT: nop\n'
                'BDIO: nop\n'
                'jmp z, :BDIO\n'
                'cal :BDIO_FCAT\n'
                "mov a, BDIO ; BDIO BDIO_FCAT\n"
                ".db 'BDIO', BDIO\n")
        plain = ('BDIO_FCAT: nop\n'
                 'BDIO: nop\n'
                 'jmp z, :BDIO\n'
                 'cal :BDIO_FCAT\n'
                 "mov a, 0x05 ; BDIO BDIO_FCAT\n"
                 ".db 'BDIO', 0x05\n")
        self.assertEqual(bytes_of(text), bytes_of(plain))
        self.assertEqual(assemble(text).label_addresses, assemble(plain).label_addresses)

    def test_defined_name_not_applied_to_longer_identifier(self):
        self.assertEqual(errors_of('#define BDIO 0x05\nmov a, BDIO_FCAT\n'), [(2, 8, "undefined name 'BDIO_FCAT'")])

    def test_names_are_case_sensitive(self):
        self.assertEqual(errors_of('#define BDIO 0x05\nmov a, bdio\n'), [(2, 8, "undefined name 'bdio'")])

    def test_registers_still_registers(self):
        self.assertEqual(bytes_of('#define X 1\nmov a, ci\nout #ci, a\nin a, #ci\nadd csci, dsdi\nshl csci, dsdi\n'),
                         bytes_of('mov a, ci\nout #ci, a\nin a, #ci\nadd csci, dsdi\nshl csci, dsdi\n'))

    def test_name_starting_like_a_register_is_a_name(self):
        self.assertEqual(bytes_of('#define cia 0x03\nin a, #cia\nmov a, cia\n'), bytes_of('in a, #0x3\nmov a, 0x03\n'))

    def test_register_name_cannot_be_defined(self):
        self.assertTrue(errors_of('#define ci 0x01\nmov a, ci\n')[0][2].startswith("'ci' is a register name"))

    def test_hilo_keep_meaning(self):
        self.assertEqual(bytes_of('#define hi 0x01\n.db hi(:x), lo(:x)\nx: nop\n'),
                         bytes_of('.db hi(:x), lo(:x)\nx: nop\n'))

    def test_literal_syntax_stays_strict(self):
        for line in ['mov a, 255', 'mov a, 0x1', 'mov a, 0x100', 'mov a, -1', 'in a, #0x10', 'add csci, 0x12',
                     "mov a, 'x'"]:
            with self.subTest(line=line):
                with self.assertRaises(AssemblerError):
                    assemble('#define X 1\n' + line + '\n')


class TestCli(unittest.TestCase):
    def test_too_big_error_block(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'prog.basm'), 'w', newline='') as f:
                f.write('#define BIG 0x100\nnop\nmov a, BIG\n')
            r = subprocess.run([sys.executable, SCRIPT, 'prog.basm'], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            lines = r.stderr.splitlines()
            self.assertEqual(lines[0], "prog.basm:3:8: error: value of 'BIG' (0x0100) does not fit in 8 bits")
            self.assertEqual(lines[1], 'mov a, BIG')
            self.assertEqual(lines[2], '       ^')
            self.assertFalse(os.path.exists(os.path.join(d, 'prog.btap')))


if __name__ == '__main__':
    unittest.main()
