"""Layout-shift proof: growing a program in the middle of the manifest must not break the e2e checks.

Builds a shifted system disc in a temp dir (HELLOWRD.PRG grown by 8+ zero sectors, so every later file
moves and HELLOWRD's progress dots change), then runs the position-sensitive scenarios on it and compares
them with the committed goldens/transcript under DISC_MASKS. Compare-only: never writes a golden, also
when BC64_UPDATE_GOLDEN=1.
"""
import difflib
import os
import tempfile
import unittest

import e2e_harness as h
import ftool_mkdisc

# Same limit as the bdos scenario tests.
LIMIT = 50000000
EXTRA_SECTORS = 8
SMOKE_SESSION = os.path.join(h.TESTDATA, "smoke_session.txt")
SMOKE_TRANSCRIPT = os.path.join(h.TESTDATA, "smoke_transcript.txt")
GROWN = "HELLOWRD.PRG"


def write_shifted_manifest(path):
    """Copy MANIFEST to path with absolute sources; GROWN's source is a zero-padded copy."""
    folder = os.path.dirname(path)
    out = []
    with open(h.MANIFEST, "r", encoding="utf-8") as handle:
        for raw in handle.read().splitlines():
            content = raw.split("#", 1)[0].strip()
            if not content:
                continue
            columns = content.split()
            if columns[1] != "-":
                source = os.path.join(os.path.dirname(h.MANIFEST), columns[1])
                if columns[0].upper() == GROWN:
                    padded = os.path.join(folder, "padded.sectors")
                    with open(padded, "wb") as target:
                        target.write(h.read_bytes(source))
                        target.write(b"\x00" * (EXTRA_SECTORS * h.SECTOR_SIZE))
                    source = padded
                columns[1] = os.path.abspath(source)
            out.append("  ".join(columns))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out) + "\n")


def compare_masked(name, golden, actual):
    """Compare actual with the committed golden under DISC_MASKS; never writes anything."""
    expected = h.apply_masks(h.read_bytes(golden), h.DISC_MASKS)
    masked = h.apply_masks(actual, h.DISC_MASKS)
    if masked == expected:
        return
    diff = "\n".join(difflib.unified_diff(
        expected.decode("latin-1").splitlines(), masked.decode("latin-1").splitlines(),
        "golden", "shifted", lineterm="", n=2))
    raise AssertionError("%s on the shifted disc differs from %s under DISC_MASKS\n%s"
                         % (name, golden, diff[:h.DIFF_CAP]))


class LayoutShiftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.manifest = os.path.join(cls._tmp.name, "shifted.bddmanifest")
        write_shifted_manifest(cls.manifest)
        cls.disc = os.path.join(cls._tmp.name, "shifted.bdd")
        ftool_mkdisc.mkdisc(cls.manifest, cls.disc)

    def scenario(self, name):
        return h.run_session(name, h.golden_path(name, "in"), disks={"a": self.disc},
                             max_instructions=LIMIT)

    def test_shifted_plan_moves_every_later_entry(self):
        real = h.planned_entries()
        shifted = h.planned_entries(self.manifest)
        self.assertEqual([(e.name, e.ext) for e in real], [(e.name, e.ext) for e in shifted])
        names = [e.name + "." + e.ext for e in real]
        index = names.index(GROWN)
        self.assertGreaterEqual(shifted[index].length, real[index].length + EXTRA_SECTORS)
        self.assertNotEqual(real[index].length // 8, shifted[index].length // 8,
                            "HELLOWRD's length must cross an 8-sector boundary (dot count changes)")
        for old, new in zip(real[index + 1:], shifted[index + 1:]):
            self.assertNotEqual((old.track, old.sector), (new.track, new.sector),
                                "%s did not move" % old.name)

    def test_ls_scenarios_match_goldens_and_derived_lines(self):
        for name in ("bdos_ls", "disc_ls_all"):
            out = self.scenario(name)
            compare_masked(name, h.golden_path(name), out)
            system = ftool_mkdisc.ATTRIBUTES["S"]
            for entry in h.planned_entries(self.manifest):
                # plain `ls` hides system files, `ls -a` lists everything
                if name == "bdos_ls" and entry.attribs & system:
                    continue
                line = h.ls_line(entry).encode("latin-1")
                self.assertIn(line, out, "%s: derived ls line %r missing" % (name, line))

    def test_hellowrd_scenario_matches_golden(self):
        compare_masked("bdos_hellowrd", h.golden_path("bdos_hellowrd"), self.scenario("bdos_hellowrd"))

    def test_smoke_session_matches_transcript(self):
        out = h.run_session("smoke", SMOKE_SESSION, disks={"a": self.disc},
                            max_instructions=h.DEFAULT_MAX_INSTRUCTIONS)
        compare_masked("smoke session", SMOKE_TRANSCRIPT, out)


if __name__ == "__main__":
    unittest.main()
