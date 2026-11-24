import contextlib
import io
import unittest

import bc81asmc
from bc81asmc_diag import AssemblerError
from bc81asmc_grammar import program


def assemble(source):
    with contextlib.redirect_stdout(io.StringIO()):
        return list(bc81asmc.compile(program.parse(source), False).bytes)


def errors_of(source):
    with contextlib.redirect_stdout(io.StringIO()):
        with unittest.TestCase().assertRaises(AssemblerError) as cm:
            bc81asmc.compile(program.parse(source), False)
    return [(d.line, d.column, d.message) for d in cm.exception.diagnostics]


class TestDbHiLo(unittest.TestCase):
    def test_backward_label(self):
        self.assertEqual(assemble(".org 0x1234\nhere: nop\n.db hi(:here), lo(:here)\n"),
                         [0x00, 0x12, 0x34])

    def test_forward_label(self):
        self.assertEqual(assemble(".org 0x0200\n.db hi(:later), lo(:later)\nlater: nop\n"),
                         [0x02, 0x02, 0x00])

    def test_def_label(self):
        self.assertEqual(assemble(".def port, 0xabcd\n.db hi(:port), lo(:port)\n"), [0xab, 0xcd])

    def test_def_zero_is_defined(self):
        self.assertEqual(assemble(".def zero, 0x0000\n.db hi(:zero), lo(:zero)\n"), [0x00, 0x00])

    def test_mixed_operands(self):
        self.assertEqual(
            assemble(".org 0x0300\nstart: nop\n.db 0x01, hi(:end), 'ab', :start, lo(:end), 0xff\nend: nop\n"),
            [0x00, 0x01, 0x03, 0x61, 0x62, 0x03, 0x00, 0x09, 0xff, 0x00])

    def test_blanks_inside_parentheses(self):
        self.assertEqual(assemble(".org 0x0102\nx: nop\n.db hi( :x ), lo(  :x)\n"), [0x00, 0x01, 0x02])

    def test_same_bytes_as_db_label(self):
        self.assertEqual(assemble(".org 0x4567\nx: .db hi(:x), lo(:x)\n"),
                         assemble(".org 0x4567\nx: .db :x\n"))

    def test_unknown_label_position(self):
        self.assertEqual(errors_of(".db 0x01, hi(:nowhere)\n"),
                         [(1, 14, "undefined label ':nowhere'")])

    def test_unknown_label_same_as_plain_db(self):
        self.assertEqual(errors_of("nop\n.db lo(:a), :a\n"), [
            (2, 8, "undefined label ':a'"),
            (2, 13, "undefined label ':a'")])
