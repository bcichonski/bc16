import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SRC = os.path.dirname(os.path.abspath(__file__))
BC64_PY = os.path.join(SRC, "bc64.py")

# Hand-made ROMs. DI=1 is the printer port, A is the data register.
KIL = bytes([0xf0])
ENDLESS_LOOP = bytes([0x6c, 0x0a])
# prints "Hi" and halts
PRINT_HI = bytes([0x15, 0x01, 0x11, 0x48, 0xd8, 0x51, 0x11, 0x69, 0xd8, 0x51, 0xf0])
# endless: read a key from the keyboard, print it back
ECHO = bytes([0x15, 0x01, 0xc0, 0x10, 0xd8, 0x51, 0x6c, 0x02])


def load_bc64_module():
    # "import bc64" from src/ is the package, so load the script by path.
    spec = importlib.util.spec_from_file_location("bc64_script", BC64_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArgumentParsingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_bc64_module()

    def parse(self, *args):
        return self.module.build_parser().parse_args(list(args))

    def test_defaults(self):
        args = self.parse()
        self.assertEqual(
            (args.rom, args.trace, args.disk_a, args.disk_b, args.tape_dir, args.input, args.output,
             args.max_instructions),
            (None,) * 8)

    def test_legacy_rom_and_trace_word(self):
        args = self.parse("rom.b81", "d")
        self.assertEqual((args.rom, args.trace), ("rom.b81", "d"))

    def test_each_option(self):
        args = self.parse("rom.b81", "--disk-a", "a.bdd", "--disk-b", "b.bdd", "--tape-dir", "tapes",
                          "--input", "-", "--output", "out.txt", "--max-instructions", "50")
        self.assertEqual(
            (args.disk_a, args.disk_b, args.tape_dir, args.input, args.output, args.max_instructions),
            ("a.bdd", "b.bdd", "tapes", "-", "out.txt", 50))

    def test_bad_max_instructions_is_a_usage_error(self):
        for bad in ("abc", "0", "-3"):
            with self.subTest(bad=bad), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    self.parse("--max-instructions", bad)
                self.assertEqual(raised.exception.code, 2)

    def test_headless_selection(self):
        module = self.module
        with mock.patch.object(module, "stdin_is_tty", return_value=True):
            self.assertFalse(module.is_headless(self.parse("rom.b81", "d")))
            self.assertTrue(module.is_headless(self.parse("--output", "o")))
            self.assertTrue(module.is_headless(self.parse("--max-instructions", "5")))
        with mock.patch.object(module, "stdin_is_tty", return_value=False):
            self.assertTrue(module.is_headless(self.parse("rom.b81")))

    def test_tty_without_options_uses_console_environment(self):
        module = self.module
        with mock.patch.object(module, "stdin_is_tty", return_value=True):
            env = module.make_env(self.parse("rom.b81"), False)
        self.assertEqual(type(env), module.bc64_env.Environment)

    def test_piped_stdin_is_the_key_source(self):
        module = self.module
        with mock.patch.object(module, "stdin_is_tty", return_value=False):
            env = module.make_env(self.parse("rom.b81"), False)
        self.assertIs(env.input, sys.stdin.buffer)

    def test_input_file_overrides_the_pipe(self):
        module = self.module
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, "keys.txt")
            with open(script, "wb") as f:
                f.write(b"x")
            with mock.patch.object(module, "stdin_is_tty", return_value=False):
                env = module.make_env(self.parse("--input", script), False)
            try:
                self.assertIsNot(env.input, sys.stdin.buffer)
            finally:
                env.close()

    def test_no_floppy_option(self):
        self.assertFalse(self.parse("rom.b81").no_floppy)
        self.assertTrue(self.parse("rom.b81", "--no-floppy").no_floppy)

    def test_no_floppy_is_headless(self):
        module = self.module
        with mock.patch.object(module, "stdin_is_tty", return_value=True):
            self.assertTrue(module.is_headless(self.parse("--no-floppy")))

    def test_no_floppy_conflicts_with_disks(self):
        module = self.module
        for disk in ("--disk-a", "--disk-b"):
            with self.subTest(disk=disk), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    module.parse_args(["--no-floppy", disk, "x.bdd"])
                self.assertEqual(raised.exception.code, 2)

    def test_help_lists_every_option(self):
        text = self.module.build_parser().format_help()
        for option in ("--disk-a", "--disk-b", "--tape-dir", "--input", "--output", "--max-instructions",
                       "--no-floppy"):
            self.assertIn(option, text)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bc64cli")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def rom(self, content):
        path = os.path.join(self.tmp, "test.rom")
        with open(path, "wb") as f:
            f.write(content)
        return path

    def run_bc64(self, *args, stdin=b""):
        return subprocess.run([sys.executable, BC64_PY, *args], input=stdin, cwd=self.tmp,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)

    def dump_exists(self):
        return os.path.exists(os.path.join(self.tmp, "bc64.dmp"))

    def test_halt_dumps_memory_and_exits_zero(self):
        result = self.run_bc64(self.rom(KIL))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.dump_exists())

    def test_halt_with_option_and_no_pipe_input(self):
        out = os.path.join(self.tmp, "out.bin")
        result = self.run_bc64(self.rom(PRINT_HI), "--output", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"Hi")
        with open(out, "rb") as f:
            self.assertEqual(f.read(), b"Hi")
        self.assertTrue(self.dump_exists())

    def test_instruction_limit_exits_three_without_dump(self):
        out = os.path.join(self.tmp, "out.bin")
        result = self.run_bc64(self.rom(ENDLESS_LOOP), "--max-instructions", "100", "--output", out)
        self.assertEqual(result.returncode, 3)
        self.assertIn(b"100", result.stderr)
        self.assertFalse(self.dump_exists())
        self.assertTrue(os.path.exists(out))

    def test_limit_not_reached_before_halt_exits_zero(self):
        result = self.run_bc64(self.rom(PRINT_HI), "--max-instructions", "1000")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.dump_exists())

    def test_end_of_input_exits_zero_without_dump(self):
        result = self.run_bc64(self.rom(ECHO), stdin=b"ab")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"ab")
        self.assertFalse(self.dump_exists())

    def test_input_file_is_typed_and_lines_become_cr(self):
        script = os.path.join(self.tmp, "keys.txt")
        out = os.path.join(self.tmp, "out.bin")
        with open(script, "wb") as f:
            f.write(b"a\r\nb\n")
        result = self.run_bc64(self.rom(ECHO), "--input", script, "--output", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(out, "rb") as f:
            self.assertEqual(f.read(), b"a\rb\r")
        self.assertFalse(self.dump_exists())

    def test_input_file_overrides_the_pipe(self):
        script = os.path.join(self.tmp, "keys.txt")
        with open(script, "wb") as f:
            f.write(b"x")
        result = self.run_bc64(self.rom(ECHO), "--input", script, stdin=b"piped")
        self.assertEqual(result.stdout, b"x")

    def test_explicit_dash_reads_stdin(self):
        result = self.run_bc64(self.rom(ECHO), "--input", "-", stdin=b"q")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"q")

    def test_piped_stdin_with_devnull_is_end_of_input(self):
        result = subprocess.run([sys.executable, BC64_PY, self.rom(ECHO)], cwd=self.tmp,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")

    def test_piped_first_line_answers_unconfigured_disk_prompt(self):
        module = load_bc64_module()
        env = module.bc64_env.ScriptedEnvironment(debug=False, input_source=_Bytes(b"my.bdd\nk\n"))
        self.assertEqual(env.get_string("Disk A name:"), "my.bdd")
        self.assertEqual(env.get_char(), "k")

    def test_disk_option_answers_prompt_without_consuming_input(self):
        module = load_bc64_module()
        env = module.bc64_env.ScriptedEnvironment(debug=False, disk_a="a.bdd", input_source=_Bytes(b"k\n"))
        self.assertEqual(env.get_string("Disk A name:"), "a.bdd")
        self.assertEqual(env.get_char(), "k")

    def test_missing_rom_is_a_python_error(self):
        result = self.run_bc64(os.path.join(self.tmp, "nope.rom"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"Traceback", result.stderr)

    def test_usage_error_exits_two(self):
        result = self.run_bc64("--max-instructions", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"usage", result.stderr)

    def test_help_exits_zero_and_lists_options(self):
        result = self.run_bc64("--help")
        self.assertEqual(result.returncode, 0)
        for option in (b"--disk-a", b"--disk-b", b"--tape-dir", b"--input", b"--output", b"--max-instructions"):
            self.assertIn(option, result.stdout)

    def test_no_floppy_boots_the_real_rom_to_the_prompt(self):
        rom = os.path.join(SRC, "bc81asmc", "bcOS", "bcos_v1_2_0.b81")
        script = os.path.join(self.tmp, "keys.txt")
        with open(script, "wb") as f:
            f.write(b"h\n")
        result = subprocess.run([sys.executable, BC64_PY, rom, "--no-floppy", "--input", script],
                                cwd=self.tmp, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"type h for help", result.stdout)
        self.assertNotIn(b"Disk A name", result.stdout)
        self.assertEqual([n for n in os.listdir(self.tmp) if n.endswith(".bdd")], [])

    def test_output_file_is_flushed_when_the_limit_stops_the_run(self):
        # prints "Hi" then loops forever: the limit stops it and the file still holds the output
        rom = PRINT_HI[:-1] + bytes([0x6c, 0x0a])
        out = os.path.join(self.tmp, "out.bin")
        result = self.run_bc64(self.rom(rom), "--max-instructions", "200", "--output", out)
        self.assertEqual(result.returncode, 3)
        with open(out, "rb") as f:
            self.assertEqual(f.read(), b"Hi")


class _Bytes:
    """Minimal binary file-like object."""
    def __init__(self, data):
        self._io = io.BytesIO(data)

    def read(self, n=-1):
        return self._io.read(n)


if __name__ == "__main__":
    unittest.main()
