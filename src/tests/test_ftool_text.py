import io
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from bc64 import bc64_env
from bc64 import bc64_io

import ftool_mkdisc  # noqa: E402  (sibling modules, side-effect free)
import ftool_text  # noqa: E402


def _import_ftool():
    # ftool.py has no __main__ guard: importing it runs main(); see tests/test_ftool.py.
    saved_argv = sys.argv
    sys.argv = ['ftool.py', 'noop']
    try:
        with mock.patch.object(bc64_env.Environment, 'log'):
            import ftool
    finally:
        sys.argv = saved_argv
    return ftool


ftool = _import_ftool()

SECTOR_SIZE = bc64_io.FloppyDriveV1.SECTOR_SIZE
SECTORS = bc64_io.FloppyDriveV1.SECTORS
IMAGE_SIZE = ftool_mkdisc.IMAGE_SIZE
CATALOG_OFFSET = SECTOR_SIZE
BOOT_SIGNATURE = bytes([0xbd, 0x05, 0x01, 0x01])


def entry_bytes(image, number):
    offset = CATALOG_OFFSET + number * 16
    return image[offset:offset + 16]


class TextTestCase(unittest.TestCase):
    """A small mkdisc image: boot (0/0), catalog (0/1..1/15), system slot of 160 sectors at 2/0, ends at 12/0."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        original_env = ftool.env
        self.addCleanup(setattr, ftool, 'env', original_env)
        ftool.env = bc64_env.Environment(debug=False)
        original_argv = ftool.argv
        self.addCleanup(setattr, ftool, 'argv', original_argv)

        self.write('boot.sector', bytes([0x11]) * (SECTOR_SIZE - 4) + BOOT_SIGNATURE)
        self.write('sys.sector', bytes([0x22]) * 300)
        self.write('disc.manifest', (
            'BOOTSECT.BIN boot.sector SR role=boot at=0/0 max=1\n'
            'DISC.CAT     -           SR role=catalog at=0/1 max=31\n'
            'BDOS.SYS     sys.sector  SR role=system at=2/0 max=160\n').encode('ascii'))
        self.disc = self.path('disc.bdd')
        ftool_mkdisc.mkdisc(self.path('disc.manifest'), self.disc)
        self.base = self.read('disc.bdd')

    def path(self, name):
        return os.path.join(self.dir, name)

    def write(self, name, data):
        with open(self.path(name), 'wb') as f:
            f.write(data)
        return self.path(name)

    def read(self, name):
        with open(self.path(name), 'rb') as f:
            return f.read()

    def imp(self, text, name='X.TXT', disc=None):
        self.write('in.txt', text)
        return ftool_text.import_text(disc or self.disc, self.path('in.txt'), name)

    def exp(self, name='X.TXT', numbers=False, disc=None):
        ftool_text.export_text(disc or self.disc, name, self.path('out.txt'), numbers)
        return self.read('out.txt')

    def run_main(self, *args):
        ftool.argv = ['ftool.py'] + list(args)
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with redirect_stdout(out), redirect_stderr(err):
            try:
                ftool.main()
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def assert_import_fails(self, text, message, name='X.TXT'):
        """Through main: exit 1, message on stderr, disc unchanged."""
        self.write('in.txt', text)
        code, _, err = self.run_main('importtext', self.disc, self.path('in.txt'), name)
        self.assertEqual(code, 1)
        self.assertIn('importtext: error: ', err)
        self.assertIn(message, err)
        self.assertEqual(self.read('disc.bdd'), self.base)


class EncodingTests(TextTestCase):
    def test_exact_bytes_of_a_small_file(self):
        self.imp(b'ab\n\n  c\n')
        start = 12 * SECTORS  # the system entry has length 160
        data = self.read('disc.bdd')[start * SECTOR_SIZE:(start + 1) * SECTOR_SIZE]
        expected = b'10 ab\x13' b'20  \x13' b'30   c\x13' + b'\x00'
        self.assertEqual(data, expected + bytes(SECTOR_SIZE - len(expected)))

    def test_empty_file_is_one_zero_sector(self):
        self.imp(b'')
        entry = entry_bytes(self.read('disc.bdd'), 3)
        self.assertEqual(entry[3], 1)
        self.assertEqual(self.exp(), b'')

    def test_record_spans_sectors_and_sector_count(self):
        lines = [('%d' % i).encode() * 1 + b' ' + b'x' * 70 for i in range(20)]
        self.imp(b'\n'.join(lines) + b'\n')
        image = self.read('disc.bdd')
        size = sum(len(str(10 * i).encode()) + 1 + len(line) + 1 for i, line in enumerate(lines, 1)) + 1
        self.assertEqual(entry_bytes(image, 3)[3], (size + SECTOR_SIZE - 1) // SECTOR_SIZE)
        self.assertEqual(self.exp(), b'\n'.join(lines) + b'\n')


class RoundTripTests(TextTestCase):
    CASES = {
        'plain': b'one\ntwo\nthree\n',
        'leading_trailing_spaces': b'  lead\ntrail  \n   \n',
        'tabs': b'\tindent\na\tb\t\n',
        'blank_lines': b'a\n\n\nb\n\n',
        'only_blank': b'\n',
        'line_80': b'x' * 80 + b'\n',
        'empty': b'',
        'multi_sector': b''.join(b'line number %d with some text\n' % i for i in range(200)),
    }

    def test_round_trip_is_identical(self):
        for name, text in self.CASES.items():
            with self.subTest(name):
                disc = self.path(name + '.bdd')
                with open(disc, 'wb') as f:
                    f.write(self.base)
                self.imp(text, disc=disc)
                self.assertEqual(self.exp(disc=disc), text)

    def test_crlf_normalises_to_lf(self):
        self.imp(b'a\r\n\r\nb\r\n')
        self.assertEqual(self.exp(), b'a\n\nb\n')

    def test_missing_final_newline_gets_one(self):
        self.imp(b'a\nb')
        self.assertEqual(self.exp(), b'a\nb\n')

    def test_numbers_option_keeps_prefix(self):
        self.imp(b'a\n\n  b\n')
        self.assertEqual(self.exp(numbers=True), b'10 a\n20  \n30   b\n')


class CatalogTests(TextTestCase):
    def test_entry_fields_and_other_bytes_unchanged(self):
        self.imp(b'hello\n', name='hello.b')
        image = self.read('disc.bdd')
        self.assertEqual(entry_bytes(image, 3), bytes([3, 12, 0, 1, 0x03]) + b'HELLO   B  ')
        changed = [i for i in range(IMAGE_SIZE) if image[i] != self.base[i]]
        data_start = 12 * SECTORS * SECTOR_SIZE
        allowed = set(range(CATALOG_OFFSET + 3 * 16, CATALOG_OFFSET + 4 * 16)) | set(
            range(data_start, data_start + SECTOR_SIZE))
        self.assertTrue(set(changed) <= allowed)
        self.assertEqual(image[:CATALOG_OFFSET + 3 * 16], self.base[:CATALOG_OFFSET + 3 * 16])

    def test_name_without_extension_is_padded(self):
        self.imp(b'a\n', name='ab')
        self.assertEqual(entry_bytes(self.read('disc.bdd'), 3)[5:], b'AB         ')

    def test_second_file_follows_the_first(self):
        self.imp(b'a\n', name='ONE.TXT')
        self.imp(b'b\n', name='TWO.TXT')
        image = self.read('disc.bdd')
        self.assertEqual(entry_bytes(image, 4)[:5], bytes([4, 12, 1, 1, 0x03]))
        self.assertEqual(self.exp('ONE.TXT'), b'a\n')
        self.assertEqual(self.exp('TWO.TXT'), b'b\n')

    def test_free_sector_is_max_end_even_when_catalog_order_differs(self):
        # entry 3 sits at the end of the disc layout, entry 4 earlier: the free sector is the max end.
        image = bytearray(self.base)
        image[CATALOG_OFFSET + 3 * 16:CATALOG_OFFSET + 3 * 16 + 16] = bytes([3, 20, 0, 4, 3]) + b'LATE    TXT'
        image[CATALOG_OFFSET + 4 * 16:CATALOG_OFFSET + 4 * 16 + 16] = bytes([4, 13, 0, 2, 3]) + b'EARLY   TXT'
        with open(self.disc, 'wb') as f:
            f.write(image)
        self.imp(b'a\n')
        entry = entry_bytes(self.read('disc.bdd'), 5)
        self.assertEqual(entry[:5], bytes([5, 20, 4, 1, 0x03]))  # linear 324 = 20*16+4

    def test_free_sector_uses_track_times_16(self):
        # 12/0..61/15 (sectors 192..991) are used, so the tail at 62/8 (sector 1000) is the largest gap
        # (guards the #111 style track*15 confusion)
        image = bytearray(self.base)
        layout = [(192, 200), (392, 200), (592, 200), (792, 200), (992, 8)]
        for number, (start, sectors) in enumerate(layout, start=3):
            entry = bytes([number, start // 16, start % 16, sectors, 3]) + b'FILL%d   BIN' % number
            image[CATALOG_OFFSET + number * 16:CATALOG_OFFSET + (number + 1) * 16] = entry
        with open(self.disc, 'wb') as f:
            f.write(image)
        self.imp(b'a\n')
        self.assertEqual(entry_bytes(self.read('disc.bdd'), 8)[:5], bytes([8, 62, 8, 1, 0x03]))

    def test_name_is_case_insensitive_for_export(self):
        self.imp(b'a\n', name='Foo.Txt')
        self.assertEqual(self.exp('foo.txt'), b'a\n')

    def test_disc_file_mode_is_kept(self):
        os.chmod(self.disc, 0o640)
        self.imp(b'a\n')
        self.assertEqual(stat.S_IMODE(os.stat(self.disc).st_mode), 0o640)
        self.assertEqual(os.listdir(self.dir).count('disc.bdd'), 1)
        self.assertFalse([n for n in os.listdir(self.dir) if n.endswith('.tmp')])


class ImportErrorTests(TextTestCase):
    def test_line_longer_than_80(self):
        self.assert_import_fails(b'ok\n' + b'x' * 81 + b'\n', 'line 2: 81 characters, at most 80')

    def test_bad_bytes(self):
        for bad in (b'\x00', b'\x13', b'\x01', b'\x7f', b'\xc3\xa9'):
            with self.subTest(bad=bad):
                self.assert_import_fails(b'a\nb' + bad + b'\n', 'line 2: byte 0x')

    def test_one_space_line(self):
        self.assert_import_fails(b'a\n \n', 'line 2: a line of exactly one space')

    def test_too_many_lines(self):
        self.assert_import_fails(b'a\n' * 6554, '6554 lines, at most 6553')

    def test_6553_lines_are_accepted_by_the_line_limit(self):
        # 6553 short lines need more than 255 sectors: the line limit passes, the sector limit stops.
        self.assert_import_fails(b'a\n' * 6553, 'sectors, a file holds at most 255')

    def test_more_than_255_sectors(self):
        self.assert_import_fails(b''.join(b'x' * 80 + b'\n' for _ in range(500)),
                                 'at most 255')

    def test_exactly_255_sectors_fit(self):
        count = 1
        while True:
            try:
                ftool_text.encode_text(b'x' * 80 + b'\n' + b'y\n' * count)
            except ftool_text.TextError:
                break
            count += 1
        text = b'x' * 80 + b'\n' + b'y\n' * (count - 1)
        data, _ = ftool_text.encode_text(text)
        self.assertEqual(len(data), 255 * SECTOR_SIZE)
        self.imp(text)
        self.assertEqual(entry_bytes(self.read('disc.bdd'), 3)[3], 255)

    def test_bad_names(self):
        for name in ('', 'TOOLONGNAME.TXT', 'a b', 'A.TOOL', 'a-b.txt', '.TXT'):
            with self.subTest(name=name):
                self.assert_import_fails(b'a\n', 'bad name', name=name)

    def test_disc_cat_is_refused(self):
        self.assert_import_fails(b'a\n', 'DISC.CAT', name='disc.cat')

    def test_existing_name_is_refused(self):
        self.imp(b'a\n')
        self.base = self.read('disc.bdd')
        self.assert_import_fails(b'b\n', 'already exists')
        self.assert_import_fails(b'b\n', 'already exists', name='x.txt')

    def test_catalog_full(self):
        image = bytearray(self.base)
        for number in range(3, 247):
            offset = CATALOG_OFFSET + number * 16
            image[offset:offset + 16] = bytes([number, 12, 0, 1, 3]) + ('F%03d    BIN' % number).encode()
        with open(self.disc, 'wb') as f:
            f.write(image)
        self.base = bytes(image)
        self.assert_import_fails(b'a\n', 'catalog full')

    def test_catalog_with_246_files_still_takes_one(self):
        image = bytearray(self.base)
        for number in range(3, 246):
            offset = CATALOG_OFFSET + number * 16
            image[offset:offset + 16] = bytes([number, 12, 0, 1, 3]) + ('F%03d    BIN' % number).encode()
        with open(self.disc, 'wb') as f:
            f.write(image)
        self.imp(b'a\n')
        self.assertEqual(entry_bytes(self.read('disc.bdd'), 246)[3], 1)

    def test_disc_full(self):
        image = bytearray(self.base)
        # four 208-sector files cover the whole allocatable area 12/0..63/15: no free sector is left
        for number in range(4):
            start = 192 + number * 208
            image[CATALOG_OFFSET + (3 + number) * 16:CATALOG_OFFSET + (4 + number) * 16] = bytes(
                [3 + number, start // 16, start % 16, 208, 3]) + b'FULL%d   BIN' % number
        with open(self.disc, 'wb') as f:
            f.write(image)
        self.base = bytes(image)
        self.assert_import_fails(b'a\n', 'disc full')

    def test_wrong_image_size(self):
        self.write('short.bdd', bytes(1000))
        self.write('in.txt', b'a\n')
        code, _, err = self.run_main('importtext', self.path('short.bdd'), self.path('in.txt'), 'X.TXT')
        self.assertEqual(code, 1)
        self.assertIn('importtext: error: ', err)
        self.assertEqual(self.read('short.bdd'), bytes(1000))

    def test_missing_disc_and_host_file(self):
        self.write('in.txt', b'a\n')
        code, _, err = self.run_main('importtext', self.path('none.bdd'), self.path('in.txt'), 'X.TXT')
        self.assertEqual(code, 1)
        self.assertIn('importtext: error: ', err)
        code, _, err = self.run_main('importtext', self.disc, self.path('none.txt'), 'X.TXT')
        self.assertEqual(code, 1)
        self.assertIn('none.txt', err)
        self.assertEqual(self.read('disc.bdd'), self.base)

    def test_missing_arguments_exit_1(self):
        for args in ([], ['d'], ['d', 'h']):
            with self.subTest(args=args):
                for command in ('importtext', 'exporttext'):
                    ftool.argv = ['ftool.py', command] + args
                    with self.assertRaises(SystemExit) as cm:
                        ftool.main()
                    self.assertEqual(cm.exception.code, 1)


class ExportTests(TextTestCase):
    def put_raw(self, data, name=b'RAW     TXT', length=1):
        image = bytearray(self.base)
        image[CATALOG_OFFSET + 3 * 16:CATALOG_OFFSET + 4 * 16] = bytes([3, 12, 0, length, 3]) + name
        start = 12 * SECTORS * SECTOR_SIZE
        image[start:start + len(data)] = data
        with open(self.disc, 'wb') as f:
            f.write(image)
        self.base = bytes(image)

    def assert_export_fails(self, message, *extra, name='RAW.TXT'):
        out = self.path('out.txt')
        code, _, err = self.run_main('exporttext', self.disc, name, out, *extra)
        self.assertEqual(code, 1)
        self.assertIn('exporttext: error: ', err)
        self.assertIn(message, err)
        self.assertFalse(os.path.exists(out))
        self.assertEqual(self.read('disc.bdd'), self.base)

    def test_command_through_main(self):
        self.write('in.txt', b'a\n\nb\n')
        code, out, _ = self.run_main('importtext', self.disc, self.path('in.txt'), 'x.txt')
        self.assertEqual((code, 'x.txt'.upper() in out), (0, True))
        code, _, _ = self.run_main('exporttext', self.disc, 'x.txt', self.path('out.txt'))
        self.assertEqual(code, 0)
        self.assertEqual(self.read('out.txt'), b'a\n\nb\n')
        code, _, _ = self.run_main('exporttext', self.disc, 'x.txt', self.path('out2.txt'), '--numbers')
        self.assertEqual(code, 0)
        self.assertEqual(self.read('out2.txt'), b'10 a\n20  \n30 b\n')

    def test_missing_name(self):
        self.assert_export_fails('not found', name='NOPE.TXT')

    def test_malformed_records(self):
        cases = {
            'no_number': b'abc\x13\x00',
            'no_space': b'10x\x13\x00',
            'two_numbers_bad': b'10 a\x13x 20\x13\x00',
            'number_too_big': b'65536 a\x13\x00',
            'six_digits': b'100000 a\x13\x00',
            'empty_record': b'10 a\x13\x13\x00',
            'number_only': b'10\x13\x00',
        }
        for label, data in cases.items():
            with self.subTest(label):
                self.put_raw(data)
                self.assert_export_fails('malformed')

    def test_error_names_the_record(self):
        self.put_raw(b'10 a\x1320 b\x13oops\x13\x00')
        self.assert_export_fails('record 3')

    def test_unterminated_last_record_ends_at_zero(self):
        self.put_raw(b'10 a\x1320 b\x00')
        self.assertEqual(self.exp('RAW.TXT'), b'a\nb\n')

    def test_stops_at_first_zero_and_max_number_ok(self):
        self.put_raw(b'65535 top\x13\x00garbage\x13')
        self.assertEqual(self.exp('RAW.TXT'), b'top\n')

    def test_bad_extra_argument(self):
        self.imp(b'a\n')
        self.base = self.read('disc.bdd')
        for extra in (['--numbr'], ['--numbers', 'x'], ['x']):
            with self.subTest(extra=extra):
                self.assert_export_fails('unexpected argument', *extra, name='X.TXT')

    def test_export_missing_disc_and_bad_name(self):
        code, _, err = self.run_main('exporttext', self.path('none.bdd'), 'X.TXT', self.path('out.txt'))
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(self.path('out.txt')))
        self.assertIn('exporttext: error: ', err)
        self.assert_export_fails('bad name', name='bad name')


class ImportSideEffectTests(unittest.TestCase):
    def test_module_import_is_side_effect_free(self):
        self.assertTrue(hasattr(ftool_text, 'import_text'))


if __name__ == '__main__':
    unittest.main()
