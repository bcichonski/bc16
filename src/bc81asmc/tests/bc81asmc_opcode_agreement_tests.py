"""Opcode agreement test: assembler encodings versus CPU decoding.

Every instruction form accepted by the assembler grammar is assembled in-process from
source text (grammar -> AST -> two-pass compile) and the resulting bytes are executed
for exactly one instruction on the emulated CPU.  The test checks that the CPU

  * advances to the expected address (after the instruction, or the jump/call target),
  * decodes the same instruction length the assembler emitted,
  * produces the expected register / memory / port effects.

Known disagreements are handled as follows (plan 48, D2/D7):
  * `out #r, imm` encodes wrongly (#11)            -> expectedFailure
  * negated `jrx` never negates in the CPU (#4)    -> expectedFailure (+ decode-only test)
  * other findings are pinned in `PinnedFindingsTests` with a D7 comment.
"""
import contextlib
import importlib.util
import io
import os
import re
import sys
import unittest
from dataclasses import dataclass, field
from typing import Any

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASM_DIR = os.path.join(SRC_DIR, 'bc81asmc')
if ASM_DIR not in sys.path:
    sys.path.append(ASM_DIR)
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)  # for `from bc64 import ...` when run from src/bc81asmc/

import parsy  # noqa: E402
import bc81asmc_ast as asm_ast  # noqa: E402
import bc81asmc_diag as asm_diag  # noqa: E402
import bc81asmc_grammar as asm_grammar  # noqa: E402
from bc64 import bc8183_cpu  # noqa: E402
from bc64 import bc64_env  # noqa: E402
from bc64 import bc64_mem  # noqa: E402

# bc81asmc.py is loaded by path: `import bc81asmc` would resolve to the package directory.
_spec = importlib.util.spec_from_file_location(
    '_bc81asmc_driver', os.path.join(ASM_DIR, 'bc81asmc.py'))
asm_driver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(asm_driver)

FLAG_BITS = {'z': bc8183_cpu.FlagsRegister.ZERO,
             'c': bc8183_cpu.FlagsRegister.CARRY,
             'n': bc8183_cpu.FlagsRegister.NEGATIVE,
             'o': bc8183_cpu.FlagsRegister.OVERFLOW}
PAIRS = {'csci': ('cs', 'ci'), 'dsdi': ('ds', 'di'), 'sssi': ('ss', 'si'), 'af': ('a', 'f')}
STACK_TOP = 0xffff          # memory is 0x10000 bytes, so SS:SI starts at 0xffff
CALL_FRAME = 0xc0


# ----------------------------------------------------------------------------------------
# harness
# ----------------------------------------------------------------------------------------
def assemble(lines):
    """Assemble source lines in-process. Returns (ast, bytes, labels)."""
    text = "\n".join(lines) + "\n"
    with contextlib.redirect_stdout(io.StringIO()):
        ast = asm_grammar.program.parse(text)
        context = asm_driver.compile(ast, False)
    labels = {t.label: t.addr for t in ast if hasattr(t, 'label')}
    return ast, bytes(context.bytes), labels


class FakeIo:
    def __init__(self, inputs):
        self.inputs = inputs
        self.writes = []

    def read_byte(self, port):
        return self.inputs.get(port, 0)

    def write_byte(self, port, val):
        self.writes.append((port, val))


def _value(x, labels, start, n):
    return x(labels, start, n) if callable(x) else x


def _get_reg(cpu, name):
    if name in PAIRS:
        hi, lo = PAIRS[name]
        return (getattr(cpu, hi).get() << 8) | getattr(cpu, lo).get()
    return getattr(cpu, name).get()


def _set_reg(cpu, name, val):
    if name in PAIRS:
        hi, lo = PAIRS[name]
        getattr(cpu, hi).set(val >> 8)
        getattr(cpu, lo).set(val & 0xff)
    else:
        getattr(cpu, name).set(val)


def execute(code, start, labels, n, regs, flags, mem, inputs):
    """Run exactly one instruction at `start`; returns (cpu, membus, io)."""
    env = bc64_env.Environment(debug=False)
    membus = bc64_mem.MemBus(env, 0x10000)
    for i, b in enumerate(code):
        membus.write_byte(i, b)
    for addr, val in mem.items():
        membus.write_byte(_value(addr, labels, start, n), _value(val, labels, start, n))
    fake_io = FakeIo(inputs)
    cpu = bc8183_cpu.Bc8183(membus, fake_io, False)
    for name, val in regs.items():
        _set_reg(cpu, name, _value(val, labels, start, n))
    for flag, bit in FLAG_BITS.items():
        cpu.f.set_flag(bit, int(flags.get(flag, 0)))
    cpu.pc.set(start)
    cpu.inc_pc(0)
    with contextlib.redirect_stdout(io.StringIO()):
        cpu.run_next_opcode()
    return cpu, membus, fake_io


@dataclass
class Case:
    name: str
    parser: str                 # grammar parser object that must accept the instruction line
    prog: list                  # assembler source lines
    n: int                      # expected instruction length in bytes
    idx: int = 0                # index of the instruction under test in `prog`
    regs: dict = field(default_factory=dict)
    flags: dict = field(default_factory=dict)
    mem: dict = field(default_factory=dict)
    inputs: dict = field(default_factory=dict)
    pc: Any = None              # None: start + n; str: label; int; or callable(labels, start, n)
    out_regs: dict = field(default_factory=dict)
    out_mem: dict = field(default_factory=dict)
    out_writes: list = field(default_factory=list)
    kill: bool = False


def run_case(testcase, case):
    ast, code, labels = assemble(case.prog)
    start = ast[case.idx].addr
    # instruction length as the assembler laid it out
    nxt = ast[case.idx + 1].addr if case.idx + 1 < len(ast) else len(code)
    testcase.assertEqual(nxt - start, case.n, 'assembled instruction length')
    cpu, membus, fake_io = execute(code, start, labels, case.n, case.regs, case.flags,
                                   case.mem, case.inputs)
    if case.pc is None:
        want_pc = start + case.n
    elif isinstance(case.pc, str):
        want_pc = labels[case.pc]
    else:
        want_pc = _value(case.pc, labels, start, case.n)
    testcase.assertEqual(cpu.pc.get(), want_pc, 'pc after instruction (0x{:04x} expected)'.format(want_pc))
    for name, val in case.out_regs.items():
        testcase.assertEqual(_get_reg(cpu, name), _value(val, labels, start, case.n), 'register ' + name)
    for addr, val in case.out_mem.items():
        a = _value(addr, labels, start, case.n)
        testcase.assertEqual(membus.read_byte(a), _value(val, labels, start, case.n),
                             'memory at 0x{:04x}'.format(a))
    testcase.assertEqual(fake_io.writes, case.out_writes)
    testcase.assertEqual(cpu.kill, case.kill)


# ----------------------------------------------------------------------------------------
# case table
# ----------------------------------------------------------------------------------------
NOPS = ['nop'] * 4
FWD_TEMPLATE = lambda instr: ([instr] + NOPS[:3] + ['tgt: nop', 'nop'], 0)           # noqa: E731
BWD_TEMPLATE = lambda instr: (['nop', 'nop', 'tgt: nop', 'nop', instr, 'nop'], 4)    # noqa: E731
TARGET = lambda lb, s, n: lb['tgt']                                                  # noqa: E731

# test mnemonic -> (flag, flag value that makes the test true)
LOGIC_TESTS = {'z': ('z', 1), 'nz': ('z', 0), 'c': ('c', 1), 'nc': ('c', 0),
               'n': ('n', 1), 'nn': ('n', 0), 'o': ('o', 1), 'no': ('o', 0)}
NEGATED = {'nz', 'nc', 'nn', 'no'}

ALU8_OPS = {'add': lambda a, b: a + b, 'sub': lambda a, b: a - b, 'and': lambda a, b: a & b,
            'or': lambda a, b: a | b, 'xor': lambda a, b: a ^ b, 'shl': lambda a, b: a << b,
            'shr': lambda a, b: a >> b}
ALU16_OPS = dict(ALU8_OPS, mul=lambda a, b: a * b, div=lambda a, b: a // b, mod=lambda a, b: a % b)
SHIFTS = ('shl', 'shr')


def simple_cases():
    cases = []

    def add(*args, **kw):
        cases.append(Case(*args, **kw))

    add('nop', 'mNOP', ['nop'], 1)
    add('kil', 'mKIL', ['kil'], 1, pc=0, kill=True)

    # 8-bit accumulator ops
    add('inc a', 'mINC', ['inc a'], 1, regs={'a': 0x41}, out_regs={'a': 0x42})
    add('dec a', 'mDEC', ['dec a'], 1, regs={'a': 0x41}, out_regs={'a': 0x40})
    add('not a', 'mNOT', ['not a'], 1, regs={'a': 0x0f}, out_regs={'a': 0xf0})
    for op, fn in ALU8_OPS.items():
        add(f'{op} imm8', f'm{op.upper()}i8', [f'{op} 0x03'], 2,
            regs={'a': 0x35}, out_regs={'a': fn(0x35, 3) & 0xff})
        add(f'{op} reg', f'm{op.upper()}r', [f'{op} ci'], 2,
            regs={'a': 0x35, 'ci': 3}, out_regs={'a': fn(0x35, 3) & 0xff, 'ci': 3})

    # 16-bit ops
    x, y = 0x0123, 0x0005
    for op, fn in ALU16_OPS.items():
        up = op.upper()
        res = fn(x, y) & 0xffff
        imm_parser = f'm{up}16i8' if op in SHIFTS else f'm{up}16i16'
        imm_text = '0x05' if op in SHIFTS else '0x0005'
        imm_len = 5
        add(f'{op}16 csci,imm', imm_parser, [f'{op} csci, {imm_text}'], imm_len,
            regs={'csci': x}, out_regs={'csci': res})
        add(f'{op}16 dsdi,imm', imm_parser, [f'{op} dsdi, {imm_text}'], imm_len,
            regs={'dsdi': x}, out_regs={'dsdi': res})
        add(f'{op}16 csci,dsdi', f'm{up}16r', [f'{op} csci, dsdi'], 3,
            regs={'csci': x, 'dsdi': y}, out_regs={'csci': res, 'dsdi': y})
        add(f'{op}16 dsdi,csci', f'm{up}16r', [f'{op} dsdi, csci'], 3,
            regs={'dsdi': x, 'csci': y}, out_regs={'dsdi': res, 'csci': y})
    # accumulator pair (a:f); F is rewritten by the flags, so only A is compared
    add('add16 af,imm', 'mADD16i16', ['add af, 0x0100'], 5, regs={'a': 0x01}, out_regs={'a': 0x02})
    add('add16 af,csci', 'mADD16r', ['add af, csci'], 3,
        regs={'a': 0x01, 'csci': 0x0100}, out_regs={'a': 0x02})
    for reg in ('csci', 'dsdi'):
        add(f'inc16 {reg}', 'mINC16', [f'inc {reg}'], 3, regs={reg: 0x01ff}, out_regs={reg: 0x0200})
        add(f'dec16 {reg}', 'mDEC16', [f'dec {reg}'], 3, regs={reg: 0x0200}, out_regs={reg: 0x01ff})
        add(f'not16 {reg}', 'mNOT16', [f'not {reg}'], 3, regs={reg: 0x0ff0}, out_regs={reg: 0xf00f})

    # MOV
    add('mov r,imm8', 'mMOVri8', ['mov ci, 0x5a'], 2, out_regs={'ci': 0x5a})
    add('mov a,imm8', 'mMOVri8', ['mov a, 0x41'], 2, out_regs={'a': 0x41})
    add('mov r,r', 'mMOVrr', ['mov ci, a'], 2, regs={'a': 0x69}, out_regs={'ci': 0x69, 'a': 0x69})
    add('mov r,r 2', 'mMOVrr', ['mov ds, di'], 2, regs={'di': 0x33}, out_regs={'ds': 0x33})
    for pair, (hi, lo) in (('csci', ('cs', 'ci')), ('dsdi', ('ds', 'di')), ('sssi', ('ss', 'si'))):
        addr = 0x2010
        add(f'mov r,#{pair}', 'mMOVrm', [f'mov a, #{pair}'], 2,
            regs={pair: addr}, mem={addr: 0x77}, out_regs={'a': 0x77})
        add(f'mov #{pair},r', 'mMOVmr', [f'mov #{pair}, a'], 2,
            regs={pair: addr, 'a': 0x5c}, out_mem={addr: 0x5c})

    # stack
    add('psh a', 'mPSH', ['psh a'], 1, regs={'a': 0x6e},
        out_mem={STACK_TOP: 0x6e}, out_regs={'sssi': STACK_TOP - 2})
    add('pop ci', 'mPOP', ['pop ci'], 1, regs={'sssi': STACK_TOP - 2},
        mem={STACK_TOP: 0x6e}, out_regs={'ci': 0x6e, 'sssi': STACK_TOP})
    add('ret', 'mRET', ['ret'], 1, regs={'sssi': STACK_TOP - 3},
        mem={STACK_TOP - 2: CALL_FRAME, STACK_TOP - 1: 0x12, STACK_TOP: 0x34},
        pc=0x1234, out_regs={'sssi': STACK_TOP})

    # port I/O
    add('in r,#imm4', 'mIN', ['in a, #0x5'], 2, inputs={5: 0x42}, out_regs={'a': 0x42})
    add('in r,#reg', 'mIN', ['in a, #ci'], 2, regs={'ci': 7}, inputs={7: 0x42}, out_regs={'a': 0x42})
    add('in ci,#reg di', 'mIN', ['in ci, #di'], 2, regs={'di': 9}, inputs={9: 0x24}, out_regs={'ci': 0x24})
    add('out #r,reg', 'mOUT', ['out #ci, a'], 2, regs={'ci': 7, 'a': 0x42}, out_writes=[(7, 0x42)])
    add('out #r,reg 2', 'mOUT', ['out #di, ds'], 2, regs={'di': 3, 'ds': 0x11}, out_writes=[(3, 0x11)])
    # `out #r, imm` is NOT here: known disagreement #11, see OutImmediateTests.
    return cases


def _flags(test, taken):
    flag, want = LOGIC_TESTS[test]
    return {flag: want if taken else 1 - want}


def jump_cases(include_negated_jrx=False):
    """JMP / JMR / JRX in every test and operand form, taken and not taken."""
    cases = []
    for test in LOGIC_TESTS:
        for taken in (True, False):
            tag = f'{test} {"taken" if taken else "not-taken"}'
            flags = _flags(test, taken)

            def go(name, parser, instr, n, template, regs=None, direction=''):
                prog, idx = template(instr)
                target = TARGET if taken else None
                cases.append(Case(f'{name} {tag}{direction}', parser, prog, n, idx=idx,
                                  regs=regs or {}, flags=flags, pc=target))

            # jmp: short (label) and register forms; the label stays in the cs page (cs = 0)
            go('jmp label', 'mJMP', f'jmp {test}, :tgt', 2, FWD_TEMPLATE)
            for pair in ('csci', 'dsdi'):
                go(f'jmp {pair}', 'mJMP', f'jmp {test}, {pair}', 2, FWD_TEMPLATE, {pair: TARGET})

            for direction, template in ((' fwd', FWD_TEMPLATE), (' bwd', BWD_TEMPLATE)):
                # jmr: 8 bit sign-magnitude offset relative to the instruction address
                go('jmr label', 'mJMR', f'jmr {test}, :tgt', 2, template, direction=direction)
                if direction == ' fwd':
                    rel = lambda lb, s, n: lb['tgt'] - s                                  # noqa: E731
                else:
                    rel = lambda lb, s, n: 0x80 | (s - lb['tgt'])                        # noqa: E731
                go('jmr reg', 'mJMR', f'jmr {test}, ci', 2, template, {'ci': rel}, direction)

                # jrx: 15 bit offset; the register form is relative to instruction address + 1
                if test in NEGATED and not include_negated_jrx:
                    continue
                go('jrx label', 'mJRX', f'jrx {test}, :tgt', 4, template, direction=direction)
                if direction == ' fwd':
                    jrel = lambda lb, s, n: lb['tgt'] - s - 1                            # noqa: E731
                else:
                    jrel = lambda lb, s, n: 0x8000 | (s + 1 - lb['tgt'])                 # noqa: E731
                go('jrx reg', 'mJRX', f'jrx {test}, cs', 2, template, {'csci': jrel}, direction)

    # remaining register operands of jmp
    prog, idx = FWD_TEMPLATE('jmp z, sssi')
    cases.append(Case('jmp sssi z taken', 'mJMP', prog, 2, idx=idx, flags={'z': 1},
                      regs={'sssi': TARGET}, pc=TARGET))
    # `af` is A:F and F holds the flags (z=1 -> F = 0x01), so with A = 0 the target is 0x0001
    cases.append(Case('jmp af z taken', 'mJMP', ['nop', 'jmp z, af', 'nop'], 2, idx=1,
                      flags={'z': 1}, regs={'a': 0}, pc=0x0001))
    return cases


def call_cases():
    cases = []
    ret = lambda lb, s, n: s + n                                                           # noqa: E731
    frame = lambda lb, s, n: {STACK_TOP: (s + n) & 0xff, STACK_TOP - 1: (s + n) >> 8,      # noqa: E731
                              STACK_TOP - 2: CALL_FRAME}
    for direction, template in ((' fwd', FWD_TEMPLATE), (' bwd', BWD_TEMPLATE)):
        def go(name, parser, instr, n, regs=None):
            prog, idx = template(instr)
            c = Case(name + direction, parser, prog, n, idx=idx, regs=regs or {}, pc=TARGET,
                     out_regs={'sssi': STACK_TOP - 3})
            c.out_mem = {STACK_TOP: lambda lb, s, n_: (s + n_) & 0xff,
                         STACK_TOP - 1: lambda lb, s, n_: (s + n_) >> 8,
                         STACK_TOP - 2: CALL_FRAME}
            cases.append(c)

        go('cal label', 'mCAL', 'cal :tgt', 3)
        for pair in ('csci', 'dsdi'):
            go(f'cal {pair}', 'mCAL', f'cal {pair}', 2, {pair: TARGET})
        # clr: the offset is relative to the instruction address + 2 (D1)
        go('clr label', 'mCLR', 'clr :tgt', 3)
        if direction == ' fwd':
            crel = lambda lb, s, n: lb['tgt'] - s - 2                                      # noqa: E731
        else:
            crel = lambda lb, s, n: 0x8000 | (s + 2 - lb['tgt'])                           # noqa: E731
        for pair in ('csci', 'dsdi'):
            go(f'clr {pair}', 'mCLR', f'clr {pair}', 2, {pair: crel})
    return cases


ALL_CASES = simple_cases() + jump_cases() + call_cases()
PARSERS_NOT_FORMS = {'mCLC'}     # alternation of the CLC forms, not a form itself


class AssembledCases:
    """Assemble each case once; shared by several tests."""
    cache = {}

    @classmethod
    def get(cls, case):
        if case.name not in cls.cache:
            cls.cache[case.name] = assemble(case.prog)
        return cls.cache[case.name]


# ----------------------------------------------------------------------------------------
# tests
# ----------------------------------------------------------------------------------------
class OpcodeAgreementTests(unittest.TestCase):
    def test_every_form_agrees_between_assembler_and_cpu(self):
        names = [c.name for c in ALL_CASES]
        self.assertEqual(len(names), len(set(names)), 'case names must be unique')
        for case in ALL_CASES:
            with self.subTest(case.name):
                run_case(self, case)

    def test_case_parser_accepts_exactly_the_instruction_line(self):
        """The named grammar parser parses the line, and the whole-program parser agrees."""
        for case in ALL_CASES:
            with self.subTest(case.name):
                ast, _, _ = AssembledCases.get(case)
                parser = getattr(asm_grammar, case.parser)
                self.assertIsInstance(parser, parsy.Parser)
                single = parser.parse(case.prog[case.idx])
                self.assertEqual(single, ast[case.idx])
                self.assertIs(type(single), type(ast[case.idx]))


class GrammarCoverageGuardTests(unittest.TestCase):
    @staticmethod
    def grammar_form_parsers():
        return {name for name, obj in vars(asm_grammar).items()
                if re.fullmatch(r'm[A-Z][A-Za-z0-9]*', name) and isinstance(obj, parsy.Parser)
                and name not in PARSERS_NOT_FORMS}

    def test_every_grammar_mnemonic_form_is_in_the_table(self):
        forms = self.grammar_form_parsers()
        self.assertGreater(len(forms), 50, 'guard found suspiciously few grammar forms')
        covered = {c.parser for c in ALL_CASES}
        self.assertEqual(sorted(forms - covered), [],
                         'grammar forms missing from the opcode agreement table')
        self.assertEqual(sorted(covered - forms), [], 'table names a parser not in the grammar')

    def test_every_ast_instruction_class_is_assembled(self):
        def concrete(cls):
            for sub in cls.__subclasses__():
                yield sub
                yield from concrete(sub)
        classes = {c for c in concrete(asm_ast.Instruction) if c.__module__ == asm_ast.__name__}
        produced = {type(t) for case in ALL_CASES for t in AssembledCases.get(case)[0]}
        self.assertEqual(sorted(c.__name__ for c in classes - produced), [])

    def test_every_cpu_opcode_is_exercised(self):
        cpu = bc8183_cpu.Bc8183(bc64_mem.MemBus(bc64_env.Environment(debug=False), 0x100), None, False)
        seen = set()
        for case in ALL_CASES:
            ast, code, _ = AssembledCases.get(case)
            seen.add(code[ast[case.idx].addr] >> 4)
        self.assertEqual(sorted(set(cpu.instructions) - seen), [])

    def test_every_jump_test_and_alu_operation_is_exercised(self):
        tests_seen = {c.prog[c.idx].split()[1].rstrip(',') for c in ALL_CASES
                      if c.prog[c.idx].split()[0] in ('jmp', 'jmr', 'jrx')}
        self.assertEqual(tests_seen, set(LOGIC_TESTS))
        ops16 = {c.prog[c.idx].split()[0] for c in ALL_CASES if c.n in (3, 5) and c.parser.endswith(('16r', '16i8', '16i16'))}
        self.assertEqual(ops16, set(ALU16_OPS))


class NegatedJrxTests(unittest.TestCase):
    """`jrx nz/nc/nn/no` never negates in the CPU (#4 item 2): op_EXT tests bit 2 of the
    EXT sub-opcode instead of the test code."""

    def negated_cases(self):
        return [c for c in jump_cases(include_negated_jrx=True)
                if c.parser == 'mJRX' and c.name.split()[2] in NEGATED]

    def test_negated_jrx_decodes_with_the_right_length(self):
        cases = self.negated_cases()
        self.assertEqual(len(cases), 4 * 2 * 2 * 2)
        for case in cases:
            with self.subTest(case.name):
                ast, code, labels = assemble(case.prog)
                start = ast[case.idx].addr
                nxt = ast[case.idx + 1].addr
                self.assertEqual(nxt - start, case.n)
                cpu, _, _ = execute(code, start, labels, case.n, case.regs, case.flags, case.mem, case.inputs)
                # decode only: lands either after the instruction or on the target
                self.assertIn(cpu.pc.get(), (start + case.n, labels['tgt']))

    # Known bug #4 (item 2, decided): a negated condition must jump when the flag is clear.
    @unittest.expectedFailure
    def test_negated_jrx_jumps_only_when_condition_negated_holds(self):
        for case in self.negated_cases():
            with self.subTest(case.name):
                run_case(self, case)


class OutImmediateTests(unittest.TestCase):
    """`out #r, imm` (#11, decided): `out #ci, 0x41` must assemble to D4 41 and
    `out #cs/#ds, imm` must be an assembler error.  Today it assembles to D0 41."""

    # Known bug #11
    @unittest.expectedFailure
    def test_out_ci_immediate_assembles_to_d4_41(self):
        _, code, _ = assemble(['out #ci, 0x41'])
        self.assertEqual(code, bytes([0xd4, 0x41]))

    # Known bug #11
    @unittest.expectedFailure
    def test_out_ci_immediate_agrees_with_cpu(self):
        run_case(self, Case('out #ci,imm', 'mOUT', ['out #ci, 0x41'], 2, regs={'ci': 7},
                            out_writes=[(7, 0x41)]))

    # Known bug #11
    @unittest.expectedFailure
    def test_out_cs_ds_immediate_is_an_assembler_error(self):
        for reg in ('cs', 'ds'):
            with self.subTest(reg):
                with self.assertRaises(Exception):
                    assemble([f'out #{reg}, 0x41'])


class PinnedFindingsTests(unittest.TestCase):
    """Other assembler/CPU disagreements found while writing this test (D7).
    Production code is not changed in this story: today's behaviour is pinned."""

    def test_16bit_rr_second_operand_is_ignored_by_cpu(self):
        # D7: the assembler encodes both register pairs of `add csci, csci`, but the CPU
        # derives the second operand from the first (CS -> DS, DS -> CS, A -> CS).
        run_case(self, Case('add csci,csci', 'mADD16r', ['add csci, csci'], 3,
                            regs={'csci': 0x0123, 'dsdi': 0x0005},
                            out_regs={'csci': 0x0128}))

    def test_inc_and_dec_of_af_cannot_be_parsed(self):
        # D7: mINC/mDEC are tried before mINC16/mDEC16 and succeed on `inc a`,
        # leaving the `f` unparsed; `inc af` / `dec af` are therefore a parse error.
        for text in ('inc af', 'dec af'):
            with self.subTest(text):
                with self.assertRaises(parsy.ParseError):
                    asm_grammar.program.parse(text + "\n")

    def test_clr_af_fails_to_assemble(self):
        # D7/D6: `clr af` is accepted by the grammar but cannot be encoded; it is now
        # a positioned assembler error instead of a bare KeyError.
        with self.assertRaises(asm_diag.AssemblerError) as cm:
            assemble(['clr af'])
        self.assertEqual([(d.line, d.column) for d in cm.exception.diagnostics], [(1, 1)])
        self.assertIn('cannot encode', str(cm.exception))

    def test_call_and_return_round_trip(self):
        ast, code, labels = assemble(['cal :sub', 'kil', 'sub: ret'])
        env = bc64_env.Environment(debug=False)
        membus = bc64_mem.MemBus(env, 0x10000)
        for i, b in enumerate(code):
            membus.write_byte(i, b)
        cpu = bc8183_cpu.Bc8183(membus, None, False)
        with contextlib.redirect_stdout(io.StringIO()):
            cpu.run()
        self.assertEqual(cpu.pc.get(), labels['sub'] - 1)   # the kil after the cal
        self.assertTrue(cpu.kill)
        self.assertEqual(_get_reg(cpu, 'sssi'), STACK_TOP)


if __name__ == '__main__':
    unittest.main()
