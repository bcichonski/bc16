"""E2E: TextEd rejects missing or bad command arguments (headless emulator, built os.bdd copy).

`strnextword` never returns 0 (it points at the terminating NUL), so TextEd treats an empty word
as a missing argument. Each session ends with `q`, then `exit`, like test_e2e_texted.py.
"""
import os
import tempfile
import unittest

import e2e_harness as h
from test_e2e_texted import LIMIT, OWNER_LINES, insert_script, printed_lines, section

NEED_FILE = b"Error. Expected argument <file>."
NEED_N = b"Error. Expected argument <n>."
NEED_S = b"Error. Expected argument <s>."
TOO_LONG = b"Error. <file> too long."
BUFFER = [b"first line", b"second line", b"third line"]


def run_one(script, name):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "session.txt")
        with open(path, "wb") as handle:
            handle.write(script)
        return h.run_session(name, path, disks={"a": h.OS_DISK, "b": h.UTILS_DISK}, max_instructions=LIMIT)


def lines_between(out, start, end):
    return section(out, start, end).replace(b"\r", b"").splitlines()


class TextedArgumentTests(unittest.TestCase):
    def test_save_without_name_creates_nothing(self):
        out = run_one(b"ls b:\nb:\ntexted\ns\nq\na:\nls b:\nexit\n", "texted_args_save")
        h.assert_markers(out, [b"texted>s", NEED_FILE, b"Bye!"])
        self.assertNotIn(b"saving", out)
        before = lines_between(out, b"A>ls b:\n", b"A>b:")
        after = lines_between(out.split(b"Bye!", 1)[1], b"A>ls b:\n", b"A>exit")
        self.assertTrue(before)
        self.assertEqual(before, after)

    def test_load_without_name_keeps_buffer(self):
        out = run_one(b"b:\ntexted\n" + insert_script(BUFFER) + b"l\np 0 65535\nq\nexit\n",
                      "texted_args_load")
        h.assert_markers(out, [b"texted>l", NEED_FILE])
        self.assertNotIn(b"loading", out)
        after = out.split(b"texted>l\n", 1)[1]
        self.assertEqual(OWNER_LINES, lines_between(after, b"texted>p 0 65535\n", b"texted>"))

    def test_name_longer_than_twelve_characters(self):
        out = run_one(b"b:\ntexted\ns abcdefghijklmnop.txt\nl abcdefghijklmnop.txt\nq\nexit\n",
                      "texted_args_long")
        self.assertEqual(2, out.count(TOO_LONG))
        self.assertNotIn(b"saving", out)
        self.assertNotIn(b"loading", out)

    def test_insert_print_delete_with_missing_numbers(self):
        script = b"b:\ntexted\n" + insert_script(BUFFER) + (
            b"i\ni 5\np\np 10\nd\nd 10\np 0 65535\nq\nexit\n")
        out = run_one(script, "texted_args_numbers")
        after = out.split(b"texted>i\n", 1)[1]
        self.assertEqual(3, after.count(NEED_N), "i, p and d without numbers")
        self.assertEqual(3, after.count(NEED_S), "i 5, p 10 and d 10: one number only")
        self.assertNotIn(b"lines removed", after)
        self.assertEqual(OWNER_LINES, printed_lines(out))


if __name__ == "__main__":
    unittest.main()
