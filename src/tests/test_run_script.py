"""Tests of src/run: it refuses to start the emulator when the ROM or os.bdd is missing.

Each test copies run into a temp folder and runs it there with bash. Nothing is built; the
stand-in bc64.py only records the arguments it was started with.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(SRC, "run")
ROM = os.path.join("bc81asmc", "bcOS", "bcos_v1_2_0.b81")
BUILD_CMD = "./buildos && ./buildtools && ./buildapps && ./makedisc"
MARKER = "started.txt"
STAND_IN_BC64 = (
    "import sys\n"
    "open('started.txt', 'w').write(repr(sys.argv[1:]))\n"
)


def make_folder(root, rom, disc):
    """Create a run folder with run and stand-in bc64.py, plus the ROM and os.bdd if asked."""
    shutil.copy(RUN, os.path.join(root, "run"))
    with open(os.path.join(root, "bc64.py"), "w") as f:
        f.write(STAND_IN_BC64)
    if rom:
        path = os.path.join(root, ROM)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"\x00" * 16)
    if disc:
        with open(os.path.join(root, "os.bdd"), "wb") as f:
            f.write(b"\x00" * 16)


def run_script(root):
    # The interpreter run picks is python3 (else python) from PATH: put this interpreter's
    # folder first so the stand-in bc64.py is started with the same Python as the tests.
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    return subprocess.run(["bash", "./run"], cwd=root, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=60, env=env)


@unittest.skipIf(shutil.which("bash") is None, "bash is not on PATH")
class RunScriptTests(unittest.TestCase):
    def test_missing_rom_exits_1_and_names_rom_and_build_command(self):
        with tempfile.TemporaryDirectory() as root:
            make_folder(root, rom=False, disc=True)
            result = run_script(root)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(os.path.basename(ROM), result.stderr)
            self.assertIn(BUILD_CMD, result.stderr)
            self.assertFalse(os.path.exists(os.path.join(root, MARKER)))

    def test_missing_os_bdd_exits_1_and_names_disc_and_build_command(self):
        with tempfile.TemporaryDirectory() as root:
            make_folder(root, rom=True, disc=False)
            result = run_script(root)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("os.bdd", result.stderr)
            self.assertIn(BUILD_CMD, result.stderr)
            self.assertFalse(os.path.exists(os.path.join(root, MARKER)))

    def test_both_missing_names_both_and_starts_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            make_folder(root, rom=False, disc=False)
            result = run_script(root)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(os.path.basename(ROM), result.stderr)
            self.assertIn("os.bdd", result.stderr)
            self.assertFalse(os.path.exists(os.path.join(root, MARKER)))

    def test_both_present_starts_emulator_with_rom_path(self):
        with tempfile.TemporaryDirectory() as root:
            make_folder(root, rom=True, disc=True)
            result = run_script(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(os.path.join(root, MARKER)) as f:
                self.assertEqual(f.read(), repr(["./" + ROM.replace(os.sep, "/")]))


if __name__ == "__main__":
    unittest.main()
