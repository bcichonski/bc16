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

class FlagsRegisterTests(unittest.TestCase):
    def test_set_flags(self):
        #given
        register = bc16.FlagsRegister(0xff)
        flags = register.flags
        #when
        for flag in flags:
            register.set_flag(flag, True)
        #then
        for flag in flags:
            self.assertTrue(register.get_flag(flag))
        self.assertEqual(0xf, register.get())

if __name__ == '__main__':
    unittest.main()
