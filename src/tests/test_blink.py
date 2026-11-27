"""Unit tests of src/blink.py: pass 1, mark, layout and size checks (#117, T1).

Objects are built with `bof.BofWriter` into a temp folder, so every case is exact and does not
depend on the assembler. One test links the real runtime (built from src/bc/runtime.basm) and
checks only the structure of the result, never its bytes (#188 changes them).
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import blink
import bof

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def abs16_call(w, symbol):
    """A 3-byte `cal :symbol` through an ABS16 fix (the target sits in the placeholder)."""
    k = w.extrn(symbol)
    w.code(bytes((0xa8, k >> 8, k & 0xff)), [(bof.FIX_ABS16, 1)])


def label_call(w, n):
    t = bof.local_label_target(n)
    w.code(bytes((0xa8, t >> 8, t & 0xff)), [(bof.FIX_ABS16, 1)])


def runtime(w, extra=None):
    """RUNTIME: an entry of 4 bytes that refers to nothing and a global `helper` of 2 bytes."""
    w.sectstat('runtime_entry')
    w.code(b'\x11\xff\x11\xff')
    w.sectstat('helper')
    w.globl('helper')
    w.code(b'\x00\xb0')
    if extra:
        extra(w)


def main_calls(*symbols, size=0):
    """A main module body: F_main calls each symbol, then `size` filler bytes and `ret`."""
    def build(w):
        w.sectstat('F_main')
        w.globl('F_main')
        for s in symbols:
            abs16_call(w, s)
        if size:
            w.code(bytes(size))
        w.code(b'\xb0')
    return build


class BlinkTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='blink_test_')
        self.main_dir = os.path.join(self.tmp, 'main')
        self.lib_dir = os.path.join(self.tmp, 'lib')
        os.mkdir(self.main_dir)
        os.mkdir(self.lib_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def obj(self, module, build, folder=None):
        w = bof.BofWriter(module)
        build(w)
        w.end()
        path = os.path.join(folder or self.main_dir, blink.object_file_name(module))
        with open(path, 'wb') as fh:
            fh.write(w.getvalue())
        return path

    def raw(self, module, data, folder=None):
        path = os.path.join(folder or self.main_dir, blink.object_file_name(module))
        with open(path, 'wb') as fh:
            fh.write(data)

    def link(self, name='HELLO'):
        return blink.link_layout(os.path.join(self.main_dir, name.lower()), lib_dir=self.lib_dir)

    def std(self, main_build=None, runtime_extra=None):
        self.obj('RUNTIME', lambda w: runtime(w, runtime_extra), self.lib_dir)
        self.obj('HELLO', main_build or main_calls())

    def assertOk(self, link):
        self.assertEqual(link.errors, [])
        self.assertTrue(link.ok)

    def assertOneError(self, link, *parts):
        self.assertEqual(len(link.errors), 1, link.errors)
        message = link.errors[0]
        self.assertTrue(message.startswith('blink: error: '), message)
        for p in parts:
            self.assertIn(p, message)

    def kept_names(self, link):
        return [(s.module.name, s.name) for s in link.kept]


class ModuleListTests(BlinkTestCase):

    def test_object_file_name_is_lower_case(self):
        self.assertEqual(blink.object_file_name('UTIL'), 'util.o')

    def test_module_list_starts_runtime_then_name(self):
        self.std()
        link = self.link()
        self.assertOk(link)
        self.assertEqual([m.name for m in link.modules], ['RUNTIME', 'HELLO'])

    def test_need_chain_with_cycle_and_duplicate(self):
        def hello(w):
            w.need('A')
            w.need('A')
            main_calls()(w)
            w.need('B')
        self.std(hello)
        self.obj('A', lambda w: (w.need('B'), w.need('HELLO')))
        self.obj('B', lambda w: (w.need('C'), w.need('A')))
        self.obj('C', lambda w: w.need('RUNTIME'), self.lib_dir)
        link = self.link()
        self.assertOk(link)
        self.assertEqual([m.name for m in link.modules], ['RUNTIME', 'HELLO', 'A', 'B', 'C'])

    def test_main_folder_is_searched_before_library_folder(self):
        self.std(lambda w: (w.need('UTIL'), main_calls('util')(w)))
        def util(value):
            def build(w):
                w.sectstat('util')
                w.globl('util')
                w.code(bytes((value,)))
            return build
        self.obj('UTIL', util(1), self.lib_dir)
        self.obj('UTIL', util(2))
        link = self.link()
        self.assertOk(link)
        self.assertEqual(link.modules[2].path, os.path.join(self.main_dir, 'util.o'))
        os.remove(os.path.join(self.main_dir, 'util.o'))
        link = self.link()
        self.assertOk(link)
        self.assertEqual(link.modules[2].path, os.path.join(self.lib_dir, 'util.o'))

    def test_lib_dir_overrides_default_library_folder(self):
        self.assertEqual(blink.DEFAULT_LIB_DIR, os.path.join(SRC, 'bc'))
        self.std()
        link = self.link()
        self.assertEqual(link.lib_dir, self.lib_dir)
        self.assertEqual(link.modules[0].path, os.path.join(self.lib_dir, 'runtime.o'))

    def test_name_with_o_extension(self):
        self.std()
        link = blink.link_layout(os.path.join(self.main_dir, 'hello.o'), lib_dir=self.lib_dir)
        self.assertOk(link)
        self.assertEqual(link.name, 'hello')


class ErrorTests(BlinkTestCase):

    def test_missing_needed_object_names_the_needing_module(self):
        self.std(lambda w: (w.need('UTIL'), main_calls()(w)))
        self.assertOneError(self.link(), 'module UTIL not found', 'util.o', 'needed by module HELLO')

    def test_missing_main_object_is_needed_by_the_command_line(self):
        self.obj('RUNTIME', runtime, self.lib_dir)
        self.assertOneError(self.link(), 'module HELLO not found', 'needed by the command line')

    def test_missing_runtime_is_needed_by_the_command_line(self):
        self.obj('HELLO', main_calls())
        link = self.link()
        self.assertIn('blink: error: module RUNTIME not found (runtime.o, needed by the command line)',
                      link.errors)

    def test_bad_header(self):
        self.obj('RUNTIME', runtime, self.lib_dir)
        self.raw('HELLO', b'\x55\x01\x41\xed\x00')
        self.assertOneError(self.link(), 'module HELLO', 'not a BOF file')

    def test_bad_version(self):
        self.obj('RUNTIME', runtime, self.lib_dir)
        self.raw('HELLO', b'\xb0\x06\x02HELLO\xed\x00')
        self.assertOneError(self.link(), 'module HELLO', 'unsupported BOF version 02')

    def test_conflicting_addr_names_both_modules(self):
        self.std(lambda w: (w.addr(bof.ADDR_HEAP, 0x9000), main_calls()(w)),
                 lambda w: w.addr(bof.ADDR_HEAP, 0x8000))
        self.assertOneError(self.link(), 'conflicting #heap', '8000 in module RUNTIME', '9000 in module HELLO')

    def test_same_addr_twice_is_not_an_error(self):
        self.std(lambda w: (w.addr(bof.ADDR_CODE, 0x7000), w.addr(bof.ADDR_CODE, 0x7000), main_calls()(w)),
                 lambda w: w.addr(bof.ADDR_CODE, 0x7000))
        self.assertOk(self.link())

    def test_duplicate_global_names_both_modules(self):
        def hello(w):
            main_calls()(w)
            w.sectstat('helper')
            w.globl('helper')
            w.code(b'\xb0')
        self.std(hello)
        self.assertOneError(self.link(), 'duplicate symbol helper', 'module RUNTIME', 'module HELLO')

    def test_duplicate_absolute_symbol(self):
        self.std(lambda w: (main_calls()(w), w.abs_symbol(8, 'helper')))
        self.assertOneError(self.link(), 'duplicate symbol helper', 'module RUNTIME', 'module HELLO')

    def test_object_defining_end_is_a_duplicate(self):
        self.std(lambda w: (main_calls()(w), w.globl('__end')))
        self.assertOneError(self.link(), 'duplicate symbol __end', 'the linker', 'module HELLO')

    def test_object_defining_heap_is_a_duplicate(self):
        self.std(lambda w: (main_calls()(w), w.abs_symbol(0x9000, '__heap')))
        self.assertOneError(self.link(), 'duplicate symbol __heap', 'the linker', 'module HELLO')

    def test_undefined_symbol_used_by_kept_section(self):
        self.std(main_calls('nowhere'))
        self.assertOneError(self.link(), 'undefined symbol nowhere', 'module HELLO')

    def test_undefined_symbol_reported_once_per_module(self):
        def hello(w):
            main_calls('nowhere', 'nowhere', 'other')(w)
            w.sectstat('other')
            w.globl('other')
            abs16_call(w, 'nowhere')
        self.std(hello)
        self.assertOneError(self.link(), 'undefined symbol nowhere (used by module HELLO)')

    def test_undefined_local_label_used_by_kept_section(self):
        self.std(lambda w: (main_calls()(w), label_call(w, 7)))
        self.assertOneError(self.link(), 'undefined symbol HELLO label 7', 'module HELLO')

    def test_no_main_is_an_error(self):
        self.std(lambda w: (w.sectstat('start'), w.code(b'\xb0')))
        self.assertOneError(self.link(), 'undefined symbol F_main')

    def test_all_errors_are_collected(self):
        self.std(lambda w: (w.addr(bof.ADDR_CODE, 0x7000), main_calls('nowhere', size=32640)(w),
                            w.globl('helper')),
                 lambda w: w.addr(bof.ADDR_CODE, 0x6000))
        errors = self.link().errors
        self.assertEqual(len(errors), 4, errors)
        self.assertTrue(all(e.startswith('blink: error: ') for e in errors))
        for part in ('conflicting #code', 'duplicate symbol helper', 'undefined symbol nowhere',
                     'program too big'):
            self.assertTrue(any(part in e for e in errors), part)

    def test_missing_module_skips_mark_and_size_errors(self):
        self.std(lambda w: (w.need('UTIL'), main_calls('nowhere')(w)))
        link = self.link()
        self.assertOneError(link, 'module UTIL not found')
        self.assertTrue(link.incomplete)
        self.assertEqual(link.kept, [])


class MarkTests(BlinkTestCase):

    def test_unreferenced_section_is_dropped(self):
        self.std()
        link = self.link()
        self.assertOk(link)
        self.assertEqual(self.kept_names(link), [('RUNTIME', 'runtime_entry'), ('HELLO', 'F_main')])
        self.assertEqual([s.name for s in link.dropped], ['helper'])

    def test_referenced_section_is_kept(self):
        self.std(main_calls('helper'))
        link = self.link()
        self.assertOk(link)
        self.assertIn(('RUNTIME', 'helper'), self.kept_names(link))
        self.assertEqual(link.dropped, [])

    def test_section_referenced_only_by_dropped_section_is_dropped(self):
        def extra(w):
            w.sectstat('dead')
            abs16_call(w, 'helper')
        self.std(runtime_extra=extra)
        link = self.link()
        self.assertOk(link)
        self.assertEqual([s.name for s in link.dropped], ['helper', 'dead'])

    def test_undefined_symbol_used_only_by_dropped_section_is_not_an_error(self):
        def extra(w):
            w.sectstat('dead')
            abs16_call(w, 'sys_stackhead')
        self.std(runtime_extra=extra)
        link = self.link()
        self.assertOk(link)
        self.assertIn('dead', [s.name for s in link.dropped])

    def test_marking_is_transitive_across_modules_and_local_labels(self):
        def hello(w):
            w.need('UTIL')
            main_calls('util')(w)
        def util(w):
            w.sectstat('util')
            w.globl('util')
            label_call(w, 0)
            w.sectstat('inner')
            w.label(0)
            abs16_call(w, 'helper')
        self.std(hello)
        self.obj('UTIL', util)
        link = self.link()
        self.assertOk(link)
        self.assertEqual(self.kept_names(link), [('RUNTIME', 'runtime_entry'), ('HELLO', 'F_main'),
                                                 ('RUNTIME', 'helper'), ('UTIL', 'util'), ('UTIL', 'inner')])

    def test_main_reached_with_entry_referencing_nothing(self):
        self.std()
        link = self.link()
        self.assertOk(link)
        self.assertEqual(link.entry.refs, [])
        self.assertIs(link.main_section, link.modules[1].sections[0])
        self.assertTrue(link.main_section.kept)

    def test_main_is_placed_right_after_the_entry(self):
        self.obj('RUNTIME', runtime, self.lib_dir)
        self.obj('HELLO', lambda w: (w.sectstat('first'), w.globl('first'), w.code(b'\xb0'),
                                     w.sectstat('main'), w.globl('F_main'), abs16_call(w, 'helper'),
                                     abs16_call(w, 'first')))
        link = self.link()
        self.assertOk(link)
        self.assertEqual(self.kept_names(link), [('RUNTIME', 'runtime_entry'), ('HELLO', 'main'),
                                                 ('RUNTIME', 'helper'), ('HELLO', 'first')])
        self.assertEqual([s.address for s in link.kept], [0x6000, 0x6004, 0x600a, 0x600c])

    def test_sectabs_sections_are_always_kept_and_not_in_the_image(self):
        def extra(w):
            w.sectabs(0x0100, 'vector')
            w.code(b'\x01\x02\x03')
        self.std(runtime_extra=extra)
        link = self.link()
        self.assertOk(link)
        vector = [s for s in link.kept if s.name == 'vector'][0]
        self.assertTrue(vector.absolute)
        self.assertEqual(vector.address, 0x0100)
        self.assertEqual(link.placed, link.kept[:2])
        self.assertEqual(link.size, 4 + 1)

    def test_sectabs_overlapping_the_image_is_an_error(self):
        def extra(w):
            w.sectabs(0x6003, 'patch')
            w.code(b'\x01\x02')
        self.std(runtime_extra=extra)
        self.assertOneError(self.link(), "section 'patch' of module RUNTIME", 'overlaps', 'program image')

    def test_sectabs_sections_overlapping_each_other_is_an_error(self):
        def extra(w):
            w.sectabs(0x0100, 'one')
            w.code(b'\x01\x02')
            w.sectabs(0x0101, 'two')
            w.code(b'\x03')
        self.std(runtime_extra=extra)
        self.assertOneError(self.link(), "section 'one'", "section 'two'", 'overlaps')


class LayoutTests(BlinkTestCase):

    def test_code_default_is_6000(self):
        self.std(main_calls('helper'))
        link = self.link()
        self.assertOk(link)
        self.assertEqual(link.code, 0x6000)
        self.assertEqual([s.address for s in link.placed], [0x6000, 0x6004, 0x6008])
        self.assertEqual(link.size, 10)
        self.assertEqual(link.end, 0x600a)

    def test_code_override(self):
        self.std(lambda w: (w.addr(bof.ADDR_CODE, 0x7000), main_calls('helper')(w)))
        link = self.link()
        self.assertOk(link)
        self.assertEqual(link.code, 0x7000)
        self.assertEqual([s.address for s in link.placed], [0x7000, 0x7004, 0x7008])
        self.assertEqual(link.symbols['helper'], 0x7008)
        self.assertEqual(link.symbols['F_main'], 0x7004)

    def test_global_offsets_and_absolute_symbols(self):
        def hello(w):
            w.abs_symbol(0x0008, 'os_metacall')
            w.sectstat('F_main')
            w.code(b'\x00\x00')
            w.globl('F_main')
            abs16_call(w, 'os_metacall')
        self.std(hello)
        link = self.link()
        self.assertOk(link)
        self.assertEqual(link.symbols['F_main'], 0x6006)
        self.assertEqual(link.symbols['os_metacall'], 0x0008)

    def test_end_and_heap_are_defined(self):
        self.std(lambda w: (w.addr(bof.ADDR_HEAP, 0x9000), main_calls('__end', '__heap')(w)))
        link = self.link()
        self.assertOk(link)
        self.assertEqual(link.symbols['__end'], 0x600b)
        self.assertEqual(link.symbols['__heap'], 0x9000)

    def test_heap_without_heap_address_is_undefined(self):
        self.std(main_calls('__heap'))
        link = self.link()
        self.assertOneError(link, 'undefined symbol __heap', 'module HELLO')
        self.assertNotIn('__heap', link.symbols)

    def test_fixes_are_kept_with_their_code_records(self):
        self.std(main_calls('helper'))
        link = self.link()
        main = link.main_section
        self.assertEqual(len(main.chunks), 1)
        self.assertEqual(main.chunks[0].offset, 0)
        self.assertEqual(main.chunks[0].data, b'\xa8\x00\x00\xb0')
        fix = main.chunks[0].fixes[0]
        self.assertEqual((fix.kind, fix.offset, fix.target), (bof.FIX_ABS16, 1, 0))
        self.assertEqual(link.target_address(main.module, fix.target), 0x6008)

    def test_target_address_of_local_label(self):
        def hello(w):
            main_calls()(w)
            w.code(b'\x00')
            w.label(3)
            w.code(b'\x00')
            k = bof.local_label_target(3)
            w.code(b'\x00\x00', [(bof.FIX_LO8, 1, k)])
        self.std(hello)
        link = self.link()
        self.assertOk(link)
        main = link.main_section
        self.assertEqual(link.target_address(main.module, bof.local_label_target(3)), 0x6006)
        self.assertEqual(main.chunks[-1].fixes[0].kind, bof.FIX_LO8)

    def test_layout_is_deterministic(self):
        self.std(main_calls('helper'))
        a = self.link()
        b = self.link()
        self.assertEqual([(s.module.name, s.name, s.address) for s in a.kept],
                         [(s.module.name, s.name, s.address) for s in b.kept])
        self.assertEqual(a.symbols, b.symbols)


class SizeCheckTests(BlinkTestCase):
    # runtime_entry is 4 bytes and F_main is its filler plus a 1-byte `ret`.

    def link_size(self, size, addrs=()):
        self.std(lambda w: ([w.addr(k, v) for k, v in addrs], main_calls(size=size - 5)(w)))
        return self.link()

    def test_size_at_the_limit(self):
        link = self.link_size(32640)
        self.assertOk(link)
        self.assertEqual(link.size, 32640)

    def test_size_one_byte_over(self):
        link = self.link_size(32641)
        self.assertOneError(link, 'program too big', '32641 bytes')

    def test_end_just_below_heap(self):
        link = self.link_size(0x100, [(bof.ADDR_HEAP, 0x6101)])
        self.assertOk(link)
        self.assertEqual(link.end, 0x6100)

    def test_end_reaching_heap(self):
        link = self.link_size(0x101, [(bof.ADDR_HEAP, 0x6101)])
        self.assertOneError(link, 'image end 6101', '#heap 6101')

    def test_end_just_below_codelimit(self):
        self.assertOk(self.link_size(0x100, [(bof.ADDR_CODELIMIT, 0x6101)]))

    def test_end_reaching_codelimit(self):
        link = self.link_size(0x101, [(bof.ADDR_CODELIMIT, 0x6101)])
        self.assertOneError(link, 'image end 6101', '#codelimit 6101')


class RealRuntimeTests(BlinkTestCase):

    def test_real_runtime_keeps_entry_and_what_main_reaches(self):
        shutil.copy(os.path.join(SRC, 'bc', 'runtime.basm'), self.lib_dir)
        completed = subprocess.run(
            [sys.executable, os.path.join(SRC, 'bc81asmc', 'bc81asmc.py'), '--obj',
             os.path.join(self.lib_dir, 'runtime.basm')],
            cwd=os.path.join(SRC, 'bc81asmc'), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.obj('HELLO', main_calls('printstr', 'print_newline'))
        link = self.link()
        self.assertOk(link)
        self.assertEqual(link.modules[0].name, 'RUNTIME')
        self.assertEqual(link.kept[0].name, 'runtime_entry')
        self.assertEqual(link.kept[1].name, 'F_main')
        self.assertEqual(link.placed[0].address, 0x6000)
        self.assertEqual(set(s.name for s in link.kept),
                         {'runtime_entry', 'F_main', 'printstr', 'print_newline'})
        dropped = set(s.name for s in link.dropped)
        self.assertIn('mseek', dropped)
        self.assertIn('stackoffscalc', dropped)
        self.assertEqual(link.size, sum(s.size for s in link.placed))



# ---------------------------------------------------------------------------------------
# T2: pass 2, output and CLI
# ---------------------------------------------------------------------------------------
ASM_DIR = os.path.join(SRC, 'bc81asmc')
BLINK = os.path.join(SRC, 'blink.py')


def jmr_to(w, target):
    """`jmr z, :x` (`70 dd`) through a REL7 fix to the 16-bit `target`."""
    w.code(b'\x70\x00', [(bof.FIX_REL7, 1, target)])


def jrx_to(w, target):
    """`jrx z, :x` (`e1 00 hh ll`) through a REL15 fix; the target sits in the placeholder."""
    w.code(bytes((0xe1, 0x00, target >> 8, target & 0xff)), [(bof.FIX_REL15, 2)])


def run_python(code, cwd):
    return subprocess.run([sys.executable, '-c', code], cwd=cwd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='replace')


class Pass2TestCase(BlinkTestCase):

    def resolve(self, name='HELLO'):
        return blink.link_program(os.path.join(self.main_dir, name.lower()), lib_dir=self.lib_dir)

    def main_bytes(self, link):
        """The bytes of F_main's section in the image."""
        s = link.main_section
        return link.image[s.address - link.code:s.address - link.code + s.size]


class FixKindTests(Pass2TestCase):
    # runtime_entry is 4 bytes at 0x6000, so F_main starts at 0x6004 and `helper` follows it.

    def test_abs16_symbol_across_modules(self):
        self.std(main_calls('helper'))
        link = self.resolve()
        self.assertOk(link)
        self.assertEqual(link.image, b'\x11\xff\x11\xff' + b'\xa8\x60\x08\xb0' + b'\x00\xb0')

    def test_abs16_local_label_within_section(self):
        self.std(lambda w: (main_calls()(w), w.label(2), label_call(w, 2)))
        link = self.resolve()
        self.assertOk(link)
        self.assertEqual(self.main_bytes(link), b'\xb0\xa8\x60\x05')

    def test_abs16_local_label_across_sections(self):
        def hello(w):
            main_calls()(w)
            label_call(w, 0)
            w.sectstat('inner')
            w.code(b'\x00')
            w.label(0)
            w.code(b'\xb0')
        self.std(hello)
        link = self.resolve()
        self.assertOk(link)
        self.assertEqual(self.main_bytes(link), b'\xb0\xa8\x60\x09')
        self.assertEqual(link.image[-2:], b'\x00\xb0')

    def test_hi8_and_lo8_symbol_and_local_label(self):
        def hello(w):
            k = w.extrn('helper')
            w.sectstat('F_main')
            w.globl('F_main')
            w.label(1)
            lab = bof.local_label_target(1)
            w.code(b'\x00\x00\x00\x00', [(bof.FIX_HI8, 0, k), (bof.FIX_LO8, 1, k),
                                         (bof.FIX_HI8, 2, lab), (bof.FIX_LO8, 3, lab)])
        self.std(hello)
        link = self.resolve()
        self.assertOk(link)
        self.assertEqual(link.symbols['helper'], 0x6008)
        self.assertEqual(self.main_bytes(link), b'\x60\x08\x60\x04')

    def test_hilo_symbol_and_local_label(self):
        def hello(w):
            k = w.extrn('helper')
            w.sectstat('F_main')
            w.globl('F_main')
            w.code(b'\x18\x00\x14\x00', [(bof.FIX_HILO, 1, k)])
            w.label(5)
            w.code(b'\x18\x00\x14\x00', [(bof.FIX_HILO, 1, bof.local_label_target(5))])
        self.std(hello)
        link = self.resolve()
        self.assertOk(link)
        self.assertEqual(self.main_bytes(link), b'\x18\x60\x14\x0c' + b'\x18\x60\x14\x08')

    def test_abs16_to_absolute_symbol(self):
        self.std(lambda w: (w.abs_symbol(0x0008, 'os_metacall'), main_calls('os_metacall')(w)))
        link = self.resolve()
        self.assertOk(link)
        self.assertEqual(self.main_bytes(link), b'\xa8\x00\x08\xb0')

    def test_rel7_local_label_forward_and_backward_within_section(self):
        def hello(w):
            w.sectstat('F_main')
            w.globl('F_main')
            w.label(0)
            jmr_to(w, bof.local_label_target(1))       # placeholder 0x6005, target 0x6007
            w.code(b'\x00')
            w.label(1)
            jmr_to(w, bof.local_label_target(0))       # placeholder 0x6008, target 0x6004
        self.std(hello)
        link = self.resolve()
        self.assertOk(link)
        # forward: 0x6007 - 0x6005 + 1 = 3; backward: 0x6004 - 0x6008 + 1 = -3 -> 0x83
        self.assertEqual(self.main_bytes(link), b'\x70\x03\x00\x70\x83')

    def test_rel7_symbol_across_sections(self):
        self.std(lambda w: (w.sectstat('F_main'), w.globl('F_main'), jmr_to(w, w.extrn('helper'))))
        link = self.resolve()
        self.assertOk(link)
        # helper at 0x6006, placeholder 0x6005: 0x6006 - 0x6005 + 1 = 2
        self.assertEqual(self.main_bytes(link), b'\x70\x02')

    def test_rel15_local_label_forward_and_backward(self):
        def hello(w):
            w.sectstat('F_main')
            w.globl('F_main')
            w.label(0)
            jrx_to(w, bof.local_label_target(1))       # placeholder 0x6006, target 0x6009
            w.code(b'\x00')
            w.label(1)
            jrx_to(w, bof.local_label_target(0))       # placeholder 0x600b, target 0x6004
        self.std(hello)
        link = self.resolve()
        self.assertOk(link)
        # forward: 0x6009 - 0x6006 - 1 = 2; backward: 0x6004 - 0x600b - 1 = -8 -> 0x8008
        self.assertEqual(self.main_bytes(link), b'\xe1\x00\x00\x02\x00\xe1\x00\x80\x08')

    def test_rel15_symbol_across_modules(self):
        def hello(w):
            k = w.extrn('helper')
            w.sectstat('F_main')
            w.globl('F_main')
            w.code(bytes((0xa9, k >> 8, k & 0xff)), [(bof.FIX_REL15, 1)])     # clr :helper
        self.std(hello)
        link = self.resolve()
        self.assertOk(link)
        # helper at 0x6007, placeholder 0x6005: 0x6007 - 0x6005 - 1 = 1
        self.assertEqual(self.main_bytes(link), b'\xa9\x00\x01')

    def test_fix_in_a_later_code_record_of_the_section(self):
        def hello(w):
            main_calls()(w)
            w.code(bytes(300))
            abs16_call(w, 'helper')
        self.std(hello)
        link = self.resolve()
        self.assertOk(link)
        self.assertGreater(len(link.main_section.chunks), 1)
        self.assertEqual(self.main_bytes(link)[-3:], bytes((0xa8, 0x61, 0x34)))

    def test_image_is_the_placed_sections_in_layout_order(self):
        self.std(main_calls('helper'))
        link = self.resolve()
        self.assertEqual(len(link.image), link.size)
        self.assertEqual(link.image[link.placed[2].address - link.code:], b'\x00\xb0')

    def test_output_is_deterministic(self):
        self.std(main_calls('helper', '__end'))
        self.assertEqual(self.resolve().image, self.resolve().image)


class RelativeRangeTests(Pass2TestCase):
    # F_main is at 0x6004; its first jump's placeholder is at 0x6005 (jmr) or 0x6006 (jrx).

    def rel7_forward(self, distance):
        """jmr at the start of F_main to local label 3, `distance` bytes ahead (as encoded)."""
        def hello(w):
            w.sectstat('F_main')
            w.globl('F_main')
            jmr_to(w, bof.local_label_target(3))
            w.code(bytes(distance - 2))
            w.label(3)
            w.code(b'\xb0')
        self.std(hello)
        return self.resolve()

    def rel7_backward(self, distance):
        def hello(w):
            w.sectstat('F_main')
            w.globl('F_main')
            w.label(3)
            w.code(bytes(distance))
            jmr_to(w, bof.local_label_target(3))
        self.std(hello)
        return self.resolve()

    def test_rel7_plus_127(self):
        link = self.rel7_forward(127)
        self.assertOk(link)
        self.assertEqual(self.main_bytes(link)[:2], b'\x70\x7f')

    def test_rel7_plus_128_names_the_label(self):
        link = self.rel7_forward(128)
        self.assertOneError(link, 'relative jump to HELLO label 3 out of range', '128 bytes', 'REL7',
                            "section 'F_main' of module HELLO")

    def test_rel7_minus_127(self):
        link = self.rel7_backward(127)
        self.assertOk(link)
        self.assertEqual(self.main_bytes(link)[-2:], b'\x70\xff')

    def test_rel7_minus_128_names_the_label(self):
        self.assertOneError(self.rel7_backward(128), 'relative jump to HELLO label 3 out of range',
                            '-128 bytes')

    def test_rel7_out_of_range_names_the_symbol(self):
        self.std(lambda w: (w.sectstat('F_main'), w.globl('F_main'), jmr_to(w, w.extrn('far_away')),
                            w.abs_symbol(0x6005 - 1 + 0x80, 'far_away')))
        self.assertOneError(self.resolve(), 'relative jump to far_away out of range', '128 bytes')

    def rel15_abs(self, value, code=None):
        """jrx at the start of F_main to the absolute symbol `far` = `value`."""
        def hello(w):
            if code is not None:
                w.addr(bof.ADDR_CODE, code)
            w.abs_symbol(value, 'far')
            w.sectstat('F_main')
            w.globl('F_main')
            jrx_to(w, w.extrn('far'))
        self.std(hello)
        return self.resolve()

    def test_rel15_plus_32767(self):
        link = self.rel15_abs(0x6006 + 1 + 0x7fff)
        self.assertOk(link)
        self.assertEqual(self.main_bytes(link), b'\xe1\x00\x7f\xff')

    def test_rel15_plus_32768_names_the_symbol(self):
        self.assertOneError(self.rel15_abs(0x6006 + 1 + 0x8000), 'relative jump to far out of range',
                            '32768 bytes', 'REL15', 'at most 32767')

    def test_rel15_minus_32767(self):
        link = self.rel15_abs(0x8006 + 1 - 0x7fff, code=0x8000)
        self.assertOk(link)
        self.assertEqual(self.main_bytes(link), b'\xe1\x00\xff\xff')

    def test_rel15_minus_32768_names_the_symbol(self):
        self.assertOneError(self.rel15_abs(0x8006 + 1 - 0x8000, code=0x8000),
                            'relative jump to far out of range', '-32768 bytes')

    def test_rel15_long_local_jump_within_the_image(self):
        def hello(w):
            w.sectstat('F_main')
            w.globl('F_main')
            jrx_to(w, bof.local_label_target(0))
            w.code(bytes(20000))
            w.label(0)
            w.code(b'\xb0')
        self.std(hello)
        link = self.resolve()
        self.assertOk(link)
        # 0x6004 + 4 + 20000 - 0x6006 - 1 = 20001
        self.assertEqual(self.main_bytes(link)[:4], bytes((0xe1, 0x00, 20001 >> 8, 20001 & 0xff)))


class EncoderEquivalenceTests(unittest.TestCase):
    """blink's REL7/REL15 encoding is the assembler's `patch_reference`, distance for distance."""

    CODE = r"""
import json
import bc81asmc
class C:
    def __init__(self):
        self.out = {}
    def emit_byte_at(self, addr, b):
        self.out[addr] = b
    def hi(self, b):
        return (b >> 8) & 0xff
    def lo(self, b):
        return b & 0xff
rows = []
for kind, span in (('lorel', 140), ('rel15', 140)):
    base = 0x4000
    targets = list(range(base - span, base + span))
    if kind == 'rel15':
        targets += list(range(base - 0x8002, base - 0x7ff0)) + list(range(base + 0x7ff0, base + 0x8002))
    for t in targets:
        c = C()
        err = bc81asmc.patch_reference(c, base, 'x', kind, t, False)
        rows.append([kind, t - base, None if err else [c.out[a] for a in sorted(c.out)]])
print('ROWS ' + json.dumps(rows))
"""

    def test_rel7_and_rel15_match_the_assembler(self):
        completed = run_python(self.CODE, ASM_DIR)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        line = [l for l in completed.stdout.splitlines() if l.startswith('ROWS ')][0]
        rows = json.loads(line[5:])
        self.assertGreater(len(rows), 500)
        base = 0x4000
        for kind, delta, expected in rows:
            if kind == 'lorel':
                value = blink.encode_rel7(blink.rel7_distance(base + delta, base))
                got = None if value is None else [value]
            else:
                value = blink.encode_rel15(blink.rel15_distance(base + delta, base))
                got = None if value is None else [value >> 8, value & 0xff]
            self.assertEqual(got, expected, (kind, delta))


HELLO_RT = (".global rt_put\n"
            ".sect runtime_entry\n"
            "            mov a, 0xff\n"
            "            mov a, 0xff\n"
            "rt_put:     mov a, 0xff\n"
            "            mov a, 0xff\n")

HELLO_MAIN = (".global F_main\n"
              ".extern rt_put\n"
              ".sect F_main\n"
              "F_main:     cal :rt_put\n"
              "            clr :sub\n"
              "            jrx z, :sub\n"
              "            jmr nz, :loop\n"
              "            .mv csci, :data\n"
              "loop:       jmp z, :loop\n"
              "            .db :sub, hi(:data), lo(:data)\n"
              "            ret\n"
              ".sect sub\n"
              "sub:        jmr z, :F_main\n"
              "            jrx nz, :loop\n"
              "            .mv dsdi, :rt_put\n"
              "            clr :rt_put\n"
              "            ret\n"
              ".sect data\n"
              "data:       .db 0x01, 0x02\n")

class AssemblerEquivalenceTests(Pass2TestCase):
    """A multi-section program assembled flat and assembled with --obj + linked: same bytes."""

    def assemble_obj(self, folder, name, text):
        path = os.path.join(folder, name + '.basm')
        with open(path, 'w', newline='\n') as fh:
            fh.write(text)
        completed = subprocess.run(
            [sys.executable, os.path.join(ASM_DIR, 'bc81asmc.py'), '--obj', path], cwd=ASM_DIR,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding='utf-8', errors='replace')
        self.assertEqual(completed.returncode, 0, completed.stdout)

    def assemble_flat(self, text):
        path = os.path.join(self.tmp, 'flat.basm')
        with open(path, 'w', newline='\n') as fh:
            fh.write(text)
        completed = run_python(
            'import bc81asmc\n'
            'path = %r\n'
            'c = bc81asmc.assemble_text(open(path).read(), path)\n'
            'print("BYTES %%04x %%s" %% (c.startaddr, bytes(c.bytes).hex()))\n' % path, ASM_DIR)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        line = [l for l in completed.stdout.splitlines() if l.startswith('BYTES ')][0]
        _, start, data = line.split()
        return int(start, 16), bytes.fromhex(data)

    def test_flat_and_linked_images_are_identical(self):
        self.assemble_obj(self.lib_dir, 'runtime', HELLO_RT)
        self.assemble_obj(self.main_dir, 'hello', HELLO_MAIN)
        link = self.resolve()
        self.assertOk(link)
        self.assertEqual([s.name for s in link.placed], ['runtime_entry', 'F_main', 'sub', 'data'])
        start, flat = self.assemble_flat('.org 0x6000\n' + HELLO_RT + HELLO_MAIN)
        self.assertEqual(start, 0x6000)
        self.assertEqual(link.code, 0x6000)
        self.assertEqual(link.image, flat)
        kinds = set(f.kind for s in link.placed for c in s.chunks for f in c.fixes)
        self.assertEqual(kinds, set(bof.FIX_ORDER))


class OutputTests(Pass2TestCase):

    def prg(self):
        return os.path.join(self.main_dir, 'hello.prg')

    def run_blink(self, *args, cwd=None):
        return subprocess.run([sys.executable, BLINK] + list(args), cwd=cwd or SRC,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              encoding='utf-8', errors='replace')

    def test_cli_writes_prg_and_prints_report(self):
        self.std(main_calls('helper'))
        completed = self.run_blink(os.path.join(self.main_dir, 'hello'), '--lib', self.lib_dir)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, 'blink: hello -> hello.prg, 10 bytes, 3 sections kept, 0 dropped\n')
        self.assertEqual(completed.stderr, '')
        with open(self.prg(), 'rb') as fh:
            self.assertEqual(fh.read(), b'\x11\xff\x11\xff\xa8\x60\x08\xb0\x00\xb0')

    def test_cli_counts_dropped_sections_and_accepts_o_suffix(self):
        self.std()
        completed = self.run_blink('hello.o', '--lib', self.lib_dir, cwd=self.main_dir)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, 'blink: hello -> hello.prg, 5 bytes, 2 sections kept, 1 dropped\n')
        self.assertTrue(os.path.isfile(self.prg()))

    def test_output_name_is_lower_case_beside_the_main_object(self):
        self.std()
        completed = self.run_blink(os.path.join(self.main_dir, 'HELLO'), '--lib', self.lib_dir)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('hello.prg', os.listdir(self.main_dir))
        self.assertNotIn('HELLO.prg', os.listdir(self.main_dir))
        self.assertEqual(sorted(os.listdir(self.lib_dir)), ['runtime.o'])

    def test_cli_is_deterministic(self):
        self.std(main_calls('helper', '__end'))
        target = os.path.join(self.main_dir, 'hello')
        self.assertEqual(self.run_blink(target, '--lib', self.lib_dir).returncode, 0)
        with open(self.prg(), 'rb') as fh:
            first = fh.read()
        self.assertEqual(self.run_blink(target, '--lib', self.lib_dir).returncode, 0)
        with open(self.prg(), 'rb') as fh:
            self.assertEqual(fh.read(), first)

    def test_cli_error_exit_1_every_error_on_stderr_and_no_file(self):
        self.std(lambda w: (main_calls('nowhere')(w), w.globl('helper')))
        completed = self.run_blink(os.path.join(self.main_dir, 'hello'), '--lib', self.lib_dir)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, '')
        lines = completed.stderr.splitlines()
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(all(l.startswith('blink: error: ') for l in lines))
        self.assertTrue(any('undefined symbol nowhere' in l for l in lines))
        self.assertTrue(any('duplicate symbol helper' in l for l in lines))
        self.assertFalse(os.path.exists(self.prg()))
        self.assertEqual(sorted(os.listdir(self.main_dir)), ['hello.o'])

    def test_range_error_leaves_an_old_prg_untouched(self):
        with open(self.prg(), 'wb') as fh:
            fh.write(b'old')
        self.std(lambda w: (w.sectstat('F_main'), w.globl('F_main'), jmr_to(w, w.extrn('far_away')),
                            w.abs_symbol(0x9000, 'far_away')))
        completed = self.run_blink(os.path.join(self.main_dir, 'hello'), '--lib', self.lib_dir)
        self.assertEqual(completed.returncode, 1)
        self.assertIn('blink: error: relative jump to far_away out of range', completed.stderr)
        with open(self.prg(), 'rb') as fh:
            self.assertEqual(fh.read(), b'old')
        self.assertEqual(sorted(os.listdir(self.main_dir)), ['hello.o', 'hello.prg'])

    def test_missing_module_exits_1_without_output(self):
        self.obj('RUNTIME', runtime, self.lib_dir)
        completed = self.run_blink(os.path.join(self.main_dir, 'hello'), '--lib', self.lib_dir)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stderr,
                         'blink: error: module HELLO not found (hello.o, needed by the command line)\n')
        self.assertFalse(os.path.exists(self.prg()))

    def test_size_error_writes_nothing(self):
        self.std(main_calls(size=32640))
        completed = self.run_blink(os.path.join(self.main_dir, 'hello'), '--lib', self.lib_dir)
        self.assertEqual(completed.returncode, 1)
        self.assertIn('program too big', completed.stderr)
        self.assertFalse(os.path.exists(self.prg()))

    def test_write_output_refuses_a_link_with_errors(self):
        self.std(main_calls('nowhere'))
        link = self.resolve()
        self.assertFalse(link.ok)
        with self.assertRaises(ValueError):
            blink.write_output(link)
        self.assertFalse(os.path.exists(self.prg()))

    def test_main_returns_0_and_writes(self):
        self.std()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = blink.main([os.path.join(self.main_dir, 'hello'), '--lib', self.lib_dir])
        self.assertEqual(status, 0)
        self.assertEqual(out.getvalue(), 'blink: hello -> hello.prg, 5 bytes, 2 sections kept, 1 dropped\n')
        with open(self.prg(), 'rb') as fh:
            self.assertEqual(fh.read(), b'\x11\xff\x11\xff\xb0')


class AbsoluteSectionOutputTests(Pass2TestCase):

    def test_empty_sectabs_section_is_fine(self):
        self.std(runtime_extra=lambda w: (w.sectabs(0x0100, 'marks'), w.globl('mark')))
        link = self.resolve()
        self.assertOk(link)
        self.assertEqual(link.image, b'\x11\xff\x11\xff\xb0')

    def test_sectabs_section_with_bytes_is_an_error(self):
        def extra(w):
            w.sectabs(0x0100, 'vector')
            w.code(b'\x01\x02\x03')
        self.std(runtime_extra=extra)
        link = self.resolve()
        self.assertOneError(link, "section 'vector' of module RUNTIME at 0100 has 3 bytes", 'hello.prg')

    def test_range_error_in_sectabs_section_is_reported(self):
        def extra(w):
            w.sectabs(0x0100, 'vector')
            jmr_to(w, w.extrn('F_main'))
        self.std(runtime_extra=extra)
        errors = self.resolve().errors
        self.assertTrue(any('relative jump to F_main out of range' in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()
