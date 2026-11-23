"""Compile-pattern create/delete on a pre-filled disc (issue #41, AC 4, light), on the headless emulator.

A compiler run creates X.TOK, X.IR and X.O and deletes X.TOK and X.IR (here X.TOK is pre-created
on the disc: loading rm.prg/cp.prg from the emulated disc is the slow part of a session). Two scenarios on temp copies of
the built os.bdd, with small `cp` sources (hellowrd.prg, test.b):
  * happy path: after the rm, X.O starts at the start of the largest free gap (the freed X.TOK
    space, not the smaller free tail); every other file is byte-identical;
  * failure: no gap is big enough for the file: `disc full`, every other file and every sector
    outside the gap are byte-identical.
Positions are derived from the built disc, never pinned.
"""
import os
import shutil
import tempfile
import unittest

import e2e_harness as h
from test_e2e_alloc_gap import (DISC_END, assert_no_overlap, end, fill_tail, find, run,
                                sector_bytes, start)

TOK = 4                       # sectors of the pre-created X.TOK (X.IR is deleted too in the real run)
TAIL_HAPPY = TOK + 1 + 2      # X.TOK, one KEEP.DAT sector, then a tail as big as X.O
TAIL_FULL = 3


class CompileCycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.disc = os.path.join(self.tmp.name, "os.bdd")
        shutil.copyfile(h.OS_DISK, self.disc)

    def assert_files_unchanged(self, before_catalog, before, catalog, image, skip=()):
        for old in before_catalog:
            name = (old.name, old.ext)
            if name == ("DISC", "CAT") or name in skip:
                continue
            new = [e for e in catalog if (e.name, e.ext) == name]
            self.assertEqual(1, len(new), "%s.%s missing" % name)
            self.assertEqual((start(old), old.length), (start(new[0]), new[0].length))
            self.assertEqual(before[start(old) * h.SECTOR_SIZE:end(old) * h.SECTOR_SIZE],
                             image[start(old) * h.SECTOR_SIZE:end(old) * h.SECTOR_SIZE],
                             "%s.%s changed" % name)

    def test_object_file_goes_to_largest_gap_after_tok_and_ir_are_deleted(self):
        obj = find(h.read_catalog(self.disc), "test.b")
        fill_tail(self.disc, TAIL_HAPPY)
        tok = h.disc_put(self.disc, "X.TOK", bytes((i * 3 + 7) & 0xff for i in range(TOK * 128)))
        keep = h.disc_put(self.disc, "KEEP.DAT", bytes((i * 5 + 1) & 0xff for i in range(128)))
        tail = DISC_END - end(keep)
        self.assertEqual(obj.length, tail)
        self.assertGreater(tok.length, tail)
        before_catalog = h.read_catalog(self.disc)
        before = h.read_bytes(self.disc)

        out, catalog, image = run("compile_cycle_happy", self.disc, [
            "rm -f x.tok", "cp test.b x.o"])

        self.assertNotIn(b"error", out)
        new = find(catalog, "x.o")
        # the freed TOK space is the largest gap, bigger than the free tail after KEEP.DAT, which
        # would also hold X.O (and is where append-only allocation would put it)
        self.assertEqual(start(tok), start(new))
        self.assertEqual(obj.length, new.length)
        self.assertEqual(before[start(obj) * 128:end(obj) * 128],
                         image[start(new) * 128:end(new) * 128])
        names = [(e.name, e.ext) for e in catalog]
        self.assertNotIn(("X", "TOK"), names)
        assert_no_overlap(self, catalog)
        self.assert_files_unchanged(before_catalog, before, catalog, image,
                                    skip=[("X", "TOK")])
        for sector in range(192):
            if h.CAT_FIRST_SECTOR <= sector < h.CAT_FIRST_SECTOR + h.CAT_SECTORS:
                continue
            self.assertEqual(sector_bytes(before, sector), sector_bytes(image, sector))

    def test_no_gap_big_enough_stops_with_disc_full(self):
        big = find(h.read_catalog(self.disc), "hellowrd.prg")
        self.assertGreater(big.length, TAIL_FULL)
        fill_tail(self.disc, TAIL_FULL)
        before_catalog = h.read_catalog(self.disc)
        before = h.read_bytes(self.disc)
        gap = (DISC_END - TAIL_FULL, DISC_END)

        out, catalog, image = run("compile_cycle_full", self.disc, ["cp hellowrd.prg x.o"])

        self.assertIn(b"error: F3 disc full", out)
        assert_no_overlap(self, catalog)
        self.assert_files_unchanged(before_catalog, before, catalog, image,
                                    skip=[("X", "O")])
        for sector in range(DISC_END):
            if h.CAT_FIRST_SECTOR <= sector < h.CAT_FIRST_SECTOR + h.CAT_SECTORS \
                    or gap[0] <= sector < gap[1]:
                continue
            self.assertEqual(sector_bytes(before, sector), sector_bytes(image, sector),
                             "sector %d changed" % sector)


if __name__ == "__main__":
    unittest.main()
