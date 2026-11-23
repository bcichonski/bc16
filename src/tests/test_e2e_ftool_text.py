"""E2E: ftool importtext / exporttext against the real TextEd (headless emulator, temp disc copies).

A host text is imported into a temp copy of utils.bdd (drive B, where texted lives) and loaded by
TextEd; lines typed in TextEd are saved and exported back. Built os.bdd/utils.bdd stay unchanged.
"""
import os
import shutil
import tempfile
import unittest

import e2e_harness as h
import ftool_text
from test_e2e_texted import LIMIT, insert_script, printed_lines

HOST_TEXT = b"first line\n    indented line\n\nlast line\n"
HOST_LINES = [b"first line", b"    indented line", b"", b"last line"]
RECORDS = [b"10 first line", b"20     indented line", b"30  ", b"40 last line"]
TYPED = [b"alpha", b"  beta", b"gamma"]


def run_on_disc(name, disc, script):
    """Run a session with `disc` as drive B; return (printer output, bytes of B after the session)."""
    kept = {}

    def inspect(paths):
        kept["disc"] = h.read_bytes(paths["b"])

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "session.txt")
        with open(path, "wb") as handle:
            handle.write(script)
        out = h.run_session(name, path, disks={"a": h.OS_DISK, "b": disc}, max_instructions=LIMIT,
                            inspect=inspect)
    return out, kept["disc"]


class FtoolTextE2ETests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def path(self, name):
        return os.path.join(self.tmp, name)

    def write(self, name, data):
        with open(self.path(name), "wb") as handle:
            handle.write(data)
        return self.path(name)

    def disc(self):
        copy = self.path("utils.bdd")
        shutil.copyfile(h.UTILS_DISK, copy)
        return copy

    def keep(self, data):
        return self.write("after.bdd", data)

    def test_imported_file_is_loaded_by_texted(self):
        disc = self.disc()
        ftool_text.import_text(disc, self.write("in.txt", HOST_TEXT), "NOTE.TXT")
        out, _ = run_on_disc("ftool_text_import", disc,
                             b"b:\ntexted\nl note.txt\np 0 65535\nq\nexit\n")
        h.assert_markers(out, [b"0004 lines loaded"])
        # The blank line is the one-space text: the printed record is "30" plus separator and
        # the space, which the printer output shows without visible text.
        printed = printed_lines(out)
        self.assertEqual(RECORDS[:2], printed[:2])
        self.assertEqual(RECORDS[3], printed[3])
        self.assertEqual(b"30", printed[2].rstrip(b" "))

    def test_typed_lines_are_exported(self):
        disc = self.disc()
        out, after = run_on_disc("ftool_text_export", disc,
                                 b"b:\ntexted\n" + insert_script(TYPED) + b"s typed.txt\nq\nexit\n")
        h.assert_markers(out, [b"0003 lines saved"])
        after = self.keep(after)
        plain, numbered = self.path("plain.txt"), self.path("numbered.txt")
        ftool_text.export_text(after, "TYPED.TXT", plain)
        ftool_text.export_text(after, "TYPED.TXT", numbered, numbers=True)
        self.assertEqual(b"".join(line + b"\n" for line in TYPED), h.read_bytes(plain))
        self.assertEqual(b"".join(b"%d %s\n" % (10 * (i + 1), line) for i, line in enumerate(TYPED)),
                         h.read_bytes(numbered))

    def test_imported_file_saved_by_texted_exports_to_the_original(self):
        disc = self.disc()
        ftool_text.import_text(disc, self.write("in.txt", HOST_TEXT), "NOTE.TXT")
        out, after = run_on_disc("ftool_text_combined", disc,
                                 b"b:\ntexted\nl note.txt\ns copy.txt\nq\nexit\n")
        h.assert_markers(out, [b"0004 lines loaded", b"0004 lines saved"])
        after = self.keep(after)
        result = self.path("out.txt")
        ftool_text.export_text(after, "COPY.TXT", result)
        self.assertEqual(HOST_TEXT, h.read_bytes(result))
        self.assertEqual(HOST_LINES, h.read_bytes(result).split(b"\n")[:-1])


if __name__ == "__main__":
    unittest.main()
