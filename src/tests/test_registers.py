import unittest
from bc64 import bc8183_cpu

class RegistersTests(unittest.TestCase):
    def test_value_setter_should_wrap(self):
        #given
        register = bc8183_cpu.Register(0xff)
        #when
        register.set(0xffab)
        #then
        self.assertEqual(register.get(), 0xab)
    def test_value_increas_should_wrap(self):
        #given
        register = bc8183_cpu.Register(0xff)
        #when
        register.set(0x0)
        register.inc(0xffab)
        #then
        self.assertEqual(register.get(), 0xab)
    def test_negative_values_should_wrap(self):
        #given
        register = bc8183_cpu.Register(0xff)
        #when
        register.set(-1)
        #then
        self.assertEqual(register.get(), 0xff)

class FlagsRegisterTests(unittest.TestCase):
    def test_set_flags(self):
        #given
        register = bc8183_cpu.FlagsRegister(0xff)
        flags = register.flags
        #when
        for flag in flags:
            register.set_flag(flag, True)
        #then
        for flag in flags:
            self.assertTrue(register.get_flag(flag))
        self.assertEqual(0xff, register.get())

if __name__ == '__main__':
    unittest.main()
