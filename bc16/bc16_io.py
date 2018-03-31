from getch import getch

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

class CasseteRecorder(IODevice):
    DEFAULT_IO_PORT = 0x2
    def __init__(self):
        self.io_port = TerminalKeyboard.DEFAULT_IO_PORT
    def read_byte(self):
        pass
    def write_byte(self, byte):
        pass

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
