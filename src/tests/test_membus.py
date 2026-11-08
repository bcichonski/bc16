import importlib.util
import os
import unittest
from bc64 import bc64_env
from bc64 import bc64_mem
from bc64 import bc8183_cpu

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_bc64_module():
    # "bc64" resolves to the package, so the top-level bc64.py is loaded by path.
    spec = importlib.util.spec_from_file_location("bc64_toplevel", os.path.join(SRC_DIR, "bc64.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MemBusTests(unittest.TestCase):
    SIZE = 0x100

    def create_mem(self):
        return bc64_mem.MemBus(bc64_env.Environment(False), MemBusTests.SIZE)

    def test_new_memory_is_zeroed(self):
        mem = self.create_mem()
        self.assertEqual(mem.read_byte(0x00), 0)
        self.assertEqual(mem.read_byte(MemBusTests.SIZE - 1), 0)

    def test_first_address_round_trip(self):
        mem = self.create_mem()
        mem.write_byte(0x0000, 0xa5)
        self.assertEqual(mem.read_byte(0x0000), 0xa5)

    def test_last_address_round_trip(self):
        mem = self.create_mem()
        mem.write_byte(MemBusTests.SIZE - 1, 0x5a)
        self.assertEqual(mem.read_byte(MemBusTests.SIZE - 1), 0x5a)

    def test_neighbours_are_untouched(self):
        mem = self.create_mem()
        mem.write_byte(0x10, 0xff)
        self.assertEqual(mem.read_byte(0x0f), 0)
        self.assertEqual(mem.read_byte(0x11), 0)

    def test_full_byte_range_is_stored(self):
        mem = self.create_mem()
        for value in (0x00, 0x01, 0x7f, 0x80, 0xff):
            mem.write_byte(0x20, value)
            self.assertEqual(mem.read_byte(0x20), value)

    def test_read_past_end_raises_index_error(self):
        # pinned: no bounds handling, the host exception reaches the caller
        mem = self.create_mem()
        with self.assertRaises(IndexError):
            mem.read_byte(MemBusTests.SIZE)

    def test_write_past_end_raises_index_error(self):
        # pinned
        mem = self.create_mem()
        with self.assertRaises(IndexError):
            mem.write_byte(MemBusTests.SIZE, 0x01)

    def test_write_value_over_a_byte_raises_value_error(self):
        # pinned: MemBus does not mask values, the bytearray rejects them
        mem = self.create_mem()
        with self.assertRaises(ValueError):
            mem.write_byte(0x00, 0x100)

    def test_negative_address_wraps_from_the_end(self):
        # pinned (D7 finding): a negative address is not rejected, it indexes from the end
        mem = self.create_mem()
        mem.write_byte(-1, 0x77)
        self.assertEqual(mem.read_byte(MemBusTests.SIZE - 1), 0x77)

    def test_16_bit_big_endian_value_at_the_top(self):
        mem = self.create_mem()
        top = MemBusTests.SIZE - 2
        mem.write_byte(top, 0xbeef >> 8)
        mem.write_byte(top + 1, 0xbeef & 0xff)
        self.assertEqual(mem.read_byte(top), 0xbe)
        self.assertEqual(mem.read_byte(top + 1), 0xef)
        self.assertEqual(mem.read_byte(top) * 256 + mem.read_byte(top + 1), 0xbeef)

    def test_cpu_reads_byte_at_last_address(self):
        mem = self.create_mem()
        mem.write_byte(MemBusTests.SIZE - 1, 0x42)
        code = [
            0x14, 0xff,  # MOV CI, 0xff
            0x18, 0x00,  # MOV CS, 0x00
            0x31, 0x40,  # MOV A, (CS:CI)
            0xff,        # KIL
        ]
        for i, b in enumerate(code):
            mem.write_byte(i, b)
        cpu = bc8183_cpu.Bc8183(mem, None, False)
        cpu.run()
        self.assertEqual(cpu.a.get(), 0x42)


class EmulatorMemorySizeTests(unittest.TestCase):
    def create_computer(self):
        module = load_bc64_module()
        return module, module.Bc64(bc64_env.Environment(False), False)

    @unittest.expectedFailure
    def test_emulator_memory_is_64_kb(self):
        # #7: the emulator memory is TOPMEM = 0xffff bytes, so 0xffff is not addressable
        module, computer = self.create_computer()
        self.assertEqual(computer.mem.size, 0x10000)
        computer.mem.write_byte(0xffff, 0x12)
        self.assertEqual(computer.mem.read_byte(0xffff), 0x12)

    def test_emulator_memory_is_65535_bytes_today(self):
        # pinned today's behaviour, owned by #7
        module, computer = self.create_computer()
        self.assertEqual(module.TOPMEM, 0xffff)
        self.assertEqual(computer.mem.size, 0xffff)
        computer.mem.write_byte(0xfffe, 0x12)
        self.assertEqual(computer.mem.read_byte(0xfffe), 0x12)
        with self.assertRaises(IndexError):
            computer.mem.read_byte(0xffff)


if __name__ == "__main__":
    unittest.main()
