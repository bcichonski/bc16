#!/usr/bin/env python3
"""Run the component test suites and report one line per suite.

Suites: emulator, ftool, assembler, compiler (group "unit") and e2e (group "e2e").

Usage (from any directory):
    python3 run_tests.py [--group unit|e2e|all]

Each suite runs as a subprocess with the interpreter that started this script and
with its own working directory, because the suites use flat imports.
The src suites are chosen by rule (see select_src_modules), not by a fixed file list.
When the environment variable GITHUB_STEP_SUMMARY names a file, a Markdown table
of the results is appended to it.
Exit code is 0 only if every selected suite passes. Standard library only.
"""

import argparse
import glob
import importlib.util
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

GROUPS = ("unit", "e2e", "all")


def select_src_modules(src_dir):
    """Partition the test modules under src_dir into {suite name: [module names]}.

    e2e:      test_e2e_*.py and test_bc64_smoke.py
    ftool:    test_ftool.py
    emulator: bc64/test_*.py and every other test_*.py
    Module names are importable with src_dir as the working directory.
    """
    e2e, ftool, emulator = [], [], []
    for path in sorted(glob.glob(os.path.join(src_dir, "test_*.py"))):
        module = os.path.splitext(os.path.basename(path))[0]
        if module.startswith("test_e2e_") or module == "test_bc64_smoke":
            e2e.append(module)
        elif module == "test_ftool":
            ftool.append(module)
        else:
            emulator.append(module)
    bc64 = [
        "bc64." + os.path.splitext(os.path.basename(path))[0]
        for path in sorted(glob.glob(os.path.join(src_dir, "bc64", "test_*.py")))
    ]
    return {"emulator": bc64 + emulator, "ftool": ftool, "e2e": e2e}


def build_suites(root=ROOT):
    """Return [(name, group, cwd relative to root, unittest arguments)] in report order."""
    modules = select_src_modules(os.path.join(root, "src"))
    discover = ["discover", "-s", ".", "-t", ".", "-p", "*_tests.py"]
    return [
        ("emulator", "unit", "src", modules["emulator"]),
        ("ftool", "unit", "src", modules["ftool"]),
        ("assembler", "unit", os.path.join("src", "bc81asmc"), discover),
        ("compiler", "unit", os.path.join("src", "bc"), discover),
        ("e2e", "e2e", "src", modules["e2e"]),
    ]


def filter_suites(suites, group):
    """Keep the suites belonging to group ("all" keeps every suite)."""
    if group == "all":
        return list(suites)
    return [suite for suite in suites if suite[1] == group]


RAN_RE = re.compile(r"^Ran (\d+) tests?\b", re.MULTILINE)
STATUS_RE = re.compile(r"^(OK|FAILED)\b.*$", re.MULTILINE)


def check_parsy():
    """Return True if parsy can be imported by this interpreter (without importing it)."""
    return importlib.util.find_spec("parsy") is not None


def summarise(output, returncode):
    """Build the human-readable summary from unittest's output."""
    ran = RAN_RE.findall(output)
    statuses = STATUS_RE.findall(output)
    status_line = ""
    matches = list(STATUS_RE.finditer(output))
    if matches:
        status_line = matches[-1].group(0).strip()
    parts = []
    if ran:
        parts.append("Ran %s tests" % ran[-1])
    if status_line:
        parts.append(status_line)
    if not parts or (returncode != 0 and not statuses):
        parts.append("exit code %d" % returncode)
    return ", ".join(parts)


COUNT_RE = re.compile(r"(failures|errors|skipped|expected failures|unexpected successes)=(\d+)")


def parse_counts(output, returncode):
    """Parse unittest output into a dict of counts, or None if no "Ran" line (crash)."""
    ran = RAN_RE.findall(output)
    if not ran:
        return None
    counts = {"ran": int(ran[-1]), "failures": 0, "errors": 0, "skipped": 0,
              "expected failures": 0, "unexpected successes": 0}
    matches = list(STATUS_RE.finditer(output))
    if matches:
        for key, value in COUNT_RE.findall(matches[-1].group(0)):
            counts[key] = int(value)
    return counts


def run_suite(name, rel_cwd, args):
    """Run one suite. Returns (passed, summary, captured_output, returncode)."""
    cwd = os.path.join(ROOT, rel_cwd)
    command = [sys.executable, "-m", "unittest"] + list(args)
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        return False, "could not start (%s)" % error, "", -1
    output = completed.stdout or ""
    passed = completed.returncode == 0
    return passed, summarise(output, completed.returncode), output, completed.returncode


def render_table(results):
    """Render results [(name, passed, counts_or_None, returncode)] as a Markdown table."""
    lines = [
        "| Suite | Result | Tests | Failures | Errors | Skipped | Expected failures |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, passed, counts, returncode in results:
        result = "PASS" if passed else "FAIL"
        if counts is None:
            lines.append("| %s | %s | exit code %d | - | - | - | - |"
                         % (name, result, returncode))
        else:
            lines.append("| %s | %s | %d | %d | %d | %d | %d |" % (
                name, result, counts["ran"], counts["failures"], counts["errors"],
                counts["skipped"], counts["expected failures"]))
    return "\n".join(lines) + "\n"


def write_summary(results, path):
    """Append the Markdown table to path; do nothing if path is empty or None."""
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("### Test results\n\n" + render_table(results) + "\n")


def main(argv=None, suites=None, runner=run_suite, environ=None):
    parser = argparse.ArgumentParser(description="Run the component test suites.")
    parser.add_argument("--group", choices=GROUPS, default="all",
                        help="unit = emulator/ftool/assembler/compiler, e2e = end-to-end, all = both")
    options = parser.parse_args(argv)
    environ = os.environ if environ is None else environ

    if not check_parsy():
        sys.stderr.write(
            "parsy is not installed for %s.\n"
            "Install it with: pip install -r requirements.txt\n" % sys.executable)
        return 1

    if suites is None:
        suites = build_suites()
    selected = filter_suites(suites, options.group)

    all_passed = True
    results = []
    for name, _group, rel_cwd, args in selected:
        if not args:
            passed, summary, output, returncode = False, "no test modules found", "", -1
        else:
            passed, summary, output, returncode = runner(name, rel_cwd, args)
        all_passed = all_passed and passed
        results.append((name, passed, parse_counts(output, returncode), returncode))
        label = "PASS" if passed else "FAIL"
        print("%-10s %s: %s" % (name, label, summary))
        if not passed and output:
            # Show the failing suite's own output so the failures are visible.
            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")
        sys.stdout.flush()

    write_summary(results, environ.get("GITHUB_STEP_SUMMARY"))
    print("ALL PASSED" if all_passed else "SOME SUITES FAILED")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
