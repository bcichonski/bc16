"""bdio allocates a new file in the largest free gap of 12/0..63/15 (issue #41), on the headless emulator.

Scenarios on temp copies of the built os.bdd, pre-filled with `e2e_harness.disc_put` so the tail of
the disc is small:
  * reuse: `rm hellowrd.prg`, then `cp` a smaller file: it starts where HELLOWRD.PRG was;
  * outgrow: `cp` a file bigger than the largest gap: `disc full`, the new file keeps the sectors
    of its gap that fit, nothing outside the gap changes;
  * reserved: removing BDOS.SYS (or the boot/catalog entries) never lets bdio allocate in 0..191;
  * ls: the free figure is 832 minus the used sectors of the allocatable area (gaps count).
Positions are derived from the built disc, never pinned.
"""
import os
import re
import shutil
import tempfile
import unittest

import e2e_harness as h

# ~10x the measured need (a few rm/cp/ls commands; cp of a long file is the bulk).
LIMIT = 150000000
ALLOC_FIRST = 192             # 12/0: first sector after the BDOS range 2/0..11/15
DISC_END = h.TRACKS * h.SECTORS_PER_TRACK
ALLOC_SECTORS = DISC_END - ALLOC_FIRST
CAT_FIRST = h.CAT_FIRST_SECTOR
CAT_END = CAT_FIRST + h.CAT_SECTORS
DISC_FULL = b"error: F3 disc full"
FREE_LINE = re.compile(rb"([0-9A-F]{2}) catalog entries free; ([0-9A-F]{4}) sectors free\.\.\.")


def start(entry):
    return entry.track * h.SECTORS_PER_TRACK + entry.sector


def end(entry):
    return start(entry) + entry.length


def key(name):
    base, _, ext = name.upper().partition(".")
    return base, ext


def find(catalog, name):
    found = [e for e in catalog if (e.name, e.ext) == key(name)]
    if len(found) != 1:
        raise AssertionError("%s found %d times in the catalog" % (name, len(found)))
    return found[0]


def sector_bytes(image, sector):
    return image[sector * h.SECTOR_SIZE:(sector + 1) * h.SECTOR_SIZE]


def fill_tail(path, leave):
    """Pre-fill the tail of a temp disc with FILLnn.DAT files so that `leave` sectors stay free.

    Each fill file gets distinct contents. Returns the names of the fill files.
    """
    names = []
    while True:
        used_end = max(end(e) for e in h.read_catalog(path))
        free = DISC_END - used_end - leave
        if free <= 0:
            break
        count = min(free, 200)
        name = "FILL%02d.DAT" % len(names)
        data = bytes((len(names) * 37 + i) & 0xff or 1 for i in range(count * h.SECTOR_SIZE))
        h.disc_put(path, name, data)
        names.append(name)
    assert DISC_END - max(end(e) for e in h.read_catalog(path)) == leave
    return names


def assert_no_overlap(test, catalog):
    ranges = sorted((start(e), end(e), e.name, e.ext) for e in catalog)
    for (_, prev_end, *prev), (next_start, _, *nxt) in zip(ranges, ranges[1:]):
        test.assertLessEqual(prev_end, next_start, "%s overlaps %s" % (prev, nxt))


def run(scenario, disc, commands):
    """Run commands on a temp copy of disc; return (printer output, catalog, image) after the session."""
    seen = {}

    def inspect(paths):
        seen["catalog"] = h.read_catalog(paths["a"])
        seen["image"] = h.read_bytes(paths["a"])

    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, scenario + ".in.txt")
        with open(script, "w", newline="\n") as handle:
            handle.write("\n".join(list(commands) + ["exit"]) + "\n")
        out = h.run_session(scenario, script, disks={"a": disc}, max_instructions=LIMIT,
                            inspect=inspect)
    h.assert_markers(out, [("A>%s" % c).encode("latin-1") for c in commands] + [b"bye!"])
    return out, seen["catalog"], seen["image"]


class AllocGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.disc = os.path.join(self.tmp.name, "os.bdd")
        shutil.copyfile(h.OS_DISK, self.disc)

    def assert_unchanged_outside(self, before, after, keep):
        """Every sector outside the catalog and outside the range keep=(first, end) is unchanged."""
        for sector in range(DISC_END):
            if CAT_FIRST <= sector < CAT_END or keep[0] <= sector < keep[1]:
                continue
            self.assertEqual(sector_bytes(before, sector), sector_bytes(after, sector),
                             "sector %d changed" % sector)

    def assert_files_unchanged(self, before_catalog, before_image, catalog, image, skip=()):
        for old in before_catalog:
            name = (old.name, old.ext)
            if name == ("DISC", "CAT") or name in skip:
                continue
            new = [e for e in catalog if (e.name, e.ext) == name]
            self.assertEqual(1, len(new), "%s.%s missing" % name)
            self.assertEqual((start(old), old.length), (start(new[0]), new[0].length),
                             "%s.%s moved" % name)
            self.assertEqual(before_image[start(old) * h.SECTOR_SIZE:end(old) * h.SECTOR_SIZE],
                             image[start(old) * h.SECTOR_SIZE:end(old) * h.SECTOR_SIZE],
                             "%s.%s changed" % name)

    def test_rm_then_smaller_file_reuses_freed_gap(self):
        hello = find(h.read_catalog(self.disc), "hellowrd.prg")
        source_sectors = hello.length - 1
        source = h.disc_put(self.disc, "SRC.DAT",
                            bytes((i * 7 + 3) & 0xff for i in range(source_sectors * h.SECTOR_SIZE)))
        tail = source_sectors - 1
        self.assertLess(tail, source.length)
        self.assertLess(source.length, hello.length)
        fill_tail(self.disc, tail)
        before_catalog = h.read_catalog(self.disc)
        before = h.read_bytes(self.disc)

        out, catalog, image = run("alloc_gap_reuse", self.disc,
                                  ["rm hellowrd.prg", "cp src.dat new.dat"])

        self.assertNotIn(b"error", out)
        new = find(catalog, "new.dat")
        self.assertEqual(start(hello), start(new))
        self.assertEqual(source.length, new.length)
        self.assertEqual(before[start(source) * 128:end(source) * 128],
                         image[start(new) * 128:end(new) * 128])
        assert_no_overlap(self, catalog)
        self.assert_files_unchanged(before_catalog, before, catalog, image,
                                    skip=[("HELLOWRD", "PRG")])
        self.assert_unchanged_outside(before, image, (start(new), end(new)))

    def test_file_bigger_than_largest_gap_stops_with_disc_full(self):
        hello = find(h.read_catalog(self.disc), "hellowrd.prg")
        big = find(h.read_catalog(self.disc), "cp.prg")
        tail = 3
        self.assertGreater(big.length, hello.length)
        fill_tail(self.disc, tail)
        before_catalog = h.read_catalog(self.disc)
        before = h.read_bytes(self.disc)

        out, catalog, image = run("alloc_gap_outgrow", self.disc,
                                  ["rm hellowrd.prg", "cp cp.prg new.prg"])

        self.assertIn(DISC_FULL, out)
        gap = (start(hello), end(hello))
        new = find(catalog, "new.prg")
        # the new file keeps the sectors of its gap that fit, never more
        self.assertEqual(gap, (start(new), end(new)))
        self.assertEqual(before[start(big) * 128:(start(big) + new.length) * 128],
                         image[start(new) * 128:end(new) * 128])
        assert_no_overlap(self, catalog)
        self.assert_files_unchanged(before_catalog, before, catalog, image,
                                    skip=[("HELLOWRD", "PRG")])
        self.assert_unchanged_outside(before, image, gap)

    def test_full_allocatable_area_with_reserved_entries_removed_is_disc_full(self):
        fill_tail(self.disc, 0)
        before = h.read_bytes(self.disc)
        before_catalog = h.read_catalog(self.disc)

        out, catalog, image = run("alloc_gap_reserved_full", self.disc,
                                  ["rm -f bdos.sys", "rm -f bootsect.bin", "cp test.b x.b"])

        self.assertIn(DISC_FULL, out)
        self.assertNotIn(("X", "B"), [(e.name, e.ext) for e in catalog])
        self.assert_unchanged_outside(before, image, (0, 0))
        self.assert_files_unchanged(before_catalog, before, catalog, image,
                                    skip=[("BDOS", "SYS"), ("BOOTSECT", "BIN")])

    def test_removed_bdos_sys_is_never_reused(self):
        tail = 3
        fill_tail(self.disc, tail)
        before = h.read_bytes(self.disc)
        test_b = find(h.read_catalog(self.disc), "test.b")
        self.assertLessEqual(test_b.length, tail)

        out, catalog, image = run("alloc_gap_reserved_tail", self.disc,
                                  ["rm -f bdos.sys", "cp test.b x.b"])

        self.assertNotIn(b"error", out)
        new = find(catalog, "x.b")
        self.assertEqual(DISC_END - tail, start(new))
        self.assertGreaterEqual(start(new), ALLOC_FIRST)
        self.assert_unchanged_outside(before, image, (start(new), end(new)))

    def test_ls_counts_free_sectors_of_middle_gaps(self):
        fill_tail(self.disc, 5)
        out, catalog, _ = run("alloc_gap_ls", self.disc, ["rm hellowrd.prg", "rm rm.prg", "ls"])
        used = sum(max(0, min(end(e), DISC_END) - max(start(e), ALLOC_FIRST)) for e in catalog)
        printed = out.split(b"A>ls", 1)[1]
        match = FREE_LINE.search(printed)
        self.assertIsNotNone(match, h._tail(out))
        self.assertEqual(ALLOC_SECTORS - used, int(match.group(2), 16))
        # the gaps left by rm are in the middle, so the figure is more than the free tail
        self.assertGreater(ALLOC_SECTORS - used, 5)


if __name__ == "__main__":
    unittest.main()
