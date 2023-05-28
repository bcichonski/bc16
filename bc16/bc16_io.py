from bc16 import bc16_cpu
import random

class IODevice:
    def __init__(self):
        self.io_port = None
    def read_byte(self):
        pass
    def write_byte(self):
        pass

class TerminalPrinter(IODevice):
    DEFAULT_IO_PORT = 0x1
    READY = 0x40
    def __init__(self, env):
        self.env = env
        self.io_port = TerminalPrinter.DEFAULT_IO_PORT
    def read_byte(self):
        return TerminalPrinter.READY
    def write_byte(self, byte):
        self.env.write_char(byte)

class TerminalKeyboard(IODevice):
    DEFAULT_IO_PORT = 0x0
    def __init__(self, env):
        self.env = env
        self.io_port = TerminalKeyboard.DEFAULT_IO_PORT
    def read_byte(self):
        return ord(self.env.get_char())
    def write_byte(self, byte):
        pass

class TapeRecorder(IODevice):
    DEFAULT_IO_PORT = 0x2
    READY = 0x10
    TAPE4WRITE = 0x40
    TAPE4READ = 0x80
    MOVE = 0x20
    ERROR = 0x08
    DX = 0x1
    TX = 0x2
    F_READY = bc16_cpu.FlagsRegister.B4
    F_TAPE4WRITE = bc16_cpu.FlagsRegister.B6
    F_TAPE4READ = bc16_cpu.FlagsRegister.B7
    F_MOVE = bc16_cpu.FlagsRegister.B5
    F_ERROR = bc16_cpu.FlagsRegister.B3
    F_DX = bc16_cpu.FlagsRegister.B0
    F_TX = bc16_cpu.FlagsRegister.B1
    HALF_BYTE = 0x80
    def __init__(self, env):
        self.state = bc16_cpu.FlagsRegister(0xff)
        self.intstate = TapeRecorder.READY
        self.env = env
        self.set_state(TapeRecorder.READY)
        self.io_port = TapeRecorder.DEFAULT_IO_PORT
        random.seed()
    def read_byte(self):
        if self.intstate == TapeRecorder.MOVE and self.state.get_flag(TapeRecorder.F_TAPE4READ):
           byte = ord(self.env.read_byte(self.file_handle))
           self.state.set_flag(TapeRecorder.F_TX, True)
           self.state.set_flag(TapeRecorder.F_DX, byte > 0)
        return self.state.get()
    def write_byte(self,byte):
        tx = bool(byte & TapeRecorder.TX == TapeRecorder.TX)
        if(tx):
            tape4write = bool(byte & TapeRecorder.TAPE4WRITE == TapeRecorder.TAPE4WRITE)
            if(tape4write):
                self.set_state(TapeRecorder.TAPE4WRITE)
            else:
                tape4read = bool(byte & TapeRecorder.TAPE4READ == TapeRecorder.TAPE4READ)
                if tape4read:
                    self.set_state(TapeRecorder.TAPE4READ)
                else:
                    move = bool(byte & TapeRecorder.MOVE == TapeRecorder.MOVE)
                    if(move):
                        self.set_state(TapeRecorder.MOVE)
                    else:
                        ready = bool(byte & TapeRecorder.READY == TapeRecorder.READY)
                        if ready:
                            self.set_state(TapeRecorder.READY)
                        else:
                            self.state.set_flag(TapeRecorder.F_TX, True)
                            self.state.set_flag(TapeRecorder.F_DX, bool(byte & TapeRecorder.DX == TapeRecorder.DX))
                            if self.state.get_flag(TapeRecorder.F_TAPE4WRITE):
                                self.write_bit()
                            elif self.state.get_flag(TapeRecorder.F_TAPE4READ):
                                self.read_bit()
            self.state.set_flag(TapeRecorder.F_TX, False)

    def read_bit(self):
        if(self.state.get_flag(TapeRecorder.F_TX)==True):
            byte = ord(self.env.read_byte(self.file_handle))
            self.state.set_flag(TapeRecorder.F_DX, byte > 0)
            self.state.set_flag(TapeRecorder.F_TX, False)
    def get_random(self, up=0xff):
        return random.randint(0,up)
    def write_bit(self):
        if(self.state.get_flag(TapeRecorder.F_TX)):
            bit = self.state.get_flag(TapeRecorder.F_DX)
            #byte = self.get_random(TapeRecorder.HALF_BYTE-1)
            byte = 0
            if bit:
                 #byte = byte | TapeRecorder.HALF_BYTE
                 byte = 1
            self.env.write_byte(self.file_handle, byte)
            self.state.set_flag(TapeRecorder.F_TX, False)
            #self.env.log("]> tape write 0x{0:02x}".format(byte))
    def set_state(self, newstate):
        if self.intstate != newstate:
            self.env.log("tape recorder state changed from 0x{0:02x} to 0x{1:02x}".format(self.intstate, newstate))
        if newstate == TapeRecorder.READY:
            if self.intstate == TapeRecorder.MOVE:
                self.close()
            ready = True
            write = False
            read = False
            move = False
            error = False
        elif newstate == TapeRecorder.TAPE4WRITE:
            if(self.intstate == TapeRecorder.READY):
                filename = self.env.get_string("Type name of the tape to write: ")
                filename += ".btap"
                try:
                    self.openwrite(filename)
                    self.intstate = newstate
                    error = False
                except Exception as e:
                    self.env.log(str(e))
                    print(str(e))
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
                filename += ".btap"
                try:
                    self.openread(filename)
                    self.intstate = newstate
                    error = False
                except:
                    error = True
                    newstate = TapeRecorder.ERROR
                ready = True
                write = False
                read  = True
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
                write = self.state.get_flag(TapeRecorder.F_TAPE4WRITE)
                read = self.state.get_flag(TapeRecorder.F_TAPE4READ)
            else:
                ready = False
                write = False
                read = False
                move = False
                error = True
        self.intstate = newstate
        self.state.set_flag(TapeRecorder.F_READY, ready)
        self.state.set_flag(TapeRecorder.F_TAPE4WRITE, write)
        self.state.set_flag(TapeRecorder.F_TAPE4READ, read)
        self.state.set_flag(TapeRecorder.F_MOVE, move)
        self.state.set_flag(TapeRecorder.F_ERROR, error)

    def openread(self, filename):
        self.file_handle = self.env.open_file_to_read(filename)

    def openwrite(self, filename):
        self.file_handle = self.env.open_file_to_write(filename)

    def close(self):
        self.env.close_file(self.file_handle)
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
