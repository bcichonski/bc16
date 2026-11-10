import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

from parsy import ParseError

import bc81asmc
from bc81asmc_ast import CodeContext
from bc81asmc_diag import AssemblerError
from bc81asmc_grammar import program


def assemble(source, verbose=False):
    '''Parse and compile the source in-process, capturing the progress printing.'''
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ast = program.parse(source)
        context = bc81asmc.compile(ast, verbose)
    return context


def code(source):
    return list(assemble(source).bytes)


def unbtapify(data):
    '''Inverse of btapify: eight bit-bytes (LSB first) per original byte.'''
    result = bytearray()
    for i in range(0, len(data), 8):
        result.append(sum(bit << n for n, bit in enumerate(data[i:i + 8])))
    return result


class TestLabelsAbsolute(unittest.TestCase):

    def test_backward_label_hi_lo(self):
        # .db with a label emits hi then lo of the label address
        self.assertEqual(
            code(".org 0x1234\nstart: nop\n.db :start\n"),
            [0x00, 0x12, 0x34])

    def test_forward_label_hi_lo(self):
        self.assertEqual(
            code(".org 0x1234\n.db :end\nend: nop\n"),
            [0x12, 0x36, 0x00])

    def test_mv_expands_to_two_mov_imm8(self):
        # 1 ds hi / 1 di lo (4 bytes), label resolved forward
        self.assertEqual(
            code(".org 0x0200\n.mv dsdi, :msg\nmsg: nop\n"),
            [0x19, 0x02, 0x15, 0x04, 0x00])

    def test_mv_backward_label(self):
        self.assertEqual(
            code(".org 0x0200\nmsg: nop\n.mv csci, :msg\n"),
            [0x00, 0x18, 0x02, 0x14, 0x00])

    def test_cal_label(self):
        self.assertEqual(
            code(".org 0x0300\ncal :fn\nfn: ret\n"),
            [0xa8, 0x03, 0x03, 0xb0])

    def test_jmp_label_is_short_page_relative(self):
        # jmp z, :label stores only the low byte of the address (2 bytes)
        self.assertEqual(
            code(".org 0x0300\njmp z, :fn\nfn: ret\n"),
            [0x68, 0x02, 0xb0])

    def test_label_at_address_zero_resolves(self):
        # D9: a label at address 0 is defined (it used to be reported as "not defined")
        self.assertEqual(code("start: nop\n.db :start\n"), [0x00, 0x00, 0x00])

    def test_def_with_value_zero_resolves(self):
        # D9: same for .def 0x0000
        self.assertEqual(code(".def zero, 0x0000\n.db :zero\n"), [0x00, 0x00])

    def test_undefined_label_is_positioned_assembler_error(self):
        # AC-1 / AC-2: no bare KeyError; the error names line and column of the reference
        with self.assertRaises(AssemblerError) as cm:
            assemble(".org 0x0100\n.db :nowhere\n")
        self.assertEqual([(d.line, d.column, d.message) for d in cm.exception.diagnostics],
                         [(2, 5, "undefined label ':nowhere'")])


class TestLabelsRelative7(unittest.TestCase):
    '''jmr :label, 7-bit sign-magnitude offset stored as target - offset_byte_addr + 1.'''

    def test_forward(self):
        # jmr at 0x100 (2 bytes), nop, end at 0x103; offset byte at 0x101
        self.assertEqual(
            code(".org 0x0100\njmr z, :end\nnop\nend: nop\n"),
            [0x70, 0x03, 0x00, 0x00])

    def test_backward_is_sign_magnitude(self):
        # start 0x100, nop, jmr at 0x101, offset byte at 0x102 -> 0x100-0x102+1 = -1 -> 0x81
        self.assertEqual(
            code(".org 0x0100\nstart: nop\njmr z, :start\n"),
            [0x00, 0x70, 0x81])

    def test_jump_to_self_has_zero_offset(self):
        # pinned: offset byte is at jmr+1, so the stored offset for a self jump is +0
        self.assertEqual(
            code(".org 0x0100\nloop: jmr nz, :loop\n"),
            [0x74, 0x00])

    def test_register_form_has_no_fixup(self):
        self.assertEqual(code("jmr z, ci\n"), [0x78, 0x40])

    def _jump_over(self, nops, forward=True):
        pad = "nop\n" * nops
        if forward:
            return ".org 0x0100\njmr z, :end\n" + pad + "end: nop\n"
        return ".org 0x0100\nstart: nop\n" + pad + "jmr z, :start\n"

    def test_forward_max_offset(self):
        # end = 0x102 + n, offset = end - 0x100 = 0x7f
        data = code(self._jump_over(0x7f - 2))
        self.assertEqual(data[:2], [0x70, 0x7f])

    def test_forward_too_far(self):
        with self.assertRaisesRegex(Exception, 'too far away for relative 7bit'):
            assemble(self._jump_over(0x80 - 2))

    def test_backward_max_offset(self):
        # jmr at 0x100+1+n, offset byte at +1, diff = start - jmr = -(n + 1)
        n = 0x7f - 1
        data = code(self._jump_over(n, forward=False))
        self.assertEqual(data[-2:], [0x70, 0xff])

    def test_backward_too_far(self):
        with self.assertRaisesRegex(Exception, 'too far away for relative 7bit'):
            assemble(self._jump_over(0x7f, forward=False))


class TestLabelsRelative15(unittest.TestCase):
    '''jrx/clr :label, 15-bit sign-magnitude offset stored as target - first_offset_byte - 1.'''

    def test_jrx_forward(self):
        # jrx at 0x100: E1 00, offset at 0x102; end at 0x105 -> 0x105-0x102-1 = 2
        self.assertEqual(
            code(".org 0x0100\njrx z, :end\nnop\nend: nop\n"),
            [0xe1, 0x00, 0x00, 0x02, 0x00, 0x00])

    def test_jrx_negated_test_nibble(self):
        self.assertEqual(
            code(".org 0x0100\njrx nz, :end\nend: nop\n"),
            [0xe1, 0x40, 0x00, 0x01, 0x00])

    def test_jrx_backward_is_sign_magnitude(self):
        # start 0x100 (nop), jrx at 0x101, offset at 0x103 -> 0x100-0x103-1 = -4
        self.assertEqual(
            code(".org 0x0100\nstart: nop\njrx z, :start\n"),
            [0x00, 0xe1, 0x00, 0x80, 0x04])

    def test_jrx_register_form_has_no_fixup(self):
        self.assertEqual(code("jrx z, ci\n"), [0xe2, 0x84])

    def test_clr_forward(self):
        # clr at 0x100: A9, offset at 0x101; fn at 0x104 -> 0x104-0x101-1 = 2
        self.assertEqual(
            code(".org 0x0100\nclr :fn\nnop\nfn: ret\n"),
            [0xa9, 0x00, 0x02, 0x00, 0xb0])

    def test_clr_backward_is_sign_magnitude(self):
        # fn at 0x100 (ret), clr at 0x101, offset at 0x102 -> 0x100-0x102-1 = -3
        self.assertEqual(
            code(".org 0x0100\nfn: ret\nclr :fn\n"),
            [0xb0, 0xa9, 0x80, 0x03])

    def test_clr_register_form(self):
        self.assertEqual(code("clr csci\n"), [0xa1, 0x84])

    def test_forward_max_offset_via_def(self):
        # offset byte at 0x102, target 0x8102 -> 0x8102 - 0x102 - 1 = 0x7fff
        data = code(".def far, 0x8102\n.org 0x0100\njrx z, :far\n")
        self.assertEqual(data, [0xe1, 0x00, 0x7f, 0xff])

    def test_forward_too_far(self):
        with self.assertRaisesRegex(Exception, 'too far away for relative 15bit'):
            assemble(".def far, 0x8103\n.org 0x0100\njrx z, :far\n")

    def test_backward_max_offset_via_def(self):
        # clr offset byte at 0x9001, target 0x1003 -> 0x1003 - 0x9001 - 1 = -0x7fff
        data = code(".def far, 0x1003\n.org 0x9000\nclr :far\n")
        self.assertEqual(data, [0xa9, 0xff, 0xff])

    def test_backward_too_far(self):
        with self.assertRaisesRegex(Exception, 'too far away for relative 15bit'):
            assemble(".def far, 0x1002\n.org 0x9000\nclr :far\n")


class TestDirectives(unittest.TestCase):

    def test_org_sets_start_address(self):
        context = assemble(".org 0x4000\nnop\nnop\n")
        self.assertEqual(context.startaddr, 0x4000)
        self.assertEqual(context.curraddr, 0x4002)
        self.assertEqual(list(context.bytes), [0, 0])

    def test_default_start_address_is_zero(self):
        self.assertEqual(assemble("nop\n").startaddr, 0)

    def test_org_does_not_emit_bytes(self):
        self.assertEqual(code(".org 0x4000\n"), [])

    def test_second_org_only_shifts_addresses(self):
        # documented: code stays contiguous, a second .org only shifts the addresses
        context = assemble(".org 0x1000\nnop\n.org 0x2000\nnop\n")
        self.assertEqual(list(context.bytes), [0x00, 0x00])
        self.assertEqual(context.startaddr, 0x2000)
        self.assertEqual(context.curraddr, 0x2001)

    def test_second_org_with_label_fixup_patches_wrong_bytes(self):
        # D7 finding: fix-ups are written at (addr - startaddr) using the LAST .org, so
        # a label reference after a second .org overwrites earlier code and leaves the
        # 0xfa placeholder in place. Pinned as-is.
        context = assemble(".org 0x1000\nnop\n.org 0x2000\nlbl: nop\n.db :lbl\n")
        self.assertEqual(list(context.bytes), [0x00, 0x20, 0x00, 0xfa])

    def test_def_constant_used_as_label(self):
        self.assertEqual(
            code(".def port, 0xbeef\n.db :port\n"),
            [0xbe, 0xef])

    def test_label_clashing_with_def_is_duplicate_symbol(self):
        # D3 (A2): labels and .def share one namespace, the clash is a positioned error
        with self.assertRaises(AssemblerError) as cm:
            assemble(".org 0x0100\n.def thing, 0x4321\nthing: nop\n.db :thing\n")
        self.assertEqual([(d.line, d.column, d.message) for d in cm.exception.diagnostics],
                         [(3, 1, "duplicate symbol 'thing' (first defined at line 2)")])

    def test_def_does_not_emit_and_is_recorded(self):
        context = assemble(".def abc, 0x1234\n")
        self.assertEqual(list(context.bytes), [])
        self.assertEqual(context.defs, {'abc': 0x1234})

    def test_def_used_with_mv(self):
        self.assertEqual(
            code(".def abc, 0x1234\n.mv csci, :abc\n"),
            [0x18, 0x12, 0x14, 0x34])

    def test_db_bytes(self):
        self.assertEqual(code(".db 0x01, 0x02, 0xff\n"), [1, 2, 0xff])

    def test_db_string(self):
        self.assertEqual(code(".db 'Hi!'\n"), [0x48, 0x69, 0x21])

    def test_db_mixed(self):
        self.assertEqual(
            code(".org 0x0100\n.db 'ab', 0x00, :end\nend: nop\n"),
            [0x61, 0x62, 0x00, 0x01, 0x05, 0x00])

    def test_db_empty_string_emits_nothing(self):
        self.assertEqual(code(".db '', 0x07\n"), [7])

    def test_label_and_comment_on_line(self):
        context = assemble(".org 0x0100\nlbl: nop ; a comment\n.db :lbl\n")
        self.assertEqual(list(context.bytes), [0x00, 0x01, 0x00])

    def test_line_comment_and_blank_indentation(self):
        self.assertEqual(code("; just a comment\n   nop\n"), [0x00])

    def test_verbose_prints_both_passes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            bc81asmc.compile(program.parse(".org 0x0100\njmr z, :e\ne: nop\n"), True)
        text = out.getvalue()
        self.assertIn('1st pass', text)
        self.assertIn('2nd pass', text)
        self.assertIn('store rel(e)=2 at 0x0101', text)
        self.assertIn('Code length: 3 labels: 1', text)

    def test_compile_prints_summary_when_not_verbose(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            bc81asmc.compile(program.parse("a: nop\n"), False)
        self.assertEqual(out.getvalue().strip(), 'Code length: 1 labels: 1')


class TestCodeContext(unittest.TestCase):

    def test_emit_4bit_pairs_into_byte(self):
        context = CodeContext()
        context.emit_4bit(0xa)
        self.assertEqual(len(context.bytes), 0)
        context.emit_4bit(0xb)
        self.assertEqual(list(context.bytes), [0xab])
        self.assertEqual(context.curraddr, 1)

    def test_label_on_half_emitted_byte_is_rejected(self):
        context = CodeContext()
        context.emit_4bit(1)
        with self.assertRaises(Exception):
            context.emit_hi8addr('x')

    def test_emit_16bit(self):
        context = CodeContext()
        context.emit_16bit(0x1234)
        self.assertEqual(list(context.bytes), [0x12, 0x34])


class TestBtapWriter(unittest.TestCase):

    def test_btapify_expands_bits_lsb_first(self):
        self.assertEqual(
            list(bc81asmc.btapify([0b10110001])),
            [1, 0, 0, 0, 1, 1, 0, 1])
        self.assertEqual(list(bc81asmc.btapify([])), [])

    def test_preamble_layout(self):
        context = assemble(".org 0x1234\nnop\nkil\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            preamble = bc81asmc.get_preamble('prog', context)
        self.assertEqual(len(preamble), 24)
        self.assertEqual(
            list(preamble[:11]),
            [0x00, 0xff, 0x00, 0xff, 0xbc, 0x05, 0x12, 0x34, 0x00, 0x02, 0x00])
        self.assertEqual(bytes(preamble[11:]), b'prog' + b'\x00' * 9)
        self.assertIn('Creating btap file from 1234 for 0002', out.getvalue())

    def test_save_output_btap_tiny_program(self):
        context = assemble(".org 0x1000\nnop\nkil\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'tiny.btap')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                written = bc81asmc.save_output_btap(path, 'tiny', context)
            with open(path, 'rb') as handle:
                data = handle.read()
        self.assertEqual(len(data), (24 + 2) * 8)
        self.assertEqual(written, 2 * 8)
        self.assertTrue(all(b in (0, 1) for b in data))
        decoded = unbtapify(data)
        self.assertEqual(
            list(decoded[:11]),
            [0x00, 0xff, 0x00, 0xff, 0xbc, 0x05, 0x10, 0x00, 0x00, 0x02, 0x00])
        self.assertEqual(bytes(decoded[11:24]), b'tiny' + b'\x00' * 9)
        self.assertEqual(list(decoded[24:]), [0x00, 0xf0])
        self.assertIn('Saving output file', out.getvalue())

    def test_save_output_file_writes_raw_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'raw.bin')
            with contextlib.redirect_stdout(io.StringIO()):
                written = bc81asmc.save_output_file(path, bytes([1, 2, 3]))
            with open(path, 'rb') as handle:
                data = handle.read()
        self.assertEqual(written, 3)
        self.assertEqual(data, bytes([1, 2, 3]))

    def test_read_input_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'a.basm')
            with open(path, 'w', encoding='utf8') as handle:
                handle.write('nop\n')
            self.assertEqual(bc81asmc.read_input_file(path), 'nop\n')

    def test_main_writes_btap_next_to_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, 'hello.basm')
            with open(src, 'w', encoding='utf8') as handle:
                handle.write('.org 0x2000\nnop\n')
            with mock.patch.object(sys, 'argv', ['bc81asmc.py', src]), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                bc81asmc.main()
            with open(os.path.join(tmp, 'hello.btap'), 'rb') as handle:
                data = handle.read()
            self.assertEqual(os.listdir(tmp).count('hello.btap'), 1)
        decoded = unbtapify(data)
        self.assertEqual(bytes(decoded[11:24]), b'hello' + b'\x00' * 8)
        self.assertEqual(list(decoded[6:8]), [0x20, 0x00])
        self.assertEqual(list(decoded[24:]), [0x00])
        self.assertIn('Done!', out.getvalue())


class TestErrorCases(unittest.TestCase):

    def test_unknown_mnemonic(self):
        with self.assertRaises(ParseError):
            program.parse("frobnicate a\n")

    def test_bad_register(self):
        with self.assertRaises(ParseError):
            program.parse("mov x, a\n")

    def test_bad_register_in_pair(self):
        with self.assertRaises(ParseError):
            program.parse("inc xyxy\n")

    def test_uppercase_mnemonic_rejected(self):
        with self.assertRaises(ParseError):
            program.parse("NOP\n")

    def test_missing_trailing_newline_rejected(self):
        with self.assertRaises(ParseError):
            program.parse("nop")

    def test_imm8_with_three_digits_is_parse_error(self):
        # D7: out-of-range immediates can't be written; the grammar needs exactly 2 digits
        with self.assertRaises(ParseError):
            program.parse("mov a, 0x100\n")

    def test_imm8_with_one_digit_is_parse_error(self):
        with self.assertRaises(ParseError):
            program.parse("mov a, 0x1\n")

    def test_imm16_with_five_digits_is_parse_error(self):
        with self.assertRaises(ParseError):
            program.parse("add csci, 0x10000\n")

    def test_org_needs_four_digits(self):
        with self.assertRaises(ParseError):
            program.parse(".org 0x100\n")

    def test_in_port_needs_one_digit(self):
        with self.assertRaises(ParseError):
            program.parse("in a, #0x10\n")

    def test_negative_and_decimal_immediates_rejected(self):
        for src in ("mov a, -1\n", "mov a, 255\n", "mov a, 0b11\n"):
            with self.subTest(src=src), self.assertRaises(ParseError):
                program.parse(src)

    def test_uppercase_hex_digits_are_accepted(self):
        # pinned: the regex accepts A-F in the digits (only the prefix is strict)
        self.assertEqual(code("mov a, 0xAB\n"), [0x11, 0xab])

    def test_out_with_register_arg_assembles(self):
        self.assertEqual(code("out #ci, a\n"), [0xd8, 0x41])


class TestOutImmediate(unittest.TestCase):
    '''Known bug #11 (decided): out #r, imm must encode as Dr HH; out #cs/#ds, imm is an error.'''

    @unittest.expectedFailure  # #11
    def test_out_ci_immediate_encodes_as_d4_41(self):
        self.assertEqual(code("out #ci, 0x41\n"), [0xd4, 0x41])

    @unittest.expectedFailure  # #11
    def test_out_cs_immediate_is_assembler_error(self):
        with self.assertRaises(Exception):
            assemble("out #cs, 0x41\n")

    @unittest.expectedFailure  # #11
    def test_out_ds_immediate_is_assembler_error(self):
        with self.assertRaises(Exception):
            assemble("out #ds, 0x41\n")


if __name__ == '__main__':
    unittest.main()
