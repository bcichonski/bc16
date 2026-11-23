"""E2E: bDOS tools run with a missing argument and leave both discs untouched (headless emulator).

Contract of `strnextword`: it never returns 0. At the end of the line it returns the address of
the terminating NUL, so a tool detects a missing argument by an empty word, not by a null pointer.
Each tool below is run without its argument(s) and must report the same error as before.

`format` without a drive is deliberately NOT tested: a missing drive makes it wipe drive A.
That is a pre-existing bug (plan D-3 of issue 82), out of scope and not pinned here.
"""
import os
import tempfile
import unittest

import e2e_harness as h

LIMIT = 200000000
NOT_FOUND = b"error: E0 file not found"


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


class BdosMissingArgumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        keys = (b"ls\ncp\ncp test.b\nrm\nrm -f\ncha\ncha +r\ncat\ncat -c\nls\nexit\n")
        cls.checked = {}

        def inspect(paths):
            cls.checked["a"] = read(paths["a"]) == read(h.OS_DISK)
            cls.checked["b"] = read(paths["b"]) == read(h.UTILS_DISK)

        with tempfile.TemporaryDirectory() as tmp:
            session = os.path.join(tmp, "session.txt")
            with open(session, "wb") as handle:
                handle.write(keys)
            cls.out = h.run_session("bdos_args", session, disks={"a": h.OS_DISK, "b": h.UTILS_DISK},
                                    max_instructions=LIMIT, inspect=inspect)

    def after(self, command, until):
        """Output between the echoed command line and the next prompt/command."""
        start = self.out.index(b"A>" + command + b"\n") + len(command) + 3
        return self.out[start:self.out.index(until, start)]

    def test_ls_without_argument_lists_current_drive(self):
        part = self.after(b"ls", b"A>cp\n")
        h.assert_markers(part, [b"listing files of drive A:", b"catalog entries free"])

    def test_cp_missing_arguments(self):
        self.assertIn(NOT_FOUND, self.after(b"cp", b"A>cp test.b\n"))
        self.assertIn(NOT_FOUND, self.after(b"cp test.b", b"A>rm\n"))

    def test_rm_missing_arguments(self):
        self.assertIn(NOT_FOUND, self.after(b"rm", b"A>rm -f\n"))
        self.assertIn(NOT_FOUND, self.after(b"rm -f", b"A>cha\n"))

    def test_cha_missing_arguments(self):
        self.assertIn(NOT_FOUND, self.after(b"cha", b"A>cha +r\n"))
        self.assertIn(NOT_FOUND, self.after(b"cha +r", b"A>cat\n"))

    def test_cat_missing_arguments(self):
        part = self.after(b"cat", b"A>cat -c\n")
        h.assert_markers(part, [b"error: unknown switch", NOT_FOUND])
        self.assertLess(part.index(b"unknown switch"), part.index(NOT_FOUND))
        self.assertIn(NOT_FOUND, self.after(b"cat -c", b"A>ls\n"))

    def test_discs_unchanged_and_ls_still_works(self):
        self.assertEqual({"a": True, "b": True}, self.checked)
        tail = self.out.rsplit(b"A>ls\n", 1)[1]
        h.assert_markers(tail, [b"listing files of drive A:", b"HELLOWRD.PRG"])


if __name__ == "__main__":
    unittest.main()
