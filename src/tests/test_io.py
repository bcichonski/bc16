import unittest
import datetime
from bc64 import bc64_io
from bc64 import bc64_env

debug = False

class MockedIODevice(bc64_io.IODevice):
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
        io = bc64_io.IOBus()
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

class MockedEnvironment(bc64_env.Environment):
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
            return chr(self.data.pop())
        return 0
    def write_byte(self, handle, byte):
        self.data.append(byte)
    def get_data(self):
        return self.data
    def set_data(self, data):
        self.data = list(reversed(data))

class TapeRecorderTests(unittest.TestCase):
    def create_tape_recorder(self):
        env = MockedEnvironment(debug)
        tape_recorder = bc64_io.TapeRecorder(env)
        return tape_recorder

    def test_should_be_able_to_write_something(self):
        #given
        tr = self.create_tape_recorder()
        data = [1, 0, 1, 1, 0, 0, 1, 0]
        data_hex = 0xb2
        #when & then
        self.assertEqual(tr.read_byte(), bc64_io.TapeRecorder.READY)
        tr.write_byte(bc64_io.TapeRecorder.TAPE4WRITE | bc64_io.TapeRecorder.TX)
        self.assertEqual(tr.read_byte(),
            bc64_io.TapeRecorder.READY
            | bc64_io.TapeRecorder.TAPE4WRITE)
        tr.write_byte(bc64_io.TapeRecorder.MOVE | bc64_io.TapeRecorder.TX)
        self.assertEqual(tr.read_byte(),
            bc64_io.TapeRecorder.TAPE4WRITE
            | bc64_io.TapeRecorder.MOVE)
        for bit in data:
            tr.write_byte(bit | bc64_io.TapeRecorder.TX)
            state = tr.read_byte()
            self.assertEqual(state & bc64_io.TapeRecorder.TAPE4WRITE, bc64_io.TapeRecorder.TAPE4WRITE)
            self.assertEqual(state & bc64_io.TapeRecorder.MOVE, bc64_io.TapeRecorder.MOVE)
            self.assertNotEqual(state & bc64_io.TapeRecorder.TX, bc64_io.TapeRecorder.TX)
            self.assertNotEqual(state & bc64_io.TapeRecorder.ERROR, bc64_io.TapeRecorder.ERROR)
        tr.write_byte(bc64_io.TapeRecorder.READY | bc64_io.TapeRecorder.TX)
        self.assertEqual(tr.read_byte() & bc64_io.TapeRecorder.READY, bc64_io.TapeRecorder.READY)
        written_data = [int(bool(x))
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
        data = [129, 0, 178, 253, 0, 0, 201, 0]
        data_hex = 0xb2
        tr.env.set_data(data)
        #when & then
        self.assertEqual(tr.read_byte(), bc64_io.TapeRecorder.READY)
        tr.write_byte(bc64_io.TapeRecorder.TAPE4READ | bc64_io.TapeRecorder.TX)
        self.assertEqual(tr.read_byte(),
            bc64_io.TapeRecorder.READY
            | bc64_io.TapeRecorder.TAPE4READ)
        tr.write_byte(bc64_io.TapeRecorder.MOVE | bc64_io.TapeRecorder.TX)
        read_data = []
        for bit in data:
            state = tr.read_byte()
            bit = int(bool(state & bc64_io.TapeRecorder.DX==bc64_io.TapeRecorder.DX))
            read_data.append(bit)
            self.assertEqual(state & bc64_io.TapeRecorder.TAPE4READ, bc64_io.TapeRecorder.TAPE4READ)
            self.assertEqual(state & bc64_io.TapeRecorder.MOVE, bc64_io.TapeRecorder.MOVE)
            self.assertEqual(state & bc64_io.TapeRecorder.TX, bc64_io.TapeRecorder.TX)
            self.assertNotEqual(state & bc64_io.TapeRecorder.ERROR, bc64_io.TapeRecorder.ERROR)
        tr.write_byte(bc64_io.TapeRecorder.READY | bc64_io.TapeRecorder.TX)
        self.assertEqual(tr.read_byte() & bc64_io.TapeRecorder.READY, bc64_io.TapeRecorder.READY)
        self.assertEqual(data_bin, read_data)
        out = 0
        for bit in read_data:
            out = (out << 1) | bit
        self.assertEqual(data_hex, out)

class ClockTests(unittest.TestCase):
    def create_clock(self):
        env = MockedEnvironment(debug)
        io = bc64_io.IOBus()
        dev = bc64_io.Clock(env)
        io.add_device(dev)

        return (io, dev)

    def test_should_get_time(self):
        #given
        (io, dev) = self.create_clock()

        #when
        self.assertEqual(dev.state, bc64_io.Clock.STATE_READY)
        io.write_byte(bc64_io.Clock.DEFAULT_IO_PORT, bc64_io.Clock.COMMAND_GETTIME)

        hour = io.read_byte(bc64_io.Clock.DEFAULT_IO_PORT)
        minute = io.read_byte(bc64_io.Clock.DEFAULT_IO_PORT)
        second = io.read_byte(bc64_io.Clock.DEFAULT_IO_PORT)

        #then
        self.assertEqual(dev.state, bc64_io.Clock.STATE_READY)
        self.assertIn(hour, range(0, 59))
        self.assertIn(minute, range(0, 59))
        self.assertIn(second, range(0, 59))

    def test_should_get_date(self):
        #given
        (io, dev) = self.create_clock()
        today = datetime.datetime.now()

        #when
        self.assertEqual(dev.state, bc64_io.Clock.STATE_READY)
        io.write_byte(bc64_io.Clock.DEFAULT_IO_PORT, bc64_io.Clock.COMMAND_GETDATE)
        
        year = io.read_byte(bc64_io.Clock.DEFAULT_IO_PORT)
        month = io.read_byte(bc64_io.Clock.DEFAULT_IO_PORT)
        day = io.read_byte(bc64_io.Clock.DEFAULT_IO_PORT)

        #then
        self.assertEqual(dev.state, bc64_io.Clock.STATE_READY)
        self.assertEqual(year, today.year % 2000)
        self.assertEqual(month, today.month)
        self.assertEqual(day, today.day)

class RandomGeneratorTests(unittest.TestCase):
    def create(self):
        env = MockedEnvironment(debug)
        io = bc64_io.IOBus()
        dev = bc64_io.RandomGenerator(env)
        io.add_device(dev)

        return (io, dev)

    def test_should_get_time(self):
        #given
        (io, dev) = self.create()

        #when
        val = io.read_byte(bc64_io.RandomGenerator.DEFAULT_IO_PORT)

        #then
        self.assertIn(val, range(0x00, 0xff))

if __name__ == '__main__':
    unittest.main()
