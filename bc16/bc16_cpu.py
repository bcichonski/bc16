def hi(b):
    return (b >> 4) & 0xf


def lo(b):
    return b & 0xf


class Register:
    def __init__(self, max_value, curr_value = 0):
        self.val = curr_value if curr_value is not None else 0
        self.max_value = max_value

    def set(self, val):
        self.val = val & self.max_value

    def get(self):
        return self.val

    def inc(self, val):
        self.set(self.val + val)


class FlagsRegister(Register):
    ZERO = 0x0
    CARRY = 0x1
    NEGATIVE = 0x2
    OVERFLOW = 0x3
    B0 = 0x0
    B1 = 0x1
    B2 = 0x2
    B3 = 0x3
    B4 = 0x4
    B5 = 0x5
    B6 = 0x6
    B7 = 0x7

    def __init__(self, max_value):
        self.zero = Register(0x1, 0x1)
        self.carry = Register(0x1)
        self.negative = Register(0x1)
        self.overflow = Register(0x1)
        self.b4 = Register(0x1)
        self.b5 = Register(0x1)
        self.b6 = Register(0x1)
        self.b7 = Register(0x1)
        self.flags = {
            FlagsRegister.ZERO: self.zero,
            FlagsRegister.CARRY: self.carry,
            FlagsRegister.NEGATIVE: self.negative,
            FlagsRegister.OVERFLOW: self.overflow,
            FlagsRegister.B4: self.b4,
            FlagsRegister.B5: self.b5,
            FlagsRegister.B6: self.b6,
            FlagsRegister.B7: self.b7
        }
        super().__init__(max_value, self._getflagsval())

    def _getflagsval(self):
        val = 0
        pos = 0
        for flag, reg in self.flags.items():
            val |= reg.get() << pos
            pos += 1
        return val

    def set_flag(self, flag, val):
        self.flags[flag].set(int(val))
        val = self._getflagsval()
        self.set(val)

    def get_flag(self, flag):
        return bool(self.flags[flag].get())


class Bc8181:
    A = 0x1
    CI = 0x4
    DI = 0x5
    CS = 0x8
    DS = 0x9
    F = 0xB
    SI = 0xC
    SS = 0xD
    PC = 0xF

    CLC_ADD = 0x0
    CLC_SUB = 0x1
    CLC_AND = 0x2
    CLC_OR = 0x3
    CLC_XOR = 0x4
    CLC_SHL = 0x5
    CLC_SHR = 0x6
    CLC_NOT = 0x7
    CLC_OP_RNO = 0x8
    CLC_INC = 0xD
    CLC_DEC = 0xE
    CLC_ZER = 0xF

    def __init__(self, membus, iobus, debug):
        self.membus = membus
        self.iobus = iobus
        self.create_registers(membus.size)
        self.create_instructions()
        self.create_arithmetic_and_logical_unit()
        self.kill = False
        self.debug = debug

    def inc_pc(self, val):
        self.pc.inc(val)
        self.nextbyte = self.membus.read_byte(self.pc.get())

    def op_NOP(self):
        self.inc_pc(1)

    def op_KIL(self):
        self.kill = True

    def op_MOV_imm(self):
        regno = lo(self.nextbyte)
        self.inc_pc(1)
        self.regs[regno].set(self.nextbyte)
        self.set_flags(regno)
        self.inc_pc(1)

    def op_MOV_reg(self):
        regno1 = lo(self.nextbyte)
        self.inc_pc(1)
        regno2 = hi(self.nextbyte)
        self.regs[regno1].set(self.regs[regno2].get())
        self.set_flags(regno1)
        self.inc_pc(1)

    def op_MOV_reg_mem(self):
        regno1 = lo(self.nextbyte)
        self.inc_pc(1)
        regno2 = hi(self.nextbyte)
        self.inc_pc(1)
        addr = self.get_addr(regno2)
        if addr is not None:
            val = self.membus.read_byte(addr)
            self.regs[regno1].set(val)
            self.set_flags(regno1)
        else:
            self.op_KIL()

    def op_MOV_mem_reg(self):
        regno1 = lo(self.nextbyte)
        self.inc_pc(1)
        regno2 = hi(self.nextbyte)
        self.inc_pc(1)
        addr = self.get_addr(regno1)
        if addr is not None:
            val = self.regs[regno2].get()
            self.membus.write_byte(addr, val)
        else:
            self.op_KIL()

    def op_CLC(self):
        subcode = lo(self.nextbyte)
        self.inc_pc(1)
        arg2 = None
        if subcode == Bc8181.CLC_INC or \
                subcode == Bc8181.CLC_DEC or \
                subcode == Bc8181.CLC_NOT or \
                subcode == Bc8181.CLC_ZER:
            pass
        else:
            if subcode & Bc8181.CLC_OP_RNO == \
                    Bc8181.CLC_OP_RNO:
                regno = hi(self.nextbyte)
                subcode = subcode & (Bc8181.CLC_OP_RNO - 1)
                arg2 = self.regs[regno].get()
            else:
                arg2 = self.nextbyte
            self.inc_pc(1)
        oper = self.alu[subcode]
        oper(self.a.get(), arg2)

    def get_addr(self, regno):
        if(regno == Bc8181.CI or regno == Bc8181.CS):
            hi = self.cs.get()
            lo = self.ci.get()
        elif (regno == Bc8181.DI or regno == Bc8181.DS):
            hi = self.ds.get()
            lo = self.di.get()
        elif (regno == Bc8181.SI or regno == Bc8181.SS):
            hi = self.ss.get()
            lo = self.si.get()
        else:
            return None
        addr = (hi << 8) | lo
        return addr

    def set_flags(self, regno, val=None):
        if regno == Bc8181.A:
            self.f.set_flag(FlagsRegister.ZERO, int(self.a.get() == 0))
            self.f.set_flag(FlagsRegister.NEGATIVE,
                            int(self.a.get() & 0x80 == 0x80))
        if val is not None:
            self.f.set_flag(FlagsRegister.CARRY, int(val > 0xff or val < 0))

    def op_JMP(self):
        opcode = lo(self.nextbyte)
        regno = opcode & 0x3
        neg = opcode & 0x4 == 0x4
        test = self.f.get_flag(regno)
        if neg:
            test = not test
        shortmode = opcode & 0x8 == 0x8
        self.inc_pc(1)
        if shortmode:
            addr = self.cs.get() << 8 | self.nextbyte
        else:
            addr = self.get_addr(lo(self.nextbyte))
        if(test):
            self.pc.set(addr)
            self.inc_pc(0)
        else:
            self.inc_pc(1)

    def op_JMR(self):
        opcode = lo(self.nextbyte)
        regno = opcode & 0x3
        neg = opcode & 0x4 == 0x4
        test = self.f.get_flag(regno)
        if neg:
            test = not test
        regmode = opcode & 0x8 == 0x8
        self.inc_pc(1)
        if not regmode:
            addr = self.nextbyte
        else:
            jmrreg = hi(self.nextbyte)
            addr = self.regs[jmrreg].get()
        if addr & 0x80 == 0x80:
            addr = - (addr & 0x7f)
        if(test):
            self.pc.set(self.pc.get() + addr - 1)
            self.inc_pc(0)
        else:
            self.inc_pc(1)

    def _PSH(self, val):
        addr = self.get_addr(Bc8181.SI)
        self.membus.write_byte(addr, val)
        self.si.set(self.si.get()-1)

    def _POP(self):
        self.si.set(self.si.get()+1)
        addr = self.get_addr(Bc8181.SI)
        return self.membus.read_byte(addr)

    def op_PSH(self):
        regno = lo(self.nextbyte)
        val = self.regs[regno].get()
        self._PSH(val)
        self.inc_pc(1)

    def op_POP(self):
        regno = lo(self.nextbyte)
        val = self._POP()
        self.regs[regno].set(val)
        self.inc_pc(1)

    def op_CAL(self):
        opcode = lo(self.nextbyte)
        directmode = opcode & Bc8181.CLC_OP_RNO == Bc8181.CLC_OP_RNO
        self.inc_pc(1)
        if(directmode):
            addrhi = self.nextbyte
            self.inc_pc(1)
            addr = (addrhi << 8) | self.nextbyte
        else:
            regno = hi(self.nextbyte)
            addr = self.get_addr(regno)
        self.inc_pc(1)
        curr = self.pc.get()
        self._PSH((curr >> 8) & 0xff)
        self._PSH(curr & 0xff)
        self.pc.set(addr)
        self.inc_pc(0)

    def op_RET(self):
        addrlo = self._POP()
        addrhi = self._POP()
        addr = addrhi << 8 | addrlo
        self.pc.set(addr)
        self.inc_pc(0)

    def op_IN(self):
        opcode = lo(self.nextbyte)
        self.inc_pc(1)
        if opcode & 0x8 == 0x8:
            regno1 = hi(self.nextbyte)
            regno2 = lo(self.nextbyte)
            port = self.regs[regno2].get()
        else:
            regno1 = opcode & 0x7
            port = hi(self.nextbyte)
        inbyte = self.iobus.read_byte(port)
        self.regs[regno1].set(inbyte)
        self.inc_pc(1)

    def op_OUT(self):
        opcode = lo(self.nextbyte)
        self.inc_pc(1)
        if opcode & 0x8 == 0x8:
            regno1 = hi(self.nextbyte)
            regno2 = lo(self.nextbyte)
            port = self.regs[regno1].get()
            val = self.regs[regno2].get()
            self.set_flags(regno2, val)
        else:
            regno1 = opcode & 0x7
            port = self.regs[regno1].get()
            val = self.nextbyte
        self.iobus.write_byte(port, val)
        self.inc_pc(1)

    def create_instructions(self):
        self.instructions = {
            0x0: self.op_NOP,
            0x1: self.op_MOV_imm,
            0x2: self.op_MOV_reg,
            0x3: self.op_MOV_reg_mem,
            0x4: self.op_MOV_mem_reg,
            0x5: self.op_CLC,
            0x6: self.op_JMP,
            0x7: self.op_JMR,
            0x8: self.op_PSH,
            0x9: self.op_POP,
            0xa: self.op_CAL,
            0xb: self.op_RET,
            0xc: self.op_IN,
            0xd: self.op_OUT,
            0xe: self.op_NOP,
            0xf: self.op_KIL
        }

    def create_registers(self, memsize):
        memsize -= 1
        self.pc = Register(0xffff)
        self.f = FlagsRegister(0xf)
        self.a = Register(0xff)
        self.ss = Register(0xff, (memsize >> 8) & 0xff)
        self.si = Register(0xff, memsize & 0xff)
        self.ds = Register(0xff)
        self.di = Register(0xff)
        self.cs = Register(0xff)
        self.ci = Register(0xff)
        self.regs = {
            Bc8181.A: self.a,
            Bc8181.CI: self.ci,
            Bc8181.DI: self.di,
            Bc8181.CS: self.cs,
            Bc8181.DS: self.ds,
            Bc8181.F: self.f,
            Bc8181.SI: self.si,
            Bc8181.SS: self.ss,
            Bc8181.PC: self.pc
        }

    def alu_add(self, arg1, arg2):
        val = arg1 + arg2
        self.set_flags(Bc8181.A, val)
        self.a.set(val)
        # self.f.set_flag(FlagsRegister.OVERFLOW, ) TODO

    def alu_sub(self, arg1, arg2):
        val = arg1 - arg2
        self.set_flags(Bc8181.A, val)
        self.a.set(val)
        # self.f.set_flag(FlagsRegister.OVERFLOW, ) TODO

    def alu_and(self, arg1, arg2):
        val = arg1 & arg2
        self.set_flags(Bc8181.A, val)
        self.a.set(val)

    def alu_or(self, arg1, arg2):
        val = arg1 | arg2
        self.set_flags(Bc8181.A, val)
        self.a.set(val)

    def alu_xor(self, arg1, arg2):
        val = arg1 ^ arg2
        self.set_flags(Bc8181.A, val)
        self.a.set(val)

    def alu_shl(self, arg1, arg2):
        val = arg1 << arg2
        self.set_flags(Bc8181.A, val & 0x100)
        self.a.set(val)

    def alu_shr(self, arg1, arg2):
        val = arg1 >> arg2
        self.set_flags(Bc8181.A, -(val & 0x1))
        self.a.set(val)

    def alu_not(self, arg1, arg2):
        val = ~arg1
        self.set_flags(Bc8181.A, val)
        self.a.set(val)

    def alu_inc(self, arg1, arg2):
        val = arg1 + 1
        self.set_flags(Bc8181.A, val)
        self.a.set(val)

    def alu_dec(self, arg1, arg2):
        val = arg1 - 1
        self.set_flags(Bc8181.A, val)
        self.a.set(val)

    def alu_zer(self, arg1, arg2):
        self.set_flags(Bc8181.A, 0)
        self.a.set(0)

    def create_arithmetic_and_logical_unit(self):
        self.alu = {
            Bc8181.CLC_ADD: self.alu_add,
            Bc8181.CLC_SUB: self.alu_sub,
            Bc8181.CLC_AND: self.alu_and,
            Bc8181.CLC_OR: self.alu_or,
            Bc8181.CLC_XOR: self.alu_xor,
            Bc8181.CLC_SHL: self.alu_shl,
            Bc8181.CLC_SHR: self.alu_shr,
            Bc8181.CLC_NOT: self.alu_not,
            Bc8181.CLC_INC: self.alu_inc,
            Bc8181.CLC_DEC: self.alu_dec,
            Bc8181.CLC_ZER: self.alu_zer
        }

    def set_reg(self, regno, val):
        reg = self.registers[regno]
        reg.set(val)

    def get_reg(self, regno):
        reg = self.registers[regno]
        return reg.get()

    def run_next_opcode(self):
        opcode = hi(self.nextbyte)
        instruction = self.instructions[opcode]
        instruction()
        self.print_context()

    def print_debug(self, mesg):
        if self.debug:
            print(mesg)

    def print_context(self):
        self.print_debug('')
        self.print_debug("PC: 0x{0:04x} next: 0x{1:02x}".format(
            self.pc.get(), self.nextbyte))
        self.print_debug("SS: 0x{0:02x} SI: 0x{1:02x}".format(
            self.ss.get(), self.si.get()))
        self.print_debug("A:  0x{0:02x} F:  0b{1:08b}".format(
            self.a.get(), self.f.get()))
        self.print_debug("CS: 0x{0:02x} CI: 0x{1:02x}".format(
            self.cs.get(), self.ci.get()))
        self.print_debug("DS: 0x{0:02x} DI: 0x{1:02x}".format(
            self.ds.get(), self.di.get()))

    def run(self):
        self.inc_pc(0)
        self.print_context()
        while not self.kill:
            self.run_next_opcode()
        self.print_debug("====================== KILL")
