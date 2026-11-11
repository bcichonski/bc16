"""Tests of scripts/make_release.py. They read the real git history (read-only) and write
only to temp folders. Run from scripts/: python3 -m unittest discover -s tests -t . -p "test_*.py"
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SCRIPTS, "make_release.py")
sys.path.insert(0, SCRIPTS)
import make_release  # noqa: E402

ROOT = make_release.find_root(SCRIPTS)

# The first bytes of bcOS 1.0 assembled from bd2498a: a jump, then the "bcOS 1.0" banner.
BC16_ROM_START = bytes.fromhex("180a146c5c10600862634f5320312e30")
BC16_ROM_SIZE = 3057


def git(*args):
    return subprocess.run(["git", "-C", ROOT] + list(args), stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, check=True).stdout


def history_missing():
    """Return why the legacy commits can't be read, or None."""
    if git("rev-parse", "--is-shallow-repository").decode().strip() == "true":
        return "shallow clone: the legacy release commits are not available"
    for commit in (make_release.LEGACY_COMMIT, make_release.BC16_ROM_COMMIT):
        try:
            make_release.require_commit(ROOT, commit)
        except make_release.ReleaseError:
            return "commit %s is not in this clone" % commit
    return None


def mode_of(info):
    return (info.external_attr >> 16) & 0o777


def run_script(script, *args, cwd=None, env=None):
    return subprocess.run([sys.executable, script] + list(args), cwd=cwd, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          stdin=subprocess.DEVNULL, encoding="utf-8")


class ZipChecks:
    """Mixin: builds one zip per class into a temp folder, opens it and checks the common rules."""

    zip_root = None

    @classmethod
    def build(cls, out_dir):
        raise NotImplementedError

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="make-release-test-")
        try:
            cls.path = cls.build(cls.tmp)
            cls.archive = zipfile.ZipFile(cls.path)
        except Exception:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise
        cls.infos = {info.filename: info for info in cls.archive.infolist()}
        prefix = cls.zip_root + "/"
        cls.names = [name[len(prefix):] for name in cls.infos if name.startswith(prefix)]

    @classmethod
    def tearDownClass(cls):
        cls.archive.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def read(self, name):
        return self.archive.read(self.zip_root + "/" + name)

    def info(self, name):
        return self.infos[self.zip_root + "/" + name]

    def test_one_root_folder(self):
        self.assertEqual(os.path.basename(self.path), self.zip_root + ".zip")
        self.assertTrue(all(name.startswith(self.zip_root + "/") for name in self.infos))
        self.assertEqual(len(self.names), len(self.infos))

    def test_run_is_executable(self):
        self.assertEqual(mode_of(self.info("run" if "run" in self.names else "src/run")), 0o755)


class Bc64ZipTests(ZipChecks, unittest.TestCase):
    zip_root = "bc64-unittest"

    @classmethod
    def build(cls, out_dir):
        return make_release.make_bc64(ROOT, cls.zip_root, out_dir)

    def test_holds_what_is_needed_to_run_and_build(self):
        for name in ("src/bc64.py", "src/bc64/bc8183_cpu.py", "src/bc81asmc/bcOS/bcos_v1_2_0.b81",
                     "src/os.bdd", "src/run", "src/bcc", "src/buildos", "src/makedisc",
                     "src/disc.bddmanifest", "src/ftool.py", "src/bc64_toolchain.py",
                     "src/bc/bc.py", "src/bc81asmc/bc81asmc.py", "src/bdos/bdos.b",
                     "README.md", "LICENSE", "pyproject.toml", "docs/README.md",
                     "docs/01-emulator.md"):
            self.assertIn(name, self.names)

    def test_no_tests_testdata_ci_or_planning_files(self):
        for name in self.names:
            parts = name.split("/")
            self.assertNotIn("tests", parts[:-1], name)
            self.assertNotIn("testdata", parts[:-1], name)
            self.assertFalse(name.startswith((".github/", "release/", "docs/specs/",
                                              "docs/analysis/")), name)
            self.assertNotEqual(name, "docs/CHANGELOG.md")
            self.assertNotEqual(name, "run_tests.py")

    def test_no_ignored_file(self):
        listing = "\n".join(self.names) + "\n"
        completed = subprocess.run(["git", "-C", ROOT, "check-ignore", "--no-index", "--stdin"],
                                   input=listing, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, encoding="utf-8")
        self.assertEqual(completed.stdout, "")
        for name in self.names:
            self.assertFalse(name.endswith((".btap", ".sector", ".genb")), name)

    def test_only_files_tracked_at_head(self):
        tracked = set(git("ls-tree", "-r", "--name-only", "--full-tree", "HEAD")
                      .decode("utf-8").splitlines())
        self.assertLessEqual(set(self.names), tracked)

    def test_content_is_the_committed_blob(self):
        for name in ("src/run", "src/bc81asmc/bcOS/bcos_v1_2_0.b81", "README.md"):
            self.assertEqual(self.read(name), git("show", "HEAD:" + name), name)
        self.assertNotIn(b"\r\n", self.read("src/run"))

    def test_modes_follow_git(self):
        for name in ("src/bcc", "src/buildos", "src/buildtools", "src/buildapps", "src/makedisc",
                     "src/ftool"):
            self.assertEqual(mode_of(self.info(name)), 0o755, name)
        self.assertEqual(mode_of(self.info("src/bc64.py")), 0o644)

    def test_invalid_tag_is_refused(self):
        with self.assertRaises(make_release.ReleaseError):
            make_release.make_bc64(ROOT, "../evil", self.tmp)


class LegacyZipMixin:
    generation = None
    rom_name = None
    start_line = None

    @classmethod
    def build(cls, out_dir):
        return make_release.make_legacy(ROOT, cls.generation, out_dir)

    @classmethod
    def setUpClass(cls):
        reason = history_missing()
        if reason:
            raise unittest.SkipTest(reason)
        super().setUpClass()

    def frozen(self):
        prefix = "release/%s_v1.0/" % self.generation
        paths = git("ls-tree", "-r", "--name-only", "--full-tree", make_release.LEGACY_COMMIT,
                    "--", prefix).decode("utf-8").splitlines()
        return {path[len(prefix):]: path for path in paths}

    def test_snapshot_files_are_byte_equal_to_the_commit(self):
        frozen = self.frozen()
        self.assertTrue(frozen)
        for name, path in frozen.items():
            if name != "run":
                self.assertEqual(self.read(name),
                                 git("show", "%s:%s" % (make_release.LEGACY_COMMIT, path)), name)

    def test_exactly_snapshot_plus_rom_and_notes(self):
        expected = set(self.frozen()) | {"rom/" + self.rom_name, "RELEASE-NOTES.md"}
        self.assertEqual(set(self.names), expected)

    def test_run_differs_only_in_the_interpreter(self):
        path = self.frozen()["run"]
        frozen = git("show", "%s:%s" % (make_release.LEGACY_COMMIT, path)).decode().splitlines()
        new = self.read("run").decode().splitlines()
        self.assertFalse([line for line in new if "winpty python " in line
                          and not line.strip().startswith(("PY=", "#"))])
        self.assertIn(self.start_line, new)
        kept = [line for line in frozen if not line.startswith("winpty python ")]
        self.assertEqual(len(kept), len(frozen) - 1)
        self.assertEqual([line for line in new if line in kept], kept)
        expected = []
        for line in frozen:
            if line.startswith("winpty python "):
                expected += make_release.INTERPRETER_PICK.splitlines()
                expected.append("$PY " + line[len("winpty python "):])
            else:
                expected.append(line)
        self.assertEqual(new, expected)

    def test_notes_are_shipped(self):
        notes = self.read("RELEASE-NOTES.md").decode("utf-8")
        self.assertIn("# " + self.generation.upper(), notes)
        self.assertIn("winpty python", notes)
        self.assertIn(self.rom_name, notes)


class Bc16ZipTests(LegacyZipMixin, ZipChecks, unittest.TestCase):
    generation = "bc16"
    zip_root = "bc16-v1.0"
    rom_name = "bcos.b81"
    start_line = "$PY ../bc16.py ../rom/bcos.b81 $1"

    def test_rom_is_the_assembled_bcos_1_0(self):
        rom = self.read("rom/bcos.b81")
        self.assertEqual(len(rom), BC16_ROM_SIZE)
        self.assertEqual(rom[:len(BC16_ROM_START)], BC16_ROM_START)

    def test_tapes_are_shipped(self):
        self.assertIn("tape/hello.run.btap", self.names)


class Bc32ZipTests(LegacyZipMixin, ZipChecks, unittest.TestCase):
    generation = "bc32"
    zip_root = "bc32-v1.0"
    rom_name = "bcos_v1_1_1.b81"
    start_line = "$PY ../bc32.py ../rom/bcos_v1_1_1.b81 $1"

    def test_rom_is_bcos_1_1_1_of_the_legacy_commit(self):
        self.assertEqual(self.read("rom/bcos_v1_1_1.b81"),
                         git("show", make_release.LEGACY_COMMIT
                             + ":src/bc81asmc/bcOS/bcos_v1_1_1.b81"))

    def test_disc_is_shipped(self):
        self.assertIn("discs/bdos.bdd", self.names)


class ReplaceInterpreterTests(unittest.TestCase):
    def test_only_the_winpty_line_changes(self):
        script = b"#!/bin/bash\ncd tape\nwinpty python ../x.py ../rom/r.b81 $1\n"
        out = make_release.replace_interpreter(script).decode()
        self.assertTrue(out.startswith("#!/bin/bash\ncd tape\n"))
        self.assertTrue(out.endswith("fi\n$PY ../x.py ../rom/r.b81 $1\n"))
        self.assertIn(make_release.INTERPRETER_PICK, out)

    def test_pick_is_the_one_of_src_run(self):
        src_run = git("show", "HEAD:src/run").decode("utf-8")
        self.assertIn(make_release.INTERPRETER_PICK, src_run)

    def test_script_without_winpty_is_an_error(self):
        with self.assertRaises(make_release.ReleaseError):
            make_release.replace_interpreter(b"#!/bin/bash\npython3 x.py\n")


class NotesTests(unittest.TestCase):
    README = (
        "intro\n\n# Getting started\n```bash\n# not a heading\n```\n"
        "# BC64\n## roadmap\n```\n# comment in code\n```\nend64\n"
        "# BC32\nbc32 text\n"
    )

    def test_section_runs_to_the_next_top_level_heading(self):
        section = make_release.readme_section(self.README, "BC64")
        self.assertEqual(section, "# BC64\n## roadmap\n```\n# comment in code\n```\nend64\n")
        self.assertEqual(make_release.readme_section(self.README, "BC32"), "# BC32\nbc32 text\n")

    def test_missing_section_is_an_error(self):
        with self.assertRaises(make_release.ReleaseError):
            make_release.readme_section(self.README, "BC16")

    def test_each_generation_uses_its_readme_section(self):
        readme = git("show", "HEAD:README.md").decode("utf-8")
        for generation in ("bc64", "bc16", "bc32"):
            section = make_release.readme_section(readme, generation.upper())
            notes = make_release.notes(ROOT, generation)
            self.assertTrue(notes.endswith(section), generation)
            others = {"bc64", "bc16", "bc32"} - {generation}
            for other in others:
                self.assertNotIn("\n# %s\n" % other.upper(), "\n" + notes)
        self.assertEqual(make_release.notes(ROOT, "bc64"),
                         make_release.readme_section(readme, "BC64"))

    def test_legacy_notes_name_the_run_change_and_rom_origin(self):
        bc16 = make_release.notes(ROOT, "bc16")
        self.assertIn(make_release.BC16_ROM_COMMIT, bc16)
        self.assertIn("winpty python", bc16)
        bc32 = make_release.notes(ROOT, "bc32")
        self.assertIn("bcos_v1_1_1.b81", bc32)
        self.assertIn(make_release.LEGACY_COMMIT, bc32)

    def test_cli_prints_the_notes_from_another_cwd(self):
        with tempfile.TemporaryDirectory() as cwd:
            completed = run_script(SCRIPT, "notes", "bc64", cwd=cwd)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, make_release.notes(ROOT, "bc64"))


class ErrorTests(unittest.TestCase):
    def assert_one_line_error(self, completed, *fragments):
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        lines = completed.stderr.strip().splitlines()
        self.assertEqual(len(lines), 1, completed.stderr)
        for fragment in fragments:
            self.assertIn(fragment, lines[0])

    def test_unknown_generation(self):
        self.assert_one_line_error(run_script(SCRIPT, "legacy", "bc8"), "bc8")
        self.assert_one_line_error(run_script(SCRIPT, "notes", "bc128"), "bc128")
        self.assert_one_line_error(run_script(SCRIPT, "legacy", "bc64"), "bc64")

    def test_outside_a_git_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, "make_release.py")
            shutil.copy(SCRIPT, copy)
            env = dict(os.environ, GIT_CEILING_DIRECTORIES=os.path.dirname(tmp))
            completed = run_script(copy, "notes", "bc64", cwd=tmp, env=env)
        self.assert_one_line_error(completed, "not inside a git clone")

    def test_missing_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            copy = os.path.join(tmp, "make_release.py")
            shutil.copy(SCRIPT, copy)
            env = dict(os.environ, GIT_CEILING_DIRECTORIES=os.path.dirname(tmp))
            completed = run_script(copy, "legacy", "bc32", "--out", tmp, cwd=tmp, env=env)
        self.assert_one_line_error(completed, make_release.LEGACY_COMMIT)


if __name__ == "__main__":
    unittest.main()
