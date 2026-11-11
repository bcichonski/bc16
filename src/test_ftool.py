import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from bc64 import bc64_env
from bc64 import bc64_io


def _import_ftool():
    # ftool.py is a script: it has no __main__ guard, so importing it runs main()
    # with whatever argv it sees, and main() logs through a debug Environment.
    # Import it with a harmless unknown command and with Environment.log muted,
    # then restore sys.argv. ftool binds `argv` at import time (`from sys import argv`),
    # so tests that call main() replace ftool.argv explicitly.
    saved_argv = sys.argv
    sys.argv = ['ftool.py', 'noop']
    try:
        with mock.patch.object(bc64_env.Environment, 'log'):
            import ftool
    finally:
        sys.argv = saved_argv
    return ftool


ftool = _import_ftool()

SECTOR_SIZE = bc64_io.FloppyDriveV1.SECTOR_SIZE  # 128
SECTORS = bc64_io.FloppyDriveV1.SECTORS          # 16 per track
TRACKS = bc64_io.FloppyDriveV1.TRACKS            # 64
IMAGE_SIZE = SECTOR_SIZE * SECTORS * TRACKS      # 131072


def _encode_btap_byte(value):
    # .btap encoding: 8 input bytes per output byte, LSB first, nonzero means bit set.
    return b''.join(b'\xff' if (value >> i) & 1 else b'\x00' for i in range(8))


class FtoolTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

        # Commands must never read stdin: any prompt is a test failure.
        patcher = mock.patch.object(bc64_env.Environment, 'get_string',
                                    side_effect=AssertionError('unexpected prompt'))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch('builtins.input',
                             side_effect=AssertionError('unexpected input() call'))
        patcher.start()
        self.addCleanup(patcher.stop)

        # Silent environment by default; the module-level env is restored after each test.
        original_env = ftool.env
        self.addCleanup(setattr, ftool, 'env', original_env)
        ftool.env = bc64_env.Environment(debug=False)

        original_argv = ftool.argv
        self.addCleanup(setattr, ftool, 'argv', original_argv)

    def path(self, name):
        return os.path.join(self.dir, name)

    def write_file(self, name, data):
        path = self.path(name)
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def read_file(self, name):
        with open(self.path(name), 'rb') as f:
            return f.read()


class BtapToBinTests(FtoolTestCase):
    PREAMBLE = bytes(8 * 24)  # 24 groups of 8 zero bytes are skipped

    def test_decodes_each_group_of_eight_bits_lsb_first(self):
        source = self.PREAMBLE + _encode_btap_byte(0xa5) + _encode_btap_byte(0x3c)
        src = self.write_file('in.btap', source)
        out = self.path('out.bin')

        ftool.btap2bin(src, out)

        self.assertEqual(self.read_file('out.bin'), b'\xa5\x3c')

    def test_output_starts_after_exactly_24_skipped_groups(self):
        only_preamble = self.write_file('preamble.btap', bytes(8 * 24))
        ftool.btap2bin(only_preamble, self.path('none.bin'))
        self.assertEqual(self.read_file('none.bin'), b'')

        one_more = self.write_file('one.btap', bytes(8 * 25))
        ftool.btap2bin(one_more, self.path('one.bin'))
        self.assertEqual(self.read_file('one.bin'), b'\x00')

    def test_trailing_partial_group_is_dropped(self):
        # Pinned current behaviour: an incomplete trailing group of input bytes
        # (fewer than 8) produces no output byte.
        source = self.PREAMBLE + _encode_btap_byte(0xff) + b'\xff\xff\xff'
        src = self.write_file('partial.btap', source)

        ftool.btap2bin(src, self.path('partial.bin'))

        self.assertEqual(self.read_file('partial.bin'), b'\xff')


class CreateBddTests(FtoolTestCase):
    def test_image_has_floppy_geometry_size_and_is_zeroed(self):
        path = self.path('blank.bdd')

        ftool.createbdd(path)

        data = self.read_file('blank.bdd')
        self.assertEqual(len(data), IMAGE_SIZE)
        self.assertEqual(data, bytes(IMAGE_SIZE))


class SectorTests(FtoolTestCase):
    def setUp(self):
        super().setUp()
        self.image = self.path('disk.bdd')
        ftool.createbdd(self.image)

    @staticmethod
    def pattern(seed):
        return bytes((i * 7 + seed) & 0xff for i in range(SECTOR_SIZE))

    @staticmethod
    def offset(track, sector):
        return (track * SECTORS + sector) * SECTOR_SIZE

    def test_import_then_export_round_trips_a_sector(self):
        data = self.pattern(3)
        self.write_file('sector.bin', data)

        ftool.importsector(self.path('sector.bin'), self.image, 2, 5)
        ftool.exportsector(self.image, self.path('exported.bin'), 2, 5)

        self.assertEqual(self.read_file('exported.bin'), data)

    def test_writing_one_sector_leaves_all_other_bytes_untouched(self):
        data = self.pattern(9)
        self.write_file('sector.bin', data)

        ftool.importsector(self.path('sector.bin'), self.image, 2, 5)

        expected = bytearray(IMAGE_SIZE)
        start = self.offset(2, 5)
        expected[start:start + SECTOR_SIZE] = data
        self.assertEqual(self.read_file('disk.bdd'), bytes(expected))

    def test_import_of_several_sectors_wraps_to_next_track(self):
        first = self.pattern(1)
        second = self.pattern(2)
        self.write_file('two.bin', first + second)

        ftool.importsector(self.path('two.bin'), self.image, 2, 15)

        image = self.read_file('disk.bdd')
        self.assertEqual(image[self.offset(2, 15):self.offset(2, 15) + SECTOR_SIZE], first)
        self.assertEqual(image[self.offset(3, 0):self.offset(3, 0) + SECTOR_SIZE], second)

    def test_dump_sector_prints_hex_rows_of_sixteen_bytes(self):
        data = self.pattern(5)
        self.write_file('sector.bin', data)
        ftool.importsector(self.path('sector.bin'), self.image, 1, 0)

        ftool.env = bc64_env.Environment(debug=True)
        out = io.StringIO()
        with redirect_stdout(out):
            ftool.dumpsector(self.image, 1, 0, 1)

        lines = out.getvalue().splitlines()
        self.assertIn('dump sector file', lines[0])
        rows = [line[len('[DBG]:'):] for line in lines[1:]]
        expected_rows = [
            ' '.join('{0:02x}'.format(v) for v in data[i:i + 16]) + ' '
            for i in range(0, SECTOR_SIZE, 16)
        ]
        self.assertEqual(rows, expected_rows)


class MainTests(FtoolTestCase):
    def test_createbdd_command_dispatches_to_createbdd(self):
        path = self.path('via_main.bdd')
        ftool.argv = ['ftool.py', 'createbdd', path]

        ftool.main()

        self.assertEqual(len(self.read_file('via_main.bdd')), IMAGE_SIZE)

    def test_missing_arguments_exit_with_status_1(self):
        ftool.argv = ['ftool.py', 'btap2bin']

        with self.assertRaises(SystemExit) as cm:
            ftool.main()

        self.assertEqual(cm.exception.code, 1)

    def test_unknown_command_is_reported(self):
        ftool.env = bc64_env.Environment(debug=True)
        ftool.argv = ['ftool.py', 'frobnicate']

        out = io.StringIO()
        with redirect_stdout(out):
            ftool.main()

        self.assertIn('Unknown command: frobnicate', out.getvalue())


import ftool_mkdisc  # noqa: E402  (sibling module, side-effect free)
from contextlib import redirect_stderr  # noqa: E402

BOOT_SIGNATURE = bytes([0xbd, 0x05, 0x01, 0x01])
CATALOG_OFFSET = SECTOR_SIZE          # catalog starts at 0/1
CATALOG_ENTRY_COUNT = 248


def _boot_sector(fill=0x11):
    return bytes([fill]) * (SECTOR_SIZE - 4) + BOOT_SIGNATURE


class MkdiscTestCase(FtoolTestCase):
    """Small synthetic manifests in a temp dir."""

    def setUp(self):
        super().setUp()
        self.write_file('boot.sector', _boot_sector())
        self.system = bytes((i * 3 + 1) & 0xff or 1 for i in range(300))  # 3 sectors
        self.write_file('sys.sector', self.system)

    def write_manifest(self, *lines, header=True):
        body = []
        if header:
            body.append('BOOTSECT.BIN boot.sector SR role=boot at=0/0 max=1')
            body.append('DISC.CAT     -           SR role=catalog at=0/1 max=31')
            body.append('BDOS.SYS     sys.sector  SR role=system at=2/0 max=160')
        body.extend(lines)
        return self.write_file('disc.manifest', ('\n'.join(body) + '\n').encode('ascii'))

    def build(self):
        out = self.path('out.bdd')
        ftool_mkdisc.mkdisc(self.path('disc.manifest'), out)
        return self.read_file('out.bdd')

    @staticmethod
    def entry(image, number):
        offset = CATALOG_OFFSET + number * 16
        return image[offset:offset + 16]

    @staticmethod
    def expected_entry(number, track, sector, length, attribs, name):
        return bytes([number, track, sector, length, attribs]) + name.encode('ascii')

    @staticmethod
    def offset(track, sector):
        return (track * SECTORS + sector) * SECTOR_SIZE

    def assert_error(self, pattern):
        out = self.path('out.bdd')
        with self.assertRaisesRegex(ftool_mkdisc.MkdiscError, pattern):
            ftool_mkdisc.mkdisc(self.path('disc.manifest'), out)
        self.assertFalse(os.path.exists(out))


class MkdiscLayoutTests(MkdiscTestCase):
    def test_minimal_manifest_gives_exact_image(self):
        first = bytes((i % 251) + 1 for i in range(3 * SECTOR_SIZE + 5))   # 4 sectors
        second = bytes((i % 13) + 1 for i in range(SECTOR_SIZE * 13 + 1))  # 14 sectors
        self.write_file('a.bin', first)
        self.write_file('b.bin', second)
        self.write_manifest('A.PRG a.bin RX', '# comment line', '', 'B.DAT b.bin RW  # trailing')

        image = self.build()

        expected = bytearray(IMAGE_SIZE)
        expected[0:SECTOR_SIZE] = _boot_sector()
        for number in range(CATALOG_ENTRY_COUNT):
            expected[CATALOG_OFFSET + number * 16] = number
        entries = [
            self.expected_entry(0, 0, 0, 1, 0x81, 'BOOTSECTBIN'),
            self.expected_entry(1, 0, 1, 31, 0x81, 'DISC    CAT'),
            self.expected_entry(2, 2, 0, 160, 0x81, 'BDOS    SYS'),
            self.expected_entry(3, 12, 0, 4, 0x05, 'A       PRG'),
            self.expected_entry(4, 12, 4, 14, 0x03, 'B       DAT'),
        ]
        for number, entry in enumerate(entries):
            expected[CATALOG_OFFSET + number * 16:CATALOG_OFFSET + number * 16 + 16] = entry
        expected[self.offset(2, 0):self.offset(2, 0) + len(self.system)] = self.system
        expected[self.offset(12, 0):self.offset(12, 0) + len(first)] = first
        expected[self.offset(12, 4):self.offset(12, 4) + len(second)] = second

        self.assertEqual(len(image), IMAGE_SIZE)
        self.assertEqual(image, bytes(expected))

    def test_files_follow_back_to_back_across_tracks_with_mid_track_starts(self):
        self.write_file('a.bin', bytes([1]) * (SECTOR_SIZE * 10))  # 10 sectors
        self.write_file('b.bin', bytes([2]) * (SECTOR_SIZE * 9))   # 9 sectors
        self.write_file('c.bin', bytes([3]))                        # 1 sector
        self.write_manifest('A a.bin R', 'B b.bin R', 'C c.bin R')

        image = self.build()

        self.assertEqual(self.entry(image, 3)[1:4], bytes([12, 0, 10]))
        self.assertEqual(self.entry(image, 4)[1:4], bytes([12, 10, 9]))
        self.assertEqual(self.entry(image, 5)[1:4], bytes([13, 3, 1]))
        self.assertEqual(image[self.offset(13, 3)], 3)
        self.assertEqual(image[self.offset(13, 3) + 1:self.offset(13, 4)], bytes(SECTOR_SIZE - 1))

    def test_system_file_is_catalogued_as_whole_loader_range_zero_padded(self):
        self.write_manifest()

        image = self.build()

        self.assertEqual(self.entry(image, 2)[:5], bytes([2, 2, 0, 160, 0x81]))
        start = self.offset(2, 0)
        self.assertEqual(image[start:start + len(self.system)], self.system)
        self.assertEqual(image[start + len(self.system):self.offset(12, 0)],
                         bytes(160 * SECTOR_SIZE - len(self.system)))

    def test_system_file_of_exactly_160_sectors_is_accepted(self):
        self.write_file('sys.sector', bytes([7]) * (160 * SECTOR_SIZE))
        self.write_manifest()

        image = self.build()

        self.assertEqual(image[self.offset(2, 0):self.offset(12, 0)], bytes([7]) * (160 * SECTOR_SIZE))

    def test_every_catalog_entry_carries_its_number_and_unused_are_otherwise_zero(self):
        self.write_manifest()

        image = self.build()

        for number in range(3, CATALOG_ENTRY_COUNT):
            self.assertEqual(self.entry(image, number), bytes([number]) + bytes(15), number)
        self.assertEqual(self.entry(image, 247)[0], 0xf7)

    def test_explicit_start_is_honoured_and_later_files_continue_after_it(self):
        self.write_file('a.bin', bytes([1]) * 10)
        self.write_file('b.bin', bytes([2]) * (SECTOR_SIZE * 2))
        self.write_file('c.bin', bytes([3]) * 10)
        self.write_manifest('A a.bin R', 'B b.bin R at=20/15', 'C c.bin R')

        image = self.build()

        self.assertEqual(self.entry(image, 3)[1:4], bytes([12, 0, 1]))
        self.assertEqual(self.entry(image, 4)[1:4], bytes([20, 15, 2]))
        self.assertEqual(self.entry(image, 5)[1:4], bytes([21, 1, 1]))
        self.assertEqual(image[self.offset(20, 15):self.offset(21, 1)], bytes([2]) * (SECTOR_SIZE * 2))
        self.assertEqual(image[self.offset(21, 1):self.offset(21, 1) + 10], bytes([3]) * 10)

    def test_explicit_start_equal_to_next_free_sector_is_accepted(self):
        self.write_file('a.bin', bytes([1]))
        self.write_manifest('A a.bin R at=12/0', 'B a.bin R at=12/1')

        image = self.build()

        self.assertEqual(self.entry(image, 4)[1:4], bytes([12, 1, 1]))

    def test_attributes_map_to_bits_in_any_order(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R', 'B a.bin w', 'C a.bin X', 'D a.bin S',
                            'E a.bin XSWR', 'F a.bin srx')

        image = self.build()

        attribs = [self.entry(image, n)[4] for n in range(3, 9)]
        self.assertEqual(attribs, [0x01, 0x02, 0x04, 0x80, 0x87, 0x85])

    def test_names_are_upper_cased_and_space_padded_with_short_extensions(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('hellowrd.prg a.bin R', 'x a.bin R', 'ab.c a.bin R', 'ABCDEFGH.12 a.bin R')

        image = self.build()

        names = [self.entry(image, n)[5:16] for n in range(3, 7)]
        self.assertEqual(names, [b'HELLOWRDPRG', b'X          ', b'AB      C  ', b'ABCDEFGH12 '])

    def test_existing_output_is_overwritten(self):
        self.write_manifest()
        self.write_file('out.bdd', b'old content')

        image = self.build()

        self.assertEqual(len(image), IMAGE_SIZE)

    def test_source_paths_are_relative_to_the_manifest_directory(self):
        sub = self.path('sub')
        os.mkdir(sub)
        with open(os.path.join(sub, 'boot.sector'), 'wb') as f:
            f.write(_boot_sector(0x22))
        with open(os.path.join(sub, 'sys.sector'), 'wb') as f:
            f.write(b'\x01')
        manifest = os.path.join(sub, 'disc.manifest')
        with open(manifest, 'w') as f:
            f.write('BOOT.BIN boot.sector SR role=boot at=0/0 max=1\nDISC.CAT - SR role=catalog at=0/1 max=31\n'
                    'BDOS.SYS sys.sector SR role=system at=2/0 max=160\n')

        saved_cwd = os.getcwd()
        os.chdir(self.dir)
        self.addCleanup(os.chdir, saved_cwd)
        ftool_mkdisc.mkdisc(manifest, self.path('out.bdd'))

        self.assertEqual(self.read_file('out.bdd')[:SECTOR_SIZE], _boot_sector(0x22))


class MkdiscErrorTests(MkdiscTestCase):
    def test_missing_source_file(self):
        self.write_manifest('A.PRG nothere.bin R')
        self.assert_error(r'disc\.manifest:4: cannot read source file .*nothere\.bin')

    def test_empty_source_file(self):
        self.write_file('empty.bin', b'')
        self.write_manifest('A.PRG empty.bin R')
        self.assert_error(r':4: source file .*empty\.bin is empty')

    def test_file_over_255_sectors(self):
        self.write_file('big.bin', bytes(SECTOR_SIZE * 255 + 1))
        self.write_manifest('BIG.PRG big.bin R')
        self.assert_error(r':4: BIG\.PRG is 256 sectors, a file holds at most 255')

    def test_file_of_exactly_255_sectors_is_accepted(self):
        self.write_file('big.bin', bytes([1]) * (SECTOR_SIZE * 255))
        self.write_manifest('BIG.PRG big.bin R')
        image = self.build()
        self.assertEqual(self.entry(image, 3)[3], 255)

    def test_system_file_over_160_sectors(self):
        self.write_file('sys.sector', bytes(160 * SECTOR_SIZE + 1))
        self.write_manifest()
        self.assert_error(r':3: BDOS\.SYS is 161 sectors, more than max=160')

    def test_file_past_end_of_disc(self):
        self.write_file('big.bin', bytes([1]) * (SECTOR_SIZE * 255))
        # 192 + 3 * 255 = 957; the fourth 255-sector file would end at 1212 > 1024
        self.write_manifest('A big.bin R', 'B big.bin R', 'C big.bin R', 'D big.bin R')
        self.assert_error(r':7: D \(255 sectors from 59/13\) does not fit: it ends past sector 1024')

    def test_file_ending_exactly_at_end_of_disc_is_accepted(self):
        self.write_file('one.bin', b'\x01')
        self.write_manifest('A one.bin R at=63/15')
        image = self.build()
        self.assertEqual(image[-SECTOR_SIZE], 1)

    def test_catalog_full_at_248_used_entries(self):
        self.write_file('one.bin', b'\x01')
        # boot + DISC.CAT + system + 245 = 248 used entries
        self.write_manifest(*['F{} one.bin R'.format(i) for i in range(245)])
        self.assert_error(r'catalog full: 248 entries used, at most 247 allowed')

    def test_catalog_with_247_used_entries_is_accepted(self):
        self.write_file('one.bin', b'\x01')
        self.write_manifest(*['F{} one.bin R'.format(i) for i in range(244)])
        image = self.build()
        self.assertEqual(self.entry(image, 246)[:5], bytes([246, 27, 3, 1, 0x01]))
        self.assertEqual(self.entry(image, 247), bytes([247]) + bytes(15))

    def test_boot_file_not_128_bytes(self):
        self.write_file('boot.sector', bytes(60) + BOOT_SIGNATURE)
        self.write_manifest()
        self.assert_error(r':1: boot file .* is 64 bytes, it must be exactly 128')

    def test_boot_file_without_signature(self):
        self.write_file('boot.sector', bytes(SECTOR_SIZE))
        self.write_manifest()
        self.assert_error(r':1: boot file .* does not end with the signature BD 05 01 01')

    def test_first_line_not_boot(self):
        self.write_manifest('BDOS.SYS sys.sector SR role=system at=2/0 max=160',
                            'BOOT.BIN boot.sector SR role=boot at=0/0 max=1', header=False)
        self.assert_error(r':1: file 1 of the manifest must have role=boot')

    def test_second_line_not_catalog(self):
        self.write_manifest('# header', 'BOOT.BIN boot.sector SR role=boot at=0/0 max=1',
                            'BDOS.SYS sys.sector SR role=system at=2/0 max=160', header=False)
        self.assert_error(r':3: file 2 of the manifest must have role=catalog')

    def test_third_line_not_system(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('BOOT.BIN boot.sector SR role=boot at=0/0 max=1',
                            'DISC.CAT - SR role=catalog at=0/1 max=31', 'A a.bin R', header=False)
        self.assert_error(r':3: file 3 of the manifest must have role=system')

    def test_boot_used_again(self):
        self.write_manifest('BOOT2.BIN boot.sector SR role=boot at=0/0 max=1')
        self.assert_error(r':4: role=boot is only allowed on line 1 of the file list')

    def test_system_used_again(self):
        self.write_manifest('BDOS2.SYS sys.sector SR role=system at=2/0 max=160')
        self.assert_error(r':4: role=system is only allowed on line 3 of the file list')

    def test_manifest_without_system_line(self):
        self.write_manifest('BOOT.BIN boot.sector SR role=boot at=0/0 max=1',
                            'DISC.CAT - SR role=catalog at=0/1 max=31', header=False)
        self.assert_error(r'at least the boot, catalog and system file')

    def test_explicit_start_before_next_free_sector(self):
        self.write_file('a.bin', bytes(SECTOR_SIZE * 2))
        self.write_manifest('A a.bin R', 'B a.bin R at=12/1')
        self.assert_error(r':5: start 12/1 is before the next free sector 12/2')

    def test_explicit_start_inside_loader_range(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R at=5/0')
        self.assert_error(r':4: start 5/0 is before the next free sector 12/0')

    def test_explicit_start_outside_geometry(self):
        self.write_file('a.bin', b'x')
        for place in ('64/0', '12/16'):
            with self.subTest(place=place):
                self.write_manifest('A a.bin R at=' + place)
                self.assert_error(r':4: start .* outside the disc')

    def test_bad_at_value(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R at=12-0')
        self.assert_error(r':4: bad value "12-0" for at')

    def test_bad_names(self):
        self.write_file('a.bin', b'x')
        for name in ('TOOLONGNM.PRG', 'A.PRGX', 'A-B.PRG', '.PRG', 'A.B.C'):
            with self.subTest(name=name):
                self.write_manifest(name + ' a.bin R')
                self.assert_error(r':4: bad name')

    def test_duplicate_name_after_upper_casing(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A.PRG a.bin R', 'a.prg a.bin R')
        self.assert_error(r':5: duplicate name "A\.PRG" \(already on line 4\)')

    def test_disc_cat_listed_again(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('disc.cat a.bin R')
        self.assert_error(r':4: duplicate name "DISC\.CAT" \(already on line 2\)')

    def test_unknown_attribute_letter(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin RQ')
        self.assert_error(r':4: unknown attribute "Q"')

    def test_empty_attributes(self):
        # A missing ATTRIBS column leaves the line with too few columns.
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin')
        self.assert_error(r':4: malformed line')

    def test_malformed_line_with_a_stray_word(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R extra')
        self.assert_error(r':4: malformed option "extra"')

    def test_missing_manifest(self):
        self.assert_error(r'cannot read manifest')

    def test_error_leaves_existing_output_unchanged(self):
        self.write_file('out.bdd', b'previous image')
        self.write_manifest('A.PRG nothere.bin R')

        with self.assertRaises(ftool_mkdisc.MkdiscError):
            ftool_mkdisc.mkdisc(self.path('disc.manifest'), self.path('out.bdd'))

        self.assertEqual(self.read_file('out.bdd'), b'previous image')
        self.assertEqual(sorted(os.listdir(self.dir)),
                         ['boot.sector', 'disc.manifest', 'out.bdd', 'sys.sector'])

class MkdiscOptionTests(MkdiscTestCase):
    def test_max_reserves_the_slot_for_the_next_file(self):
        self.write_file('a.bin', bytes([1]) * (SECTOR_SIZE * 2))
        self.write_file('b.bin', b'x')
        self.write_manifest('A a.bin R max=5', 'B b.bin R')

        image = self.build()

        self.assertEqual(self.entry(image, 3)[1:4], bytes([12, 0, 2]))  # catalog length = real size
        self.assertEqual(self.entry(image, 4)[1:4], bytes([12, 5, 1]))

    def test_max_equal_to_size_is_accepted(self):
        self.write_file('a.bin', bytes([1]) * (SECTOR_SIZE * 2))
        self.write_manifest('A a.bin R max=2')
        self.assertEqual(self.entry(self.build(), 3)[1:4], bytes([12, 0, 2]))

    def test_file_larger_than_max_is_an_error(self):
        self.write_file('a.bin', bytes(SECTOR_SIZE * 3 + 1))
        self.write_manifest('A.PRG a.bin R max=3')
        self.assert_error(r':4: A\.PRG is 4 sectors, more than max=3')

    def test_max_over_255_is_an_error(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R max=256')
        self.assert_error(r':4: max=256 is more than a file can hold \(255 sectors\)')

    def test_bad_max_values_are_errors(self):
        self.write_file('a.bin', b'x')
        for value in ('0', 'x', '-1', '1.5'):
            with self.subTest(value=value):
                self.write_manifest('A a.bin R max=' + value)
                self.assert_error(r':4: bad value "{}" for max'.format(value))

    def test_slot_past_the_end_of_the_disc_is_an_error(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R at=63/15 max=2')
        self.assert_error(r':4: A \(2 sectors from 63/15\) does not fit')

    def test_at_is_honoured_and_may_leave_a_gap(self):
        self.write_file('a.bin', b'\x07')
        self.write_manifest('A a.bin R at=30/4')
        image = self.build()
        self.assertEqual(self.entry(image, 3)[1:4], bytes([30, 4, 1]))
        self.assertEqual(image[self.offset(30, 4)], 7)

    def test_at_inside_the_previous_slot_is_an_error(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R max=4', 'B a.bin R at=12/3')
        self.assert_error(r':5: start 12/3 is before the next free sector 12/4')

    def test_at_equal_to_the_end_of_the_previous_slot_is_accepted(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R max=4', 'B a.bin R at=12/4')
        self.assertEqual(self.entry(self.build(), 4)[1:4], bytes([12, 4, 1]))

    def test_unknown_key_is_an_error(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R size=3')
        self.assert_error(r':4: unknown option "size"')

    def test_malformed_options_are_errors(self):
        self.write_file('a.bin', b'x')
        for option in ('max', 'max=', '=3', 'role=other'):
            with self.subTest(option=option):
                self.write_manifest('A a.bin R ' + option)
                self.assert_error(r':4: ')

    def test_duplicate_key_is_an_error(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R max=2 max=3')
        self.assert_error(r':4: duplicate option "max"')

    def test_old_positional_place_is_gone(self):
        self.write_file('a.bin', b'x')
        for place in ('12/0', 'boot', 'system'):
            with self.subTest(place=place):
                self.write_manifest('A a.bin R ' + place)
                self.assert_error(r':4: malformed option')

    def test_options_in_any_order(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R max=3 at=14/2')
        self.assertEqual(self.entry(self.build(), 3)[1:4], bytes([14, 2, 1]))


class MkdiscRoleTests(MkdiscTestCase):
    BOOT = 'BOOT.BIN boot.sector SR role=boot at=0/0 max=1'
    CAT = 'DISC.CAT - SR role=catalog at=0/1 max=31'
    SYS = 'BDOS.SYS sys.sector SR role=system at=2/0 max=160'

    def manifest(self, boot=BOOT, cat=CAT, system=SYS):
        self.write_manifest(boot, cat, system, header=False)

    def test_reference_roles_are_accepted(self):
        self.manifest()
        self.assertEqual(self.entry(self.build(), 1)[:5], bytes([1, 0, 1, 31, 0x81]))

    def test_boot_not_at_0_0(self):
        self.manifest(boot='BOOT.BIN boot.sector SR role=boot at=0/2 max=1')
        self.assert_error(r':1: role=boot needs at=0/0 max=1')

    def test_boot_without_at(self):
        self.manifest(boot='BOOT.BIN boot.sector SR role=boot max=1')
        self.assert_error(r':1: role=boot needs at=0/0 max=1')

    def test_boot_max_not_1(self):
        self.manifest(boot='BOOT.BIN boot.sector SR role=boot at=0/0 max=2')
        self.assert_error(r':1: role=boot needs at=0/0 max=1')

    def test_catalog_not_at_0_1(self):
        self.manifest(cat='DISC.CAT - SR role=catalog at=0/2 max=31')
        self.assert_error(r':2: role=catalog needs at=0/1 max=31')

    def test_catalog_max_not_31(self):
        self.manifest(cat='DISC.CAT - SR role=catalog at=0/1 max=30')
        self.assert_error(r':2: role=catalog needs at=0/1 max=31')

    def test_catalog_with_a_source(self):
        self.manifest(cat='DISC.CAT boot.sector SR role=catalog at=0/1 max=31')
        self.assert_error(r':2: the source "-" is for \(and only for\) role=catalog')

    def test_catalog_with_another_name(self):
        self.manifest(cat='OTHER.CAT - SR role=catalog at=0/1 max=31')
        self.assert_error(r':2: role=catalog is only for DISC\.CAT')

    def test_disc_cat_without_role_catalog(self):
        self.manifest(cat='DISC.CAT boot.sector SR')
        self.assert_error(r':2: DISC\.CAT is the catalog: it needs role=catalog')

    def test_source_dash_without_role_catalog(self):
        self.write_manifest('A.PRG - R')
        self.assert_error(r':4: the source "-" is for \(and only for\) role=catalog')

    def test_system_not_at_2_0(self):
        self.manifest(system='BDOS.SYS sys.sector SR role=system at=3/0 max=160')
        self.assert_error(r':3: role=system needs at=2/0')

    def test_system_max_over_160(self):
        self.manifest(system='BDOS.SYS sys.sector SR role=system at=2/0 max=161')
        self.assert_error(r':3: role=system needs max=N with N <= 160')

    def test_system_without_max(self):
        self.manifest(system='BDOS.SYS sys.sector SR role=system at=2/0')
        self.assert_error(r':3: role=system needs max=N with N <= 160')

    def test_system_catalog_length_is_max_and_next_file_follows_the_slot(self):
        self.write_file('a.bin', b'x')
        self.manifest(system='BDOS.SYS sys.sector SR role=system at=2/0 max=100')
        self.write_manifest(self.BOOT, self.CAT, 'BDOS.SYS sys.sector SR role=system at=2/0 max=100',
                            'A a.bin R', header=False)
        image = self.build()
        self.assertEqual(self.entry(image, 2)[1:4], bytes([2, 0, 100]))
        self.assertEqual(self.entry(image, 3)[1:4], bytes([8, 4, 1]))  # 32 + 100 = linear 132

    def test_role_on_a_later_line_is_an_error(self):
        self.write_file('a.bin', b'x')
        self.write_manifest('A a.bin R role=catalog')
        self.assert_error(r':4: role=catalog is only allowed on line 2 of the file list')

    def test_system_file_over_max_is_an_error(self):
        self.write_file('sys.sector', bytes(SECTOR_SIZE * 11))
        self.manifest(system='BDOS.SYS sys.sector SR role=system at=2/0 max=10')
        self.assert_error(r':3: BDOS\.SYS is 11 sectors, more than max=10')


class MkdiscMainTests(MkdiscTestCase):
    def test_mkdisc_command_writes_image(self):
        self.write_manifest()
        ftool.argv = ['ftool.py', 'mkdisc', self.path('disc.manifest'), self.path('via_main.bdd')]

        ftool.main()

        image = self.read_file('via_main.bdd')
        self.assertEqual(len(image), IMAGE_SIZE)
        self.assertEqual(image[:SECTOR_SIZE], _boot_sector())

    def test_mkdisc_error_exits_1_with_message_on_stderr_and_no_output(self):
        self.write_file('sys.sector', bytes(161 * SECTOR_SIZE))
        self.write_manifest()
        out = self.path('via_main.bdd')
        ftool.argv = ['ftool.py', 'mkdisc', self.path('disc.manifest'), out]

        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            ftool.main()

        self.assertEqual(cm.exception.code, 1)
        self.assertIn('disc.manifest:3', err.getvalue())
        self.assertIn('160', err.getvalue())
        self.assertFalse(os.path.exists(out))

    def test_mkdisc_missing_arguments_exit_with_status_1(self):
        for args in ([], [self.path('disc.manifest')]):
            with self.subTest(args=args):
                ftool.argv = ['ftool.py', 'mkdisc'] + args
                with self.assertRaises(SystemExit) as cm:
                    ftool.main()
                self.assertEqual(cm.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
