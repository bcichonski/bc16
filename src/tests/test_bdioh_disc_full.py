"""Static checks of the disc-full code and the reserved-area constants in src/bdos/bdioh.b (#41)."""
import re
import unittest

from tests import test_bdioh_codes as codes


class BdiohDiscFullTests(unittest.TestCase):
    def test_disc_full_code_is_f3(self):
        self.assertEqual(0xf3, dict(codes.defines())["BDIO_FILE_DISC_FULL"])
        self.assertEqual(0xf3, codes.error_codes()["BDIO_FILE_DISC_FULL"])

    def test_disc_full_has_a_message(self):
        body = codes.printexecres_body()
        self.assertRegex(body, r"execres\s*=\s*BDIO_FILE_DISC_FULL\)\s*\{\s*errorMessage\s*<-\s*\"disc full\"")

    def test_header_comment_lists_disc_full_and_free_range(self):
        text = codes.read_text()
        self.assertRegex(text, r"(?m)^//.*disc full\s+0xf3")
        self.assertRegex(text, r"(?m)^//.*0xf4\.\.0xfe free")

    def test_reserved_area_constants(self):
        d = dict(codes.defines())
        self.assertEqual(0x20, d["BDIO_DISC_BDOSFIRSTSECT"])
        self.assertEqual(0xbf, d["BDIO_DISC_BDOSLASTSECT"])
        self.assertEqual(d["BDIO_DISC_BDOSLASTSECT"] + 1, d["BDIO_DISC_ALLOCFIRSTSECT"])
        self.assertEqual(d["FDD_TRACKS"] * d["FDD_SECTORS"], d["BDIO_DISC_SECTORS"])
        self.assertEqual(d["BDIO_DISC_SECTORS"] - d["BDIO_DISC_ALLOCFIRSTSECT"],
                         d["BDIO_DISC_ALLOCSECTORS"])
        self.assertEqual(d["BDIO_DISC_ALLOCFIRSTSECT"] // 8, d["BDIO_USEDMAP_RESERVEDLEN"])
        self.assertEqual(d["BDIO_DISC_SECTORS"] // 8, d["BDIO_USEDMAP_LEN"])
        self.assertEqual(d["FDD_TRACKS"] << 8, d["BDIO_DISC_ENDTRACKSECT"])
        # the map sits between the last handle buffer and the bdos heap
        self.assertGreaterEqual(d["BDIO_USEDMAP_ADDR"], d["BDIO_FDESCBUF_ADDR"] + 4 * d["BDIO_SECTBUF_LEN"])
        self.assertLessEqual(d["BDIO_USEDMAP_ADDR"] + d["BDIO_USEDMAP_LEN"], 0x5fd0)


if __name__ == "__main__":
    unittest.main()
