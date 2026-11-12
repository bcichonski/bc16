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


class ScriptedEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bc64scr")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def make(self, script=None, **kw):
        stream = io.BytesIO(script) if script is not None else None
        env = bc64_env.ScriptedEnvironment(False, input_source=stream, **kw)
        self.addCleanup(env.close)
        return env

    def keys(self, env, count):
        return [ord(env.get_char()) for _ in range(count)]

    def test_disk_prompt_answered_per_drive_every_time(self):
        env = self.make(disk_a="a.bdd", disk_b="b.bdd")
        out = io.StringIO()
        with mock.patch.object(builtins, "input", side_effect=AssertionError("stdin used")):
            with contextlib.redirect_stdout(out):
                self.assertEqual(env.get_string("Disk A name:"), "a.bdd")
                self.assertEqual(env.get_string("Disk B name:"), "b.bdd")
                self.assertEqual(env.get_string("Disk A name:"), "a.bdd")
        self.assertEqual(out.getvalue(), "")

    def test_unconfigured_drive_falls_back_to_next_script_line(self):
        env = self.make(b"other.bdd\nnext", disk_a="a.bdd")
        self.assertEqual(env.get_string("Disk B name:"), "other.bdd")
        self.assertEqual(env.get_string("Type name of the tape to read: "), "next")

    def test_fallback_to_console_without_input(self):
        env = self.make(disk_a="a.bdd")
        with mock.patch.object(builtins, "input", return_value="x") as fake_input:
            self.assertEqual(env.get_string("Disk B name:"), "x")
        fake_input.assert_called_once_with("]> Disk B name:")

    def test_line_endings_become_single_cr(self):
        env = self.make(b"a\nb\r\nc\rd\n\ne\r\r\xff\x00")
        self.assertEqual(self.keys(env, 14),
                         [0x61, 13, 0x62, 13, 0x63, 13, 0x64, 13, 13, 0x65, 13, 13, 0xff, 0])
        with self.assertRaises(bc64_env.EndOfInput):
            env.get_char()

    def test_other_bytes_unchanged(self):
        env = self.make(bytes([1, 0x7f, 0x80, 0xfe, 0xff]))
        self.assertEqual(self.keys(env, 5), [1, 0x7f, 0x80, 0xfe, 0xff])

    def test_end_of_input_raises(self):
        env = self.make(b"x")
        env.get_char()
        with self.assertRaises(bc64_env.EndOfInput):
            env.get_char()
        with self.assertRaises(bc64_env.EndOfInput):
            env.get_string("Anything")

    def test_prompt_line_consumes_ending_but_not_following_bytes(self):
        env = self.make(b"name\r\nhi")
        self.assertEqual(env.get_string("Type name of the tape to write: "), "name")
        self.assertEqual(self.keys(env, 2), [ord("h"), ord("i")])

    def test_input_from_file_path(self):
        name = os.path.join(self.tmp, "in.txt")
        with open(name, "wb") as f:
            f.write(b"ls\n")
        env = bc64_env.ScriptedEnvironment(False, input_source=name)
        self.addCleanup(env.close)
        self.assertEqual(self.keys(env, 3), [ord("l"), ord("s"), 13])
        with self.assertRaises(bc64_env.EndOfInput):
            env.get_char()

    def test_tape_dir_resolves_relative_btap_only(self):
        tapes = os.path.join(self.tmp, "tapes")
        os.mkdir(tapes)
        env = self.make(tape_dir=tapes)
        env.close_file(env.open_file_to_write("t.btap"))
        self.assertTrue(os.path.exists(os.path.join(tapes, "t.btap")))
        self.assertTrue(env.file_exists("t.btap"))
        env.close_file(env.open_file_to_read("t.btap"))
        absolute = os.path.join(self.tmp, "abs.btap")
        env.close_file(env.open_file_to_write(absolute))
        self.assertTrue(os.path.exists(absolute))
        other = os.path.join(self.tmp, "x.bdd")
        with open(other, "wb") as f:
            f.write(b"1")
        env.close_file(env.open_file_to_readwrite(other))

    def test_btap_stays_in_cwd_without_tape_dir(self):
        env = self.make()
        self.assertEqual(env._resolve("t.btap"), "t.btap")

    def test_output_file_receives_printed_bytes(self):
        name = os.path.join(self.tmp, "out.bin")
        env = self.make(output_path=name)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            for b in (0x41, 13, 10, 0xe9, 0):
                env.write_char(b)
            with open(name, "rb") as f:  # flushed before close
                self.assertEqual(f.read(), bytes([0x41, 13, 10, 0xe9, 0]))
        env.close()
        self.assertTrue(out.getvalue().startswith("A"))

    def test_floppy_drive_asks_prompt_the_environment_answers(self):
        from bc64 import bc64_io, bc64_mem
        fdd_cls = bc64_io.FloppyDriveV1
        img = os.path.join(self.tmp, "d.bdd")
        env = self.make(disk_a=img)
        fdd = fdd_cls(env, bc64_mem.MemBus(env, 0x1000))
        self.addCleanup(lambda: fdd.fileA_handle and fdd.fileA_handle.close())
        with mock.patch.object(builtins, "input", side_effect=AssertionError("stdin used")):
            for b in (fdd_cls.CMD_CFG, 0x01, 0x00, fdd_cls.CMD_READSECT, 0, 0):
                fdd.write_byte(b)
        self.assertEqual(fdd.read_byte(), fdd_cls.STATE_READY)
        self.assertEqual(fdd.fileA_name, img)
        self.assertTrue(os.path.exists(img))


if __name__ == "__main__":
    unittest.main()
