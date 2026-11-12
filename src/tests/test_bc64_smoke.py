"""End-to-end smoke tests: boot bdos headless, type a session, check the printer output.

Two tests, both on the freshly built src/os.bdd (build first: ./buildos && ./buildtools &&
./buildapps && ./makedisc):
- the transcript test boots os.bdd and compares the printer output byte for byte with
  bc64/testdata/smoke_transcript.txt, after the layout masks of e2e_harness.DISC_MASKS (disc positions
  are not pinned); BC64_UPDATE_GOLDEN=1 (or `python3 run_tests.py --update-golden`) rewrites it;
- the live test checks only output that a rebuilt disc keeps (banner, listing header, HELLOWRD, exit).
Both run on a temporary copy of the disc, so the built image is never written.
"""
import difflib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import e2e_harness as h

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BC64_PY = os.path.join(SRC, "bc64.py")
ROM = os.path.join(SRC, "bc81asmc", "bcOS", "bcos_v1_2_0.b81")
OS_DISK = os.path.join(SRC, "os.bdd")
TESTDATA = os.path.join(SRC, "bc64", "testdata")
SESSION = os.path.join(TESTDATA, "smoke_session.txt")
TRANSCRIPT = os.path.join(TESTDATA, "smoke_transcript.txt")
LIVE_SESSION = os.path.join(TESTDATA, "smoke_live_session.txt")
MAX_INSTRUCTIONS = "200000000"

REGENERATE = (
    "If the change is intended (bcOS or emulator), regenerate the transcript with\n"
    "  python3 run_tests.py --update-golden   (rebuilds the disc first; or set BC64_UPDATE_GOLDEN=1)\n"
    "then inspect the git diff by eye and commit it."
)

TRANSCRIPT_MARKERS = [b"bDOS 1.1 shell", b"A>ls", b"HELLOWRD.PRG", b"TEST    .B", b"sectors free",
                      b"A>cat -c test.b", b"first line", b"A>hellowrd", b"Hello world!", b"A>exit",
                      b"bye!"]
LIVE_MARKERS = [b"bDOS 1.1 shell", b"A>ls", b"listing files of drive A:", b"HELLOWRD.PRG",
                b"sectors free", b"A>hellowrd", b"Hello world!", b"A>exit", b"bye!"]


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


class SmokeSessionTests(unittest.TestCase):
    def run_session(self, disk_image, session):
        """Boot disk_image (on a temp copy) with the session script; return the printer output."""
        disk_before = read_bytes(disk_image)
        with tempfile.TemporaryDirectory() as tmp:
            disk = os.path.join(tmp, "os.bdd")
            output = os.path.join(tmp, "out.txt")
            shutil.copyfile(disk_image, disk)
            result = subprocess.run(
                [sys.executable, BC64_PY, ROM, "--disk-a", disk, "--input", session, "--output", output,
                 "--max-instructions", MAX_INSTRUCTIONS],
                cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertNotIn(b"Disk A name", result.stdout)
            actual = read_bytes(output)
        self.assertEqual(disk_before, read_bytes(disk_image), disk_image + " was modified")
        return actual

    def test_built_disc_session_matches_transcript(self):
        actual = self.run_session(OS_DISK, SESSION)
        for marker in TRANSCRIPT_MARKERS:
            self.assertIn(marker, actual)
        actual = h.apply_masks(actual, h.DISC_MASKS)
        if os.environ.get(h.UPDATE_ENV) == "1":
            with open(TRANSCRIPT, "wb") as handle:
                handle.write(actual)
            sys.stderr.write("[smoke] transcript written: %s (review the git diff)\n" % TRANSCRIPT)
            return
        expected = h.apply_masks(read_bytes(TRANSCRIPT), h.DISC_MASKS)
        if actual != expected:
            diff = "\n".join(difflib.unified_diff(
                expected.decode("latin-1").splitlines(), actual.decode("latin-1").splitlines(),
                "expected", "actual", lineterm="", n=2))
            self.fail("printer output differs from the committed transcript\n" + diff[:4000] + "\n" + REGENERATE)

    def test_current_os_disc_boots_and_runs_hellowrd(self):
        actual = self.run_session(OS_DISK, LIVE_SESSION)
        for marker in LIVE_MARKERS:
            self.assertIn(marker, actual, "missing in the session on src/os.bdd:\n"
                          + actual.decode("latin-1")[:3000])


if __name__ == "__main__":
    unittest.main()
