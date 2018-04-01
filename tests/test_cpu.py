import unittest
from bc16 import bc16_cpu
from bc16 import bc16

class CpuTests(unittest.TestCase):
    def create_cpu(self, code):
        mem = bc16.MemBus(0xff)
        i = 0
        for b in code:
            mem.write_byte(i, b)
            i += 1
        return bc16_cpu.Bc8181(mem, None, False)
    def test_MOV_opcodes_internal(self):
        #given
        cpu = self.create_cpu([
            0x11, 0x69,  # MOV A,0x69 
            0x24, 0x10,  # MOV CI, A  
            0x25, 0x40,  # MOV DI, CI
            0x28, 0x50,  # MOV CS, DI
            0x29, 0x80,  # MOV DS, CS
            0xff         # KIL
        ])
        #when
        cpu.run()
        #then
        self.assertEqual(cpu.a.get(),  0x69)
        self.assertEqual(cpu.ci.get(), 0x69)
        self.assertEqual(cpu.di.get(), 0x69)
        self.assertEqual(cpu.cs.get(), 0x69)
        self.assertEqual(cpu.ds.get(), 0x69)
