"""ALU tests of the bc8183 CPU (8-bit `alu` and 16-bit `alu16` tables).

Every test executes encoded bytes on the CPU and asserts the result, the
flags and the instruction length (PC ends on the KIL after the code).

Flags are asserted exactly as the CPU defines them. Z and N describe the
stored result (A or the destination pair, story #53). C is the unsigned
carry (add, inc, mul) or borrow (sub, dec) and O the two's-complement signed
overflow of add, sub, inc and dec; and/or/xor/not clear both, mul sets
C = O, div/mod clear both (story #54). The SHL/SHR flags (8- and 16-bit)
follow #55: Z/N from the stored result, C = the last bit shifted out,
O = a 1 bit was lost (SHL only).
"""
import contextlib
import io
import unittest

from bc64 import bc8183_cpu
from bc64 import bc64_mem
from bc64 import bc64_env

KIL = 0xff
CS, DS, A = 0x8, 0x9, 0x1


def flags_of(cpu):
    f = cpu.f
    return (f.get_flag(f.ZERO), f.get_flag(f.CARRY),
            f.get_flag(f.NEGATIVE), f.get_flag(f.OVERFLOW))


def flags_from_raw(v, bits=8):
    """Flags (Z, C, N, O) from the raw (unmasked) result, valid for results
    that stay in range and for the pinned SHL/SHR flags (#55). It does not
    model signed overflow or borrow (#54): for add/sub/inc/dec results that
    wrap or overflow, and for logic ops with a negative raw value, pass the
    expected flags explicitly. Z is computed from the raw value too, so for
    a result that wraps to 0 pass them explicitly as well (Z is set from the
    stored value, #53)."""
    top = 1 << bits
    sign = top >> 1
    return (v == 0, v >= top, (v & sign) == sign, v >= top or v < 0)


class AluTestBase(unittest.TestCase):
    def run_code(self, code, **regs):
        """Run `code` followed by KIL, return the CPU. Registers are preset
        by keyword (a, ci, di, cs, ds); flags can be preset with `flags`."""
        env = bc64_env.Environment(False)
        mem = bc64_mem.MemBus(env, 0x0100)
        code = list(code)
        for i, b in enumerate(code + [KIL]):
            mem.write_byte(i, b)
        cpu = bc8183_cpu.Bc8183(mem, None, False)
        flags = regs.pop('flags', None)
        for name, val in regs.items():
            getattr(cpu, name).set(val)
        if flags:
            for flag, val in flags.items():
                cpu.f.set_flag(flag, val)
        cpu.run()
        self.assertEqual(cpu.pc.get(), len(code),
                         "instruction length / PC after execution")
        return cpu

    def pair(self, cpu, hi='cs', lo='ci'):
        return (getattr(cpu, hi).get() << 8) | getattr(cpu, lo).get()


class Alu8Tests(AluTestBase):
    def check(self, code, a, expected_a, raw, other=None, **regs):
        cpu = self.run_code(code, a=a, **regs)
        self.assertEqual(cpu.a.get(), expected_a)
        self.assertEqual(flags_of(cpu), flags_from_raw(raw) if other is None else other)
        return cpu

    # --- ADD ---------------------------------------------------------
    def test_add_imm(self):
        self.check([0x50, 0x20], 0x10, 0x30, 0x30)

    def test_add_imm_zero_result(self):
        self.check([0x50, 0x00], 0x00, 0x00, 0x00)

    def test_add_imm_wrap_at_0xff(self):
        # Z describes the stored A (#53); 0xff + 1: unsigned carry, no signed overflow (-1 + 1)
        self.check([0x50, 0x01], 0xff, 0x00, 0x100, (True, True, False, False))

    def test_add_imm_sign_bit_signed_overflow(self):
        # 0x7f + 1 = 0x80 sets N and the signed overflow O (127 + 1), no carry
        self.check([0x50, 0x01], 0x7f, 0x80, 0x80, (False, False, True, True))

    def test_add_reg(self):
        self.check([0x58, 0x40], 0x10, 0x35, 0x35, ci=0x25)

    def test_add_reg_a_a(self):
        self.check([0x58, 0x10], 0x81, 0x02, 0x102)

    # --- SUB ---------------------------------------------------------
    def test_sub_imm(self):
        self.check([0x51, 0x03], 0x05, 0x02, 0x02)

    def test_sub_imm_zero(self):
        self.check([0x51, 0x05], 0x05, 0x00, 0x00)

    def test_sub_imm_wrap_below_zero(self):
        # 3 - 5 = -2 -> 0xfe, N and C (borrow), no signed overflow
        self.check([0x51, 0x05], 0x03, 0xfe, -2, (False, True, True, False))

    def test_sub_reg(self):
        self.check([0x59, 0x40], 0x50, 0x30, 0x30, ci=0x20)

    def test_sub_reg_borrow(self):
        self.check([0x59, 0x50], 0x00, 0xff, -1, (False, True, True, False), di=0x01)

    # --- AND / OR / XOR ----------------------------------------------
    def test_and_imm(self):
        self.check([0x52, 0x3c], 0xf0, 0x30, 0x30)

    def test_and_imm_zero(self):
        self.check([0x52, 0x0f], 0xf0, 0x00, 0x00)

    def test_and_reg(self):
        self.check([0x5a, 0x40], 0xff, 0x81, 0x81, ci=0x81)

    def test_or_imm(self):
        self.check([0x53, 0x0f], 0xf0, 0xff, 0xff)

    def test_or_reg(self):
        self.check([0x5b, 0x40], 0x00, 0x00, 0x00, ci=0x00)

    def test_xor_imm(self):
        self.check([0x54, 0x55], 0xaa, 0xff, 0xff)

    def test_xor_reg_self_zero(self):
        self.check([0x5c, 0x10], 0x69, 0x00, 0x00)

    def test_xor_reg(self):
        self.check([0x5c, 0x50], 0xff, 0xf0, 0xf0, di=0x0f)

    # --- SHL / SHR -----------------------------------------------------
    def test_shl_imm_result(self):
        # Z and N describe the stored A = 0x02
        self.check([0x55, 0x01], 0x01, 0x02, 0, (False, False, False, False))

    def test_shl_imm_into_sign_bit(self):
        # A = 0x80: Z = 0, N = 1, nothing shifted out; 64 -> 128 does not
        # fit a signed byte, so O = 1 (#161)
        self.check([0x55, 0x01], 0x40, 0x80, 0, (False, False, True, True))

    def test_shl_imm_carry_out(self):
        # bit 7 shifted out: A = 0x02, C = 1 (last bit out), O = 1, Z = 0
        self.check([0x55, 0x01], 0x81, 0x02, 0x100, (False, True, False, True))

    def test_shl_imm_by_zero(self):
        self.check([0x55, 0x00], 0x12, 0x12, 0, (False, False, False, False))

    def test_shr_imm_even_result(self):
        # A = 0x02: Z = 0; the bit shifted out (bit 0 of 0x04) is 0
        self.check([0x56, 0x01], 0x04, 0x02, 0, (False, False, False, False))

    def test_shr_imm_odd_result(self):
        # A = 0x03; the bit shifted out (bit 0 of 0x06) is 0: no C, N, O
        self.check([0x56, 0x01], 0x06, 0x03, -1, (False, False, False, False))

    def test_shr_imm_by_two(self):
        self.check([0x56, 0x02], 0xf0, 0x3c, 0, (False, False, False, False))

    def test_single_byte_5d_5e_are_inc_dec(self):
        # 0x5d/0x5e would be the short register forms of SHL/SHR, but they
        # are the single-byte INC/DEC. SHL/SHR by a register use 58 r5 / 58 r6.
        cpu = self.run_code([0x5d], a=0x10)
        self.assertEqual(cpu.a.get(), 0x11)
        cpu = self.run_code([0x5e], a=0x10)
        self.assertEqual(cpu.a.get(), 0x0f)

    # --- NOT ---------------------------------------------------------
    def test_not(self):
        # ~0x0f = 0xf0: N set; C and O are cleared by logic ops
        self.check([0x57], 0x0f, 0xf0, -16, (False, False, True, False))

    def test_not_zero_gives_ff(self):
        self.check([0x57], 0x00, 0xff, -1, (False, False, True, False))

    def test_not_ff_gives_zero(self):
        # Z describes the stored A (#53); C and O are cleared by logic ops
        self.check([0x57], 0xff, 0x00, -256, (True, False, False, False))

    # --- INC / DEC ---------------------------------------------------
    def test_inc(self):
        self.check([0x5d], 0x41, 0x42, 0x42)

    def test_inc_into_sign_bit(self):
        # 0x7f + 1: signed overflow O, no carry
        self.check([0x5d], 0x7f, 0x80, 0x80, (False, False, True, True))

    def test_inc_wrap_at_0xff(self):
        # Z describes the stored A (#53); 0xff + 1: carry, no signed overflow
        self.check([0x5d], 0xff, 0x00, 0x100, (True, True, False, False))

    def test_dec(self):
        self.check([0x5e], 0x42, 0x41, 0x41)

    def test_dec_to_zero(self):
        self.check([0x5e], 0x01, 0x00, 0x00)

    def test_dec_wrap_below_zero(self):
        # 0 - 1: borrow C, no signed overflow
        self.check([0x5e], 0x00, 0xff, -1, (False, True, True, False))

    def test_inc_dec_do_not_touch_next_byte(self):
        cpu = self.run_code([0x5d, 0x5d, 0x5e], a=0x00)
        self.assertEqual(cpu.a.get(), 0x01)

    def test_alu_only_changes_a(self):
        cpu = self.run_code([0x50, 0x01], a=0x01, ci=0x11, di=0x22, cs=0x33, ds=0x44)
        self.assertEqual((cpu.ci.get(), cpu.di.get(), cpu.cs.get(), cpu.ds.get()),
                         (0x11, 0x22, 0x33, 0x44))

    def test_flags_are_overwritten_each_operation(self):
        # ADD ... wraps (C set), then a plain INC clears C again
        cpu = self.run_code([0x50, 0x01, 0x5d], a=0xff)
        self.assertEqual(cpu.a.get(), 0x01)
        self.assertEqual(flags_of(cpu), (False, False, False, False))


class Alu16Tests(AluTestBase):
    def imm(self, group, op, regbyte, value):
        return [0x5f, group << 4 | op, regbyte, value >> 8, value & 0xff]

    def check16(self, code, start, expected, raw, other=None, **regs):
        cs, ci = start >> 8, start & 0xff
        cpu = self.run_code(code, cs=cs, ci=ci, **regs)
        self.assertEqual(self.pair(cpu), expected)
        self.assertEqual(flags_of(cpu),
                         flags_from_raw(raw, 16) if other is None else other)
        return cpu

    # --- ADD / SUB ---------------------------------------------------
    def test_add16_imm(self):
        self.check16(self.imm(0xa, 0x0, 0x80, 0x1234), 0x1111, 0x2345, 0x2345)

    def test_add16_carry_across_low_byte(self):
        self.check16(self.imm(0xa, 0x0, 0x80, 0x0001), 0x00ff, 0x0100, 0x0100)

    def test_add16_wrap_at_0xffff(self):
        # Z describes the stored pair (#53); 0xffff + 1: carry, no signed overflow
        self.check16(self.imm(0xa, 0x0, 0x80, 0x0001), 0xffff, 0x0000,
                     0x10000, (True, True, False, False))

    def test_add16_into_sign_bit(self):
        # 0x7fff + 1: signed overflow O, no carry
        self.check16(self.imm(0xa, 0x0, 0x80, 0x0001), 0x7fff, 0x8000, 0x8000,
                     (False, False, True, True))

    def test_add16_zero(self):
        self.check16(self.imm(0xa, 0x0, 0x80, 0x0000), 0x0000, 0x0000, 0)

    def test_add16_reg_cs_ds(self):
        self.check16([0x5f, 0xa8, 0x80], 0x1000, 0x1234, 0x1234, ds=0x02, di=0x34)

    def test_add16_reg_ds_cs(self):
        cpu = self.run_code([0x5f, 0xa8, 0x90], ds=0x01, di=0xff, cs=0x00, ci=0x01)
        self.assertEqual(self.pair(cpu, 'ds', 'di'), 0x0200)
        self.assertEqual(flags_of(cpu), flags_from_raw(0x0200, 16))

    def test_sub16_imm(self):
        self.check16(self.imm(0xa, 0x1, 0x80, 0x0101), 0x0302, 0x0201, 0x0201)

    def test_sub16_zero(self):
        self.check16(self.imm(0xa, 0x1, 0x80, 0x1234), 0x1234, 0x0000, 0)

    def test_sub16_wrap_below_zero(self):
        # 0 - 1: borrow C, no signed overflow
        self.check16(self.imm(0xa, 0x1, 0x80, 0x0001), 0x0000, 0xffff,
                     -1, (False, True, True, False))

    def test_sub16_reg(self):
        self.check16([0x5f, 0xa9, 0x80], 0x1000, 0x0fff, 0x0fff, ds=0x00, di=0x01)

    def test_sub16_reg_ds_cs(self):
        cpu = self.run_code([0x5f, 0xa9, 0x90], ds=0x05, di=0x00, cs=0x01, ci=0x00)
        self.assertEqual(self.pair(cpu, 'ds', 'di'), 0x0400)

    # --- MUL / DIV / MOD ---------------------------------------------
    def test_mul16_imm(self):
        self.check16(self.imm(0xa, 0x2, 0x80, 0x0003), 0x0101, 0x0303, 0x0303)

    def test_mul16_overflow(self):
        # Z describes the stored pair (#53); product over 0xffff: C = O = 1 (#54)
        self.check16(self.imm(0xa, 0x2, 0x80, 0x0100), 0x0100, 0x0000,
                     0x10000, (True, True, False, True))

    def test_mul16_by_zero(self):
        self.check16(self.imm(0xa, 0x2, 0x80, 0x0000), 0x1234, 0x0000, 0)

    def test_mul16_reg(self):
        self.check16([0x5f, 0xaa, 0x80], 0x0010, 0x0100, 0x0100, ds=0x00, di=0x10)

    def test_div16_imm(self):
        self.check16(self.imm(0xa, 0x3, 0x80, 0x0007), 0x0064, 0x000e, 0x000e)

    def test_div16_smaller_than_divisor(self):
        self.check16(self.imm(0xa, 0x3, 0x80, 0x0200), 0x0064, 0x0000, 0)

    def test_div16_reg(self):
        self.check16([0x5f, 0xab, 0x80], 0x8000, 0x4000, 0x4000, ds=0x00, di=0x02)

    def test_mod16_imm(self):
        self.check16(self.imm(0xa, 0x4, 0x80, 0x0007), 0x0064, 0x0002, 0x0002)

    def test_mod16_exact_is_zero(self):
        self.check16(self.imm(0xa, 0x4, 0x80, 0x0005), 0x000a, 0x0000, 0)

    def test_mod16_reg(self):
        self.check16([0x5f, 0xac, 0x80], 0x1235, 0x0001, 0x0001, ds=0x00, di=0x04)

    # Div/mod by zero (#4 item 3, D8): no exception, the CPU keeps running.
    # The destination pair and Z/N/C stay as they were, O is set.
    def check_zero_divisor(self, code, flag_state, **regs):
        flags = dict(zip((bc8183_cpu.FlagsRegister.ZERO, bc8183_cpu.FlagsRegister.CARRY,
                          bc8183_cpu.FlagsRegister.NEGATIVE, bc8183_cpu.FlagsRegister.OVERFLOW),
                         flag_state))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cpu = self.run_code(list(code) + [0x15, 0x55], cs=0x12, ci=0x34, flags=flags, **regs)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(self.pair(cpu), 0x1234)
        z, c, n, _ = flag_state
        self.assertEqual(flags_of(cpu), (z, c, n, 1))
        # the CPU went on: the trailing "mov di" ran, run_code checked PC
        self.assertEqual(cpu.di.get(), 0x55)
        return cpu

    FLAG_STATES = [(0, 0, 0, 0), (1, 0, 1, 0), (0, 1, 0, 1), (1, 1, 1, 1)]

    def test_div16_imm_by_zero_sets_overflow_only(self):
        for state in self.FLAG_STATES:
            with self.subTest(flags=state):
                self.check_zero_divisor(self.imm(0xa, 0x3, 0x80, 0), state)

    def test_mod16_imm_by_zero_sets_overflow_only(self):
        for state in self.FLAG_STATES:
            with self.subTest(flags=state):
                self.check_zero_divisor(self.imm(0xa, 0x4, 0x80, 0), state)

    def test_div16_reg_by_zero_sets_overflow_only(self):
        for state in self.FLAG_STATES:
            with self.subTest(flags=state):
                self.check_zero_divisor([0x5f, 0xab, 0x80], state, ds=0, di=0)

    def test_mod16_reg_by_zero_sets_overflow_only(self):
        for state in self.FLAG_STATES:
            with self.subTest(flags=state):
                self.check_zero_divisor([0x5f, 0xac, 0x80], state, ds=0, di=0)

    def test_nonzero_div_mod_clear_a_previously_set_overflow(self):
        o = {bc8183_cpu.FlagsRegister.OVERFLOW: 1}
        for code in (self.imm(0xa, 0x3, 0x80, 2), self.imm(0xa, 0x4, 0x80, 5),
                     [0x5f, 0xab, 0x80], [0x5f, 0xac, 0x80]):
            with self.subTest(code=code):
                cpu = self.run_code(code, cs=0x00, ci=0x0a, ds=0, di=3, flags=o)
                self.assertEqual(flags_of(cpu)[3], 0)

    def test_div_by_zero_then_jrx_o_reaches_the_error_branch(self):
        # div cs, 0 ; jrx o -> error ; ok: mov di,0x11 ; kil ; error: mov di,0x22 ; kil
        code = self.imm(0xa, 0x3, 0x80, 0) + [0xe1, 0x30, 0x00, 0x04] + [0x15, 0x11, KIL, 0x00] + [0x15, 0x22, KIL]
        env = bc64_env.Environment(False)
        mem = bc64_mem.MemBus(env, 0x0100)
        for i, b in enumerate(code):
            mem.write_byte(i, b)
        cpu = bc8183_cpu.Bc8183(mem, None, False)
        cpu.cs.set(0x01)
        cpu.run()
        self.assertEqual(cpu.di.get(), 0x22)
        self.assertEqual(self.pair(cpu), 0x0100)

    # --- INC / DEC ---------------------------------------------------
    def test_inc16(self):
        self.check16([0x5f, 0xad, 0x80], 0x1234, 0x1235, 0x1235)

    def test_inc16_carry_across_low_byte(self):
        self.check16([0x5f, 0xad, 0x80], 0x00ff, 0x0100, 0x0100)

    def test_inc16_wrap_at_0xffff(self):
        # Z describes the stored pair (#53); 0xffff + 1: carry, no signed overflow
        self.check16([0x5f, 0xad, 0x80], 0xffff, 0x0000, 0x10000,
                     (True, True, False, False))

    def test_inc16_ds_pair(self):
        cpu = self.run_code([0x5f, 0xad, 0x90], ds=0x12, di=0xff)
        self.assertEqual(self.pair(cpu, 'ds', 'di'), 0x1300)

    def test_dec16(self):
        self.check16([0x5f, 0xae, 0x80], 0x1234, 0x1233, 0x1233)

    def test_dec16_borrow_across_low_byte(self):
        self.check16([0x5f, 0xae, 0x80], 0x0100, 0x00ff, 0x00ff)

    def test_dec16_to_zero(self):
        self.check16([0x5f, 0xae, 0x80], 0x0001, 0x0000, 0)

    def test_dec16_wrap_below_zero(self):
        # 0 - 1: borrow C, no signed overflow
        self.check16([0x5f, 0xae, 0x80], 0x0000, 0xffff, -1,
                     (False, True, True, False))

    def test_dec16_ds_pair(self):
        cpu = self.run_code([0x5f, 0xae, 0x90], ds=0x13, di=0x00)
        self.assertEqual(self.pair(cpu, 'ds', 'di'), 0x12ff)

    # --- AND / OR / XOR ----------------------------------------------
    def test_and16_imm(self):
        self.check16(self.imm(0xb, 0x2, 0x80, 0x0ff0), 0x1234, 0x0230, 0x0230)

    def test_and16_zero(self):
        self.check16(self.imm(0xb, 0x2, 0x80, 0xff00), 0x00ff, 0x0000, 0)

    def test_and16_reg(self):
        self.check16([0x5f, 0xba, 0x80], 0xffff, 0x8001, 0x8001, ds=0x80, di=0x01)

    def test_or16_imm(self):
        self.check16(self.imm(0xb, 0x3, 0x80, 0x00ff), 0xf000, 0xf0ff, 0xf0ff)

    def test_or16_reg(self):
        self.check16([0x5f, 0xbb, 0x80], 0x0100, 0x0101, 0x0101, ds=0x00, di=0x01)

    def test_xor16_imm(self):
        self.check16(self.imm(0xb, 0x4, 0x80, 0xffff), 0x1234, 0xedcb, 0xedcb)

    def test_xor16_reg_self_inverse(self):
        self.check16([0x5f, 0xbc, 0x80], 0xabcd, 0x0000, 0, ds=0xab, di=0xcd)

    # --- SHL / SHR -----------------------------------------------------
    def test_shl16_imm(self):
        self.check16(self.imm(0xb, 0x5, 0x80, 0x0004), 0x0001, 0x0010, 0x0010)

    def test_shl16_carry_out(self):
        # bit 15 shifted out: pair 0x0002, C = 1 (last bit out), O = 1
        self.check16(self.imm(0xb, 0x5, 0x80, 0x0001), 0x8001, 0x0002,
                     0x10002, (False, True, False, True))

    def test_shl16_reg(self):
        self.check16([0x5f, 0xbd, 0x80], 0x0003, 0x0030, 0x0030, ds=0x00, di=0x04)

    def test_shr16_imm(self):
        self.check16(self.imm(0xb, 0x6, 0x80, 0x0004), 0x0100, 0x0010, 0x0010)

    def test_shr16_to_zero(self):
        # Z from the stored pair; C = last bit shifted out (bit 7 of 0x00ff)
        self.check16(self.imm(0xb, 0x6, 0x80, 0x0008), 0x00ff, 0x0000, 0,
                     (True, True, False, False))

    def test_shr16_reg(self):
        self.check16([0x5f, 0xbe, 0x80], 0x8000, 0x2000, 0x2000, ds=0x00, di=0x02)

    # --- NOT -----------------------------------------------------------
    def test_not16(self):
        # ~0x00ff = 0xff00: N; C and O are cleared by logic ops
        self.check16([0x5f, 0xb7, 0x80], 0x00ff, 0xff00, -256,
                     (False, False, True, False))

    def test_not16_zero(self):
        self.check16([0x5f, 0xb7, 0x80], 0x0000, 0xffff, -1,
                     (False, False, True, False))

    def test_not16_ffff(self):
        # Z describes the stored pair (#53); C and O are cleared by logic ops
        self.check16([0x5f, 0xb7, 0x80], 0xffff, 0x0000, -65536,
                     (True, False, False, False))

    def test_not16_ds_pair(self):
        cpu = self.run_code([0x5f, 0xb7, 0x90], ds=0x0f, di=0xf0)
        self.assertEqual(self.pair(cpu, 'ds', 'di'), 0xf00f)

    # --- A:F pair --------------------------------------------------------
    def test_add16_on_a_f_pair(self):
        # Defined behaviour (E14, #58): A:F is a 16-bit pair. A takes the high
        # byte of the result, F takes the flags (set_flags16) and the low byte
        # is discarded. af is allowed but not meant for 16-bit arithmetic.
        cpu = self.run_code(self.imm(0xa, 0x0, 0x10, 0x0100), a=0x01)
        self.assertEqual(cpu.a.get(), 0x02)
        self.assertEqual(cpu.f.get(), 0x00)

    def test_add16_reg_on_a_f_pair_uses_cs_ci(self):
        cpu = self.run_code([0x5f, 0xa8, 0x10], a=0x01, cs=0x02, ci=0x00)
        self.assertEqual(cpu.a.get(), 0x03)

    def test_add16_on_a_f_pair_low_byte_discarded_f_is_flags(self):
        # 0x7f00 + 0x0123 = 0x8023: A = 0x80, F = N|O (signed overflow, E13) = 0x0c, not the low byte 0x23
        cpu = self.run_code(self.imm(0xa, 0x0, 0x10, 0x0123), a=0x7f, f=0x00)
        self.assertEqual(cpu.a.get(), 0x80)
        self.assertEqual(cpu.f.get(), 0x0c)

    def test_add16_on_a_f_pair_reads_f_as_low_byte(self):
        # pair 0x00ff + 0x0001 = 0x0100: F = 0xff is the low byte of the input
        cpu = self.run_code(self.imm(0xa, 0x0, 0x10, 0x0001), a=0x00, f=0xff)
        self.assertEqual(cpu.a.get(), 0x01)
        self.assertEqual(cpu.f.get(), 0x00)

    def test_sub16_on_a_f_pair_borrow_sets_n_and_c(self):
        # 0x0100 - 0x0200 = -0x0100: stored 0xff00, A = 0xff, F = N|C (borrow, E13) = 0x06
        cpu = self.run_code(self.imm(0xa, 0x1, 0x10, 0x0200), a=0x01, f=0x00)
        self.assertEqual(cpu.a.get(), 0xff)
        self.assertEqual(cpu.f.get(), 0x06)

    def test_mul16_on_a_f_pair_wrap_to_zero_sets_z_c_o(self):
        # 0x1000 * 0x0100 = 0x100000: stored 0x0000, A = 0x00, F = Z|C|O (0x01|0x02|0x08)
        cpu = self.run_code(self.imm(0xa, 0x2, 0x10, 0x0100), a=0x10, f=0x00)
        self.assertEqual(cpu.a.get(), 0x00)
        self.assertEqual(cpu.f.get(), 0x0b)

    def test_add16_reg_on_a_f_pair_low_byte_discarded(self):
        # op af, csci: 0x7ff0 + 0x0123 = 0x8113: A = 0x81, F = N|O (signed overflow, E13) = 0x0c
        cpu = self.run_code([0x5f, 0xa8, 0x10], a=0x7f, f=0xf0, cs=0x01, ci=0x23)
        self.assertEqual(cpu.a.get(), 0x81)
        self.assertEqual(cpu.f.get(), 0x0c)

    def test_shl16_wrap_to_zero_sets_z(self):
        # 0x8000 << 1 = pair 0x0000: Z describes the stored pair (#53); C = bit 15 shifted out, O = a 1 bit lost
        self.check16(self.imm(0xb, 0x5, 0x80, 0x0001), 0x8000, 0x0000,
                     0x10000, (True, True, False, True))


class CarryAndOverflowTests(AluTestBase):
    """C is the unsigned carry/borrow, O the signed overflow (#54)."""
    CF, OF = 1, 3

    def flags8(self, code, a, **regs):
        cpu = self.run_code(code, a=a, **regs)
        return cpu.a.get(), flags_of(cpu)

    def flags16(self, code, start, **regs):
        cpu = self.run_code(code, cs=start >> 8, ci=start & 0xff, **regs)
        return self.pair(cpu), flags_of(cpu)

    def imm16(self, op, value):
        return [0x5f, 0xa0 | op, 0x80, value >> 8, value & 0xff]

    def test_add8_signed_overflow_without_carry(self):
        self.assertEqual(self.flags8([0x50, 0x01], 0x7f), (0x80, (False, False, True, True)))

    def test_add8_carry_and_overflow(self):
        self.assertEqual(self.flags8([0x50, 0x80], 0x80), (0x00, (True, True, False, True)))

    def test_add8_negative_plus_positive_never_overflows(self):
        self.assertEqual(self.flags8([0x50, 0x7f], 0x80), (0xff, (False, False, True, False)))

    def test_add8_reg_signed_overflow(self):
        self.assertEqual(self.flags8([0x58, 0x40], 0x50, ci=0x50), (0xa0, (False, False, True, True)))

    def test_sub8_signed_overflow_without_borrow(self):
        self.assertEqual(self.flags8([0x51, 0x01], 0x80), (0x7f, (False, False, False, True)))

    def test_sub8_borrow_and_overflow(self):
        self.assertEqual(self.flags8([0x51, 0xff], 0x7f), (0x80, (False, True, True, True)))

    def test_sub8_borrow_without_overflow(self):
        self.assertEqual(self.flags8([0x51, 0x01], 0x00), (0xff, (False, True, True, False)))

    def test_sub8_no_borrow(self):
        self.assertEqual(self.flags8([0x51, 0x01], 0x05), (0x04, (False, False, False, False)))

    def test_sub8_equal_operands_no_borrow(self):
        self.assertEqual(self.flags8([0x51, 0x05], 0x05), (0x00, (True, False, False, False)))

    def test_sub8_reg_borrow(self):
        self.assertEqual(self.flags8([0x59, 0x50], 0x03, di=0x05), (0xfe, (False, True, True, False)))

    def test_inc8_overflow_only_at_0x7f(self):
        self.assertEqual(self.flags8([0x5d], 0x7f), (0x80, (False, False, True, True)))
        self.assertEqual(self.flags8([0x5d], 0x80), (0x81, (False, False, True, False)))

    def test_dec8_overflow_only_at_0x80(self):
        self.assertEqual(self.flags8([0x5e], 0x80), (0x7f, (False, False, False, True)))
        self.assertEqual(self.flags8([0x5e], 0x7f), (0x7e, (False, False, False, False)))

    def test_logic8_clear_a_preset_carry_and_overflow(self):
        preset = {bc8183_cpu.FlagsRegister.CARRY: 1, bc8183_cpu.FlagsRegister.OVERFLOW: 1}
        for name, code in (('and', [0x52, 0xff]), ('or', [0x53, 0x01]),
                           ('xor', [0x54, 0x01]), ('not', [0x57])):
            with self.subTest(op=name):
                cpu = self.run_code(code, a=0x80, flags=preset)
                _, c, _, o = flags_of(cpu)
                self.assertEqual((c, o), (0, 0))

    def test_add16_signed_overflow_without_carry(self):
        self.assertEqual(self.flags16(self.imm16(0, 1), 0x7fff), (0x8000, (False, False, True, True)))

    def test_add16_carry_and_overflow(self):
        self.assertEqual(self.flags16(self.imm16(0, 0x8000), 0x8000), (0x0000, (True, True, False, True)))

    def test_sub16_signed_overflow_without_borrow(self):
        self.assertEqual(self.flags16(self.imm16(1, 1), 0x8000), (0x7fff, (False, False, False, True)))

    def test_sub16_borrow_and_overflow(self):
        self.assertEqual(self.flags16(self.imm16(1, 0xffff), 0x7fff), (0x8000, (False, True, True, True)))

    def test_sub16_borrow_without_overflow(self):
        self.assertEqual(self.flags16(self.imm16(1, 1), 0x0000), (0xffff, (False, True, True, False)))

    def test_sub16_no_borrow(self):
        self.assertEqual(self.flags16(self.imm16(1, 1), 0x0005), (0x0004, (False, False, False, False)))

    def test_sub16_reg_borrow(self):
        self.assertEqual(self.flags16([0x5f, 0xa9, 0x80], 0x0000, ds=0x00, di=0x01),
                         (0xffff, (False, True, True, False)))

    def test_inc16_overflow_only_at_0x7fff(self):
        self.assertEqual(self.flags16([0x5f, 0xad, 0x80], 0x7fff), (0x8000, (False, False, True, True)))
        self.assertEqual(self.flags16([0x5f, 0xad, 0x80], 0x8000), (0x8001, (False, False, True, False)))

    def test_dec16_overflow_only_at_0x8000(self):
        self.assertEqual(self.flags16([0x5f, 0xae, 0x80], 0x8000), (0x7fff, (False, False, False, True)))
        self.assertEqual(self.flags16([0x5f, 0xae, 0x80], 0x7fff), (0x7ffe, (False, False, False, False)))

    def test_mul16_over_range_sets_c_and_o(self):
        self.assertEqual(self.flags16(self.imm16(2, 0x0100), 0x0200), (0x0000, (True, True, False, True)))
        self.assertEqual(self.flags16(self.imm16(2, 2), 0x8000), (0x0000, (True, True, False, True)))

    def test_mul16_in_range_clears_c_and_o(self):
        preset = {bc8183_cpu.FlagsRegister.CARRY: 1, bc8183_cpu.FlagsRegister.OVERFLOW: 1}
        cpu = self.run_code(self.imm16(2, 2), cs=0x40, ci=0x00, flags=preset)
        self.assertEqual((self.pair(cpu), flags_of(cpu)), (0x8000, (False, False, True, False)))

    def test_div_mod16_clear_a_preset_carry_and_overflow(self):
        preset = {bc8183_cpu.FlagsRegister.CARRY: 1, bc8183_cpu.FlagsRegister.OVERFLOW: 1}
        for op in (3, 4):
            with self.subTest(op=op):
                cpu = self.run_code(self.imm16(op, 7), cs=0x00, ci=0x64, flags=preset)
                _, c, _, o = flags_of(cpu)
                self.assertEqual((c, o), (0, 0))

    def test_div_mod16_by_zero_keep_carry(self):
        preset = {bc8183_cpu.FlagsRegister.CARRY: 1}
        for op in (3, 4):
            with self.subTest(op=op):
                cpu = self.run_code(self.imm16(op, 0), cs=0x00, ci=0x64, flags=preset)
                _, c, _, o = flags_of(cpu)
                self.assertEqual((c, o), (1, 1))

    def test_logic16_clear_a_preset_carry_and_overflow(self):
        preset = {bc8183_cpu.FlagsRegister.CARRY: 1, bc8183_cpu.FlagsRegister.OVERFLOW: 1}
        for name, code in (('and', [0x5f, 0xb2, 0x80, 0xff, 0xff]), ('or', [0x5f, 0xb3, 0x80, 0x00, 0x01]),
                           ('xor', [0x5f, 0xb4, 0x80, 0x00, 0x01]), ('not', [0x5f, 0xb7, 0x80])):
            with self.subTest(op=name):
                cpu = self.run_code(code, cs=0x80, ci=0x00, flags=preset)
                _, c, _, o = flags_of(cpu)
                self.assertEqual((c, o), (0, 0))


class JumpOnZeroAfterWrapTests(AluTestBase):
    """`jmp z` is taken after an operation whose result wraps to zero (#53).
    Not taken: MOV DI,0x11 then KIL. Taken: lands on MOV DI,0x22."""

    def check_taken(self, op_code, target, **regs):
        code = list(op_code) + [0x68, target, 0x15, 0x11, KIL]
        code += [0x00] * (target - len(code))
        code += [0x15, 0x22]
        cpu = self.run_code(code, **regs)
        self.assertEqual(cpu.di.get(), 0x22)
        return cpu

    def test_jmp_z_taken_after_add_wrap(self):
        self.check_taken([0x50, 0x01], 0x08, a=0xff)

    def test_jmp_z_taken_after_inc_wrap(self):
        self.check_taken([0x5d], 0x07, a=0xff)

    def test_jmp_z_taken_after_add16_wrap(self):
        # CS becomes 0 with the wrap, so the short jump target is 0x00:imm8
        self.check_taken([0x5f, 0xa0, 0x80, 0x00, 0x01], 0x0d, cs=0xff, ci=0xff)

    def test_jmp_z_taken_after_inc16_wrap(self):
        self.check_taken([0x5f, 0xad, 0x80], 0x0b, cs=0xff, ci=0xff)


class ShiftFlagTests(AluTestBase):
    """SHL/SHR flags (#55, #161): Z/N from the stored result, C = last bit
    shifted out (0 for a shift by 0 or by more than the width). O after SHL
    is the signed overflow (E13): the stored result read as signed differs
    from the signed operand times 2**count; O after SHR is 0 (logical)."""
    Z, C, N, O = 0, 1, 2, 3

    def shift8(self, op, a, n, **regs):
        cpu = self.run_code([op, n], a=a, **regs)
        return cpu.a.get(), flags_of(cpu)

    def shl8(self, a, n, **regs):
        return self.shift8(0x55, a, n, **regs)

    def shr8(self, a, n, **regs):
        return self.shift8(0x56, a, n, **regs)

    def test_shl_into_bit7_sets_n(self):
        self.assertEqual(self.shl8(0x40, 1), (0x80, (False, False, True, True)))

    def test_shl_to_zero_sets_z_and_c(self):
        self.assertEqual(self.shl8(0x80, 1), (0x00, (True, True, False, True)))

    def test_shl_by_two_takes_last_bit_out(self):
        self.assertEqual(self.shl8(0x40, 2), (0x00, (True, True, False, True)))
        self.assertEqual(self.shl8(0x80, 2), (0x00, (True, False, False, True)))

    def test_shl_by_eight_and_more(self):
        self.assertEqual(self.shl8(0x01, 8), (0x00, (True, True, False, True)))
        self.assertEqual(self.shl8(0x02, 8), (0x00, (True, False, False, True)))
        self.assertEqual(self.shl8(0xff, 9), (0x00, (True, False, False, True)))
        self.assertEqual(self.shl8(0xff, 255), (0x00, (True, False, False, True)))
        self.assertEqual(self.shl8(0x00, 200), (0x00, (True, False, False, False)))

    def test_shl_by_zero_clears_c_and_o(self):
        cpu = self.run_code([0x55, 0x00], a=0x81,
                            flags={bc8183_cpu.FlagsRegister.CARRY: 1,
                                   bc8183_cpu.FlagsRegister.OVERFLOW: 1})
        self.assertEqual(cpu.a.get(), 0x81)
        self.assertEqual(flags_of(cpu), (False, False, True, False))

    def test_shr_odd_value_sets_c(self):
        self.assertEqual(self.shr8(0x03, 1), (0x01, (False, True, False, False)))
        self.assertEqual(self.shr8(0x01, 1), (0x00, (True, True, False, False)))

    def test_shr_by_n_takes_bit_n_minus_1(self):
        self.assertEqual(self.shr8(0x04, 3), (0x00, (True, True, False, False)))
        self.assertEqual(self.shr8(0x03, 2), (0x00, (True, True, False, False)))
        self.assertEqual(self.shr8(0x05, 2), (0x01, (False, False, False, False)))
        self.assertEqual(self.shr8(0x80, 8), (0x00, (True, True, False, False)))

    def test_shr_more_than_eight_clears_c(self):
        self.assertEqual(self.shr8(0xff, 9), (0x00, (True, False, False, False)))
        self.assertEqual(self.shr8(0xff, 255), (0x00, (True, False, False, False)))

    def test_shr_to_zero_sets_z(self):
        self.assertEqual(self.shr8(0x02, 2), (0x00, (True, True, False, False)))

    def test_shr_by_zero_clears_preset_c(self):
        cpu = self.run_code([0x56, 0x00], a=0x80,
                            flags={bc8183_cpu.FlagsRegister.CARRY: 1})
        self.assertEqual(cpu.a.get(), 0x80)
        self.assertEqual(flags_of(cpu), (False, False, True, False))

    def test_shr_never_sets_o_or_n(self):
        self.assertEqual(self.shr8(0xff, 1), (0x7f, (False, True, False, False)))

    def test_every_8bit_count_matches_the_definition(self):
        for v in (0x00, 0x01, 0x80, 0xa5, 0xff):
            for n in range(0, 256, 1 if v == 0xa5 else 7):
                full = v << n
                res = full & 0xff
                c = (full >> 8) & 1 if n <= 8 and n > 0 else 0
                sv = v - 0x100 if v >= 0x80 else v
                sr = res - 0x100 if res >= 0x80 else res
                o = int(sr != sv * (1 << min(n, 8)) if n < 8 else v != 0)
                self.assertEqual(self.shl8(v, n), (res, (res == 0, bool(c), res >= 0x80, bool(o))), (v, n))
                res = v >> n
                c = (v >> (n - 1)) & 1 if 0 < n <= 8 else 0
                self.assertEqual(self.shr8(v, n), (res, (res == 0, bool(c), res >= 0x80, False)), (v, n))

    # --- register-count forms: 58 r5 (shl a, r) / 58 r6 (shr a, r) ---------
    def shift_reg(self, op, a, reg, count, **regs):
        regno = {'ci': 0x4, 'di': 0x5}[reg]
        regs[reg] = count
        cpu = self.run_code([0x58, (regno << 4) | op], a=a, **regs)
        self.assertEqual(getattr(cpu, reg).get(), count, "count register kept")
        return cpu.a.get(), flags_of(cpu)

    def test_shl_by_register_ci_and_di(self):
        for reg in ('ci', 'di'):
            self.assertEqual(self.shift_reg(5, 0x40, reg, 1),
                             (0x80, (False, False, True, True)))
            self.assertEqual(self.shift_reg(5, 0x81, reg, 1),
                             (0x02, (False, True, False, True)))
            self.assertEqual(self.shift_reg(5, 0x40, reg, 2),
                             (0x00, (True, True, False, True)))
            self.assertEqual(self.shift_reg(5, 0x03, reg, 3),
                             (0x18, (False, False, False, False)))

    def test_shr_by_register_ci_and_di(self):
        for reg in ('ci', 'di'):
            self.assertEqual(self.shift_reg(6, 0x03, reg, 1),
                             (0x01, (False, True, False, False)))
            self.assertEqual(self.shift_reg(6, 0x80, reg, 1),
                             (0x40, (False, False, False, False)))
            self.assertEqual(self.shift_reg(6, 0x04, reg, 3),
                             (0x00, (True, True, False, False)))
            self.assertEqual(self.shift_reg(6, 0xff, reg, 4),
                             (0x0f, (False, True, False, False)))

    def test_shift_by_register_zero_clears_c_and_o(self):
        preset = {bc8183_cpu.FlagsRegister.CARRY: 1,
                  bc8183_cpu.FlagsRegister.OVERFLOW: 1}
        for op in (5, 6):
            self.assertEqual(self.shift_reg(op, 0x81, 'ci', 0, flags=preset),
                             (0x81, (False, False, True, False)))

    def test_shift_by_register_more_than_eight(self):
        self.assertEqual(self.shift_reg(5, 0xff, 'ci', 9),
                         (0x00, (True, False, False, True)))
        self.assertEqual(self.shift_reg(5, 0xff, 'di', 255),
                         (0x00, (True, False, False, True)))
        self.assertEqual(self.shift_reg(5, 0x00, 'ci', 9),
                         (0x00, (True, False, False, False)))
        self.assertEqual(self.shift_reg(6, 0xff, 'ci', 9),
                         (0x00, (True, False, False, False)))
        self.assertEqual(self.shift_reg(6, 0xff, 'di', 255),
                         (0x00, (True, False, False, False)))

    def test_shl_a_by_a_uses_old_a_as_count(self):
        # 58 15: the count is the old value of A
        cpu = self.run_code([0x58, 0x15], a=0x01)
        self.assertEqual(cpu.a.get(), 0x02)
        self.assertEqual(flags_of(cpu), (False, False, False, False))
        cpu = self.run_code([0x58, 0x15], a=0x03)
        self.assertEqual(cpu.a.get(), 0x18)
        self.assertEqual(flags_of(cpu), (False, False, False, False))
        # count 9 > 8: everything shifted out
        cpu = self.run_code([0x58, 0x15], a=0x09)
        self.assertEqual(cpu.a.get(), 0x00)
        self.assertEqual(flags_of(cpu), (True, False, False, True))

    def test_shr_a_by_a_uses_old_a_as_count(self):
        cpu = self.run_code([0x58, 0x16], a=0x01)
        self.assertEqual(cpu.a.get(), 0x00)
        self.assertEqual(flags_of(cpu), (True, True, False, False))
        cpu = self.run_code([0x58, 0x16], a=0x0c)
        self.assertEqual(cpu.a.get(), 0x00)
        self.assertEqual(flags_of(cpu), (True, False, False, False))
        cpu = self.run_code([0x58, 0x16], a=0xff)
        self.assertEqual(cpu.a.get(), 0x00)
        self.assertEqual(flags_of(cpu), (True, False, False, False))

    def shift16(self, code, start, **regs):
        cpu = self.run_code(code, cs=start >> 8, ci=start & 0xff, **regs)
        return self.pair(cpu), flags_of(cpu)

    def imm16(self, op, value, count):
        return [0x5f, 0xb0 | op, 0x80, count >> 8, count & 0xff]

    def test_shl16_imm_c_from_last_bit_out(self):
        self.assertEqual(self.shift16(self.imm16(5, 0, 2), 0x4000),
                         (0x0000, (True, True, False, True)))
        self.assertEqual(self.shift16(self.imm16(5, 0, 2), 0x8000),
                         (0x0000, (True, False, False, True)))
        self.assertEqual(self.shift16(self.imm16(5, 0, 1), 0x4000),
                         (0x8000, (False, False, True, True)))

    def test_shl16_by_16_and_more(self):
        self.assertEqual(self.shift16(self.imm16(5, 0, 16), 0x0001),
                         (0x0000, (True, True, False, True)))
        self.assertEqual(self.shift16(self.imm16(5, 0, 17), 0xffff),
                         (0x0000, (True, False, False, True)))

    def test_shl16_reg_large_count(self):
        self.assertEqual(self.shift16([0x5f, 0xbd, 0x80], 0xffff, ds=0xff, di=0xff),
                         (0x0000, (True, False, False, True)))
        self.assertEqual(self.shift16([0x5f, 0xbd, 0x80], 0x0000, ds=0xff, di=0xff),
                         (0x0000, (True, False, False, False)))
        self.assertEqual(self.shift16([0x5f, 0xbd, 0x80], 0x0001, ds=0x00, di=0x10),
                         (0x0000, (True, True, False, True)))

    def test_shr16_imm_c_from_last_bit_out(self):
        self.assertEqual(self.shift16(self.imm16(6, 0, 1), 0x0003),
                         (0x0001, (False, True, False, False)))
        self.assertEqual(self.shift16(self.imm16(6, 0, 3), 0x0004),
                         (0x0000, (True, True, False, False)))
        self.assertEqual(self.shift16(self.imm16(6, 0, 16), 0x8000),
                         (0x0000, (True, True, False, False)))
        self.assertEqual(self.shift16(self.imm16(6, 0, 17), 0xffff),
                         (0x0000, (True, False, False, False)))

    def test_shr16_reg_and_large_count(self):
        self.assertEqual(self.shift16([0x5f, 0xbe, 0x80], 0x0006, ds=0x00, di=0x02),
                         (0x0001, (False, True, False, False)))
        self.assertEqual(self.shift16([0x5f, 0xbe, 0x80], 0xffff, ds=0xff, di=0xff),
                         (0x0000, (True, False, False, False)))

    def test_shr16_by_zero_clears_c(self):
        cpu = self.run_code(self.imm16(6, 0, 0), cs=0x80, ci=0x01,
                            flags={bc8183_cpu.FlagsRegister.CARRY: 1})
        self.assertEqual(self.pair(cpu), 0x8001)
        self.assertEqual(flags_of(cpu), (False, False, True, False))

    def test_jmp_c_taken_after_shr_of_odd_value(self):
        # shr 1 of 0x03 sets C; `jmp c` (0x69 short) lands on MOV DI,0x22
        code = [0x56, 0x01, 0x69, 0x08, 0x15, 0x11, KIL]
        code += [0x00] * (0x08 - len(code)) + [0x15, 0x22]
        self.assertEqual(self.run_code(code, a=0x03).di.get(), 0x22)

    def test_jmp_c_not_taken_after_shr_of_even_value(self):
        code = [0x56, 0x01, 0x69, 0x08, 0x15, 0x11]
        self.assertEqual(self.run_code(code, a=0x04).di.get(), 0x11)

    def test_jmp_z_not_taken_after_shl_to_nonzero(self):
        # shl 1 of 0x40 gives A = 0x80, so Z = 0 (was 1 before #55)
        code = [0x55, 0x01, 0x68, 0x08, 0x15, 0x11]
        self.assertEqual(self.run_code(code, a=0x40).di.get(), 0x11)


class ShiftSignedOverflowTests(AluTestBase):
    """O after SHL/SHL16 is the signed overflow of `add x, x` (#161, E13);
    O after SHR/SHR16 is always 0 (logical shift)."""
    OVF = bc8183_cpu.FlagsRegister.OVERFLOW

    def run8(self, code, a, **regs):
        cpu = self.run_code(code, a=a, **regs)
        return cpu.a.get(), flags_of(cpu)

    def run16(self, code, start, **regs):
        cpu = self.run_code(code, cs=start >> 8, ci=start & 0xff, **regs)
        return (cpu.cs.get() << 8) | cpu.ci.get(), flags_of(cpu)

    def test_shl_by_one_equals_add_a_a_for_all_values(self):
        for v in range(256):
            self.assertEqual(self.run8([0x55, 0x01], v),
                             self.run8([0x58, 0x10], v), v)

    def test_shl16_by_one_equals_add_csci_dsdi_on_sample(self):
        sample = [0x0000, 0x0001, 0x3fff, 0x4000, 0x7fff, 0x8000, 0x8001,
                  0xbfff, 0xc000, 0xffff, 0x1234, 0xa5a5, 0x5a5a, 0xfffe]
        for v in sample:
            self.assertEqual(
                self.run16([0x5f, 0xb5, 0x80, 0x00, 0x01], v),
                self.run16([0x5f, 0xa8, 0x80], v, ds=v >> 8, di=v & 0xff), v)

    def test_shl_multi_bit_cases(self):
        # (value, count) -> (result, (Z, C, N, O))
        cases = [
            ((0x20, 2), (0x80, (False, False, True, True))),
            ((0xe0, 2), (0x80, (False, True, True, False))),
            ((0x90, 1), (0x20, (False, True, False, True))),
            ((0xc0, 1), (0x80, (False, True, True, False))),
            ((0x40, 1), (0x80, (False, False, True, True))),
        ]
        for (v, n), expected in cases:
            self.assertEqual(self.run8([0x55, n], v), expected, (v, n))
            # register-count form (58 r5, count in ci) gives the same flags
            self.assertEqual(self.run8([0x58, 0x45], v, ci=n), expected, (v, n))

    def test_shl16_multi_bit_cases(self):
        code2 = [0x5f, 0xb5, 0x80, 0x00, 0x02]
        self.assertEqual(self.run16(code2, 0x2000),
                         (0x8000, (False, False, True, True)))
        self.assertEqual(self.run16(code2, 0xe000),
                         (0x8000, (False, True, True, False)))
        self.assertEqual(self.run16([0x5f, 0xb5, 0x80, 0x00, 0x01], 0xc000),
                         (0x8000, (False, True, True, False)))
        # register count: ds:di = 2
        self.assertEqual(self.run16([0x5f, 0xbd, 0x80], 0x2000, ds=0, di=2),
                         (0x8000, (False, False, True, True)))

    def test_shr_clears_preset_o(self):
        preset = {self.OVF: 1}
        for n in (1, 3, 8, 9, 255):
            res, (z, c, neg, o) = self.run8([0x56, n], 0xff, flags=preset)
            self.assertFalse(o, n)
            self.assertEqual(res, 0xff >> min(n, 8), n)

    def test_shr16_clears_preset_o(self):
        preset = {self.OVF: 1}
        for n in (1, 3, 16, 17, 300):
            code = [0x5f, 0xb6, 0x80, n >> 8, n & 0xff]
            res, (z, c, neg, o) = self.run16(code, 0xffff, flags=preset)
            self.assertFalse(o, n)
            self.assertEqual(res, 0xffff >> min(n, 16), n)

if __name__ == '__main__':
    unittest.main()
