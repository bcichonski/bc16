"""E2E: `return` from any nesting depth leaves sys_stackhead and caller locals intact."""
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
PROGRAM = os.path.join(h.GOLDEN_DIR, "return_prog.b")
SCENARIO = "return_run"
SECTION = re.compile(rb"A>e2eprog[^\n]*\n(.*?)(?=A>)", re.S)
MAX_INSTRUCTIONS = 200000000
# x, find(5,23)=203, z, find(5,30)=7777, find(3,99)=9999, fact(6), fib(10), 7 classify paths,
# 3 pick results, deep(5), x, z, then the two sys_stackhead values (compared separately)
EXPECTED = ["1111", "00CB", "3333", "1E61", "270F", "02D0", "0037",
            "0101", "0102", "0103", "0104", "0105", "0106", "0107",
            "0041", "0042", "0043", "0458", "1111", "3333"]


class ReturnTests(unittest.TestCase):
    def run_tool(self, cwd, *args):
        result = subprocess.run([sys.executable] + list(args), cwd=cwd, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=300)
        if result.returncode != 0:
            self.fail("%s failed (exit %d):\n%s\n%s" % (
                " ".join(os.path.basename(a) for a in args), result.returncode,
                result.stdout.decode("latin-1")[-3000:], result.stderr.decode("latin-1")[-3000:]))

    def test_return_from_nested_scopes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for lib in glob.glob(os.path.join(BDOS_DIR, "*.b")):
                shutil.copy(lib, tmp)
            shutil.copy(PROGRAM, os.path.join(tmp, "prog.b"))
            self.run_tool(tmp, os.path.join(h.SRC, "bc", "bc.py"), "--btap", "prog.b")
            self.run_tool(tmp, os.path.join(h.SRC, "bc81asmc", "bc81asmc.py"), "--btap", "prog.basm")
            self.run_tool(tmp, os.path.join(h.SRC, "ftool.py"), "btap2bin", "prog.btap", "prog.sectors")
            disk = os.path.join(tmp, "e2e.bdd")
            shutil.copyfile(h.OS_DISK, disk)
            with open(os.path.join(tmp, "prog.sectors"), "rb") as handle:
                h.disc_put(disk, "E2EPROG.PRG", handle.read())
            session = os.path.join(tmp, "session.txt")
            with open(session, "wb") as handle:
                handle.write(b"e2eprog\nexit\n")
            out = h.run_session(SCENARIO, session, disks={"a": disk},
                                max_instructions=MAX_INSTRUCTIONS)
        h.assert_markers(out, [b"A>e2eprog", b"done"])
        match = SECTION.search(out)
        self.assertIsNotNone(match, "no program output:\n%s" % out.decode("latin-1")[-1500:])
        lines = [l.strip().upper() for l in match.group(1).decode("latin-1").split("\n") if l.strip()]
        # the program output follows a progress-dots line printed by the loader
        self.assertGreaterEqual(len(lines), len(EXPECTED) + 3, "output lines: %r" % lines)
        lines = lines[-(len(EXPECTED) + 3):]
        self.assertEqual(lines[:len(EXPECTED)], EXPECTED)
        before, after, done = lines[len(EXPECTED):]
        self.assertRegex(before, r"^[0-9A-F]{4}$")
        self.assertEqual(before, after, "sys_stackhead changed across the calls")
        self.assertEqual(done.lower(), "done")


if __name__ == "__main__":
    unittest.main()
