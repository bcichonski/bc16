import unittest
from bc16 import bc16

class MockedIODevice(bc16.IODevice):
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
        io = bc16.IOBus()
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

if __name__ == '__main__':
    unittest.main()
