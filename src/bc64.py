#!/usr/bin/python3

from bc64 import bc64_io
from bc64 import bc8182_cpu
from bc64 import bc64_mem
from bc64 import bc64_env
from sys import argv

TOPMEM = 0xffff

class Bc32:
    def __init__(self, env, debug):
        self.mem = bc64_mem.MemBus(env, TOPMEM)
        self.keyboard = bc64_io.TerminalKeyboard(env)
        self.printer = bc64_io.TerminalPrinter(env)
        self.taperecorder = bc64_io.TapeRecorder(env)
        self.clock = bc64_io.Clock(env)
        self.randgen = bc64_io.RandomGenerator(env)
        self.floppydrive = bc64_io.FloppyDriveV1(env, self.mem)
        
        self.io = bc64_io.IOBus()
        self.io.add_device(self.keyboard)
        self.io.add_device(self.printer)
        self.io.add_device(self.taperecorder)
        self.io.add_device(self.clock)
        self.io.add_device(self.randgen)
        self.io.add_device(self.floppydrive)

        self.cpu = bc8182_cpu.Bc8182(self.mem, self.io, debug)

    def run(self):
        self.cpu.run()

def main(argv):
    env = bc64_env.Environment()
    computer = Bc32(env, len(argv) >= 3)
    if len(argv) >= 2:
        import_rom(argv[1], env, computer.mem)
    computer.mem.write_byte(TOPMEM-1, 0xff)
    computer.run()
    dump_mem('bc64.dmp', env, computer.mem)

def dump_mem(file, env, mem):
    fhandle = env.open_file_to_write(file)
    i = 0
    while i < TOPMEM:
        byte = mem.read_byte(i)
        env.write_byte(fhandle, byte)
        i+=1
    env.close_file(fhandle)

def import_rom(file, env, mem):
    fhandle = env.open_file_to_read(file)
    i = 0
    byte = env.read_byte(fhandle)
    while len(byte) > 0:
        mem.write_byte(i, ord(byte))
        i += 1
        byte = env.read_byte(fhandle)
    env.close_file(fhandle)

if __name__ == "__main__":
    main(argv)
