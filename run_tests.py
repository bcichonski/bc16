#!/usr/bin/env python3
"""Run all three test suites (emulator, assembler, compiler) and report one line per suite.

Usage (from any directory):
    python3 run_tests.py

Each suite runs as a subprocess with the interpreter that started this script and
with its own working directory, because the suites use flat imports.
Exit code is 0 only if every suite passes. Standard library only.
"""

import importlib.util
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# (name, working directory relative to ROOT, unittest arguments)
SUITES = [
    ("emulator", os.path.join("src"),
     ["discover", "-s", "tests", "-t", "."]),
    ("assembler", os.path.join("src", "bc81asmc"),
     ["discover", "-s", ".", "-t", ".", "-p", "*_tests.py"]),
    ("compiler", os.path.join("src", "bc"),
     ["discover", "-s", ".", "-t", ".", "-p", "*_tests.py"]),
]

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


def run_suite(name, rel_cwd, args):
    """Run one suite. Returns (passed, summary, captured_output)."""
    cwd = os.path.join(ROOT, rel_cwd)
    command = [sys.executable, "-m", "unittest"] + args
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
        return False, "could not start (%s)" % error, ""
    output = completed.stdout or ""
    passed = completed.returncode == 0
    return passed, summarise(output, completed.returncode), output


def main():
    if not check_parsy():
        sys.stderr.write(
            "parsy is not installed for %s.\n"
            "Install it with: pip install -r requirements.txt\n" % sys.executable)
        return 1

    all_passed = True
    for name, rel_cwd, args in SUITES:
        passed, summary, output = run_suite(name, rel_cwd, args)
        all_passed = all_passed and passed
        label = "PASS" if passed else "FAIL"
        print("%-10s %s: %s" % (name, label, summary))
        if not passed and output:
            # Show the failing suite's own output so the failures are visible.
            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")
        sys.stdout.flush()

    print("ALL PASSED" if all_passed else "SOME SUITES FAILED")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
