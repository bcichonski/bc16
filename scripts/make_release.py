#!/usr/bin/env python3
"""Build the GitHub Release zips and their release notes.

Usage (from any directory inside a full clone):
    python3 scripts/make_release.py bc64 --tag NAME [--out DIR]
    python3 scripts/make_release.py legacy bc16|bc32 [--out DIR]
    python3 scripts/make_release.py notes bc64|bc16|bc32

bc64    zips the tracked files of the current machine at HEAD (emulator, ROM, os.bdd,
        toolchain, scripts, README, LICENSE, pyproject.toml, reference docs) into
        DIR/NAME.zip with the single root folder NAME/. Tests, test data, CI and
        planning docs are left out. File modes from git are kept.
legacy  zips a frozen earlier generation into DIR/<gen>-v1.0.zip (root <gen>-v1.0/):
        release/<gen>_v1.0/ as at LEGACY_COMMIT, plus rom/ (bc32: the bcOS 1.1.1 ROM of
        BC32_ROM_COMMIT, the release commit; bc16: bcOS 1.0 assembled from BC16_ROM_COMMIT with that commit's
        assembler), the run script with the interpreter pick of src/run, and RELEASE-NOTES.md.
notes   prints the release notes: the README section of that generation.

Everything is read from git objects (not from the working tree), so the output doesn't
depend on line-ending settings and works after release/ is deleted. The default DIR is
dist/ in the repo root. Errors print one line and exit with code 1.
Standard library only (Python >= 3.10). The bc16 ROM build also needs parsy.
"""

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

LEGACY_COMMIT = "7d4cda9"
# The bc32 ROM comes from the release commit: b9f2fe6 changed it later, and that copy
# (the one at LEGACY_COMMIT) crashes the bc32 emulator at start.
BC32_ROM_COMMIT = "6304761"
BC16_ROM_COMMIT = "bd2498a"
LEGACY_GENERATIONS = ("bc16", "bc32")
NOTES_GENERATIONS = ("bc64", "bc16", "bc32")
TAG_TARGETS = {"bc16": "bd2498a", "bc32": "6304761"}

# Interpreter pick of src/run, put in place of "winpty python" in the legacy run scripts.
INTERPRETER_PICK = (
    "# Pick the Python interpreter: winpty python on Git Bash (Windows), else python3, else python.\n"
    "if command -v winpty >/dev/null 2>&1; then\n"
    "    PY=\"winpty python\"\n"
    "elif command -v python3 >/dev/null 2>&1; then\n"
    "    PY=\"python3\"\n"
    "else\n"
    "    PY=\"python\"\n"
    "fi\n"
)
WINPTY_PREFIX = "winpty python "

BC64_ROOT_FILES = ("README.md", "LICENSE", "pyproject.toml", "docs/README.md")
BC64_DOCS_RE = re.compile(r"^docs/0[^/]*-[^/]*\.md$")
# Test tooling: the tests aren't shipped, so their runner isn't either.
BC64_EXCLUDED_FILES = ("src/run_tests",)
EXCLUDED_DIRS = ("tests", "testdata")
EXCLUDED_PREFIXES = ("docs/specs/", "docs/analysis/", "docs/CHANGELOG.md", ".github/", "release/")
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ReleaseError(Exception):
    """A problem reported to the user as one line."""


# --- git access -----------------------------------------------------------------------

def git(root, *args, binary=False):
    """Run git in root and return its stdout; raise ReleaseError on failure."""
    try:
        completed = subprocess.run(["git", "-C", root] + list(args), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    except OSError as error:
        raise ReleaseError("git could not be started (%s)" % error)
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        raise ReleaseError("git %s failed: %s" % (args[0], message[-1] if message else "exit code %d"
                                                  % completed.returncode))
    return completed.stdout if binary else completed.stdout.decode("utf-8")


def find_root(start=None):
    """Return the top folder of the git clone holding start (default: this script)."""
    start = start or os.path.dirname(os.path.abspath(__file__))
    try:
        completed = subprocess.run(["git", "-C", start, "rev-parse", "--show-toplevel"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   stdin=subprocess.DEVNULL)
    except OSError as error:
        raise ReleaseError("git could not be started (%s)" % error)
    if completed.returncode != 0:
        raise ReleaseError("%s is not inside a git clone" % start)
    return completed.stdout.decode("utf-8").strip()


def require_commit(root, commit):
    """Raise ReleaseError unless commit exists in the clone."""
    completed = subprocess.run(["git", "-C", root, "cat-file", "-e", commit + "^{commit}"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               stdin=subprocess.DEVNULL)
    if completed.returncode != 0:
        raise ReleaseError("commit %s is not in this clone (a shallow clone? fetch the full history)"
                           % commit)


def list_tree(root, commit, prefix=None):
    """Return [(path, mode, blob id)] of the files in commit (under prefix, if given)."""
    args = ["ls-tree", "-r", "-z", "--full-tree", commit]
    if prefix:
        args += ["--", prefix]
    entries = []
    for record in git(root, *args).split("\0"):
        if not record:
            continue
        meta, path = record.split("\t", 1)
        mode, kind, blob = meta.split()
        if kind == "blob":
            entries.append((path, mode, blob))
    return entries


def read_blobs(root, blobs):
    """Return {blob id: bytes} for the given blob ids, read raw (no line-ending conversion)."""
    unique = list(dict.fromkeys(blobs))
    if not unique:
        return {}
    completed = subprocess.run(["git", "-C", root, "cat-file", "--batch"],
                               input=("\n".join(unique) + "\n").encode("ascii"),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        raise ReleaseError("git cat-file failed: %s"
                           % completed.stderr.decode("utf-8", "replace").strip())
    out = completed.stdout
    contents, pos = {}, 0
    for blob in unique:
        end = out.index(b"\n", pos)
        header = out[pos:end].decode("ascii").split()
        if len(header) != 3:
            raise ReleaseError("git object %s is missing" % blob)
        size = int(header[2])
        contents[blob] = out[end + 1:end + 1 + size]
        pos = end + 1 + size + 1
    return contents


def show(root, commit, path):
    """Return the raw bytes of path at commit."""
    return git(root, "show", "%s:%s" % (commit, path), binary=True)


def commit_time(root, commit):
    """Return the commit's time as a zip date_time tuple (UTC)."""
    seconds = int(git(root, "show", "-s", "--format=%ct", commit).strip())
    stamp = time.gmtime(seconds)
    return (max(stamp.tm_year, 1980),) + tuple(stamp[1:6])


# --- zip writing ----------------------------------------------------------------------

def write_zip(path, root_name, files, date_time):
    """Write files [(relative path, bytes, unix mode)] under root_name/ into the zip at path."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data, mode in sorted(files):
            info = zipfile.ZipInfo(root_name + "/" + name, date_time=date_time)
            info.create_system = 3  # unix, so unzip applies the mode
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    os.replace(tmp, path)
    return path


def git_mode(mode):
    return 0o755 if mode == "100755" else 0o644


# --- bc64 -----------------------------------------------------------------------------

def is_bc64_file(path):
    """True if a tracked path belongs in the bc64 zip."""
    if path.startswith(EXCLUDED_PREFIXES) or path in BC64_EXCLUDED_FILES:
        return False
    if any(part in EXCLUDED_DIRS for part in path.split("/")[:-1]):
        return False
    return path.startswith("src/") or path in BC64_ROOT_FILES or bool(BC64_DOCS_RE.match(path))


def bc64_files(root, commit="HEAD"):
    """Return [(path, bytes, mode)] of the bc64 zip, read from commit."""
    entries = [entry for entry in list_tree(root, commit) if is_bc64_file(entry[0])]
    blobs = read_blobs(root, [blob for _path, _mode, blob in entries])
    return [(path, blobs[blob], git_mode(mode)) for path, mode, blob in entries]


def make_bc64(root, tag, out_dir):
    if not TAG_RE.match(tag):
        raise ReleaseError("invalid zip name %r (letters, digits, '.', '_' and '-' only)" % tag)
    files = bc64_files(root)
    names = {path for path, _data, _mode in files}
    for needed in ("src/bc64.py", "src/os.bdd", "src/bc81asmc/bcOS/bcos_v1_2_0.b81", "src/run"):
        if needed not in names:
            raise ReleaseError("%s is not tracked at HEAD" % needed)
    return write_zip(os.path.join(out_dir, tag + ".zip"), tag, files, commit_time(root, "HEAD"))


# --- legacy ---------------------------------------------------------------------------

def legacy_name(generation):
    return "%s-v1.0" % generation


def check_generation(generation, allowed):
    if generation not in allowed:
        raise ReleaseError("unknown generation %r (choose %s)" % (generation, ", ".join(allowed)))


def replace_interpreter(script):
    """Return the run script with "winpty python" replaced by the interpreter pick of src/run."""
    text = script.decode("utf-8")
    lines = text.splitlines(keepends=True)
    result, replaced = [], False
    for line in lines:
        if line.startswith(WINPTY_PREFIX):
            result.append(INTERPRETER_PICK)
            result.append("$PY " + line[len(WINPTY_PREFIX):])
            replaced = True
        else:
            result.append(line)
    if not replaced:
        raise ReleaseError("the run script has no '%s' line" % WINPTY_PREFIX.strip())
    return "".join(result).encode("utf-8")


def build_bc16_rom(root, python=None):
    """Assemble bcOS 1.0 from BC16_ROM_COMMIT with that commit's assembler; return the ROM."""
    require_commit(root, BC16_ROM_COMMIT)
    prefix = "src/bc81asmc/"
    entries = list_tree(root, BC16_ROM_COMMIT, prefix)
    blobs = read_blobs(root, [blob for _path, _mode, blob in entries])
    work = tempfile.mkdtemp(prefix="bc16rom-")
    try:
        asm_dir = os.path.join(work, "bc81asmc")
        for path, _mode, blob in entries:
            target = os.path.join(asm_dir, *path[len(prefix):].split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(blobs[blob])
        completed = subprocess.run([python or sys.executable, "bc81asmc.py", "bcOS/bcos.basm"],
                                   cwd=asm_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL)
        rom = os.path.join(asm_dir, "bcOS", "bcos.b81")
        if completed.returncode != 0 or not os.path.exists(rom):
            lines = completed.stdout.decode("utf-8", "replace").strip().splitlines()
            raise ReleaseError("assembling the bc16 ROM failed: %s"
                               % (lines[-1] if lines else "exit code %d" % completed.returncode))
        with open(rom, "rb") as handle:
            return handle.read()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def legacy_rom(root, generation):
    """Return (file name, bytes) of the generation's ROM."""
    if generation == "bc32":
        require_commit(root, BC32_ROM_COMMIT)
        return "bcos_v1_1_1.b81", show(root, BC32_ROM_COMMIT, "src/bc81asmc/bcOS/bcos_v1_1_1.b81")
    return "bcos.b81", build_bc16_rom(root)


def legacy_files(root, generation):
    """Return [(path, bytes, mode)] of the legacy zip."""
    check_generation(generation, LEGACY_GENERATIONS)
    require_commit(root, LEGACY_COMMIT)
    prefix = "release/%s_v1.0/" % generation
    entries = list_tree(root, LEGACY_COMMIT, prefix)
    if not entries:
        raise ReleaseError("%s has no %s" % (LEGACY_COMMIT, prefix))
    blobs = read_blobs(root, [blob for _path, _mode, blob in entries])
    files = []
    for path, mode, blob in entries:
        name, data = path[len(prefix):], blobs[blob]
        if name == "run":
            data = replace_interpreter(data)
        # scripts are stored as 100644 there; make the ones with a #! line executable
        executable = mode == "100755" or data.startswith(b"#!")
        files.append((name, data, 0o755 if executable else 0o644))
    rom_name, rom = legacy_rom(root, generation)
    files.append(("rom/" + rom_name, rom, 0o644))
    files.append(("RELEASE-NOTES.md", notes(root, generation).encode("utf-8"), 0o644))
    return files


def make_legacy(root, generation, out_dir):
    files = legacy_files(root, generation)
    name = legacy_name(generation)
    return write_zip(os.path.join(out_dir, name + ".zip"), name, files,
                     commit_time(root, LEGACY_COMMIT))


# --- notes ----------------------------------------------------------------------------

def readme_section(readme, heading):
    """Return the README text from the line "# heading" up to the next top-level heading.

    Lines inside ``` fences are never headings (bash comments start with "# ").
    """
    lines = readme.replace("\r\n", "\n").split("\n")
    section, inside, fenced = [], False, False
    for line in lines:
        is_heading = not fenced and line.startswith("# ")
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if is_heading:
            if inside:
                break
            inside = line[2:].strip() == heading
        if inside:
            section.append(line)
    if not section:
        raise ReleaseError("README.md has no '# %s' section" % heading)
    return "\n".join(section).strip() + "\n"


def notes(root, generation):
    """Return the release notes of a generation (Markdown)."""
    check_generation(generation, NOTES_GENERATIONS)
    readme = show(root, "HEAD", "README.md").decode("utf-8")
    section = readme_section(readme, generation.upper())
    if generation == "bc64":
        return section
    if generation == "bc16":
        rom = ("`rom/bcos.b81` (bcOS 1.0) was assembled for this release from "
               "`src/bc81asmc/bcOS/bcos.basm` at commit `%s` with the assembler of that commit."
               % BC16_ROM_COMMIT)
        start = "cd tape` and loads `../rom/bcos.b81"
    else:
        rom = ("`rom/bcos_v1_1_1.b81` (bcOS 1.1.1) is `src/bc81asmc/bcOS/bcos_v1_1_1.b81` "
               "as at the release commit `%s`." % BC32_ROM_COMMIT)
        start = "cd discs` and loads `../rom/bcos_v1_1_1.b81"
    intro = (
        "Frozen %s machine generation (tag `%s` on `%s`). The files are `release/%s_v1.0/` "
        "as at commit `%s`, which can be newer than the tagged commit.\n\n"
        "- %s\n"
        "- `run` does `%s`. The only change to the frozen files: it no longer calls "
        "`winpty python` but picks the interpreter like `src/run` (`winpty python` when "
        "`winpty` is on `PATH`, otherwise `python3`, otherwise `python`).\n\n"
        % (generation.upper(), legacy_name(generation), TAG_TARGETS[generation], generation,
           LEGACY_COMMIT, rom, start))
    return intro + section


# --- command line ---------------------------------------------------------------------

def parse_args(argv):
    parser = argparse.ArgumentParser(description="Build the GitHub Release zips and notes.")
    commands = parser.add_subparsers(dest="command", required=True)
    bc64 = commands.add_parser("bc64", help="zip the current machine")
    bc64.add_argument("--tag", required=True, help="zip name and root folder, e.g. bc64-v1.0")
    bc64.add_argument("--out", help="output folder (default: dist/ in the repo root)")
    legacy = commands.add_parser("legacy", help="zip a frozen generation")
    legacy.add_argument("generation", help="bc16 or bc32")
    legacy.add_argument("--out", help="output folder (default: dist/ in the repo root)")
    note = commands.add_parser("notes", help="print the release notes")
    note.add_argument("generation", help="bc64, bc16 or bc32")
    return parser.parse_args(argv)


def run(options):
    if options.command == "legacy":
        check_generation(options.generation, LEGACY_GENERATIONS)
    elif options.command == "notes":
        check_generation(options.generation, NOTES_GENERATIONS)
    root = find_root()
    if options.command == "notes":
        sys.stdout.write(notes(root, options.generation))
        return
    out_dir = os.path.abspath(options.out) if options.out else os.path.join(root, "dist")
    if options.command == "bc64":
        path = make_bc64(root, options.tag, out_dir)
    else:
        path = make_legacy(root, options.generation, out_dir)
    print(path)


def main(argv=None):
    options = parse_args(argv)
    try:
        run(options)
    except ReleaseError as error:
        sys.stderr.write("make_release: error: %s\n" % error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
