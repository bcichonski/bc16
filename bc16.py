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
    zero = 0x0
    carry = 0x1
    negative = 0x2
    overflow = 0x3
    def __init__(self, max_value):
        super().__init__(max_value)
        self.zero = Register(0x1)
        self.carry = Register(0x1)
        self.negative = Register(0x1)
        self.overflow = Register(0x1)
        self.flags = {
            FlagsRegister.zero : self.zero,
            FlagsRegister.carry : self.carry,
            FlagsRegister.negative : self.negative,
            FlagsRegister.overflow : self.overflow
        }
    def set_flag(self,flag,val):
        self.flags[flag].set(int(val))
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
        
class Bc8181:
    def __init__(self,membus,iobus,debug):
        self.membus = membus
        self.iobus = iobus
        self.create_registers()
        self.create_instructions()
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
        self.inc_pc(1)
        
    def op_MOV_reg(self):
        regno1 = lo(self.nextbyte)
        self.inc_pc(1)
        regno2 = hi(self.nextbyte)
        self.regs[regno1].set(self.regs[regno2.get()])
        self.inc_pc(1)
        
    def create_instructions(self):
        self.instructions = {
          0x0 : self.op_NOP,
          0x1 : self.op_MOV_imm,
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
            0x1 : self.a,
            0x4 : self.ci,
            0x5 : self.di,
            0x8 : self.cs,
            0x9 : self.ds,
            0xB : self.f,
            0xC : self.si,
            0xD : self.ss,
            0xF : self.pc
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
        self.proc = Bc8181(self.mem,self.io,True)    
        
    def run(self):
        self.proc.run()
        
computer = Bc16()
computer.mem.write_byte(0x0000,0xff)
computer.run()
