import unittest
from bc16 import bc16_io
from bc16 import bc16_env

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
    def open_file_to_read(self,filename):
        pass
    def open_file_to_write(self,filename):
        self.data=[]
    def close_file(self, handle):
        pass
    def get_string(self, prompt):
        return "string"
    def read_byte(self):
        if len(self.data)>0:
            return self.data.pop()
        return 0
    def write_byte(self, byte):
        self.data.insert(0, byte)
    def get_data(self):
        return self.data

class TapeRecorderTests(unittest.TestCase):
    def create_tape_recorder(self):
        env = MockedEnvironment()
        tape_recorder = bc16_io.TapeRecorder(env)
        return tape_recorder
        
    def test_should_be_able_to_write_something(self):
        #given
        tr = self.create_tape_recorder()
        #when & then
        self.assertEqual(tr.read_byte(), bc16_io.TapeRecorder.READY)
        tr.write_byte(bc16_io.TapeRecorder.TAPE4WRITE)
        self.assertEqual(tr.read_byte(), 
            bc16_io.TapeRecorder.READY 
            | bc16_io.TapeRecorder.TAPE4WRITE)
        
if __name__ == '__main__':
    unittest.main()
