"""E2E: the freshly built bcOS ROM booted headless without a floppy (needs ./buildos first)."""
import os
import subprocess
import sys
import tempfile
import unittest

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BC64_PY = os.path.join(SRC, "bc64.py")
ROM = os.path.join(SRC, "bc81asmc", "bcOS", "bcos_v1_2_0.b81")
LAUNCH = ("import sys; sys.path.insert(0, %r); import bc64_toolchain; sys.argv = ['cmd'] + sys.argv[1:]; "
          "sys.exit(bc64_toolchain.%s())")


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def run(cwd, *args):
    return subprocess.run([sys.executable] + list(args), cwd=cwd, stdin=subprocess.DEVNULL,
                          capture_output=True, timeout=300)


def launch(cwd, command, *args, src=SRC):
    return run(cwd, "-c", LAUNCH % (src, command), *args)


class RomBootTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def sub(self, name):
        path = os.path.join(self.tmp, name)
        os.mkdir(path)
        return path

    def test_no_floppy_boots_the_real_rom_to_the_prompt(self):
        script = os.path.join(self.tmp, "keys.txt")
        with open(script, "wb") as f:
            f.write(b"h\n")
        result = subprocess.run([sys.executable, BC64_PY, ROM, "--no-floppy", "--input", script],
                                cwd=self.tmp, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"type h for help", result.stdout)
        self.assertNotIn(b"Disk A name", result.stdout)
        self.assertEqual([n for n in os.listdir(self.tmp) if n.endswith(".bdd")], [])

    def test_bc64_headless_run_matches_the_script(self):
        via_cmd, via_script = self.sub("cmd"), self.sub("script")
        keys = os.path.join(self.tmp, "keys.txt")
        with open(keys, "wb") as handle:
            handle.write(b"q\n")
        options = [ROM, "--no-floppy", "--input", keys, "--max-instructions", "100000000"]
        direct = run(via_script, BC64_PY, *options, "--output", "out.txt")
        result = launch(via_cmd, "bc64", *options, "--output", "out.txt")
        self.assertEqual(result.returncode, direct.returncode)
        self.assertIn(b"bcOS", read(os.path.join(via_cmd, "out.txt")))
        self.assertEqual(read(os.path.join(via_cmd, "out.txt")), read(os.path.join(via_script, "out.txt")))
        self.assertEqual(result.stdout, direct.stdout)


if __name__ == "__main__":
    unittest.main()
