"""CPU control-flow, stack, memory-move and I/O opcode tests (plan #48, T5).

Conventions used by the CPU (see docs/01-emulator.md):

* every program is a raw byte list loaded at 0x0000 into a 0x400 byte memory;
  the stack starts at 0x03ff (SS=0x03, SI=0xff) and grows down;
* ``jmr`` target = address of the instruction + offset (sign-magnitude, 7 bit);
* ``clr`` target = address of the instruction + offset + 2 (sign-magnitude, 15 bit);
* ``jrx`` address form target = instruction address + offset + 3 (instruction is
  4 bytes), register form target = instruction address + offset + 1 (2 bytes);
  offset is sign-magnitude 15 bit;
* the negation bit of ``jrx`` is assembled into the high nibble of the test byte
  (``TEST_NZ = 0x4``) but the CPU reads it from the opcode nibble: negated
  ``jrx`` never negates (issue #4, item 2).

The CPU debug trace is off, so nothing is printed and no cpudebug.log is created.
"""
import contextlib
import io
import unittest

from bc64 import bc8183_cpu
from bc64 import bc64_env
from bc64 import bc64_io
from bc64 import bc64_mem

MEMSIZE = 0x400
STACK_TOP = MEMSIZE - 1
STEP_LIMIT = 1000

CPU = bc8183_cpu.Bc8183
FLAG_Z, FLAG_C, FLAG_N, FLAG_O = 0, 1, 2, 3
FLAG_NAMES = {FLAG_Z: 'z', FLAG_C: 'c', FLAG_N: 'n', FLAG_O: 'o'}
KIL = 0xff


class RecordingDevice:
    """Mock I/O device: serves queued bytes and records written bytes."""

    def __init__(self, io_port, to_read=()):
        self.io_port = io_port
        self.to_read = list(to_read)
        self.written = []

    def read_byte(self):
        return self.to_read.pop(0)

    def write_byte(self, val):
        self.written.append(val)


def make_cpu(code, iobus=None, at=0):
    env = bc64_env.Environment(False)
    mem = bc64_mem.MemBus(env, MEMSIZE)
    for i, b in enumerate(code):
        mem.write_byte(at + i, b)
    return CPU(mem, iobus, False)


def run_cpu(cpu):
    """Run until KIL; fails instead of hanging on an endless loop."""
    cpu.inc_pc(0)
    steps = 0
    while not cpu.kill:
        steps += 1
        if steps > STEP_LIMIT:
            raise AssertionError("program did not reach KIL")
        cpu.run_next_opcode()
    return cpu


def set_flags(cpu, **flags):
    """Set the four flags explicitly, e.g. set_flags(cpu, z=1, c=0)."""
    for flag, name in FLAG_NAMES.items():
        cpu.f.set_flag(flag, int(flags.get(name, 0)))


class ControlTestBase(unittest.TestCase):
    def build(self, code, flags=None, iobus=None, **regs):
        """Flags are given as flags={...} or as the z/c/n/o keywords, registers by attribute name."""
        flags = dict(flags or {})
        for name in FLAG_NAMES.values():
            if name in regs:
                flags[name] = regs.pop(name)
        cpu = make_cpu(code, iobus)
        set_flags(cpu, **flags)
        for name, val in regs.items():
            getattr(cpu, name).set(val)
        return cpu

    def run_code(self, code, flags=None, iobus=None, **regs):
        return run_cpu(self.build(code, flags, iobus, **regs))


class NopKilTests(ControlTestBase):
    def test_NOP_advances_pc_by_one_and_changes_nothing(self):
        cpu = self.run_code([0x00, 0x00, 0x00, KIL], z=1)
        self.assertEqual(cpu.pc.get(), 3)
        self.assertEqual(cpu.a.get(), 0)
        self.assertTrue(cpu.f.get_flag(FLAG_Z))

    def test_KIL_stops_cpu_and_leaves_pc_on_it(self):
        cpu = self.run_code([0x00, KIL, 0x11, 0x55])
        self.assertTrue(cpu.kill)
        self.assertEqual(cpu.pc.get(), 1)
        self.assertEqual(cpu.a.get(), 0)


class MovTests(ControlTestBase):
    def test_MOV_imm_to_each_register(self):
        regs = {0x1: 'a', 0x4: 'ci', 0x5: 'di', 0x8: 'cs', 0x9: 'ds', 0xC: 'si', 0xD: 'ss'}
        for regno, name in regs.items():
            with self.subTest(register=name):
                cpu = self.run_code([0x10 | regno, 0x5a, KIL])
                self.assertEqual(getattr(cpu, name).get(), 0x5a)
                self.assertEqual(cpu.pc.get(), 2)

    def test_MOV_imm_to_A_sets_zero_and_negative_flags(self):
        cpu = self.run_code([0x11, 0x00, KIL], z=0, n=1)
        self.assertTrue(cpu.f.get_flag(FLAG_Z))
        self.assertFalse(cpu.f.get_flag(FLAG_N))
        cpu = self.run_code([0x11, 0x80, KIL], z=1)
        self.assertFalse(cpu.f.get_flag(FLAG_Z))
        self.assertTrue(cpu.f.get_flag(FLAG_N))

    def test_MOV_imm_to_other_register_keeps_flags(self):
        cpu = self.run_code([0x14, 0x00, KIL], z=0, n=1)
        self.assertFalse(cpu.f.get_flag(FLAG_Z))
        self.assertTrue(cpu.f.get_flag(FLAG_N))

    def test_MOV_reg_copies_source_to_destination(self):
        # 0x2d, 0x s d: low nibble of the first byte is the destination, high nibble of the second the source
        cpu = self.run_code([0x25, 0x40, KIL], ci=0x37)       # MOV DI, CI
        self.assertEqual(cpu.di.get(), 0x37)
        self.assertEqual(cpu.ci.get(), 0x37)
        self.assertEqual(cpu.pc.get(), 2)

    def test_MOV_reg_to_A_sets_flags(self):
        cpu = self.run_code([0x21, 0x40, KIL], ci=0x00, z=0)  # MOV A, CI
        self.assertTrue(cpu.f.get_flag(FLAG_Z))
        cpu = self.run_code([0x21, 0x40, KIL], ci=0x90, z=1)
        self.assertFalse(cpu.f.get_flag(FLAG_Z))
        self.assertTrue(cpu.f.get_flag(FLAG_N))

    # address pair: (register number used in the encoding, high register, low register)
    PAIRS = [
        ('csci', 0x4, 'cs', 'ci'),
        ('csci_via_cs', 0x8, 'cs', 'ci'),
        ('dsdi', 0x5, 'ds', 'di'),
        ('dsdi_via_ds', 0x9, 'ds', 'di'),
        ('sssi', 0xC, 'ss', 'si'),
        ('sssi_via_ss', 0xD, 'ss', 'si'),
    ]

    def test_MOV_reg_mem_loads_from_each_address_pair(self):
        for label, regno, hi_name, lo_name in self.PAIRS:
            with self.subTest(pair=label):
                cpu = self.build([0x31, regno << 4, KIL], **{hi_name: 0x02, lo_name: 0x10})
                cpu.membus.write_byte(0x0210, 0xc3)
                run_cpu(cpu)
                self.assertEqual(cpu.a.get(), 0xc3)
                self.assertEqual(cpu.pc.get(), 2)

    def test_MOV_reg_mem_loads_from_A_F_pair(self):
        # the pair A:F uses the flags register as the low byte
        cpu = self.build([0x34, 0x10, KIL], a=0x02)           # MOV CI, (A:F)
        addr = (0x02 << 8) | cpu.f.get()
        cpu.membus.write_byte(addr, 0x6e)
        run_cpu(cpu)
        self.assertEqual(cpu.ci.get(), 0x6e)

    def test_MOV_reg_mem_into_A_sets_flags(self):
        cpu = self.build([0x31, 0x40, KIL], cs=0x01, ci=0x00, z=0)
        cpu.membus.write_byte(0x0100, 0x00)
        run_cpu(cpu)
        self.assertTrue(cpu.f.get_flag(FLAG_Z))

    def test_MOV_mem_reg_stores_through_each_address_pair(self):
        for label, regno, hi_name, lo_name in self.PAIRS:
            with self.subTest(pair=label):
                cpu = self.run_code([0x40 | regno, 0x10, KIL], a=0x9b, **{hi_name: 0x02, lo_name: 0x20})
                self.assertEqual(cpu.membus.read_byte(0x0220), 0x9b)
                self.assertEqual(cpu.pc.get(), 2)

    def test_MOV_mem_reg_stores_through_A_F_pair(self):
        cpu = self.build([0x41, 0x40, KIL], a=0x02, ci=0x4d)   # MOV (A:F), CI
        addr = (0x02 << 8) | cpu.f.get()
        run_cpu(cpu)
        self.assertEqual(cpu.membus.read_byte(addr), 0x4d)

    def test_MOV_mem_reg_does_not_touch_flags(self):
        cpu = self.run_code([0x44, 0x10, KIL], a=0x00, cs=0x01, ci=0x00, z=0, n=1)
        self.assertFalse(cpu.f.get_flag(FLAG_Z))
        self.assertTrue(cpu.f.get_flag(FLAG_N))

    def test_MOV_with_register_that_is_not_an_address_pair_kills_cpu(self):
        # pinned (D7): get_addr() returns None for e.g. PC (0xF); the CPU stops instead of faulting
        cpu = self.run_code([0x31, 0xf0, 0x11, 0x44, KIL], a=0x77)  # MOV A, (PC pair)
        self.assertTrue(cpu.kill)
        self.assertEqual(cpu.a.get(), 0x77)
        self.assertEqual(cpu.pc.get(), 2)
        cpu = self.run_code([0x4f, 0x10, 0x11, 0x44, KIL])           # MOV (PC pair), A
        self.assertTrue(cpu.kill)
        self.assertEqual(cpu.pc.get(), 2)


class JmpTests(ControlTestBase):
    # JMP at 0, "not taken" falls into MOV DI,0x11; "taken" lands on MOV DI,0x22 at 0x10
    TARGET = 0x10

    def program(self, jmp_bytes):
        code = list(jmp_bytes) + [0x15, 0x11, KIL]
        code += [0x00] * (self.TARGET - len(code))
        code += [0x15, 0x22, KIL]
        return code

    def check_all_conditions(self, make_jmp, expected_len, **regs):
        for flag, name in FLAG_NAMES.items():
            for neg in (False, True):
                for flag_set in (False, True):
                    with self.subTest(test=('n' if neg else '') + name, flag_set=flag_set):
                        opcode = 0x60 | flag | (0x4 if neg else 0)
                        cpu = self.run_code(self.program(make_jmp(opcode)), flags={name: flag_set}, **regs)
                        taken = flag_set != neg
                        if taken:
                            self.assertEqual(cpu.di.get(), 0x22)
                            self.assertEqual(cpu.pc.get(), self.TARGET + 2)
                        else:
                            self.assertEqual(cpu.di.get(), 0x11)
                            self.assertEqual(cpu.pc.get(), expected_len + 2)

    def test_JMP_short_each_flag_negated_and_not(self):
        # short form (bit 3): target = CS:imm8
        self.check_all_conditions(lambda op: [op | 0x8, self.TARGET], 2)

    def test_JMP_short_uses_cs_as_high_byte(self):
        code = [0x68, 0x40, KIL]
        cpu = self.build(code, flags={'z': 1}, cs=0x02)
        cpu.membus.write_byte(0x0240, 0x15)
        cpu.membus.write_byte(0x0241, 0x33)
        cpu.membus.write_byte(0x0242, KIL)
        run_cpu(cpu)
        self.assertEqual(cpu.di.get(), 0x33)

    def test_JMP_register_form_each_flag_negated_and_not(self):
        # register form: target = address pair named in the low nibble of the second byte (CS:CI)
        self.check_all_conditions(lambda op: [op, 0x04], 2, ci=self.TARGET)

    def test_JMP_register_form_with_other_pairs(self):
        for regno, hi_name, lo_name in [(0x5, 'ds', 'di'), (0xC, 'ss', 'si')]:
            with self.subTest(pair=hi_name + lo_name):
                code = self.program([0x60, regno])
                regs = {hi_name: 0x00, lo_name: self.TARGET}
                cpu = self.run_code(code, flags={'z': 1}, **regs)
                self.assertEqual(cpu.pc.get(), self.TARGET + 2)

    def test_JMP_not_taken_and_taken_in_sequence(self):
        code = [
            0x5d,                  # 0x00: INC A          (Z cleared)
            0x6c, 0x05,            # 0x01: JMP NZ, 0x05   (taken)
            KIL,                   # 0x03
            0x00,                  # 0x04
            0x61, 0x03,            # 0x05: JMP C, 0x03    (carry clear: not taken)
            0x15, 0x44,            # 0x07: MOV DI, 0x44
            0x68, 0x03,            # 0x09: JMP Z, 0x03    (zero clear: not taken)
            KIL,                   # 0x0b
        ]
        cpu = self.run_code(code)
        self.assertEqual(cpu.di.get(), 0x44)
        self.assertEqual(cpu.pc.get(), 0x0b)


class JmrTests(ControlTestBase):
    def test_JMR_forward_immediate_each_flag_negated_and_not(self):
        for flag, name in FLAG_NAMES.items():
            for neg in (False, True):
                for flag_set in (False, True):
                    with self.subTest(test=('n' if neg else '') + name, flag_set=flag_set):
                        opcode = 0x70 | flag | (0x4 if neg else 0)
                        code = [opcode, 0x10, 0x15, 0x11, KIL] + [0x00] * 11 + [0x15, 0x22, KIL]
                        cpu = self.run_code(code, flags={name: flag_set})
                        if flag_set != neg:
                            self.assertEqual((cpu.di.get(), cpu.pc.get()), (0x22, 0x12))
                        else:
                            self.assertEqual((cpu.di.get(), cpu.pc.get()), (0x11, 0x04))

    def test_JMR_target_is_instruction_address_plus_offset(self):
        code = [0x00, 0x00, 0x70, 0x05, KIL, 0x00, 0x00, 0x15, 0x66, KIL]
        cpu = self.run_code(code, z=1)
        self.assertEqual(cpu.pc.get(), 0x09)
        self.assertEqual(cpu.di.get(), 0x66)

    def test_JMR_backward_immediate_uses_sign_magnitude(self):
        code = [
            0x70, 0x10,            # 0x00: JMR Z, +0x10
            KIL,                   # 0x02
            0x00, 0x00, 0x00, 0x00, 0x00,
            0x15, 0x22,            # 0x08: MOV DI, 0x22
            KIL,                   # 0x0a
            0x00, 0x00, 0x00, 0x00, 0x00,
            0x70, 0x88,            # 0x10: JMR Z, -8   (0x80 | 8)
            KIL,                   # 0x12
        ]
        cpu = self.run_code(code, z=1)
        self.assertEqual(cpu.di.get(), 0x22)
        self.assertEqual(cpu.pc.get(), 0x0a)

    def test_JMR_register_form_forward(self):
        code = [0x78, 0x40, KIL, 0x00, 0x00, 0x00, 0x15, 0x66, KIL]    # JMR Z, (CI) with CI=6
        cpu = self.run_code(code, z=1, ci=0x06)
        self.assertEqual((cpu.di.get(), cpu.pc.get()), (0x66, 0x08))

    def test_JMR_register_form_backward_sign_magnitude(self):
        code = [
            0x70, 0x0a,            # 0x00: JMR Z, +0x0a
            KIL,                   # 0x02
            0x00, 0x00, 0x00,
            0x15, 0x66, KIL,       # 0x06: MOV DI, 0x66 ; KIL
            0x00,
            0x78, 0x40,            # 0x0a: JMR Z, (CI) with CI = 0x84 = -4
            KIL,
        ]
        cpu = self.run_code(code, z=1, ci=0x84)
        self.assertEqual((cpu.di.get(), cpu.pc.get()), (0x66, 0x08))

    def test_JMR_register_form_each_flag_negated_and_not(self):
        for flag, name in FLAG_NAMES.items():
            for neg in (False, True):
                for flag_set in (False, True):
                    with self.subTest(test=('n' if neg else '') + name, flag_set=flag_set):
                        opcode = 0x78 | flag | (0x4 if neg else 0)
                        code = [opcode, 0x40, 0x15, 0x11, KIL] + [0x00] * 11 + [0x15, 0x22, KIL]
                        cpu = self.run_code(code, flags={name: flag_set}, ci=0x10)
                        if flag_set != neg:
                            self.assertEqual((cpu.di.get(), cpu.pc.get()), (0x22, 0x12))
                        else:
                            self.assertEqual((cpu.di.get(), cpu.pc.get()), (0x11, 0x04))


class JrxTests(ControlTestBase):
    """jrx: EXT opcodes 0xe1 (address, 4 bytes) and 0xe2 (register, 2 bytes)."""

    @staticmethod
    def address_form(test, offset):
        # as assembled: e1, (test << 4), offset hi, offset lo
        return [0xe1, test << 4, (offset >> 8) & 0xff, offset & 0xff]

    @staticmethod
    def register_form(test, regno):
        # as assembled: e2, ((test | 8) << 4) | regno
        return [0xe2, ((test | 0x8) << 4) | regno]

    def test_JRX_address_form_non_negated_each_flag(self):
        for flag, name in FLAG_NAMES.items():
            for flag_set in (False, True):
                with self.subTest(test=name, flag_set=flag_set):
                    # target = 0 + 0x0c + 3 = 0x0f
                    code = self.address_form(flag, 0x000c) + [0x15, 0x11, KIL] + [0x00] * 8 + [0x15, 0x22, KIL]
                    cpu = self.run_code(code, flags={name: flag_set})
                    if flag_set:
                        self.assertEqual((cpu.di.get(), cpu.pc.get()), (0x22, 0x11))
                    else:
                        self.assertEqual((cpu.di.get(), cpu.pc.get()), (0x11, 0x06))

    def test_JRX_address_form_backward_sign_magnitude(self):
        code = [0x00] * 0x20
        code[0:4] = self.address_form(FLAG_Z, 0x000d)                 # 0x00 + 3 + 0x0d = 0x10
        code[4] = KIL
        code[0x0d:0x10] = [0x15, 0x22, KIL]                           # MOV DI,0x22 ; KIL
        code[0x10:0x14] = self.address_form(FLAG_Z, 0x8006)           # 0x10 + 3 - 6 = 0x0d
        code[0x14] = KIL
        cpu = self.run_code(code, z=1)
        self.assertEqual(cpu.di.get(), 0x22)
        self.assertEqual(cpu.pc.get(), 0x0f)

    def test_JRX_register_form_non_negated_each_flag(self):
        for flag, name in FLAG_NAMES.items():
            for flag_set in (False, True):
                with self.subTest(test=name, flag_set=flag_set):
                    # CS:CI = 0x000c, register form target = 0 + 0x0c + 1 = 0x0d
                    code = self.register_form(flag, 0x8) + [0x15, 0x11, KIL] + [0x00] * 8 + [0x15, 0x22, KIL]
                    cpu = self.run_code(code, flags={name: flag_set}, ci=0x0c)
                    if flag_set:
                        self.assertEqual((cpu.di.get(), cpu.pc.get()), (0x22, 0x0f))
                    else:
                        self.assertEqual((cpu.di.get(), cpu.pc.get()), (0x11, 0x04))

    def test_JRX_register_form_uses_named_pair_and_backward_offset(self):
        code = [0x00] * 0x20
        code[0:2] = self.register_form(FLAG_Z, 0x5)                   # DS:DI = 0x000f -> 0x00 + 1 + 0x0f = 0x10
        code[2] = KIL
        code[0x0d:0x10] = [0x15, 0x22, KIL]
        code[0x10:0x12] = self.register_form(FLAG_Z, 0x9)             # DS:DI = 0x8004 -> 0x10 + 1 - 4 = 0x0d
        code[0x12] = KIL
        cpu = self.build(code, z=1, di=0x0f)
        cpu.inc_pc(0)
        cpu.run_next_opcode()
        self.assertEqual(cpu.pc.get(), 0x10)
        cpu.ds.set(0x80)
        cpu.di.set(0x04)
        cpu.run_next_opcode()
        self.assertEqual(cpu.pc.get(), 0x0d)

    def test_JRX_unknown_ext_opcode_is_not_handled_pinned(self):
        # pinned (D7): EXT sub-opcodes other than 1 and 2 leave 'testcode' unset
        cpu = self.build([0xe3, 0x00, KIL])
        cpu.inc_pc(0)
        with contextlib.redirect_stdout(io.StringIO()):   # the CPU dumps its stack on an exception
            with self.assertRaises(UnboundLocalError):
                cpu.run_next_opcode()

    # --- negated jrx: decided behaviour (#4 item 2), currently never negates ----------------

    @unittest.expectedFailure   # issue #4: negated jrx never negates
    def test_JRX_address_form_negated_jumps_when_flag_clear(self):
        for flag, name in FLAG_NAMES.items():
            code = self.address_form(flag | 0x4, 0x000c) + [0x15, 0x11, KIL] + [0x00] * 8 + [0x15, 0x22, KIL]
            cpu = self.run_code(code, flags={name: False})
            self.assertEqual(cpu.di.get(), 0x22, 'jrx n' + name + ' with flag clear')
            cpu = self.run_code(code, flags={name: True})
            self.assertEqual(cpu.di.get(), 0x11, 'jrx n' + name + ' with flag set')

    @unittest.expectedFailure   # issue #4: negated jrx never negates
    def test_JRX_register_form_negated_jumps_when_flag_clear(self):
        for flag, name in FLAG_NAMES.items():
            code = self.register_form(flag | 0x4, 0x8) + [0x15, 0x11, KIL] + [0x00] * 8 + [0x15, 0x22, KIL]
            cpu = self.run_code(code, flags={name: False}, ci=0x0c)
            self.assertEqual(cpu.di.get(), 0x22, 'jrx n' + name + ' with flag clear')
            cpu = self.run_code(code, flags={name: True}, ci=0x0c)
            self.assertEqual(cpu.di.get(), 0x11, 'jrx n' + name + ' with flag set')


class StackTests(ControlTestBase):
    def test_PSH_writes_tag_and_value_and_moves_stack_pointer(self):
        cpu = self.run_code([0x81, KIL], a=0x42)
        self.assertEqual(cpu.membus.read_byte(STACK_TOP), 0x42)
        self.assertEqual(cpu.membus.read_byte(STACK_TOP - 1), CPU.STACKFRAME_TYPE_PUSH)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x03, 0xfd))
        self.assertEqual(cpu.pc.get(), 1)

    def test_POP_restores_value_and_stack_pointer(self):
        cpu = self.run_code([0x81, 0x94, KIL], a=0x42)           # PSH A ; POP CI
        self.assertEqual(cpu.ci.get(), 0x42)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x03, 0xff))
        self.assertEqual(cpu.pc.get(), 2)

    def test_PSH_POP_is_last_in_first_out(self):
        cpu = self.run_code([0x81, 0x84, 0x85, 0x91, 0x94, 0x95, KIL], a=0x01, ci=0x02, di=0x03)
        # PSH A, CI, DI ; POP A, CI, DI  -> A=3 CI=2 DI=1
        self.assertEqual((cpu.a.get(), cpu.ci.get(), cpu.di.get()), (0x03, 0x02, 0x01))
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x03, 0xff))

    def test_PSH_POP_work_across_the_page_boundary(self):
        # stack moved to 0x0200: the frame crosses into 0x01ff and SS follows
        cpu = self.run_code([0x1C, 0x00, 0x1D, 0x02, 0x81, KIL], a=0x5c)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x01, 0xfe))
        self.assertEqual(cpu.membus.read_byte(0x0200), 0x5c)
        self.assertEqual(cpu.membus.read_byte(0x01ff), CPU.STACKFRAME_TYPE_PUSH)
        cpu = self.run_code([0x1C, 0x00, 0x1D, 0x02, 0x81, 0x94, KIL], a=0x5c)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x02, 0x00))
        self.assertEqual(cpu.ci.get(), 0x5c)

    def test_PSH_stack_is_tagged_with_push_marker_for_each_frame(self):
        cpu = self.run_code([0x81, 0x84, KIL], a=0x11, ci=0x22)
        self.assertEqual([cpu.membus.read_byte(STACK_TOP - i) for i in range(4)],
                         [0x11, 0x10, 0x22, 0x10])


class CallRetTests(ControlTestBase):
    def frame(self, cpu, ret):
        """Assert that a call frame (lo, hi, tag) with return address ret sits at the top."""
        self.assertEqual(cpu.membus.read_byte(STACK_TOP), ret & 0xff)
        self.assertEqual(cpu.membus.read_byte(STACK_TOP - 1), ret >> 8)
        self.assertEqual(cpu.membus.read_byte(STACK_TOP - 2), CPU.STACKFRAME_TYPE_CALL)

    def test_CAL_direct_jumps_and_pushes_return_address(self):
        cpu = self.build([0xA8, 0x00, 0x10, KIL] + [0x00] * 12 + [KIL])
        cpu.inc_pc(0)
        cpu.run_next_opcode()
        self.assertEqual(cpu.pc.get(), 0x10)
        self.frame(cpu, 0x0003)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x03, 0xfc))

    def test_CAL_register_jumps_and_pushes_return_address(self):
        for regno, hi_name, lo_name in [(0x4, 'cs', 'ci'), (0x5, 'ds', 'di'), (0xC, 'ss', 'si')]:
            with self.subTest(pair=hi_name + lo_name):
                code = [0x00, 0xA0, regno << 4, KIL] + [0x00] * 12 + [KIL]
                cpu = self.build(code)
                if hi_name == 'ss':
                    # SS:SI is the stack pointer itself: call to the stack address
                    cpu.membus.write_byte(STACK_TOP, KIL)
                    cpu.membus.write_byte(STACK_TOP - 1, KIL)
                    expected_target = STACK_TOP
                else:
                    getattr(cpu, hi_name).set(0x00)
                    getattr(cpu, lo_name).set(0x10)
                    expected_target = 0x10
                cpu.inc_pc(0)
                cpu.run_next_opcode()
                cpu.run_next_opcode()
                self.assertEqual(cpu.pc.get(), expected_target)
                if hi_name != 'ss':
                    self.frame(cpu, 0x0003)

    def test_CAL_direct_with_register_call_and_ret_roundtrip(self):
        code = [
            0x14, 0x0a,          # 0x00: MOV CI, 0x0a
            0xA0, 0x40,          # 0x02: CAL CSCI
            0x5d,                # 0x04: INC A
            KIL,                 # 0x05
            0x00, 0x00, 0x00, 0x00,
            0x5d,                # 0x0a: INC A
            0xB0,                # 0x0b: RET
        ]
        cpu = self.run_code(code)
        self.assertEqual(cpu.a.get(), 2)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x03, 0xff))
        self.assertEqual(cpu.pc.get(), 0x05)

    def test_CAL_direct_and_RET_roundtrip_restores_stack_and_continues(self):
        code = [0xA8, 0x00, 0x08, 0x5d, KIL, 0x00, 0x00, 0x00, 0x5d, 0xb0]
        cpu = self.run_code(code)
        self.assertEqual(cpu.a.get(), 2)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x03, 0xff))
        self.assertEqual(cpu.pc.get(), 4)

    def test_nested_CAL_RET(self):
        code = [
            0xA8, 0x00, 0x08,    # 0x00: CAL 0x0008
            KIL,                 # 0x03
            0x00, 0x00, 0x00, 0x00,
            0xA8, 0x00, 0x10,    # 0x08: CAL 0x0010
            0x5d,                # 0x0b: INC A
            0xb0,                # 0x0c: RET
            0x00, 0x00, 0x00,
            0x5d,                # 0x10: INC A
            0xb0,                # 0x11: RET
        ]
        cpu = self.run_code(code)
        self.assertEqual(cpu.a.get(), 2)
        self.assertEqual(cpu.pc.get(), 3)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x03, 0xff))

    def test_CLR_immediate_forward_and_backward(self):
        # target = instruction address + offset + 2, backward offset has bit 15 set (sign-magnitude)
        code = [0x00] * 0x20
        code[0x00:0x03] = [0xA9, 0x00, 0x0e]          # CLR +0x0e   -> 0x10
        code[0x03] = KIL
        code[0x08:0x0a] = [0x5d, 0xb0]                # sub2: INC A ; RET
        code[0x10:0x13] = [0xA9, 0x80, 0x0a]          # CLR -0x0a   -> 0x10 - 0x0a + 2 = 0x08
        code[0x13:0x15] = [0x5d, 0xb0]                # INC A ; RET
        cpu = self.run_code(code)
        self.assertEqual(cpu.a.get(), 2)
        self.assertEqual(cpu.pc.get(), 0x03)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x03, 0xff))

    def test_CLR_immediate_pushes_address_after_instruction(self):
        cpu = self.build([0xA9, 0x00, 0x0e] + [0x00] * 20)
        cpu.inc_pc(0)
        cpu.run_next_opcode()
        self.assertEqual(cpu.pc.get(), 0x10)
        self.frame(cpu, 0x0003)

    def test_CLR_register_forward_and_backward(self):
        code = [0x00] * 0x20
        code[0x00:0x02] = [0xA1, 0x84]                # CLR CSCI (CS:CI = +0x0e) -> 0x00 + 0x0e + 2 = 0x10
        code[0x02] = KIL
        code[0x08:0x0a] = [0x5d, 0xb0]                # INC A ; RET
        code[0x10:0x12] = [0xA1, 0x94]                # CLR DSDI (DS:DI = -0x0a) -> 0x10 - 0x0a + 2 = 0x08
        code[0x12:0x14] = [0x5d, 0xb0]                # INC A ; RET
        cpu = self.run_code(code, ci=0x0e, ds=0x80, di=0x0a)
        self.assertEqual(cpu.a.get(), 2)
        self.assertEqual(cpu.pc.get(), 0x02)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x03, 0xff))

    def test_CLR_register_pushes_address_after_instruction(self):
        cpu = self.build([0x00, 0xA1, 0x84] + [0x00] * 20, ci=0x0e)
        cpu.inc_pc(0)
        cpu.run_next_opcode()
        cpu.run_next_opcode()
        self.assertEqual(cpu.pc.get(), 0x01 + 0x0e + 2)
        self.frame(cpu, 0x0003)

    def test_RET_after_two_pushes_returns_to_pushed_address(self):
        # RET on a push frame takes the address from two pushed bytes: low byte pushed first, then high
        code = [0x14, 0x0a, 0x84, 0x18, 0x00, 0x88, 0xb0, KIL, 0x00, 0x00, 0x15, 0x55, KIL]
        # CI=0x0a, PSH CI (lo), MOV CS,0 , PSH CS (hi), RET -> 0x000a
        cpu = self.run_code(code)
        self.assertEqual(cpu.pc.get(), 0x0c)
        self.assertEqual(cpu.di.get(), 0x55)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x03, 0xff))


class IoTests(ControlTestBase):
    def bus(self, *devices):
        bus = bc64_io.IOBus()
        for device in devices:
            bus.add_device(device)
        return bus

    def test_IN_immediate_port_reads_into_register(self):
        device = RecordingDevice(0x07, [0x5a, 0x6b])
        # IN A, #7 ; IN CI, #7  (dest in the high nibble, port in the low nibble)
        cpu = self.run_code([0xc0, 0x17, 0xc0, 0x47, KIL], iobus=self.bus(device))
        self.assertEqual(cpu.a.get(), 0x5a)
        self.assertEqual(cpu.ci.get(), 0x6b)
        self.assertEqual(cpu.pc.get(), 4)

    def test_IN_register_port_reads_from_port_in_register(self):
        device = RecordingDevice(0x0e, [0x77])
        cpu = self.run_code([0xc8, 0x14, KIL], iobus=self.bus(device), ci=0x0e)  # IN A, (port = CI)
        self.assertEqual(cpu.a.get(), 0x77)
        self.assertEqual(cpu.pc.get(), 2)

    def test_IN_selects_the_device_by_port(self):
        d1 = RecordingDevice(0x01, [0x11])
        d2 = RecordingDevice(0x02, [0x22])
        cpu = self.run_code([0xc0, 0x12, KIL], iobus=self.bus(d1, d2))
        self.assertEqual(cpu.a.get(), 0x22)
        self.assertEqual(d1.to_read, [0x11])

    def test_IN_does_not_change_flags(self):
        device = RecordingDevice(0x01, [0x00])
        cpu = self.run_code([0xc0, 0x11, KIL], iobus=self.bus(device), z=0, n=1)
        self.assertFalse(cpu.f.get_flag(FLAG_Z))
        self.assertTrue(cpu.f.get_flag(FLAG_N))

    def test_OUT_immediate_sends_full_byte_to_port_in_register(self):
        # D4 41: port number held in CI (register 4), value is the whole second byte (#11: CPU side works)
        device = RecordingDevice(0x07)
        cpu = self.run_code([0xd4, 0x41, KIL], iobus=self.bus(device), ci=0x07)
        self.assertEqual(device.written, [0x41])
        self.assertEqual(cpu.pc.get(), 2)

    def test_OUT_immediate_with_other_port_registers(self):
        for opcode, name in [(0xd1, 'a'), (0xd5, 'di')]:
            with self.subTest(port_register=name):
                device = RecordingDevice(0x09)
                self.run_code([opcode, 0xfe, KIL], iobus=self.bus(device), **{name: 0x09})
                self.assertEqual(device.written, [0xfe])

    def test_OUT_register_form_sends_register_value_to_register_port(self):
        device = RecordingDevice(0x0b)
        # OUT (port = CI), A : high nibble of the second byte is the port register, low nibble the value register
        cpu = self.run_code([0xd8, 0x41, KIL], iobus=self.bus(device), ci=0x0b, a=0x33)
        self.assertEqual(device.written, [0x33])
        self.assertEqual(cpu.pc.get(), 2)

    def test_OUT_register_form_sets_flags_from_value(self):
        device = RecordingDevice(0x05)
        cpu = self.run_code([0xd8, 0x41, KIL], iobus=self.bus(device), ci=0x05, a=0x00, z=0)
        self.assertTrue(cpu.f.get_flag(FLAG_Z))
        cpu = self.run_code([0xd8, 0x41, KIL], iobus=self.bus(device), ci=0x05, a=0x81, z=1)
        self.assertFalse(cpu.f.get_flag(FLAG_Z))
        self.assertTrue(cpu.f.get_flag(FLAG_N))

    def test_OUT_immediate_does_not_change_flags(self):
        device = RecordingDevice(0x05)
        cpu = self.run_code([0xd4, 0x00, KIL], iobus=self.bus(device), ci=0x05, z=0, n=1)
        self.assertFalse(cpu.f.get_flag(FLAG_Z))
        self.assertTrue(cpu.f.get_flag(FLAG_N))

    def test_IN_OUT_round_trip(self):
        device = RecordingDevice(0x04, [0x21, 0x22])
        code = [0x14, 0x04,        # MOV CI, 4
                0xc8, 0x14,        # IN A, (CI)
                0xc8, 0x54,        # IN DI, (CI)
                0xd8, 0x45,        # OUT (CI), DI
                0xd8, 0x41,        # OUT (CI), A
                KIL]
        run_cpu(self.build(code, iobus=self.bus(device)))
        self.assertEqual(device.written, [0x22, 0x21])


if __name__ == '__main__':
    unittest.main()
