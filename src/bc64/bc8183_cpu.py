# 8183 cpu version 1.2 (20240814)
def hi(b):
    return (b >> 4) & 0xf


def lo(b):
    return b & 0xf


class Register:
    def __init__(self, max_value, curr_value=0):
        self.val = curr_value if curr_value is not None else 0
        self.max_value = max_value

    def set(self, val):
        while(val < 0):
            val += self.max_value + 1
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


class Bc8183:
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

    CLC_EXT = 0xF
    CLC_EXT_AR = 0xA
    CLC_EXT_BIN = 0xB

    CLC_MUL = 0x2
    CLC_DIV = 0x3
    CLC_MOD = 0x4
    CLC_ADD16 = CLC_EXT_AR << 4 | CLC_ADD
    CLC_SUB16 = CLC_EXT_AR << 4 | CLC_SUB
    CLC_MUL16 = CLC_EXT_AR << 4 | CLC_MUL
    CLC_DIV16 = CLC_EXT_AR << 4 | CLC_DIV
    CLC_MOD16 = CLC_EXT_AR << 4 | CLC_MOD
    CLC_INC16 = CLC_EXT_AR << 4 | CLC_INC
    CLC_DEC16 = CLC_EXT_AR << 4 | CLC_DEC

    CLC_AND16 = CLC_EXT_BIN << 4 | CLC_AND
    CLC_OR16 = CLC_EXT_BIN << 4 | CLC_OR
    CLC_XOR16 = CLC_EXT_BIN << 4 | CLC_XOR
    CLC_SHL16 = CLC_EXT_BIN << 4 | CLC_SHL
    CLC_SHR16 = CLC_EXT_BIN << 4 | CLC_SHR
    CLC_NOT16 = CLC_EXT_BIN << 4 | CLC_NOT

    STACKFRAME_TYPE_PUSH = 0x10
    STACKFRAME_TYPE_CALL = 0xc0

    def __init__(self, membus, iobus, debug):
        self.membus = membus
        self.iobus = iobus
        self.create_registers(membus.size)
        self.create_instructions()
        self.create_arithmetic_and_logical_unit()
        self.kill = False
        self.debug = debug
        self.mesglog = []

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
        if subcode == Bc8183.CLC_OP_RNO:
            regno = hi(self.nextbyte)
            subcode = lo(self.nextbyte)
            arg2 = self.regs[regno].get()
            self.inc_pc(1)
        elif subcode == Bc8183.CLC_INC or \
                subcode == Bc8183.CLC_DEC or \
                subcode == Bc8183.CLC_NOT:
            pass
        elif subcode == Bc8183.CLC_EXT:
            subcode = hi(self.nextbyte)
            suboper = lo(self.nextbyte)
            self.inc_pc(1)
            regno = hi(self.nextbyte)
            self.inc_pc(1)
            arg2 = None
            regno2 = None
            opersubcode = (subcode << 4) | suboper
            singlearg = (opersubcode & Bc8183.CLC_INC16) == Bc8183.CLC_INC16 \
              or (opersubcode & Bc8183.CLC_DEC16) == Bc8183.CLC_DEC16 \
              or (opersubcode & Bc8183.CLC_NOT16) == Bc8183.CLC_NOT16
            if (not singlearg):
                if(regno == Bc8183.CS):            
                    regno2 = Bc8183.DS
                elif(regno == Bc8183.DS):
                    regno2 = Bc8183.CS
                elif(regno == Bc8183.A):
                    regno2 = Bc8183.CS
                else:
                    pass
                if suboper & Bc8183.CLC_OP_RNO == \
                    Bc8183.CLC_OP_RNO:
                    arg2 = self.alu_getval16(regno2)
                    suboper = suboper & 0x07
                    opersubcode = (subcode << 4) | suboper
                else:
                    b1 = self.nextbyte
                    self.inc_pc(1)
                    arg2 = (b1 << 8) | self.nextbyte
                    self.inc_pc(1)

            oper16 = self.alu16[opersubcode]
            oper16(regno, arg2, regno2)
            return
        else:
            # this is bug, there is conflict between CLC_OP_RNO and register with INC, DEC, ZER
            if subcode & Bc8183.CLC_OP_RNO == \
                    Bc8183.CLC_OP_RNO:
                regno = hi(self.nextbyte)
                subcode = subcode & (Bc8183.CLC_OP_RNO - 1)
                arg2 = self.regs[regno].get()
            else:
                arg2 = self.nextbyte
            self.inc_pc(1)
        oper = self.alu[subcode]
        oper(self.a.get(), arg2)

    def get_addr(self, regno):
        if(regno == Bc8183.CI or regno == Bc8183.CS):
            hi = self.cs.get()
            lo = self.ci.get()
        elif (regno == Bc8183.DI or regno == Bc8183.DS):
            hi = self.ds.get()
            lo = self.di.get()
        elif (regno == Bc8183.SI or regno == Bc8183.SS):
            hi = self.ss.get()
            lo = self.si.get()
        elif (regno == Bc8183.A or regno == Bc8183.F):
            hi = self.a.get()
            lo = self.f.get()
        else:
            return None
        addr = (hi << 8) | lo
        return addr

    def set_flags(self, regno, val=None):
        if regno == Bc8183.A:
            if val is None:
                val = self.a.get()
            self.f.set_flag(FlagsRegister.ZERO, int(val == 0))
            self.f.set_flag(FlagsRegister.NEGATIVE,
                            int(val & 0x80 == 0x80))
        if val is not None:
            self.f.set_flag(FlagsRegister.CARRY, int(val > 0xff))
            self.f.set_flag(FlagsRegister.OVERFLOW, int(val > 0xff or val < 0))

    def set_flags16(self, val):
        self.f.set_flag(FlagsRegister.ZERO, int(val == 0))
        self.f.set_flag(FlagsRegister.NEGATIVE, int(val & 0x8000 == 0x8000))
        self.f.set_flag(FlagsRegister.CARRY, int(val > 0xffff))
        self.f.set_flag(FlagsRegister.OVERFLOW, int(val > 0xffff or val < 0))

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
        addr = self.get_addr(Bc8183.SI)
        self.membus.write_byte(addr - 1, Bc8183.STACKFRAME_TYPE_PUSH)
        self.membus.write_byte(addr, val)
        addr -= 2
        self.si.set(addr & 0xff)
        self.ss.set((addr & 0xff00) >> 8)

    def _POP(self):
        addr = self.get_addr(Bc8183.SI)
        val = self.membus.read_byte(addr + 2)
        addr += 2
        self.si.set(addr & 0xff)
        self.ss.set((addr & 0xff00) >> 8)
        return val 

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
        curraddr = self.pc.get()
        
        opcode = lo(self.nextbyte)
        directmode = opcode & Bc8183.CLC_OP_RNO == Bc8183.CLC_OP_RNO
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
        stacktop = self.get_addr(Bc8183.SI)
        self.membus.write_byte(stacktop, curr & 0xff)
        self.membus.write_byte(stacktop - 1, (curr >> 8) & 0xff)
        self.membus.write_byte(stacktop - 2, Bc8183.STACKFRAME_TYPE_CALL)
        stacktop -= 3
        self.si.set(stacktop & 0xff)
        self.ss.set((stacktop & 0xff00) >> 8)

        relmode = opcode & 0x01 == 0x01
        if(relmode):
            if(addr & 0x8000 == 0x8000):
                addr = curraddr - (addr & 0x7fff)
            else:
                addr = curraddr + addr

        self.pc.set(addr)
        self.inc_pc(0)

    def op_RET(self):
        addr = self.get_addr(Bc8183.SI)
        frametype = self.membus.read_byte(addr + 1)
        addrhi = self.membus.read_byte(addr + 2)
        if(frametype == Bc8183.STACKFRAME_TYPE_CALL):
            addrlo = self.membus.read_byte(addr + 3)
            addr += 3
        else: #two frames type push
            addrlo = self.membus.read_byte(addr + 4)
            addr += 4
            
        self.si.set(addr & 0xff)
        self.ss.set((addr & 0xff00) >> 8)
    
        addr = (addrhi << 8) | addrlo
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
            regno1 = hi(self.nextbyte)
            port = lo(self.nextbyte)
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

    def op_EXT(self):
        opcode = lo(self.nextbyte)
        self.inc_pc(1)
        if(opcode == 0x01):
            testcode = hi(self.nextbyte)
            self.inc_pc(1)
            addr = self.nextbyte
            self.inc_pc(1)
            addr = (addr << 8) | self.nextbyte
        if(opcode == 0x02):
            testcode = hi(self.nextbyte)
            regno = lo(self.nextbyte)
            addr = self.get_addr(regno)

        regno = testcode & 0x3
        neg = opcode & 0x4 == 0x4
        test = self.f.get_flag(regno)
        if neg:
            test = not test
        
        if addr & 0x80 == 0x80:
            addr = - (addr & 0x7f)
        if(test):
            self.pc.set(self.pc.get() + addr - 1)
            self.inc_pc(0)
        else:
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
            0xe: self.op_EXT,
            0xf: self.op_KIL
        }

    def create_registers(self, memsize):
        memsize -= 1
        self.pc = Register(0xffff)
        self.f = FlagsRegister(0xff)
        self.a = Register(0xff)
        self.ss = Register(0xff, (memsize >> 8) & 0xff)
        self.si = Register(0xff, memsize & 0xff)
        self.ds = Register(0xff)
        self.di = Register(0xff)
        self.cs = Register(0xff)
        self.ci = Register(0xff)
        self.regs = {
            Bc8183.A: self.a,
            Bc8183.CI: self.ci,
            Bc8183.DI: self.di,
            Bc8183.CS: self.cs,
            Bc8183.DS: self.ds,
            Bc8183.F: self.f,
            Bc8183.SI: self.si,
            Bc8183.SS: self.ss,
            Bc8183.PC: self.pc
        }

    def alu_add(self, arg1, arg2):
        val = arg1 + arg2
        self.set_flags(Bc8183.A, val)
        self.a.set(val)

    def alu_sub(self, arg1, arg2):
        val = arg1 - arg2
        self.set_flags(Bc8183.A, val)
        self.a.set(val)

    def alu_and(self, arg1, arg2):
        val = arg1 & arg2
        self.set_flags(Bc8183.A, val)
        self.a.set(val)

    def alu_or(self, arg1, arg2):
        val = arg1 | arg2
        self.set_flags(Bc8183.A, val)
        self.a.set(val)

    def alu_xor(self, arg1, arg2):
        val = arg1 ^ arg2
        self.set_flags(Bc8183.A, val)
        self.a.set(val)

    def alu_shl(self, arg1, arg2):
        val = arg1 << arg2
        self.set_flags(Bc8183.A, val & 0x100)
        self.a.set(val)

    def alu_shr(self, arg1, arg2):
        val = arg1 >> arg2
        self.set_flags(Bc8183.A, -(val & 0x1))
        self.a.set(val)

    def alu_not(self, arg1, arg2):
        val = ~arg1
        self.set_flags(Bc8183.A, val)
        self.a.set(val)

    def alu_inc(self, arg1, arg2):
        val = arg1 + 1
        self.set_flags(Bc8183.A, val)
        self.a.set(val)

    def alu_dec(self, arg1, arg2):
        val = arg1 - 1
        self.set_flags(Bc8183.A, val)
        self.a.set(val)

    def alu_getval16(self,reg):
        return self.get_addr(reg)
    
    def alu_setval16(self, reg, val):
        if reg == Bc8183.CS:
            r2 = Bc8183.CI
        elif reg == Bc8183.DS:
            r2 = Bc8183.DI
        elif reg == Bc8183.A:
            r2 = Bc8183.F
        
        self.regs[reg].set((val & 0xff00) >> 8)
        self.regs[r2].set(val & 0xff)
        self.set_flags16(val)

    def alu_add16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val += arg
        self.alu_setval16(reg, val)

    def alu_sub16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val -= arg
        self.alu_setval16(reg, val)

    def alu_mul16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val *= arg
        self.alu_setval16(reg, val)

    def alu_div16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val //= arg
        self.alu_setval16(reg, val)

    def alu_mod16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val %= arg
        self.alu_setval16(reg, val)

    def alu_inc16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val += 1
        self.alu_setval16(reg, val)

    def alu_dec16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val -= 1
        self.alu_setval16(reg, val)

    def alu_and16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val &= arg
        self.alu_setval16(reg, val)

    def alu_or16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val |= arg
        self.alu_setval16(reg, val)

    def alu_xor16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val ^= arg
        self.alu_setval16(reg, val)

    def alu_shl16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val <<= arg
        self.alu_setval16(reg, val)

    def alu_shr16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val >>= arg
        self.alu_setval16(reg, val)
    
    def alu_not16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val = ~val
        self.alu_setval16(reg, val)

    def create_arithmetic_and_logical_unit(self):
        self.alu = {
            Bc8183.CLC_ADD: self.alu_add,
            Bc8183.CLC_SUB: self.alu_sub,
            Bc8183.CLC_AND: self.alu_and,
            Bc8183.CLC_OR: self.alu_or,
            Bc8183.CLC_XOR: self.alu_xor,
            Bc8183.CLC_SHL: self.alu_shl,
            Bc8183.CLC_SHR: self.alu_shr,
            Bc8183.CLC_NOT: self.alu_not,
            Bc8183.CLC_INC: self.alu_inc,
            Bc8183.CLC_DEC: self.alu_dec,
        }
        self.alu16 = {
            Bc8183.CLC_ADD16: self.alu_add16,
            Bc8183.CLC_SUB16: self.alu_sub16,
            Bc8183.CLC_MUL16: self.alu_mul16,
            Bc8183.CLC_DIV16: self.alu_div16,
            Bc8183.CLC_MOD16: self.alu_mod16,
            Bc8183.CLC_INC16: self.alu_inc16,
            Bc8183.CLC_DEC16: self.alu_dec16,

            Bc8183.CLC_AND16: self.alu_and16,
            Bc8183.CLC_OR16: self.alu_or16,
            Bc8183.CLC_XOR16: self.alu_xor16,
            Bc8183.CLC_SHL16: self.alu_shl16,
            Bc8183.CLC_SHR16: self.alu_shr16,
            Bc8183.CLC_NOT16: self.alu_not16
        }

    def set_reg(self, regno, val):
        reg = self.registers[regno]
        reg.set(val)

    def get_reg(self, regno):
        reg = self.registers[regno]
        return reg.get()
    
    def print_cpu_stack(self):
        print(":::CPU stack:::")
        self.print_debug(":::CPU stack:::")
        cpustackstart = self.get_addr(Bc8183.SS) + 1
        lastcpustackstart = cpustackstart
        if(cpustackstart >= self.membus.size):
            print(":::empty:::")
            self.print_debug(":::empty:::")
            return
        cpuframetype = self.membus.read_byte(cpustackstart)
        if cpuframetype == Bc8183.STACKFRAME_TYPE_CALL:
            cpuframe = (self.membus.read_byte(cpustackstart + 1) << 8) | self.membus.read_byte(cpustackstart + 2)
            cpustackstart += 3
            cpuframetypestr = 'CAL'
        else:
            cpuframe = self.membus.read_byte(cpustackstart + 1)
            cpustackstart += 2
            cpuframetypestr = 'VAL'
        
        while(cpuframetype > 0 and cpustackstart <= self.membus.size):
            msg = "{0} {1:04x}: {2:04x}".format(cpuframetypestr, lastcpustackstart, cpuframe)
            print(msg)
            self.print_debug(msg)
            lastcpustackstart = cpustackstart
            if cpuframetype == Bc8183.STACKFRAME_TYPE_CALL:
                cpuframe = (self.membus.read_byte(cpustackstart + 1) << 8) | self.membus.read_byte(cpustackstart + 2)
                cpustackstart += 3
                cpuframetypestr = 'CAL'
            else:
                cpuframe = self.membus.read_byte(cpustackstart + 1)
                cpustackstart += 2
                cpuframetypestr = 'VAL'
            
            cpuframetype = self.membus.read_byte(cpustackstart)

        print(":::end of stack:::")
        self.print_debug(":::end of stack:::")

    def run_next_opcode(self):
        opcode = hi(self.nextbyte)
        instruction = self.instructions[opcode]
        try:
            instruction()
        except Exception:
            mesg = 'exception at {0:04x}'.format(self.pc.get())
            print(mesg)
            self.print_debug(mesg)
            self.print_cpu_stack()
            raise
        self.print_context()

    def filelog(self, messages):
        with open('cpudebug.log', 'a') as fhandle:
            fhandle.writelines(messages)
            fhandle.close()

    def print_debug(self, mesg):
        if self.debug:
            self.mesglog.append(mesg+'\n')

    def flush_debug(self):
        if self.debug:
            self.filelog(self.mesglog)
            self.mesglog = []

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
        self.flush_debug()

    def run(self):
        try:
            self.inc_pc(0)
            self.print_context()
            while not self.kill:
                self.run_next_opcode()
            self.print_debug("====================== KILL")
        finally:
            self.flush_debug()

    def runAsync(self):
        self.inc_pc(0)
        self.print_context()
        while not self.kill and not self.env:
            self.run_next_opcode()
