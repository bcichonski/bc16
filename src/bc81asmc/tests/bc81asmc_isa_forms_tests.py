"""Form-table test: every emitted form of the shared ISA table (src/bc8183_isa.py FORMS) is
assembled from a representative source line, checked against its record, and executed by the CPU.

For every `emitted` form this checks that
  * the grammar parser named for the form accepts the line,
  * the assembler emits exactly `length` bytes, the first nibble is the form's opcode and every
    fixed nibble / fixed bit of the layout (`InstructionForm.fixed`) matches,
  * the CPU, run for one instruction, consumes the same length (jumps and calls land on the
    target; `ret` on the address in the frame; `kil` stops).
It also checks that every grammar `m*` form parser maps to at least one ISA form and every
emitted ISA form is reached. The in-process assemble/execute harness of the opcode agreement
test is reused (loaded by path, that file is not changed).
"""
import importlib.util
import os
import re
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(os.path.dirname(TESTS_DIR))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

import parsy  # noqa: E402
import bc8183_isa as isa  # noqa: E402
import bc81asmc_grammar as asm_grammar  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    '_isa_forms_agreement_harness', os.path.join(TESTS_DIR, 'bc81asmc_opcode_agreement_tests.py'))
harness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness)

STACK_TOP = harness.STACK_TOP
CALL_FRAME = harness.CALL_FRAME
TGT = 'tgt'
# program shape of the jump/call forms: the instruction first, the target label after it
JUMP_PROGRAM = ['{0}', 'nop', 'nop', 'nop', 'tgt: nop', 'nop']


class Spec:
    def __init__(self, parser, lines, regs=None, flags=None, mem=None, pc=None, kill=False):
        self.parser = parser
        self.lines = lines
        self.regs = regs or {}
        self.flags = flags or {}
        self.mem = mem or {}
        self.pc = pc          # None: next instruction; TGT: the label; int: that address
        self.kill = kill


def jump(parser, instr, regs=None):
    return Spec(parser, [line.format(instr) for line in JUMP_PROGRAM], regs,
                flags={'z': 1}, pc=TGT)


def upper(name):
    return name.upper()


def specs():
    """Form key -> Spec, one representative source line per emitted form."""
    tgt = lambda lb, s, n: lb[TGT]                          # noqa: E731
    s = {
        'nop': Spec('mNOP', ['nop']),
        'kil': Spec('mKIL', ['kil'], pc=0, kill=True),
        'mov.imm8': Spec('mMOVri8', ['mov ci, 0x5a']),
        'mov.reg': Spec('mMOVrr', ['mov ci, a']),
        'mov.reg_mem': Spec('mMOVrm', ['mov a, #dsdi'], regs={'dsdi': 0x2010}),
        'mov.mem_reg': Spec('mMOVmr', ['mov #dsdi, a'], regs={'dsdi': 0x2010}),
        'psh': Spec('mPSH', ['psh a']),
        'pop': Spec('mPOP', ['pop ci'], regs={'sssi': STACK_TOP - 2}),
        'ret': Spec('mRET', ['ret'], regs={'sssi': STACK_TOP - 3}, pc=0x1234,
                    mem={STACK_TOP - 2: CALL_FRAME, STACK_TOP - 1: 0x12, STACK_TOP: 0x34}),
        'in.imm4': Spec('mIN', ['in a, #0x5']),
        'in.reg': Spec('mIN', ['in a, #ci'], regs={'ci': 7}),
        'out.reg': Spec('mOUT', ['out #ci, a'], regs={'ci': 7}),
        'out.imm8': Spec('mOUT', ['out #ci, 0x41'], regs={'ci': 7}),
        'jmp.label': jump('mJMP', 'jmp z, :tgt'),
        'jmp.pair': jump('mJMP', 'jmp z, dsdi', {'dsdi': tgt}),
        'jmr.label': jump('mJMR', 'jmr z, :tgt'),
        'jmr.reg': jump('mJMR', 'jmr z, ci', {'ci': tgt}),
        'jrx.label': jump('mJRX', 'jrx z, :tgt'),
        'jrx.pair': jump('mJRX', 'jrx z, cs', {'csci': lambda lb, st, n: lb[TGT] - st - 1}),
        'cal.label': jump('mCAL', 'cal :tgt'),
        'cal.pair': jump('mCAL', 'cal dsdi', {'dsdi': tgt}),
        'clr.label': jump('mCLR', 'clr :tgt'),
        'clr.pair': jump('mCLR', 'clr csci', {'csci': lambda lb, st, n: lb[TGT] - st - 2}),
    }
    for form in isa.FORMS:
        if not form.emitted or form.key in s:
            continue
        key, name, ops = form.key, form.mnemonic, form.operands
        up = upper(name)
        regs = {'a': 0x35, 'ci': 3, 'csci': 0x0123, 'dsdi': 5}
        if key.endswith('.imm8') and ops == ('imm8',):
            s[key] = Spec('m%si8' % up, ['%s 0x03' % name], regs)
        elif key.endswith('.reg') and ops == ('reg',):
            s[key] = Spec('m%sr' % up, ['%s ci' % name], regs)
        elif ops == ('a',):
            s[key] = Spec('m' + up, ['%s a' % name], regs)
        elif key.endswith('16.imm16'):
            s[key] = Spec('m%s16i16' % up, ['%s csci, 0x0005' % name], regs)
        elif key.endswith('16.imm8'):
            s[key] = Spec('m%s16i8' % up, ['%s dsdi, 0x05' % name], regs)
        elif key.endswith('16.reg'):
            s[key] = Spec('m%s16r' % up, ['%s csci, dsdi' % name], regs)
        elif ops == ('pair',):
            s[key] = Spec('m%s16' % up, ['%s csci' % name], regs)
    return s


SPECS = specs()
EMITTED = [form for form in isa.FORMS if form.emitted]


def grammar_form_parsers():
    return {name for name, obj in vars(asm_grammar).items()
            if re.fullmatch(r'm[A-Z][A-Za-z0-9]*', name) and isinstance(obj, parsy.Parser)
            and name not in harness.PARSERS_NOT_FORMS}


class IsaFormTableTests(unittest.TestCase):
    def test_every_emitted_form_has_a_representative_line(self):
        self.assertEqual(sorted(f.key for f in EMITTED if f.key not in SPECS), [])
        self.assertEqual(sorted(set(SPECS) - {f.key for f in EMITTED}), [])

    def test_every_emitted_form_assembles_to_its_record(self):
        for form in EMITTED:
            with self.subTest(form.key):
                spec = SPECS[form.key]
                ast, code, labels = harness.assemble(spec.lines)
                start = ast[0].addr
                self.assertEqual(start, 0)
                single = getattr(asm_grammar, spec.parser).parse(spec.lines[0])
                self.assertIs(type(single), type(ast[0]), 'grammar parser ' + spec.parser)
                length = (ast[1].addr if len(ast) > 1 else len(code)) - start
                self.assertEqual(length, form.length, 'assembled length')
                nibbles = ''.join('{0:02x}'.format(b) for b in code[:form.length])
                self.assertEqual(int(nibbles[0], 16), form.opcode, 'opcode nibble')
                for index, mask, value in form.fixed:
                    self.assertEqual(int(nibbles[index], 16) & mask, value,
                                     'fixed nibble %d of %s (%s)' % (index, form.layout, nibbles))

    def test_the_cpu_consumes_the_length_of_every_emitted_form(self):
        for form in EMITTED:
            with self.subTest(form.key):
                spec = SPECS[form.key]
                ast, code, labels = harness.assemble(spec.lines)
                regs = {k: harness._value(v, labels, 0, form.length) for k, v in spec.regs.items()}
                mem = {k: v for k, v in spec.mem.items()}
                cpu, _, _ = harness.execute(code, 0, labels, form.length, regs, spec.flags,
                                            mem, {5: 0x42, 7: 0x42})
                if spec.pc is None:
                    want = form.length
                elif spec.pc == TGT:
                    want = labels[TGT]
                else:
                    want = spec.pc
                self.assertEqual(cpu.pc.get(), want, 'pc after one instruction')
                self.assertEqual(cpu.kill, spec.kill)

    def test_every_grammar_form_parser_maps_to_an_isa_form(self):
        parsers = grammar_form_parsers()
        self.assertGreater(len(parsers), 50)
        mapped = {spec.parser for spec in SPECS.values()}
        self.assertEqual(sorted(parsers - mapped), [], 'grammar form without an ISA form')
        self.assertEqual(sorted(mapped - parsers), [], 'ISA form names a parser not in the grammar')

    def test_the_non_emitted_alias_is_not_assembled(self):
        for form in isa.FORMS:
            if not form.emitted:
                self.assertNotIn(form.key, SPECS)


if __name__ == '__main__':
    unittest.main()
