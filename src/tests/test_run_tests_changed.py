"""Unit tests of run_tests.py --changed REF (injected path lists, a temp git repo; no boots)."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import run_tests  # noqa: E402

MODULES = ["tests.test_bc64_smoke", "tests.test_e2e_bcos", "tests.test_e2e_return"]
SUITES = [("emulator", "unit", "src", ["tests.test_a"]), ("e2e", "e2e", "src", MODULES)]


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false"]
                   + list(args), cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class ChangedOptionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name in run_tests.BUILT_OUTPUTS:
            path = os.path.join(tmp.name, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
        self.manifest = os.path.join(tmp.name, "disc.bddmanifest")
        with open(self.manifest, "w") as handle:
            handle.write("DISC.CAT  -  SR  role=catalog at=0/1\n")

    def run_main(self, argv, paths=(), bad_ref=False):
        calls, builds = [], []

        def runner(name, cwd, args, env=None):
            calls.append((name, list(args)))
            output = "Ran %d tests in 0.1s\n\nOK\n" % len(args)
            return True, run_tests.summarise(output, 0), output, 0

        def changed_paths(ref):
            if bad_ref:
                raise run_tests.BadRef("unknown revision")
            return list(paths)

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = run_tests.main(argv, suites=SUITES, runner=runner, environ={},
                                      manifest=self.manifest, changed_paths=changed_paths,
                                      build=lambda: builds.append(1) or (True, "built", "", 0))
            except SystemExit as exit_:
                code = exit_.code
        e2e = [args for name, args in calls if name == "e2e"]
        return code, e2e, builds, out.getvalue(), err.getvalue()

    def test_selects_only_affected_areas_and_prints_them(self):
        code, e2e, _builds, out, _err = self.run_main(
            ["--group", "e2e", "--jobs", "1", "--changed", "origin/master"],
            ["src/tests/test_e2e_bcos.py"])
        self.assertEqual(code, 0)
        self.assertEqual(e2e, [["tests.test_e2e_bcos"]])
        self.assertIn("changed since origin/master: bcos", out)

    def test_no_affected_area_passes_without_build_or_run(self):
        code, e2e, builds, out, _err = self.run_main(
            ["--group", "e2e", "--changed", "HEAD"], ["README.md", "docs/x.md"])
        self.assertEqual(code, 0)
        self.assertEqual(e2e, [])
        self.assertEqual(builds, [])
        self.assertIn("e2e        PASS: not run, no e2e area affected since HEAD", out)

    def test_area_without_modules_is_dropped(self):
        # a unit-test-only change triggers no area
        code, e2e, builds, out, _err = self.run_main(
            ["--group", "e2e", "--changed", "HEAD"], ["src/tests/test_something_unit.py"])
        self.assertEqual(code, 0)
        self.assertEqual(e2e, [])
        self.assertEqual(builds, [])

    def test_combines_with_happy_tier(self):
        _code, e2e, _b, _out, _err = self.run_main(
            ["--group", "e2e", "--jobs", "1", "--tier", "happy", "--changed", "HEAD"],
            ["src/tests/test_e2e_bcos.py"])
        (ids,) = e2e
        self.assertTrue(ids)
        self.assertTrue(all(i.startswith("tests.test_e2e_bcos") for i in ids))

    def test_mutually_exclusive_with_area(self):
        code, e2e, builds, _out, err = self.run_main(
            ["--group", "e2e", "--changed", "HEAD", "--area", "bcos"], ["x"])
        self.assertEqual(code, 2)
        self.assertEqual((e2e, builds), ([], []))
        self.assertIn("mutually exclusive", err)

    def test_invalid_ref_exits_2_with_message(self):
        code, e2e, builds, _out, err = self.run_main(
            ["--group", "e2e", "--changed", "no-such-ref"], bad_ref=True)
        self.assertEqual(code, 2)
        self.assertEqual((e2e, builds), ([], []))
        self.assertIn("no-such-ref", err)

    def test_unit_suites_unaffected_by_changed(self):
        _code, _e2e, _b, out, _err = self.run_main(["--changed", "HEAD", "--no-build"], ["README.md"])
        self.assertIn("emulator   PASS", out)


class GitChangedPathsTests(unittest.TestCase):
    def test_merge_base_diff_uncommitted_and_untracked_not_ignored(self):
        with tempfile.TemporaryDirectory() as repo:
            def write(name, text="x\n"):
                path = os.path.join(repo, name)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as handle:
                    handle.write(text)

            git(repo, "init", "-q", "-b", "main")
            write(".gitignore", "ignored.txt\n")
            write("a.txt")
            write("b.txt")
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "base")
            git(repo, "branch", "base")
            write("c.txt")
            git(repo, "add", "c.txt")
            git(repo, "commit", "-q", "-m", "committed")
            write("a.txt", "changed\n")      # uncommitted, tracked
            write("sub/new.txt")             # untracked
            write("ignored.txt")             # untracked but ignored
            paths = run_tests.git_changed_paths("base", cwd=repo)
            self.assertEqual(paths, ["a.txt", "c.txt", "sub/new.txt"])

    def test_invalid_ref_raises(self):
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q", "-b", "main")
            git(repo, "commit", "-q", "--allow-empty", "-m", "base")
            with self.assertRaises(run_tests.BadRef):
                run_tests.git_changed_paths("no-such-ref", cwd=repo)


if __name__ == "__main__":
    unittest.main()
