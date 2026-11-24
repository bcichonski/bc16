import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

import bc81asmc
import bc81asmc_listing
from bc81asmc_grammar import program

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(HERE, 'bc81asmc.py')
BOOT = os.path.join(HERE, '..', 'bdos', 'boot.basm')
BCOS = os.path.join(HERE, 'bcOS', 'bcos.basm')


def build(source):
    with contextlib.redirect_stdout(io.StringIO()):
        return bc81asmc.compile(program.parse(source), False)


def read(path):
    with open(path, encoding='utf-8', newline='') as f:
        return f.read().replace('\r\n', '\n')


def parse_rows(listing):
    '''Rows as (address text, bytes text, source text) from the fixed columns.'''
    return [(row[0:4].strip(), row[6:17].strip(), row[19:]) for row in listing.split('\n')[:-1]]


class TestMap(unittest.TestCase):
    def test_header_labels_defs_sorted_by_value_then_name(self):
        src = (".org 0x0100\n"
               ".def zeta, 0x0002\n"
               ".def beta, 0x0102\n"
               "start: nop\n"
               "nop\n"
               "alpha: nop\n"
               "aa: nop\n")
        text = bc81asmc_listing.format_map('prog.basm', build(src))
        lines = text.split('\n')
        self.assertEqual(lines[0], '; bc81asmc map prog.basm')
        self.assertEqual(lines[1], '; org 0x0100 end 0x0104')
        self.assertEqual(lines[2:], [
            '0x0002 def zeta',
            '0x0100 label start',
            '0x0102 label alpha',
            '0x0102 def beta',
            '0x0103 label aa',
            ''])

    def test_label_at_end_of_file_takes_end_address(self):
        text = bc81asmc_listing.format_map('p.basm', build(".org 0x0200\nnop\nnop\nfin:\n"))
        parsed = bc81asmc_listing.read_map(text)
        self.assertEqual(parsed.end, 0x0202)
        self.assertEqual(parsed.value_of('fin'), 0x0202)

    def test_read_map_round_trip(self):
        src = ".org 0x0300\n.def k, 0x00ff\nstart: nop\nend: nop\n"
        parsed = bc81asmc_listing.read_map(bc81asmc_listing.format_map('r.basm', build(src)))
        self.assertEqual(parsed.source, 'r.basm')
        self.assertEqual((parsed.org, parsed.end), (0x0300, 0x0302))
        self.assertEqual(parsed.symbols, [
            bc81asmc_listing.Symbol('k', 0xff, 'def'),
            bc81asmc_listing.Symbol('start', 0x300, 'label'),
            bc81asmc_listing.Symbol('end', 0x301, 'label')])

    def test_read_map_rejects_bad_line(self):
        with self.assertRaises(ValueError):
            bc81asmc_listing.read_map('; bc81asmc map x\n; org 0x0000 end 0x0000\n0x0001 oops name\n')


class TestListing(unittest.TestCase):
    def test_forward_reference_shows_patched_bytes(self):
        src = ".org 0x0100\n  cal :target\nnop\ntarget: nop\n"
        ctx = build(src)
        listing = bc81asmc_listing.format_listing(src, ctx)
        self.assertNotIn('fa', listing)
        rows = parse_rows(listing)
        self.assertEqual(rows[1][0], '0100')
        self.assertEqual(rows[1][1], ' '.join('{0:02x}'.format(b) for b in ctx.bytes[0:len(rows[1][1].split())]))
        self.assertEqual(rows[1][2], '  cal :target')

    def test_mv_is_one_row_of_four_bytes(self):
        src = ".org 0x0100\n.mv csci, :x\nx: nop\n"
        rows = parse_rows(bc81asmc_listing.format_listing(src, build(src)))
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[1][1].split()), 4)
        self.assertEqual(rows[1][0], '0100')

    def test_db_longer_than_four_bytes_wraps(self):
        src = ".org 0x0100\n.db 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09\n"
        rows = parse_rows(bc81asmc_listing.format_listing(src, build(src)))
        self.assertEqual(rows, [
            ('0100', '', '.org 0x0100'),
            ('0100', '01 02 03 04', '.db 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09'),
            ('0104', '05 06 07 08', ''),
            ('0108', '09', '')])

    def test_comment_blank_org_and_label_rows(self):
        src = "; header\n.org 0x0100\nstart:\n.def k, 0x0001\n  nop ; fine   \n.assert :start = 0x0100\n"
        ctx = build(src)
        rows = parse_rows(bc81asmc_listing.format_listing(src, ctx))
        self.assertEqual(rows, [
            ('', '', '; header'),
            ('0100', '', '.org 0x0100'),
            ('0100', '', 'start:'),
            ('', '', '.def k, 0x0001'),
            ('0100', '00', '  nop ; fine'),
            ('', '', '.assert :start = 0x0100')])

    def test_every_source_line_once_in_order(self):
        src = "; a\n.org 0x0100\nx: nop\n; b\n.db 0x01,0x02,0x03,0x04,0x05,0x06\nnop\n"
        listing = bc81asmc_listing.format_listing(src, build(src))
        sources = [r[2] for r in parse_rows(listing) if r[2]]
        self.assertEqual(sources, [l for l in src.split('\n') if l])
        self.assertEqual(len(parse_rows(listing)), len(src.split('\n')) - 1 + 1)  # one wrap row

    def test_no_trailing_whitespace_and_lf_endings(self):
        src = "; top   \n.org 0x0100\nnop   \n"
        listing = bc81asmc_listing.format_listing(src, build(src))
        self.assertNotIn('\r', listing)
        for row in listing.split('\n'):
            self.assertEqual(row, row.rstrip())


class TestRealImages(unittest.TestCase):
    def check(self, path):
        src = read(path)
        ctx = build(src)
        listing = bc81asmc_listing.format_listing(src, ctx)
        rows = parse_rows(listing)
        image = bytearray()
        for address, data, _ in rows:
            if data:
                self.assertEqual(int(address, 16), ctx.startaddr + len(image))
                image.extend(int(b, 16) for b in data.split())
        self.assertEqual(bytes(image), bytes(ctx.bytes))
        return bc81asmc_listing.read_map(bc81asmc_listing.format_map(os.path.basename(path), ctx))

    def test_bcos(self):
        parsed = self.check(BCOS)
        self.assertEqual(parsed.value_of('os_metacall'), 0x0008)
        self.assertEqual(parsed.value_of('os_metatab'), 0x000c)
        self.assertEqual(parsed.org, 0x0000)

    def test_boot(self):
        parsed = self.check(BOOT)
        self.assertEqual(parsed.org, 0x0e00)


class TestCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def path(self, name):
        return os.path.join(self.dir, name)

    def run_asm(self, source, *flags):
        with open(self.path('prog.basm'), 'w', encoding='utf8', newline='') as f:
            f.write(source)
        return subprocess.run([sys.executable, SCRIPT, 'prog.basm', *flags], cwd=self.dir,
                              capture_output=True, text=True)

    def test_no_flags_writes_no_extra_files(self):
        r = self.run_asm("start: nop\n")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(sorted(os.listdir(self.dir)), ['prog.basm', 'prog.btap'])
        self.assertNotIn('.lst', r.stdout)

    def test_flags_write_both_files_and_btap_is_identical(self):
        src = ".org 0x0100\nstart: cal :start\n.db 0x01,0x02,0x03,0x04,0x05\n"
        plain = self.run_asm(src)
        with open(self.path('prog.btap'), 'rb') as f:
            expected = f.read()
        os.remove(self.path('prog.btap'))
        r = self.run_asm(src, '--lst', 'out.lst', '--map', 'out.map')
        self.assertEqual(r.returncode, 0)
        with open(self.path('prog.btap'), 'rb') as f:
            self.assertEqual(f.read(), expected)
        self.assertEqual(r.stderr, '')
        self.assertEqual(r.stdout.splitlines()[:-1],
                         plain.stdout.splitlines()[:-1] + ['Saving output file out.lst...',
                                                           'Saving output file out.map...'])
        with open(self.path('out.lst'), encoding='utf8', newline='') as f:
            self.assertIn('0100  ', f.read())
        with open(self.path('out.map'), encoding='utf8', newline='') as f:
            parsed = bc81asmc_listing.read_map(f.read())
        self.assertEqual(parsed.source, 'prog.basm')
        self.assertEqual(parsed.value_of('start'), 0x0100)

    def test_only_one_flag(self):
        r = self.run_asm("nop\n", '--map', 'only.map')
        self.assertEqual(r.returncode, 0)
        self.assertTrue(os.path.exists(self.path('only.map')))
        self.assertFalse(os.path.exists(self.path('only.lst')))

    def test_assembler_error_writes_neither_file(self):
        r = self.run_asm("cal :nowhere\n", '--lst', 'out.lst', '--map', 'out.map')
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(self.path('out.lst')))
        self.assertFalse(os.path.exists(self.path('out.map')))
        self.assertFalse(os.path.exists(self.path('prog.btap')))

    def test_parse_error_writes_neither_file(self):
        r = self.run_asm("mov a, 0x100\n", '--lst', 'out.lst', '--map', 'out.map')
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(self.path('out.lst')))
        self.assertFalse(os.path.exists(self.path('out.map')))

    def test_bcos_btap_identical_with_flags(self):
        for src, name in ((BCOS, 'bcos'), (BOOT, 'boot')):
            with open(self.path(name + '.basm'), 'w', encoding='utf8', newline='') as f:
                f.write(read(src))
            subprocess.run([sys.executable, SCRIPT, name + '.basm'], cwd=self.dir,
                           capture_output=True, check=True)
            with open(self.path(name + '.btap'), 'rb') as f:
                expected = f.read()
            subprocess.run([sys.executable, SCRIPT, name + '.basm', '--lst', name + '.lst',
                            '--map', name + '.map'], cwd=self.dir, capture_output=True, check=True)
            with open(self.path(name + '.btap'), 'rb') as f:
                self.assertEqual(f.read(), expected)


if __name__ == '__main__':
    unittest.main()
