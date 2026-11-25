import contextlib
import io
import os
import tempfile
import unittest

import bc81asmc
import bc81asmc_pre as pre
from bc81asmc_diag import AssemblerError, format_diagnostics
from bc81asmc_listing import format_listing, format_map


class PreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf8', newline='') as f:
            f.write(text)
        return path

    def run_pre(self, text, name='prog.basm'):
        return pre.prepass(text, os.path.join(self.dir, name))

    def assemble(self, text, name='prog.basm'):
        with contextlib.redirect_stdout(io.StringIO()):
            return bc81asmc.assemble_text(text, os.path.join(self.dir, name))

    def messages(self, result, severity='error'):
        return [d.message for d in result.diagnostics if d.severity == severity]


class TestHeaders(PreCase):
    def test_header_with_defines_comments_and_prototypes(self):
        self.write('a.h', "// a header\n\n#define ONE 1\nbyte f(byte x);\nword g(word a, byte b)\n"
                          "byte h(byte x) ***;\nword k() *** // note\n  #define TWO 0x02 // two\n")
        r = self.run_pre("#include a.h\nnop\n")
        self.assertEqual(r.diagnostics, [])
        self.assertEqual(r.defines.lookup('ONE', 2).value, '1')
        self.assertEqual(r.defines.lookup('TWO', 2).value, '0x02')
        self.assertEqual(r.text, ";\nnop\n")

    def test_header_body_line_is_error_naming_header_and_line(self):
        path = self.write('a.h', "#define X 1\nbyte f(byte x) { return x; }\n")
        r = self.run_pre("#include a.h\n")
        self.assertEqual(len(r.diagnostics), 1)
        d = r.diagnostics[0]
        self.assertEqual((d.file, d.line), (path, 2))
        self.assertTrue(r.errors)

    def test_header_global_variable_is_error(self):
        self.write('a.h', "byte counter;\n")
        r = self.run_pre("#include a.h\n")
        self.assertEqual(r.diagnostics[0].line, 1)
        self.assertTrue(r.errors)

    def test_nested_includes_resolve_against_main_dir(self):
        self.write('sub/a.h', "#include b.h\n")
        self.write('b.h', "#define DEEP 5\n")
        r = self.run_pre("#include sub/a.h\n")
        self.assertEqual(r.diagnostics, [])
        self.assertEqual(r.defines.lookup('DEEP', 2).value, '5')
        self.assertIsNone(r.defines.lookup('DEEP', 1))

    def test_cycle_is_error_not_hang(self):
        self.write('a.h', "#include b.h\n")
        self.write('b.h', "#include a.h\n")
        r = self.run_pre("#include a.h\n")
        self.assertTrue(any('include cycle' in m for m in self.messages(r)))

    def test_missing_file_error_at_include_line_of_right_file(self):
        path = self.write('a.h', "\n#include nope.h\n")
        r = self.run_pre("nop\n#include a.h\n")
        d = r.diagnostics[0]
        self.assertEqual((d.file, d.line), (path, 2))
        self.assertIn("cannot read include file 'nope.h'", d.message)
        r = self.run_pre("nop\n#include gone.h\n")
        self.assertEqual((r.diagnostics[0].file, r.diagnostics[0].line), (None, 2))

    def test_same_header_twice_is_fine(self):
        self.write('a.h', "#define X 1\n")
        r = self.run_pre("#include a.h\n#include a.h\n")
        self.assertEqual(r.diagnostics, [])


class TestDefines(PreCase):
    def test_effective_line_and_lookup(self):
        r = self.run_pre("nop\n#define A 1\nnop\n#define A 2 ; c\nnop\n")
        self.assertEqual(r.defines.lookup('A', 2), None)
        self.assertEqual(r.defines.lookup('A', 3).value, '1')
        self.assertEqual(r.defines.lookup('A', 4).value, '1')
        self.assertEqual(r.defines.lookup('A', 5).value, '2')
        self.assertEqual(self.messages(r, 'warning'), ["'A' redefined: '2' replaces '1'"])
        self.assertFalse(r.errors)

    def test_same_value_redefinition_is_silent(self):
        r = self.run_pre("#define A 1\n#define A 1\n")
        self.assertEqual(r.diagnostics, [])

    def test_char_value_keeps_semicolon(self):
        r = self.run_pre("#define S ';' ; semi\n")
        self.assertEqual(r.defines.lookup('S', 2).value, "';'")

    def test_malformed_define(self):
        for text in ("#define\n", "#define NAME\n", "#define 1x 2\n", "#define A ; only comment\n"):
            r = self.run_pre(text)
            self.assertEqual(self.messages(r), ['malformed #define (expected: #define NAME value)'], text)

    def test_register_and_pair_names_rejected(self):
        for name in ('ci', 'a', 'csci', 'af'):
            r = self.run_pre("#define {0} 0x01\n".format(name))
            self.assertEqual(self.messages(r), ["'{0}' is a register name and cannot be #defined".format(name)])
            self.assertEqual(r.diagnostics[0].column, 9)

    def test_condition_names_are_not_reserved(self):
        r = self.run_pre("#define z 1\n")
        self.assertEqual(r.diagnostics, [])

    def test_other_hash_words_are_not_directives(self):
        r = self.run_pre("#foo bar\n#defined x\n")
        self.assertEqual(r.diagnostics, [])
        self.assertEqual(r.text, "#foo bar\n#defined x\n")


class TestLinks(PreCase):
    def test_link_recorded_in_order_without_duplicates(self):
        self.write('a.h', "#link beta\n#link alpha\n")
        r = self.run_pre("#link alpha\n#include a.h\n#link gamma ; c\n")
        self.assertEqual(r.link_names, ['alpha', 'beta', 'gamma'])
        context = self.assemble("#link alpha\n#include a.h\nnop\n")
        self.assertEqual(context.link_names, ['alpha', 'beta'])

    def test_malformed_link(self):
        for text in ("#link\n", "#link a b\n", "#link 1a\n"):
            r = self.run_pre(text)
            self.assertEqual(self.messages(r), ['malformed #link (expected: #link NAME)'], text)

    def test_malformed_include(self):
        r = self.run_pre("#include\n#include a b\n")
        self.assertEqual(self.messages(r), ['malformed #include (expected: #include NAME)'] * 2)


class TestAssemble(PreCase):
    PLAIN = "start: nop\n.def k, 0x0010\nmov a, 0x01\nend: cal :start\n"
    WITH = "#define X 1\n#link foo\n  #include a.h\nstart: nop\n.def k, 0x0010\nmov a, 0x01\nend: cal :start\n"

    def test_directives_do_not_change_bytes_or_map(self):
        self.write('a.h', "#define Y 2\nbyte f(byte x);\n")
        plain = self.assemble(self.PLAIN)
        with_dir = self.assemble(self.WITH)
        self.assertEqual(plain.bytes, with_dir.bytes)
        self.assertEqual(format_map('p', plain), format_map('p', with_dir))

    def test_listing_rows_of_directives_have_no_address(self):
        self.write('a.h', "#define Y 2\n")
        listing = format_listing(self.WITH, self.assemble(self.WITH)).split('\n')
        for row in listing[:3]:
            self.assertEqual(row[:4], '    ')
        self.assertIn('#include a.h', listing[2])
        self.assertTrue(listing[3].startswith('0000'))

    def test_later_diagnostics_keep_line_numbers(self):
        text = "#define X 1\n#link foo\nnop\nmov a, 0x100\n"
        with self.assertRaises(AssemblerError) as ctx:
            self.assemble(text)
        self.assertEqual(ctx.exception.diagnostics[0].line, 4)

    def test_warning_kept_on_context_and_error_list(self):
        text = "#define X 1\n#define X 2\nnop\n"
        context = self.assemble(text)
        self.assertEqual([d.severity for d in context.warnings], ['warning'])
        with self.assertRaises(AssemblerError) as ctx:
            self.assemble(text + "jmp :nowhere\n")
        self.assertEqual([d.severity for d in ctx.exception.diagnostics], ['warning', 'error'])

    def test_header_error_block_names_header(self):
        path = self.write('a.h', "#define Y 2\nword x\n")
        text = "#include a.h\nnop\n"
        with self.assertRaises(AssemblerError) as ctx:
            self.assemble(text)
        block = format_diagnostics(ctx.exception.diagnostics, text, 'prog.basm').splitlines()
        self.assertEqual(block[0].split(': ')[0], path + ':2:1')
        self.assertEqual(block[1], 'word x')

    def test_compile_without_defines_still_works(self):
        import bc81asmc_grammar
        with contextlib.redirect_stdout(io.StringIO()):
            context = bc81asmc.compile(bc81asmc_grammar.program.parse("nop\n"), False)
        self.assertEqual(bytes(context.bytes), b'\x00')
        self.assertEqual(context.link_names, [])
        self.assertIsNone(context.define_table)


if __name__ == '__main__':
    unittest.main()
