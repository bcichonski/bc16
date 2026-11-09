"""End-to-end scenarios of the bcOS monitor on the headless emulator (--no-floppy).

Scripts and goldens live in bc64/testdata/e2e/ (bcos_*.in.txt, bcos_*.golden.txt).
Regenerate goldens with BC64_UPDATE_GOLDEN=1, then inspect the diff by eye.
Scripts never use `q` nor a bad-argument command followed by more commands: both crash the CPU.
"""
import os
import unittest

import e2e_harness as h

# about 10x the measured need (the scenarios take well under 1M instructions)
LIMIT = 20000000


class BcosMonitorTests(unittest.TestCase):
    def run_scenario(self, scenario, **kwargs):
        return h.run_session(scenario, h.golden_path(scenario, "in"), no_floppy=True,
                             max_instructions=LIMIT, **kwargs)

    def test_boot_and_unknown_command(self):
        out = self.run_scenario("bcos_unknown")
        h.check_golden(h.golden_path("bcos_unknown"), out, scenario="bcos_unknown",
                       markers=[b"bcOS 1.2", b"type h for help", b"> z", b"error 01"])

    def test_dump_write_print(self):
        out = self.run_scenario("bcos_dump_write_print")
        h.check_golden(h.golden_path("bcos_dump_write_print"), out, scenario="bcos_dump_write_print",
                       markers=[b"> d 0000 0010", b"2000 68 65 6C 6C 6F", b"> p 2000 0005",
                                b"2000 hello"])

    # Known bug, found by #49: the tape round trip fails. `s` writes the tape file, but `l`
    # prints "load 3000 for 2000" and then reads past the end of the tape (TypeError in
    # TapeRecorder.read_byte, exit non-zero). Related: #32 (s/l register quirk), #62 (reading
    # past the tape end). No golden is committed: the correct output can't be generated while
    # the bug exists, so only markers are asserted.
    @unittest.expectedFailure
    def test_tape_round_trip(self):
        out = self.run_scenario("bcos_tape", tape_dir=True)
        h.assert_markers(out, [b"> s 2000 0005 hello.txt", b"> l 3000", b"> p 3000 0005",
                               b"3000 hello"])


if __name__ == "__main__":
    unittest.main()
