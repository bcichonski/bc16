"""Area map of the end-to-end tests: which module belongs to which area, which tests
make up the happy-path tier, and which changed paths trigger which areas.

Standard library only and loadable by file path (importlib); never imported as a
package. Command line (used by CI):

    python3 src/tests/e2e_areas.py changed --base <sha> --head <sha>
    python3 src/tests/e2e_areas.py list

`changed` prints a compact sorted JSON array of the areas whose e2e tests must run
for the diff base..head (only areas that have e2e modules). A base that is empty,
all zeros or not a commit of this clone yields every area.
"""
import argparse
import fnmatch
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))

# Named after the doc pages 01..05.
AREAS = ("emulator", "assembler", "compiler", "bcos", "bdos")

# Every e2e module (module name without the "tests." prefix) belongs to exactly one area.
MODULE_AREA = {
    "test_e2e_harness": "emulator",
    "test_e2e_toolchain": "compiler",
    "test_e2e_return": "compiler",
    "test_e2e_bcos": "bcos",
    "test_e2e_rom": "bcos",
    "test_bc64_smoke": "bdos",
    "test_e2e_bdos": "bdos",
    "test_e2e_bdos_args": "bdos",
    "test_e2e_bdos_cmdtable": "bdos",
    "test_e2e_bdio_buffered": "bdos",
    "test_e2e_bdio_errors": "bdos",
    "test_e2e_alloc_gap": "bdos",
    "test_e2e_rm_alloc": "bdos",
    "test_e2e_ls_free": "bdos",
    "test_e2e_compile_cycles": "bdos",
    "test_e2e_disc": "bdos",
    "test_e2e_utils_disc": "bdos",
    "test_e2e_layout_shift": "bdos",
    "test_e2e_random": "bdos",
    "test_e2e_ftool_text": "bdos",
    "test_e2e_texted": "bdos",
    "test_e2e_texted_commands": "bdos",
    "test_e2e_texted_disc_full": "bdos",
    "test_e2e_texted_flows": "bdos",
    "test_e2e_calc": "bdos",
    "test_e2e_theodore": "bdos",
}

# Happy-path tier: "module", "module.Class" or "module.Class.test" (module without "tests.").
HAPPY = (
    "test_bc64_smoke",
    "test_e2e_bdos.BdosShellTests.test_boot_prompt_and_exit",
    "test_e2e_bdos.BdosShellTests.test_ls_lists_catalog",
    "test_e2e_bdos.BdosShellTests.test_cat_prints_text_file",
    "test_e2e_bdos.BdosShellTests.test_hellowrd_prints_greeting",
    "test_e2e_bdos.BdosShellTests.test_rm_removes_file_from_ls_and_catalog",
    "test_e2e_disc.DiscStructureTests",
    "test_e2e_disc.DiscSessionTests.test_ls_all_lists_every_file",
    "test_e2e_utils_disc.UtilsDiscStructureTests.test_utils_bdd_matches_manifest",
    "test_e2e_utils_disc.UtilsDiscSessionTests.test_hellowrd_runs_from_b_and_returns_to_b_prompt",
    "test_e2e_calc.CalcTests.test_each_operation",
    "test_e2e_theodore.TheodoreTests.test_seeded_game_north_south_found_bye",
    "test_e2e_texted.TextedRoundTripTests.test_save_restart_load_prints_same_lines",
    "test_e2e_texted_flows.TextedFlowTests.test_startup_banner",
    "test_e2e_bcos.BcosMonitorTests.test_boot_and_unknown_command",
    "test_e2e_bcos.BcosMonitorTests.test_dump_write_print",
    "test_e2e_rom",
    "test_e2e_toolchain",
    "test_e2e_return",
    "test_e2e_harness.SessionRunnerTests.test_real_boot_returns_output_and_leaves_source_untouched",
    "test_e2e_harness.GoldenTests",
    "test_e2e_harness.DiscMasksTests",
    "test_e2e_harness.CatalogTests",
    "test_e2e_harness.SlowDecoratorTests",
)

# Trigger rules, first match wins per path. Each rule: (fnmatch patterns, areas);
# "*" in fnmatch also matches "/", so "dir/*" covers a whole subtree.
NONE = ()
ALL = AREAS
_SHARED_BDOS_LIBS = ("std", "stdio", "stdmem", "strings", "bdosh", "bdioh",
                     "bdosargs", "bdostools", "random")
_E2E_INFRA = ("src/tests/e2e_harness.py", "src/tests/e2e_areas.py", "src/tests/__init__.py")

RULES = (
    (("docs/*", "*.md", "LICENSE", "bc/*", "scripts/*", ".github/workflows/release.yml",
      "src/bc/code_size.csv"), NONE),
    (("src/bc64/tests/*", "src/bc/tests/*", "src/bc81asmc/tests/*"), NONE),
    (_E2E_INFRA, ALL),
    (("run_tests.py", "pyproject.toml", ".github/workflows/tests.yml",
      "src/bc64/testdata/*",
      "src/buildos", "src/buildtools", "src/buildapps", "src/makedisc", "src/bcc",
      "src/ftool", "src/ftool*.py",
      "src/bc64.py", "src/bc64/*", "src/bc81asmc/*", "src/bc/*")
     + tuple("src/bdos/%s.%s" % (name, ext) for name in _SHARED_BDOS_LIBS for ext in ("b", "h")), ALL),
    (("src/bdos/*", "src/disc.bddmanifest", "src/utils.bddmanifest"), ("bdos", "compiler")),
)


def area_of_module(module):
    """Area of an e2e module name ('tests.' prefix optional), or None if unmapped."""
    return MODULE_AREA.get(module.rsplit(".", 1)[-1] if module.startswith("tests.") else module)


def discover_modules(tests_dir=HERE):
    """Names of the e2e modules (as run_tests.py recognises them) in tests_dir."""
    names = []
    for path in sorted(glob.glob(os.path.join(tests_dir, "test_*.py"))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name.startswith("test_e2e_") or name == "test_bc64_smoke":
            names.append(name)
    return names


def modules_of_areas(areas, modules):
    """The modules (from the discovered list) that belong to any of the areas, in order."""
    wanted = set(areas)
    return [m for m in modules if area_of_module(m) in wanted]


def areas_with_modules(modules):
    """Sorted areas that own at least one of the modules."""
    return sorted({area_of_module(m) for m in modules} - {None})


def happy_ids(module):
    """Happy-path ids of one module (in HAPPY order)."""
    module = module[len("tests."):] if module.startswith("tests.") else module
    return [i for i in HAPPY if i == module or i.startswith(module + ".")]


def _normalise(path):
    path = path.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def areas_for_path(path):
    """Areas whose e2e tests the change of one repo-relative path triggers."""
    path = _normalise(path)
    for patterns, areas in RULES:
        if any(fnmatch.fnmatchcase(path, p) for p in patterns):
            return set(areas)
    directory, _, name = path.rpartition("/")
    if directory == "src/tests" and name.endswith(".py"):
        module = name[:-3]
        if module in MODULE_AREA:
            return {MODULE_AREA[module]}
        if not (module.startswith("test_e2e_") or module == "test_bc64_smoke"):
            return set()  # a unit test of some tool
    return set(ALL)  # unknown path (or an unmapped e2e module): conservative


def areas_for_paths(paths):
    """Union of areas_for_path over the paths."""
    result = set()
    for path in paths:
        result |= areas_for_path(path)
    return result


def _git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


def _is_commit(sha, cwd):
    if not sha or set(sha) == {"0"}:
        return False
    return _git(["rev-parse", "--verify", "--quiet", sha + "^{commit}"], cwd).returncode == 0


def changed_areas(base, head, cwd=REPO_ROOT, tests_dir=HERE):
    """Sorted areas (with e2e modules) to run for the diff base..head; all if unresolvable."""
    available = areas_with_modules(discover_modules(tests_dir))
    if not (_is_commit(base, cwd) and _is_commit(head, cwd)):
        return available
    diff = _git(["diff", "--name-only", base, head], cwd)
    if diff.returncode != 0:
        return available
    triggered = areas_for_paths(line for line in diff.stdout.splitlines() if line.strip())
    return [a for a in available if a in triggered]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    changed = sub.add_parser("changed", help="areas to run for a commit range (JSON array)")
    changed.add_argument("--base", default="")
    changed.add_argument("--head", default="HEAD")
    sub.add_parser("list", help="area -> modules (JSON object)")
    args = parser.parse_args(argv)
    if args.command == "changed":
        print(json.dumps(changed_areas(args.base, args.head), separators=(",", ":")))
    else:
        modules = discover_modules()
        print(json.dumps({a: modules_of_areas([a], modules) for a in AREAS}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
