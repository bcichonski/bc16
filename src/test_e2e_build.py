"""Full rebuild check: build everything in a temp copy of src/ and compare with the committed outputs."""
import os
import shutil
import subprocess
import tempfile
import unittest

SRC = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = ["buildos", "buildtools", "buildapps", "makedisc"]
TEXT_EXT = (".genb", ".basm", ".btap")
BINARY_EXT = (".sector", ".sectors", ".b81", ".bdd")
TIMEOUT = 600


def tracked_outputs():
    """Git-tracked generated files under src/, as paths relative to src/; None if git is unavailable."""
    try:
        res = subprocess.run(["git", "ls-files", "-z", "--", "."], cwd=SRC, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    names = [n for n in res.stdout.decode().split("\0") if n]
    return sorted(n for n in names if n.endswith(TEXT_EXT + BINARY_EXT))


def read(path, text):
    with open(path, "rb") as f:
        data = f.read()
    return data.replace(b"\r", b"") if text else data


class FullRebuildTests(unittest.TestCase):
    def test_rebuild_reproduces_committed_outputs(self):
        files = tracked_outputs()
        if not files:
            self.skipTest("git is unavailable or lists no tracked files under src/")
        self.assertIn("os.bdd", files)
        tmp = tempfile.mkdtemp(prefix="bc16-build-")
        try:
            work = os.path.join(tmp, "src")
            shutil.copytree(SRC, work, ignore=shutil.ignore_patterns("__pycache__", "*.log", "*.dmp"))
            for script in SCRIPTS:
                res = subprocess.run(["./" + script], cwd=work, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=TIMEOUT)
                tail = res.stdout.decode(errors="replace")[-2000:]
                self.assertEqual(res.returncode, 0, "./%s exited %d, output tail:\n%s" % (script, res.returncode, tail))
            differing = []
            for name in files:
                text = name.endswith(TEXT_EXT)
                rebuilt = os.path.join(work, name)
                if not os.path.exists(rebuilt) or read(os.path.join(SRC, name), text) != read(rebuilt, text):
                    differing.append(name)
            self.assertEqual(differing, [], "committed outputs differ from a full rebuild (run ./buildos, "
                             "./buildtools, ./buildapps, ./makedisc in src/ and commit): " + ", ".join(differing))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
