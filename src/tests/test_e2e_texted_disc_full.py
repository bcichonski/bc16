"""E2E: TextEd `s` on a disc whose largest free gap is too small prints `disc full` (issue #41).

Temp copy of the built utils.bdd (drive B, where texted lives), pre-filled with
`e2e_harness.disc_put` so the largest gap is smaller than the typed text; session A is os.bdd.
Positions are derived from the built disc, never pinned. Typing costs about 0.4 s per inserted
line, so the text is two 80-character lines (2 sectors) and the gap is made tiny instead.
"""
import os
import shutil
import tempfile
import unittest

import e2e_harness as h
from test_e2e_alloc_gap import end, fill_tail, find, sector_bytes, start
from test_e2e_texted import insert_script, numbered, printed_lines

LIMIT = 150000000
DISC_FULL = b"error: F3 disc full"
TEXTS = [b"a" * 80, b"b" * 80]
RECORDS = numbered(TEXTS)
TEXT_SECTORS = -(-(sum(len(r) + 1 for r in RECORDS) + 1) // h.SECTOR_SIZE)


def run(scenario, disc, script):
    """Run the script with A = os.bdd and B = a temp copy of disc; return (output, catalog, image) of B."""
    seen = {}

    def inspect(paths):
        seen["catalog"] = h.read_catalog(paths["b"])
        seen["image"] = h.read_bytes(paths["b"])

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, scenario + ".in.txt")
        with open(path, "wb") as handle:
            handle.write(script)
        out = h.run_session(scenario, path, disks={"a": h.OS_DISK, "b": disc},
                            max_instructions=LIMIT, inspect=inspect)
    return out, seen["catalog"], seen["image"]


class TextedDiscFullTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.disc = os.path.join(self.tmp.name, "utils.bdd")
        shutil.copyfile(h.UTILS_DISK, self.disc)

    def test_save_into_too_small_gap_prints_disc_full_and_keeps_other_files(self):
        tail = 1
        self.assertLess(tail, TEXT_SECTORS)
        fill_tail(self.disc, tail)
        before_catalog = h.read_catalog(self.disc)
        before = h.read_bytes(self.disc)
        gap_first = max(end(e) for e in before_catalog)

        out, catalog, image = run("texted_disc_full", self.disc,
                                  b"b:\ntexted\n" + insert_script(TEXTS) + b"s big.txt\nq\nexit\n")

        h.assert_markers(out, [b"texted>s big.txt", b"saving big.txt...", DISC_FULL, b"Bye!"])
        self.assertEqual(1, out.count(DISC_FULL))
        for old in before_catalog:
            if (old.name, old.ext) == ("DISC", "CAT"):
                continue
            new = [e for e in catalog if (e.name, e.ext) == (old.name, old.ext)]
            self.assertEqual(1, len(new))
            self.assertEqual((start(old), old.length), (start(new[0]), new[0].length))
            for sector in range(start(old), end(old)):
                self.assertEqual(sector_bytes(before, sector), sector_bytes(image, sector))
        for sector in range(h.CAT_FIRST_SECTOR + h.CAT_SECTORS, gap_first):
            self.assertEqual(sector_bytes(before, sector), sector_bytes(image, sector))
        for e in catalog:
            if (e.name, e.ext) == ("BIG", "TXT"):
                self.assertGreaterEqual(start(e), gap_first)
                self.assertLessEqual(end(e), gap_first + tail)

    def test_save_into_reused_gap_loads_back(self):
        gap = h.disc_put(self.disc, "GAP.DAT", bytes((i * 5 + 1) & 0xff or 1
                                                     for i in range(TEXT_SECTORS * h.SECTOR_SIZE)))
        fill_tail(self.disc, 0)
        before_catalog = h.read_catalog(self.disc)
        before = h.read_bytes(self.disc)
        self.assertEqual(TEXT_SECTORS, gap.length)

        script = (b"rm b:gap.dat\nb:\ntexted\n" + insert_script(TEXTS) + b"s big.txt\nq\n"
                  b"texted\nl big.txt\np 0 65535\nq\nexit\n")
        out, catalog, image = run("texted_reuse_gap", self.disc, script)

        self.assertNotIn(b"error", out)
        h.assert_markers(out, [b"%04X lines saved" % len(TEXTS), b"%04X lines loaded" % len(TEXTS),
                               b"Bye!"])
        self.assertEqual(RECORDS, printed_lines(out))
        new = find(catalog, "big.txt")
        self.assertEqual(start(gap), start(new))
        for old in before_catalog:
            if (old.name, old.ext) in (("DISC", "CAT"), ("GAP", "DAT")):
                continue
            kept = find(catalog, "%s.%s" % (old.name, old.ext))
            self.assertEqual((start(old), old.length), (start(kept), kept.length))
            self.assertEqual(before[start(old) * h.SECTOR_SIZE:end(old) * h.SECTOR_SIZE],
                             image[start(old) * h.SECTOR_SIZE:end(old) * h.SECTOR_SIZE])


if __name__ == "__main__":
    unittest.main()
