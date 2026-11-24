import sys
import bc8183_isa
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
    ZERO = bc8183_isa.FLAG_ZERO
    CARRY = bc8183_isa.FLAG_CARRY
    NEGATIVE = bc8183_isa.FLAG_NEGATIVE
    OVERFLOW = bc8183_isa.FLAG_OVERFLOW
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
    A = bc8183_isa.REG_A
    CI = bc8183_isa.REG_CI
    DI = bc8183_isa.REG_DI
    CS = bc8183_isa.REG_CS
    DS = bc8183_isa.REG_DS
    F = bc8183_isa.REG_F
    SI = bc8183_isa.REG_SI
    SS = bc8183_isa.REG_SS
    PC = bc8183_isa.REG_PC

    CLC_ADD = bc8183_isa.ALU_ADD
    CLC_SUB = bc8183_isa.ALU_SUB
    CLC_AND = bc8183_isa.ALU_AND
    CLC_OR = bc8183_isa.ALU_OR
    CLC_XOR = bc8183_isa.ALU_XOR
    CLC_SHL = bc8183_isa.ALU_SHL
    CLC_SHR = bc8183_isa.ALU_SHR
    CLC_NOT = bc8183_isa.ALU_NOT
    CLC_OP_RNO = bc8183_isa.CLC_REGISTER_FORM
    CLC_INC = bc8183_isa.ALU_INC
    CLC_DEC = bc8183_isa.ALU_DEC

    CLC_EXT = bc8183_isa.CLC_EXT
    CLC_EXT_AR = bc8183_isa.ALU16_GROUP_ARITH
    CLC_EXT_BIN = bc8183_isa.ALU16_GROUP_BINARY

    CLC_MUL = bc8183_isa.ALU16_MUL
    CLC_DIV = bc8183_isa.ALU16_DIV
    CLC_MOD = bc8183_isa.ALU16_MOD
    CLC_ADD16 = bc8183_isa.ALU16_CODES['add']
    CLC_SUB16 = bc8183_isa.ALU16_CODES['sub']
    CLC_MUL16 = bc8183_isa.ALU16_CODES['mul']
    CLC_DIV16 = bc8183_isa.ALU16_CODES['div']
    CLC_MOD16 = bc8183_isa.ALU16_CODES['mod']
    CLC_INC16 = bc8183_isa.ALU16_CODES['inc']
    CLC_DEC16 = bc8183_isa.ALU16_CODES['dec']

    CLC_AND16 = bc8183_isa.ALU16_CODES['and']
    CLC_OR16 = bc8183_isa.ALU16_CODES['or']
    CLC_XOR16 = bc8183_isa.ALU16_CODES['xor']
    CLC_SHL16 = bc8183_isa.ALU16_CODES['shl']
    CLC_SHR16 = bc8183_isa.ALU16_CODES['shr']
    CLC_NOT16 = bc8183_isa.ALU16_CODES['not']

    STACKFRAME_TYPE_PUSH = bc8183_isa.STACKFRAME_PUSH
    STACKFRAME_TYPE_CALL = bc8183_isa.STACKFRAME_CALL

    def __init__(self, membus, iobus, debug, stack_top=None):
        self.membus = membus
        self.iobus = iobus
        self.create_registers(membus.size - 1 if stack_top is None else stack_top)
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
            self.print_debug(f"====================== MEM ACCESS TROUBLE at {self.pc.get():04x}")
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
            self.print_debug(f"====================== MEM ACCESS TROUBLE at {self.pc.get():04x}")
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

            singlearg = ((opersubcode & Bc8183.CLC_INC16) == Bc8183.CLC_INC16 and (subcode == Bc8183.CLC_EXT_AR)) \
              or ((opersubcode & Bc8183.CLC_DEC16) == Bc8183.CLC_DEC16 and (subcode == Bc8183.CLC_EXT_AR)) \
              or ((opersubcode & Bc8183.CLC_NOT16) == Bc8183.CLC_NOT16 and (subcode == Bc8183.CLC_EXT_BIN))
            
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
                    suboper = suboper & (Bc8183.CLC_OP_RNO - 1)
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
            # The long register form 58 ro (the == CLC_OP_RNO branch above) covers every
            # op, including shl/shr. This branch is the short register form 5(o|8) r0,
            # a CPU-only alias that exists only for sub/and/or/xor (o=1..4), because
            # o|8 for shl/shr/not would be 0xD/0xE/0xF = inc/dec/EXT.
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
        # Z/N describe the stored (8-bit) value; C/O use the raw val (#54).
        if regno == Bc8183.A:
            if val is None:
                zn = self.a.get()
            else:
                zn = val & 0xff
            self.f.set_flag(FlagsRegister.ZERO, int(zn == 0))
            self.f.set_flag(FlagsRegister.NEGATIVE,
                            int(zn & 0x80 == 0x80))
        if val is not None:
            self.f.set_flag(FlagsRegister.CARRY, int(val > 0xff))
            self.f.set_flag(FlagsRegister.OVERFLOW, int(val > 0xff or val < 0))

    def set_flags16(self, val, carry=None, overflow=None):
        # carry/overflow None: legacy C/O of shl16/shr16, kept as is (#55).
        stored = val & 0xffff
        self.f.set_flag(FlagsRegister.ZERO, int(stored == 0))
        self.f.set_flag(FlagsRegister.NEGATIVE, int(stored & 0x8000 == 0x8000))
        if carry is None:
            carry = int(val > 0xffff)
            overflow = int(val > 0xffff or val < 0)
        self.f.set_flag(FlagsRegister.CARRY, carry)
        self.f.set_flag(FlagsRegister.OVERFLOW, overflow)

    def set_flags_alu(self, val, carry, overflow):
        # 8-bit arithmetic/logic into A (#54): Z/N from the stored value,
        # C = unsigned carry/borrow, O = signed overflow, both given.
        stored = val & 0xff
        self.f.set_flag(FlagsRegister.ZERO, int(stored == 0))
        self.f.set_flag(FlagsRegister.NEGATIVE, int(stored & 0x80 == 0x80))
        self.f.set_flag(FlagsRegister.CARRY, carry)
        self.f.set_flag(FlagsRegister.OVERFLOW, overflow)

    @staticmethod
    def add_flags(a, b, r, mask):
        # C, O of the sum r = a + b for operands within mask (0xff / 0xffff)
        sign = (mask + 1) >> 1
        carry = int(r > mask)
        overflow = int((a & sign) == (b & sign) and (r & sign) != (a & sign))
        return carry, overflow

    @staticmethod
    def sub_flags(a, b, r, mask):
        # C (borrow), O of the difference r = a - b
        sign = (mask + 1) >> 1
        carry = int(r < 0)
        overflow = int((a & sign) != (b & sign) and (r & sign) != (a & sign))
        return carry, overflow

    def op_JMP(self):
        opcode = lo(self.nextbyte)
        regno = opcode & bc8183_isa.COND_FLAG_MASK
        neg = opcode & bc8183_isa.COND_NEGATE == bc8183_isa.COND_NEGATE
        test = self.f.get_flag(regno)
        if neg:
            test = not test
        shortmode = opcode & bc8183_isa.JMP_SHORT == bc8183_isa.JMP_SHORT
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
        regno = opcode & bc8183_isa.COND_FLAG_MASK
        neg = opcode & bc8183_isa.COND_NEGATE == bc8183_isa.COND_NEGATE
        test = self.f.get_flag(regno)
        if neg:
            test = not test
        regmode = opcode & bc8183_isa.JMR_REGISTER == bc8183_isa.JMR_REGISTER
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

    def stack_fault(self, name, addrs):
        """Stack bounds rule: every stack byte must lie inside memory (0 <= addr < size).

        If not, stop like KIL (PC, registers, SS:SI and memory untouched) and report
        on stderr and in the debug trace. Returns True when the instruction must not run.
        """
        size = self.membus.size
        if all(0 <= a < size for a in addrs):
            return False
        if any(a >= size for a in addrs):
            reason = 'empty stack (read past the top of memory)'
        else:
            reason = 'stack overflow (write below 0x0000)'
        mesg = '{0} at {1:04x}: {2}, CPU stopped'.format(name, self.pc.get(), reason)
        print(mesg, file=sys.stderr)
        self.print_debug(mesg)
        self.kill = True
        return True

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
        addr = self.get_addr(Bc8183.SI)
        if self.stack_fault('PSH', [addr - 1, addr]):
            return
        regno = lo(self.nextbyte)
        val = self.regs[regno].get()
        self._PSH(val)
        self.inc_pc(1)

    def op_POP(self):
        if self.stack_fault('POP', [self.get_addr(Bc8183.SI) + 2]):
            return
        regno = lo(self.nextbyte)
        val = self._POP()
        self.regs[regno].set(val)
        self.inc_pc(1)

    def dumpmem(self, addr, expected, offset = 64):
        if(addr == expected):
            i = -offset
            while(i<128):
                a = self.membus.read_byte(addr + i + 0)
                b = self.membus.read_byte(addr + i + 1)
                c = self.membus.read_byte(addr + i + 2)
                d = self.membus.read_byte(addr + i + 3)
                aa = chr(a)
                bb = chr(b)
                cc = chr(c)
                dd = chr(d)
                print('{8:04x}: {0:02x} {1:02x} {2:02x} {3:02x} {4}{5}{6}{7}'.format(a, b, c, d, aa, bb, cc, dd, addr + i))
                i += 4

    def op_CAL(self):
        addr = self.get_addr(Bc8183.SI)
        if self.stack_fault('CAL', [addr - 2, addr - 1, addr]):
            return
        curraddr = self.pc.get()
        
        opcode = lo(self.nextbyte)
        directmode = opcode & bc8183_isa.CAL_DIRECT == bc8183_isa.CAL_DIRECT
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

        relmode = opcode & bc8183_isa.CAL_RELATIVE == bc8183_isa.CAL_RELATIVE
        if(relmode):
            if(addr & 0x8000 == 0x8000):
                addr = curraddr - (addr & 0x7fff)
            else:
                addr = curraddr + addr
            addr = addr + 2

        #print(f'{self.pc.get():04x} call to {addr:04x}')
        self.pc.set(addr)
        #self.dumpmem(addr, 0x0008, 4)
        self.inc_pc(0)

    def op_RET(self):
        addr = self.get_addr(Bc8183.SI)
        if self.stack_fault('RET', [addr + 1]):
            return
        frametype = self.membus.read_byte(addr + 1)
        if frametype == Bc8183.STACKFRAME_TYPE_CALL:
            needed = [addr + 2, addr + 3]
        else:
            needed = [addr + 2, addr + 3, addr + 4]
        if self.stack_fault('RET', needed):
            return
        if frametype == Bc8183.STACKFRAME_TYPE_CALL:
            addrhi = self.membus.read_byte(addr + 2)
            addrlo = self.membus.read_byte(addr + 3)
            addr += 3
        elif frametype == Bc8183.STACKFRAME_TYPE_PUSH:
            if self.membus.read_byte(addr + 3) != Bc8183.STACKFRAME_TYPE_PUSH:
                self.ret_stop('single push frame on top of the stack')
                return
            addrhi = self.membus.read_byte(addr + 2)  # two frames type push
            addrlo = self.membus.read_byte(addr + 4)
            addr += 4
        else:
            self.ret_stop('no call or push frame on top of the stack')
            return

        self.si.set(addr & 0xff)
        self.ss.set((addr & 0xff00) >> 8)

        addr = (addrhi << 8) | addrlo
        self.pc.set(addr)
        self.inc_pc(0)

    def ret_stop(self, reason):
        """RET found no frame to return through: stop like KIL (PC, registers, SS:SI, memory untouched)."""
        mesg = 'RET at {0:04x}: {1}, CPU stopped'.format(self.pc.get(), reason)
        print(mesg, file=sys.stderr)
        self.print_debug(mesg)
        self.kill = True

    def op_IN(self):
        opcode = lo(self.nextbyte)
        self.inc_pc(1)
        if opcode & bc8183_isa.IN_REGISTER == bc8183_isa.IN_REGISTER:
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
        if opcode & bc8183_isa.OUT_REGISTER == bc8183_isa.OUT_REGISTER:
            regno1 = hi(self.nextbyte)
            regno2 = lo(self.nextbyte)
            port = self.regs[regno1].get()
            val = self.regs[regno2].get()
            self.set_flags(regno2, val)
        else:
            regno1 = opcode & bc8183_isa.OUT_PORT_MASK
            port = self.regs[regno1].get()
            val = self.nextbyte
        self.iobus.write_byte(port, val)
        self.inc_pc(1)

    def op_EXT(self):
        opcode = lo(self.nextbyte)
        if opcode not in bc8183_isa.EXT_SUBOPS:
            mesg = 'EXT at {0:04x}: unknown sub-opcode 0x{1:x}, CPU stopped'.format(self.pc.get(), opcode)
            print(mesg, file=sys.stderr)
            self.print_debug(mesg)
            self.kill = True
            return
        self.inc_pc(1)
        if(opcode == bc8183_isa.EXT_JRX_ADDR):
            testcode = hi(self.nextbyte)
            self.inc_pc(1)
            addr = self.nextbyte
            self.inc_pc(1)
            addr = (addr << 8) | self.nextbyte
            self.inc_pc(1)
        if(opcode == bc8183_isa.EXT_JRX_REG):
            testcode = hi(self.nextbyte)
            regno = lo(self.nextbyte)
            addr = self.get_addr(regno)
            self.inc_pc(1)

        regno = testcode & bc8183_isa.COND_FLAG_MASK
        neg = testcode & bc8183_isa.COND_NEGATE == bc8183_isa.COND_NEGATE
        test = self.f.get_flag(regno)
        if neg:
            test = not test

        if (addr & 0x8000) == 0x8000:
            addr = - (addr & 0x7fff)

        if(test):
            #x = addr
            addr = self.pc.get() + addr - 1
            #print(f'{self.pc.get():04x} {x:04x} JUMP to {addr:04x}')
            self.pc.set(addr)
            self.inc_pc(0)

    def create_instructions(self):
        self.instructions = {
            nibble: getattr(self, 'op_' + name)
            for nibble, name in bc8183_isa.OPCODE_NAMES.items()
        }

    def create_registers(self, memsize):
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
        self.set_flags_alu(val, *self.add_flags(arg1, arg2, val, 0xff))
        self.a.set(val)

    def alu_sub(self, arg1, arg2):
        val = arg1 - arg2
        self.set_flags_alu(val, *self.sub_flags(arg1, arg2, val, 0xff))
        self.a.set(val)

    def alu_and(self, arg1, arg2):
        val = arg1 & arg2
        self.set_flags_alu(val, 0, 0)
        self.a.set(val)

    def alu_or(self, arg1, arg2):
        val = arg1 | arg2
        self.set_flags_alu(val, 0, 0)
        self.a.set(val)

    def alu_xor(self, arg1, arg2):
        val = arg1 ^ arg2
        self.set_flags_alu(val, 0, 0)
        self.a.set(val)

    @staticmethod
    def shift_left_flags(val, count, width):
        # (C, O) of a left shift (#55): C is the last bit shifted out (bit
        # width-count of val; 0 for a shift by 0 or by more than the width),
        # O is set when any 1 bit was shifted out.
        if count == 0:
            return 0, 0
        if count > width:
            return 0, int(val != 0)
        out = val >> (width - count)
        return out & 1, int(out != 0)

    @staticmethod
    def shift_right_carry(val, count, width):
        # C of a right shift (#55): bit count-1 of val, 0 for a shift by 0
        # or by more than the width. (O is always 0.)
        if count == 0 or count > width:
            return 0
        return (val >> (count - 1)) & 1

    def alu_shl(self, arg1, arg2):
        carry, over = self.shift_left_flags(arg1, arg2, 8)
        val = (arg1 << min(arg2, 8)) & 0xff
        self.set_flags(Bc8183.A, val)
        self.f.set_flag(FlagsRegister.CARRY, carry)
        self.f.set_flag(FlagsRegister.OVERFLOW, over)
        self.a.set(val)

    def alu_shr(self, arg1, arg2):
        carry = self.shift_right_carry(arg1, arg2, 8)
        val = arg1 >> min(arg2, 8)
        self.set_flags(Bc8183.A, val)
        self.f.set_flag(FlagsRegister.CARRY, carry)
        self.f.set_flag(FlagsRegister.OVERFLOW, 0)
        self.a.set(val)

    def alu_not(self, arg1, arg2):
        val = ~arg1
        self.set_flags_alu(val, 0, 0)
        self.a.set(val)

    def alu_inc(self, arg1, arg2):
        val = arg1 + 1
        self.set_flags_alu(val, *self.add_flags(arg1, 1, val, 0xff))
        self.a.set(val)

    def alu_dec(self, arg1, arg2):
        val = arg1 - 1
        self.set_flags_alu(val, *self.sub_flags(arg1, 1, val, 0xff))
        self.a.set(val)

    def alu_getval16(self,reg):
        return self.get_addr(reg)
    
    def alu_setval16(self, reg, val, carry=None, overflow=None):
        if reg == Bc8183.CS:
            r2 = Bc8183.CI
        elif reg == Bc8183.DS:
            r2 = Bc8183.DI
        elif reg == Bc8183.A:
            r2 = Bc8183.F
        
        self.regs[reg].set((val & 0xff00) >> 8)
        self.regs[r2].set(val & 0xff)
        self.set_flags16(val, carry, overflow)

    def alu_add16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        a = val
        val += arg
        self.alu_setval16(reg, val, *self.add_flags(a, arg, val, 0xffff))

    def alu_sub16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        a = val
        val -= arg
        self.alu_setval16(reg, val, *self.sub_flags(a, arg, val, 0xffff))

    def alu_mul16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val *= arg
        self.alu_setval16(reg, val, int(val > 0xffff), int(val > 0xffff))

    def alu_zero_divisor16(self):
        # div/mod by zero: destination and Z/N/C stay as they are, the
        # OVERFLOW flag is set for the program to test (jmp/jrx o).
        self.f.set_flag(FlagsRegister.OVERFLOW, 1)

    def alu_div16(self, reg, arg, reg2):
        if arg == 0:
            self.alu_zero_divisor16()
            return
        val = self.alu_getval16(reg)
        val //= arg
        self.alu_setval16(reg, val, 0, 0)

    def alu_mod16(self, reg, arg, reg2):
        if arg == 0:
            self.alu_zero_divisor16()
            return
        val = self.alu_getval16(reg)
        val %= arg
        self.alu_setval16(reg, val, 0, 0)

    def alu_inc16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        a = val
        val += 1
        self.alu_setval16(reg, val, *self.add_flags(a, 1, val, 0xffff))

    def alu_dec16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        a = val
        val -= 1
        self.alu_setval16(reg, val, *self.sub_flags(a, 1, val, 0xffff))

    def alu_and16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val &= arg
        self.alu_setval16(reg, val, 0, 0)

    def alu_or16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val |= arg
        self.alu_setval16(reg, val, 0, 0)

    def alu_xor16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val ^= arg
        self.alu_setval16(reg, val, 0, 0)

    def alu_shl16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        carry, over = self.shift_left_flags(val, arg, 16)
        self.alu_setval16(reg, (val << min(arg, 16)) & 0xffff)
        self.f.set_flag(FlagsRegister.CARRY, carry)
        self.f.set_flag(FlagsRegister.OVERFLOW, over)

    def alu_shr16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        carry = self.shift_right_carry(val, arg, 16)
        self.alu_setval16(reg, val >> min(arg, 16))
        self.f.set_flag(FlagsRegister.CARRY, carry)
        self.f.set_flag(FlagsRegister.OVERFLOW, 0)
    
    def alu_not16(self, reg, arg, reg2):
        val = self.alu_getval16(reg)
        val = ~val
        self.alu_setval16(reg, val, 0, 0)

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
    
    def process_frame(self, cpustackstart, cpuframetype):
        lastcpustackstart = cpustackstart
        if cpuframetype == Bc8183.STACKFRAME_TYPE_CALL:
            if cpustackstart + 2 < self.membus.size:
                cpuframe = (self.membus.read_byte(cpustackstart + 1) << 8) | self.membus.read_byte(cpustackstart + 2)
                cpustackstart += 3
                cpuframetypestr = 'CAL'
                return cpustackstart, lastcpustackstart, cpuframe, cpuframetypestr    
        else:
            if cpustackstart + 1 < self.membus.size:
                cpuframe = self.membus.read_byte(cpustackstart + 1)
                cpustackstart += 2
                cpuframetypestr = 'VAL'
                return cpustackstart, lastcpustackstart, cpuframe, cpuframetypestr

        cpuframe = None
        cpuframetypestr = 'ERR'

        return cpustackstart, lastcpustackstart, cpuframe, cpuframetypestr
    
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
        cpustackstart, lastcpustackstart, cpuframe, cpuframetypestr = self.process_frame(cpustackstart, cpuframetype)
        if cpuframe is None:
            print(":::empty:::")
            self.print_debug(":::empty:::")
            return
        
        while(cpuframetype > 0 and cpustackstart <= self.membus.size):
            msg = "{0} {1:04x}: {2:04x}".format(cpuframetypestr, lastcpustackstart, cpuframe)
            print(msg)
            self.print_debug(msg)

            cpustackstart, lastcpustackstart, cpuframe, cpuframetypestr = self.process_frame(cpustackstart, cpuframetype)
            
            if cpuframe is not None and cpustackstart < self.membus.size:
                cpuframetype = self.membus.read_byte(cpustackstart)
            else: cpuframetype = 0

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
            self.print_debug(f"====================== KILL at {self.pc.get():04x}")
        finally:
            self.flush_debug()

    def runAsync(self):
        self.inc_pc(0)
        self.print_context()
        while not self.kill and not self.env:
            self.run_next_opcode()
