#!/usr/bin/python3

def hi(b):
    return (b >> 4) & 0xf

def lo(b):
    return b & 0xf

class Register:
    def __init__(self, max_value):
        self.val = 0
        self.max_value = max_value
    def set(self,val):
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
    def __init__(self, max_value):
        super().__init__(max_value)
        self.zero = Register(0x1)
        self.carry = Register(0x1)
        self.negative = Register(0x1)
        self.overflow = Register(0x1)
        self.flags = {
            FlagsRegister.ZERO : self.zero,
            FlagsRegister.CARRY : self.carry,
            FlagsRegister.NEGATIVE : self.negative,
            FlagsRegister.OVERFLOW : self.overflow
        }
    def set_flag(self,flag,val):
        self.flags[flag].set(int(val))
        val = 0
        pos = 0
        for flag,reg in self.flags.items():
            val |= reg.get() << pos
            pos += 1
        self.set(val)

    def get_flag(self,flag):
        return bool(self.flags[flag].get())

class MemBus:
    def __init__(self, size):
        self.size = size
        self.mem = bytearray(size)
    def write_byte(self, addr, byte):
        self.mem[addr] = byte
    def read_byte(self, addr):
        return self.mem[addr]

class IOBus:
    def __init__(self):
        self.ports = { }
    def add_device(self, device):
        self.ports[device.input_port] = device.read_byte
        self.ports[device.output_ports] = device.write_byte
    def read_byte(self, port):
        return self.ports[port]()
    def write_byte(self, port, val):
        self.ports[port](val)

class Proc_Bc8181:
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
    CLC_OR  = 0x3
    CLC_XOR = 0x4
    CLC_SHL = 0x5
    CLC_SHR = 0x6
    CLC_NOT = 0x7
    CLC_OP_RNO = 0x8
    CLC_INC = 0xD
    CLC_DEC = 0xE

    def __init__(self,membus,iobus,debug):
        self.membus = membus
        self.iobus = iobus
        self.create_registers()
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
        self.regs[regno1].set(self.regs[regno2.get()])
        self.set_flags(regno1)
        self.inc_pc(1)

    def op_MOV_reg_mem(self):
        regno1 = lo(self.nextbyte)
        self.inc_pc(1)
        regno2 = hi(self.nextbyte)
        self.inc_pc(1)
        addr = self.get_addr(regno)
        if addr is not None:
            val = self.membus.read_byte(addr)
            self.regs[regno1].set(val)
            self.set_flags(regno1)

    def op_MOV_mem_reg(self):
        regno1 = lo(self.nextbyte)
        self.inc_pc(1)
        regno2 = hi(self.nextbyte)
        self.inc_pc(1)
        addr = self.get_addr(regno)
        if addr is not None:
            val = self.regs[regno1].get()
            self.membus.write_byte(addr, val)

    def op_CLC_a(self):
        subcode = lo(self.nextbyte)
        self.inc_pc(1)
        arg2 = None
        if  subcode == Proc_Bc8181.CLC_INC or \
            subcode == Proc_Bc8181.CLC_DEC:
            pass
        elif subcode & Proc_Bc8181.CLC_OP_RNO == \
            Proc_Bc8181.CLC_OP_RNO:
            regno = hi(self.nextbyte)
            subcode = subcode & (Proc_Bc8181.CLC_OP_RNO - 1)
            arg2 = self.regs[regno].get()
        else:
            arg2 = self.nextbyte
        self.inc_pc(1)
        oper = self.alu[subcode]
        result = oper(self.a.get(), arg2)
        self.set_flags(Proc_Bc8181.A, result)

    def get_addr(self, regno):
        if(regno == Proc_Bc8181.CI):
            hi = self.cs.get()
            lo = self.ci.get()
        elif (regno == Proc_Bc8181.DI):
            hi = self.ds.get()
            lo = self.di.get()
        elif (regno == Proc_Bc8181.SI):
            hi = self.ss.get()
            lo = self.si.get()
        else:
            return None
        addr = (hi << 8) | lo

    def set_flags(self, regno, val = None):
        if regno == Proc_Bc8181.A:
            self.f.set_flag(FlagsRegister.ZERO, int(self.a.get()==0))
            self.f.set_flag(FlagsRegister.NEGATIVE, int(self.a.get() & 0x80 == 0x80))
        if val is not None:
            self.f.set_flag(FlagsRegister.CARRY, int(val > 0xff or val < 0))

    def create_instructions(self):
        self.instructions = {
          0x0 : self.op_NOP,
          0x1 : self.op_MOV_imm,
          0x2 : self.op_MOV_reg,
          0x3 : self.op_MOV_reg_mem,
          0x4 : self.op_MOV_mem_reg,
          0xF : self.op_KIL
        }

    def create_registers(self):
        self.pc = Register(0xffff)
        self.f  = FlagsRegister(0xf)
        self.a  = Register(0xff)
        self.ss = Register(0xff)
        self.si = Register(0xff)
        self.ds = Register(0xff)
        self.di = Register(0xff)
        self.cs = Register(0xff)
        self.ci = Register(0xff)
        self.registers = {
            Proc_Bc8181.A  : self.a,
            Proc_Bc8181.CI : self.ci,
            Proc_Bc8181.DI : self.di,
            Proc_Bc8181.CS : self.cs,
            Proc_Bc8181.DS : self.ds,
            Proc_Bc8181.F  : self.f,
            Proc_Bc8181.SI : self.si,
            Proc_Bc8181.SS : self.ss,
            Proc_Bc8181.PC : self.pc
        }

    def alu_add(self,arg1,arg2):
        val = arg1 + arg2
        self.set_flags(Proc_Bc8181.A, val)
        self.a.set(val)
        #self.f.set_flag(FlagsRegister.OVERFLOW, ) TODO

    def alu_sub(self,arg1,arg2):
        val = arg1 - arg2
        self.set_flags(Proc_Bc8181.A, val)
        self.a.set(val)
        #self.f.set_flag(FlagsRegister.OVERFLOW, ) TODO

    def alu_and(self,arg1,arg2):
        val = arg1 & arg2
        self.set_flags(Proc_Bc8181.A)
        self.a.set(val)

    def alu_or(self,arg1,arg2):
        val = arg1 | arg2
        self.set_flags(Proc_Bc8181.A)
        self.a.set(val)

    def alu_xor(self,arg1,arg2):
        val = arg1 ^ arg2
        self.set_flags(Proc_Bc8181.A)
        self.a.set(val)

    def alu_shl(self,arg1,arg2):
        val = arg1 << arg2
        self.set_flags(Proc_Bc8181.A, val & 0x100)
        self.a.set(val)

    def alu_shr(self,arg1,arg2):
        val = arg1 >> arg2
        self.set_flags(Proc_Bc8181.A, -(arg1 & 0x1))
        self.a.set(val)

    def alu_not(self,arg1,arg2):
        val = ~arg1
        self.set_flags(Proc_Bc8181.A, arg1)
        self.a.set(val)

    def alu_inc(self,arg1,arg2):
        val = arg1 + 1
        self.set_flags(Proc_Bc8181.A, arg)
        self.a.set(val)

    def alu_dec(self,arg1,arg2):
        val = arg1 - 1
        self.set_flags(Proc_Bc8181.A, arg)
        self.a.set(val)

    def create_arithmetic_and_logical_unit(self):
        self.alu = {
            Proc_Bc8181.CLC_ADD : self.alu_add,
            Proc_Bc8181.CLC_SUB : self.alu_sub,
            Proc_Bc8181.CLC_AND : self.alu_and,
            Proc_Bc8181.CLC_OR  : self.alu_or,
            Proc_Bc8181.CLC_XOR : self.alu_xor,
            Proc_Bc8181.CLC_SHL : self.alu_shl,
            Proc_Bc8181.CLC_SHR : self.alu_shr,
            Proc_Bc8181.CLC_NOT : self.alu_not,
            Proc_Bc8181.CLC_INC : self.alu_inc,
            Proc_Bc8181.CLC_DEC : self.alu_dec
        }

    def set_reg(self, regno, val):
        reg = self.registers[regno]
        reg.set(val)

    def get_reg(self, regno):
        reg = self.registers[regno]
        return reg.get(val)

    def run_next_opcode(self):
        opcode = hi(self.nextbyte)
        instruction = self.instructions[opcode]
        instruction()
        self.print_context()

    def print_debug(self, mesg):
        if self.debug:
            print(mesg)

    def print_context(self):
        self.print_debug("PC: {0:x} next instruction: {1:x}".format(self.pc.get(), self.nextbyte))
        self.print_debug("SS: {0:x} SI: {1:x}".format(self.ss.get(), self.si.get()))
        self.print_debug("A:  {0:x} F:  {1:b}".format(self.a.get(), self.f.get()))
        self.print_debug("CS: {0:x} CI: {1:x}".format(self.cs.get(), self.ci.get()))
        self.print_debug("DS: {0:x} DI: {1:x}".format(self.ds.get(), self.ds.get()))

    def run(self):
        self.inc_pc(0)
        while not self.kill:
            self.run_next_opcode()
        self.print_debug("====================== KILL")

class Bc16:
    def __init__(self):
        self.mem = MemBus(0x4000)
        self.io = IOBus()
        self.proc = Proc_Bc8181(self.mem,self.io,True)

    def run(self):
        self.proc.run()

def main():
    computer = Bc16()
    computer.mem.write_byte(0x0000,0xff)
    computer.run()

if __name__ == "__main__":
    main()