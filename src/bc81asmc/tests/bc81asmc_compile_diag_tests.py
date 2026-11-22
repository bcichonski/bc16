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


class TestSixteenBitPairs(unittest.TestCase):
    def test_wrong_second_pair(self):
        for text, implied, first in (('add csci,csci', 'dsdi', 'csci'), ('add dsdi,dsdi', 'csci', 'dsdi'),
                                     ('shl csci,csci', 'dsdi', 'csci')):
            with self.subTest(text):
                errs = errors_of("nop\n  " + text + "\n")
                self.assertEqual(len(errs), 1)
                self.assertEqual(errs[0][:2], (2, 3))
                self.assertTrue(errs[0][2].startswith("cannot encode '" + text + "':"))
                self.assertIn("second operand must be " + implied, errs[0][2])

    def test_unknown_pair(self):
        for text, name in (('add csci,sssi', 'sssi'), ('add sssi,csci', 'sssi'),
                           ('add sssi,0x0001', 'sssi'), ('inc sssi', 'sssi')):
            with self.subTest(text):
                errs = errors_of("nop\n  " + text + "\n")
                self.assertEqual(len(errs), 1)
                self.assertEqual(errs[0][:2], (2, 3))
                self.assertIn("'" + name + "' is not a 16-bit pair", errs[0][2])

    def test_all_bad_lines_reported(self):
        errs = errors_of("add csci,csci\nnop\nadd sssi,0x0001\ninc sssi\nadd af,dsdi\n")
        self.assertEqual([e[:2] for e in errs], [(1, 1), (3, 1), (4, 1), (5, 1)])

    def test_valid_pairs_still_encode(self):
        self.assertEqual(list(compile_source("add csci,dsdi\nadd dsdi,csci\n").bytes),
                         [0x5f, 0xa8, 0x89, 0x5f, 0xa8, 0x98])


class TestValidProgram(unittest.TestCase):
    def test_no_diagnostics(self):
        context = compile_source(".org 0x0100\nstart: jmr z, :end\nnop\nend: cal :start\n.db :end\n")
        self.assertGreater(len(context.bytes), 0)


class TestIncDecAf(unittest.TestCase):
    def reason(self, op):
        return ("cannot encode '{0} af': {0} af is not allowed: the 16-bit result would "
                "overwrite the flags in f (use {0} a, or a pair csci or dsdi)".format(op))

    def test_inc_dec_af_rejected_with_position(self):
        for op in ('inc', 'dec'):
            with self.subTest(op):
                self.assertEqual(errors_of("nop\n  {0} af\n".format(op)),
                                 [(2, 3, self.reason(op))])

    def test_rejected_line_emits_nothing_and_assembly_continues(self):
        for op in ('inc', 'dec'):
            with self.subTest(op):
                source = "nop\n{0} af\nkil\n".format(op)
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(AssemblerError) as cm:
                        bc81asmc.compile(program.parse(source), False)
                self.assertEqual(len(cm.exception.diagnostics), 1)
                # a following line is still assembled: a second bad line is also reported
                self.assertEqual(
                    [d.line for d in self.diags("{0} af\nnop\n{0} af\n".format(op))], [1, 3])
                self.assertEqual(list(compile_source("nop\nkil\n").bytes), [0x00, 0xf0])

    def diags(self, source):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(AssemblerError) as cm:
                bc81asmc.compile(program.parse(source), False)
        return cm.exception.diagnostics

    def test_unchanged_encodings(self):
        expected = {'inc a': [0x5d], 'dec a': [0x5e],
                    'inc csci': [0x5f, 0xad, 0x80], 'dec csci': [0x5f, 0xae, 0x80],
                    'inc dsdi': [0x5f, 0xad, 0x90], 'dec dsdi': [0x5f, 0xae, 0x90],
                    'not csci': [0x5f, 0xb7, 0x80], 'not dsdi': [0x5f, 0xb7, 0x90]}
        for text, want in expected.items():
            with self.subTest(text):
                self.assertEqual(list(compile_source(text + "\n").bytes), want)

    def test_unknown_pair_keeps_its_message(self):
        self.assertEqual(errors_of("inc sssi\n"), [(1, 1,
            "cannot encode 'inc sssi': 'sssi' is not a 16-bit pair (use csci or dsdi)")])


class TestAluOnAf(unittest.TestCase):
    OPS = ('add', 'sub', 'mul', 'div', 'mod', 'and', 'or', 'xor', 'shl', 'shr')

    def reason(self, text, op):
        return ("cannot encode '{0}': {1} af is not allowed: the 16-bit result would "
                "overwrite the flags in f (use a pair csci or dsdi)".format(text, op))

    def test_immediate_and_register_forms_rejected(self):
        for op in self.OPS:
            imm = '0x01' if op in ('shl', 'shr') else '0x0100'
            for text in ('{0} af, {1}'.format(op, imm), '{0} af, csci'.format(op)):
                with self.subTest(text):
                    self.assertEqual(errors_of("nop\n  " + text + "\n"),
                                     [(2, 3, self.reason(text, op))])

    def test_not_af_rejected(self):
        self.assertEqual(errors_of("not af\n"), [(1, 1, self.reason('not af', 'not'))])

    def test_af_checked_before_implied_pair(self):
        for text in ('add af, dsdi', 'add af, af'):
            with self.subTest(text):
                self.assertEqual(errors_of(text + "\n"), [(1, 1, self.reason(text, 'add'))])

    def test_assembly_continues_after_rejected_line(self):
        errs = errors_of("add af, 0x0001\nnop\nnot af\n")
        self.assertEqual([e[:2] for e in errs], [(1, 1), (3, 1)])

    def test_pair_and_non_alu_forms_unchanged(self):
        expected = {'add csci, 0x0100': [0x5f, 0xa0, 0x80, 0x01, 0x00],
                    'add csci, dsdi': [0x5f, 0xa8, 0x89], 'add dsdi, csci': [0x5f, 0xa8, 0x98]}
        for text, want in expected.items():
            with self.subTest(text):
                self.assertEqual(list(compile_source(text + "\n").bytes), want)
        # non-ALU uses of af still assemble
        self.assertEqual(len(compile_source("jmp z, af\n").bytes), 2)


class TestOrgPlacement(unittest.TestCase):
    DUP = "duplicate .org (first .org at line {0}); use .org once, at the top"
    LATE = ".org must come before any code or label"

    def test_second_org_without_code_between(self):
        self.assertEqual(errors_of(".org 0x1000\n  .org 0x2000\n"), [(2, 3, self.DUP.format(1))])

    def test_second_org_after_comments_def_assert_names_first_line(self):
        src = "; hdr\n.def x, 0x0001\n.assert 0x0001 <= 0x0002\n.org 0x1000\nnop\n.org 0x2000\n"
        self.assertEqual(errors_of(src), [(6, 1, self.DUP.format(4))])

    def test_org_after_instruction(self):
        self.assertEqual(errors_of("nop\n.org 0x1000\n"), [(2, 1, self.LATE)])

    def test_org_after_label_line(self):
        self.assertEqual(errors_of("start: .db 0x01\n.org 0x1000\n"), [(2, 1, self.LATE)])

    def test_label_on_org_line(self):
        self.assertEqual(errors_of("lbl: .org 0x1000\n"), [(1, 1, self.LATE)])

    def test_def_and_comments_before_org_are_fine(self):
        context = compile_source("; c\n.def p, 0x0010\n.org 0x1000\nnop\n")
        self.assertEqual(context.startaddr, 0x1000)

    def test_no_org_is_fine(self):
        self.assertEqual(list(compile_source("nop\n").bytes), [0x00])

    def test_rejected_org_keeps_later_diagnostics_in_order(self):
        src = ".org 0x1000\nnop\n.org 0x2000\n.db :nowhere\n"
        self.assertEqual(errors_of(src), [
            (3, 1, self.DUP.format(1)),
            (4, 5, "undefined label ':nowhere'")])


if __name__ == '__main__':
    unittest.main()
