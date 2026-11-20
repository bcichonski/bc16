"""RET frame rule (plan #59): RET returns through a call frame, jumps through two push frames,
and stops the CPU cleanly (like KIL) on a single push frame or on an unknown top tag.

A stop leaves PC on the RET, registers, SS:SI and memory untouched and writes one line to
stderr (never stdout) and to the debug trace.
"""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from bc64.tests.test_cpu_stack_bounds import (
    CAL_ABS, KIL, POP_CI, PSH_A, RET, full_machine, run, small_cpu, snapshot)

MOV_A = 0x11
BC64_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bc64.py")


class RetFrameTests(unittest.TestCase):
    def assertRetStop(self, cpu, pc, before, out, err, reason):
        self.assertTrue(cpu.kill)
        self.assertEqual(cpu.pc.get(), pc)
        self.assertEqual(snapshot(cpu), before)
        self.assertEqual(out, "")
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertIn("RET at %04x" % pc, err)
        self.assertIn(reason, err)
        self.assertIn("CPU stopped", err)

    def run_to_ret(self, cpu, ret_pc):
        """Execute until the next instruction is the RET at ret_pc; returns nothing."""
        cpu.inc_pc(0)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            for _ in range(100):
                if cpu.pc.get() == ret_pc:
                    return
                cpu.run_next_opcode()
        raise AssertionError("never reached the RET")

    def test_call_then_single_push_then_ret_stops(self):
        # cal sub; kil; ... sub: psh a; ret
        code = [CAL_ABS, 0x00, 0x10, KIL] + [0] * 12 + [PSH_A, RET]
        cpu = full_machine(code).cpu
        cpu.a.set(0x42)
        self.run_to_ret(cpu, 0x11)
        before = snapshot(cpu)
        out, err = run(cpu)
        self.assertRetStop(cpu, 0x11, before, out, err, "single push frame")
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0xff, 0xf9))

    def test_two_pushes_over_call_frame_jump_and_leave_the_call_frame(self):
        # sub: mov a,3; psh a (lo); mov a,0; psh a (hi); ret  -> jumps to 0x0003 (kil)
        code = [CAL_ABS, 0x00, 0x10, KIL] + [0] * 12 + [MOV_A, 0x03, PSH_A, MOV_A, 0x00, PSH_A, RET]
        cpu = full_machine(code).cpu
        out, err = run(cpu)
        self.assertEqual((out, err), ("", ""))
        self.assertEqual(cpu.pc.get(), 3)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0xff, 0xfb))
        self.assertEqual(cpu.membus.read_byte(0xfffc), 0xc0)

    def test_single_push_over_call_frame_after_one_pop_stops(self):
        # as above but pop ci after the second push: a push frame over the call frame remains
        code = ([CAL_ABS, 0x00, 0x10, KIL] + [0] * 12
                + [MOV_A, 0x03, PSH_A, MOV_A, 0x00, PSH_A, POP_CI, RET])
        cpu = full_machine(code).cpu
        self.run_to_ret(cpu, 0x17)
        before = snapshot(cpu)
        out, err = run(cpu)
        self.assertRetStop(cpu, 0x17, before, out, err, "single push frame")

    def test_unknown_top_tag_stops(self):
        cpu = small_cpu([RET])
        cpu.ss.set(0x00)
        cpu.si.set(0x10)
        for i, b in enumerate([0x55, 0x03, 0x10, 0x00]):
            cpu.membus.write_byte(0x11 + i, b)
        before = snapshot(cpu)
        out, err = run(cpu)
        self.assertRetStop(cpu, 0, before, out, err, "no call or push frame")

    def test_single_push_over_unknown_tag_stops(self):
        cpu = small_cpu([RET])
        cpu.ss.set(0x00)
        cpu.si.set(0x10)
        for i, b in enumerate([0x10, 0x03, 0x77, 0x00]):
            cpu.membus.write_byte(0x11 + i, b)
        before = snapshot(cpu)
        out, err = run(cpu)
        self.assertRetStop(cpu, 0, before, out, err, "single push frame")

    def test_two_push_frames_still_jump_on_small_memory(self):
        cpu = small_cpu([RET] + [0] * 7 + [KIL])
        cpu.ss.set(0x00)
        cpu.si.set(0x10)
        for i, b in enumerate([0x10, 0x00, 0x10, 0x08]):  # tag hi tag lo -> jump to 0x0008
            cpu.membus.write_byte(0x11 + i, b)
        out, err = run(cpu)
        self.assertEqual((out, err), ("", ""))
        self.assertEqual(cpu.pc.get(), 0x08)
        self.assertEqual((cpu.ss.get(), cpu.si.get()), (0x00, 0x14))

    def test_stop_message_also_goes_to_the_debug_trace(self):
        tmp = tempfile.mkdtemp(prefix="bc64ret")
        cwd = os.getcwd()
        self.addCleanup(shutil.rmtree, tmp, True)
        self.addCleanup(os.chdir, cwd)
        os.chdir(tmp)
        cpu = full_machine([CAL_ABS, 0x00, 0x10, KIL] + [0] * 12 + [PSH_A, RET], debug=True).cpu
        out, err = run(cpu)
        with open(os.path.join(tmp, "cpudebug.log")) as f:
            trace = f.read()
        self.assertIn("RET at 0011", err)
        self.assertIn(err.strip(), trace)


class RetFrameCliTests(unittest.TestCase):
    def test_headless_single_push_ret_exits_zero_with_stderr_line(self):
        tmp = tempfile.mkdtemp(prefix="bc64retcli")
        self.addCleanup(shutil.rmtree, tmp, True)
        rom = os.path.join(tmp, "ret.b81")
        with open(rom, "wb") as f:
            f.write(bytes([CAL_ABS, 0x00, 0x04, KIL, PSH_A, RET]))
        result = subprocess.run([sys.executable, BC64_PY, rom, "--no-floppy"], cwd=tmp,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        lines = result.stderr.decode().splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("RET at 0005", lines[0])
        self.assertIn("CPU stopped", lines[0])


if __name__ == "__main__":
    unittest.main()
