"""Static checks of the bdio result/error codes in src/bdos/bdioh.b (one value per meaning)."""
import os
import re
import unittest

BDIOH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bdos", "bdioh.h")
ERROR_PREFIXES = ("BDIO_FOPEN_", "BDIO_FCREATE_", "BDIO_FCLOSE_", "BDIO_FEXEC_", "BDIO_FILE_")
ERROR_FLOOR = 0xe0


def read_text():
    with open(BDIOH, encoding="latin-1") as f:
        return f.read()


def defines():
    """All (name, value) pairs of `#define NAME 0xNN` / decimal lines, in file order."""
    return [(m.group(1), int(m.group(2), 0))
            for m in re.finditer(r"^#define\s+(\w+)\s+(0x[0-9a-fA-F]+|\d+)\s*$", read_text(), re.M)]


def error_codes():
    """name -> value of every bdio error code (value >= 0xe0 in an operation group, plus no-free-handle)."""
    result = {}
    for name, value in defines():
        if name.startswith(ERROR_PREFIXES) and value >= ERROR_FLOOR:
            result[name] = value
    result["BDIO_FDESCRIPTOR_NUMBERFULL"] = dict(defines())["BDIO_FDESCRIPTOR_NUMBERFULL"]
    return result


def printexecres_body():
    with open(os.path.join(os.path.dirname(BDIOH), "bdioh.b"), encoding="latin-1") as f:
        text = f.read()
    start = text.index("bdio_printexecres(")
    return text[start:]


class BdiohCodesTests(unittest.TestCase):
    def test_no_define_name_occurs_twice(self):
        names = [name for name, _ in defines()]
        dups = sorted({n for n in names if names.count(n) > 1})
        self.assertEqual([], dups)

    def test_error_values_are_unique(self):
        codes = error_codes()
        by_value = {}
        for name, value in codes.items():
            by_value.setdefault(value, []).append(name)
        clashes = {hex(v): sorted(n) for v, n in by_value.items() if len(n) > 1}
        self.assertEqual({}, clashes)

    def test_error_codes_found(self):
        self.assertGreaterEqual(len(error_codes()), 19)

    def test_every_error_code_is_in_error_range(self):
        for name, value in error_codes().items():
            self.assertTrue(ERROR_FLOOR <= value <= 0xff, f"{name}={value:#x}")

    def test_fname_notfound_is_the_handle_error_split(self):
        self.assertEqual(0xe0, dict(defines())["BDIO_FOPEN_FNAME_NOTFOUND"])

    def test_changed_codes_have_a_message(self):
        body = printexecres_body()
        for name in ("BDIO_FOPEN_FDD_NOT_READY", "BDIO_FCLOSE_FCAT_SAVEERR"):
            self.assertRegex(body, r"execres\s*=\s*%s\b" % name)

    def test_retired_and_free_values_are_not_used(self):
        used = set(error_codes().values())
        self.assertNotIn(0xe5, used)
        self.assertFalse([v for v in used if 0xf4 <= v <= 0xfe])

    def test_fixed_values(self):
        d = dict(defines())
        self.assertEqual(0xe1, d["BDIO_FOPEN_FDD_NOT_READY"])
        self.assertEqual(0xef, d["BDIO_FCLOSE_FCAT_SAVEERR"])
        self.assertEqual(0xe6, d["BDIO_FCLOSE_FCAT_READERR"])
        self.assertEqual(0xe7, d["BDIO_FEXEC_ATTR_NOEXEC"])
        self.assertNotIn("BDIO_FCREATE_FNAME_EXISTS", d)


if __name__ == "__main__":
    unittest.main()
