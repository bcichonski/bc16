#!/usr/bin/python3
from bc16 import bc16_io
from bc16 import bc16_cpu
from bc16 import bc16_mem
from bc16 import bc16_env

class Bc16:
    def __init__(self, env):
        self.mem = bc16_mem.MemBus(env, 0x4000)
        self.io = bc16_io.IOBus()
        self.proc = bc16_cpu.Bc8181(self.mem,self.io,True)

    def run(self):
        self.proc.run()

def main():
    env = bc16_env.Environment()
    computer = Bc16(env)
    computer.mem.write_byte(0x0000,0xff)
    computer.run()

if __name__ == "__main__":
    main()
