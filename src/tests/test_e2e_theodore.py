"""E2E: THEODORE.PRG v1.1 on the utilities disc (run from B) (listing, catalog entry, seeded game, quit paths)."""
import os
import unittest

import e2e_harness as h

LIMIT = 50000000
SEED = 1          # secret stop 40 with this seed (found by a spike run)
OTHER_SEED = 2    # secret stop 14
SECTORS = os.path.join(h.SRC, "bdos", "theodore.sectors")


def run(scenario, seed=SEED, inspect=None):
    return h.run_session(scenario, h.golden_path(scenario, "in"), disks={"a": h.OS_DISK, "b": h.UTILS_DISK},
                         max_instructions=LIMIT, inspect=inspect, seed=seed)


def sector_count():
    return -(-os.path.getsize(SECTORS) // h.SECTOR_SIZE)


class TheodoreTests(unittest.TestCase):
    def test_catalog_entry_and_ls(self):
        self.assertEqual(os.path.getsize(SECTORS) > 0, True)
        count = sector_count()
        entries = [e for e in h.read_catalog(h.UTILS_DISK) if (e.name, e.ext) == ("THEODORE", "PRG")]
        self.assertEqual(1, len(entries))
        entry = entries[0]
        self.assertEqual(h.ATTR_RX, entry.attributes & (h.ATTR_R | h.ATTR_X))
        planned = h.planned_entry("THEODORE.PRG", h.UTILS_MANIFEST)
        self.assertEqual((planned.track, planned.sector, count), (entry.track, entry.sector, entry.length))

    def test_ls_lists_theodore(self):
        out = h.run_session("theodore_ls", h.golden_path("theodore_ls", "in"),
                            disks={"a": h.OS_DISK, "b": h.UTILS_DISK}, max_instructions=LIMIT)
        line = h.ls_line(h.planned_entry("THEODORE.PRG", h.UTILS_MANIFEST)).encode("latin-1")
        h.assert_markers(out, [b"A>ls b:", line])

    def test_seeded_game_north_south_found_bye(self):
        out = run("theodore_win")
        self.assertNotIn(b"What time", out)
        h.assert_markers(out, [b"B>theodore", b"Looking for uncle Theodore v1.1",
                               b"Type train stop number (0..99) or 100 to quit: ",
                               b"Uncle Theodore went south.", b"Uncle Theodore went north.",
                               b"Yes! You have found uncle Theodore!", b"Bye!", b"B>exit"])

    def test_quit_with_100(self):
        out = run("theodore_quit")
        h.assert_markers(out, [b"B>theodore", b"Bye!", b"B>exit"])
        self.assertNotIn(b"went", out)

    def test_value_over_255_also_quits(self):
        out = run("theodore_big")
        h.assert_markers(out, [b"B>theodore", b"Bye!", b"B>exit"])
        self.assertNotIn(b"went", out)
        self.assertNotIn(b"Yes!", out)

    def test_different_seeds_give_different_secret_stops(self):
        first = run("theodore_win", SEED)
        second = run("theodore_seed2", OTHER_SEED)
        h.assert_markers(first, [b"Yes! You have found uncle Theodore!"])
        # secret 14 for the other seed: 49 is south, 24 is south, 14 is the hit
        self.assertEqual(2, second.count(b"went south"))
        self.assertNotIn(b"went north", second)
        h.assert_markers(second, [b"Yes! You have found uncle Theodore!", b"Bye!"])


if __name__ == "__main__":
    unittest.main()
