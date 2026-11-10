#!/usr/bin/python3

from bc64 import bc64_io
from bc64 import bc8183_cpu
from bc64 import bc64_mem
from bc64 import bc64_env
import argparse
import sys

MEMORY_SIZE = 0x10000
TOP_ADDRESS = MEMORY_SIZE - 1
STACK_TOP = TOP_ADDRESS - 1

class Bc64:
    def __init__(self, env, debug, no_floppy=False):
        self.mem = bc64_mem.MemBus(env, MEMORY_SIZE)
        self.keyboard = bc64_io.TerminalKeyboard(env)
        self.printer = bc64_io.TerminalPrinter(env)
        self.taperecorder = bc64_io.TapeRecorder(env)
        self.clock = bc64_io.Clock(env)
        self.randgen = bc64_io.RandomGenerator(env)
        if no_floppy:
            self.floppydrive = bc64_io.NoFloppyDrive()
        else:
            self.floppydrive = bc64_io.FloppyDriveV1(env, self.mem)
        
        self.io = bc64_io.IOBus()
        self.io.add_device(self.keyboard)
        self.io.add_device(self.printer)
        self.io.add_device(self.taperecorder)
        self.io.add_device(self.clock)
        self.io.add_device(self.randgen)
        self.io.add_device(self.floppydrive)

        self.cpu = bc8183_cpu.Bc8183(self.mem, self.io, debug, STACK_TOP)

    def write_top_kil(self):
        """Start-up step: 0xffff is ordinary RAM holding KIL, so running off the end of memory halts."""
        self.mem.write_byte(TOP_ADDRESS, 0xff)

    def run(self, max_instructions=None):
        """Run until KIL. Returns True on KIL, False when max_instructions was reached first."""
        if max_instructions is None:
            self.cpu.run()
            return True
        cpu = self.cpu
        count = 0
        try:
            cpu.inc_pc(0)
            cpu.print_context()
            while not cpu.kill:
                if count >= max_instructions:
                    return False
                cpu.run_next_opcode()
                count += 1
            cpu.print_debug(f"====================== KILL at {cpu.pc.get():04x}")
            return True
        finally:
            cpu.flush_debug()

EXIT_OK = 0
EXIT_LIMIT = 3

def positive_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer: {text!r}")
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value

def build_parser():
    parser = argparse.ArgumentParser(
        prog='bc64.py',
        description='bc64 emulator. With a terminal on stdin and no option the console is used; '
                    'with any option, or with piped stdin, the scripted (headless) environment is used '
                    'and keys are read from stdin unless --input FILE is given.')
    parser.add_argument('rom', nargs='?', help='ROM image loaded at 0x0000')
    parser.add_argument('trace', nargs='?', help='any word here turns the per-instruction trace on')
    parser.add_argument('--disk-a', metavar='FILE', help='disk image answered to the "Disk A name:" prompt')
    parser.add_argument('--disk-b', metavar='FILE', help='disk image answered to the "Disk B name:" prompt')
    parser.add_argument('--no-floppy', action='store_true',
                        help='do not attach a floppy drive (port 0x08 reads 0x00); conflicts with --disk-a and --disk-b')
    parser.add_argument('--tape-dir', metavar='DIR', help='directory where *.btap tape files are read and written')
    parser.add_argument('--input', metavar='FILE',
                        help='file with the keystrokes to type; "-" reads stdin (the default when stdin is piped)')
    parser.add_argument('--output', metavar='FILE', help='file receiving a copy of every printer byte')
    parser.add_argument('--max-instructions', metavar='N', type=positive_int,
                        help='stop with exit code 3 after N instructions without a halt')
    return parser

def parse_args(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.no_floppy and (args.disk_a is not None or args.disk_b is not None):
        parser.error('--no-floppy cannot be combined with --disk-a or --disk-b')
    return args

def stdin_is_tty():
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False

def is_headless(args):
    return stdin_is_tty() is False or args.no_floppy or any(value is not None for value in (
        args.disk_a, args.disk_b, args.tape_dir, args.input, args.output, args.max_instructions))

def make_env(args, trace):
    if not is_headless(args):
        return bc64_env.Environment()
    input_source = args.input
    if input_source is None and not stdin_is_tty():
        input_source = '-'
    return bc64_env.ScriptedEnvironment(
        debug=trace, disk_a=args.disk_a, disk_b=args.disk_b, tape_dir=args.tape_dir,
        input_source=input_source, output_path=args.output)

def main(argv):
    """Runs the emulator. argv includes the program name. Returns the exit code:
    0 halt or end of input, 3 instruction limit; 2 usage error (SystemExit from argparse);
    an exception in the emulator propagates (Python exits with 1)."""
    args = parse_args(argv[1:])
    trace = args.trace is not None
    env = make_env(args, trace)
    try:
        computer = Bc64(env, trace, args.no_floppy)
        if args.rom is not None:
            import_rom(args.rom, env, computer.mem)
        computer.write_top_kil()
        try:
            halted = computer.run(args.max_instructions)
        except bc64_env.EndOfInput:
            return EXIT_OK
        if not halted:
            print(f"bc64: stopped after {args.max_instructions} instructions without a halt", file=sys.stderr)
            return EXIT_LIMIT
        dump_mem('bc64.dmp', env, computer.mem)
        return EXIT_OK
    finally:
        if hasattr(env, 'close'):
            env.close()

def dump_mem(file, env, mem):
    fhandle = env.open_file_to_write(file)
    i = 0
    while i < MEMORY_SIZE:
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
    sys.exit(main(sys.argv))
