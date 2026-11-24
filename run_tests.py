#!/usr/bin/env python3
"""Run the component test suites and report one line per suite.

Suites: emulator, ftool, assembler, compiler, release (group "unit") and e2e (group "e2e").

Usage (from any directory):
    python3 run_tests.py [--group unit|e2e|all] [--no-build] [--update-golden]
                         [--tier full|happy] [--area NAME ...] [--jobs N] [--changed REF]

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
The e2e suite can be narrowed and parallelised (unit suites are never affected):
--tier happy runs only the happy-path tests listed in src/tests/e2e_areas.py (HAPPY);
--tier full (the default) runs every e2e test.
--area NAME (repeatable; emulator, assembler, compiler, bcos, bdos) runs only the e2e modules of
those areas (the map is src/tests/e2e_areas.py); without it every e2e module runs, including one
the map doesn't know yet.
--jobs N (default: the number of CPUs) runs the e2e suite as one unittest process per module, up
to N at a time, and merges the results into one e2e line and table row with the same counts and
wording as a single-process run; the output of failing modules is printed. --jobs 1 runs the e2e
suite in one process, and --update-golden always does (goldens are shared between modules).
--changed REF runs only the e2e areas affected by the change since REF: the files of
`git diff --name-only $(git merge-base REF HEAD)` (committed and uncommitted changes of tracked
files) plus untracked, not-ignored files, mapped to areas by src/tests/e2e_areas.py (areas without
e2e modules are dropped). It combines with --tier and excludes --area (exit 2). When no area is
affected e2e is reported PASS ("not run, no e2e area affected since REF") and nothing is built; an
unknown REF exits with 2. The selected areas are printed before the e2e suite runs.
Exit code is 0 only if every selected suite passes. Standard library only.
"""

import argparse
import concurrent.futures
import glob
import importlib.util
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))

GROUPS = ("unit", "e2e", "all")

MANIFEST = os.path.join(ROOT, "src", "disc.bddmanifest")
BUILD_COMMAND = "./buildos && ./buildtools && ./buildapps && ./makedisc"
PIPELINE = "cd src && " + BUILD_COMMAND
# Built outputs the e2e suite needs besides the manifest sources, relative to src/.
BUILT_OUTPUTS = ("bc81asmc/bcOS/bcos_v1_2_0.b81", "os.bdd", "utils.bdd")

E2E_AREAS_PATH = os.path.join(ROOT, "src", "tests", "e2e_areas.py")


def load_e2e_areas(path=E2E_AREAS_PATH):
    """Load the e2e area map by file path (never as a package: src/ may be on sys.path)."""
    spec = importlib.util.spec_from_file_location("run_tests_e2e_areas", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


E2E_AREAS = load_e2e_areas()
TIERS = ("full", "happy")


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

    Checks the manifest sources first, then those of utils.bddmanifest next to it (if any),
    then the boot ROM, os.bdd and utils.bdd (paths relative to src/,
    which is the manifest's folder).
    """
    missing = missing_disc_source(manifest_path)
    if missing:
        return missing
    utils_manifest = os.path.join(os.path.dirname(manifest_path), "utils.bddmanifest")
    if os.path.exists(utils_manifest):
        missing = missing_disc_source(utils_manifest)
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


def select_e2e(modules, tier="full", areas=None, area_map=E2E_AREAS):
    """Return the e2e run units [(module, unittest ids)] for a tier and an optional area filter.

    areas (None = no filter) keeps the modules of those areas only; without it every module is
    kept, unmapped ones too. tier "happy" replaces each module by its happy-path ids (modules
    without any are dropped); tier "full" runs each module whole.
    """
    units = []
    for module in modules:
        if areas and area_map.area_of_module(module) not in areas:
            continue
        if tier == "happy":
            ids = ["tests." + test_id for test_id in area_map.happy_ids(module)]
            if ids:
                units.append((module, ids))
        else:
            units.append((module, [module]))
    return units


class BadRef(Exception):
    """The --changed REF is not a revision with a merge base with HEAD."""


def _git_lines(args, cwd):
    completed = subprocess.run(["git"] + args, cwd=cwd, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise BadRef((completed.stderr or "").strip() or "git %s failed" % args[0])
    return [line for line in completed.stdout.splitlines() if line.strip()]


def git_changed_paths(ref, cwd=ROOT):
    """Repo-relative paths changed since the merge base of ref and HEAD.

    Committed and uncommitted changes of tracked files, plus untracked files that are not
    ignored. Raises BadRef when ref is not a revision (or shares no history with HEAD).
    """
    try:
        base = _git_lines(["merge-base", ref, "HEAD"], cwd)
    except OSError as error:
        raise BadRef("could not run git (%s)" % error)
    if not base:
        raise BadRef("no merge base with HEAD")
    paths = _git_lines(["diff", "--name-only", base[0]], cwd)
    paths += _git_lines(["ls-files", "--others", "--exclude-standard"], cwd)
    return sorted(set(paths))


def changed_e2e_areas(paths, modules, area_map=E2E_AREAS):
    """Sorted areas affected by the paths that own at least one of the e2e modules."""
    triggered = area_map.areas_for_paths(paths)
    return [area for area in area_map.areas_with_modules(modules) if area in triggered]


def format_status(counts, passed):
    """unittest's final status line ("OK (...)" / "FAILED (...)") for merged counts."""
    keys = ("skipped", "expected failures", "unexpected successes")
    if not passed:
        keys = ("failures", "errors") + keys
    infos = ["%s=%d" % (key, counts[key]) for key in keys if counts[key]]
    status = "OK" if passed else "FAILED"
    return status + (" (%s)" % ", ".join(infos) if infos else "")


def merge_results(units, results, seconds=0.0):
    """Merge per-module results [(passed, summary, output, returncode)] into one suite result.

    Returns (passed, summary, output, returncode) like run_suite: output holds the failing
    modules' own output followed by one unittest-style "Ran N tests" / status footer, so
    summarise and parse_counts read the merged totals. A module without a "Ran" line (a crash)
    counts as one error.
    """
    total = {"ran": 0, "failures": 0, "errors": 0, "skipped": 0,
             "expected failures": 0, "unexpected successes": 0}
    passed = True
    failing = []
    for (module, _ids), (unit_passed, _summary, output, returncode) in zip(units, results):
        counts = parse_counts(output, returncode)
        if counts is None:
            total["errors"] += 1
        else:
            for key in total:
                total[key] += counts[key]
        if not unit_passed:
            passed = False
            failing.append("=== %s (exit code %d) ===\n%s%s" % (
                module, returncode, output, "" if output.endswith("\n") else "\n"))
    returncode = 0 if passed else 1
    footer = "-" * 70 + "\nRan %d test%s in %.3fs\n\n%s\n" % (
        total["ran"], "" if total["ran"] == 1 else "s", seconds, format_status(total, passed))
    output = "".join(failing) + footer
    return passed, summarise(output, returncode), output, returncode


def run_e2e(name, rel_cwd, units, runner, env=None, jobs=1):
    """Run the e2e units: one call with every id when jobs is 1 (or one unit), else one call per
    unit with up to jobs at a time, merged by merge_results."""
    def call(args):
        if env is None:
            return runner(name, rel_cwd, args)
        return runner(name, rel_cwd, args, env=env)

    if jobs <= 1 or len(units) <= 1:
        return call([test_id for _module, ids in units for test_id in ids])
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(call, ids) for _module, ids in units]
        results = [future.result() for future in futures]
    return merge_results(units, results, time.monotonic() - started)


def positive_int(text):
    """argparse type: an integer >= 1."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("not an integer: %r" % text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1: %r" % text)
    return value


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


def main(argv=None, suites=None, runner=run_suite, environ=None, manifest=MANIFEST, build=run_build,
         changed_paths=git_changed_paths):
    parser = argparse.ArgumentParser(description="Run the component test suites.")
    parser.add_argument("--group", choices=GROUPS, default="all",
                        help="unit = emulator/ftool/assembler/compiler/release, e2e = end-to-end, all = both")
    parser.add_argument("--no-build", action="store_true",
                        help="don't build the ROM and discs before the e2e suite (they must already exist)")
    parser.add_argument("--update-golden", action="store_true",
                        help="rewrite the e2e goldens: sets BC64_UPDATE_GOLDEN=1 for the e2e suite only "
                             "(still builds first unless --no-build); implies --jobs 1")
    parser.add_argument("--tier", choices=TIERS, default="full",
                        help="e2e tier: full = every e2e test (default), happy = only the happy-path "
                             "tests listed in src/tests/e2e_areas.py")
    parser.add_argument("--area", action="append", choices=E2E_AREAS.AREAS, metavar="NAME",
                        help="run only the e2e modules of this area (repeatable; one of %s); "
                             "default: every e2e module" % ", ".join(E2E_AREAS.AREAS))
    parser.add_argument("--jobs", type=positive_int, default=max(1, os.cpu_count() or 1),
                        metavar="N",
                        help="run up to N e2e modules at once, one process each, results merged "
                             "(default: the number of CPUs, %(default)s); --update-golden forces 1")
    parser.add_argument("--changed", metavar="REF",
                        help="run only the e2e areas affected by the change since REF (merge base "
                             "with HEAD, uncommitted and untracked files included; areas without "
                             "e2e modules are dropped); combines with --tier, excludes --area; "
                             "nothing affected = e2e passes without building")
    options = parser.parse_args(argv)
    if options.changed is not None and options.area:
        parser.error("--changed and --area are mutually exclusive")
    changed_list = None
    if options.changed is not None:
        try:
            changed_list = changed_paths(options.changed)
        except BadRef as error:
            parser.error("--changed %s: not a usable revision (%s)" % (options.changed, error))
    jobs = 1 if options.update_golden else options.jobs
    environ = os.environ if environ is None else environ

    if not check_parsy():
        sys.stderr.write(
            "parsy is not installed for %s.\n"
            "Install it with: pip install -e .\n" % sys.executable)
        return 1

    if suites is None:
        suites = build_suites()
    selected = filter_suites(suites, options.group)
    # The e2e suite's run units after the tier and area filters; its args become their ids.
    e2e_units = {}
    unaffected = set()  # e2e suite index when --changed selects no area
    for index, (name, group, rel_cwd, args) in enumerate(selected):
        if name == "e2e" and args:
            areas = options.area
            if changed_list is not None:
                areas = changed_e2e_areas(changed_list, args)
                print("%-10s changed since %s: %s" % ("e2e", options.changed, ", ".join(areas) or "no area"))
                sys.stdout.flush()
            if changed_list is not None and not areas:
                unaffected.add(index)
                units = []
            else:
                units = select_e2e(args, options.tier, areas)
            e2e_units[index] = units
            selected[index] = (name, group, rel_cwd, [i for _m, ids in units for i in ids])

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
    for index, (name, _group, rel_cwd, args) in enumerate(selected):
        is_e2e = name == "e2e" and bool(args)
        missing = missing_build_output(manifest) if is_e2e and not build_failed else None
        if index in unaffected:
            passed, summary, output, returncode = True, "not run, no e2e area affected since %s" % (
                options.changed), "", 0
        elif not args and index in e2e_units:
            passed, summary, output, returncode = False, "no e2e tests selected (tier %s, area %s)" % (
                options.tier, ", ".join(options.area or ["any"])), "", -1
        elif not args:
            passed, summary, output, returncode = False, "no test modules found", "", -1
        elif is_e2e and build_failed:
            passed, output, returncode = False, "", -1
            summary = "not run, the build failed"
        elif missing:
            passed, output, returncode = False, "", -1
            summary = "not run, %s is missing; build it first with: %s" % (missing, PIPELINE)
        elif index in e2e_units:
            golden_env = None
            if options.update_golden:
                golden_env = dict(os.environ)
                golden_env["BC64_UPDATE_GOLDEN"] = "1"
            passed, summary, output, returncode = run_e2e(
                name, rel_cwd, e2e_units[index], runner, env=golden_env, jobs=jobs)
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
