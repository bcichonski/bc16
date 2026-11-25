import contextlib
import io
import os
import tempfile
import unittest

import parsy

import bc81asmc
import bc81asmc_ast as ast
from bc81asmc_diag import AssemblerError
from bc81asmc_grammar import program
from bc81asmc_listing import format_listing, format_map

BODY = ".org 0x0100\nstart: nop\nnop\nkil\n"
WITH = (".org 0x0100\n.global start\n.extern other\n.sect code\nstart: nop\nnop\n"
        "here: .sect data ; comment\n.global here\nkil\n")


def build(source):
    with contextlib.redirect_stdout(io.StringIO()):
        return bc81asmc.compile(program.parse(source), False)


class TestParse(unittest.TestCase):
    def one(self, text):
        return program.parse(text + '\n')[0]

    def test_each_directive(self):
        for text, cls in ((".global foo", ast.GLOBAL), (".extern foo", ast.EXTERN), (".sect foo", ast.SECT)):
            node = self.one(text)
            self.assertIsInstance(node, cls)
            self.assertEqual(node.name, 'foo')

    def test_label_and_comment(self):
        node = self.one("lbl: .global foo ; note")
        self.assertIsInstance(node, ast.GLOBAL)
        self.assertEqual(node.label, 'lbl')
        self.assertEqual(node.comment.strip(), '; note')

    def test_malformed(self):
        for text in (".global", ".extern", ".sect", ".global a b", ".global :a", ".extern 0x10", ".sect a, b"):
            with self.assertRaises(parsy.ParseError, msg=text):
                program.parse(text + '\n')

    def test_malformed_is_positioned_diagnostic(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(AssemblerError) as raised:
                bc81asmc.assemble_text("nop\n.global\n", 'x.basm')
        self.assertEqual(raised.exception.diagnostics[0].line, 2)


class TestFlatNoOp(unittest.TestCase):
    def test_same_bytes_and_labels(self):
        plain, with_dirs = build(BODY), build(WITH)
        self.assertEqual(plain.bytes, with_dirs.bytes)
        self.assertEqual(with_dirs.startaddr, plain.startaddr)

    def test_label_on_directive_line_gets_current_address(self):
        context = build(WITH)
        self.assertEqual(context.bytes, bytearray(build(BODY).bytes))
        text = format_map('x', context)
        self.assertIn('0x0102 label here', text)
        self.assertIn('0x0100 label start', text)

    def test_listing_rows_have_no_bytes(self):
        context = build(WITH)
        rows = format_listing(WITH, context).split('\n')
        for index in (1, 2, 3):
            self.assertEqual(rows[index][:4].strip(), '')
            self.assertEqual(rows[index][6:17].strip(), '')
        self.assertIn('.global start', rows[1])
        self.assertEqual(rows[6][:4], '0102')
        self.assertEqual(rows[6][6:17].strip(), '')

    def test_map_unchanged(self):
        without = ".org 0x0100\nstart: nop\nnop\nhere: kil\n"
        with_ = ".org 0x0100\n.global start\nstart: nop\nnop\nhere: .global here\nkil\n"
        self.assertEqual(format_map('x', build(without)), format_map('x', build(with_)))


class TestLinkOccurrences(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, 'w', encoding='utf8', newline='') as f:
            f.write(text)
        return path

    def assemble(self, text):
        with contextlib.redirect_stdout(io.StringIO()):
            return bc81asmc.assemble_text(text, os.path.join(self.dir, 'prog.basm'))

    def test_order_and_repeats(self):
        context = self.assemble("#link a\nnop\n#link b\n#link a\nnop\n")
        self.assertEqual([(o.name, o.line) for o in context.link_occurrences], [('a', 1), ('b', 3), ('a', 4)])
        self.assertEqual(context.link_names, ['a', 'b'])

    def test_header_link_belongs_to_include_line(self):
        self.write('h.bh', "#link x\n#link y\n")
        context = self.assemble("nop\n#include h.bh\n#link x\nnop\n")
        self.assertEqual([(o.name, o.line) for o in context.link_occurrences], [('x', 2), ('y', 2), ('x', 3)])
        self.assertEqual(context.link_names, ['x', 'y'])

    def test_none(self):
        self.assertEqual(self.assemble("nop\n").link_occurrences, [])


if __name__ == '__main__':
    unittest.main()
