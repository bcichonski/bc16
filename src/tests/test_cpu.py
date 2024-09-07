import unittest
from bc64 import bc8183_cpu
from bc64 import bc64_mem
from bc64 import bc64_env

debug = True

class CpuTests(unittest.TestCase):
    def create_cpu(self, code):
        environment = bc64_env.Environment()
        mem = bc64_mem.MemBus(environment, 0x0100)
        i = 0
        for b in code:
            mem.write_byte(i, b)
            i += 1
        mem.write_byte(0xff, 0xff) #ultimate KIL
        environment.debug = debug
        return bc8183_cpu.Bc8183(mem, None, debug)
    def test_MOV_opcodes_internal(self):
        if debug: print("test_MOV_opcodes_internal")
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
        if debug: print("test_MOV_opcodes_mem")
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
        if debug: print("test_CLC_opcodes")
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
        if debug: print("test_JMP_ZNZ_opcodes")
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

    def test_JMR_ZNZ_opcodes(self):
        if debug: print("test_JMR_ZNZ_opcodes")
        #given
        cpu = self.create_cpu([
            0x11, 0x00,  # 0x0000: MOV A, 0x00
            0x14, 0x03,  # 0x0002: MOV CI, 0x03
            0x18, 0x00,  # 0x0004: MOV CS, 0x00
            0x70, 0x03,  # 0x0006: JMR Z, +3
            0xff,        # 0x0008: KIL
            0x5c, 0x10,  # 0x0009: XOR A,A
            0x7e, 0x40,  # 0x000B: JMR NN, (CI)
            0xff,        # 0x000D: KIL
            0x5d,        # 0x000E: INC A
            0xff         # 0x000F: KIL
        ])
        #when
        cpu.run()
        #then
        self.assertEqual(cpu.a.get(),  0x01)

    def test_PUSH_POP_opcodes(self):
        if debug: print("test_PUSH_POP_opcodes")
        #given
        cpu = self.create_cpu([
            0x1C, 0xff,  # 0x0000: MOV SI, 0xfe ; stack at 00fe
            0x11, 0xf1,  # 0x0002: MOV A, 0xf1
            0x14, 0xa2,  # 0x0004: MOV CI, 0xa2
            0x81,        # 0x0006: PSH A
            0x84,        # 0x0007: PSH CI
            0x91,        # 0x0008: POP A
            0x94,        # 0x0009: POP CI
            0xff,        # 0x000A: KIL
        ])
        #when
        cpu.run()
        #then
        self.assertEqual(cpu.a.get(),  0xa2)
        self.assertEqual(cpu.ci.get(), 0xf1)

    def test_CAL_reg_RET_opcodes(self):
        if debug: print("test_CAL_RET_opcodes")
        #given
        cpu = self.create_cpu([
            0x1C, 0xff,  # 0x0000: MOV SI, 0xfe ; stack at 00fe
            0x14, 0x0A,  # 0x0002: MOV CI, 0x0A
            0x11, 0x00,  # 0x0004: MOV A, 0x00
            0xA0, 0x80,  # 0x0006: CAL #CSCI
            0x5d,        # 0x0008: INC A
            0xff,        # 0x0009: KIL
            0x5d,        # 0x000A: INC A
            0xB0,        # 0x000B: RET
            0xff,        # 0x000C: KIL
        ])
        #when
        cpu.run()
        #then
        self.assertEqual(cpu.a.get(),  0x02)

    def test_CAL_mem_RET_opcodes(self):
        if debug: print("test_CAL_mem_RET_opcodes")
        #given
        cpu = self.create_cpu([
            0x1C, 0xff,         # 0x0000: MOV SI, 0xfe ; stack at 00fe
            0x14, 0x0A,         # 0x0002: MOV CI, 0x0A
            0x11, 0x00,         # 0x0004: MOV A, 0x00
            0xA8, 0x00, 0x0B,   # 0x0006: CAL #000B
            0x5d,               # 0x0009: INC A
            0xff,               # 0x000A: KIL
            0x5d,               # 0x000B: INC A
            0xB0,               # 0x000C: RET
            0xff,               # 0x000D: KIL
        ])
        #when
        cpu.run()
        #then
        self.assertEqual(cpu.a.get(),  0x02)

    def test_CLC16_opcodes(self):
        if debug: print("test_CLC16_opcodes")
        #given
        cpu = self.create_cpu([
            0x18, 0x00,            # 0x0000: MOV CS, 0x00 ; stack at 00fe
            0x14, 0xff,            # 0x0002: MOV CI, 0xff
            0x5f, 0xad, 0x80,      # 0x0004: INC CSCI
            0x5f, 0xae, 0x80,      # 0x0007: DEC CSCI
            0x5f, 0xb7, 0x80,      # 0x000a: NOT CSCI
            0x15, 0x03,            # 0x000d: MOV DI, 0x03     
            0x5f, 0xa8, 0x80,      # 0x000f: ADD CSCI, DSDI
            0x5f, 0xab, 0x80,      # 0x0011: DIV CSCI, DSDI
            0x5f, 0xb4, 0x80, 0xab, 0xcd, # 0x0014: XOR CSCI, 0xabcd
            0xff,                  # 0x000f: KIL
        ])
        #when
        cpu.run()
        #then
        self.assertEqual(cpu.cs.get(),  0xfe)
        self.assertEqual(cpu.ci.get(),  0xcc)

    def test_CLR_opcodes(self):
        if debug: print("test_CLR_opcodes")
        #given
        cpu = self.create_cpu([
            0x18, 0x00,            # 0x0000: MOV CS, 0x00 ; stack at 00fe
            0x14, 0x06,            # 0x0002: MOV CI, 0x06
            0xA1, 0x84,            # 0x0004: CLR csci
            0xA9, 0x00, 0x06,      # 0x0006: CLR +0x0006
            0xff,                  # 0x0009: KIL
            0x5d,                  # 0x000a: INC a
            0xb0,                  # 0x000b: RET
            0xA9, 0x80, 0x02,      # 0x000c: CLR -0x0002
            0xb0,                  # 0x000f: RET
            0xff                   # 0x0010: KIL
        ])
        #when
        cpu.run()
        #then
        self.assertEqual(cpu.a.get(),  0x02)

    def test_CLC16_arithmetic_opcodes(self):
        if debug: print("test_CLC16_arithmetic_opcodes")
        #given
        cpu = self.create_cpu([
            0x18, 0x01,            # 0x0000: MOV CS, 0x01 ; stack at 00fe
            0x14, 0x01,            # 0x0002: MOV CI, 0x01
            0x19, 0x01,            # 0x0004: MOV DS, 0x01
            0x15, 0x01,            # 0x0006: MOV DI, 0x01
            0x5f, 0xa8, 0x80,      # 0x0008: ADD CSCI, DSDI
            0x5f, 0xa0, 0x80, 0x02, 0x02,# 0x000b: ADD CSCI, 0x0202
            0x5f, 0xa9, 0x80,      # 0x000f: SUB CSCI, DSDI
            0x5f, 0xa1, 0x80, 0x01, 0x01,# 0x0013: SUB CSCI, 0x0101
            0x5f, 0xaa, 0x80,      # 0x0016: MUL CSCI, DSDI
            0x5f, 0xa2, 0x80, 0x00, 0x02,# 0x0019: MUL CSCI, 0x0002
            0x5f, 0xab, 0x80,      # 0x001d: DIV CSCI, DSDI
            0x5f, 0xa3, 0x80, 0x00, 0x02,# 0x0020: DIV CSCI, 0x0002
            0x5f, 0xad, 0x80,      # 0x0024: INC CSCI
            0x5f, 0xae, 0x80,      # 0x0027: DEC CSCI
            0x5f, 0xa4, 0x80, 0x00, 0x02,# 0x002a: MOD CSCI, 0x0002
            0xff                   # 0x0010: KIL
        ])
        #when
        cpu.run()
        #then
        self.assertEqual(cpu.cs.get(),  0x00)
        self.assertEqual(cpu.ci.get(),  0x01)
