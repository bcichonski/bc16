"""End-to-end by-hand error paths of the bdos shell (bdio error codes) on the headless emulator."""
import unittest

import e2e_harness as h

# ~10x the measured need (about 2M instructions for a handful of commands).
LIMIT = 50000000
SCENARIO = "bdos_bdio_errors"
MARKERS = [
    b"A>hellowrd",
    b"error: E7 execution not allowed",
    b"A>cat -c test.b",
    b"error: E3 reading not allowed",
    b"A>foo",
    b"error: E0 file not found",
    b"bye!",
]


class BdioErrorPathTests(unittest.TestCase):
    def test_by_hand_error_paths_print_their_messages_in_order(self):
        out = h.run_session(SCENARIO, h.golden_path(SCENARIO, "in"), disks={"a": h.OS_DISK},
                            max_instructions=LIMIT)
        h.assert_markers(out, MARKERS)
        positions = [out.index(marker) for marker in MARKERS]
        self.assertEqual(sorted(positions), positions)


if __name__ == "__main__":
    unittest.main()
