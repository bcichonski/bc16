import builtins
import contextlib
import io
import os
import shutil
import tempfile
import unittest
from unittest import mock
from bc64 import bc64_env


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bc64env")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = bc64_env.Environment(False)

    def path(self, name):
        return os.path.join(self.tmp, name)

    def test_debug_defaults_to_on(self):
        self.assertTrue(bc64_env.Environment().debug)

    def test_log_is_silent_when_debug_is_off(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.env.log("hello")
        self.assertEqual(out.getvalue(), "")

    def test_log_prints_when_debug_is_on(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            bc64_env.Environment(True).log("hello")
        self.assertEqual(out.getvalue(), "[DBG]:hello\n")

    def test_get_string_prompts_and_returns_input(self):
        with mock.patch.object(builtins, "input", return_value="disk1") as fake_input:
            res = self.env.get_string("Name:")
        self.assertEqual(res, "disk1")
        fake_input.assert_called_once_with("]> Name:")

    def test_write_then_read_bytes(self):
        name = self.path("f.bin")
        handle = self.env.open_file_to_write(name)
        self.assertEqual(self.env.write_bytes(handle, bytes([1, 2, 3, 4])), 4)
        self.env.close_file(handle)
        handle = self.env.open_file_to_read(name)
        self.assertEqual(self.env.read_bytes(handle, 3), bytes([1, 2, 3]))
        self.assertEqual(self.env.read_byte(handle), b"\x04")
        self.assertEqual(self.env.read_byte(handle), b"")  # end of file
        self.env.close_file(handle)

    def test_write_byte_writes_single_byte(self):
        name = self.path("f.bin")
        handle = self.env.open_file_to_write(name)
        self.env.write_byte(handle, 0xab)
        self.env.write_byte(handle, 0x01)
        self.env.close_file(handle)
        with open(name, "rb") as f:
            self.assertEqual(f.read(), bytes([0xab, 0x01]))

    def test_open_to_write_truncates(self):
        name = self.path("f.bin")
        with open(name, "wb") as f:
            f.write(b"long content")
        self.env.close_file(self.env.open_file_to_write(name))
        self.assertEqual(os.path.getsize(name), 0)

    def test_readwrite_and_move_file_handle(self):
        name = self.path("f.bin")
        with open(name, "wb") as f:
            f.write(bytes(range(10)))
        handle = self.env.open_file_to_readwrite(name)
        self.env.move_file_handle(handle, 4)
        self.env.write_bytes(handle, b"\xaa\xbb")
        self.env.move_file_handle(handle, 3)
        self.assertEqual(self.env.read_bytes(handle, 4), bytes([3, 0xaa, 0xbb, 6]))
        self.env.close_file(handle)

    def test_readwrite_does_not_create_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            self.env.open_file_to_readwrite(self.path("missing.bin"))

    def test_open_to_read_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.env.open_file_to_read(self.path("missing.bin"))

    def test_file_exists(self):
        name = self.path("f.bin")
        self.assertFalse(self.env.file_exists(name))
        self.env.close_file(self.env.open_file_to_write(name))
        self.assertTrue(self.env.file_exists(name))

    def test_close_file_closes_handle(self):
        handle = self.env.open_file_to_write(self.path("f.bin"))
        self.env.close_file(handle)
        self.assertTrue(handle.closed)

    def test_write_char_prints_character_without_newline(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.env.write_char(ord("A"))
            self.env.write_char(ord("b"))
        self.assertEqual(out.getvalue(), "Ab")

    def test_get_char_delegates_to_getch(self):
        with mock.patch.object(bc64_env, "getch", return_value="x"):
            self.assertEqual(self.env.get_char(), "x")


if __name__ == "__main__":
    unittest.main()
