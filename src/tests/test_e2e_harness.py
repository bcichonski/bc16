"""Self-tests of src/e2e_harness.py (silent; temp dirs only, never the real testdata)."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import e2e_harness as h


def write(path, data):
    with open(path, "wb") as handle:
        handle.write(data)


class TempCase(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(h.UPDATE_ENV, None)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def path(self, name):
        return os.path.join(self.tmp, name)

    def session(self, text):
        path = self.path("session.txt")
        write(path, text)
        return path


class SessionRunnerTests(TempCase):
    def test_tiny_instruction_limit_fails_clearly(self):
        session = self.session(b"ls\nexit\n")
        before = h.read_bytes(h.OS_DISK)
        with self.assertRaises(AssertionError) as caught:
            h.run_session("limit-scenario", session, disks={"a": h.OS_DISK}, max_instructions=1000)
        message = str(caught.exception)
        self.assertIn("instruction limit", message)
        self.assertIn("1000", message)
        self.assertIn("limit-scenario", message)
        self.assertEqual(before, h.read_bytes(h.OS_DISK))

    def test_real_boot_returns_output_and_leaves_source_untouched(self):
        session = self.session(b"ls\nexit\n")
        before = h.read_bytes(h.OS_DISK)
        out = h.run_session("boot", session, disks={"a": h.OS_DISK})
        h.assert_markers(out, [b"A>ls", b"HELLOWRD.PRG", b"bye!"])
        self.assertEqual(before, h.read_bytes(h.OS_DISK))

    def test_seed_is_passed_as_random_seed_flag(self):
        session = self.session(b"ls\n")
        commands = []
        real_run = h.subprocess.run
        def spy(cmd, *args, **kwargs):
            commands.append(list(cmd))
            return real_run(cmd, *args, **kwargs)
        with mock.patch.object(h.subprocess, "run", spy):
            h.run_session("seeded", session, no_floppy=True, seed=0x2a)
            h.run_session("unseeded", session, no_floppy=True)
        self.assertEqual(commands[0][commands[0].index("--random-seed") + 1], str(0x2a))
        self.assertNotIn("--random-seed", commands[1])

    def test_other_nonzero_exit_reports_stderr(self):
        session = self.session(b"ls\n")
        with self.assertRaises(AssertionError) as caught:
            h.run_session("bad", session, rom=self.path("missing.b81"))
        self.assertIn("exited with", str(caught.exception))

    def test_disc_put_then_boot_shows_file_in_ls(self):
        disk = self.path("copy.bdd")
        shutil.copyfile(h.OS_DISK, disk)
        h.disc_put(disk, "newfile.txt", b"hello disc")
        session = self.session(b"ls\nexit\n")
        out = h.run_session("put", session, disks={"a": disk})
        h.assert_markers(out, [b"NEWFILE .TXT", b"HELLOWRD.PRG"])


class GoldenTests(TempCase):
    def test_pass_fail_and_diff(self):
        golden = self.path("g.golden.txt")
        write(golden, b"line1\nline2\n")
        h.check_golden(golden, b"line1\nline2\n", markers=[b"line2"])
        with self.assertRaises(AssertionError) as caught:
            h.check_golden(golden, b"line1\nlineX\n", scenario="demo")
        message = str(caught.exception)
        self.assertIn("-line2", message)
        self.assertIn("+lineX", message)
        self.assertIn(h.UPDATE_ENV, message)
        self.assertIn("demo", message)

    def test_missing_golden_fails(self):
        with self.assertRaises(AssertionError):
            h.check_golden(self.path("none.txt"), b"x")

    def test_exact_bytes_crlf_matters(self):
        golden = self.path("g.txt")
        write(golden, b"a\r\nb\r\n")
        with self.assertRaises(AssertionError):
            h.check_golden(golden, b"a\nb\n")

    def test_update_mode_writes_golden_silently_on_stdout(self):
        golden = os.path.join(self.tmp, "sub", "new.golden.txt")
        with mock.patch.dict(os.environ, {h.UPDATE_ENV: "1"}), mock.patch("sys.stderr"):
            h.check_golden(golden, b"fresh\n", markers=[b"fresh"])
            write(golden + ".old", b"")
        self.assertEqual(b"fresh\n", h.read_bytes(golden))
        with mock.patch.dict(os.environ, {h.UPDATE_ENV: "1"}), mock.patch("sys.stderr"):
            h.check_golden(golden, b"changed\n")
        self.assertEqual(b"changed\n", h.read_bytes(golden))

    def test_update_mode_does_not_write_when_markers_missing(self):
        golden = self.path("m.txt")
        with mock.patch.dict(os.environ, {h.UPDATE_ENV: "1"}), mock.patch("sys.stderr"):
            with self.assertRaises(AssertionError):
                h.check_golden(golden, b"", markers=[b"needed"])
        self.assertFalse(os.path.exists(golden))

    def test_masks_apply_to_both_sides(self):
        golden = self.path("mask.txt")
        write(golden, b"time 12:00:01 ok\n")
        masks = [(rb"\d\d:\d\d:\d\d", b"HH:MM:SS")]
        h.check_golden(golden, b"time 23:59:59 ok\n", masks=masks)
        self.assertEqual(b"x HH:MM:SS", h.apply_masks(b"x 01:02:03", masks))

    def test_assert_markers(self):
        h.assert_markers(b"abc", [b"a", b"c"])
        with self.assertRaises(AssertionError):
            h.assert_markers(b"abc", [b"zz"])

    def test_golden_dir_is_testdata_e2e(self):
        self.assertTrue(h.GOLDEN_DIR.endswith(os.path.join("bc64", "testdata", "e2e")))
        self.assertTrue(h.golden_path("x").endswith("x.golden.txt"))


LS_HEAD = b"\rlisting files of drive A:\n"


def ls_row(name, attrs="-R-X", numbers="0700 0F 0A 0E"):
    return ("\r%s %s %s\n" % (name, attrs, numbers)).encode("latin-1")


class DiscMasksTests(TempCase):
    def golden_with(self, data):
        path = self.path("m.golden.txt")
        write(path, data)
        return path

    def check(self, golden_data, actual):
        h.check_golden(self.golden_with(golden_data), actual, masks=h.DISC_MASKS)

    def assert_differs(self, golden_data, actual):
        with self.assertRaises(AssertionError):
            self.check(golden_data, actual)

    def test_masks_only_layout_numbers_of_an_ls_line(self):
        masked = h.apply_masks(ls_row("HELLOWRD.PRG"), h.DISC_MASKS)
        self.assertEqual(b"\rHELLOWRD.PRG -R-X SIZE TT SS LL\n", masked)
        self.assertEqual(masked, h.apply_masks(masked, h.DISC_MASKS))

    def test_masks_free_sector_figure_only(self):
        line = b"\rEA catalog entries free; 0120 sectors free...\n"
        self.assertEqual(b"\rEA catalog entries free; XXXX sectors free...\n",
                         h.apply_masks(line, h.DISC_MASKS))

    def test_masks_dot_only_lines(self):
        self.assertEqual(b"\r<dots>\n", h.apply_masks(b"\r.......\n", h.DISC_MASKS))
        self.assertEqual(b"\r<dots>\n\r<dots>\n", h.apply_masks(b"\r..\n\r.\n", h.DISC_MASKS))

    def test_masks_leave_other_text_untouched(self):
        text = (b"bcOS 1.2\nbooting from FDDlding\n\rbDOS 1.1 shell\n\r9FF5 bytes free\n"
                b"\rwith options 10...\n\rA>ls -a\n\rlisting files of drive A:\n")
        self.assertEqual(text, h.apply_masks(text, h.DISC_MASKS))

    def test_equal_up_to_layout_numbers_passes(self):
        a = LS_HEAD + ls_row("HELLOWRD.PRG") + b"\r..\n\rEA catalog entries free; 0120 sectors free...\n"
        b = (LS_HEAD + ls_row("HELLOWRD.PRG", numbers="0F00 20 03 1E")
             + b"\r.........\n\rEA catalog entries free; 0042 sectors free...\n")
        self.check(a, b)

    def test_missing_ls_line_fails(self):
        two = LS_HEAD + ls_row("HELLOWRD.PRG") + ls_row("TEXTED  .PRG")
        self.assert_differs(two, LS_HEAD + ls_row("HELLOWRD.PRG"))

    def test_wrong_attribute_fails(self):
        self.assert_differs(LS_HEAD + ls_row("HELLOWRD.PRG"),
                            LS_HEAD + ls_row("HELLOWRD.PRG", attrs="SR-X"))

    def test_renamed_file_fails(self):
        self.assert_differs(LS_HEAD + ls_row("HELLOWRD.PRG"), LS_HEAD + ls_row("HELLOWR2.PRG"))

    def test_changed_order_fails(self):
        a = ls_row("HELLOWRD.PRG")
        b = ls_row("TEXTED  .PRG")
        self.assert_differs(LS_HEAD + a + b, LS_HEAD + b + a)

    def test_removed_dot_line_fails(self):
        self.assert_differs(b"\rA>ls -a\n\r.......\n" + LS_HEAD, b"\rA>ls -a\n" + LS_HEAD)

    def test_changed_free_entries_count_fails(self):
        self.assert_differs(b"\rEA catalog entries free; 0120 sectors free...\n",
                            b"\rE9 catalog entries free; 0120 sectors free...\n")

    def test_changed_untouched_text_fails(self):
        self.assert_differs(b"\r9FF5 bytes free\n", b"\r9FF4 bytes free\n")


class ManifestHelperTests(TempCase):
    def test_planned_entries_follow_the_manifest(self):
        entries = h.planned_entries()
        names = [(e.name, e.ext) for e in entries]
        self.assertEqual(("BOOTSECT", "BIN"), names[0])
        self.assertIn(("THEODORE", "PRG"), names)
        self.assertEqual([h.ls_line(e) for e in entries],
                         [h.ls_line(e) for e in h.planned_entries(h.MANIFEST)])
        with self.assertRaises(KeyError):
            h.planned_entry("NOSUCH.FIL")

    def test_ls_line_formats_known_entries(self):
        from ftool_mkdisc import CatalogEntry as Planned
        self.assertEqual("BOOTSECT.BIN SR-- 0080 00 00 01",
                         h.ls_line(Planned(0, 0, 1, 0x81, "BOOTSECT", "BIN", None)))
        self.assertEqual("LS      .PRG SR-X 1D00 0C 00 3A",
                         h.ls_line(Planned(0, 12 * 16, 0x3A, 0x85, "LS", "PRG", None)))
        self.assertEqual("TEST    .B   -RW- 0100 2B 08 02",
                         h.ls_line(Planned(0, 43 * 16 + 8, 2, 0x03, "TEST", "B", None)))

    def test_ls_line_of_every_planned_entry_is_in_a_real_ls_session(self):
        session = h.golden_path("disc_ls_all", "in")
        out = h.run_session("disc_ls_all", session, disks={"a": h.OS_DISK})
        lines = out.decode("latin-1").split("\n")
        for entry in h.planned_entries():
            self.assertIn("\r" + h.ls_line(entry), lines)
        listed = [l for l in lines if h.apply_masks(l.encode("latin-1"), h.DISC_MASKS).endswith(b"SIZE TT SS LL")]
        self.assertEqual(len(h.planned_entries()), len(listed))


class SlowDecoratorTests(unittest.TestCase):
    def test_skips_without_variable(self):
        @h.slow
        def scenario(self_):
            raise AssertionError("must not run")

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(h.SLOW_ENV, None)
            decorated = h.slow(lambda s: None)
        self.assertTrue(getattr(decorated, "__unittest_skip__", False))

    def test_runs_with_variable(self):
        with mock.patch.dict(os.environ, {h.SLOW_ENV: "1"}):
            decorated = h.slow(lambda s: None)
        self.assertFalse(getattr(decorated, "__unittest_skip__", False))


class CatalogTests(TempCase):
    def test_reader_lists_known_files(self):
        rows = h.read_catalog(h.OS_DISK)
        names = {(r.name, r.ext) for r in rows}
        for known in [("HELLOWRD", "PRG"), ("TEXTED", "PRG"), ("TEST", "B"), ("BDOS", "SYS")]:
            self.assertIn(known, names)
        hello = [r for r in rows if r.name == "HELLOWRD"][0]
        planned = h.planned_entry("HELLOWRD.PRG")
        self.assertEqual((planned.track, planned.sector, planned.length, planned.attribs),
                         (hello.track, hello.sector, hello.length, hello.attributes))

    def test_disc_put_adds_entry_and_refuses_duplicate(self):
        disk = self.path("c.bdd")
        shutil.copyfile(h.OS_DISK, disk)
        before = h.read_catalog(disk)
        end = max(r.track * 16 + r.sector + r.length for r in before)
        row = h.disc_put(disk, "abc.b", b"x" * 130)
        after = h.read_catalog(disk)
        self.assertEqual(len(before) + 1, len(after))
        self.assertEqual(row, after[-1])
        self.assertEqual(("ABC", "B", 0x05, 2), (row.name, row.ext, row.attributes, row.length))
        self.assertEqual(end, row.track * 16 + row.sector)
        data = h.read_bytes(disk)
        self.assertEqual(b"x" * 130 + bytes(126), data[end * 128:end * 128 + 256])
        with self.assertRaises(ValueError):
            h.disc_put(disk, "ABC.B", b"y")
        with self.assertRaises(ValueError):
            h.disc_put(disk, "toolongname.b", b"y")

    def test_disc_put_refuses_full_disc(self):
        disk = self.path("f.bdd")
        shutil.copyfile(h.OS_DISK, disk)
        with self.assertRaises(ValueError):
            h.disc_put(disk, "big.b", bytes(255 * 128 * 5))
        with self.assertRaises(ValueError):
            h.disc_put(disk, "huge.b", bytes(256 * 128))

    def test_disc_put_refuses_full_catalog(self):
        disk = self.path("n.bdd")
        shutil.copyfile(h.OS_DISK, disk)
        image = bytearray(h.read_bytes(disk))
        for index in range(248):
            offset = 128 + index * 16
            image[offset + 1:offset + 4] = bytes([0, 0, 1])
        write(disk, bytes(image))
        with self.assertRaises(ValueError):
            h.disc_put(disk, "last.b", b"z")


if __name__ == "__main__":
    unittest.main()
