import unittest
from bc16 import bc16

class RegistersTests(unittest.TestCase):
    def test_value_setter_should_wrap(self):
        #given
        register = bc16.Register(0xff)
        #when
        register.set(0xffab)
        #then
        self.assertEqual(register.get(), 0xab)
    def test_value_increas_should_wrap(self):
        #given
        register = bc16.Register(0xff)
        #when
        register.set(0x0)
        register.inc(0xffab)
        #then
        self.assertEqual(register.get(), 0xab)

if __name__ == '__main__':
    unittest.main()
