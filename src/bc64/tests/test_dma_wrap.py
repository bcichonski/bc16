"""Floppy DMA addresses wrap modulo 0x10000 (plan #7, D5)."""
import os
import shutil
import tempfile
import unittest

from bc64 import bc64_env
from bc64 import bc64_io
from bc64 import bc64_mem

FDD = bc64_io.FloppyDriveV1


class Env(bc64_env.Environment):
    def __init__(self, answers):
        super().__init__(False)
        self.answers = list(answers)

    def get_string(self, prompt):
        return self.answers.pop(0)


class DmaWrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bc64dma")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = Env([os.path.join(self.tmp, "diska.bdd")])
        self.mem = bc64_mem.MemBus(env, 0x10000)
        self.fdd = FDD(env, self.mem)
        self.addCleanup(self.close)

    def close(self):
        for h in (self.fdd.fileA_handle, self.fdd.fileB_handle):
            if h is not None and not h.closed:
                h.close()

    def send(self, *data):
        for b in data:
            self.fdd.write_byte(b)

    def dma(self, addr):
        self.send(FDD.CMD_CFG, addr >> 8, addr & 0xff)

    def test_read_sector_crossing_0xffff_wraps_to_zero(self):
        sector = bytes((i + 1) & 0xff for i in range(FDD.SECTOR_SIZE))
        with open(os.path.join(self.tmp, "diska.bdd"), "wb") as f:
            f.write(sector + bytes(FDD.TRACKS * FDD.SECTORS * FDD.SECTOR_SIZE - len(sector)))
        self.dma(0xffc0)
        self.send(FDD.CMD_READSECT, 0, 0)
        first = 0x10000 - 0xffc0
        for i in range(FDD.SECTOR_SIZE):
            self.assertEqual(self.mem.read_byte((0xffc0 + i) & 0xffff), sector[i], i)
        self.assertEqual(self.mem.read_byte(0xffff), sector[first - 1])
        self.assertEqual(self.mem.read_byte(0x0000), sector[first])

    def test_write_sector_crossing_0xffff_reads_tail_from_zero(self):
        self.dma(0xffc0)
        data = bytes((i * 3 + 5) & 0xff for i in range(FDD.SECTOR_SIZE))
        for i, b in enumerate(data):
            self.mem.write_byte((0xffc0 + i) & 0xffff, b)
        self.send(FDD.CMD_WRITESECT, 0, 1)
        with open(os.path.join(self.tmp, "diska.bdd"), "rb") as f:
            f.seek(FDD.SECTOR_SIZE)
            self.assertEqual(f.read(FDD.SECTOR_SIZE), data)


if __name__ == "__main__":
    unittest.main()
