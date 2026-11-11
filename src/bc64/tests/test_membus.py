import importlib.util
import os
import unittest
from bc64 import bc64_env
from bc64 import bc64_mem
from bc64 import bc8183_cpu

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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

    def test_emulator_memory_is_64_kb(self):
        # #7: the emulator memory is the full 64 KB, so 0xffff is addressable
        module, computer = self.create_computer()
        self.assertEqual(computer.mem.size, 0x10000)
        computer.mem.write_byte(0xffff, 0x12)
        self.assertEqual(computer.mem.read_byte(0xffff), 0x12)

    def test_memory_constants(self):
        module, computer = self.create_computer()
        self.assertEqual(module.MEMORY_SIZE, 0x10000)
        self.assertEqual(module.TOP_ADDRESS, 0xffff)
        self.assertEqual(module.STACK_TOP, 0xfffe)
        self.assertFalse(hasattr(module, "TOPMEM"))

    def test_round_trip_at_both_ends_and_below_top(self):
        module, computer = self.create_computer()
        for addr, val in ((0x0000, 0x34), (0xfffe, 0x56), (0xffff, 0x78)):
            computer.mem.write_byte(addr, val)
            self.assertEqual(computer.mem.read_byte(addr), val)
        with self.assertRaises(IndexError):
            computer.mem.read_byte(0x10000)

    def test_stack_starts_at_0xfffe_and_first_push_leaves_0xffff_alone(self):
        module, computer = self.create_computer()
        cpu = computer.cpu
        self.assertEqual(cpu.ss.get() << 8 | cpu.si.get(), 0xfffe)
        computer.write_top_kil()
        cpu._PSH(0x5a)
        self.assertEqual(computer.mem.read_byte(0xfffe), 0x5a)
        self.assertEqual(computer.mem.read_byte(0xfffd), bc8183_cpu.Bc8183.STACKFRAME_TYPE_PUSH)
        self.assertEqual(computer.mem.read_byte(0xffff), 0xff)
        self.assertEqual(cpu.ss.get() << 8 | cpu.si.get(), 0xfffc)

    def test_startup_step_writes_kil_at_0xffff(self):
        module, computer = self.create_computer()
        self.assertEqual(computer.mem.read_byte(0xffff), 0)
        computer.write_top_kil()
        self.assertEqual(computer.mem.read_byte(0xffff), 0xff)
        self.assertEqual(computer.mem.read_byte(0xfffe), 0)

    def test_jump_to_0xffff_halts_there(self):
        module, computer = self.create_computer()
        computer.write_top_kil()
        # MOV CS,0xff ; JMP short if flag 0 set (it is after reset) -> 0xffff
        for i, b in enumerate((0x18, 0xff, 0x68, 0xff)):
            computer.mem.write_byte(i, b)
        self.assertTrue(computer.run(1000))
        self.assertEqual(computer.cpu.pc.get(), 0xffff)

    def test_running_sequentially_into_0xffff_halts_there(self):
        module, computer = self.create_computer()
        computer.write_top_kil()
        # all-zero memory is NOPs from 0x0000 up to the KIL at 0xffff
        self.assertTrue(computer.run(0x20000))
        self.assertEqual(computer.cpu.pc.get(), 0xffff)

    def test_bare_full_size_cpu_defaults_stack_to_size_minus_one(self):
        mem = bc64_mem.MemBus(bc64_env.Environment(False), 0x10000)
        cpu = bc8183_cpu.Bc8183(mem, None, False)
        self.assertEqual(cpu.ss.get() << 8 | cpu.si.get(), 0xffff)

    def test_pc_wraps_from_0xffff_to_0x0000(self):
        mem = bc64_mem.MemBus(bc64_env.Environment(False), 0x10000)
        cpu = bc8183_cpu.Bc8183(mem, None, False)
        mem.write_byte(0xffff, 0x00)  # NOP, 1 byte, not KIL
        mem.write_byte(0x0000, 0xf0)
        cpu.pc.set(0xffff)
        cpu.inc_pc(0)
        cpu.run_next_opcode()
        self.assertEqual(cpu.pc.get(), 0x0000)


if __name__ == "__main__":
    unittest.main()
