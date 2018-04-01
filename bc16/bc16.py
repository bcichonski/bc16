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
