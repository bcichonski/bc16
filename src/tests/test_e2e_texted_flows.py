"""E2E: TextEd start-up, insert/print/delete, save size and a large load after a restart.

Headless emulator on temp copies of the built os.bdd. Sessions end with `q` then `exit`, like
test_e2e_texted.py. Assertions only: `m` prints addresses that move with the code size.
"""
import re
import unittest

import e2e_harness as h
from test_e2e_texted import (DEBUG_TEXT, insert_script, numbered, printed_lines,
                             run_two_sessions, section)
from test_e2e_texted_commands import run_one

# Typing costs about 0.4 s per inserted line whatever its length, so the large file is made of
# 40 long lines (about 3.4 KB, 27 sectors) instead of a few hundred short ones.
BIG_COUNT = 40


def saved_sectors(records):
    """Sectors bdos records for a saved file: `<number> <text>` + 0x13 each, one 0x00 at the end."""
    size = sum(len(record) + 1 for record in records) + 1
    return -(-size // h.SECTOR_SIZE)


def ls_entry(out, name):
    """The `ls` line of the file `name` (as ls prints it), without the carriage return."""
    for line in out.replace(b"\r", b"").splitlines():
        if line.startswith(name):
            return line
    raise AssertionError("no ls entry for %r" % name)


class TextedFlowTests(unittest.TestCase):
    def assert_no_debug(self, out):
        for text in (b"iowrite",) + DEBUG_TEXT:
            self.assertNotIn(text, out)

    def test_startup_banner(self):
        out = run_one(b"b:\ntexted\nq\nexit\n", "texted_flows_banner")
        h.assert_markers(out, [b"B>texted", b"TextEd v1.2", b"texted>q", b"Bye!"])
        self.assert_no_debug(out)

    def test_insert_print_delete_save_and_list(self):
        texts = [b"alpha", b"bravo", b"charlie", b"delta", b"echo", b"foxtrot"]
        all_lines = numbered(texts)
        remaining = [all_lines[0], all_lines[4], all_lines[5]]
        script = (b"b:\ntexted\n" + insert_script(texts) + b"p 0 65535\nd 20 40\np 0 65535\n"
                  b"s flows.txt\nq\na:\nls b:\nexit\n")
        out = run_one(script, "texted_flows_edit")
        h.assert_markers(out, [b"texted>i 10 10", b"texted>d 20 40", b"3 lines removed",
                               b"flows.txt", b"0003 lines saved", b"Bye!"])
        first = section(out, b"texted>p 0 65535\n", b"texted>").replace(b"\r", b"")
        self.assertEqual(all_lines, first.splitlines())
        after_delete = out.split(b"3 lines removed\n", 1)[1]
        self.assertEqual(remaining, printed_lines(b"texted>p 0 65535\n" + section(
            after_delete, b"texted>p 0 65535\n", b"texted>") + b"texted>"))
        entry = ls_entry(out.split(b"Bye!", 1)[1], b"FLOWS")
        self.assertRegex(entry, rb"^FLOWS\s+\.TXT -RW- %04X " % (
            saved_sectors(remaining) * h.SECTOR_SIZE))
        self.assertEqual(1, saved_sectors(remaining))
        self.assert_no_debug(out)

    def test_large_file_loads_after_restart(self):
        texts = [b"%03d " % i + b"x" * 76 for i in range(BIG_COUNT)]
        records = numbered(texts, 10, 10)
        self.assertGreaterEqual(saved_sectors(records), 4)
        save = b"b:\ntexted\n" + insert_script(texts) + b"s big.txt\nq\na:\nls b:\nexit\n"
        load = (b"b:\ntexted\nl big.txt\nm\np 10 30\nq\nexit\n")
        first, second = run_two_sessions(save, load, "texted_flows_big")
        h.assert_markers(first, [b"%04X lines saved" % BIG_COUNT, b"Bye!"])
        entry = ls_entry(first.split(b"Bye!", 1)[1], b"BIG")
        self.assertRegex(entry, rb"^BIG\s+\.TXT -RW- %04X " % (
            saved_sectors(records) * h.SECTOR_SIZE))
        h.assert_markers(second, [b"texted>l big.txt", b"%04X lines loaded" % BIG_COUNT,
                                  b"total lines: %d" % BIG_COUNT, b"Bye!"])
        self.assertEqual(1, second.count(b"lines loaded"))
        self.assertEqual(records[:3], printed_lines(second.replace(b"p 10 30", b"p 0 65535")))
        self.assertTrue(re.search(rb"total lines: %d\n" % BIG_COUNT, second.replace(b"\r", b"")))
        self.assert_no_debug(first)
        self.assert_no_debug(second)


if __name__ == "__main__":
    unittest.main()
