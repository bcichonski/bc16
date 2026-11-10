"""Launcher tests: the console commands (bc64_toolchain.py) behave like the scripts they run.

The project is not installed for these tests: the launcher is imported from the source tree in a
child process of this interpreter, in a temporary working directory outside src/.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = os.path.dirname(os.path.abspath(__file__))
BC_PY = os.path.join(SRC, "bc", "bc.py")
ASM_PY = os.path.join(SRC, "bc81asmc", "bc81asmc.py")
FTOOL_PY = os.path.join(SRC, "ftool.py")
BC64_PY = os.path.join(SRC, "bc64.py")
ROM = os.path.join(SRC, "bc81asmc", "bcOS", "bcos_v1_2_0.b81")

PROGRAM = "#code 0x6000\n#heap 0xf000\n\nbyte main()\n{\n    word a;\n    a <- 5;\n}\n"
BAD_PROGRAM = "#code 0x6000\n#heap 0xf000\n\nbyte main()\n{\n    a <- <- ;\n}\n"
BAD_ASM = "this is not assembler ???\n"
LAUNCH = ("import sys; sys.path.insert(0, %r); import bc64_toolchain; sys.argv = ['cmd'] + sys.argv[1:]; "
          "sys.exit(bc64_toolchain.%s())")


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def write(path, text):
    with open(path, "w", newline="") as handle:
        handle.write(text)


def run(cwd, *args):
    return subprocess.run([sys.executable] + list(args), cwd=cwd, stdin=subprocess.DEVNULL,
                          capture_output=True, timeout=300)


def launch(cwd, command, *args, src=SRC):
    return run(cwd, "-c", LAUNCH % (src, command), *args)


class ToolchainLauncherTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def sub(self, name):
        path = os.path.join(self.tmp, name)
        os.mkdir(path)
        return path

    def test_bcc_matches_the_scripts_and_runs_outside_src(self):
        via_cmd, via_script = self.sub("cmd"), self.sub("script")
        for folder in (via_cmd, via_script):
            write(os.path.join(folder, "prog.b"), PROGRAM)
        result = launch(via_cmd, "bcc", "prog")
        self.assertEqual(result.returncode, 0, result.stderr.decode("latin-1"))
        self.assertEqual(run(via_script, BC_PY, "--verbose", "--btap", "prog.b").returncode, 0)
        self.assertEqual(run(via_script, ASM_PY, "--verbose", "--btap", "prog.basm").returncode, 0)
        for name in ("prog.basm", "prog.btap"):
            self.assertTrue(read(os.path.join(via_cmd, name)))
            self.assertEqual(read(os.path.join(via_cmd, name)), read(os.path.join(via_script, name)), name)

    def test_bcc_stops_after_a_compile_error(self):
        write(os.path.join(self.tmp, "bad.b"), BAD_PROGRAM)
        direct = run(self.tmp, BC_PY, "--verbose", "--btap", "bad.b")
        self.assertNotEqual(direct.returncode, 0)
        result = launch(self.tmp, "bcc", "bad")
        self.assertEqual(result.returncode, direct.returncode)
        self.assertIn(b"Error", result.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "bad.btap")))

    def test_bcc_help_and_usage(self):
        self.assertEqual(launch(self.tmp, "bcc", "--help").returncode, 0)
        self.assertNotEqual(launch(self.tmp, "bcc").returncode, 0)

    def test_bc81asmc_matches_the_script(self):
        via_cmd, via_script = self.sub("cmd"), self.sub("script")
        for folder in (via_cmd, via_script):
            write(os.path.join(folder, "prog.b"), PROGRAM)
        self.assertEqual(run(via_script, BC_PY, "--btap", "prog.b").returncode, 0)
        shutil.copy(os.path.join(via_script, "prog.basm"), via_cmd)
        direct = run(via_script, ASM_PY, "--verbose", "--btap", "prog.basm")
        result = launch(via_cmd, "bc81asmc", "--verbose", "--btap", "prog.basm")
        self.assertEqual(result.returncode, direct.returncode)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(read(os.path.join(via_cmd, "prog.btap")), read(os.path.join(via_script, "prog.btap")))

    def test_bc81asmc_error_has_the_script_exit_code(self):
        write(os.path.join(self.tmp, "bad.basm"), BAD_ASM)
        direct = run(self.tmp, ASM_PY, "bad.basm")
        result = launch(self.tmp, "bc81asmc", "bad.basm")
        self.assertNotEqual(direct.returncode, 0)
        self.assertEqual(result.returncode, direct.returncode)

    def test_ftool_btap2bin_matches_the_script(self):
        via_cmd, via_script = self.sub("cmd"), self.sub("script")
        write(os.path.join(via_script, "prog.b"), PROGRAM)
        self.assertEqual(run(via_script, BC_PY, "--btap", "prog.b").returncode, 0)
        self.assertEqual(run(via_script, ASM_PY, "--btap", "prog.basm").returncode, 0)
        shutil.copy(os.path.join(via_script, "prog.btap"), via_cmd)
        direct = run(via_script, FTOOL_PY, "btap2bin", "prog.btap", "prog.bin")
        result = launch(via_cmd, "ftool", "btap2bin", "prog.btap", "prog.bin")
        self.assertEqual(direct.returncode, 0)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(read(os.path.join(via_script, "prog.bin")))
        self.assertEqual(read(os.path.join(via_cmd, "prog.bin")), read(os.path.join(via_script, "prog.bin")))

    def test_bc64_help_exits_zero(self):
        result = launch(self.tmp, "bc64", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"--no-floppy", result.stdout)

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

    def test_missing_source_tree_gives_the_install_hint_without_a_traceback(self):
        lonely = self.sub("lonely")
        shutil.copy(os.path.join(SRC, "bc64_toolchain.py"), lonely)
        for command, args in (("bc64", ["--help"]), ("bc81asmc", ["x.basm"]), ("ftool", []),
                              ("bcc", ["prog"])):
            result = launch(self.tmp, command, *args, src=lonely)
            self.assertNotEqual(result.returncode, 0, command)
            self.assertIn(b"pip install -e .", result.stderr, command)
            self.assertNotIn(b"Traceback", result.stderr, command)


if __name__ == "__main__":
    unittest.main()
