"""Unit tests of the pure logic in run_tests.py (never spawns the real suites)."""

import contextlib
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, ROOT)
import run_tests  # noqa: E402


def touch(directory, *names):
    for name in names:
        path = os.path.join(directory, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()


class SelectionTests(unittest.TestCase):
    def test_rules_on_synthetic_tree(self):
        with tempfile.TemporaryDirectory() as src:
            touch(src, "bc64/tests/test_bc64_cli.py", "tests/test_new_thing.py",
                  "tests/test_ftool.py", "tests/test_e2e_a.py", "tests/test_e2e_new.py",
                  "tests/test_bc64_smoke.py", "tests/e2e_harness.py", "ftool.py",
                  "bc64/tests/test_cpu.py", "bc64/bc64_io.py", "test_stray.py")
            modules = run_tests.select_src_modules(src)
        self.assertEqual(modules["emulator"],
                         ["bc64.tests.test_bc64_cli", "bc64.tests.test_cpu", "tests.test_new_thing"])
        self.assertEqual(modules["ftool"], ["tests.test_ftool"])
        self.assertEqual(modules["e2e"],
                         ["tests.test_bc64_smoke", "tests.test_e2e_a", "tests.test_e2e_new"])

    def test_real_tree_partition_has_no_overlap_and_no_gap(self):
        modules = run_tests.select_src_modules(SRC)
        selected = [m for names in modules.values() for m in names]
        self.assertEqual(len(selected), len(set(selected)))
        expected = set()
        for name in os.listdir(os.path.join(SRC, "tests")):
            if name.startswith("test_") and name.endswith(".py"):
                expected.add("tests." + name[:-3])
        for name in os.listdir(os.path.join(SRC, "bc64", "tests")):
            if name.startswith("test_") and name.endswith(".py"):
                expected.add("bc64.tests." + name[:-3])
        orphans = [name for name in os.listdir(SRC)
                   if name.startswith("test_") and name.endswith(".py")]
        self.assertEqual(orphans, [])
        self.assertEqual(set(selected), expected)
        self.assertIn("tests.test_run_tests", modules["emulator"])
        self.assertIn("tests.test_bc64_smoke", modules["e2e"])
        self.assertIn("tests.test_ftool", modules["ftool"])

    def test_suite_order_and_groups(self):
        suites = run_tests.build_suites()
        self.assertEqual([s[0] for s in suites],
                         ["emulator", "ftool", "assembler", "compiler", "release", "e2e"])
        self.assertEqual([s[1] for s in suites],
                         ["unit", "unit", "unit", "unit", "unit", "e2e"])

    def test_group_filtering(self):
        suites = run_tests.build_suites()
        names = lambda group: [s[0] for s in run_tests.filter_suites(suites, group)]
        self.assertEqual(names("unit"), ["emulator", "ftool", "assembler", "compiler", "release"])
        self.assertEqual(names("e2e"), ["e2e"])
        self.assertEqual(names("all"),
                         ["emulator", "ftool", "assembler", "compiler", "release", "e2e"])

    def test_release_suite_discovers_scripts_tests(self):
        suites = {s[0]: s for s in run_tests.build_suites()}
        _name, group, cwd, args = suites["release"]
        self.assertEqual((group, cwd), ("unit", "scripts"))
        self.assertEqual(args[:3], ["discover", "-s", "tests"])
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "scripts", "tests", "__init__.py")))


class ParseTests(unittest.TestCase):
    def test_ok(self):
        out = "....\n" + "-" * 70 + "\nRan 12 tests in 0.1s\n\nOK\n"
        counts = run_tests.parse_counts(out, 0)
        self.assertEqual(counts["ran"], 12)
        self.assertEqual(counts["failures"] + counts["errors"] + counts["skipped"], 0)

    def test_failed_with_failures_and_errors(self):
        out = "Ran 10 tests in 0.1s\n\nFAILED (failures=2, errors=3)\n"
        counts = run_tests.parse_counts(out, 1)
        self.assertEqual((counts["ran"], counts["failures"], counts["errors"]), (10, 2, 3))

    def test_skipped_and_expected_failures(self):
        out = "Ran 328 tests in 3s\n\nOK (skipped=1, expected failures=6)\n"
        counts = run_tests.parse_counts(out, 0)
        self.assertEqual(counts["skipped"], 1)
        self.assertEqual(counts["expected failures"], 6)

    def test_unexpected_successes(self):
        out = "Ran 4 tests in 1s\n\nFAILED (unexpected successes=1)\n"
        self.assertEqual(run_tests.parse_counts(out, 1)["unexpected successes"], 1)

    def test_single_test_wording(self):
        self.assertEqual(run_tests.parse_counts("Ran 1 test in 0.1s\n\nOK\n", 0)["ran"], 1)

    def test_crash_without_ran_line(self):
        self.assertIsNone(run_tests.parse_counts("Traceback (most recent call last):\n", 1))


class TableTests(unittest.TestCase):
    def test_render_table(self):
        ok = {"ran": 5, "failures": 0, "errors": 0, "skipped": 1,
              "expected failures": 2, "unexpected successes": 0}
        bad = {"ran": 7, "failures": 1, "errors": 2, "skipped": 0,
               "expected failures": 0, "unexpected successes": 0}
        table = run_tests.render_table([
            ("emulator", True, ok, 0),
            ("e2e", False, bad, 1),
            ("compiler", False, None, 3),
        ])
        lines = table.splitlines()
        self.assertTrue(lines[0].startswith("| Suite | Result | Tests |"))
        self.assertEqual(lines[1].count("|"), lines[0].count("|"))
        self.assertEqual(lines[2], "| emulator | PASS | 5 | 0 | 0 | 1 | 2 |")
        self.assertEqual(lines[3], "| e2e | FAIL | 7 | 1 | 2 | 0 | 0 |")
        self.assertIn("exit code 3", lines[4])
        self.assertIn("FAIL", lines[4])

    def test_write_summary_appends(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "summary.md")
            with open(path, "w") as handle:
                handle.write("existing\n")
            run_tests.write_summary([("x", True, None, 0)], path)
            text = open(path).read()
        self.assertTrue(text.startswith("existing\n"))
        self.assertIn("| x |", text)

    def test_write_summary_noop_without_path(self):
        run_tests.write_summary([("x", True, None, 0)], None)
        run_tests.write_summary([("x", True, None, 0)], "")


class MainTests(unittest.TestCase):
    SUITES = [
        ("a", "unit", "src", ["m1"]),
        ("b", "unit", "src", ["m2"]),
        ("c", "e2e", "src", ["m3"]),
    ]

    def run_main(self, argv, runner, environ):
        calls = []

        def wrapped(name, cwd, args):
            calls.append(name)
            return runner(name, cwd, args)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run_tests.main(argv, suites=self.SUITES, runner=wrapped, environ=environ)
        return code, calls, out.getvalue()

    @staticmethod
    def passing(name, cwd, args):
        return True, "Ran 2 tests, OK", "Ran 2 tests in 0s\n\nOK\n", 0

    def test_all_pass(self):
        code, calls, out = self.run_main([], self.passing, {})
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["a", "b", "c"])
        self.assertIn("ALL PASSED", out)

    def test_group_runs_only_its_suites(self):
        _, calls, _ = self.run_main(["--group", "e2e"], self.passing, {})
        self.assertEqual(calls, ["c"])
        _, calls, _ = self.run_main(["--group", "unit"], self.passing, {})
        self.assertEqual(calls, ["a", "b"])

    def test_failing_suite_gives_nonzero_exit(self):
        def runner(name, cwd, args):
            if name == "b":
                return (False, "Ran 3 tests, FAILED (failures=1)",
                        "Ran 3 tests in 0s\n\nFAILED (failures=1)\n", 1)
            return self.passing(name, cwd, args)

        code, calls, out = self.run_main([], runner, {})
        self.assertEqual(code, 1)
        self.assertEqual(calls, ["a", "b", "c"])
        self.assertIn("SOME SUITES FAILED", out)

    def test_summary_written_only_when_env_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.md")
            self.run_main(["--group", "unit"], self.passing, {"GITHUB_STEP_SUMMARY": path})
            text = open(path).read()
            self.assertIn("| a | PASS | 2 |", text)
            self.assertIn("| b | PASS | 2 |", text)
            self.assertNotIn("| c |", text)
            os.remove(path)
            self.run_main([], self.passing, {})
            self.assertFalse(os.path.exists(path))


class DiscSourceHintTests(unittest.TestCase):
    E2E_SUITES = [("e2e", "e2e", "src", ["tests.test_x"]), ("ftool", "unit", "src", ["tests.test_y"])]

    @staticmethod
    def write_manifest(directory, sources):
        path = os.path.join(directory, "disc.bddmanifest")
        lines = ["# comment", "", "DISC.CAT  -  SR  role=catalog at=0/1"]
        lines += ["%s.PRG  %s  RX" % (os.path.basename(s).upper(), s) for s in sources]
        with open(path, "w") as handle:
            handle.write("\n".join(lines) + "\n")
        return path

    def run_main(self, manifest):
        calls = []

        def runner(name, cwd, args):
            calls.append(name)
            return True, "Ran 1 test, OK", "Ran 1 test in 0s\n\nOK\n", 0

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run_tests.main(["--no-build"], suites=self.E2E_SUITES, runner=runner, environ={},
                                  manifest=manifest)
        return code, calls, out.getvalue()

    def test_missing_source_is_reported_first_one_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            touch(tmp, "bdos/b.sectors")
            manifest = self.write_manifest(tmp, ["bdos/a.sectors", "bdos/b.sectors", "bdos/c.sectors"])
            self.assertEqual(run_tests.missing_disc_source(manifest), "bdos/a.sectors")

    def test_catalog_dash_and_comments_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.write_manifest(tmp, [])
            self.assertIsNone(run_tests.missing_disc_source(manifest))

    def test_all_sources_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            touch(tmp, "bdos/a.sectors", "bdos/b.sectors")
            manifest = self.write_manifest(tmp, ["bdos/a.sectors", "bdos/b.sectors"])
            self.assertIsNone(run_tests.missing_disc_source(manifest))

    def test_e2e_fails_with_hint_and_does_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.write_manifest(tmp, ["bdos/a.sectors"])
            code, calls, out = self.run_main(manifest)
        self.assertEqual(code, 1)
        self.assertEqual(calls, ["ftool"])
        self.assertIn("e2e        FAIL", out)
        self.assertIn("bdos/a.sectors", out)
        self.assertIn(run_tests.PIPELINE, out)
        self.assertIn("SOME SUITES FAILED", out)

    def test_e2e_runs_when_sources_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            touch(tmp, "bdos/a.sectors", *run_tests.BUILT_OUTPUTS)
            manifest = self.write_manifest(tmp, ["bdos/a.sectors"])
            code, calls, out = self.run_main(manifest)
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["e2e", "ftool"])
        self.assertIn("ALL PASSED", out)


class BuildStepTests(unittest.TestCase):
    SUITES = [("emulator", "unit", "src", ["tests.test_a"]), ("e2e", "e2e", "src", ["tests.test_x"]),
              ("ftool", "unit", "src", ["tests.test_y"])]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        touch(self.tmp.name, "bdos/a.sectors", *run_tests.BUILT_OUTPUTS)
        self.manifest = DiscSourceHintTests.write_manifest(self.tmp.name, ["bdos/a.sectors"])

    def run_main(self, argv, build_ok=True):
        events = []

        def runner(name, cwd, args):
            events.append("suite:" + name)
            return True, "Ran 1 test, OK", "Ran 1 test in 0s\n\nOK\n", 0

        def build():
            events.append("build")
            if build_ok:
                return True, "built", "", 0
            return False, "exit code 2", "compiler exploded\n", 2

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run_tests.main(argv, suites=self.SUITES, runner=runner, environ={},
                                  manifest=self.manifest, build=build)
        return code, events, out.getvalue()

    def test_all_builds_once_before_the_suites(self):
        code, events, out = self.run_main([])
        self.assertEqual(code, 0)
        self.assertEqual(events, ["build", "suite:emulator", "suite:e2e", "suite:ftool"])
        self.assertIn("build      PASS", out)

    def test_e2e_group_builds_once_before_e2e(self):
        code, events, _out = self.run_main(["--group", "e2e"])
        self.assertEqual(code, 0)
        self.assertEqual(events, ["build", "suite:e2e"])

    def test_unit_group_never_builds(self):
        code, events, out = self.run_main(["--group", "unit"])
        self.assertEqual(code, 0)
        self.assertEqual(events, ["suite:emulator", "suite:ftool"])
        self.assertNotIn("build", out)

    def test_no_build_skips_the_build(self):
        code, events, _out = self.run_main(["--no-build"])
        self.assertEqual(code, 0)
        self.assertNotIn("build", events)
        self.assertIn("suite:e2e", events)

    def test_build_failure_fails_e2e_but_other_suites_run(self):
        code, events, out = self.run_main([], build_ok=False)
        self.assertEqual(code, 1)
        self.assertEqual(events, ["build", "suite:emulator", "suite:ftool"])
        self.assertIn("build      FAIL", out)
        self.assertIn("compiler exploded", out)
        self.assertIn("e2e        FAIL: not run, the build failed", out)
        self.assertIn("SOME SUITES FAILED", out)

    def test_no_build_with_missing_output_names_path_and_build_command(self):
        for missing in run_tests.BUILT_OUTPUTS:
            with self.subTest(missing=missing):
                os.remove(os.path.join(self.tmp.name, missing))
                code, events, out = self.run_main(["--no-build"])
                self.assertEqual(code, 1)
                self.assertNotIn("suite:e2e", events)
                self.assertIn("e2e        FAIL", out)
                self.assertIn(missing, out)
                self.assertIn(run_tests.PIPELINE, out)
                touch(self.tmp.name, missing)

    def test_no_build_with_missing_manifest_source_fails_e2e(self):
        os.remove(os.path.join(self.tmp.name, "bdos/a.sectors"))
        code, events, out = self.run_main(["--no-build"])
        self.assertEqual(code, 1)
        self.assertNotIn("suite:e2e", events)
        self.assertIn("bdos/a.sectors", out)


if __name__ == "__main__":
    unittest.main()
