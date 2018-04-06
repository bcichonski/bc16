from bc16 import bc16_cpu
from random import random
# from https://github.com/joeyespo/py-getch
try:
    from msvcrt import getch
except ImportError:
    def getch():
        """
        Gets a single character from STDIO.
        """
        import sys
        import tty
        import termios
        fd = sys.stdin.fileno()
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            old = termios.tcgetattr(fd)
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
# end from

class IODevice:
    def __init__(self):
        self.input_port = None
        self.output_port = None
    def read_byte(self):
        pass
    def write_byte(self):
        pass

class TerminalPrinter(IODevice):
    DEFAULT_IO_PORT = 0x1
    def __init__(self):
        self.io_port = TerminalPrinter.DEFAULT_IO_PORT
    def read_byte(self):
        return 0x50
    def write_byte(self, byte):
        print(chr(byte), end='')

class TerminalKeyboard(IODevice):
    DEFAULT_IO_PORT = 0x0
    def __init__(self):
        self.io_port = TerminalKeyboard.DEFAULT_IO_PORT
    def read_byte(self):
        return ord(getch())
    def write_byte(self, byte):
        pass

class TapeRecorder(IODevice):
    DEFAULT_IO_PORT = 0x2
    READY = 0x10
    TAPE4WRITE = 0x40
    TAPE4READ = 0x80
    MOVE = 0x20
    ERROR = 0x08
    DX = FlagsRegister.B0
    TX = FlagsRegister.B1
    HALF_BYTE = 0x80
    def __init__(self, env):
        self.state = bc16_cpu.FlagsRegister(0xff)
        self.set_state(TapeRecorder.READY)
        self.env = env
        self.io_port = TapeRecorder.DEFAULT_IO_PORT
        random.seed(None)
    def read_byte(self):
        if(self.state.get_flag(TapeRecorder.TX)==False):
            byte = self.file_handle.read(1)
            if not byte:
                byte = self.get_random()
            self.state.set_flag(TapeRecorder.DX,
              bool((byte & TapeRecorder.HALF_BYTE) == TapeRecorder.HALF_BYTE))
            self.state.set_flag(TapeRecorder.DX, True)
    def get_random(self, up=0xff):
        return random.randint(0,up)
    def write_byte(self):
        if(self.state.get_flag(TapeRecorder.TX)==True):
            bit = self.state.get_flag(TapeRecorder.DX)
            byte = self.get_random(TapeRecorder.HALF_BYTE)
            if bool(bit):
                 byte = byte | TapeRecorder.HALF_BYTE
            self.file_handle.write(byte)
            self.state.set_flag(TapeRecorder.DX, False)
    def set_state(self, newstate):
        if newstate == TapeRecorder.READY:
            if newstate == TapeRecorder.MOVE:
                self.close()
            ready = True
            write = False
            read = False
            move = False
            error = False
        elif newstate == TapeRecorder.TAPE4WRITE:
            if(self.intstate == TapeRecorder.READY):
                filename = self.env.get_string("Type name of the tape to write: ")
                filename += ".bc16.tap"
                try:
                    self.openwrite(filename)
                    self.intstate = newstate
                except:
                    error = True
                    newstate = TapeRecorder.ERROR
                ready = True
                write = True
                read  = False
                move  = False
            else:
                ready = False
                write = False
                read  = False
                move  = False
                error = True
        elif newstate == TapeRecorder.TAPE4READ:
            if(self.intstate == TapeRecorder.READY):
                filename = self.env.get_string("Type name of the tape to read: ")
                filename += ".bc16.tap"
                try:
                    self.openread(filename)
                    self.intstate = newstate
                except:
                    error = True
                    newstate = TapeRecorder.ERROR
                ready = True
                write = True
                read  = False
                move  = False
            else:
                ready = False
                write = False
                read  = False
                move  = False
                error = True
        elif newstate == TapeRecorder.MOVE:
            if(self.intstate == TapeRecorder.TAPE4READ or
               self.intstate == TapeRecorder.TAPE4WRITE):
                ready = False
                move = True
                error = False
            else:
                ready = False
                write = False
                read = False
                move = False
                error = True

        self.intstate = newstate
        self.state.set_flag(TapeRecorder.READY, ready)
        self.state.set_flag(TapeRecorder.TAPE4WRITE, write)
        self.state.set_flag(TapeRecorder.TAPE4READ, read)
        self.state.set_flag(TapeRecorder.MOVE, move)
        self.state.set_flag(TapeRecorder.ERROR, error)

    def openread(self, filename):
        self.file_handle = open(filename, "rb")

    def openwrite(self, filename):
        self.file_handle = open(filename, "wb")

    def close(self):
        self.file_handle.close()
        self.file_handle = None

class IOBus:
    def __init__(self):
        self.in_ports = { }
        self.out_ports = { }
    def add_device(self, device):
        self.in_ports[device.io_port] = device.read_byte
        self.out_ports[device.io_port] = device.write_byte
    def read_byte(self, port):
        return self.in_ports[port]()
    def write_byte(self, port, val):
        self.out_ports[port](val)
