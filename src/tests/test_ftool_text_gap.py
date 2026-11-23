"""ftool importtext places a file in the largest free gap of sectors 192..1023 (same rule as bdio, #41)."""
import unittest

import ftool_mkdisc as mk
import ftool_text

from tests.test_ftool_text import CATALOG_OFFSET, SECTOR_SIZE, TextTestCase, entry_bytes

FIRST = mk.ALLOC_FIRST_SECTOR
END = mk.DISC_SECTORS


class GapPlacementTests(TextTestCase):
    def put_entries(self, extents):
        """Add (start, length) files from entry 3; a length over 255 is split into several entries."""
        pieces = []
        for start, length in extents:
            while length > 0:
                part = min(length, 255)
                pieces.append((start, part))
                start, length = start + part, length - part
        image = bytearray(self.base)
        for number, (start, length) in enumerate(pieces, start=3):
            offset = CATALOG_OFFSET + number * 16
            image[offset:offset + 16] = bytes(
                [number, start // 16, start % 16, length, 3]) + b'F%-2d     BIN' % number
        with open(self.disc, 'wb') as f:
            f.write(image)
        self.base = bytes(image)

    def placed(self, text=b'a\n', name='NEW.TXT'):
        self.imp(text, name=name)
        image = self.read('disc.bdd')
        for number in range(3, 40):
            entry = entry_bytes(image, number)
            if entry[3] and entry[5:13].rstrip() == name.split('.')[0].encode():
                return entry[1] * 16 + entry[2]
        self.fail('entry not found')

    def test_middle_gap_larger_than_tail_is_reused(self):
        # gap of 100 sectors after the first file, tail of 10
        self.put_entries([(FIRST, 20), (FIRST + 120, END - FIRST - 120 - 10)])
        self.assertEqual(self.placed(), FIRST + 20)

    def test_tie_goes_to_the_lowest_start(self):
        self.put_entries([(FIRST, 10), (FIRST + 20, 10), (FIRST + 40, END - FIRST - 40 - 10)])
        # gaps: 10 at FIRST+10, 10 at FIRST+30, 10 at the tail
        self.assertEqual(self.placed(), FIRST + 10)

    def test_tail_is_chosen_when_largest(self):
        self.put_entries([(FIRST, 20), (FIRST + 30, 20)])
        self.assertEqual(self.placed(), FIRST + 50)

    def test_empty_disc_starts_at_first_allocatable_sector(self):
        self.assertEqual(self.placed(), FIRST)

    def test_text_larger_than_largest_gap_is_disc_full_and_unchanged(self):
        # free: 3 + 3 + 3 sectors in three gaps, a 4-sector text does not fit any of them
        self.put_entries([(FIRST + 3, 100), (FIRST + 106, 100), (FIRST + 209, END - FIRST - 209 - 3)])
        text = b''.join(b'x' * 70 + b'\n' for _ in range(6))
        data, _ = ftool_text.encode_text(text)
        self.assertEqual(len(data) // SECTOR_SIZE, 4)
        self.assert_import_fails(text, 'disc full')

    def test_text_exactly_filling_the_largest_gap_fits(self):
        self.put_entries([(FIRST + 3, 100), (FIRST + 106, END - FIRST - 106)])
        text = b''.join(b'x' * 70 + b'\n' for _ in range(4))
        self.assertEqual(len(ftool_text.encode_text(text)[0]) // SECTOR_SIZE, 3)
        self.assertEqual(self.placed(text), FIRST)

    def test_sectors_below_the_allocatable_area_are_never_used(self):
        # the catalog keeps only a file at the tail: 0..191 look free but are reserved
        image = bytearray(self.base)
        for number in range(3):
            offset = CATALOG_OFFSET + number * 16
            image[offset:offset + 16] = bytes(16)
        offset = CATALOG_OFFSET
        image[offset:offset + 16] = bytes([0, FIRST // 16 + 1, 0, 1, 3]) + b'ONLY    BIN'
        with open(self.disc, 'wb') as f:
            f.write(image)
        self.base = bytes(image)
        self.imp(b'a\n')
        entry = entry_bytes(self.read('disc.bdd'), 1)
        self.assertEqual(entry[1] * 16 + entry[2], FIRST + 16 + 1)

    def test_extent_past_the_disc_is_clipped(self):
        self.put_entries([(END - 5, 40)])
        self.assertEqual(self.placed(), FIRST)

    def test_reserved_area_free_in_catalog_but_alloc_area_full_is_disc_full(self):
        image = bytearray(self.base)
        for number in range(3):
            image[CATALOG_OFFSET + number * 16:CATALOG_OFFSET + number * 16 + 16] = bytes(16)
        self.base = bytes(image)
        for number in range(4):
            start = FIRST + number * 208
            image[CATALOG_OFFSET + number * 16:CATALOG_OFFSET + number * 16 + 16] = bytes(
                [number, start // 16, start % 16, 208, 3]) + b'FULL%d   BIN' % number
        with open(self.disc, 'wb') as f:
            f.write(image)
        self.base = bytes(image)
        self.assert_import_fails(b'a\n', 'disc full')


if __name__ == '__main__':
    unittest.main()
