import unittest

from parsy import *
from bc81asmc_grammar import *

debug = True

class TestGrammar(unittest.TestCase):
    '''Test the implementation of ast parser.'''

    def test_hex_imm8(self):
        self.assertEqual(
            heximm8.parse('0x8b'),
            0x8b)

    def test_comment(self):
        self.assertEqual(
            comment.parse('; everything can have comment'),
            '; everything can have comment')

    def test_ignore_spaces(self):
        self.assertEqual(
            ignore.parse('   '),
            '   ')

    def test_mnemonic_nop(self):
        self.assertEqual(
            mnemonic.parse('nop'),
            NOP('nop'))

    def test_paramdb_string(self):
        val = paramdb.parse("'quotedstring'")
        if debug:
            print(val)
        self.assertEqual(
            val,
            "quotedstring")

    def test_paramdb_heximm8(self):
        val = paramdb.parse("0xaf")
        if debug:
            print(val)
        self.assertEqual(
            val,
            0xaf)

    def test_jmpregargs(self):
        val = jmpregargs.parse("dsdi")
        if debug:
            print(val)
        self.assertEqual(
            val,
            "dsdi")

    def test_directive_db(self):
        val = directive.parse(".db 'quoted', 0xff, 'new', 0x00")
        if debug:
            print(val)
        self.assertEqual(
            val,
            DB(['quoted', 0xff, 'new', 0x00]))

    def test_directive_mv(self):
        val = directive.parse(".mv af, :label")
        if debug:
            print(val)
        self.assertEqual(
            val,
            MV('af', ':label'))

    def test_directive_org(self):
        val = directive.parse('.org 0x0100')
        if debug:
            print(val)
        self.assertEqual(
            val,
            ORG(0x0100))

    def test_line_with_label_spaces_and_comment(self):
        res = line.parse(' label:  nop ;comment\n')
        self.assertEqual(
            res,
            NOP('nop'))
        self.assertEqual(res.label, 'label')

    def test_line_with_spaces_and_comment(self):
        res = line.parse('         nop ;comment\n')
        self.assertEqual(
            res,
            NOP('nop'))
        self.assertFalse(hasattr(res, 'label'))

    def test_inc_a(self):
        self.assertEqual(
            mnemonic.parse('inc a'),
            INC('a'))
        
    def test_inc16(self):
        self.assertEqual(
            mnemonic.parse('inc dsdi'),
            INC16('dsdi'))
    
    def test_dec16(self):
        self.assertEqual(
            mnemonic.parse('dec csci'),
            DEC16('csci'))
        
    def test_not16(self):
        self.assertEqual(
            mnemonic.parse('not af'),
            NOT16('af'))

    def test_dec_a(self):
        self.assertEqual(
            mnemonic.parse('dec a'),
            DEC('a'))

    def test_not_a(self):
        self.assertEqual(
            mnemonic.parse('not a'),
            NOT('a'))

    def test_mov_r_i8(self):
        self.assertEqual(
            mMOVri8.parse('mov si, 0xff'),
            MOVRI8('si',0xff))

    def test_mov_r_r(self):
        self.assertEqual(
            mMOVrr.parse('mov cs, di'),
            MOVRR('cs','di'))

    def test_mov_r_m(self):
        self.assertEqual(
            mMOVrm.parse('mov ss, #dsdi'),
            MOVRM('ss','dsdi'))

    def test_mov_m_r(self):
        self.assertEqual(
            mMOVmr.parse('mov #dsdi, a'),
            MOVMR('dsdi', 'a'))

    def test_add_i8(self):
        self.assertEqual(
            mADDi8.parse('add 0xad'),
            CLC_A_IMM('add', 0xad))

    def test_add_r(self):
        self.assertEqual(
            mADDr.parse('add cs'),
            CLC_A_R('add', 'cs'))
        
    def test_add16_i16(self):
        self.assertEqual(
            mADD16i16.parse('add csci, 0xadbc'),
            CLC16_R_IMM('add', 'csci', 0xadbc))

    def test_add16_rr(self):
        self.assertEqual(
            mADD16r.parse('add csci, dsdi'),
            CLC16_R_R('add', 'csci', 'dsdi'))

    def test_sub_i8(self):
        self.assertEqual(
            mSUBi8.parse('sub 0xaf'),
            CLC_A_IMM('sub', 0xaf))

    def test_sub_r(self):
        self.assertEqual(
            mSUBr.parse('sub a'),
            CLC_A_R('sub', 'a'))
        
    def test_sub16_i16(self):
        self.assertEqual(
            mSUB16i16.parse('sub csci, 0xadbc'),
            CLC16_R_IMM('sub', 'csci', 0xadbc))

    def test_sub16_rr(self):
        self.assertEqual(
            mSUB16r.parse('sub csci, dsdi'),
            CLC16_R_R('sub', 'csci', 'dsdi'))
        
    def test_mul16_i16(self):
        self.assertEqual(
            mMUL16i16.parse('mul csci, 0xadbc'),
            CLC16_R_IMM('mul', 'csci', 0xadbc))

    def test_mul16_rr(self):
        self.assertEqual(
            mMUL16r.parse('mul csci, dsdi'),
            CLC16_R_R('mul', 'csci', 'dsdi'))
        
    def test_div16_i16(self):
        self.assertEqual(
            mDIV16i16.parse('div csci, 0xadbc'),
            CLC16_R_IMM('div', 'csci', 0xadbc))

    def test_div16_rr(self):
        self.assertEqual(
            mDIV16r.parse('div csci, dsdi'),
            CLC16_R_R('div', 'csci', 'dsdi'))
        
    def test_mod16_i16(self):
        self.assertEqual(
            mMOD16i16.parse('mod csci, 0xadbc'),
            CLC16_R_IMM('mod', 'csci', 0xadbc))

    def test_mod16_rr(self):
        self.assertEqual(
            mMOD16r.parse('mod csci, dsdi'),
            CLC16_R_R('mod', 'csci', 'dsdi'))
        
    def test_and16_i16(self):
        self.assertEqual(
            mAND16i16.parse('and csci, 0xadbc'),
            CLC16_R_IMM('and', 'csci', 0xadbc))

    def test_and16_rr(self):
        self.assertEqual(
            mAND16r.parse('and csci, dsdi'),
            CLC16_R_R('and', 'csci', 'dsdi'))
        
    def test_or16_i16(self):
        self.assertEqual(
            mOR16i16.parse('or csci, 0xadbc'),
            CLC16_R_IMM('or', 'csci', 0xadbc))

    def test_or16_rr(self):
        self.assertEqual(
            mOR16r.parse('or csci, dsdi'),
            CLC16_R_R('or', 'csci', 'dsdi'))
        
    def test_xor16_i16(self):
        self.assertEqual(
            mXOR16i16.parse('xor csci, 0xadbc'),
            CLC16_R_IMM('xor', 'csci', 0xadbc))

    def test_xor16_rr(self):
        self.assertEqual(
            mXOR16r.parse('xor csci, dsdi'),
            CLC16_R_R('xor', 'csci', 'dsdi'))
        
    def test_shl16_i16(self):
        self.assertEqual(
            mSHL16i8.parse('shl csci, 0xad'),
            CLC16_R_IMM('shl', 'csci', 0xad))

    def test_shl16_rr(self):
        self.assertEqual(
            mSHL16r.parse('shl csci, dsdi'),
            CLC16_R_R('shl', 'csci', 'dsdi'))
        
    def test_shr16_i16(self):
        self.assertEqual(
            mSHR16i8.parse('shr csci, 0xad'),
            CLC16_R_IMM('shr', 'csci', 0xad))

    def test_shr16_rr(self):
        self.assertEqual(
            mSHR16r.parse('shr csci, dsdi'),
            CLC16_R_R('shr', 'csci', 'dsdi'))

    def test_and_i8(self):
        self.assertEqual(
            mANDi8.parse('and 0xaa'),
            CLC_A_IMM('and', 0xaa))

    def test_and_r(self):
        self.assertEqual(
            mANDr.parse('and di'),
            CLC_A_R('and', 'di'))

    def test_or_i8(self):
        self.assertEqual(
            mORi8.parse('or 0x1d'),
            CLC_A_IMM('or', 0x1d))

    def test_or_r(self):
        self.assertEqual(
            mORr.parse('or ds'),
            CLC_A_R('or', 'ds'))

    def test_xor_i8(self):
        self.assertEqual(
            mXORi8.parse('xor 0x10'),
            CLC_A_IMM('xor', 0x10))

    def test_xor_r(self):
        self.assertEqual(
            mXORr.parse('xor cs'),
            CLC_A_R('xor', 'cs'))

    def test_shl_i8(self):
        self.assertEqual(
            mSHLi8.parse('shl 0x05'),
            CLC_A_IMM('shl', 0x05))

    def test_shl_r(self):
        self.assertEqual(
            mSHLr.parse('shl cs'),
            CLC_A_R('shl', 'cs'))

    def test_shr_i8(self):
        self.assertEqual(
            mSHRi8.parse('shr 0x04'),
            CLC_A_IMM('shr', 0x04))

    def test_shr_r(self):
        self.assertEqual(
            mSHRr.parse('shr ci'),
            CLC_A_R('shr', 'ci'))

    def test_jmp_reg(self):
        self.assertEqual(
            mJMP.parse('jmp nz, dsdi'),
            JMP('nz', 'dsdi'))

    def test_jmp_lbl(self):
        self.assertEqual(
            mJMP.parse('jmp c, :label'),
            JMP('c', ':label'))

    def test_jmr_reg(self):
        self.assertEqual(
            mJMR.parse('jmr nz, di'),
            JMR('nz', 'di'))

    def test_jmr_lbl(self):
        self.assertEqual(
            mJMR.parse('jmr c, :label'),
            JMR('c', ':label'))
        
    def test_jrx_reg(self):
        self.assertEqual(
            mJRX.parse('jrx nz, di'),
            JRX('nz', 'di'))

    def test_jrx_lbl(self):
        self.assertEqual(
            mJRX.parse('jrx c, :label'),
            JRX('c', ':label'))

    def test_psh_r(self):
        self.assertEqual(
            mPSH.parse('psh ds'),
            PSH('ds'))

    def test_pop_r(self):
        self.assertEqual(
            mPOP.parse('pop a'),
            POP('a'))

    def test_cal_reg(self):
        self.assertEqual(
            mCAL.parse('cal csci'),
            CAL('csci'))

    def test_cal_addr(self):
        self.assertEqual(
            mCAL.parse('cal :label'),
            CAL(':label'))
        
    def test_clr_addr(self):
        self.assertEqual(
            mCLR.parse('clr :label'),
            CLR(':label'))
        
    def test_clr_reg(self):
        self.assertEqual(
            mCLR.parse('clr dsdi'),
            CLR('dsdi'))

    def test_ret(self):
        self.assertEqual(
            mRET.parse('ret'),
            RET('ret'))

    def test_in_reg(self):
        self.assertEqual(
            mIN.parse('in a, #di'),
            IN('a', 'di'))

    def test_in_i8(self):
        self.assertEqual(
            mIN.parse('in a, #0xd'),
            IN('a', 0xd))

    def test_out_reg(self):
        self.assertEqual(
            mOUT.parse('out #ds, di'),
            OUT('ds', 'di'))

    def test_out_i8(self):
        self.assertEqual(
            mOUT.parse('out #cs, 0xad'),
            OUT('cs', 0xad))

    def test_kil(self):
        self.assertEqual(
            mKIL.parse('kil'),
            KIL('kil'))

if __name__ == '__main__':
    unittest.main()
