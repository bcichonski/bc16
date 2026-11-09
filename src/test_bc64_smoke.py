import difflib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = os.path.dirname(os.path.abspath(__file__))
BC64_PY = os.path.join(SRC, "bc64.py")
ROM = os.path.join(SRC, "bc81asmc", "bcOS", "bcos_v1_2_0.b81")
OS_DISK = os.path.join(SRC, "os.bdd")
TESTDATA = os.path.join(SRC, "bc64", "testdata")
SESSION = os.path.join(TESTDATA, "smoke_session.txt")
TRANSCRIPT = os.path.join(TESTDATA, "smoke_transcript.txt")

REGENERATE = (
    "To regenerate the transcript after an intended change (os.bdd, bcOS or emulator), run in a scratch directory:\n"
    "  cp {disk} os.bdd && python3 {bc64} {rom} --disk-a os.bdd --input {session} "
    "--output {transcript} --max-instructions 200000000 < /dev/null\n"
    "then inspect the result by eye and commit it."
).format(disk=OS_DISK, bc64=BC64_PY, rom=ROM, session=SESSION, transcript=TRANSCRIPT)

MARKERS = [b"bDOS 1.1 shell", b"A>ls", b"HELLOWRD.PRG", b"TEST    .B", b"sectors free",
           b"A>cat -c test.b", b"first line", b"A>hellowrd", b"Hello world!", b"A>exit", b"bye!"]


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


class SmokeSessionTests(unittest.TestCase):
    def test_boot_ls_cat_run_exit_matches_transcript(self):
        disk_before = read_bytes(OS_DISK)
        expected = read_bytes(TRANSCRIPT)
        with tempfile.TemporaryDirectory() as tmp:
            disk = os.path.join(tmp, "os.bdd")
            output = os.path.join(tmp, "out.txt")
            shutil.copyfile(OS_DISK, disk)
            result = subprocess.run(
                [sys.executable, BC64_PY, ROM, "--disk-a", disk, "--input", SESSION, "--output", output,
                 "--max-instructions", "200000000"],
                cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertNotIn(b"Disk A name", result.stdout)
            actual = read_bytes(output)

        self.assertEqual(disk_before, read_bytes(OS_DISK), "the committed src/os.bdd was modified")
        for marker in MARKERS:
            self.assertIn(marker, actual)
        if actual != expected:
            diff = "\n".join(difflib.unified_diff(
                expected.decode("latin-1").splitlines(), actual.decode("latin-1").splitlines(),
                "expected", "actual", lineterm="", n=2))
            self.fail("printer output differs from the committed transcript\n" + diff[:4000] + "\n" + REGENERATE)


if __name__ == "__main__":
    unittest.main()
