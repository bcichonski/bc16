#!/usr/bin/env python3
"""Check the fixed memory map (design decision G2) against the symbol maps of a built tree.

Usage (from any directory):
    python3 scripts/check_memory_map.py [--root DIR]

--root DIR is the folder holding src/ (default: the repo root). The script only reads the maps
that the build scripts write next to the .btap files (bc81asmc --map); it never builds and never
writes. One line per violation goes to stdout and the exit code is 1; otherwise a short OK
summary is printed and the exit code is 0.

Checked (the values live here, not in the docs):
    bcos.map   org 0x0000, os_metacall = 0x0008, os_metatab = 0x000c, user_mem <= 0x0d80,
               image end <= 0x0d80
    boot.map   org 0x0e00, bd_end <= 0x0e80
    bdos.map   org 0x0f00, sys_codeend < 0x5d00
    every other src/bdos/*.map is a program: org 0x6000 (at least one must exist)

Map format (bc81asmc_listing.py): header lines "; bc81asmc map <source>" and
"; org 0xHHHH end 0xHHHH", then one "0xHHHH <label|def> <name>" line per symbol.
Standard library only.
"""

import argparse
import os
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)

BCOS_MAP = os.path.join("src", "bc81asmc", "bcOS", "bcos.map")
BDOS_DIR = os.path.join("src", "bdos")
BOOT_MAP = os.path.join(BDOS_DIR, "boot.map")
BDOS_MAP = os.path.join(BDOS_DIR, "bdos.map")

PROGRAM_ORG = 0x6000


def read_map(path):
    """Return (org, end, {name: value}) of a map file; raise ValueError when it is malformed."""
    org = end = None
    symbols = {}
    with open(path, "r", encoding="utf8") as handle:
        for number, raw in enumerate(handle.read().splitlines(), 1):
            row = raw.strip()
            if not row:
                continue
            if row.startswith(";"):
                parts = row[1:].split()
                if len(parts) == 4 and parts[0] == "org" and parts[2] == "end":
                    org, end = int(parts[1], 16), int(parts[3], 16)
                continue
            parts = row.split()
            if len(parts) != 3 or parts[1] not in ("label", "def"):
                raise ValueError("bad line %d: %r" % (number, raw))
            symbols[parts[2]] = int(parts[0], 16)
    if org is None:
        raise ValueError("org/end header missing")
    return org, end, symbols


def _load(root, rel, violations):
    path = os.path.join(root, rel)
    shown = rel.replace(os.sep, "/")
    if not os.path.isfile(path):
        violations.append("%s: map missing (build first)" % shown)
        return None
    try:
        return read_map(path)
    except (ValueError, OSError) as error:
        violations.append("%s: unreadable map: %s" % (shown, error))
        return None


def _expect_eq(violations, shown, what, expected, actual):
    if actual != expected:
        violations.append("%s: %s expected 0x%04x, found %s"
                          % (shown, what, expected, "0x%04x" % actual if actual is not None else "missing"))


def _expect_le(violations, shown, what, limit, actual, strict=False):
    if actual is None:
        violations.append("%s: %s missing" % (shown, what))
    elif actual > limit or (strict and actual == limit):
        violations.append("%s: %s expected %s 0x%04x, found 0x%04x"
                          % (shown, what, "<" if strict else "<=", limit, actual))


def check(root):
    """Return (violations, summary) for the maps of the tree under root."""
    violations = []
    checked = []

    shown = BCOS_MAP.replace(os.sep, "/")
    loaded = _load(root, BCOS_MAP, violations)
    if loaded:
        org, end, symbols = loaded
        _expect_eq(violations, shown, "org", 0x0000, org)
        _expect_eq(violations, shown, "os_metacall", 0x0008, symbols.get("os_metacall"))
        _expect_eq(violations, shown, "os_metatab", 0x000c, symbols.get("os_metatab"))
        _expect_le(violations, shown, "user_mem", 0x0d80, symbols.get("user_mem"))
        _expect_le(violations, shown, "end", 0x0d80, end)
        checked.append("bcos")

    shown = BOOT_MAP.replace(os.sep, "/")
    loaded = _load(root, BOOT_MAP, violations)
    if loaded:
        org, end, symbols = loaded
        _expect_eq(violations, shown, "org", 0x0e00, org)
        _expect_le(violations, shown, "bd_end", 0x0e80, symbols.get("bd_end"))
        checked.append("boot")

    shown = BDOS_MAP.replace(os.sep, "/")
    loaded = _load(root, BDOS_MAP, violations)
    if loaded:
        org, end, symbols = loaded
        _expect_eq(violations, shown, "org", 0x0f00, org)
        _expect_le(violations, shown, "sys_codeend", 0x5d00, symbols.get("sys_codeend"), strict=True)
        checked.append("bdos")

    folder = os.path.join(root, BDOS_DIR)
    programs = []
    if os.path.isdir(folder):
        programs = sorted(name for name in os.listdir(folder)
                          if name.endswith(".map") and name not in ("boot.map", "bdos.map"))
    if not programs:
        violations.append("%s/*.map: no program map found (build first)" % BDOS_DIR.replace(os.sep, "/"))
    for name in programs:
        rel = os.path.join(BDOS_DIR, name)
        loaded = _load(root, rel, violations)
        if loaded:
            _expect_eq(violations, rel.replace(os.sep, "/"), "org", PROGRAM_ORG, loaded[0])
            checked.append(name[:-4])

    summary = "memory map OK: %d maps checked (%s)" % (len(checked), ", ".join(checked))
    return violations, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the G2 fixed memory map against built symbol maps.")
    parser.add_argument("--root", default=ROOT, help="the folder holding src/ with the built maps")
    args = parser.parse_args(argv)
    violations, summary = check(args.root)
    if violations:
        for line in violations:
            print(line)
        print("memory map check FAILED: %d violation(s)" % len(violations))
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
