#!/usr/bin/env python3
"""Run the component test suites and report one line per suite.

Suites: emulator, ftool, assembler, compiler, release (group "unit") and e2e (group "e2e").

Usage (from any directory):
    python3 run_tests.py [--group unit|e2e|all] [--no-build] [--update-golden]

Each suite runs as a subprocess with the interpreter that started this script and
with its own working directory, because the suites use flat imports.
The src suites are chosen by rule (see select_src_modules), not by a fixed file list.
When the environment variable GITHUB_STEP_SUMMARY names a file, a Markdown table
of the results is appended to it.
Before the e2e suite (--group e2e or all) the runner builds the ROM and the discs from source
(the pipeline below, run once in src/); --group unit never builds. --no-build skips the build; the
e2e suite then needs the ROM, src/os.bdd and the sources named in src/disc.bddmanifest to exist, and
when one is missing it is reported as FAIL with the missing path and the build command, and is not run.
If the build fails, e2e is reported FAIL (not run) and the other suites still run.
--update-golden sets BC64_UPDATE_GOLDEN=1 in the environment of the e2e suite only (never the unit
suites, and never this process's own environment), so the e2e tests rewrite their goldens instead of
comparing against them. It still builds first unless --no-build is given.
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

MANIFEST = os.path.join(ROOT, "src", "disc.bddmanifest")
BUILD_COMMAND = "./buildos && ./buildtools && ./buildapps && ./makedisc"
PIPELINE = "cd src && " + BUILD_COMMAND
# Built outputs the e2e suite needs besides the manifest sources, relative to src/.
BUILT_OUTPUTS = ("bc81asmc/bcOS/bcos_v1_2_0.b81", "os.bdd")


def missing_disc_source(manifest_path=MANIFEST):
    """Return the first SOURCE file named in the disc manifest that doesn't exist, or None.

    The e2e tests read the build intermediates (.sector/.sectors) that the manifest names;
    they are not committed, so a fresh clone has to build them first. Paths in the manifest
    are relative to its own folder; "-" (the generated catalog) has no source.
    """
    base = os.path.dirname(manifest_path)
    with open(manifest_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            columns = line.split()
            if len(columns) < 2 or columns[1] == "-":
                continue
            if not os.path.exists(os.path.join(base, columns[1])):
                return columns[1]
    return None


def missing_build_output(manifest_path=MANIFEST):
    """Return the first built file the e2e suite needs that doesn't exist, or None.

    Checks the manifest sources first, then the boot ROM and os.bdd (paths relative to src/,
    which is the manifest's folder).
    """
    missing = missing_disc_source(manifest_path)
    if missing:
        return missing
    base = os.path.dirname(manifest_path)
    for name in BUILT_OUTPUTS:
        if not os.path.exists(os.path.join(base, name)):
            return name
    return None


def run_build(root=ROOT):
    """Build the ROM and the discs from source. Returns (passed, summary, output, returncode)."""
    try:
        completed = subprocess.run(
            ["bash", "-c", BUILD_COMMAND],
            cwd=os.path.join(root, "src"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        return False, "could not start bash (%s)" % error, "", -1
    summary = "built" if completed.returncode == 0 else "exit code %d" % completed.returncode
    return completed.returncode == 0, summary, completed.stdout or "", completed.returncode


def select_src_modules(src_dir):
    """Partition the test modules under src_dir into {suite name: [module names]}.

    Tests live in a tests/ package of their tool:
    e2e:      tests/test_e2e_*.py and tests/test_bc64_smoke.py
    ftool:    tests/test_ftool.py
    emulator: bc64/tests/test_*.py and every other tests/test_*.py
    Module names are importable with src_dir as the working directory.
    """
    e2e, ftool, emulator = [], [], []
    for path in sorted(glob.glob(os.path.join(src_dir, "tests", "test_*.py"))):
        module = "tests." + os.path.splitext(os.path.basename(path))[0]
        if module.startswith("tests.test_e2e_") or module == "tests.test_bc64_smoke":
            e2e.append(module)
        elif module == "tests.test_ftool":
            ftool.append(module)
        else:
            emulator.append(module)
    bc64 = [
        "bc64.tests." + os.path.splitext(os.path.basename(path))[0]
        for path in sorted(glob.glob(os.path.join(src_dir, "bc64", "tests", "test_*.py")))
    ]
    return {"emulator": bc64 + emulator, "ftool": ftool, "e2e": e2e}


def build_suites(root=ROOT):
    """Return [(name, group, cwd relative to root, unittest arguments)] in report order."""
    modules = select_src_modules(os.path.join(root, "src"))
    discover = ["discover", "-s", "tests", "-t", ".", "-p", "*_tests.py"]
    return [
        ("emulator", "unit", "src", modules["emulator"]),
        ("ftool", "unit", "src", modules["ftool"]),
        ("assembler", "unit", os.path.join("src", "bc81asmc"), discover),
        ("compiler", "unit", os.path.join("src", "bc"), discover),
        ("release", "unit", "scripts", ["discover", "-s", "tests", "-t", ".", "-p", "test_*.py"]),
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


def run_suite(name, rel_cwd, args, env=None):
    """Run one suite; env, when given, is the child's full environment. Returns (passed, summary, captured_output, returncode)."""
    cwd = os.path.join(ROOT, rel_cwd)
    command = [sys.executable, "-m", "unittest"] + list(args)
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
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


def main(argv=None, suites=None, runner=run_suite, environ=None, manifest=MANIFEST, build=run_build):
    parser = argparse.ArgumentParser(description="Run the component test suites.")
    parser.add_argument("--group", choices=GROUPS, default="all",
                        help="unit = emulator/ftool/assembler/compiler/release, e2e = end-to-end, all = both")
    parser.add_argument("--no-build", action="store_true",
                        help="don't build the ROM and discs before the e2e suite (they must already exist)")
    parser.add_argument("--update-golden", action="store_true",
                        help="rewrite the e2e goldens: sets BC64_UPDATE_GOLDEN=1 for the e2e suite only "
                             "(still builds first unless --no-build)")
    options = parser.parse_args(argv)
    environ = os.environ if environ is None else environ

    if not check_parsy():
        sys.stderr.write(
            "parsy is not installed for %s.\n"
            "Install it with: pip install -e .\n" % sys.executable)
        return 1

    if suites is None:
        suites = build_suites()
    selected = filter_suites(suites, options.group)

    all_passed = True
    results = []
    build_failed = False
    if not options.no_build and any(suite[0] == "e2e" and suite[3] for suite in selected):
        print("%-10s ..." % "build")
        sys.stdout.flush()
        passed, summary, output, returncode = build()
        build_failed = not passed
        print("%-10s %s: %s" % ("build", "PASS" if passed else "FAIL", summary))
        if not passed and output:
            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")
        sys.stdout.flush()
        all_passed = passed
    for name, _group, rel_cwd, args in selected:
        is_e2e = name == "e2e" and bool(args)
        missing = missing_build_output(manifest) if is_e2e and not build_failed else None
        if not args:
            passed, summary, output, returncode = False, "no test modules found", "", -1
        elif is_e2e and build_failed:
            passed, output, returncode = False, "", -1
            summary = "not run, the build failed"
        elif missing:
            passed, output, returncode = False, "", -1
            summary = "not run, %s is missing; build it first with: %s" % (missing, PIPELINE)
        else:
            if options.update_golden and name == "e2e":
                golden_env = dict(os.environ)
                golden_env["BC64_UPDATE_GOLDEN"] = "1"
                passed, summary, output, returncode = runner(name, rel_cwd, args, env=golden_env)
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
