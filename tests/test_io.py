import unittest
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
if __name__ == '__main__':
    unittest.main()
