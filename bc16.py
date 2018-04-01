#!/usr/bin/python3
from bc16 import bc16_io
from bc16 import bc16_cpu

class MemBus:
    def __init__(self, size):
        self.size = size
        self.mem = bytearray(size)
    def write_byte(self, addr, byte):
        self.mem[addr] = byte
    def read_byte(self, addr):
        return self.mem[addr]

class Bc16:
    def __init__(self):
        self.mem = MemBus(0x4000)
        self.io = bc16_io.IOBus()
        self.proc = bc16_cpu.Bc8181(self.mem,self.io,True)

    def run(self):
        self.proc.run()

def main():
    computer = Bc16()
    computer.mem.write_byte(0x0000,0xff)
    computer.run()

if __name__ == "__main__":
    main()
