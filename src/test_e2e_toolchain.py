"""E2E: B source -> bc.py -> bc81asmc.py -> ftool btap2bin -> disc -> boot in the emulator -> run."""
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
PROGRAM = os.path.join(h.GOLDEN_DIR, "toolchain_prog.b")
SCENARIO = "toolchain_run"
# A>e2eprog line up to (not including) the next prompt
SECTION = re.compile(rb"A>e2eprog[^\n]*\n(.*?)(?=A>)", re.S)


class ToolchainTests(unittest.TestCase):
    def run_tool(self, cwd, *args):
        result = subprocess.run([sys.executable] + list(args), cwd=cwd, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=300)
        if result.returncode != 0:
            self.fail("%s failed (exit %d):\n%s\n%s" % (
                " ".join(os.path.basename(a) for a in args), result.returncode,
                result.stdout.decode("latin-1")[-3000:], result.stderr.decode("latin-1")[-3000:]))

    def test_compile_assemble_put_on_disc_and_run(self):
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
                handle.write(b"ls\ne2eprog\nexit\n")
            out = h.run_session(SCENARIO, session, disks={"a": disk})
        h.assert_markers(out, [b"A>ls", b"E2EPROG", b"A>e2eprog"])
        match = SECTION.search(out)
        self.assertIsNotNone(match, "no program output between A>e2eprog and the next prompt:\n%s"
                             % out.decode("latin-1")[-1500:])
        h.check_golden(h.golden_path(SCENARIO), match.group(1), scenario=SCENARIO)


if __name__ == "__main__":
    unittest.main()
