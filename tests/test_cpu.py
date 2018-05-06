import unittest
from bc16 import bc16_cpu
from bc16 import bc16_mem
from bc16 import bc16_env

debug = False

class CpuTests(unittest.TestCase):
    def create_cpu(self, code):
        environment = bc16_env.Environment()
        mem = bc16_mem.MemBus(environment, 0x100)
        i = 0
        for b in code:
            mem.write_byte(i, b)
            i += 1
        mem.write_byte(0xff, 0xff) #ultimate KIL
        environment.debug = debug
        return bc16_cpu.Bc8181(mem, None, debug)
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
    def test_CLC_opcodes(self):
        #given
        cpu = self.create_cpu([
            0x11, 0x69,  # MOV A, 0x69
            0x5c, 0x10,  # XOR A, A
            0x5d,        # INC A
            0x5e,        # DEC A
            0x57,        # NOT A
            0x52, 0x00,  # AND A, 0x00
            0x14, 0x69,  # MOV CI, 0x69
            0x59, 0x40,  # SUB A, CI
            0x58, 0x40,  # ADD A, CI
            0x53, 0xab,  # OR A, 0xab
            0xff         # KIL
        ])
        #when
        cpu.run()
        #then
        self.assertEqual(cpu.a.get(),  0xab)
    def test_JMP_ZNZ_opcodes(self):
        #given
        cpu = self.create_cpu([
            0x11, 0x69,  # 0x0000: MOV A, 0x69
            0x18, 0x00,  # 0x0002: MOV CS, 0x00
            0x14, 0x09,  # 0x0004: MOV CI, 0x09
            0x64, 0x84,  # 0x0006: JMP NZ, 0x0009
            0xff,        # 0x0008: KIL
            0x5c, 0x10,  # 0x0009: XOR A,A
            0x68, 0x0e,  # 0x000B: JMP Z, 0x000E
            0xff,        # 0x000D: KIL
            0x5d,        # 0x000E: INC A
            0xff         # 0x000F: KIL
        ])
        #when
        cpu.run()
        #then
        self.assertEqual(cpu.a.get(),  0x01)
