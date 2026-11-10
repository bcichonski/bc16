import contextlib
import io
import os
import unittest

import bc81asmc
from bc81asmc_diag import AssemblerError
from bc81asmc_grammar import program

HERE = os.path.dirname(os.path.abspath(__file__))
BOOT = os.path.join(HERE, '..', 'bdos', 'boot.basm')
BCOS = os.path.join(HERE, 'bcOS', 'bcos.basm')

BCOS_ASSERTS = ("  .assert :os_metacall = 0x0008\n"
                "  .assert :os_metatab = 0x000c\n"
                "  .assert :user_mem <= 0x0d80\n")


def read(path):
    with open(path, encoding='utf-8', newline='') as f:
        return f.read().replace('\r\n', '\n')


def insert_before_label(source, label, text):
    lines = source.split('\n')
    idx = [i for i, l in enumerate(lines) if l.startswith(label + ':')]
    assert len(idx) == 1, label
    lines.insert(idx[0], text)
    return '\n'.join(lines)


def compile_source(source):
    with contextlib.redirect_stdout(io.StringIO()):
        return bc81asmc.compile(program.parse(source), False)


def messages_of(source):
    with contextlib.redirect_stdout(io.StringIO()):
        with unittest.TestCase().assertRaises(AssemblerError) as cm:
            bc81asmc.compile(program.parse(source), False)
    return [d.message for d in cm.exception.diagnostics]


class TestBootContract(unittest.TestCase):
    def test_committed_boot_assembles(self):
        compile_source(read(BOOT))

    def test_boot_with_extra_byte_fails_assert(self):
        src = read(BOOT).replace('\nbd_end:', '\n                   .db 0x00\nbd_end:')
        self.assertIn('.db 0x00', src)
        msgs = messages_of(src)
        self.assertTrue(any('bd_end' in m for m in msgs), msgs)


class TestBcosContract(unittest.TestCase):
    def test_committed_bcos_satisfies_contract(self):
        compile_source(read(BCOS) + BCOS_ASSERTS)

    def test_byte_before_os_metacall_fails(self):
        src = insert_before_label(read(BCOS), 'os_metacall', '                 nop')
        msgs = messages_of(src + BCOS_ASSERTS)
        self.assertTrue(any('os_metacall' in m for m in msgs), msgs)

    def test_padding_before_user_mem_fails(self):
        src = insert_before_label(read(BCOS), 'user_mem', '\n'.join(['                 nop'] * 0x400))
        msgs = messages_of(src + BCOS_ASSERTS)
        self.assertTrue(any('user_mem' in m for m in msgs), msgs)


if __name__ == '__main__':
    unittest.main()
