"""E2E: CALC.PRG on utils.bdd in the default A/B session (os.bdd in A, a temp copy of utils.bdd in B)."""
import os
import unittest

import e2e_harness as h

LIMIT = 100000000
SECTORS = os.path.join(h.SRC, "bdos", "calc.sectors")


def run(scenario):
    out = h.run_session("calc_" + scenario, h.golden_path("calc_" + scenario, "in"),
                        disks={"a": h.OS_DISK, "b": h.UTILS_DISK}, max_instructions=LIMIT)
    return out.replace(b"\n\r", b"\n")  # the printer ends a line with LF CR


class CalcTests(unittest.TestCase):
    def test_banner_and_help(self):
        out = run("help")
        h.assert_markers(out, [b"B>calc", b"calc v1.0\ntype h for help\ncalc>h\n",
                               b"+ for addition\n- for subtraction\n* for multiplication\n"
                               b"/ for division\nh for help\nq for quit\ncalc>"])
        self.assertNotIn(b"deletion", out)

    def test_each_operation(self):
        out = run("ops")
        h.assert_markers(out, [b"calc>+\n1>12\n2>30\nres>42\n",
                               b"calc>-\n1>3\n2>5\nres>65534\n",
                               b"calc>*\n1>300\n2>500\nres>18928\n",
                               b"calc>/\n1>100\n2>7\nres>14\n",
                               b"calc>q\nbye\nB>"])

    def test_division_by_zero_is_refused_and_session_continues(self):
        out = run("divzero")
        h.assert_markers(out, [b"calc>/\n1>5\n2>0\nerror: division by zero\ncalc>+\n1>1\n2>2\nres>3\n",
                               b"bye\nB>"])
        self.assertNotIn(b"res>\n", out)

    def test_bad_numbers(self):
        out = run("bad")
        h.assert_markers(out, [b"1>abc\nerror: bad number\ncalc>",
                               b"1>\nerror: bad number\ncalc>",
                               b"1>65536\nerror: bad number\ncalc>",
                               b"1>100000\nerror: bad number\ncalc>",
                               b"2>1234567\nerror: bad number\ncalc>"])
        # no second prompt after a bad first operand: only the "1>1" and "1>65535" runs asked for 2>
        self.assertEqual(2, out.count(b"2>"))

    def test_65535_is_accepted_and_65536_is_not(self):
        out = run("bad")
        h.assert_markers(out, [b"1>65535\n2>0\nres>65535\n"])
        self.assertEqual(1, out.count(b"res>"))

    def test_unknown_command(self):
        out = run("unknown")
        h.assert_markers(out, [b"calc>x\nerror: unknown command, type h for help\ncalc>q\nbye\n"])
        self.assertNotIn(b"1>", out)

    def test_quit_returns_to_shell_and_bdos_survives(self):
        out = run("quit")
        h.assert_markers(out, [b"calc>q\nbye\nB>a:\nA>ls\n", b"HELLOWRD.PRG", b"TEST    .B"])

    def test_catalog_entry_is_read_execute_not_system(self):
        entries = [e for e in h.read_catalog(h.UTILS_DISK) if (e.name, e.ext) == ("CALC", "PRG")]
        self.assertEqual(1, len(entries))
        entry = entries[0]
        self.assertEqual(h.ATTR_RX, entry.attributes & (h.ATTR_R | h.ATTR_X))
        self.assertEqual(0, entry.attributes & 0x80)
        self.assertEqual(-(-os.path.getsize(SECTORS) // h.SECTOR_SIZE), entry.length)
