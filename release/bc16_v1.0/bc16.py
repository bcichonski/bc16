#!/usr/bin/python3

from bc32 import bc32_io
from bc32 import bc8182_cpu
from bc32 import bc32_mem
from bc32 import bc32_env
from sys import argv

TOPMEM = 0x4000


class Bc16:
    def __init__(self, env, debug):
        self.mem = bc32_mem.MemBus(env, TOPMEM)
        self.keyboard = bc32_io.TerminalKeyboard(env)
        self.printer = bc32_io.TerminalPrinter(env)
        self.taperecorder = bc32_io.TapeRecorder(env)
        self.floppydrive = bc32_io.FloppyDriveV1(env, self.mem)
        self.io = bc32_io.IOBus()
        self.io.add_device(self.keyboard)
        self.io.add_device(self.printer)
        self.io.add_device(self.taperecorder)
        self.io.add_device(self.floppydrive)
        self.cpu = bc8182_cpu.Bc8181(self.mem, self.io, debug)

    def run(self):
        self.cpu.run()

def main(argv):
    env = bc32_env.Environment()
    computer = Bc16(env, len(argv) >= 3)
    if len(argv) >= 2:
        import_rom(argv[1], env, computer.mem)
    computer.mem.write_byte(TOPMEM-1, 0xff)
    computer.run()

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
