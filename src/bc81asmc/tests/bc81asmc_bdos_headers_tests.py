"""The real library headers src/bdos/*.h (#114, D13): each is a valid bc81asmc header, and their names assemble."""
import contextlib
import glob
import io
import os
import re
import shutil
import tempfile
import unittest

import bc81asmc
import bc81asmc_pre as pre

BDOS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'bdos')
HEADERS = sorted(glob.glob(os.path.join(BDOS, '*.h')))


class TestBdosHeaders(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def prepass_with(self, header):
        shutil.copy(os.path.join(BDOS, header), os.path.join(self.dir, header))
        return pre.prepass('#include %s\nnop\n' % header, os.path.join(self.dir, 'prog.basm'))

    def test_headers_exist(self):
        self.assertTrue(HEADERS)

    def test_every_header_is_accepted_without_diagnostics(self):
        for path in HEADERS:
            name = os.path.basename(path)
            with self.subTest(header=name):
                result = self.prepass_with(name)
                self.assertEqual([d.message for d in result.diagnostics], [])

    def test_bdioh_name_assembles_to_its_defined_value(self):
        with open(os.path.join(BDOS, 'bdioh.h'), encoding='latin-1') as f:
            match = re.search(r'^#define\s+BDIO_DISC_ALLOCFIRSTSECT\s+(0x[0-9a-fA-F]+|\d+)\s*$', f.read(), re.M)
        self.assertIsNotNone(match)
        value = int(match.group(1), 0)
        shutil.copy(os.path.join(BDOS, 'bdioh.h'), os.path.join(self.dir, 'bdioh.h'))
        with contextlib.redirect_stdout(io.StringIO()):
            context = bc81asmc.assemble_text('#include bdioh.h\nmov a, BDIO_DISC_ALLOCFIRSTSECT\n',
                                             os.path.join(self.dir, 'prog.basm'))
            literal = bc81asmc.assemble_text('mov a, 0x%02x\n' % value, os.path.join(self.dir, 'lit.basm'))
        self.assertEqual(bytes(context.bytes), bytes(literal.bytes))
