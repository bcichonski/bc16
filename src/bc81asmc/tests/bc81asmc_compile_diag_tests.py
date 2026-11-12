import contextlib
import io
import unittest

import bc81asmc
from bc81asmc_diag import AssemblerError
from bc81asmc_grammar import program


def compile_source(source):
    with contextlib.redirect_stdout(io.StringIO()):
        return bc81asmc.compile(program.parse(source), False)


def errors_of(source):
    '''(line, column, message) of every diagnostic compile() raises for the source.'''
    with contextlib.redirect_stdout(io.StringIO()):
        with unittest.TestCase().assertRaises(AssemblerError) as cm:
            bc81asmc.compile(program.parse(source), False)
    return [(d.line, d.column, d.message) for d in cm.exception.diagnostics]


class TestUndefinedLabels(unittest.TestCase):
    def test_all_undefined_labels_reported_sorted(self):
        source = "nop\ncal :b\nnop\n.db :a\n  .mv dsdi, :c\n"
        self.assertEqual(errors_of(source), [
            (2, 5, "undefined label ':b'"),
            (4, 5, "undefined label ':a'"),
            (5, 13, "undefined label ':c'")])

    def test_each_use_is_an_error(self):
        self.assertEqual(errors_of(".db :x, :x\njmr z, :x\n"), [
            (1, 5, "undefined label ':x'"),
            (1, 9, "undefined label ':x'"),
            (2, 8, "undefined label ':x'")])

    def test_str_contains_every_message(self):
        with self.assertRaises(AssemblerError) as cm:
            compile_source("cal :a\ncal :b\n")
        self.assertIn("undefined label ':a'", str(cm.exception))
        self.assertIn("undefined label ':b'", str(cm.exception))


class TestZeroAddress(unittest.TestCase):
    def test_label_at_zero_resolves(self):
        self.assertEqual(list(compile_source("start: nop\ncal :start\n").bytes),
                         [0x00, 0xa8, 0x00, 0x00])

    def test_def_zero_resolves(self):
        self.assertEqual(list(compile_source(".def zero, 0x0000\n.mv dsdi, :zero\n").bytes),
                         [0x19, 0x00, 0x15, 0x00])


class TestRangeErrors(unittest.TestCase):
    def test_rel7_out_of_range(self):
        source = "jmr z, :far\n" + "nop\n" * 200 + "far: nop\n"
        errs = errors_of(source)
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0][:2], (1, 8))
        self.assertIn("label ':far' too far away for relative 7bit jump", errs[0][2])

    def test_rel15_out_of_range(self):
        source = "jrx z, :far\n.db '" + "a" * 0x8100 + "'\nfar: nop\n"
        errs = errors_of(source)
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0][:2], (1, 8))
        self.assertIn("label ':far' too far away for relative 15bit jump", errs[0][2])

    def test_all_range_errors_collected(self):
        source = "jmr z, :far\njmr nz, :far\n" + "nop\n" * 200 + "far: nop\n"
        self.assertEqual([e[:2] for e in errors_of(source)], [(1, 8), (2, 9)])


class TestDuplicates(unittest.TestCase):
    def test_duplicate_label(self):
        self.assertEqual(errors_of("a: nop\nnop\n  a: nop\n"),
                         [(3, 3, "duplicate label 'a' (first defined at line 1)")])

    def test_duplicate_def(self):
        self.assertEqual(errors_of(".def x, 0x0001\n.def x, 0x0002\n"),
                         [(2, 6, "duplicate symbol 'x' (first defined at line 1)")])

    def test_label_then_def_clash(self):
        self.assertEqual(errors_of("x: nop\n.def x, 0x0002\n"),
                         [(2, 6, "duplicate symbol 'x' (first defined at line 1)")])

    def test_def_then_label_clash(self):
        self.assertEqual(errors_of(".def x, 0x0002\nx: nop\n"),
                         [(2, 1, "duplicate symbol 'x' (first defined at line 1)")])


class TestEmitAndOverflow(unittest.TestCase):
    def test_unencodable_line_is_positioned_and_skipped(self):
        errs = errors_of("nop\n  clr af\nnop\ncal :nowhere\n")
        self.assertEqual(errs[0][:2], (2, 3))
        self.assertTrue(errs[0][2].startswith("cannot encode 'clr af':"))
        self.assertEqual(errs[1], (4, 5, "undefined label ':nowhere'"))

    def test_overflow_reported_once(self):
        errs = errors_of(".org 0xffff\nnop\n nop\nnop\n")
        self.assertEqual(errs, [(3, 2, 'code exceeds the 64 KB address space (past 0xffff)')])

    def test_last_byte_at_ffff_is_fine(self):
        self.assertEqual(list(compile_source(".org 0xffff\nnop\n").bytes), [0x00])


class TestValidProgram(unittest.TestCase):
    def test_no_diagnostics(self):
        context = compile_source(".org 0x0100\nstart: jmr z, :end\nnop\nend: cal :start\n.db :end\n")
        self.assertGreater(len(context.bytes), 0)


if __name__ == '__main__':
    unittest.main()
