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


if __name__ == '__main__':
    unittest.main()
