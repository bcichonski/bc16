#!/usr/bin/env python3
"""Measure the code size of every B program and track it in src/bc/code_size.csv.

Usage (from any directory):
    python3 scripts/code_size.py            report: a Markdown table of program, start, bytes,
                                            hex size and the change against the CSV. Also appended
                                            to $GITHUB_STEP_SUMMARY when that is set. Exit 0 even
                                            when sizes differ from the CSV; exit 1 only if a
                                            program fails to build (its name goes to stderr).
    python3 scripts/code_size.py --check    like the report, but exit 1 when any program differs
                                            from its latest CSV row (size or code), has no row, or
                                            a row names a program that no longer exists.
    python3 scripts/code_size.py --record   append a row for every changed or new program (and an
                                            empty-bytes row for a removed one) dated today (UTC).
                                            Nothing is appended when nothing changed.
    --csv FILE and --root DIR (the folder holding src/) override the defaults; for tests.

A program is a .b file directly in src/bdos/ or src/bc/code/ that defines main (the other files
are include libraries). Ids look like bdos/ls and code/funrec. Every program is compiled by a
fresh bc.py process and assembled in a temp copy of the sources, so the repo tree is never
written to. The size is len(context.bytes) of the assembler, i.e. the codelen of the .btap.

The CSV is an append-only log, header date,program,start,bytes,basm_sha. basm_sha is the first
12 hex digits of the SHA-256 of the LF-normalised .basm, so a code change of the same size is
caught too. For each program the last row is its expected state. Standard library only
(Python >= 3.10); bc and the assembler need parsy.
"""

import argparse
import contextlib
import csv
import datetime
import hashlib
import importlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)
CSV_REL = os.path.join("src", "bc", "code_size.csv")
HEADER = ["date", "program", "start", "bytes", "basm_sha"]
RECORD_COMMAND = "python3 scripts/code_size.py --record"

# (id prefix, folder relative to the root)
SOURCE_DIRS = (("bdos", os.path.join("src", "bdos")),
               ("code", os.path.join("src", "bc", "code")))
MAIN_RE = re.compile(r"^\s*\w+\s+main\s*\(", re.MULTILINE)


class Measurement:
    def __init__(self, start, size, sha):
        self.start = start
        self.size = size
        self.sha = sha


def discover(root):
    """Return {program id: path of its .b} for every .b with a main, sorted by id."""
    found = {}
    for prefix, rel in SOURCE_DIRS:
        folder = os.path.join(root, rel)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if not name.endswith(".b") or not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf8") as handle:
                if MAIN_RE.search(handle.read()):
                    found["%s/%s" % (prefix, name[:-2])] = path
    return dict(sorted(found.items()))


def basm_sha(text):
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf8")).hexdigest()[:12]


_ASSEMBLER = None


def load_assembler():
    folder = os.path.join(ROOT, "src", "bc81asmc")
    if folder not in sys.path:
        sys.path.append(folder)
    # Load bc81asmc.py by path: with src/ on sys.path (editable install) the package
    # src/bc81asmc/__init__.py would shadow the module of the same name.
    global _ASSEMBLER
    if _ASSEMBLER is None:
        spec = importlib.util.spec_from_file_location(
            "_code_size_bc81asmc", os.path.join(folder, "bc81asmc.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _ASSEMBLER = module
    return _ASSEMBLER, importlib.import_module("bc81asmc_grammar")


def assemble(basm_text):
    """Assemble the text; return (start address, byte count)."""
    asm, grammar = load_assembler()
    with contextlib.redirect_stdout(io.StringIO()):  # the assembler prints a summary line
        context = asm.compile(grammar.program.parse(basm_text), False)
    return context.startaddr, len(context.bytes)


def measure_all(root, ids=None):
    """Measure the programs under root in a temp copy.

    Return (results {id: Measurement}, failures {id: message}). ids limits the programs.
    """
    programs = discover(root)
    if ids is not None:
        programs = {key: value for key, value in programs.items() if key in ids}
    results, failures = {}, {}
    bc_py = os.path.join(ROOT, "src", "bc", "bc.py")
    with tempfile.TemporaryDirectory(prefix="code_size_") as tmp:
        for prefix, rel in SOURCE_DIRS:
            folder = os.path.join(root, rel)
            if not os.path.isdir(folder):
                continue
            os.makedirs(os.path.join(tmp, prefix))
            for name in os.listdir(folder):
                if name.endswith(".b"):
                    shutil.copyfile(os.path.join(folder, name), os.path.join(tmp, prefix, name))
        for program in programs:
            source = os.path.join(tmp, *program.split("/")) + ".b"
            completed = subprocess.run(
                [sys.executable, bc_py, source], cwd=os.path.join(ROOT, "src", "bc"),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                encoding="utf-8", errors="replace")
            if completed.returncode != 0:
                failures[program] = "bc failed: " + (completed.stderr.strip() or completed.stdout.strip())
                continue
            with open(source[:-2] + ".basm", "r", encoding="utf8") as handle:
                text = handle.read()
            try:
                start, size = assemble(text)
            except Exception as error:  # parse and assembler errors; the name is what matters
                failures[program] = "assembler failed: %s: %s" % (type(error).__name__, error)
                continue
            results[program] = Measurement(start, size, basm_sha(text))
    return results, failures


def read_log(path):
    """Return {program: latest row dict} (a row with empty bytes means the program is gone)."""
    latest = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("program"):
                    latest[row["program"]] = row
    return latest


def expected(latest):
    """Programs a check expects: the latest row has a size."""
    return {key: row for key, row in latest.items() if row.get("bytes")}


def compare(results, latest, present=None):
    """Return a list of (program, kind, old row or None) for every mismatch, sorted by program.

    kind is "size", "code" (same size, other hash), "new" or "removed". present is the set of
    program ids that still exist (default: the measured ones); a failed build is not removed.
    """
    want = expected(latest)
    present = set(results) if present is None else present
    changes = []
    for program, found in results.items():
        row = want.get(program)
        if row is None:
            changes.append((program, "new", None))
        elif int(row["bytes"]) != found.size:
            changes.append((program, "size", row))
        elif row["basm_sha"] != found.sha:
            changes.append((program, "code", row))
    for program, row in want.items():
        if program not in present:
            changes.append((program, "removed", row))
    return sorted(changes, key=lambda change: change[0])


def describe(change, results):
    program, kind, row = change
    if kind == "new":
        return "%s: new program, %d bytes" % (program, results[program].size)
    if kind == "size":
        return "%s: %s -> %d bytes" % (program, row["bytes"], results[program].size)
    if kind == "code":
        return "%s: code changed, same size (%s bytes)" % (program, row["bytes"])
    return "%s: removed (was %s bytes)" % (program, row["bytes"])


def append_rows(path, rows):
    """Append rows (lists of strings) to the CSV, writing the header first if it is new."""
    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    lead = ""
    if not new_file:
        with open(path, "rb") as handle:
            handle.seek(-1, os.SEEK_END)
            if handle.read(1) != b"\n":
                lead = "\n"
    with open(path, "a", encoding="utf8", newline="") as handle:
        if lead:
            handle.write(lead)
        writer = csv.writer(handle, lineterminator="\n")
        if new_file:
            writer.writerow(HEADER)
        writer.writerows(rows)


def record(path, results, changes, today):
    """Append the rows for the changes; return how many were written."""
    rows = []
    for program, kind, _ in changes:
        if kind == "removed":
            rows.append([today, program, "", "", ""])
        else:
            found = results[program]
            rows.append([today, program, "0x%04x" % found.start, str(found.size), found.sha])
    if rows:
        append_rows(path, rows)
    return len(rows)


def report_table(results, latest):
    """Return the Markdown table of the measurements with the change against the log."""
    want = expected(latest)
    lines = ["| program | start | bytes | hex | change |",
             "| :--- | :--- | ---: | ---: | ---: |"]
    total, total_delta = 0, 0
    for program, found in results.items():
        row = want.get(program)
        if row is None:
            change = "new"
        else:
            delta = found.size - int(row["bytes"])
            total_delta += delta
            if delta:
                change = "%+d" % delta
            elif row["basm_sha"] != found.sha:
                change = "0 (code changed)"
            else:
                change = "0"
        total += found.size
        lines.append("| %s | 0x%04x | %d | 0x%04x | %s |" % (program, found.start, found.size,
                                                                found.size, change))
    lines.append("| **total** | | **%d** | 0x%04x | %+d |" % (total, total, total_delta))
    return "\n".join(lines) + "\n"


def today_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Measure and track the code size of the B programs.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="exit 1 when a program differs from its latest CSV row")
    mode.add_argument("--record", action="store_true",
                      help="append rows for the changed, new and removed programs")
    parser.add_argument("--csv", help="the size log (default: %s)" % CSV_REL)
    parser.add_argument("--root", default=ROOT, help="the folder holding src/ with the sources")
    args = parser.parse_args(argv)
    csv_path = args.csv or os.path.join(args.root, CSV_REL)

    results, failures = measure_all(args.root)
    for program, message in failures.items():
        sys.stderr.write("%s: %s\n" % (program, message))
    latest = read_log(csv_path)
    changes = compare(results, latest, set(discover(args.root)))

    if args.record:
        if failures:
            sys.stderr.write("not recording: %d program(s) failed to build\n" % len(failures))
            return 1
        count = record(csv_path, results, changes, today_utc())
        for change in changes:
            print(describe(change, results))
        print("recorded %d row(s) in %s" % (count, csv_path))
        return 0

    table = report_table(results, latest)
    sys.stdout.write(table)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf8", newline="") as handle:
            handle.write("### Code size\n\n" + table + "\n")
    if failures:
        return 1
    if args.check and changes:
        sys.stderr.write("code size differs from %s:\n" % CSV_REL)
        for change in changes:
            sys.stderr.write("  " + describe(change, results) + "\n")
        sys.stderr.write("if the change is intended, run: %s\n" % RECORD_COMMAND)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
