"""Compile-pattern create/delete cycles do not fill the disc (issue #41, AC 4), on the headless emulator.

A compiler run creates X.TOK, X.IR and X.O, then deletes X.TOK and X.IR; the .O files stay. On a temp
copy of the built os.bdd pre-filled so that append-only allocation would run out within the cycles,
several such cycles (one name prefix each) must all succeed: no `error` in the printer output, every
.O present and byte-identical to its source, no overlapping extents, every original file and sectors
0..191 unchanged. The files are `cp` copies of existing programs (.TOK biggest, .O smallest).
Positions are derived from the built disc, never pinned.
"""
import os
import shutil
import tempfile
import unittest

import e2e_harness as h
from test_e2e_alloc_gap import (ALLOC_FIRST, DISC_END, assert_no_overlap, end, fill_tail, find,
                                sector_bytes, start)

# ~10x the measured need (3 cp + 2 rm per cycle; the cp of the biggest file is the bulk).
LIMIT = 300000000
PREFIXES = "ABCDE"
SOURCES = {"TOK": "cat.prg", "IR": "cha.prg", "O": "test.b"}
FREE = 150                    # sectors left after pre-filling the allocatable area


def commands():
    lines = []
    for prefix in PREFIXES:
        for ext in ("TOK", "IR", "O"):
            lines.append("cp %s %s.%s" % (SOURCES[ext], prefix, ext.lower()))
        lines += ["rm -f %s.tok" % prefix, "rm -f %s.ir" % prefix]
    return lines


class CompileCycleTests(unittest.TestCase):
    def test_cycles_reuse_freed_space_and_never_fill_the_disc(self):
        with tempfile.TemporaryDirectory() as tmp:
            disc = os.path.join(tmp, "os.bdd")
            shutil.copyfile(h.OS_DISK, disc)
            original = h.read_catalog(disc)
            sizes = {ext: find(original, name).length for ext, name in SOURCES.items()}
            self.assertGreater(sizes["TOK"], sizes["IR"])
            self.assertGreater(sizes["IR"], sizes["O"])
            fill_tail(disc, FREE)
            before_catalog = h.read_catalog(disc)
            before = h.read_bytes(disc)
            self.assertLessEqual(len(before_catalog) + 3, 248)

            # append-only allocation needs every created file (nothing is ever reused) ...
            append_only = len(PREFIXES) * sum(sizes.values())
            self.assertGreater(append_only, FREE)
            # ... while with reuse only the .O files plus one cycle's live files must fit.
            self.assertLessEqual(len(PREFIXES) * sizes["O"] + sizes["TOK"] + sizes["IR"], FREE)

            lines = commands()
            for line in lines:
                self.assertLessEqual(len(line), 45)
            script = os.path.join(tmp, "cycles.in.txt")
            with open(script, "w", newline="\n") as handle:
                handle.write("\n".join(lines + ["exit"]) + "\n")
            seen = {}

            def inspect(paths):
                seen["catalog"] = h.read_catalog(paths["a"])
                seen["image"] = h.read_bytes(paths["a"])

            out = h.run_session("compile_cycles", script, disks={"a": disc},
                                max_instructions=LIMIT, inspect=inspect)
            catalog, image = seen["catalog"], seen["image"]

        h.assert_markers(out, [("A>%s" % c).encode("latin-1") for c in lines] + [b"bye!"])
        self.assertNotIn(b"error", out)

        names = [(e.name, e.ext) for e in catalog]
        self.assertEqual(len(names), len(set(names)))
        for prefix in PREFIXES:
            self.assertNotIn((prefix, "TOK"), names)
            self.assertNotIn((prefix, "IR"), names)
            new = find(catalog, "%s.o" % prefix)
            source = find(before_catalog, SOURCES["O"])
            self.assertEqual(source.length, new.length)
            self.assertEqual(before[start(source) * 128:end(source) * 128],
                             image[start(new) * 128:end(new) * 128], "%s.O differs" % prefix)
            self.assertGreaterEqual(start(new), ALLOC_FIRST)
            self.assertLessEqual(end(new), DISC_END)
        assert_no_overlap(self, catalog)

        # every file of the pre-filled disc is unchanged, and so are sectors 0..191
        for old in before_catalog:
            if (old.name, old.ext) == ("DISC", "CAT"):
                continue
            new = find(catalog, "%s.%s" % (old.name, old.ext))
            self.assertEqual((start(old), old.length), (start(new), new.length))
            self.assertEqual(before[start(old) * 128:end(old) * 128],
                             image[start(new) * 128:end(new) * 128])
        for sector in range(ALLOC_FIRST):
            if h.CAT_FIRST_SECTOR <= sector < h.CAT_FIRST_SECTOR + h.CAT_SECTORS:
                continue
            self.assertEqual(sector_bytes(before, sector), sector_bytes(image, sector),
                             "sector %d changed" % sector)


if __name__ == "__main__":
    unittest.main()
