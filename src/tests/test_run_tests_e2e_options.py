"""Unit tests of run_tests.py's e2e options --tier, --area and --jobs (fake runners, no boots)."""

import contextlib
import io
import os
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import run_tests  # noqa: E402

AREAS = run_tests.E2E_AREAS

MODULES = ["tests.test_bc64_smoke", "tests.test_e2e_bcos", "tests.test_e2e_harness",
           "tests.test_e2e_return", "tests.test_e2e_unmapped_new"]


def touch(directory, *names):
    for name in names:
        path = os.path.join(directory, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()


def ok_output(ran, extra=""):
    return "Ran %d test%s in 0.1s\n\nOK%s\n" % (ran, "" if ran == 1 else "s", extra)


def result(output, returncode=0):
    """A fake run_suite result whose summary is what run_suite would make of output."""
    return returncode == 0, run_tests.summarise(output, returncode), output, returncode


class E2eOptionsBase(unittest.TestCase):
    SUITES = [("emulator", "unit", "src", ["tests.test_a"]), ("e2e", "e2e", "src", MODULES)]

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        touch(tmp.name, *run_tests.BUILT_OUTPUTS)
        self.manifest = os.path.join(tmp.name, "disc.bddmanifest")
        with open(self.manifest, "w") as handle:
            handle.write("DISC.CAT  -  SR  role=catalog at=0/1\n")

    def run_main(self, argv, result_for=None, suites=None):
        """Run main with a fake runner; result_for(args) -> (passed, summary, output, rc)."""
        calls = []
        lock = threading.Lock()

        def default(args):
            return result(ok_output(len(args)))

        def runner(name, cwd, args, env=None):
            with lock:
                calls.append((name, list(args), None if env is None else env.get("BC64_UPDATE_GOLDEN")))
            return (result_for or default)(args)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run_tests.main(argv, suites=suites or self.SUITES, runner=runner, environ={},
                                  manifest=self.manifest, build=lambda: (True, "built", "", 0))
        return code, calls, out.getvalue()

    @staticmethod
    def e2e_calls(calls):
        return [args for name, args, _env in calls if name == "e2e"]


class TierTests(E2eOptionsBase):
    def test_happy_tier_passes_only_happy_ids(self):
        _code, calls, _out = self.run_main(["--no-build", "--tier", "happy", "--jobs", "1"])
        (args,) = self.e2e_calls(calls)
        expected = []
        for module in MODULES:
            expected += ["tests." + i for i in AREAS.happy_ids(module)]
        self.assertEqual(args, expected)
        self.assertIn("tests.test_bc64_smoke", args)
        self.assertIn("tests.test_e2e_bcos.BcosMonitorTests.test_boot_and_unknown_command", args)
        self.assertNotIn("tests.test_e2e_bcos", args)
        self.assertFalse(any(a.startswith("tests.test_e2e_unmapped_new") for a in args))

    def test_happy_tier_with_jobs_runs_one_call_per_module_with_its_ids(self):
        _code, calls, _out = self.run_main(["--no-build", "--tier", "happy", "--jobs", "4"])
        got = sorted(self.e2e_calls(calls))
        expected = sorted(["tests." + i for i in AREAS.happy_ids(m)]
                          for m in MODULES if AREAS.happy_ids(m))
        self.assertEqual(got, expected)

    def test_full_tier_is_default_and_runs_every_module_including_unmapped(self):
        _code, calls, _out = self.run_main(["--no-build", "--jobs", "1"])
        self.assertEqual(self.e2e_calls(calls), [MODULES])

    def test_unit_suites_are_unaffected_by_tier_and_area(self):
        _code, calls, _out = self.run_main(["--no-build", "--tier", "happy", "--area", "bcos"])
        self.assertIn(("emulator", ["tests.test_a"], None), calls)


class AreaTests(E2eOptionsBase):
    def test_area_filter_keeps_only_that_areas_modules(self):
        _code, calls, _out = self.run_main(["--no-build", "--area", "bcos", "--jobs", "1"])
        self.assertEqual(self.e2e_calls(calls), [["tests.test_e2e_bcos"]])

    def test_area_is_repeatable(self):
        _code, calls, _out = self.run_main(
            ["--no-build", "--area", "bcos", "--area", "compiler", "--jobs", "1"])
        self.assertEqual(self.e2e_calls(calls), [["tests.test_e2e_bcos", "tests.test_e2e_return"]])

    def test_area_with_happy_tier(self):
        _code, calls, _out = self.run_main(
            ["--no-build", "--area", "emulator", "--tier", "happy", "--jobs", "1"])
        self.assertEqual(self.e2e_calls(calls),
                         [["tests." + i for i in AREAS.happy_ids("test_e2e_harness")]])

    def test_area_without_modules_fails_and_does_not_build_or_run(self):
        built = []
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run_tests.main(["--group", "e2e", "--area", "assembler"], suites=self.SUITES,
                                  runner=lambda *a, **k: self.fail("ran"), environ={},
                                  manifest=self.manifest,
                                  build=lambda: built.append(1) or (True, "built", "", 0))
        self.assertEqual(code, 1)
        self.assertEqual(built, [])
        self.assertIn("e2e        FAIL: no e2e tests selected", out.getvalue())

    def test_select_e2e_pure(self):
        self.assertEqual(run_tests.select_e2e(MODULES, "full", ["compiler"]),
                         [("tests.test_e2e_return", ["tests.test_e2e_return"])])
        self.assertEqual(run_tests.select_e2e(["tests.test_e2e_unmapped_new"], "full", None),
                         [("tests.test_e2e_unmapped_new", ["tests.test_e2e_unmapped_new"])])
        self.assertEqual(run_tests.select_e2e(["tests.test_e2e_unmapped_new"], "full", ["bdos"]), [])


class JobsTests(E2eOptionsBase):
    SUITES = [("e2e", "e2e", "src", MODULES)]

    @staticmethod
    def module_results(args):
        """Per-module fake results; one module has an expected failure, one a skip."""
        module = args[0].split(".")[1]
        if module == "test_e2e_bcos":
            return result(ok_output(3, " (expected failures=1)"))
        if module == "test_e2e_harness":
            return result(ok_output(1, " (skipped=2)"))
        return result(ok_output(2))

    def summary_line(self, out):
        return [line for line in out.splitlines() if line.startswith("e2e ")][-1]

    def test_parallel_merges_counts_and_summary_like_sequential(self):
        def sequential(args):
            return result(ok_output(10, " (skipped=2, expected failures=1)"))

        with tempfile.TemporaryDirectory() as tmp:
            summary_seq = os.path.join(tmp, "seq.md")
            summary_par = os.path.join(tmp, "par.md")
            code1, calls1, out1 = self.run_main(["--no-build", "--jobs", "1"], sequential)
            code4, calls4, out4 = self.run_main(["--no-build", "--jobs", "4"], self.module_results)
            self.assertEqual((code1, code4), (0, 0))
            self.assertEqual(len(self.e2e_calls(calls1)), 1)
            self.assertEqual(len(self.e2e_calls(calls4)), len(MODULES))
            self.assertEqual(self.summary_line(out1), self.summary_line(out4))
            self.assertEqual(self.summary_line(out4),
                             "e2e        PASS: Ran 10 tests, OK (skipped=2, expected failures=1)")
            self.assertIn("ALL PASSED", out4)
            self.assertNotIn("Ran 3 tests", out4)  # passing modules' output is not printed
            for path, argv, fake in ((summary_seq, ["--jobs", "1"], sequential),
                                     (summary_par, ["--jobs", "4"], self.module_results)):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    run_tests.main(["--no-build"] + argv, suites=self.SUITES,
                                   runner=lambda n, c, a, env=None, f=fake: f(a),
                                   environ={"GITHUB_STEP_SUMMARY": path}, manifest=self.manifest)
            with open(summary_seq) as seq, open(summary_par) as par:
                self.assertEqual(seq.read(), par.read())

    def test_one_failing_module_fails_the_suite_and_shows_its_output(self):
        def results(args):
            if args == ["tests.test_e2e_return"]:
                return (False, "", "FAIL: test_x (tests.test_e2e_return.ReturnTests)\nboom\n"
                        "Ran 2 tests in 0.1s\n\nFAILED (failures=1)\n", 1)
            return self.module_results(args)

        code, _calls, out = self.run_main(["--no-build", "--jobs", "3"], results)
        self.assertEqual(code, 1)
        self.assertEqual(self.summary_line(out),
                         "e2e        FAIL: Ran 10 tests, FAILED (failures=1, skipped=2, "
                         "expected failures=1)")
        self.assertIn("tests.test_e2e_return", out)
        self.assertIn("boom", out)
        self.assertNotIn("Ran 3 tests", out)
        self.assertIn("SOME SUITES FAILED", out)

    def test_crashing_module_counts_as_an_error(self):
        def results(args):
            if args == ["tests.test_e2e_bcos"]:
                return False, "", "Traceback (most recent call last):\nImportError: nope\n", 1
            return result(ok_output(2))

        code, _calls, out = self.run_main(["--no-build", "--jobs", "2"], results)
        self.assertEqual(code, 1)
        self.assertEqual(self.summary_line(out), "e2e        FAIL: Ran 8 tests, FAILED (errors=1)")
        self.assertIn("ImportError: nope", out)

    def test_update_golden_forces_one_job(self):
        _code, calls, _out = self.run_main(["--no-build", "--update-golden", "--jobs", "8"])
        e2e = [c for c in calls if c[0] == "e2e"]
        self.assertEqual(len(e2e), 1)
        self.assertEqual(e2e[0][1], MODULES)
        self.assertEqual(e2e[0][2], "1")

    def test_default_jobs_is_cpu_count(self):
        parser_default = max(1, os.cpu_count() or 1)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            run_tests.main(["--help"])
        self.assertIn("default: the number of CPUs, %d" % parser_default, out.getvalue())
        _code, calls, _out = self.run_main(["--no-build"])
        expected = 1 if parser_default == 1 else len(MODULES)
        self.assertEqual(len(self.e2e_calls(calls)), expected)

    def test_merge_results_single_test_wording(self):
        units = [("tests.a", ["tests.a"]), ("tests.b", ["tests.b"])]
        passed, summary, output, code = run_tests.merge_results(
            units, [(True, "", ok_output(1), 0), (True, "", "Ran 0 tests in 0s\n\nOK\n", 0)])
        self.assertEqual((passed, code, summary), (True, 0, "Ran 1 tests, OK"))
        self.assertIn("\nRan 1 test in ", output)


class ArgumentTests(unittest.TestCase):
    def parse_error(self, argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            run_tests.main(argv)
        self.assertEqual(raised.exception.code, 2)
        return err.getvalue()

    def test_invalid_tier(self):
        self.assertIn("--tier", self.parse_error(["--tier", "smoke"]))

    def test_invalid_area(self):
        self.assertIn("--area", self.parse_error(["--area", "kernel"]))

    def test_jobs_must_be_a_positive_integer(self):
        for value in ("0", "-2", "many"):
            with self.subTest(value=value):
                self.assertIn("--jobs", self.parse_error(["--jobs", value]))

    def test_help_describes_the_options(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            run_tests.main(["--help"])
        text = out.getvalue()
        for option in ("--tier", "--area", "--jobs", "happy") + AREAS.AREAS:
            self.assertIn(option, text)

    def test_docstring_describes_the_options(self):
        for option in ("--tier", "--area", "--jobs"):
            self.assertIn(option, run_tests.__doc__)


if __name__ == "__main__":
    unittest.main()
