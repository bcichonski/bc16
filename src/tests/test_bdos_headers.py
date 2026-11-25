"""Static checks of the shared library headers src/bdos/*.h (#114, D13): defines live only in the headers."""
import glob
import os
import re
import unittest

BDOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bdos")
DEFINE = re.compile(r"^[ \t]*#define[ \t]+(\w+)", re.M)


def read(path):
    with open(path, encoding="latin-1") as f:
        return f.read()


def headers():
    return sorted(glob.glob(os.path.join(BDOS, "*.h")))


class BdosHeadersTests(unittest.TestCase):
    def test_headers_exist(self):
        self.assertTrue(headers())

    def test_no_define_is_in_both_a_header_and_a_b_file(self):
        header_names = {}
        for path in headers():
            for name in DEFINE.findall(read(path)):
                header_names.setdefault(name, os.path.basename(path))
        for path in sorted(glob.glob(os.path.join(BDOS, "*.b"))):
            for name in DEFINE.findall(read(path)):
                self.assertNotIn(name, header_names,
                                 "%s is defined in %s and %s" % (name, header_names.get(name), os.path.basename(path)))

    def test_no_define_is_in_two_headers(self):
        seen = {}
        for path in headers():
            for name in DEFINE.findall(read(path)):
                self.assertNotIn(name, seen, "%s is defined in %s and %s" % (name, seen.get(name), os.path.basename(path)))
                seen[name] = os.path.basename(path)

    def test_each_library_includes_its_header(self):
        for path in headers():
            stem = os.path.splitext(os.path.basename(path))[0]
            source = os.path.join(BDOS, stem + ".b")
            with self.subTest(library=stem):
                self.assertTrue(os.path.exists(source))
                first = [l.strip() for l in read(source).splitlines() if l.strip()][0]
                self.assertEqual("#include %s.h" % stem, first)

    def test_header_area_rule_matches_b_rule(self):
        from tests import e2e_areas
        for path in headers():
            stem = os.path.splitext(os.path.basename(path))[0]
            with self.subTest(library=stem):
                self.assertEqual(e2e_areas.areas_for_path("src/bdos/%s.b" % stem),
                                 e2e_areas.areas_for_path("src/bdos/%s.h" % stem))
                self.assertEqual(set(e2e_areas.AREAS), set(e2e_areas.areas_for_path("src/bdos/%s.h" % stem)))
