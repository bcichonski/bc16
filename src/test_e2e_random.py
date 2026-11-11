"""E2E: the bdos BDIO_RANDOM call through random.b (bounded values, seed determinism)."""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import e2e_harness as h

BDOS_DIR = os.path.join(h.SRC, "bdos")
PROGRAM = os.path.join(h.GOLDEN_DIR, "random_prog.b")
SCENARIO = "random_run"
SECTION = re.compile(rb"A>e2eprog[^\n]*\n(.*?)(?=A>)", re.S)
MAX_INSTRUCTIONS = 100000000


class RandomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = cls.tmp.name
        for lib in glob.glob(os.path.join(BDOS_DIR, "*.b")):
            shutil.copy(lib, tmp)
        shutil.copy(PROGRAM, os.path.join(tmp, "prog.b"))
        cls.run_tool(tmp, os.path.join(h.SRC, "bc", "bc.py"), "--btap", "prog.b")
        cls.run_tool(tmp, os.path.join(h.SRC, "bc81asmc", "bc81asmc.py"), "--btap", "prog.basm")
        cls.run_tool(tmp, os.path.join(h.SRC, "ftool.py"), "btap2bin", "prog.btap", "prog.sectors")
        cls.disk = os.path.join(tmp, "e2e.bdd")
        shutil.copyfile(h.OS_DISK, cls.disk)
        with open(os.path.join(tmp, "prog.sectors"), "rb") as handle:
            h.disc_put(cls.disk, "E2EPROG.PRG", handle.read())
        cls.session = os.path.join(tmp, "session.txt")
        with open(cls.session, "wb") as handle:
            handle.write(b"e2eprog\nexit\n")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @staticmethod
    def run_tool(cwd, *args):
        result = subprocess.run([sys.executable] + list(args), cwd=cwd, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=300)
        if result.returncode != 0:
            raise AssertionError("%s failed (exit %d):\n%s\n%s" % (
                " ".join(os.path.basename(a) for a in args), result.returncode,
                result.stdout.decode("latin-1")[-3000:], result.stderr.decode("latin-1")[-3000:]))

    def run_program(self, seed):
        out = h.run_session(SCENARIO, self.session, disks={"a": self.disk},
                            max_instructions=MAX_INSTRUCTIONS, seed=seed)
        h.assert_markers(out, [b"A>e2eprog"])
        match = SECTION.search(out)
        self.assertIsNotNone(match, "no program output:\n%s" % out.decode("latin-1")[-1500:])
        return match.group(1).decode("latin-1").split()

    def parse(self, lines):
        self.assertIn("full", lines)
        self.assertEqual(lines[-1], "end")
        split = lines.index("full")
        bounded = [int(v, 16) for v in lines[max(0, split - 8):split]]
        self.assertEqual(len(bounded), 8)
        self.assertEqual(len(lines) - split, 3, "one unbounded value expected")
        self.assertNotIn("...", lines[split - 8:split])
        return bounded, int(lines[split + 1], 16)

    def test_bounded_values_below_max(self):
        bounded, full = self.parse(self.run_program(1))
        self.assertTrue(all(v < 10 for v in bounded), bounded)
        self.assertTrue(0 <= full <= 0xffff)

    def test_same_seed_same_output(self):
        self.assertEqual(self.run_program(5), self.run_program(5))

    def test_different_seed_different_output(self):
        self.assertNotEqual(self.run_program(5), self.run_program(6))


if __name__ == "__main__":
    unittest.main()
