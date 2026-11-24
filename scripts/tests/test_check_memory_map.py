"""Tests of scripts/check_memory_map.py. The real build happens in a temp copy of the sources
(bcOS and boot with the assembler, bdos and every program with bc.py then the assembler, all with
--map, in parallel subprocesses); the repo tree is never written to. The failing cases use
hand-written maps.
Run from scripts/: python3 -m unittest discover -s tests -t . -p "test_*.py"
"""

import concurrent.futures
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)
import check_memory_map  # noqa: E402
import code_size  # noqa: E402

ROOT = check_memory_map.ROOT
ASM = os.path.join(ROOT, "src", "bc81asmc", "bc81asmc.py")
BC = os.path.join(ROOT, "src", "bc", "bc.py")


def map_text(org, end, symbols):
    lines = ["; bc81asmc map x.basm", "; org 0x%04x end 0x%04x" % (org, end)]
    lines += ["0x%04x label %s" % (value, name) for name, value in sorted(symbols.items(), key=lambda s: s[1])]
    return "\n".join(lines) + "\n"


GOOD = {
    "bcos": (0x0000, 0x0c00, {"os_metacall": 0x0008, "os_metatab": 0x000c, "user_mem": 0x0d00}),
    "boot": (0x0e00, 0x0e50, {"bd_end": 0x0e50}),
    "bdos": (0x0f00, 0x5000, {"sys_codeend": 0x5000}),
    "prog": (0x6000, 0x6100, {"main": 0x6000}),
}


def run_check(root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = check_memory_map.main(["--root", root])
    return code, out.getvalue()


def run(command, cwd):
    completed = subprocess.run(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise RuntimeError("%s failed: %s %s" % (command, completed.stdout, completed.stderr))


def build_program(tmp_bdos, name):
    source = os.path.join(tmp_bdos, name + ".b")
    run([sys.executable, BC, source], os.path.join(ROOT, "src", "bc"))
    run([sys.executable, ASM, "--map", os.path.join(tmp_bdos, name + ".map"),
         os.path.join(tmp_bdos, name + ".basm")], tmp_bdos)


class SyntheticMaps(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="test_check_memory_map_")
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, "src", "bc81asmc", "bcOS"))
        os.makedirs(os.path.join(self.root, "src", "bdos"))
        for key in GOOD:
            self.put(key)

    def path(self, key):
        return {"bcos": os.path.join("src", "bc81asmc", "bcOS", "bcos.map"),
                "boot": os.path.join("src", "bdos", "boot.map"),
                "bdos": os.path.join("src", "bdos", "bdos.map"),
                "prog": os.path.join("src", "bdos", "ls.map")}[key]

    def put(self, key, org=None, end=None, **symbols):
        good_org, good_end, good_symbols = GOOD[key]
        merged = dict(good_symbols)
        merged.update(symbols)
        text = map_text(good_org if org is None else org, good_end if end is None else end, merged)
        with open(os.path.join(self.root, self.path(key)), "w", encoding="utf8", newline="") as handle:
            handle.write(text)

    def assert_fails(self, *needles):
        code, out = run_check(self.root)
        self.assertEqual(code, 1, out)
        for needle in needles:
            self.assertIn(needle, out)

    def test_good_maps_pass(self):
        code, out = run_check(self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("OK", out)

    def test_os_metacall_moved(self):
        self.put("bcos", os_metacall=0x0009)
        self.assert_fails("bcos.map", "os_metacall")

    def test_os_metatab_moved(self):
        self.put("bcos", os_metatab=0x000d)
        self.assert_fails("bcos.map", "os_metatab")

    def test_bcos_org_moved(self):
        self.put("bcos", org=0x0001)
        self.assert_fails("bcos.map", "org")

    def test_bcos_end_past_limit(self):
        self.put("bcos", end=0x0d81)
        self.assert_fails("bcos.map", "end")

    def test_user_mem_past_limit(self):
        self.put("bcos", user_mem=0x0d81)
        self.assert_fails("bcos.map", "user_mem")

    def test_boot_end_past_limit(self):
        self.put("boot", bd_end=0x0e81)
        self.assert_fails("boot.map", "bd_end")

    def test_boot_org_moved(self):
        self.put("boot", org=0x0e01)
        self.assert_fails("boot.map", "org")

    def test_sys_codeend_at_limit(self):
        self.put("bdos", sys_codeend=0x5d00)
        self.assert_fails("bdos.map", "sys_codeend")

    def test_bdos_org_moved(self):
        self.put("bdos", org=0x0f01)
        self.assert_fails("bdos.map", "org")

    def test_program_not_at_6000(self):
        self.put("prog", org=0x6001)
        self.assert_fails("ls.map", "org")

    def test_missing_bdos_map(self):
        os.remove(os.path.join(self.root, self.path("bdos")))
        self.assert_fails("bdos.map", "missing")

    def test_missing_bcos_and_boot_maps(self):
        os.remove(os.path.join(self.root, self.path("bcos")))
        os.remove(os.path.join(self.root, self.path("boot")))
        self.assert_fails("bcos.map", "boot.map")

    def test_no_program_map(self):
        os.remove(os.path.join(self.root, self.path("prog")))
        self.assert_fails("program map")

    def test_missing_symbol_is_a_violation(self):
        text = map_text(0x0000, 0x0c00, {"os_metatab": 0x000c, "user_mem": 0x0d00})
        with open(os.path.join(self.root, self.path("bcos")), "w", encoding="utf8") as handle:
            handle.write(text)
        self.assert_fails("os_metacall")

    def test_one_line_per_violation(self):
        self.put("bcos", os_metacall=0x0009, os_metatab=0x000d)
        code, out = run_check(self.root)
        self.assertEqual(code, 1)
        self.assertEqual(sum("bcos.map" in line for line in out.splitlines()), 2)

    def test_malformed_map_is_reported(self):
        with open(os.path.join(self.root, self.path("boot")), "w", encoding="utf8") as handle:
            handle.write("garbage\n")
        self.assert_fails("boot.map", "unreadable")


class FreshBuild(unittest.TestCase):
    def test_fresh_build_satisfies_the_memory_map(self):
        tmp = tempfile.mkdtemp(prefix="test_check_memory_map_build_")
        self.addCleanup(shutil.rmtree, tmp, True)
        bcos_dir = os.path.join(tmp, "src", "bc81asmc", "bcOS")
        bdos_dir = os.path.join(tmp, "src", "bdos")
        os.makedirs(bcos_dir)
        os.makedirs(bdos_dir)
        src_bdos = os.path.join(ROOT, "src", "bdos")
        for name in os.listdir(src_bdos):
            if name.endswith(".b") or name == "boot.basm":
                shutil.copyfile(os.path.join(src_bdos, name), os.path.join(bdos_dir, name))
        shutil.copyfile(os.path.join(ROOT, "src", "bc81asmc", "bcOS", "bcos.basm"),
                        os.path.join(bcos_dir, "bcos.basm"))
        programs = sorted(key[len("bdos/"):] for key in code_size.discover(ROOT) if key.startswith("bdos/"))
        self.assertIn("bdos", programs)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            jobs = [pool.submit(run, [sys.executable, ASM, "--map", os.path.join(bcos_dir, "bcos.map"),
                                      os.path.join(bcos_dir, "bcos.basm")], bcos_dir),
                    pool.submit(run, [sys.executable, ASM, "--map", os.path.join(bdos_dir, "boot.map"),
                                      os.path.join(bdos_dir, "boot.basm")], bdos_dir)]
            jobs += [pool.submit(build_program, bdos_dir, name) for name in programs]
            for job in jobs:
                job.result()

        code, out = run_check(tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("OK", out)


if __name__ == "__main__":
    unittest.main()
