import unittest
import bc8183_isa
import importlib.util
import os
from bc64 import bc8183_cpu


class _Bus:
    size = 0x10000

    def read_byte(self, addr):
        return 0

    def write_byte(self, addr, val):
        pass


class CpuIsaTests(unittest.TestCase):
    def setUp(self):
        self.cpu = bc8183_cpu.Bc8183(_Bus(), None, False)

    def test_decode_table_is_the_isa_opcode_table(self):
        self.assertEqual(set(self.cpu.instructions), set(bc8183_isa.OPCODE_NAMES))
        self.assertEqual(len(self.cpu.instructions), 16)
        for nibble, name in bc8183_isa.OPCODE_NAMES.items():
            self.assertEqual(self.cpu.instructions[nibble].__name__, 'op_' + name)

    def test_alu8_dispatch_keys_are_the_isa_ops(self):
        self.assertEqual(set(self.cpu.alu), set(bc8183_isa.ALU8_OPS.values()))

    def test_alu16_dispatch_keys_are_the_isa_codes(self):
        self.assertEqual(set(self.cpu.alu16), set(bc8183_isa.ALU16_CODES.values()))

    def test_alu16_handlers_match_names(self):
        for name, code in bc8183_isa.ALU16_CODES.items():
            self.assertEqual(self.cpu.alu16[code].__name__, 'alu_' + name + '16')

    def test_compat_attributes_hold_isa_values(self):
        self.assertEqual(bc8183_cpu.Bc8183.STACKFRAME_TYPE_PUSH, bc8183_isa.STACKFRAME_PUSH)
        self.assertEqual(bc8183_cpu.Bc8183.STACKFRAME_TYPE_CALL, bc8183_isa.STACKFRAME_CALL)
        self.assertEqual(bc8183_cpu.FlagsRegister.OVERFLOW, bc8183_isa.FLAG_OVERFLOW)

    def test_write_top_kil_writes_the_isa_byte(self):
        class Mem:
            def __init__(self):
                self.writes = []

            def write_byte(self, addr, val):
                self.writes.append((addr, val))

        path = os.path.join(os.path.dirname(__file__), '..', '..', 'bc64.py')
        spec = importlib.util.spec_from_file_location('bc64_entry', path)
        entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(entry)
        computer = entry.Bc64.__new__(entry.Bc64)
        computer.mem = Mem()
        computer.write_top_kil()
        self.assertEqual(computer.mem.writes, [(0xffff, bc8183_isa.TOP_OF_MEMORY_KIL)])


if __name__ == '__main__':
    unittest.main()
