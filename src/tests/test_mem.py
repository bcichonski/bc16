import unittest
from bc32 import bc32_mem
from bc32 import bc32_env

class MemBusTests(unittest.TestCase):
    def test_value_should_be_stored(self):
        #given
        env = bc32_env.Environment()
        mem = bc32_mem.MemBus(env, 0x100)
        #when
        mem.write_byte(0xff, 0xa1)
        mem.write_byte(0x00, 0xff)
        #then
        self.assertEqual(mem.read_byte(0xff), 0xa1)
        self.assertEqual(mem.read_byte(0x00), 0xff)

if __name__ == '__main__':
    unittest.main()
