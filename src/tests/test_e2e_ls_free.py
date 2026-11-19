"""`ls` free-sector figure on the headless emulator: derived from the disc layout, not pinned.

The printer line `XX catalog entries free; HHHH sectors free...` is read unmasked. The expected
figure is 1024 minus the end (track * 16 + sector + length) of the highest used catalog entry.
"""
import os
import re
import shutil
import tempfile
import unittest

import e2e_harness as h

# ~10x the measured need (about 2M instructions for a handful of commands).
LIMIT = 50000000
TOTAL_SECTORS = h.TRACKS * h.SECTORS_PER_TRACK
FREE_LINE = re.compile(rb"([0-9A-F]{2}) catalog entries free; ([0-9A-F]{4}) sectors free\.\.\.")
GROWN_DATA = b"x" * 300  # 300 bytes = 3 sectors of 128 bytes


def planned_free(entries):
    """Free sectors derived from planned entries: 1024 minus the end of the highest one."""
    end = max(e.track * h.SECTORS_PER_TRACK + e.sector + e.length for e in entries)
    return TOTAL_SECTORS - end


def run_ls(disk_path):
    """Run `ls` on a temp copy of disk_path; return the printed free-sector figure (an int)."""
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "ls_free.in.txt")
        with open(script, "w", newline="\n") as handle:
            handle.write("ls\nexit\n")
        out = h.run_session("ls_free", script, disks={"a": disk_path}, max_instructions=LIMIT)
    h.assert_markers(out, [b"A>ls", b"catalog entries free", b"bye!"])
    match = FREE_LINE.search(out)
    if match is None:
        raise AssertionError("no free-sector line in output:\n%s" % h._tail(out))
    return int(match.group(2), 16)


class LsFreeSectorsTests(unittest.TestCase):
    def test_built_os_disc_free_sectors_match_layout(self):
        expected = planned_free(h.planned_entries())
        self.assertGreater(expected, 0)
        self.assertEqual(expected, run_ls(h.OS_DISK))

    def test_grown_disc_free_sectors_drop_by_added_length(self):
        base = planned_free(h.planned_entries())
        with tempfile.TemporaryDirectory() as tmp:
            grown = os.path.join(tmp, "grown.bdd")
            shutil.copyfile(h.OS_DISK, grown)
            added = h.disc_put(grown, "GROW.TXT", GROWN_DATA)
            # the used area ends at the highest planned entry or at the added file, whichever is later
            end = max(added.track * h.SECTORS_PER_TRACK + added.sector + added.length,
                      max(e.track * h.SECTORS_PER_TRACK + e.sector + e.length
                          for e in h.planned_entries()))
            expected = TOTAL_SECTORS - end
            self.assertEqual(base - added.length, expected)
            self.assertEqual(expected, run_ls(grown))


if __name__ == "__main__":
    unittest.main()
