"""E2E: TextEd save -> restart -> load on the headless emulator (built os.bdd, temp copies only).

Session 1 writes a file with texted and exits; its disc image is copied out and used as the disc
of session 2, a fresh boot, which loads the file again (#47).
"""
import os
import re
import shutil
import tempfile
import unittest

import e2e_harness as h

LIMIT = 100000000
SCENARIO_OWNER = "texted_roundtrip"
OWNER_LINES = [b"10 first line", b"20 second line", b"30 third line"]
# Lines of exactly 80 characters (the longest `i` accepts), distinct, plus short ones; the saved
# file spans several 128-byte sectors and records cross sector boundaries.
LINE80_A = (b"ABCDEFGHIJ" * 8)
LINE80_B = (b"0123456789" * 8)
LINE80_C = (b"klmnopqrst" * 8)
LONG_LINES = [b"short one", LINE80_A, b"x", LINE80_B, b"another short line", LINE80_C,
              b"the end"]
WRAP = re.compile(rb" !catln\d+\n")
DEBUG_TEXT = (b"read md:", b"Pb:")


def insert_script(lines, first=10, step=10):
    """texted `i` command with the given lines; an empty line ends the insert."""
    return b"i %d %d\n" % (first, step) + b"".join(line + b"\n" for line in lines) + b"\n"


def numbered(lines, first=10, step=10):
    return [b"%d %s" % (first + i * step, line) for i, line in enumerate(lines)]


def run_two_sessions(save_script, load_script, name):
    """Run save_script, then load_script on the very same disc (a restart); return both outputs."""
    kept = {}

    def inspect(paths):
        kept["disc"] = os.path.join(kept["tmp"], "restart.bdd")
        shutil.copyfile(paths["a"], kept["disc"])

    with tempfile.TemporaryDirectory() as tmp:
        kept["tmp"] = tmp
        scripts = []
        for index, text in enumerate((save_script, load_script)):
            path = os.path.join(tmp, "session%d.txt" % index)
            with open(path, "wb") as handle:
                handle.write(text)
            scripts.append(path)
        first = h.run_session(name + "_save", scripts[0], disks={"a": h.OS_DISK},
                              max_instructions=LIMIT, inspect=inspect)
        second = h.run_session(name + "_load", scripts[1], disks={"a": kept["disc"]},
                               max_instructions=LIMIT)
    return first, second


def section(out, start, end):
    """The bytes after the first `start` up to the next `end` (the prompt of the next command)."""
    return out.split(start, 1)[1].split(end, 1)[0]


def printed_lines(out):
    """The output of `p 0 65535` as a list of lines."""
    return section(out, b"texted>p 0 65535\n", b"texted>").replace(b"\r", b"").splitlines()


def cat_records(out, marker=b"A>cat -c "):
    """Text records of a `cat -c` output: wrap markers and line breaks removed, split at ` !ln`.

    Returns (records, tail); tail is whatever follows the last record (the sector's zero padding).
    """
    body = out.replace(b"\r", b"").split(marker, 1)[1].split(b"\nA>", 1)[0]
    body = body.split(b"printing ", 1)[1].split(b"\n", 1)[1]
    body = WRAP.sub(b"", body).replace(b"\n", b"")
    parts = body.split(b" !ln")
    return parts[:-1], parts[-1]


class TextedRoundTripTests(unittest.TestCase):
    def assert_no_debug(self, out):
        for text in DEBUG_TEXT:
            self.assertNotIn(text, out)

    def test_save_restart_load_prints_same_lines(self):
        save = b"texted\n" + insert_script([b"first line", b"second line", b"third line"]) + \
            b"s note.txt\nq\nexit\n"
        load = b"texted\nl note.txt\np 0 65535\nq\nexit\n"
        first, second = run_two_sessions(save, load, SCENARIO_OWNER)
        h.assert_markers(first, [b"texted>s note.txt", b"0003 lines saved", b"Bye!"])
        h.check_golden(h.golden_path(SCENARIO_OWNER), second,
                       markers=[b"texted>l note.txt", b"0003 lines loaded"] + OWNER_LINES,
                       scenario=SCENARIO_OWNER)
        self.assertEqual(OWNER_LINES, printed_lines(second))
        self.assert_no_debug(first)
        self.assert_no_debug(second)

    def test_file_over_one_sector_with_80_character_lines(self):
        expected = numbered(LONG_LINES)
        self.assertGreater(sum(len(line) + 1 for line in expected), 2 * h.SECTOR_SIZE)
        save = b"texted\n" + insert_script(LONG_LINES) + b"s long.txt\nq\nexit\n"
        load = b"texted\nl long.txt\np 0 65535\nq\nexit\n"
        first, second = run_two_sessions(save, load, "texted_long")
        h.assert_markers(first, [b"%04d lines saved" % len(LONG_LINES)])
        h.assert_markers(second, [b"%04d lines loaded" % len(LONG_LINES)])
        self.assertEqual(expected, printed_lines(second))
        self.assert_no_debug(second)

    def test_missing_file_prints_error_and_keeps_buffer(self):
        save = b"texted\n" + insert_script([b"first line", b"second line", b"third line"]) + \
            b"s note.txt\nq\nexit\n"
        load = b"texted\nl note.txt\np 0 65535\nl missing.txt\np 0 65535\nq\nexit\n"
        _, second = run_two_sessions(save, load, "texted_missing")
        h.assert_markers(second, [b"texted>l missing.txt", b"error: E0 file not found"])
        self.assertEqual(1, second.count(b"error: E0 file not found"))
        self.assertEqual(1, second.count(b"lines loaded"))
        after_error = second.split(b"texted>l missing.txt\n", 1)[1]
        after = section(after_error, b"texted>p 0 65535\n", b"texted>").replace(b"\r", b"")
        self.assertEqual(OWNER_LINES, after.splitlines())

    def test_load_replaces_a_non_empty_buffer(self):
        save = b"texted\n" + insert_script([b"first line", b"second line", b"third line"]) + \
            b"s note.txt\nq\nexit\n"
        # Lines 5 and 20 exist before the load: 5 is not in the file, 20 would be overwritten.
        load = (b"texted\ni 5 15\nold five\nold twenty\nold thirty-five\nold fifty\n\n"
                b"p 0 65535\nl note.txt\np 0 65535\nq\nexit\n")
        _, second = run_two_sessions(save, load, "texted_replace")
        before = section(second, b"texted>p 0 65535\n", b"texted>l note.txt").replace(b"\r", b"")
        h.assert_markers(before, [b"5 old five", b"20 old twenty", b"35 old thirty-five",
                                  b"50 old fifty"])
        loaded = second.split(b"lines loaded\n", 1)[1]
        after = section(loaded, b"texted>p 0 65535\n", b"texted>").replace(b"\r", b"")
        self.assertEqual(OWNER_LINES, after.splitlines())
        self.assertNotIn(b"old", after)

    def test_cat_c_shows_saved_records_whole(self):
        expected = numbered(LONG_LINES)
        offset = 0
        crossing = 0
        for record in expected:
            end = offset + len(record) + 1
            crossing += offset // h.SECTOR_SIZE != (end - 1) // h.SECTOR_SIZE
            offset = end
        self.assertGreaterEqual(crossing, 2, "the file must have records across sector boundaries")
        save = b"texted\n" + insert_script(LONG_LINES) + b"s long.txt\nq\nexit\n"
        load = b"cat -c long.txt\nexit\n"
        _, second = run_two_sessions(save, load, "texted_cat")
        h.assert_markers(second, [b"A>cat -c long.txt", b"printing A:LONG    TXT"])
        records, tail = cat_records(second)
        self.assertEqual(expected, records)
        for record in records:
            self.assertNotIn(b"#00", record)
        # After the last record only the zero padding of its sector follows.
        self.assertEqual(b"", tail.replace(b"#00", b""))
        self.assert_no_debug(second)


if __name__ == "__main__":
    unittest.main()
