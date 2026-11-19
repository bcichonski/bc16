"""Tests of scripts/code_size.py. The programs of the unit tests live in temp trees with a temp
CSV; only the repo check reads the real sources and src/bc/code_size.csv (read-only).
Run from scripts/: python3 -m unittest discover -s tests -t . -p "test_*.py"
"""

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)
import code_size  # noqa: E402

ROOT = code_size.ROOT


def program(value):
    return "byte main()\n{\n    return %d;\n}\n" % value


class TempTree(unittest.TestCase):
    """A temp source root (src/bdos, src/bc/code) and a temp CSV path."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="test_code_size_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "root")
        os.makedirs(os.path.join(self.root, "src", "bdos"))
        os.makedirs(os.path.join(self.root, "src", "bc", "code"))
        self.csv = os.path.join(self.tmp, "code_size.csv")

    def write(self, rel, text):
        path = os.path.join(self.root, *rel.split("/"))
        with open(path, "w", encoding="utf8", newline="") as handle:
            handle.write(text)

    def run_main(self, *args, env=None):
        """Run code_size.main in-process; return (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        saved = dict(os.environ)
        try:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
            os.environ.update(env or {})
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = code_size.main(["--root", self.root, "--csv", self.csv] + list(args))
        finally:
            os.environ.clear()
            os.environ.update(saved)
        return code, out.getvalue(), err.getvalue()

    def csv_lines(self):
        with open(self.csv, "r", encoding="utf8", newline="") as handle:
            return handle.read().splitlines()


class RepoCheck(unittest.TestCase):
    def test_current_sources_match_the_committed_csv(self):
        results, failures = code_size.measure_all(ROOT)
        self.assertEqual(failures, {})
        latest = code_size.read_log(os.path.join(ROOT, code_size.CSV_REL))
        changes = code_size.compare(results, latest)
        message = "\n".join(code_size.describe(change, results) for change in changes)
        self.assertEqual(changes, [],
                         "code size differs from src/bc/code_size.csv:\n%s\nif intended, run: %s"
                         % (message, code_size.RECORD_COMMAND))

    def test_repo_discovers_the_known_programs(self):
        found = code_size.discover(ROOT)
        self.assertEqual(sum(key.startswith("bdos/") for key in found), 13)
        self.assertEqual(sum(key.startswith("code/") for key in found), 5)
        self.assertNotIn("bdos/std", found)
        self.assertNotIn("code/stdio", found)


class Discovery(TempTree):
    def test_skips_files_without_main_and_sorts_ids(self):
        self.write("src/bdos/zed.b", program(1))
        self.write("src/bdos/lib.b", "byte helper()\n{\n    return 1;\n}\n")
        self.write("src/bdos/notes.txt", "byte main()")
        self.write("src/bc/code/alpha.b", program(2))
        self.assertEqual(list(code_size.discover(self.root)), ["bdos/zed", "code/alpha"])


class Measuring(TempTree):
    def test_tiny_program_size_equals_the_btap_codelen(self):
        self.write("src/bdos/tiny.b", program(7))
        results, failures = code_size.measure_all(self.root)
        self.assertEqual(failures, {})
        found = results["bdos/tiny"]
        # build the same program with the real tools in a temp folder and read the .btap header
        work = os.path.join(self.tmp, "work")
        os.makedirs(work)
        shutil.copyfile(os.path.join(self.root, "src", "bdos", "tiny.b"), os.path.join(work, "tiny.b"))
        subprocess.run([sys.executable, os.path.join(ROOT, "src", "bc", "bc.py"),
                        os.path.join(work, "tiny.b")], check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, os.path.join(ROOT, "src", "bc81asmc", "bc81asmc.py"),
                        "--btap", os.path.join(work, "tiny.basm")], check=True,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        with open(os.path.join(work, "tiny.btap"), "rb") as handle:
            bits = handle.read()
        header = bytes(sum(bits[i * 8 + b] << b for b in range(8)) for i in range(11))
        codelen = header[8] * 256 + header[9]
        self.assertEqual(found.size, codelen)
        self.assertEqual(found.start, header[6] * 256 + header[7])
        self.assertEqual(len(found.sha), 12)

    def test_measuring_does_not_write_into_the_source_tree(self):
        self.write("src/bdos/tiny.b", program(1))
        code_size.measure_all(self.root)
        self.assertEqual(os.listdir(os.path.join(self.root, "src", "bdos")), ["tiny.b"])


class Modes(TempTree):
    def seed(self):
        self.write("src/bdos/one.b", program(1))
        self.write("src/bc/code/two.b", program(2))
        self.assertEqual(self.run_main("--record")[0], 0)

    def test_record_creates_header_and_one_row_per_program(self):
        self.seed()
        lines = self.csv_lines()
        self.assertEqual(lines[0], "date,program,start,bytes,basm_sha")
        self.assertEqual([line.split(",")[1] for line in lines[1:]], ["bdos/one", "code/two"])
        self.assertTrue(lines[1].split(",")[2].startswith("0x"))

    def test_record_is_idempotent_and_check_passes(self):
        self.seed()
        before = self.csv_lines()
        code, _, _ = self.run_main("--record")
        self.assertEqual(code, 0)
        self.assertEqual(self.csv_lines(), before)
        self.assertEqual(self.run_main("--check")[0], 0)

    def test_check_reports_a_size_change(self):
        self.seed()
        self.write("src/bdos/one.b", "byte main()\n{\n    byte a;\n    a <- 1;\n    return a;\n}\n")
        code, _, err = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("bdos/one", err)
        self.assertIn("->", err)
        self.assertNotIn("code/two", err)
        self.assertIn(code_size.RECORD_COMMAND, err)

    def test_check_reports_a_same_size_code_change(self):
        self.seed()
        self.write("src/bdos/one.b", program(3))
        code, _, err = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("bdos/one: code changed, same size", err)

    def test_report_exits_zero_when_sizes_differ_and_shows_the_delta(self):
        self.seed()
        self.write("src/bdos/one.b", "byte main()\n{\n    byte a;\n    a <- 1;\n    return a;\n}\n")
        code, out, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("| bdos/one |", out)
        self.assertIn("**total**", out)
        row = [line for line in out.splitlines() if line.startswith("| bdos/one |")][0]
        self.assertRegex(row.split("|")[-2].strip(), r"^\+\d+$")

    def test_check_and_record_handle_new_program(self):
        self.seed()
        self.write("src/bdos/three.b", program(3))
        code, _, err = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("bdos/three: new program", err)
        self.run_main("--record")
        self.assertEqual(len(self.csv_lines()), 4)
        self.assertEqual(self.run_main("--check")[0], 0)

    def test_removed_program_is_reported_and_recorded_as_gone(self):
        self.seed()
        os.remove(os.path.join(self.root, "src", "bdos", "one.b"))
        code, _, err = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("bdos/one: removed", err)
        self.run_main("--record")
        last = self.csv_lines()[-1].split(",")
        self.assertEqual(last[1], "bdos/one")
        self.assertEqual(last[3], "")
        self.assertEqual(self.run_main("--check")[0], 0)
        before = self.csv_lines()
        self.run_main("--record")
        self.assertEqual(self.csv_lines(), before)

    def test_record_appends_only_changed_rows(self):
        self.seed()
        self.write("src/bdos/one.b", program(3))
        self.run_main("--record")
        lines = self.csv_lines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[-1].split(",")[1], "bdos/one")

    def test_latest_row_wins_over_earlier_rows(self):
        self.write("src/bdos/one.b", program(1))
        results, _ = code_size.measure_all(self.root)
        found = results["bdos/one"]
        good = "2026-01-02,bdos/one,0x%04x,%d,%s" % (found.start, found.size, found.sha)
        stale = "2026-01-01,bdos/one,0x6000,1,abcdefabcdef"
        for rows in (stale + "\n" + good, good):
            with open(self.csv, "w", encoding="utf8", newline="") as handle:
                handle.write("date,program,start,bytes,basm_sha\n" + rows + "\n")
            self.assertEqual(self.run_main("--check")[0], 0)
        with open(self.csv, "w", encoding="utf8", newline="") as handle:
            handle.write("date,program,start,bytes,basm_sha\n" + good + "\n" + stale + "\n")
        self.assertEqual(self.run_main("--check")[0], 1)

    def test_step_summary_is_appended_when_set(self):
        self.seed()
        summary = os.path.join(self.tmp, "summary.md")
        with open(summary, "w", encoding="utf8") as handle:
            handle.write("existing\n")
        code, _, _ = self.run_main(env={"GITHUB_STEP_SUMMARY": summary})
        self.assertEqual(code, 0)
        with open(summary, "r", encoding="utf8") as handle:
            text = handle.read()
        self.assertTrue(text.startswith("existing\n"))
        self.assertIn("| bdos/one |", text)

    def test_a_program_that_fails_to_compile_fails_with_its_name_on_stderr(self):
        self.write("src/bdos/good.b", program(1))
        self.write("src/bdos/broken.b", "byte main()\n{\n    return ;;; (\n")
        for flag in ([], ["--check"], ["--record"]):
            code, _, err = self.run_main(*flag)
            self.assertNotEqual(code, 0, flag)
            self.assertIn("bdos/broken", err)
        self.assertFalse(os.path.exists(self.csv))


if __name__ == "__main__":
    unittest.main()
