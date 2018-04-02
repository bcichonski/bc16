from bc16 import bc16_cpu
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
    DX = 0x01
    def __init__(self, env):
        self.state = bc16_cpu.FlagsRegister(0xff)
        self.set_state(TapeRecorder.READY)
        self.env = env
        self.io_port = TapeRecorder.DEFAULT_IO_PORT
    def read_byte(self):
        pass
    def write_byte(self, byte):
        pass
    def set_state(self, newstate):
        
        
        if newstate == TapeRecorder.READY:
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
                    self.intstate = TapeRecorder.ERROR
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
                    self.intstate = TapeRecorder.ERROR
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
        
        self.intstate = newstate
        self.state.set_flag(TapeRecorder.READY, ready)
        self.state.set_flag(TapeRecorder.TAPE4WRITE, write)
        self.state.set_flag(TapeRecorder.TAPE4READ, read)
        self.state.set_flag(TapeRecorder.MOVE, move)
        self.state.set_flag(TapeRecorder.ERROR, error)
            

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
