"""The manifest-built system disc (src/disc.bddmanifest): structure of os.bdd/smoke.bdd and a session on it."""
import os
import unittest

import e2e_harness as h
import ftool_mkdisc as mk

MANIFEST = os.path.join(h.SRC, "disc.bddmanifest")
LIMIT = 50000000
SECTOR = h.SECTOR_SIZE
CAT_NAME = b"DISC    .CAT"


def _catalog_rows(image):
    """All used catalog entries as (number, track, sector, length, attribs, name+ext bytes)."""
    rows = []
    base = h.CAT_FIRST_SECTOR * SECTOR
    for number in range(248):
        entry = image[base + number * h.ENTRY_SIZE:base + (number + 1) * h.ENTRY_SIZE]
        if entry[3] > 0:
            rows.append((entry[0], entry[1], entry[2], entry[3], entry[4], bytes(entry[5:16])))
    return rows


def check_disc_structure(image, planned):
    """Assert the disc image carries every planned entry (and only those, plus DISC.CAT)."""
    rows = _catalog_rows(image)
    by_name = {row[5]: row for row in rows}
    expected = {}
    for entry in planned:
        expected[(entry.name.ljust(8) + entry.ext.ljust(3)).encode("ascii")] = entry
    assert set(by_name) == set(expected), "catalog names %r != manifest %r" % (sorted(by_name), sorted(expected))
    assert [r[5] for r in rows][:1] == [b"BOOTSECTBIN"], "boot file must be the first entry"
    ends = []
    for name, entry in expected.items():
        number, track, sector, length, attribs, _ = by_name[name]
        where = name.decode("ascii")
        assert (number, track, sector) == (entry.number, entry.track, entry.sector), \
            "%s: entry/start %r != %r" % (where, (number, track, sector), (entry.number, entry.track, entry.sector))
        assert attribs == entry.attribs, "%s: attributes %02X != %02X" % (where, attribs, entry.attribs)
        assert length == entry.length, "%s: length %d != %d" % (where, length, entry.length)
        if entry.data is not None:
            start = (track * h.SECTORS_PER_TRACK + sector) * SECTOR
            padded = entry.data.ljust(length * SECTOR, b"\0")
            assert image[start:start + length * SECTOR] == padded, "%s: bytes on disc differ from source" % where
    for row in rows:
        ends.append(row[1] * h.SECTORS_PER_TRACK + row[2] + row[3])
    # catalog order = entry number order; BOOTSECT, DISC.CAT and BDOS.SYS sit at the fixed start
    assert [r[0] for r in rows] == sorted(r[0] for r in rows)
    assert ends == sorted(ends) and len(set(ends)) == len(ends), "end positions do not rise: %r" % ends


class DiscStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.planned = mk.plan_disc(MANIFEST)

    def test_manifest_has_system_file_of_160_sectors(self):
        system = self.planned[2]
        self.assertEqual("BDOS", system.name)
        self.assertEqual(160, system.length)

    def test_os_bdd_matches_manifest(self):
        check_disc_structure(h.read_bytes(h.OS_DISK), self.planned)

    def test_smoke_bdd_matches_manifest(self):
        check_disc_structure(h.read_bytes(h.SMOKE_DISK), self.planned)

    def test_check_detects_a_corrupt_length(self):
        image = bytearray(h.read_bytes(h.OS_DISK))
        image[h.CAT_FIRST_SECTOR * SECTOR + 3 * h.ENTRY_SIZE + 3] += 1  # LS.PRG length
        with self.assertRaises(AssertionError):
            check_disc_structure(bytes(image), self.planned)

    def test_check_detects_a_corrupt_source_byte(self):
        image = bytearray(h.read_bytes(h.SMOKE_DISK))
        row = [r for r in _catalog_rows(image) if r[5] == b"LS      PRG"][0]
        image[(row[1] * h.SECTORS_PER_TRACK + row[2]) * SECTOR] ^= 0xFF
        with self.assertRaises(AssertionError):
            check_disc_structure(bytes(image), self.planned)


class DiscSessionTests(unittest.TestCase):
    def run_scenario(self, scenario):
        return h.run_session(scenario, h.golden_path(scenario, "in"), disks={"a": h.SMOKE_DISK},
                             max_instructions=LIMIT)

    def test_ls_all_lists_every_file(self):
        out = self.run_scenario("disc_ls_all")
        markers = [b"A>ls -a", b"listing files of drive A:", b"bye!"]
        planned = mk.plan_disc(MANIFEST)
        for entry in sorted(planned, key=lambda e: e.number):
            markers.append((entry.name.ljust(8) + "." + entry.ext.ljust(3)).encode("ascii"))
        markers.append(CAT_NAME)
        h.check_golden(h.golden_path("disc_ls_all"), out, markers=markers, scenario="disc_ls_all")

    def test_every_utility_prints_usage_and_returns_to_shell(self):
        out = self.run_scenario("disc_help")
        markers = [b"A>ls -h", b"A>cp -h", b"A>format -h", b"A>rm -h", b"A>cha -h", b"A>cat -h", b"A>exit", b"bye!"]
        h.check_golden(h.golden_path("disc_help"), out, markers=markers, scenario="disc_help")


if __name__ == "__main__":
    unittest.main()
