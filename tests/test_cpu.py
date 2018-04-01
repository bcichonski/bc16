import unittest
from bc16 import bc16_cpu
from bc16 import bc16

class CpuTests(unittest.TestCase):
    def create_cpu(self, code):
        mem = bc16.MemBus(0x100)
        i = 0
        for b in code:
            mem.write_byte(i, b)
            i += 1
        mem.write_byte(0xff, 0xff) #ultimate KIL
        return bc16_cpu.Bc8181(mem, None, True)
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
    def test_MOV_opcodes_mem(self):
        #given
        cpu = self.create_cpu([
            0x11, 0x69,  # MOV A, 0x69 
            0x14, 0xab,  # MOV CI, 0xab   
            0x18, 0x00,  # MOV CS, 0x00
            0x44, 0x10,  # MOV (CS:CI), A
            0x11, 0x00,  # MOV A, 0x00
            0x31, 0x40,  # MOV A, (CS:CI)
            0xff         # KIL
        ])
        #when
        cpu.run()
        #then
        self.assertEqual(cpu.a.get(),  0x69)
