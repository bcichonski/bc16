#!/usr/bin/python3
from bc16 import bc16_io
from bc16 import bc16_cpu
from bc16 import env

class MemBus:
    def __init__(self, env, size):
        self.env = env
        self.size = size
        self.mem = bytearray(size)
    def write_byte(self, addr, byte):
        self.mem[addr] = byte
        self.env.log("MEM WRITE AT {0:x} VAL {1:x}".format(addr, byte)) 
    def read_byte(self, addr):
        val = self.mem[addr]
        self.env.log("MEM READ AT {0:x} VAL {1:x}".format(addr, val))
        return val

class Bc16:
    def __init__(self, env):
        self.mem = MemBus(env, 0x4000)
        self.io = bc16_io.IOBus()
        self.proc = bc16_cpu.Bc8181(self.mem,self.io,True)

    def run(self):
        self.proc.run()

def main():
    env = Environment()
    computer = Bc16(env)
    computer.mem.write_byte(0x0000,0xff)
    computer.run()

if __name__ == "__main__":
    main()
