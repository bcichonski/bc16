"""Harness for end-to-end tests on the headless emulator (plain module, not a test).

Provides a session runner (boots bc64.py on temp copies of the discs), a byte-exact golden
compare with an update mode, regex masks, marker assertions, a slow-scenario decorator, a
catalog reader and a disc-put helper. Imports are flat: run from src/ (as run_tests.py does).
"""
import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import namedtuple

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BC64_PY = os.path.join(SRC, "bc64.py")
ROM = os.path.join(SRC, "bc81asmc", "bcOS", "bcos_v1_2_0.b81")
OS_DISK = os.path.join(SRC, "os.bdd")
TESTDATA = os.path.join(SRC, "bc64", "testdata")
SMOKE_DISK = os.path.join(TESTDATA, "smoke.bdd")
GOLDEN_DIR = os.path.join(TESTDATA, "e2e")
DEFAULT_MAX_INSTRUCTIONS = 200000000
UPDATE_ENV = "BC64_UPDATE_GOLDEN"
SLOW_ENV = "BC64_E2E_SLOW"
EXIT_INSTRUCTION_LIMIT = 3
TAIL = 3000
DIFF_CAP = 4000

SECTOR_SIZE = 128
SECTORS_PER_TRACK = 16
TRACKS = 64
CAT_FIRST_SECTOR = 1          # linear sector: track 0 sector 1
CAT_SECTORS = 31
ENTRY_SIZE = 16
ATTR_R = 0x01
ATTR_X = 0x04
ATTR_RX = ATTR_R | ATTR_X

CatalogEntry = namedtuple("CatalogEntry", "name ext attributes track sector length")


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def golden_path(scenario, kind="golden"):
    """Path of the script (kind='in') or golden (kind='golden') of a scenario in GOLDEN_DIR."""
    return os.path.join(GOLDEN_DIR, "%s.%s.txt" % (scenario, kind))


def slow(test):
    """Skip a scenario unless BC64_E2E_SLOW=1 is set."""
    return unittest.skipUnless(os.environ.get(SLOW_ENV) == "1",
                               "slow e2e scenario; set %s=1 to run" % SLOW_ENV)(test)


def _tail(data, limit=TAIL):
    text = data.decode("latin-1") if isinstance(data, bytes) else data
    return text[-limit:]


def run_session(scenario, session, rom=ROM, disks=None, tape_dir=False, no_floppy=False,
                max_instructions=DEFAULT_MAX_INSTRUCTIONS, inspect=None, seed=None):
    """Boot the emulator headless with the keys of the session file; return the printer bytes.

    disks: {"a": path, "b": path}; each image is copied to a temp dir and the copy is used.
    tape_dir: pass a temp tape directory (--tape-dir). no_floppy: pass --no-floppy (no disks).
    inspect: optional callable(paths) run before cleanup; paths has "tmp", "a", "b", "tape".
    seed: optional int passed as --random-seed (reproducible port 0x05 random numbers).
    Raises AssertionError on an instruction-limit stop (exit 3) or any other non-zero exit,
    and when a source image changed or a cpudebug.log appeared.
    """
    disks = dict(disks or {})
    before = {name: read_bytes(path) for name, path in disks.items()}
    with tempfile.TemporaryDirectory() as tmp:
        paths = {"tmp": tmp}
        output = os.path.join(tmp, "out.txt")
        cmd = [sys.executable, BC64_PY, rom, "--input", session, "--output", output,
               "--max-instructions", str(max_instructions)]
        if seed is not None:
            cmd += ["--random-seed", str(seed)]
        if no_floppy:
            cmd.append("--no-floppy")
        for name in sorted(disks):
            copy = os.path.join(tmp, "disk_%s.bdd" % name)
            shutil.copyfile(disks[name], copy)
            paths[name] = copy
            cmd += ["--disk-" + name, copy]
        if tape_dir:
            paths["tape"] = os.path.join(tmp, "tapes")
            os.makedirs(paths["tape"])
            cmd += ["--tape-dir", paths["tape"]]
        result = subprocess.run(cmd, cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True, timeout=600)
        actual = read_bytes(output) if os.path.exists(output) else b""
        if result.returncode == EXIT_INSTRUCTION_LIMIT:
            raise AssertionError(
                "scenario %r stopped by the instruction limit (--max-instructions %s, exit 3); "
                "the system hung or the limit is too low. Output tail:\n%s"
                % (scenario, max_instructions, _tail(actual)))
        if result.returncode != 0:
            raise AssertionError("scenario %r: bc64.py exited with %d. stderr tail:\n%s"
                                 % (scenario, result.returncode, _tail(result.stderr)))
        if os.path.exists(os.path.join(tmp, "cpudebug.log")):
            raise AssertionError("scenario %r: cpudebug.log appeared (trace was on?)" % scenario)
        if inspect is not None:
            inspect(paths)
    for name, path in disks.items():
        if before[name] != read_bytes(path):
            raise AssertionError("source disc image %s was modified" % path)
    return actual


def apply_masks(data, masks=None):
    """Apply (regex, replacement) pairs (bytes) to data, in order."""
    for pattern, replacement in masks or []:
        if isinstance(pattern, str):
            pattern = pattern.encode("latin-1")
        if isinstance(replacement, str):
            replacement = replacement.encode("latin-1")
        data = re.sub(pattern, replacement, data)
    return data


def assert_markers(actual, markers):
    """Every marker (bytes) must occur in actual, so an empty or truncated output can't pass."""
    for marker in markers:
        if marker not in actual:
            raise AssertionError("marker %r missing in output:\n%s" % (marker, _tail(actual)))


def check_golden(golden, actual, masks=None, markers=(), scenario=""):
    """Compare actual with the golden file byte for byte (after masks).

    BC64_UPDATE_GOLDEN=1 writes the golden and passes (note on stderr only).
    Raises AssertionError with a unified diff and regeneration hint on mismatch.
    """
    assert_markers(actual, markers)
    actual = apply_masks(actual, masks)
    if os.environ.get(UPDATE_ENV) == "1":
        os.makedirs(os.path.dirname(golden), exist_ok=True)
        with open(golden, "wb") as handle:
            handle.write(actual)
        sys.stderr.write("[e2e] golden written: %s (review the git diff)\n" % golden)
        return
    if not os.path.exists(golden):
        raise AssertionError("golden %s does not exist. Create it with %s=1 and review it."
                             % (golden, UPDATE_ENV))
    expected = apply_masks(read_bytes(golden), masks)
    if actual == expected:
        return
    diff = "\n".join(difflib.unified_diff(
        expected.decode("latin-1").splitlines(), actual.decode("latin-1").splitlines(),
        "golden", "actual", lineterm="", n=2))
    raise AssertionError(
        "scenario %s: printer output differs from golden %s\n%s\n"
        "If the change is intended, regenerate with %s=1 (e.g. `cd src && %s=1 python3 -m unittest "
        "<module>`), inspect the git diff by eye and commit it."
        % (scenario, golden, diff[:DIFF_CAP], UPDATE_ENV, UPDATE_ENV))


def _name_field(name):
    """Split 'name.ext' into the 8-byte name and 3-byte extension fields (upper case, padded)."""
    base, _, ext = name.upper().partition(".")
    if not base or len(base) > 8 or len(ext) > 3 or "." in ext:
        raise ValueError("not an 8.3 name: %r" % name)
    return base.ljust(8).encode("latin-1"), ext.ljust(3).encode("latin-1")


def _entries(image):
    for index in range(CAT_SECTORS * SECTOR_SIZE // ENTRY_SIZE):
        offset = CAT_FIRST_SECTOR * SECTOR_SIZE + index * ENTRY_SIZE
        yield index, offset, image[offset:offset + ENTRY_SIZE]


def read_catalog(image_path):
    """Parse the catalog of a disc image into CatalogEntry rows (used entries only)."""
    image = read_bytes(image_path)
    rows = []
    for _, _, entry in _entries(image):
        if entry[3] > 0:
            rows.append(CatalogEntry(entry[5:13].decode("latin-1").rstrip(),
                                     entry[13:16].decode("latin-1").rstrip(),
                                     entry[4], entry[1], entry[2], entry[3]))
    return rows


def disc_put(image_path, name, data, attributes=ATTR_RX):
    """Add a file to a (temp!) disc image, the way bdos allocates.

    Uses the first free catalog entry (first entry with length 0) and the first free sector
    after the used area (the end of the used entries before it, as bdio_fcat_scanmem does).
    Raises ValueError for a duplicate name, a bad name, a full catalog or a full disc.
    Returns the CatalogEntry.
    """
    name_field, ext_field = _name_field(name)
    image = bytearray(read_bytes(image_path))
    free_sector = 0
    free_offset = None
    for _, offset, entry in _entries(image):
        if entry[3] == 0:
            if free_offset is None:
                free_offset = offset
            continue
        if entry[5:13] == name_field and entry[13:16] == ext_field:
            raise ValueError("file already exists: %s" % name)
        if free_offset is None:
            free_sector = max(free_sector, entry[1] * SECTORS_PER_TRACK + entry[2] + entry[3])
    if free_offset is None:
        raise ValueError("catalog is full")
    count = max(1, -(-len(data) // SECTOR_SIZE))
    if count > 255 or free_sector + count > TRACKS * SECTORS_PER_TRACK:
        raise ValueError("disc is full")
    start = free_sector * SECTOR_SIZE
    image[start:start + count * SECTOR_SIZE] = data.ljust(count * SECTOR_SIZE, b"\x00")
    track, sector = divmod(free_sector, SECTORS_PER_TRACK)
    image[free_offset + 1:free_offset + 5] = bytes([track, sector, count, attributes])
    image[free_offset + 5:free_offset + 16] = name_field + ext_field
    with open(image_path, "wb") as handle:
        handle.write(image)
    return CatalogEntry(name_field.decode().rstrip(), ext_field.decode().rstrip(), attributes,
                        track, sector, count)
