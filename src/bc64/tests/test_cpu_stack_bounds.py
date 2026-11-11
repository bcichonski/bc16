"""Stack bounds rule (plan #7, D3): stack accesses outside memory stop the CPU cleanly.

Every stack byte PSH/POP/CAL/RET reads or writes must lie inside 0 <= addr < membus.size.
Otherwise the CPU is killed like KIL, the PC stays on the instruction, registers, SS:SI and
memory are untouched and one line goes to stderr (never stdout) and to the debug trace.
"""
import contextlib
import io
import os
import shutil
import tempfile
import unittest

import importlib.util
from bc64 import bc8183_cpu
from bc64 import bc64_env
from bc64 import bc64_mem

PSH_A = 0x81
POP_CI = 0x94
CAL_ABS = 0xa8
RET = 0xb0
KIL = 0xf0


def load_bc64_main():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bc64.py")
    spec = importlib.util.spec_from_file_location("bc64_main_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bc64_main = load_bc64_main()


def full_machine(code, debug=False):
    """A started-up Bc64 (SS:SI = 0xfffe, 0xff at 0xffff) with code at 0x0000."""
    computer = bc64_main.Bc64(bc64_env.Environment(False), debug, no_floppy=True)
    for i, b in enumerate(code):
        computer.mem.write_byte(i, b)
    computer.write_top_kil()
    return computer


def small_cpu(code, size=0x400):
    env = bc64_env.Environment(False)
    mem = bc64_mem.MemBus(env, size)
    for i, b in enumerate(code):
        mem.write_byte(i, b)
    return bc8183_cpu.Bc8183(mem, None, False)


def run(cpu, limit=100):
    """Run to kill with stdout and stderr captured; returns (stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        cpu.inc_pc(0)
        steps = 0
        while not cpu.kill:
            steps += 1
            if steps > limit:
                raise AssertionError("did not stop")
            cpu.run_next_opcode()
    return out.getvalue(), err.getvalue()


def snapshot(cpu):
    regs = {n: getattr(cpu, n).get() for n in ('a', 'ci', 'di', 'cs', 'ds', 'ss', 'si')}
    return regs, bytes(cpu.membus.mem)


class FullMachineStackStopTests(unittest.TestCase):
    def assertStoppedOnInstruction(self, cpu, pc, before, stdout, stderr, name, kind):
        self.assertTrue(cpu.kill)
        self.assertEqual(cpu.pc.get(), pc)
        self.assertEqual(snapshot(cpu), before)
        self.assertEqual(stdout, "")
        self.assertEqual(len(stderr.splitlines()), 1, stderr)
        self.assertIn(name, stderr)
        self.assertIn("%04x" % pc, stderr)
        self.assertIn(kind, stderr)

    def test_start_up_state(self):
        cpu = full_machine([]).cpu
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0xff, 0xfe))

    def test_POP_on_empty_stack_stops(self):
        cpu = full_machine([POP_CI]).cpu
        before = snapshot(cpu)
        out, err = run(cpu)
        self.assertStoppedOnInstruction(cpu, 0, before, out, err, "POP", "empty stack")

    def test_RET_on_empty_stack_stops(self):
        cpu = full_machine([0x00, RET]).cpu
        before = snapshot(cpu)
        out, err = run(cpu)
        self.assertStoppedOnInstruction(cpu, 1, before, out, err, "RET", "empty stack")

    def test_RET_with_one_push_frame_needs_past_top_and_stops(self):
        cpu = full_machine([PSH_A, RET]).cpu
        cpu.a.set(0x12)
        cpu.inc_pc(0)
        with contextlib.redirect_stdout(io.StringIO()):
            cpu.run_next_opcode()
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0xff, 0xfc))
        before = snapshot(cpu)
        out, err = run(cpu)
        # run() restarts at the current PC (inc_pc(0) only re-reads the byte)
        self.assertStoppedOnInstruction(cpu, 1, before, out, err, "RET", "empty stack")

    def test_call_and_return_round_trip_at_top_of_memory(self):
        code = [CAL_ABS, 0x00, 0x10, KIL] + [0] * 12 + [RET]
        cpu = full_machine(code).cpu
        out, err = run(cpu)
        self.assertEqual(err, "")
        self.assertEqual(cpu.pc.get(), 3)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0xff, 0xfe))
        self.assertEqual(cpu.membus.read_byte(0xfffe), 0x03)
        self.assertEqual(cpu.membus.read_byte(0xfffd), 0x00)
        self.assertEqual(cpu.membus.read_byte(0xfffc), 0xc0)

    def test_push_and_pop_round_trip_at_top_of_memory(self):
        cpu = full_machine([PSH_A, POP_CI, KIL]).cpu
        cpu.a.set(0x42)
        out, err = run(cpu)
        self.assertEqual(err, "")
        self.assertEqual(cpu.ci.get(), 0x42)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0xff, 0xfe))
        self.assertEqual(cpu.membus.read_byte(0xfffe), 0x42)
        self.assertEqual(cpu.membus.read_byte(0xfffd), 0x10)

    def test_stop_message_also_goes_to_the_debug_trace(self):
        tmp = tempfile.mkdtemp(prefix="bc64stack")
        cwd = os.getcwd()
        self.addCleanup(shutil.rmtree, tmp, True)
        self.addCleanup(os.chdir, cwd)
        os.chdir(tmp)
        cpu = full_machine([POP_CI], debug=True).cpu
        out, err = run(cpu)
        with open(os.path.join(tmp, "cpudebug.log")) as f:
            trace = f.read()
        self.assertIn(err.strip(), trace)


class SmallBusStackStopTests(unittest.TestCase):
    def test_POP_on_empty_stack_stops(self):
        cpu = small_cpu([POP_CI])
        before = snapshot(cpu)
        out, err = run(cpu)
        self.assertTrue(cpu.kill)
        self.assertEqual(cpu.pc.get(), 0)
        self.assertEqual(snapshot(cpu), before)
        self.assertEqual(out, "")
        self.assertIn("POP", err)
        self.assertIn("empty stack", err)

    def test_RET_on_empty_stack_stops(self):
        cpu = small_cpu([RET])
        before = snapshot(cpu)
        out, err = run(cpu)
        self.assertTrue(cpu.kill)
        self.assertEqual(cpu.pc.get(), 0)
        self.assertEqual(snapshot(cpu), before)
        self.assertEqual(out, "")
        self.assertIn("RET", err)
        self.assertIn("empty stack", err)


class StackOverflowStopTests(unittest.TestCase):
    def check_overflow(self, code, ss, si, name):
        cpu = small_cpu(code)
        cpu.ss.set(ss)
        cpu.si.set(si)
        before = snapshot(cpu)
        out, err = run(cpu)
        self.assertTrue(cpu.kill)
        self.assertEqual(cpu.pc.get(), 0)
        self.assertEqual(snapshot(cpu), before)
        self.assertEqual(out, "")
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertIn(name, err)
        self.assertIn("stack overflow", err)

    def test_PSH_at_SI_0_would_write_below_zero(self):
        self.check_overflow([PSH_A], 0x00, 0x00, "PSH")

    def test_CAL_at_SI_1_would_write_below_zero(self):
        self.check_overflow([CAL_ABS, 0x00, 0x10], 0x00, 0x01, "CAL")

    def test_CAL_at_SI_0_would_write_below_zero(self):
        self.check_overflow([CAL_ABS, 0x00, 0x10], 0x00, 0x00, "CAL")

    def test_PSH_at_SI_1_still_fits(self):
        cpu = small_cpu([PSH_A, KIL])
        cpu.ss.set(0x00)
        cpu.si.set(0x01)
        cpu.a.set(0x77)
        cpu.inc_pc(0)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            cpu.run_next_opcode()
        self.assertEqual(err.getvalue(), "")
        self.assertFalse(cpu.kill)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0xff, 0xff))
        self.assertEqual(cpu.membus.read_byte(0), 0x10)
        self.assertEqual(cpu.membus.read_byte(1), 0x77)


class StackDumpTests(unittest.TestCase):
    def test_print_cpu_stack_on_empty_full_size_stack_does_not_raise(self):
        cpu = full_machine([]).cpu
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cpu.print_cpu_stack()
        self.assertIn(":::empty:::", out.getvalue())

    def test_print_cpu_stack_with_incomplete_frame_at_top_does_not_raise(self):
        cpu = full_machine([]).cpu
        cpu.si.set(0xfd)  # tag byte at 0xfffe, only one byte follows it
        cpu.membus.write_byte(0xfffe, 0xc0)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cpu.print_cpu_stack()
        self.assertIn(":::CPU stack:::", out.getvalue())


if __name__ == "__main__":
    unittest.main()
