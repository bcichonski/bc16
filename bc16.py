#!/usr/bin/python3

from bc16 import bc16_io
from bc16 import bc16_cpu
from bc16 import bc16_mem
from bc16 import bc16_env
from sys import argv

TOPMEM = 0x4000


class Bc16:
    def __init__(self, env, debug):
        self.mem = bc16_mem.MemBus(env, TOPMEM)
        self.keyboard = bc16_io.TerminalKeyboard(env)
        self.printer = bc16_io.TerminalPrinter(env)
        self.taperecorder = bc16_io.TapeRecorder(env)
        self.io = bc16_io.IOBus()
        self.io.add_device(self.keyboard)
        self.io.add_device(self.printer)
        self.io.add_device(self.taperecorder)
        self.cpu = bc16_cpu.Bc8181(self.mem, self.io, debug)

    def run(self):
        self.cpu.run()

def main(argv):
    env = bc16_env.Environment()
    computer = Bc16(env, len(argv) >= 3)
    if len(argv) >= 2:
        import_rom(argv[1], env, computer.mem)
    computer.mem.write_byte(TOPMEM-1, 0xff)
    computer.run()

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
