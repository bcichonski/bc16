"""End-to-end bdos shell scenarios on the headless emulator (built os.bdd, temp copy only)."""
import unittest

import e2e_harness as h

# ~10x the measured need (about 2M instructions for a handful of commands).
LIMIT = 50000000
# Plain `ls` lines of the non-system files, derived from the manifest plan (not pinned numbers).
CATALOG_LINES = [h.ls_line(h.planned_entry(name)).encode("latin-1")
                 for name in ("HELLOWRD.PRG", "TEXTED.PRG", "TEST.B", "THEODORE.PRG")]
TEST_B_TEXT = [b"10 first line !ln", b"20 second line !ln"]


def run(scenario, inspect=None):
    """Run the scenario script on a temp copy of the built os.bdd; return the printer bytes."""
    return h.run_session(scenario, h.golden_path(scenario, "in"), disks={"a": h.OS_DISK},
                         max_instructions=LIMIT, inspect=inspect)


class BdosShellTests(unittest.TestCase):
    def check(self, scenario, markers, inspect=None):
        out = run(scenario, inspect)
        h.check_golden(h.golden_path(scenario), out, masks=h.DISC_MASKS, markers=markers,
                      scenario=scenario)
        return out

    def test_boot_prompt_and_exit(self):
        self.check("bdos_boot", [b"bDOS 1.1 shell", b"A>exit", b"bye!"])

    def test_ls_lists_catalog(self):
        self.check("bdos_ls", [b"A>ls"] + CATALOG_LINES + [b"EA catalog entries free"])

    def test_cat_prints_text_file(self):
        self.check("bdos_cat", [b"A>cat -c test.b"] + TEST_B_TEXT)

    def test_hellowrd_prints_greeting(self):
        self.check("bdos_hellowrd", [b"A>hellowrd", b"Hello world!"])

    def test_rm_removes_file_from_ls_and_catalog(self):
        seen = {}

        def inspect(paths):
            seen["names"] = [(e.name, e.ext) for e in h.read_catalog(paths["a"])]
            seen["before"] = [(e.name, e.ext) for e in h.read_catalog(h.OS_DISK)]

        out = self.check("bdos_rm", [b"A>rm test.b", b"A>ls", b"HELLOWRD.PRG", b"TEXTED  .PRG"], inspect)
        self.assertNotIn(b"TEST    .B", out)
        self.assertIn(("TEST", "B"), seen["before"])
        self.assertNotIn(("TEST", "B"), seen["names"])
        self.assertEqual([n for n in seen["before"] if n != ("TEST", "B")], seen["names"])

    def test_error_paths(self):
        out = self.check("bdos_errors", [b"A>foo", b"A>cat -c nofile.txt", b"bye!"])
        self.assertEqual(2, out.count(b"error: E0 file not found"))

    def test_cp_then_cat_shows_same_text(self):
        out = run("bdos_cp")
        h.assert_markers(out, [b"A>cp test.b copy.b", b"A>cat -c copy.b"] + TEST_B_TEXT + [b"bye!"])
        copy = out.split(b"A>cat -c copy.b", 1)[1]
        for line in TEST_B_TEXT:
            self.assertIn(line, copy)


if __name__ == "__main__":
    unittest.main()
