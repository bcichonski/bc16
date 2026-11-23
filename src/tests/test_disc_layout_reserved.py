"""Static cross-check of the reserved disc range: bdioh.b, both manifests, boot.basm and ftool agree (#41)."""
import os
import re
import unittest

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SECTORS_PER_TRACK = 16


def read(*parts):
    with open(os.path.join(SRC, *parts), encoding="latin-1") as f:
        return f.read()


def bdioh_define(name):
    m = re.search(r"^#define\s+%s\s+(0x[0-9a-fA-F]+|\d+)\s*$" % name, read("bdos", "bdioh.b"), re.M)
    assert m, name
    return int(m.group(1), 0)


def manifest_slots(name):
    """role -> (linear start, max) from the `role=... at=T/S max=N` options."""
    slots = {}
    for line in read(name).splitlines():
        line = line.split(";")[0].split("#")[0]
        role = re.search(r"role=(\w+)", line)
        at = re.search(r"at=(\d+)/(\d+)", line)
        mx = re.search(r"max=(\d+)", line)
        if role and at and mx:
            slots[role.group(1)] = (int(at.group(1)) * SECTORS_PER_TRACK + int(at.group(2)), int(mx.group(1)))
    return slots


class ReservedRangeTests(unittest.TestCase):
    def boot_last_sector(self):
        m = re.search(r"mov\s+a,\s*(0x[0-9a-fA-F]+)", read("bdos", "boot.basm").split("bd_dend")[1])
        self.assertIsNotNone(m)
        return int(m.group(1), 0)

    def test_first_allocatable_is_end_of_system_slot_in_both_manifests(self):
        first = bdioh_define("BDIO_DISC_ALLOCFIRSTSECT")
        for name in ("disc.bddmanifest", "utils.bddmanifest"):
            with self.subTest(name):
                start, mx = manifest_slots(name)["system"]
                self.assertEqual(start + mx, first)

    def test_first_allocatable_is_boot_last_loaded_sector_plus_one(self):
        self.assertEqual(self.boot_last_sector() + 1, bdioh_define("BDIO_DISC_ALLOCFIRSTSECT"))
        self.assertEqual(bdioh_define("BDIO_DISC_BDOSLASTSECT"), self.boot_last_sector())

    def test_bdioh_layout_is_consistent(self):
        first = bdioh_define("BDIO_DISC_ALLOCFIRSTSECT")
        self.assertEqual(bdioh_define("BDIO_DISC_BDOSLASTSECT") + 1, first)
        self.assertEqual(bdioh_define("BDIO_DISC_SECTORS") - first, bdioh_define("BDIO_DISC_ALLOCSECTORS"))

    def test_boot_catalog_and_system_slots_lie_in_the_reserved_range(self):
        first = bdioh_define("BDIO_DISC_ALLOCFIRSTSECT")
        for name in ("disc.bddmanifest", "utils.bddmanifest"):
            slots = manifest_slots(name)
            for role in ("boot", "catalog", "system"):
                with self.subTest(name=name, role=role):
                    start, mx = slots[role]
                    self.assertLessEqual(start + mx, first)

    def test_ftool_constant_equals_bdioh(self):
        import ftool_mkdisc
        import ftool_text
        first = bdioh_define("BDIO_DISC_ALLOCFIRSTSECT")
        self.assertEqual(ftool_mkdisc.ALLOC_FIRST_SECTOR, first)
        self.assertIs(ftool_text.mk, ftool_mkdisc)


if __name__ == "__main__":
    unittest.main()
