import unittest
import datetime
from bc16 import bc16_io
from bc16 import bc16_env

debug = False

class MockedIODevice(bc16_io.IODevice):
    IO_PORT = 0x1
    def __init__(self):
        self.io_port = MockedIODevice.IO_PORT
        self.io_queue = []
    def read_byte(self):
        if len(self.io_queue)>0:
            return self.io_queue.pop()
        return 0
    def write_byte(self, byte):
        self.io_queue.insert(0, byte)

class IOBusTests(unittest.TestCase):
    def test_device_should_work(self):
        #given
        io = bc16_io.IOBus()
        dev = MockedIODevice()
        io.add_device(dev)
        #when
        io.write_byte(MockedIODevice.IO_PORT, 0x1)
        io.write_byte(MockedIODevice.IO_PORT, 0xa1)
        io.write_byte(MockedIODevice.IO_PORT, 0xff)
        #then
        self.assertEqual(io.read_byte(MockedIODevice.IO_PORT), 0x1)
        self.assertEqual(io.read_byte(MockedIODevice.IO_PORT), 0xa1)
        self.assertEqual(io.read_byte(MockedIODevice.IO_PORT), 0xff)
        self.assertEqual(io.read_byte(MockedIODevice.IO_PORT), 0x0)

class MockedEnvironment(bc16_env.Environment):
    def __init__(self, debug):
        super().__init__(debug)
        self.data=[]
    def open_file_for_read(self,filename):
        pass
    def open_file_for_write(self,filename):
        self.data=[]
    def close_file(self, handle):
        pass
    def get_string(self, prompt):
        return "string"
    def read_byte(self, handle):
        if len(self.data)>0:
            return self.data.pop()
        return 0
    def write_byte(self, handle, byte):
        super().log("write byte {}".format(byte))
        self.data.append(byte)
    def get_data(self):
        return self.data
    def set_data(self, data):
        self.data = list(reversed(data))

class TapeRecorderTests(unittest.TestCase):
    def create_tape_recorder(self):
        env = MockedEnvironment(debug)
        tape_recorder = bc16_io.TapeRecorder(env)
        return tape_recorder

    def test_should_be_able_to_write_something(self):
        #given
        tr = self.create_tape_recorder()
        data = [1, 0, 1, 1, 0, 0, 1, 0]
        data_hex = 0xb2
        #when & then
        self.assertEqual(tr.read_byte(), bc16_io.TapeRecorder.READY)
        tr.write_byte(bc16_io.TapeRecorder.TAPE4WRITE | bc16_io.TapeRecorder.TX)
        self.assertEqual(tr.read_byte(),
            bc16_io.TapeRecorder.READY
            | bc16_io.TapeRecorder.TAPE4WRITE)
        tr.write_byte(bc16_io.TapeRecorder.MOVE | bc16_io.TapeRecorder.TX)
        self.assertEqual(tr.read_byte(),
            bc16_io.TapeRecorder.TAPE4WRITE
            | bc16_io.TapeRecorder.MOVE)
        for bit in data:
            tr.write_byte(bit | bc16_io.TapeRecorder.TX)
            state = tr.read_byte()
            self.assertEqual(state & bc16_io.TapeRecorder.TAPE4WRITE, bc16_io.TapeRecorder.TAPE4WRITE)
            self.assertEqual(state & bc16_io.TapeRecorder.MOVE, bc16_io.TapeRecorder.MOVE)
            self.assertNotEqual(state & bc16_io.TapeRecorder.TX, bc16_io.TapeRecorder.TX)
            self.assertNotEqual(state & bc16_io.TapeRecorder.ERROR, bc16_io.TapeRecorder.ERROR)
        tr.write_byte(bc16_io.TapeRecorder.READY | bc16_io.TapeRecorder.TX)
        self.assertEqual(tr.read_byte() & bc16_io.TapeRecorder.READY, bc16_io.TapeRecorder.READY)
        written_data = [int(bool(x & bc16_io.TapeRecorder.HALF_BYTE == bc16_io.TapeRecorder.HALF_BYTE))
            for x in tr.env.get_data()]
        self.assertEqual(data, written_data)
        out = 0
        for bit in written_data:
            out = (out << 1) | bit
        self.assertEqual(data_hex, out)
    def test_should_be_able_to_read_something(self):
        #given
        tr = self.create_tape_recorder()
        data_bin = [1 ,0 ,1, 1, 0, 0, 1, 0]
        data = [129, 16, 178, 253, 110, 96, 201, 66]
        data_hex = 0xb2
        tr.env.set_data(data)
        #when & then
        self.assertEqual(tr.read_byte(), bc16_io.TapeRecorder.READY)
        tr.write_byte(bc16_io.TapeRecorder.TAPE4READ | bc16_io.TapeRecorder.TX)
        self.assertEqual(tr.read_byte(),
            bc16_io.TapeRecorder.READY
            | bc16_io.TapeRecorder.TAPE4READ)
        tr.write_byte(bc16_io.TapeRecorder.MOVE | bc16_io.TapeRecorder.TX)
        read_data = []
        for bit in data:
            state = tr.read_byte()
            bit = int(bool(state & bc16_io.TapeRecorder.DX==bc16_io.TapeRecorder.DX))
            read_data.append(bit)
            self.assertEqual(state & bc16_io.TapeRecorder.TAPE4READ, bc16_io.TapeRecorder.TAPE4READ)
            self.assertEqual(state & bc16_io.TapeRecorder.MOVE, bc16_io.TapeRecorder.MOVE)
            self.assertEqual(state & bc16_io.TapeRecorder.TX, bc16_io.TapeRecorder.TX)
            self.assertNotEqual(state & bc16_io.TapeRecorder.ERROR, bc16_io.TapeRecorder.ERROR)
        tr.write_byte(bc16_io.TapeRecorder.READY | bc16_io.TapeRecorder.TX)
        self.assertEqual(tr.read_byte() & bc16_io.TapeRecorder.READY, bc16_io.TapeRecorder.READY)
        self.assertEqual(data_bin, read_data)
        out = 0
        for bit in read_data:
            out = (out << 1) | bit
        self.assertEqual(data_hex, out)

class ClockTests(unittest.TestCase):
    def create_clock(self):
        env = MockedEnvironment(debug)
        io = bc16_io.IOBus()
        dev = bc16_io.Clock(env)
        io.add_device(dev)

        return (io, dev)

    def test_should_get_time(self):
        #given
        (io, dev) = self.create_clock()

        #when
        self.assertEqual(dev.state, bc16_io.Clock.STATE_READY)
        io.write_byte(bc16_io.Clock.DEFAULT_IO_PORT, bc16_io.Clock.COMMAND_GETTIME)

        hour = io.read_byte(bc16_io.Clock.DEFAULT_IO_PORT)
        minute = io.read_byte(bc16_io.Clock.DEFAULT_IO_PORT)
        second = io.read_byte(bc16_io.Clock.DEFAULT_IO_PORT)

        #then
        self.assertEqual(dev.state, bc16_io.Clock.STATE_READY)
        self.assertIn(hour, range(0, 59))
        self.assertIn(minute, range(0, 59))
        self.assertIn(second, range(0, 59))

    def test_should_get_date(self):
        #given
        (io, dev) = self.create_clock()
        today = datetime.datetime.now()

        #when
        self.assertEqual(dev.state, bc16_io.Clock.STATE_READY)
        io.write_byte(bc16_io.Clock.DEFAULT_IO_PORT, bc16_io.Clock.COMMAND_GETDATE)
        
        year = io.read_byte(bc16_io.Clock.DEFAULT_IO_PORT)
        month = io.read_byte(bc16_io.Clock.DEFAULT_IO_PORT)
        day = io.read_byte(bc16_io.Clock.DEFAULT_IO_PORT)

        #then
        self.assertEqual(dev.state, bc16_io.Clock.STATE_READY)
        self.assertEqual(year, today.year % 2000)
        self.assertEqual(month, today.month)
        self.assertEqual(day, today.day)

class RandomGeneratorTests(unittest.TestCase):
    def create(self):
        env = MockedEnvironment(debug)
        io = bc16_io.IOBus()
        dev = bc16_io.RandomGenerator(env)
        io.add_device(dev)

        return (io, dev)

    def test_should_get_time(self):
        #given
        (io, dev) = self.create()

        #when
        val = io.read_byte(bc16_io.RandomGenerator.DEFAULT_IO_PORT)

        #then
        self.assertIn(val, range(0x00, 0xff))

if __name__ == '__main__':
    unittest.main()
