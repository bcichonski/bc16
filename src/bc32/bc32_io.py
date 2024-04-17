from bc32 import bc8182_cpu
import random
import datetime

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
    F_READY = bc8182_cpu.FlagsRegister.B4
    F_TAPE4WRITE = bc8182_cpu.FlagsRegister.B6
    F_TAPE4READ = bc8182_cpu.FlagsRegister.B7
    F_MOVE = bc8182_cpu.FlagsRegister.B5
    F_ERROR = bc8182_cpu.FlagsRegister.B3
    F_DX = bc8182_cpu.FlagsRegister.B0
    F_TX = bc8182_cpu.FlagsRegister.B1
    HALF_BYTE = 0x80
    def __init__(self, env):
        self.state = bc8182_cpu.FlagsRegister(0xff)
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

class Clock(IODevice):
    DEFAULT_IO_PORT = 0x03
    STATE_READY = 0x80
    STATE_ERROR = 0xff
    STATE_TIME_HOUR = 0x01
    STATE_TIME_MINUTE = 0x02
    STATE_TIME_SECOND = 0x03
    STATE_DATE_YEAR = 0x11
    STATE_DATE_MONTH = 0x12
    STATE_DATE_DAY = 0x13
    COMMAND_GETTIME = 0x01
    COMMAND_GETDATE = 0x02
    COMMAND_RESET = 0xff

    def __init__(self, env):
        self.env = env
        self.io_port = Clock.DEFAULT_IO_PORT
        self.state = Clock.STATE_READY

    def read_byte(self):
        if(self.state == Clock.STATE_READY):
            return Clock.STATE_READY
        elif(self.state == Clock.STATE_TIME_HOUR):
            self.state = Clock.STATE_TIME_MINUTE
            return self.currtime.hour
        elif(self.state == Clock.STATE_TIME_MINUTE):
            self.state = Clock.STATE_TIME_SECOND
            return self.currtime.minute
        elif(self.state == Clock.STATE_TIME_SECOND):
            self.state = Clock.STATE_READY
            return self.currtime.second
        elif(self.state == Clock.STATE_DATE_YEAR):
            self.state = Clock.STATE_DATE_MONTH
            return (self.currtime.year - 2000) & 0xff
        elif(self.state == Clock.STATE_DATE_MONTH):
            self.state = Clock.STATE_DATE_DAY
            return self.currtime.month & 0xff
        elif(self.state == Clock.STATE_DATE_DAY):
            self.state = Clock.STATE_READY
            return self.currtime.day & 0xff
        
        return Clock.STATE_ERROR
    
    def write_byte(self, byte):
        if (byte == Clock.COMMAND_RESET):
            self.state = Clock.STATE_READY
        elif (self.state == Clock.STATE_READY and byte == Clock.COMMAND_GETTIME):
            self.currtime = datetime.datetime.now()
            self.state = Clock.STATE_TIME_HOUR
            return
        elif (self.state == Clock.STATE_READY and byte == Clock.COMMAND_GETDATE):
            self.currtime = datetime.datetime.now()
            self.state = Clock.STATE_DATE_YEAR
            return
        
class RandomGenerator(IODevice):
    DEFAULT_IO_PORT = 0x05

    def __init__(self, env):
        self.env = env
        self.io_port = RandomGenerator.DEFAULT_IO_PORT
        self.rnd = random.Random()

    def read_byte(self):
        return self.rnd.randint(0x00, 0xff)
    
    def write_byte(self, byte):
        None

class FloppyDriveV1(IODevice):
    DEFAULT_IO_PORT = 0x08
    SECTOR_SIZE = 128
    SECTORS = 16
    TRACKS = 64

    CMD_PING = 0xf0
    CMD_CFG = 0xf1
    CMD_SETDRVA = 0xfa
    CMD_SETDRVB = 0xfb
    CMD_READSECT = 0xf2
    CMD_WRITESECT = 0xf3
    CMD_EJECT = 0xf4

    STATE_READY = 0x10
    STATE_FDDV1 = 0x01
    STATE_CFG1 = 0x02
    STATE_CFG2 = 0x03
    STATE_DRIVE_FAILURE = 0xe1
    STATE_READ_FAILURE = 0xe2
    STATE_WRITE_FAILURE = 0xe3
    STATE_RD1 = 0x04
    STATE_RD2 = 0x05
    STATE_WR1 = 0x06
    STATE_WR2 = 0x07

    def __init__(self, env, mem):
        self.env = env
        self.mem = mem
        self.io_port = FloppyDriveV1.DEFAULT_IO_PORT
        self.state = FloppyDriveV1.STATE_READY
        self.dmaaddr = None
        self.fileA_name = None
        self.fileB_name = None

    def read_byte(self):
        return self.state
    
    def create_disk(self, name):
        handle = self.env.open_file_to_write(name)
        disksize = FloppyDriveV1.TRACKS * FloppyDriveV1.SECTORS * FloppyDriveV1.SECTOR_SIZE

        bytes = bytearray(disksize)
        self.env.write_bytes(handle, bytes)
        self.env.close_file(handle)
    
    def eject_disk(self, handle, name):
        if handle is not None:
            self.env.close_file(handle)
            self.env.log("Disk {}: {} ejected.".format(self.active_drive, name))
            return (None, None)
        
        return (handle, name)
    
    def check(self, handle, name):
        if self.sector < 0 or self.sector >= FloppyDriveV1.SECTORS:
            return (handle, name, FloppyDriveV1.STATE_READ_FAILURE)
        
        if self.track < 0 or self.track >= FloppyDriveV1.TRACKS:
            return (handle, name, FloppyDriveV1.STATE_READ_FAILURE)
        
        if name is None:
            name = self.env.get_string('Disk {} name:'.format(self.active_drive))

        if handle is None:
            if not self.env.file_exists(name):
                self.create_disk(name)
            handle = self.env.open_file_to_readwrite(name)

        return (handle, name, FloppyDriveV1.STATE_READY)
    
    def read_sector(self, handle, name):
        (handle, name, state) = self.check(handle, name)
        if state != FloppyDriveV1.STATE_READY:
            return (handle, name, state)

        position = self.track * FloppyDriveV1.SECTORS * FloppyDriveV1.SECTOR_SIZE + self.sector * FloppyDriveV1.SECTOR_SIZE
        self.env.move_file_handle(handle, position)
        bytes = self.env.read_bytes(handle, FloppyDriveV1.SECTOR_SIZE)

        dmaaddr = self.dmaaddr
        for byte in bytes:
            self.mem.write_byte(dmaaddr, byte & 0xff)
            dmaaddr += 1

        return (handle, name, FloppyDriveV1.STATE_READY)
    
    def write_sector(self, handle, name):
        (handle, name, state) = self.check(handle, name)
        if state != FloppyDriveV1.STATE_READY:
            return (handle, name, state)

        bytes = bytearray(FloppyDriveV1.SECTOR_SIZE)

        i = 0
        while (i < FloppyDriveV1.SECTOR_SIZE):
            bytes[i] = self.mem.read_byte(self.dmaaddr + i)
            i += 1

        position = self.track * FloppyDriveV1.SECTORS * FloppyDriveV1.SECTOR_SIZE + self.sector * FloppyDriveV1.SECTOR_SIZE
        self.env.move_file_handle(handle, position)
        res = self.env.write_bytes(handle, bytes)
        if res != FloppyDriveV1.SECTOR_SIZE:
            raise Exception("Disk write error")

        return (handle, name, FloppyDriveV1.STATE_READY)
    
    def write_byte(self, byte):
        if (byte == FloppyDriveV1.CMD_PING):
            self.state = FloppyDriveV1.STATE_READY | FloppyDriveV1.STATE_FDDV1
            return
        if (byte == FloppyDriveV1.CMD_CFG):
            self.state = FloppyDriveV1.STATE_CFG1
            return
        elif (self.state == FloppyDriveV1.STATE_CFG1):
            self.state = FloppyDriveV1.STATE_CFG2
            self.dmaaddr = byte
            return
        elif (self.state == FloppyDriveV1.STATE_CFG2):
            self.state = FloppyDriveV1.STATE_READY
            self.dmaaddr = self.dmaaddr * 256 + byte
            return
        elif (byte == FloppyDriveV1.CMD_SETDRVA):
            self.active_drive = 'A'
            self.state = FloppyDriveV1.STATE_READY
            return
        elif (byte == FloppyDriveV1.CMD_SETDRVB):
            self.active_drive = 'B'
            self.state = FloppyDriveV1.STATE_READY
            return
        elif (byte == FloppyDriveV1.CMD_EJECT):
            if self.active_drive is None:
                self.state = FloppyDriveV1.STATE_DRIVE_FAILURE
                return
            if self.active_drive == 'A':
                (self.fileA_handle, self.fileA_name) = self.eject_disk(self.fileA_handle, self.fileA_name)
                return
            elif self.active_drive == 'B':
                (self.fileB_handle, self.fileB_name) = self.eject_disk(self.fileB_handle, self.fileB_name)
                return
            self.state = FloppyDriveV1.STATE_DRIVE_FAILURE
        elif byte == FloppyDriveV1.CMD_READSECT and self.state == FloppyDriveV1.STATE_READY:
            self.state = FloppyDriveV1.STATE_RD1
            return
        elif self.state == FloppyDriveV1.STATE_RD1:
            self.track = byte
            self.state = FloppyDriveV1.STATE_RD2
            return
        elif self.state == FloppyDriveV1.STATE_RD2:
            self.sector = byte
            if self.active_drive == 'A':
                (self.fileA_handle, self.fileA_name, self.state) = self.read_sector(self.fileA_handle, self.fileA_name)
                return
            elif self.active_drive == 'B':
                (self.fileB_handle, self.fileB_name, self.state) = self.read_sector(self.fileB_handle, self.fileB_name)
                return
        elif byte == FloppyDriveV1.CMD_WRITESECT and self.state == FloppyDriveV1.STATE_READY:
            self.state = FloppyDriveV1.STATE_WR1
            return
        elif self.state == FloppyDriveV1.STATE_WR1:
            self.track = byte
            self.state = FloppyDriveV1.STATE_WR2
            return
        elif self.state == FloppyDriveV1.STATE_WR2:
            self.sector = byte
            if self.active_drive == 'A':
                (self.fileA_handle, self.fileA_name, self.state) = self.write_sector(self.fileA_handle, self.fileA_name)
                return
            elif self.active_drive == 'B':
                (self.fileB_handle, self.fileB_name, self.state) = self.write_sector(self.fileB_handle, self.fileB_name)
                return
            self.state = FloppyDriveV1.STATE_DRIVE_FAILURE
            return
        
        self.setate = FloppyDriveV1.STATE_DRIVE_FAILURE
         