"""The utilities disc (src/utils.bddmanifest -> utils.bdd): structure, reproducibility, a solo boot."""
import os
import subprocess
import tempfile
import unittest

import e2e_harness as h
import ftool_mkdisc as mk
from tests.test_e2e_disc import _catalog_rows, check_disc_structure

SECTOR = h.SECTOR_SIZE
LIMIT = 50000000
FTOOL = os.path.join(h.SRC, "ftool")


def _bytes_of(image, name):
    """The on-disc byte range of the catalog entry called name (8+3 field, e.g. b"BDOS    SYS")."""
    row = [r for r in _catalog_rows(image) if r[5] == name][0]
    start = (row[1] * h.SECTORS_PER_TRACK + row[2]) * SECTOR
    return image[start:start + row[3] * SECTOR]


class UtilsDiscStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.planned = mk.plan_disc(h.UTILS_MANIFEST)
        cls.image = h.read_bytes(h.UTILS_DISK)

    def test_utils_bdd_matches_manifest(self):
        check_disc_structure(self.image, self.planned)

    def test_catalog_is_exactly_boot_catalog_system_texted_calc_hellowrd_theodore(self):
        names = [r[5] for r in _catalog_rows(self.image)]
        self.assertEqual([b"BOOTSECTBIN", b"DISC    CAT", b"BDOS    SYS", b"TEXTED  PRG", b"CALC    PRG",
                          b"HELLOWRDPRG", b"THEODOREPRG"], names)

    def test_texted_is_read_execute_and_not_system(self):
        row = [r for r in _catalog_rows(self.image) if r[5] == b"TEXTED  PRG"][0]
        self.assertTrue(row[4] & mk.ATTRIBUTES["R"])
        self.assertTrue(row[4] & mk.ATTRIBUTES["X"])
        self.assertFalse(row[4] & mk.ATTRIBUTES["S"])

    def test_boot_sector_and_system_bytes_equal_those_of_os_bdd(self):
        os_image = h.read_bytes(h.OS_DISK)
        for name in (b"BOOTSECTBIN", b"BDOS    SYS"):
            self.assertEqual(_bytes_of(os_image, name), _bytes_of(self.image, name), name)

    def test_mkdisc_twice_is_byte_identical_and_equals_built_disc(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = []
            for index in range(2):
                out = os.path.join(tmp, "utils%d.bdd" % index)
                subprocess.run([FTOOL, "mkdisc", h.UTILS_MANIFEST, out], cwd=h.SRC,
                               check=True, stdin=subprocess.DEVNULL, capture_output=True)
                outputs.append(h.read_bytes(out))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(self.image, outputs[0])

    def test_os_bdd_catalog_is_exactly_the_system_utilities(self):
        names = [(e.name, e.ext) for e in h.read_catalog(h.OS_DISK)]
        self.assertEqual([("BOOTSECT", "BIN"), ("DISC", "CAT"), ("BDOS", "SYS"), ("LS", "PRG"),
                          ("HELLOWRD", "PRG"), ("CP", "PRG"), ("FORMAT", "PRG"), ("RM", "PRG"),
                          ("CHA", "PRG"), ("CAT", "PRG"), ("TEST", "B")], names)

    def test_hellowrd_bytes_are_identical_on_both_discs(self):
        os_image = h.read_bytes(h.OS_DISK)
        self.assertEqual(_bytes_of(os_image, b"HELLOWRDPRG"), _bytes_of(self.image, b"HELLOWRDPRG"))


class UtilsDiscSessionTests(unittest.TestCase):
    def test_utils_disc_alone_boots_and_has_no_utilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, "utils_solo.in.txt")
            with open(script, "w", newline="\n") as handle:
                handle.write("ls\nexit\n")
            out = h.run_session("utils_solo", script, disks={"a": h.UTILS_DISK}, max_instructions=LIMIT)
        h.assert_markers(out, [b"bDOS 1.1 shell", b"A>", b"error: E0 file not found", b"bye!"])

    def test_hellowrd_runs_from_b_and_returns_to_b_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, "hellowrd_b.in.txt")
            with open(script, "w", newline="\n") as handle:
                handle.write("b:\nhellowrd\nexit\n")
            out = h.run_session("hellowrd_b", script, disks={"a": h.OS_DISK, "b": h.UTILS_DISK},
                                max_instructions=LIMIT)
        h.assert_markers(out, [b"B>hellowrd", b"Hello world!", b"B>exit"])

    def test_theodore_is_not_found_on_os_bdd_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, "theodore_a.in.txt")
            with open(script, "w", newline="\n") as handle:
                handle.write("theodore\nexit\n")
            out = h.run_session("theodore_a", script, disks={"a": h.OS_DISK}, max_instructions=LIMIT)
        h.assert_markers(out, [b"A>theodore", b"error: E0 file not found", b"bye!"])


if __name__ == "__main__":
    unittest.main()
