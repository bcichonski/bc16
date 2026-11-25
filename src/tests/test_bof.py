"""Unit tests of src/bof.py, the BOF v1 object file writer, reader and dump formatter.

Expected bytes are written out here on purpose, so a changed tag or layout fails a test.
"""
import unittest

import bof

HELLO_O = bytes.fromhex(
    'b0 06 01 48 45 4c 4c 4f'
    'de 05 53 54 44 49 4f'
    '55 06 46 5f 6d 61 69 6e'
    '91 06 46 5f 6d 61 69 6e'
    'c0 06 18 00 14 00 11 00'
    'fb 03 01 80 00'
    'ee 0d 73 74 61 63 6b 76 61 72 38 73 74 31 36'
    'c0 03 a8 00 00'
    'f1 01 01'
    'ee 06 46 5f 70 75 74 73'
    'c0 08 a8 00 01 18 00 14 00 b0'
    'f1 01 01'
    '1a 02 00 00'
    'c0 03 68 69 00'
    'ed 00')


def build_hello():
    w = bof.BofWriter('HELLO')
    w.need('STDIO')
    w.sectstat('F_main')
    w.globl('F_main')
    w.code(bytes.fromhex('18 00 14 00'), [(bof.FIX_HILO, 1, bof.local_label_target(0))])
    w.code(bytes.fromhex('11 00'))
    assert w.extrn('stackvar8st16') == 0
    w.code(bytes.fromhex('a8 00 00'), [(bof.FIX_ABS16, 1)])
    assert w.extrn('F_puts') == 1
    w.code(bytes.fromhex('a8 00 01'), [(bof.FIX_ABS16, 1)])
    w.code(bytes.fromhex('18 00 14 00'))
    w.code(bytes.fromhex('b0'))
    w.label(0)
    w.code(b'hi\x00')
    w.end()
    return w


def records(data):
    return [(r.tag, r.content) for r in bof.read_records(data)]


def written(build):
    w = bof.BofWriter('M')
    build(w)
    w.end()
    return records(w.getvalue())[1:-1]


class ConstantTests(unittest.TestCase):
    def test_tags(self):
        self.assertEqual(
            [bof.TAG_HEADER, bof.TAG_EXTRN, bof.TAG_NEED, bof.TAG_ADDR, bof.TAG_SECTSTAT, bof.TAG_SECTABS,
             bof.TAG_GLOBL, bof.TAG_CODE, bof.TAG_LABEL, bof.TAG_ABS, bof.TAG_ABS16, bof.TAG_REL15,
             bof.TAG_HI8, bof.TAG_LO8, bof.TAG_REL7, bof.TAG_HILO, bof.TAG_END],
            [0xb0, 0xee, 0xde, 0xad, 0x55, 0x5a, 0x91, 0xc0, 0x1a, 0xab,
             0xf1, 0xf2, 0xf8, 0xf9, 0xfa, 0xfb, 0xed])
        self.assertEqual(bof.VERSION, 1)
        self.assertEqual(bof.MAX_CONTENT, 255)
        self.assertEqual((bof.ADDR_CODE, bof.ADDR_HEAP, bof.ADDR_CODELIMIT), (0, 1, 2))
        self.assertEqual(bof.local_label_target(5), 0x8005)


class HelloTests(unittest.TestCase):
    def test_hello_exact_bytes(self):
        data = build_hello().getvalue()
        self.assertEqual(len(data), 99)
        self.assertEqual(data, HELLO_O)

    def test_hello_dump(self):
        text = bof.dump(HELLO_O)
        self.assertEqual(text, '\n'.join([
            "0000  b0 HEADER   version 01 module 'HELLO'",
            "0008  de NEED     'STDIO'",
            "000f  55 SECTSTAT 'F_main'",
            "0017  91 GLOBL    'F_main' @0000",
            "001f  c0 CODE     @0000 6 bytes: 18 00 14 00 11 00",
            "0027  fb HILO     offset 01 -> label 0",
            "002c  ee EXTRN    symbol 0 'stackvar8st16'",
            "003b  c0 CODE     @0006 3 bytes: a8 00 00",
            "0040  f1 ABS16    offset 01 -> symbol 0 'stackvar8st16'",
            "0043  ee EXTRN    symbol 1 'F_puts'",
            "004b  c0 CODE     @0009 8 bytes: a8 00 01 18 00 14 00 b0",
            "0055  f1 ABS16    offset 01 -> symbol 1 'F_puts'",
            "0058  1a LABEL    label 0 @0011",
            "005c  c0 CODE     @0011 3 bytes: 68 69 00",
            "0061  ed END",
            ""]))

    def test_hello_section_offset(self):
        w = build_hello()
        self.assertEqual(w.section_offset, 20)


class RecordRoundTripTests(unittest.TestCase):
    def test_each_record_kind(self):
        def build(w):
            w.need('LIB')
            w.addr(bof.ADDR_CODE, 0x6000)
            w.addr(bof.ADDR_HEAP, 0x1234)
            w.addr(bof.ADDR_CODELIMIT, 0xFFFF)
            w.sectabs(0x0400, 'BOOT')
            w.sectstat('S')
            w.globl('g')
            w.abs_symbol(0xBEEF, 'K')
            w.label(7)
            w.code(b'\x01')
        self.assertEqual(written(build), [
            (0xde, b'LIB'), (0xad, b'\x00\x60\x00'), (0xad, b'\x01\x12\x34'), (0xad, b'\x02\xff\xff'),
            (0x5a, b'\x04\x00BOOT'), (0x55, b'S'), (0x91, b'g'), (0xab, b'\xbe\xefK'),
            (0x1a, b'\x00\x07'), (0xc0, b'\x01')])

    def test_reader_fields(self):
        w = bof.BofWriter('MOD')
        w.addr(bof.ADDR_HEAP, 0x1234)
        w.sectabs(0x0400, 'BOOT')
        w.abs_symbol(0xBEEF, 'K')
        w.label(7)
        w.end()
        recs = bof.read_records(w.getvalue())
        self.assertEqual([r.name for r in recs], ['HEADER', 'ADDR', 'SECTABS', 'ABS', 'LABEL', 'END'])
        self.assertEqual(recs[0].fields, {'version': 1, 'module': 'MOD'})
        self.assertEqual(recs[1].fields, {'kind': 1, 'value': 0x1234})
        self.assertEqual(recs[2].fields, {'address': 0x400, 'name': 'BOOT'})
        self.assertEqual(recs[3].fields, {'value': 0xBEEF, 'name': 'K'})
        self.assertEqual(recs[4].fields, {'n': 7})
        self.assertEqual([r.offset for r in recs], [0, 6, 11, 19, 24, 28])

    def test_each_fix_kind(self):
        w = bof.BofWriter('M')
        w.extrn('x')
        w.code(bytes(range(1, 21)), [
            (bof.FIX_HILO, 14, 0x8001), (bof.FIX_REL7, 12, 0x0002), (bof.FIX_LO8, 10, 0x0003),
            (bof.FIX_HI8, 8, 0x8004), (bof.FIX_REL15, 5, 0), (bof.FIX_ABS16, 1, 0)])
        w.end()
        recs = bof.read_records(w.getvalue())
        self.assertEqual([r.tag for r in recs[2:-1]], [0xc0, 0xf1, 0xf2, 0xf8, 0xf9, 0xfa, 0xfb])
        self.assertEqual(recs[3].fields['offsets'], [1])
        self.assertEqual(recs[4].fields['offsets'], [5])
        self.assertEqual(recs[5].fields['entries'], [(8, 0x8004)])
        self.assertEqual(recs[6].fields['entries'], [(10, 3)])
        self.assertEqual(recs[7].fields['entries'], [(12, 2)])
        self.assertEqual(recs[8].fields['entries'], [(14, 0x8001)])
        self.assertEqual(recs[7].content, b'\x0c\x00\x02')

    def test_fix_offsets_ascending_across_units(self):
        w = bof.BofWriter('M')
        w.code(b'\x00\x00\x00', [(bof.FIX_ABS16, 0)])
        w.code(b'\x00\x00\x00\x00', [(bof.FIX_ABS16, 2), (bof.FIX_ABS16, 0)])
        w.end()
        self.assertEqual(records(w.getvalue())[1:-1], [
            (0xc0, bytes(7)), (0xf1, b'\x00\x03\x05')])

    def test_extrn_numbers_in_order_and_reused(self):
        w = bof.BofWriter('M')
        self.assertEqual(w.extrn('a'), 0)
        self.assertEqual(w.extrn('b'), 1)
        self.assertEqual(w.extrn('a'), 0)
        self.assertEqual(w.symbols, {'a': 0, 'b': 1})
        w.end()
        self.assertEqual(records(w.getvalue())[1:-1], [(0xee, b'a'), (0xee, b'b')])

    def test_globl_allocates_no_number(self):
        w = bof.BofWriter('M')
        w.globl('f')
        self.assertEqual(w.extrn('g'), 0)

    def test_empty_code_unit_writes_nothing(self):
        self.assertEqual(written(lambda w: w.code(b'')), [])


class FlushTests(unittest.TestCase):
    def test_flush_before_each_non_code_record(self):
        calls = {
            'label': lambda w: w.label(1), 'globl': lambda w: w.globl('g'),
            'sectstat': lambda w: w.sectstat('s'), 'sectabs': lambda w: w.sectabs(0x10, 's'),
            'extrn': lambda w: w.extrn('x'), 'need': lambda w: w.need('n'),
            'addr': lambda w: w.addr(0, 1), 'abs': lambda w: w.abs_symbol(1, 'a'),
            'end': lambda w: None}
        for name, call in calls.items():
            with self.subTest(name):
                w = bof.BofWriter('M')
                w.code(b'\x01\x02')
                call(w)
                w.end()
                recs = records(w.getvalue())
                self.assertEqual(recs[1], (0xc0, b'\x01\x02'))
                self.assertEqual(w.pending, 0)

    def test_pending_bytes_stay_open_between_units(self):
        w = bof.BofWriter('M')
        w.code(b'\x01')
        w.code(b'\x02\x03')
        self.assertEqual(w.pending, 3)
        w.end()
        self.assertEqual(records(w.getvalue())[1:-1], [(0xc0, b'\x01\x02\x03')])

    def test_code_record_of_exactly_255_bytes(self):
        w = bof.BofWriter('M')
        w.code(bytes(100))
        w.code(bytes(155))
        self.assertEqual(w.pending, 255)
        w.code(b'\x07')
        w.end()
        self.assertEqual(records(w.getvalue())[1:-1], [(0xc0, bytes(255)), (0xc0, b'\x07')])

    def test_unit_that_does_not_fit_starts_new_record(self):
        w = bof.BofWriter('M')
        w.code(bytes(250))
        w.code(b'\x01\x02\x03\x04\x05\x06', [(bof.FIX_ABS16, 4)])
        w.end()
        self.assertEqual(records(w.getvalue())[1:-1], [
            (0xc0, bytes(250)), (0xc0, b'\x01\x02\x03\x04\x05\x06'), (0xf1, b'\x04')])

    def test_long_unit_split_at_255(self):
        w = bof.BofWriter('M')
        w.code(b'\x09')
        w.code(bytes(range(256)) * 2, [(bof.FIX_ABS16, 0), (bof.FIX_ABS16, 300)])
        self.assertEqual(w.section_offset, 513)
        w.end()
        recs = records(w.getvalue())[1:-1]
        self.assertEqual([t for t, _ in recs], [0xc0, 0xc0, 0xf1, 0xc0, 0xf1, 0xc0])
        self.assertEqual(recs[0], (0xc0, b'\x09'))
        self.assertEqual([len(c) for t, c in recs if t == 0xc0], [1, 255, 255, 2])
        self.assertEqual(recs[2], (0xf1, b'\x00'))
        self.assertEqual(recs[4], (0xf1, bytes((300 - 255,))))

    def test_long_unit_split_never_cuts_a_placeholder(self):
        w = bof.BofWriter('M')
        w.code(bytes(300), [(bof.FIX_ABS16, 254)])
        w.end()
        recs = records(w.getvalue())[1:-1]
        self.assertEqual(recs[0], (0xc0, bytes(254)))
        self.assertEqual(recs[1], (0xc0, bytes(46)))
        self.assertEqual(recs[2], (0xf1, b'\x00'))

    def test_long_unit_split_never_cuts_a_hilo(self):
        w = bof.BofWriter('M')
        w.code(bytes(300), [(bof.FIX_HILO, 253, 0x8000)])
        w.end()
        recs = records(w.getvalue())[1:-1]
        self.assertEqual([len(c) for t, c in recs if t == 0xc0], [253, 47])
        self.assertEqual(recs[1], (0xc0, bytes(47)))
        self.assertEqual(recs[2], (0xfb, b'\x00\x80\x00'))


class FixListTests(unittest.TestCase):
    def _code_with_fixes(self, n, kind):
        w = bof.BofWriter('M')
        w.code(bytes(255), [(kind, i, 0x8000 | i) for i in range(n)] if kind not in bof.FIX_OFFSET_ONLY
               else [(kind, i * 2) for i in range(n)])
        w.end()
        return [(t, c) for t, c in records(w.getvalue())[1:-1] if t != 0xc0]

    def test_list_of_exactly_255_bytes_not_split(self):
        fixes = self._code_with_fixes(85, bof.FIX_HI8)
        self.assertEqual([t for t, _ in fixes], [0xf8])
        self.assertEqual(len(fixes[0][1]), 255)

    def test_hi8_list_over_255_bytes_continues(self):
        fixes = self._code_with_fixes(86, bof.FIX_HI8)
        self.assertEqual([(t, len(c)) for t, c in fixes], [(0xf8, 255), (0xf8, 3)])
        self.assertEqual(fixes[1][1], bytes((85, 0x80, 85)))

    def test_abs16_list_of_127_entries(self):
        fixes = self._code_with_fixes(127, bof.FIX_ABS16)
        self.assertEqual([(t, len(c)) for t, c in fixes], [(0xf1, 127)])

    def test_abs16_list_of_255_one_byte_entries_not_split(self):
        w = bof.BofWriter('M')
        w.code(bytes(256 - 1), [(bof.FIX_ABS16, 0)])
        w.end()
        # 255 one-byte entries need 255 offsets; offsets are bytes, so build them directly
        w = bof.BofWriter('M')
        for i in range(127):
            w.code(b'\x00\x00', [(bof.FIX_ABS16, 0)])
        w.end()
        recs = records(w.getvalue())
        self.assertEqual([t for t, _ in recs[1:-1]], [0xc0, 0xf1])
        self.assertEqual(len(recs[2][1]), 127)

    def test_empty_fix_lists_not_written(self):
        w = bof.BofWriter('M')
        w.code(b'\x01\x02')
        w.end()
        self.assertEqual([t for t, _ in records(w.getvalue())], [0xb0, 0xc0, 0xed])

    def test_fix_records_in_tag_order_for_each_code_record(self):
        w = bof.BofWriter('M')
        w.code(bytes(8), [(bof.FIX_HILO, 0, 1), (bof.FIX_LO8, 4, 2), (bof.FIX_ABS16, 6)])
        w.label(0)
        w.code(bytes(2), [(bof.FIX_REL15, 0)])
        w.end()
        self.assertEqual([t for t, _ in records(w.getvalue())],
                         [0xb0, 0xc0, 0xf1, 0xf9, 0xfb, 0x1a, 0xc0, 0xf2, 0xed])


class WriterTests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(build_hello().getvalue(), build_hello().getvalue())

    def test_section_offset_resets_per_section(self):
        w = bof.BofWriter('M')
        w.sectstat('a')
        w.code(bytes(10))
        self.assertEqual(w.section_offset, 10)
        w.sectabs(0x100, 'b')
        self.assertEqual(w.section_offset, 0)
        w.code(bytes(3))
        w.sectstat('c')
        self.assertEqual(w.section_offset, 0)

    def test_getvalue_needs_end(self):
        with self.assertRaises(bof.BofError):
            bof.BofWriter('M').getvalue()

    def test_nothing_after_end(self):
        w = bof.BofWriter('M')
        w.end()
        with self.assertRaises(bof.BofError):
            w.code(b'\x00')
        with self.assertRaises(bof.BofError):
            w.label(0)

    def test_writer_errors(self):
        w = bof.BofWriter('M')
        bad = [
            lambda: w.extrn('café'), lambda: w.extrn('x' * 256), lambda: w.extrn(''),
            lambda: w.sectabs(0x10, 'x' * 254), lambda: w.abs_symbol(1, 'x' * 254),
            lambda: w.sectabs(0x10000, 's'), lambda: w.addr(3, 0), lambda: w.addr(0, -1),
            lambda: w.label(0x8000), lambda: w.code(b'\x00', [(bof.FIX_ABS16, 0)]),
            lambda: w.code(b'\x00\x00', [(0x77, 0)]), lambda: w.code(b'\x00', [(bof.FIX_HI8, 1, 0)]),
            lambda: w.code(b'\x00', [(bof.FIX_HI8, 0, 0x10000)]),
            lambda: bof.BofWriter('x' * 255), lambda: bof.local_label_target(0x8000)]
        for i, call in enumerate(bad):
            with self.subTest(i):
                with self.assertRaises(bof.BofError):
                    call()

    def test_longest_names_fit(self):
        w = bof.BofWriter('M')
        w.extrn('x' * 255)
        w.sectabs(1, 'y' * 253)
        w.abs_symbol(1, 'z' * 253)
        w.end()
        self.assertEqual(len(bof.read_records(w.getvalue())), 5)


class ReaderErrorTests(unittest.TestCase):
    def assertRejects(self, data, offset, text=''):
        with self.assertRaises(bof.BofError) as cm:
            bof.read_records(data)
        self.assertEqual(cm.exception.offset, offset)
        self.assertIn(text, str(cm.exception))
        self.assertIn('offset %d' % offset, str(cm.exception))

    def test_wrong_first_tag(self):
        self.assertRejects(b'\xc0\x01\x00' + b'\xed\x00', 0, 'not a BOF file')

    def test_empty_file(self):
        self.assertRejects(b'', 0, 'empty')

    def test_wrong_version(self):
        self.assertRejects(b'\xb0\x02\x02M\xed\x00', 0, 'version')

    def test_truncated_record(self):
        self.assertRejects(HELLO_O[:12], 8, 'truncated')

    def test_truncated_record_header(self):
        self.assertRejects(HELLO_O[:8] + b'\xde', 8, 'truncated')

    def test_unknown_tag(self):
        self.assertRejects(b'\xb0\x02\x01M\x77\x00\xed\x00', 4, 'unknown record tag')

    def test_data_after_end(self):
        self.assertRejects(HELLO_O + b'\x00', 99, 'after END')

    def test_missing_end(self):
        self.assertRejects(HELLO_O[:-2], 97, 'missing END')

    def test_header_only_without_end(self):
        self.assertRejects(b'\xb0\x02\x01M', 4, 'missing END')

    def test_second_header(self):
        self.assertRejects(b'\xb0\x02\x01M\xb0\x02\x01M\xed\x00', 4, 'second header')

    def test_malformed_records(self):
        head = b'\xb0\x02\x01M'
        cases = [
            b'\xad\x02\x00\x00', b'\xad\x03\x09\x00\x00', b'\x1a\x01\x00', b'\xee\x00', b'\xc0\x00',
            b'\x5a\x02\x00\x01', b'\xab\x01\x00', b'\xed\x01\x00', b'\xf8\x02\x00\x00',
            b'\xee\x01\xff', b'\xf1\x01\x00',
            b'\xc0\x02\x00\x00\xf1\x01\x01', b'\xc0\x02\x00\x00\x1a\x02\x00\x00\xf1\x01\x00']
        for case in cases:
            with self.subTest(case.hex()):
                with self.assertRaises(bof.BofError) as cm:
                    bof.read_records(head + case + b'\xed\x00')
                self.assertIsNotNone(cm.exception.offset)

    def test_dump_rejects_bad_file(self):
        with self.assertRaises(bof.BofError):
            bof.dump(b'\x00\x00')


class DumpTests(unittest.TestCase):
    def test_dump_every_record_kind(self):
        w = bof.BofWriter('M')
        w.need('LIB')
        w.addr(bof.ADDR_CODELIMIT, 0x0e80)
        w.sectabs(0x0400, 'BOOT')
        w.abs_symbol(0x20, 'K')
        w.code(bytes(range(20)), [(bof.FIX_REL7, 3, 0x0001), (bof.FIX_HILO, 5, 0x8002)])
        w.extrn('s')
        w.end()
        self.assertEqual(bof.dump(w.getvalue()), '\n'.join([
            "0000  b0 HEADER   version 01 module 'M'",
            "0004  de NEED     'LIB'",
            "0009  ad ADDR     #codelimit 0e80",
            "000e  5a SECTABS  address 0400 'BOOT'",
            "0016  ab ABS      'K' = 0020",
            "001b  c0 CODE     @0000 20 bytes: 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f",
            "                        10 11 12 13",
            "0031  fa REL7     offset 03 -> symbol 1 (not declared)",
            "0036  fb HILO     offset 05 -> label 2",
            "003b  ee EXTRN    symbol 0 's'",
            "003e  ed END",
            ""]))


if __name__ == '__main__':
    unittest.main()
