"""Unit tests of src/blink.py: pass 1, mark, layout and size checks (#117, T1).

Objects are built with `bof.BofWriter` into a temp folder, so every case is exact and does not
depend on the assembler. One test links the real runtime (built from src/bc/runtime.basm) and
checks only the structure of the result, never its bytes (#188 changes them).
"""
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


if __name__ == '__main__':
    unittest.main()
