"""Tests of src/tests/e2e_areas.py, the e2e area map (silent; static checks only)."""
import ast
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SCRIPT = os.path.join(HERE, "e2e_areas.py")

_spec = importlib.util.spec_from_file_location("e2e_areas_under_test", SCRIPT)
areas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(areas)


def _module_tests(module):
    """{class name: {test names}} of a module, read from its source (never imported)."""
    with open(os.path.join(HERE, module + ".py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return {
        node.name: {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
        for node in tree.body if isinstance(node, ast.ClassDef)
    }


class MapTests(unittest.TestCase):
    def test_every_discovered_e2e_module_is_mapped_to_a_known_area(self):
        for module in areas.discover_modules(HERE):
            self.assertIn(module, areas.MODULE_AREA, module + " is missing from MODULE_AREA")
            self.assertIn(areas.area_of_module(module), areas.AREAS)

    def test_map_names_no_missing_module(self):
        self.assertEqual(sorted(areas.MODULE_AREA), sorted(areas.discover_modules(HERE)))

    def test_area_of_module_accepts_tests_prefix_and_unknown(self):
        self.assertEqual(areas.area_of_module("tests.test_e2e_calc"), "bdos")
        self.assertEqual(areas.area_of_module("test_e2e_rom"), "bcos")
        self.assertIsNone(areas.area_of_module("test_e2e_nonexistent"))

    def test_modules_of_areas_filters_the_given_list(self):
        found = ["test_e2e_calc", "test_e2e_rom", "test_e2e_return", "test_e2e_harness"]
        self.assertEqual(areas.modules_of_areas(["bcos", "compiler"], found),
                         ["test_e2e_rom", "test_e2e_return"])
        self.assertEqual(areas.modules_of_areas(["assembler"], found), [])

    def test_every_happy_id_resolves_statically(self):
        for ident in areas.HAPPY:
            parts = ident.split(".")
            self.assertIn(parts[0], areas.MODULE_AREA, ident)
            if len(parts) == 1:
                continue
            tests = _module_tests(parts[0])
            self.assertIn(parts[1], tests, ident)
            if len(parts) == 3:
                self.assertIn(parts[2], tests[parts[1]], ident)
                self.assertTrue(parts[2].startswith("test_"), ident)

    def test_every_area_with_modules_has_a_happy_id(self):
        modules = areas.discover_modules(HERE)
        for area in areas.areas_with_modules(modules):
            ids = [i for m in areas.modules_of_areas([area], modules) for i in areas.happy_ids(m)]
            self.assertTrue(ids, "area %s has no happy test" % area)

    def test_happy_ids_of_a_module(self):
        self.assertEqual(areas.happy_ids("tests.test_e2e_rom"), ["test_e2e_rom"])
        self.assertEqual(len(areas.happy_ids("test_e2e_bdos")), 5)
        self.assertEqual(areas.happy_ids("test_e2e_bdos_args"), [])

    def test_assembler_has_no_e2e_module(self):
        self.assertNotIn("assembler", areas.areas_with_modules(areas.discover_modules(HERE)))


class TriggerTests(unittest.TestCase):
    def check(self, paths, expected):
        self.assertEqual(areas.areas_for_paths(paths), set(expected), paths)

    def test_docs_and_scripts_trigger_nothing(self):
        self.check(["docs/x.md"], [])
        self.check(["README.md", "src/bdos/notes.md", "LICENSE", "scripts/verify.sh",
                    "bc/grammar.txt", ".github/workflows/release.yml",
                    "src/bc/code_size.csv"], [])

    def test_unit_test_only_changes_trigger_nothing(self):
        self.check(["src/tests/test_ftool.py", "src/tests/test_areas.py"], [])
        self.check(["src/bc64/tests/test_cpu.py", "src/bc/tests/test_x.py",
                    "src/bc81asmc/tests/test_y.py"], [])

    def test_e2e_module_triggers_its_area_only(self):
        self.check(["src/tests/test_e2e_calc.py"], ["bdos"])
        self.check(["src/tests/test_bc64_smoke.py"], ["bdos"])
        self.check(["src/tests/test_e2e_rom.py"], ["bcos"])
        self.check(["src/tests/test_e2e_return.py", "src/tests/test_e2e_harness.py"],
                   ["compiler", "emulator"])

    def test_unmapped_e2e_module_triggers_everything(self):
        self.check(["src/tests/test_e2e_brand_new.py"], areas.AREAS)

    def test_shared_paths_trigger_everything(self):
        for path in ["src/bc/bc.py", "src/bc81asmc/bcOS/bcos.basm", "src/bdos/strings.b",
                     "src/bdos/std.b", "src/bc/code/x.b", "src/bc64.py", "src/bc64/cpu.py",
                     "src/bc64/testdata/e2e/x.txt", "run_tests.py", "pyproject.toml",
                     ".github/workflows/tests.yml", "src/tests/e2e_harness.py",
                     "src/tests/e2e_areas.py", "src/tests/__init__.py", "src/buildos",
                     "src/makedisc", "src/ftool", "src/ftool_text.py"]:
            self.check([path], areas.AREAS)

    def test_bdos_only_paths_trigger_bdos_and_compiler(self):
        self.check(["src/bdos/ls.b"], ["bdos", "compiler"])
        self.check(["src/bdos/texted.b"], ["bdos", "compiler"])
        self.check(["src/disc.bddmanifest"], ["bdos", "compiler"])

    def test_unknown_path_triggers_everything(self):
        self.check(["something/unknown.bin"], areas.AREAS)

    def test_union_over_paths_and_normalisation(self):
        self.check(["docs/a.md", "./src/tests/test_e2e_calc.py"], ["bdos"])
        self.check(["src/tests/test_e2e_calc.py", "src/tests/test_e2e_rom.py"], ["bdos", "bcos"])
        self.check([], [])


class CliTests(unittest.TestCase):
    def run_cli(self, *args, cwd=REPO):
        proc = subprocess.run([sys.executable, SCRIPT] + list(args), cwd=cwd,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def all_areas(self):
        return areas.areas_with_modules(areas.discover_modules(HERE))

    def test_zero_empty_or_bad_base_gives_all_areas_with_modules(self):
        for base in ("0" * 40, "", "deadbeef" * 5, "not-a-commit"):
            out = self.run_cli("changed", "--base", base, "--head", "HEAD")
            self.assertEqual(json.loads(out), self.all_areas(), base)
            self.assertEqual(out.strip(), json.dumps(self.all_areas(), separators=(",", ":")))

    def test_bad_base_outside_a_repository_gives_all_areas(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.run_cli("changed", "--base", "abc", "--head", "HEAD", cwd=tmp)
        self.assertEqual(json.loads(out), self.all_areas())

    def test_real_commit_range_gives_a_sorted_subset(self):
        probe = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "HEAD~1^{commit}"],
                               cwd=REPO, capture_output=True, text=True)
        if probe.returncode != 0:
            self.skipTest("clone has no parent commit")
        result = json.loads(self.run_cli("changed", "--base", "HEAD~1", "--head", "HEAD"))
        self.assertIsInstance(result, list)
        self.assertEqual(result, sorted(result))
        self.assertTrue(set(result) <= set(self.all_areas()))

    def test_same_commit_gives_no_areas(self):
        probe = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "HEAD^{commit}"],
                               cwd=REPO, capture_output=True, text=True)
        if probe.returncode != 0:
            self.skipTest("not a git clone")
        self.assertEqual(json.loads(self.run_cli("changed", "--base", "HEAD", "--head", "HEAD")), [])


if __name__ == "__main__":
    unittest.main()
