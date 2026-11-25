"""Object mode (`--obj`, #115): records, fixes, sections, symbol classes, errors, and the consistency of
the object with the flat assembly (a test-side resolver lays the sections out at the flat base and applies
every fix with the flat-mode arithmetic)."""
import contextlib
import glob
import io
import os
import tempfile
import unittest

import bc81asmc
from bc81asmc_diag import AssemblerError

import bof

HERE = os.path.dirname(os.path.abspath(__file__))
ASM_DIR = os.path.dirname(HERE)
SRC_DIR = os.path.dirname(ASM_DIR)

# doc 07 "Object file format", worked example HELLO.O (99 bytes)
HELLO_O = bytes.fromhex(
    'b0 06 01 48 45 4c 4c 4f'
    'de 05 53 54 44 49 4f'
    '55 06 46 5f 6d 61 69 6e'
    '91 06 46 5f 6d 61 69 6e'
    'c0 06 18 00 14 00 11 00'
    'fb 03 01 80 00'
    'ee 0d 73 74 61 63 6b 76 61 72 38 73 74 31 36'
    'c0 03 a8 00 00'
    'f1 01 01'
    'ee 06 46 5f 70 75 74 73'
    'c0 08 a8 00 01 18 00 14 00 b0'
    'f1 01 01'
    '1a 02 00 00'
    'c0 03 68 69 00'
    'ed 00')

HELLO_BASM = ("#link stdio\n"
              ".global F_main\n"
              ".extern stackvar8st16\n"
              ".extern F_puts\n"
              ".sect F_main\n"
              "F_main:   .mv csci, :DATA0020\n"
              "          mov a, 0x00\n"
              "          cal :stackvar8st16\n"
              "          cal :F_puts\n"
              "          mov cs, 0x00\n"
              "          mov ci, 0x00\n"
              "          ret\n"
              "DATA0020: .db 'hi', 0x00\n")

# a relocatable module with every reference form, several sections (implicit first, an empty one,
# a label on a .sect line), global labels, an exported and a local .def, forward and backward references
MULTI = (".global entry\n"
         ".global far\n"
         ".global value\n"
         ".def value, 0x1234\n"
         ".def local, 0x0f0e\n"
         "pre:    nop\n"
         "        jmr z, :pre\n"
         ".sect first\n"
         "entry:  cal :far\n"
         "        cal :pre\n"
         "        .mv csci, :tail\n"
         "        .mv dsdi, :local\n"
         "        .mv csci, :value\n"
         "back:   jmr nz, :back\n"
         "        jmr z, :fwd\n"
         "        jrx z, :far\n"
         "        jrx nz, :back\n"
         "        clr :entry\n"
         "        clr :tail\n"
         "        jmp z, :fwd\n"
         "fwd:    .db :tail, hi(:far), lo(:far), :local, hi(:local), lo(:value), 0x01, 'ab'\n"
         ".sect empty\n"
         "far:    .sect second\n"
         "        cal :entry\n"
         "        jmp nz, :back\n"
         "tail:   .db :entry, 0x00\n"
         "        ret\n")


def obj(text, name='prog.basm', directory=None):
    path = os.path.join(directory, name) if directory else name
    with contextlib.redirect_stdout(io.StringIO()):
        return bc81asmc.assemble_text(text, path, obj=True)


def flat(text, name='prog.basm'):
    with contextlib.redirect_stdout(io.StringIO()):
        return bc81asmc.assemble_text(text, name)


def obj_errors(text, name='prog.basm'):
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            bc81asmc.assemble_text(text, name, obj=True)
        except AssemblerError as error:
            return error.diagnostics
    raise AssertionError('no error')


def records(data):
    return bof.read_records(data)


def tags(data):
    return [r.tag for r in records(data)]


def sign_magnitude(diff, bits):
    if diff < 0:
        return (-diff) | (1 << (bits - 1))
    return diff


def resolve(data, base):
    """Lay the sections out in order (a SECTSTAT after the previous section, starting at `base`; a SECTABS at
    its address) and apply every fix with the flat-mode arithmetic. Returns (start address, image bytes)."""
    recs = records(data)
    sections = []          # [address, bytearray]
    symbols = []           # names of the EXTRN records
    globals_ = {}
    locals_ = {}
    pending = []           # (section index, offset of the CODE record in it, record)
    current = None
    code_start = 0
    for r in recs:
        if r.tag == bof.TAG_SECTSTAT:
            address = sections[-1][0] + len(sections[-1][1]) if sections else base
            sections.append([address, bytearray()])
            current = sections[-1]
        elif r.tag == bof.TAG_SECTABS:
            sections.append([r.fields['address'], bytearray()])
            current = sections[-1]
        elif r.tag == bof.TAG_EXTRN:
            symbols.append(r.fields['name'])
        elif r.tag == bof.TAG_GLOBL:
            globals_[r.fields['name']] = current[0] + len(current[1])
        elif r.tag == bof.TAG_ABS:
            globals_[r.fields['name']] = r.fields['value']
        elif r.tag == bof.TAG_LABEL:
            locals_[r.fields['n']] = current[0] + len(current[1])
        elif r.tag == bof.TAG_CODE:
            code_start = len(current[1])
            current[1] += r.fields['bytes']
        elif r.tag in bof.FIX_SPAN:
            pending.append((current, code_start, r))

    def address_of(target):
        if target & bof.LOCAL_LABEL_FLAG:
            return locals_[target & 0x7fff]
        return globals_[symbols[target]]

    for section, start, r in pending:
        image = section[1]
        if r.tag in bof.FIX_OFFSET_ONLY:
            entries = [(o, image[start + o] << 8 | image[start + o + 1]) for o in r.fields['offsets']]
        else:
            entries = r.fields['entries']
        for o, target in entries:
            at = start + o
            place = section[0] + at
            value = address_of(target)
            if r.tag == bof.FIX_ABS16:
                image[at], image[at + 1] = value >> 8, value & 0xff
            elif r.tag == bof.FIX_REL15:
                diff = sign_magnitude(value - place - 1, 16)
                image[at], image[at + 1] = diff >> 8, diff & 0xff
            elif r.tag == bof.FIX_HI8:
                image[at] = value >> 8
            elif r.tag == bof.FIX_LO8:
                image[at] = value & 0xff
            elif r.tag == bof.FIX_REL7:
                image[at] = sign_magnitude(value - place + 1, 8)
            elif r.tag == bof.FIX_HILO:
                image[at], image[at + 2] = value >> 8, value & 0xff
    start = sections[0][0]
    out = bytearray()
    for address, image in sections:
        assert address == start + len(out), 'sections are not contiguous'
        out += image
    return start, bytes(out)


def read_source(path):
    with open(path, 'r', encoding='utf8') as f:
        return f.read()


class TestHello(unittest.TestCase):
    def test_doc07_hello_o_byte_exact(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'stdio.h'), 'w') as f:
                f.write('#define STDIO_H 1\n')
            context = obj(HELLO_BASM, 'hello.basm', d)
        self.assertEqual(len(context.object_bytes), 99)
        self.assertEqual(context.object_bytes, HELLO_O)

    def test_link_from_header_is_written_at_include_line(self):
        source = HELLO_BASM.replace('#link stdio\n', '#include stdio.h\n')
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'stdio.h'), 'w') as f:
                f.write('#link stdio\n')
            context = obj(source, 'hello.basm', d)
        self.assertEqual(context.object_bytes, HELLO_O)


class TestFixKinds(unittest.TestCase):
    def fixes(self, data):
        """(tag, offset in its CODE record, target, CODE bytes)."""
        result = []
        code = b''
        for r in records(data):
            if r.tag == bof.TAG_CODE:
                code = r.fields['bytes']
            elif r.tag in bof.FIX_OFFSET_ONLY:
                result.extend((r.tag, o, code[o] << 8 | code[o + 1], code) for o in r.fields['offsets'])
            elif r.tag in bof.FIX_SPAN:
                result.extend((r.tag, o, t, code) for o, t in r.fields['entries'])
        return result

    def one_fix(self, line, kind, offset):
        data = obj("x: nop\n" + line + "\n").object_bytes
        found = self.fixes(data)
        self.assertEqual(len(found), 1, found)
        tag, off, target, code = found[0]
        self.assertEqual((tag, off), (kind, offset))
        self.assertEqual(target, bof.local_label_target(0))
        return code

    def test_cal_is_abs16_with_target_in_placeholder(self):
        code = self.one_fix('cal :x', bof.FIX_ABS16, 2)
        self.assertEqual(code[2:4], b'\x80\x00')

    def test_db_label_is_abs16(self):
        code = self.one_fix('.db 0x01, :x', bof.FIX_ABS16, 2)
        self.assertEqual(code[1:4], b'\x01\x80\x00')

    def test_jrx_and_clr_are_rel15(self):
        for line in ('jrx z, :x', 'clr :x'):
            data = obj("x: nop\n" + line + "\n").object_bytes
            (tag, off, target, code), = self.fixes(data)
            self.assertEqual(tag, bof.FIX_REL15, line)
            self.assertEqual(target, 0x8000)
            self.assertEqual(code[off:off + 2], b'\x80\x00')

    def test_hi_and_lo_bytes(self):
        data = obj("x: nop\n.db hi(:x), lo(:x)\n").object_bytes
        found = [(t, o, tg, c[o]) for t, o, tg, c in self.fixes(data)]
        self.assertEqual(found, [(bof.FIX_HI8, 1, 0x8000, 0), (bof.FIX_LO8, 2, 0x8000, 0)])

    def test_jmp_is_lo8(self):
        data = obj("x: nop\njmp z, :x\n").object_bytes
        (tag, off, target, code), = self.fixes(data)
        self.assertEqual((tag, off, target, code[off]), (bof.FIX_LO8, 2, 0x8000, 0))

    def test_jmr_is_rel7(self):
        data = obj("x: nop\njmr z, :x\n").object_bytes
        (tag, off, target, code), = self.fixes(data)
        self.assertEqual((tag, off, target, code[off]), (bof.FIX_REL7, 2, 0x8000, 0))

    def test_mv_is_hilo(self):
        data = obj("x: nop\n.mv dsdi, :x\n").object_bytes
        (tag, off, target, code), = self.fixes(data)
        self.assertEqual((tag, off, target), (bof.FIX_HILO, 2, 0x8000))
        self.assertEqual((code[off], code[off + 2]), (0, 0))

    def test_forward_and_backward_references_number_by_first_appearance(self):
        data = obj("a: cal :c\nb: cal :a\nc: nop\n").object_bytes
        recs = records(data)
        labels = [r.fields['n'] for r in recs if r.tag == bof.TAG_LABEL]
        self.assertEqual(labels, [0, 2, 1])   # a=0, c=1 (forward use), b=2
        code = b''.join(r.fields['bytes'] for r in recs if r.tag == bof.TAG_CODE)
        self.assertEqual(code[1:3], b'\x80\x01')
        self.assertEqual(code[4:6], b'\x80\x00')

    def test_long_db_lo_list_continues(self):
        count = 100
        items = ', '.join('lo(:x)' for _ in range(count))
        data = obj("x: .db " + items + "\n").object_bytes
        recs = records(data)
        lo = [r for r in recs if r.tag == bof.TAG_LO8]
        self.assertEqual([len(r.fields['entries']) for r in lo], [85, 15])
        offsets = [o for r in lo for o, _ in r.fields['entries']]
        self.assertEqual(offsets, list(range(count)))
        i = recs.index(lo[0])
        self.assertEqual(recs[i - 1].tag, bof.TAG_CODE)
        self.assertEqual(recs[i + 1], lo[1])

    def test_long_db_split_keeps_abs16_whole(self):
        items = ', '.join(['0x01', '0x02'] + [':x'] * 200)
        data = obj("x: .db " + items + "\n").object_bytes
        recs = records(data)
        codes = [r for r in recs if r.tag == bof.TAG_CODE]
        self.assertEqual([len(c.fields['bytes']) for c in codes], [254, 148])  # 255 would cut an item
        context = flat("x: .db " + items + "\n")
        self.assertEqual(resolve(data, 0)[1], bytes(context.bytes))


class TestSectionsAndSymbols(unittest.TestCase):
    def test_implicit_first_section_named_after_module(self):
        data = obj("nop\n", 'my_prog.basm').object_bytes
        recs = records(data)
        self.assertEqual(recs[0].fields['module'], 'MY_PROG')
        self.assertEqual((recs[1].tag, recs[1].fields['name']), (bof.TAG_SECTSTAT, 'MY_PROG'))

    def test_file_starting_with_sect_has_no_implicit_section(self):
        data = obj(".sect code\nnop\n").object_bytes
        self.assertEqual([r.fields['name'] for r in records(data) if r.tag == bof.TAG_SECTSTAT], ['code'])

    def test_multiple_and_empty_sections(self):
        data = obj("nop\n.sect a\n.sect b\nnop\n").object_bytes
        self.assertEqual(tags(data), [bof.TAG_HEADER, bof.TAG_SECTSTAT, bof.TAG_CODE, bof.TAG_SECTSTAT,
                                      bof.TAG_SECTSTAT, bof.TAG_CODE, bof.TAG_END])

    def test_label_at_section_offset_zero_and_on_sect_line(self):
        data = obj(".global g\nnop\nl: .sect s\ng: nop\n").object_bytes
        self.assertEqual(tags(data), [bof.TAG_HEADER, bof.TAG_SECTSTAT, bof.TAG_CODE, bof.TAG_SECTSTAT,
                                      bof.TAG_LABEL, bof.TAG_GLOBL, bof.TAG_CODE, bof.TAG_END])
        out = bof.dump(data)
        self.assertIn('label 0 @0000', out)
        self.assertIn("'g' @0000", out)

    def test_org_file_is_one_sectabs(self):
        data = obj(".org 0x0e00\n.def k, 0x0001\nstart: nop\ncal :start\n", 'boot.basm').object_bytes
        recs = records(data)
        self.assertEqual((recs[1].tag, recs[1].fields['address'], recs[1].fields['name']),
                         (bof.TAG_SECTABS, 0x0e00, 'BOOT'))
        self.assertEqual(recs[2].tag, bof.TAG_LABEL)

    def test_empty_org_file_still_has_its_section(self):
        data = obj(".org 0x0100\n").object_bytes
        self.assertEqual(tags(data), [bof.TAG_HEADER, bof.TAG_SECTABS, bof.TAG_END])

    def test_exported_def_is_abs_and_referenced_through_extrn(self):
        data = obj(".global k\n.def k, 0x1234\nnop\ncal :k\n").object_bytes
        recs = records(data)
        self.assertEqual((recs[1].tag, recs[1].fields['value'], recs[1].fields['name']), (bof.TAG_ABS, 0x1234, 'k'))
        self.assertIn(bof.TAG_EXTRN, tags(data))

    def test_local_def_resolved_in_place(self):
        data = obj(".def k, 0x1234\ncal :k\n.mv csci, :k\n").object_bytes
        recs = records(data)
        self.assertEqual(tags(data), [bof.TAG_HEADER, bof.TAG_SECTSTAT, bof.TAG_CODE, bof.TAG_END])
        code = recs[2].fields['bytes']
        self.assertEqual(code[1:3], b'\x12\x34')
        self.assertEqual((code[4], code[6]), (0x12, 0x34))

    def test_extrn_at_first_use_for_globals_and_externals(self):
        data = obj(".global g\n.extern e\ng: nop\ncal :e\ncal :g\ncal :e\n").object_bytes
        recs = records(data)
        self.assertEqual([r.fields['name'] for r in recs if r.tag == bof.TAG_EXTRN], ['e', 'g'])
        i = [r.tag for r in recs].index(bof.TAG_EXTRN)
        self.assertEqual(recs[i - 1].tag, bof.TAG_CODE)    # the ee flushed the open CODE record

    def test_need_per_link_occurrence_with_repeats(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'lib.h'), 'w') as f:
                f.write('#link stdio\n')
            data = obj("#link stdio\nnop\n#include lib.h\n#link std\nnop\n", 'p.basm', d).object_bytes
        recs = records(data)
        self.assertEqual([(r.tag, r.fields.get('name')) for r in recs[1:-1]],
                         [(bof.TAG_NEED, 'STDIO'), (bof.TAG_SECTSTAT, 'P'), (bof.TAG_CODE, None),
                          (bof.TAG_NEED, 'STDIO'), (bof.TAG_NEED, 'STD'), (bof.TAG_CODE, None)])

    def test_assert_evaluated_in_org_file(self):
        obj(".org 0x0100\nnop\ne: .assert :e <= 0x0101\n")
        diags = obj_errors(".org 0x0100\nnop\ne: .assert :e <= 0x0100\n")
        self.assertIn('assertion failed', diags[0].message)

    def test_assert_on_label_skipped_with_warning_in_relocatable(self):
        context = obj("nop\ne: .assert :e <= 0x0000\n")
        self.assertEqual(len(context.warnings), 1)
        w = context.warnings[0]
        self.assertEqual((w.severity, w.line, w.column), ('warning', 2, 12))
        self.assertEqual(w.message, ".assert not checked with --obj: ':e' is relocatable")
        self.assertTrue(context.object_bytes)

    def test_assert_on_defs_evaluated_in_relocatable(self):
        diags = obj_errors(".def a, 0x0002\nnop\n.assert :a < 0x0001\n")
        self.assertIn('assertion failed', diags[0].message)

    def test_no_relative_range_check(self):
        filler = '.db ' + ', '.join(['0x00'] * 200) + '\n'
        obj("x: nop\n" + filler + "jmr z, :x\n")


class TestErrors(unittest.TestCase):
    def one(self, text, line, fragment):
        diags = obj_errors(text)
        self.assertEqual(len([d for d in diags if d.severity == 'error']), 1, diags)
        d = [d for d in diags if d.severity == 'error'][0]
        self.assertEqual(d.line, line, d)
        self.assertIn(fragment, d.message)
        return d

    def test_sect_in_org_file(self):
        self.one(".org 0x0100\nnop\n.sect s\n", 3, '.sect is not allowed in an .org file')

    def test_org_after_sect_global_extern(self):
        for first in ('.sect s', '.global g', '.extern e'):
            text = first + "\n.org 0x0100\n" + ("g: nop\n" if 'global' in first else "nop\n")
            self.one(text, 2, '.org must come before .sect, .global and .extern')

    def test_duplicate_section(self):
        self.one(".sect s\nnop\n.sect s\n", 3, "duplicate section 's' (first started at line 1)")

    def test_global_never_defined(self):
        d = self.one("nop\n.global g\n", 2, "'.global g' is never defined")
        self.assertEqual(d.column, 9)

    def test_extern_defined(self):
        self.one(".extern e\ne: nop\n", 2, "'e' is declared .extern (line 1) and must not be defined")
        self.one(".extern e\n.def e, 0x0001\n", 2, "'e' is declared .extern")

    def test_global_and_extern(self):
        self.one(".global g\n.extern g\ng: nop\n", 2, "both .global and .extern")

    def test_declaration_after_use_or_definition(self):
        self.one("cal :g\n.global g\ng: nop\n", 2, "'.global g' must come before the first use or definition")
        self.one("g: nop\n.global g\n", 2, "must come before the first use or definition of 'g' (line 1)")
        self.one("cal :e\n.extern e\n", 2, "'.extern e' must come before")

    def test_repeated_declaration_is_harmless(self):
        obj(".global g\n.global g\ng: nop\n")

    def test_def_used_before_defined(self):
        self.one("cal :k\n.def k, 0x0001\n", 1, "'k' is used before its .def (line 2)")

    def test_undefined_label(self):
        self.one("cal :nowhere\n", 1, "undefined label ':nowhere'")

    def test_relative_jump_to_local_def_in_relocatable(self):
        self.one(".def k, 0x0001\njmr z, :k\n", 2, "relative jump to the constant ':k'")

    def test_flat_mode_unaffected_by_object_rules(self):
        # declarations after use are fine without --obj
        flat("cal :g\n.global g\ng: nop\n")


def consistency_sources():
    paths = [os.path.join(SRC_DIR, 'bdos', 'boot.basm'), os.path.join(ASM_DIR, 'bcOS', 'bcos.basm')]
    paths += sorted(glob.glob(os.path.join(ASM_DIR, 'examples', '*.basm')))
    return paths


class TestConsistencyWithFlat(unittest.TestCase):
    def check(self, text, name):
        flat_context = flat(text, name)
        data = obj(text, name).object_bytes
        start, image = resolve(data, flat_context.startaddr)
        self.assertEqual(start, flat_context.startaddr, name)
        self.assertEqual(image, bytes(flat_context.bytes), name)

    def test_repo_sources(self):
        for path in consistency_sources():
            with self.subTest(path=path):
                data = obj(read_source(path), os.path.basename(path)).object_bytes
                self.assertEqual(sum(1 for t in tags(data) if t == bof.TAG_SECTABS), 1)
                self.check(read_source(path), os.path.basename(path))

    def test_multi_section_relocatable(self):
        data = obj(MULTI, 'multi.basm').object_bytes
        present = set(tags(data))
        for kind in bof.FIX_ORDER:
            self.assertIn(kind, present, hex(kind))
        self.assertEqual([r.fields['name'] for r in records(data) if r.tag == bof.TAG_SECTSTAT],
                         ['MULTI', 'first', 'empty', 'second'])
        self.check(MULTI, 'multi.basm')

    def test_deterministic_in_process(self):
        self.assertEqual(obj(MULTI).object_bytes, obj(MULTI).object_bytes)


if __name__ == '__main__':
    unittest.main()
