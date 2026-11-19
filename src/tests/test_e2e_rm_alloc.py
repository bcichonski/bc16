"""`rm` then create a file: every other file stays intact (issue #111), on the headless emulator.

Each scenario removes a file in a different position (middle of the disc, last file on the disc,
the file in the last catalog entry), then creates a new file with `cp ls.prg new.prg` (a long file
with other contents, so an overwrite can neither hide in a gap nor write identical bytes) and checks:
  * `cat -c` of the remaining text file prints its original lines (printer output);
  * every remaining file of the built os.bdd has the same sectors on the session image;
  * no two catalog entries share a sector, and the new file starts right after the highest-ending
    other entry (bdio allocates append-only from the end of the used area);
  * the catalog lists the expected files in the expected order (rm moves the last entry into the hole).
Positions are derived from the built os.bdd catalog, never pinned.
"""
import os
import tempfile
import unittest

import e2e_harness as h

# ~10x the measured need (a handful of rm/cp/cat commands).
LIMIT = 150000000
CATALOG_NAME = ("DISC", "CAT")
TEXT_SEP = b"\x13"


def key(name):
    """('NAME', 'EXT') of a 'name.ext' string."""
    base, _, ext = name.upper().partition(".")
    return base, ext


def start(entry):
    return entry.track * h.SECTORS_PER_TRACK + entry.sector


def end(entry):
    return start(entry) + entry.length


def file_bytes(image, entry):
    return image[start(entry) * h.SECTOR_SIZE:end(entry) * h.SECTOR_SIZE]


def text_lines(image, entry):
    """The lines of a text file as `cat -c` prints them (`line !ln`)."""
    data = file_bytes(image, entry).rstrip(b"\x00")
    return [line + b" !ln" for line in data.split(TEXT_SEP) if line]


def model_rm(names, name):
    """Catalog order after `rm name`: the last entry moves into the hole of the removed one."""
    names = list(names)
    index = names.index(key(name))
    last = names.pop()
    if index < len(names):
        names[index] = last
    return names


def model_cp(names, name):
    """Catalog order after `cp x name`: the new file takes the first free entry (the end)."""
    return list(names) + [key(name)]


class RmThenCreateTests(unittest.TestCase):
    """Commands are (verb, arg) pairs: ('rm', 'x.y'), ('cp', 'src.ext dst.ext')."""

    def run_scenario(self, scenario, commands, new_file, text_file):
        original = h.read_catalog(h.OS_DISK)
        original_image = h.read_bytes(h.OS_DISK)
        by_key = {(e.name, e.ext): e for e in original}
        expected_names = [(e.name, e.ext) for e in original]
        lines = []
        for verb, arg in commands:
            lines.append("%s %s" % (verb, arg))
            if verb == "rm":
                expected_names = model_rm(expected_names, arg)
            else:
                expected_names = model_cp(expected_names, arg.split()[1])
        lines += ["cat -c %s" % text_file, "exit"]
        seen = {}

        def inspect(paths):
            seen["catalog"] = h.read_catalog(paths["a"])
            seen["image"] = h.read_bytes(paths["a"])

        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, scenario + ".in.txt")
            with open(script, "w", newline="\n") as handle:
                handle.write("\n".join(lines) + "\n")
            out = h.run_session(scenario, script, disks={"a": h.OS_DISK},
                                max_instructions=LIMIT, inspect=inspect)

        # printer: every command ran, and the remaining text file still holds its original lines
        h.assert_markers(out, [("A>%s" % line).encode("latin-1") for line in lines] + [b"bye!"])
        self.assertNotIn(b"error", out)
        source = by_key.get(key(text_file)) or by_key[("TEST", "B")]
        expected_text = text_lines(original_image, source)
        self.assertTrue(expected_text)
        printed = out.split(("A>cat -c %s" % text_file).encode("latin-1"), 1)[1]
        for line in expected_text:
            self.assertIn(line, printed)

        catalog = seen["catalog"]
        image = seen["image"]
        # catalog: the expected files, in the order rm/cp leave them
        self.assertEqual(expected_names, [(e.name, e.ext) for e in catalog])

        # disc image: files of the built os.bdd are byte-for-byte unchanged
        for entry in catalog:
            name = (entry.name, entry.ext)
            if name in by_key and name != CATALOG_NAME:
                before = by_key[name]
                self.assertEqual((start(before), before.length), (start(entry), entry.length),
                                 "%s.%s moved" % name)
                self.assertEqual(file_bytes(original_image, before), file_bytes(image, entry),
                                 "%s.%s was overwritten" % name)

        # no overlap; the new file is appended after the highest-ending other entry
        ranges = sorted((start(e), end(e), e.name, e.ext) for e in catalog)
        for (_, prev_end, *prev), (next_start, _, *nxt) in zip(ranges, ranges[1:]):
            self.assertLessEqual(prev_end, next_start, "%s overlaps %s" % (prev, nxt))
        new = [e for e in catalog if (e.name, e.ext) == key(new_file)]
        self.assertEqual(1, len(new))
        others_end = max(end(e) for e in catalog if (e.name, e.ext) != key(new_file))
        self.assertEqual(others_end, start(new[0]))
        return out

    def test_rm_middle_file_then_create_keeps_files(self):
        # HELLOWRD.PRG sits in the middle of the disc with its entry in the first catalog sector,
        # so rm moves the last entry (TEST.B) across catalog sectors into its hole.
        names = [(e.name, e.ext) for e in h.read_catalog(h.OS_DISK)]
        entries_per_sector = h.SECTOR_SIZE // h.ENTRY_SIZE
        self.assertLess(names.index(("HELLOWRD", "PRG")), entries_per_sector)
        self.assertGreaterEqual(len(names) - 1, entries_per_sector)
        self.run_scenario("rm_alloc_middle",
                          [("rm", "hellowrd.prg"), ("cp", "ls.prg new.prg")],
                          new_file="new.prg", text_file="test.b")

    def test_rm_last_file_on_disc_then_create_keeps_files(self):
        # A.B is appended last on the disc; rm hellowrd.prg moves A.B into the first catalog
        # sector, so the catalog is no longer in disc order. Then the last file on the disc
        # (A.B, not the last catalog entry) is removed and its space is free again.
        self.run_scenario("rm_alloc_last_on_disc",
                          [("cp", "test.b a.b"), ("rm", "hellowrd.prg"), ("rm", "a.b"),
                           ("cp", "ls.prg new.prg")],
                          new_file="new.prg", text_file="test.b")

    def test_rm_last_catalog_entry_not_last_on_disc_then_create_keeps_files(self):
        # cp adds A.B (last on the disc); rm hellowrd.prg moves A.B into the hole, so the last
        # catalog entry is now an older file that is not the last on the disc. Remove it.
        original = h.read_catalog(h.OS_DISK)
        names = model_rm([(e.name, e.ext) for e in original] + [("A", "B")], "hellowrd.prg")
        last = names[-1]
        last_name = "%s.%s" % last
        self.assertNotEqual(("A", "B"), last)
        text_file = "test.b" if last != ("TEST", "B") else "a.b"
        self.run_scenario("rm_alloc_last_entry",
                          [("cp", "test.b a.b"), ("rm", "hellowrd.prg"), ("rm", last_name.lower()),
                           ("cp", "ls.prg new.prg")],
                          new_file="new.prg", text_file=text_file)


if __name__ == "__main__":
    unittest.main()
