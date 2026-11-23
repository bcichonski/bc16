"""E2E: command table of the six bDOS utilities (ls, cp, rm, cha, cat, format), one session.

Boots temp copies of os.bdd (A) and utils.bdd (B) and runs a table of well-formed command lines
(help, switches, drive prefixes, missing files). The masked golden was recorded from the tools
BEFORE they were ported to the shared argument library (issue 43) and must never change: it
proves that the ported tools accept exactly the same command lines with the same messages.

Deliberately not in the table: bare `format` (a missing drive wipes drive A), `cat` of a .PRG
(its bytes change with the tools), tape commands and the monitor.
"""
import os
import tempfile
import unittest

import e2e_harness as h

LIMIT = 400000000
SCENARIO = "bdos_cmdtable"
COMMANDS = [
    "ls -h", "cp -h", "rm -h", "cha -h", "cat -h", "format -h",
    "ls", "ls -a", "ls b:", "ls -a b:",
    "cat -c test.b", "cat -b test.b", "cat test.b", "cat -x test.b",
    "cp test.b t1.b", "cp test.b b:t2.b", "cp b:hellowrd.prg h2.prg", "a:", "cp a:test.b b:t3.b",
    "cat -c b:t3.b",
    "cha +w t1.b", "cha -r t1.b", "cha +rx b:t2.b",
    "ls", "ls b:",
    "rm t1.b", "rm b:t2.b", "rm ls.prg", "rm -f b:t3.b",
    "ls", "ls -a b:",
    "format -q b:", "ls b:",
    "exit",
]


class BdosCommandTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            session = os.path.join(tmp, "session.txt")
            with open(session, "wb") as handle:
                handle.write(("\n".join(COMMANDS) + "\n").encode("latin-1"))
            cls.out = h.run_session(SCENARIO, session, disks={"a": h.OS_DISK, "b": h.UTILS_DISK},
                                    max_instructions=LIMIT)

    def test_transcript_matches_golden(self):
        markers = [b">" + c.encode("latin-1") + b"\n" for c in COMMANDS]
        h.check_golden(h.golden_path(SCENARIO), self.out, masks=h.DISC_MASKS, markers=markers,
                       scenario=SCENARIO)

    def test_markers(self):
        h.assert_markers(self.out, [b"listing files of drive A:", b"listing files of drive B:",
                                    b"error: cannot remove system file", b"bye!"])
        self.assertTrue(self.out.rstrip().endswith(b"bye!") or b"bye!" in self.out[-200:])


if __name__ == "__main__":
    unittest.main()
