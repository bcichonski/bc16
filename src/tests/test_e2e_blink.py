"""E2E: an assembly-only program is assembled to .o, linked by blink against runtime.o, runs from the shell."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import e2e_harness as h

RUNTIME = os.path.join(h.SRC, "bc", "runtime.basm")
BLINK = os.path.join(h.SRC, "blink.py")
ASMC = os.path.join(h.SRC, "bc81asmc", "bc81asmc.py")
MAX_INSTRUCTIONS = 200000000
HELLO = """\
.extern printstr
.extern print_newline
.sect hello_main
.global F_main
F_main:     .mv dsdi, :msg
            cal :printstr
            cal :print_newline
            ret
.sect hello_msg
msg:        .db 'h', 'e', 'l', 'l', 'o', ' ', 'b', 'l', 'i', 'n', 'k', 0x00
"""


class BlinkE2ETests(unittest.TestCase):
    def run_tool(self, cwd, *args):
        result = subprocess.run([sys.executable] + list(args), cwd=cwd, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=300)
        if result.returncode != 0:
            self.fail("%s failed (exit %d):\n%s\n%s" % (
                " ".join(os.path.basename(a) for a in args), result.returncode,
                result.stdout.decode("latin-1")[-3000:], result.stderr.decode("latin-1")[-3000:]))

    def test_linked_hello_runs_from_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(RUNTIME, os.path.join(tmp, "runtime.basm"))
            with open(os.path.join(tmp, "hello.basm"), "w", newline="\n") as handle:
                handle.write(HELLO)
            self.run_tool(tmp, ASMC, "--obj", "runtime.basm")
            self.run_tool(tmp, ASMC, "--obj", "hello.basm")
            self.run_tool(tmp, BLINK, "hello", "--lib", tmp)
            prg = os.path.join(tmp, "hello.prg")
            self.assertTrue(os.path.exists(prg), os.listdir(tmp))
            disk = os.path.join(tmp, "e2e.bdd")
            shutil.copyfile(h.OS_DISK, disk)
            with open(prg, "rb") as handle:
                h.disc_put(disk, "HELLO.PRG", handle.read())
            session = os.path.join(tmp, "session.txt")
            with open(session, "wb") as handle:
                handle.write(b"hello\nexit\n")
            out = h.run_session("blink_run", session, disks={"a": disk},
                                max_instructions=MAX_INSTRUCTIONS)
        h.assert_markers(out, [b"A>hello", b"hello blink"])
        self.assertGreater(out.rindex(b"A>"), out.index(b"hello blink"),
                           "no shell prompt after the program:\n%s" % out.decode("latin-1")[-800:])


if __name__ == "__main__":
    unittest.main()
