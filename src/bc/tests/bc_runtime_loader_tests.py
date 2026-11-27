"""The runtime source `runtime.basm` (#116): the loader in bc_stdlib.py and the RUNTIME.O it builds.

Structure only: no test pins object bytes or record offsets (#188 changes them)."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from bc_labels import asm_labels
from bc_stdlib import ENTRY_SECTION, RUNTIME_PATH, RuntimeSourceError, parse_runtime, runtime_banner, \
    runtime_fragments, runtime_head

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSEMBLER = os.path.join(SRC_DIR, 'bc81asmc', 'bc81asmc.py')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
import bof  # noqa: E402

EXTERNS = ('sys_stackhead', 'sys_heaphead')
DATA_LABELS = ('sys_stdprntf', 'sys_seektmp')


def read_source_lines():
    with open(RUNTIME_PATH, 'r', encoding='utf-8', newline=None) as f:
        return f.read().splitlines()


def fragment(name):
    return next(f for f in runtime_fragments if f.name == name)


class LoaderTests(unittest.TestCase):
    def test_entry_section_is_first_and_holds_the_four_line_head(self):
        _, entry, _ = parse_runtime(pathlib.Path(RUNTIME_PATH))
        lines = entry.splitlines()
        self.assertTrue(lines[0].startswith(';'))
        self.assertEqual(len(lines), 5)
        self.assertEqual([l.strip() for l in lines[1:]], ['mov a, 0xff'] * 4)
        self.assertEqual(read_source_lines().index('.sect ' + ENTRY_SECTION),
                         min(i for i, l in enumerate(read_source_lines()) if l.startswith('.sect')))
        self.assertEqual(runtime_banner, '\n' + lines[0] + '\n')
        self.assertEqual(runtime_head.count('mov a, 0xff'), 4)

    def test_fragments_are_unique_and_in_file_order(self):
        names = [f.name for f in runtime_fragments]
        self.assertEqual(len(names), 39)
        self.assertEqual(len(set(names)), len(names))
        in_file = [l.split()[1] for l in read_source_lines() if l.startswith('.sect')]
        self.assertEqual(in_file, [ENTRY_SECTION] + names)

    def test_fragment_text_holds_no_directives_or_format_fields(self):
        for f in runtime_fragments:
            for token in ('.sect', '.global', '.extern', '{0}', '{1}'):
                self.assertNotIn(token, f.text, f.name)
            self.assertTrue(f.text.endswith('\n'), f.name)
            self.assertNotIn('\n\n', f.text, f.name)

    def test_known_dependencies(self):
        self.assertEqual(set(fragment('stackheadrll8').deps), {'poke16', 'stackoffsclc8'})
        self.assertEqual(set(fragment('mseek').deps), {'poke16', 'peek16', 'gteq16', 'sys_seektmp'})
        self.assertEqual(set(fragment('fatal').deps), {'os_metacall'})
        self.assertEqual(fragment('os_metacall').deps, ())

    def test_duplicate_section_is_rejected(self):
        source = '.sect runtime_entry\n nop\n.sect a\na: nop\n.sect a\n'
        with self.assertRaisesRegex(RuntimeSourceError, 'duplicate section a'):
            parse_runtime(source, 'bad.basm')

    def test_source_without_sections_is_rejected(self):
        with self.assertRaisesRegex(RuntimeSourceError, 'bad.basm'):
            parse_runtime('.global a\n', 'bad.basm')

    def test_text_after_section_name_is_rejected(self):
        with self.assertRaisesRegex(RuntimeSourceError, 'expected ".sect NAME"'):
            parse_runtime('.sect runtime_entry extra\n', 'bad.basm')

    def test_first_section_must_be_the_entry(self):
        with self.assertRaisesRegex(RuntimeSourceError, ENTRY_SECTION):
            parse_runtime('.sect a\na: nop\n', 'bad.basm')

    def test_parser_reads_a_path_with_any_newlines(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'x.basm')
            with open(path, 'wb') as f:
                f.write(b'.sect runtime_entry\r\n; banner\r\n.sect a\r\na: nop\r\n')
            _, entry, fragments = parse_runtime(pathlib.Path(path))
            self.assertEqual(entry, '; banner\n')
            self.assertEqual([(f.name, f.text) for f in fragments], [('a', 'a: nop\n')])


class PreambleTests(unittest.TestCase):
    def setUp(self):
        self.lines = read_source_lines()
        self.first_sect = min(i for i, l in enumerate(self.lines) if l.startswith('.sect'))
        self.preamble = self.lines[:self.first_sect]

    def test_every_fragment_label_has_a_global_except_the_metacall_def(self):
        globals_ = {l.split()[1] for l in self.preamble if l.startswith('.global')}
        for f in runtime_fragments:
            if f.name == 'os_metacall':
                self.assertNotIn(f.name, globals_)
            else:
                self.assertIn(f.name, asm_labels(f.text)[0], f.name)
                self.assertIn(f.name, globals_, f.name)
        self.assertEqual(len(globals_), 38)

    def test_internal_labels_are_not_global(self):
        globals_ = {l.split()[1] for l in self.preamble if l.startswith('.global')}
        internal = set()
        for f in runtime_fragments:
            internal |= asm_labels(f.text)[0] - {f.name}
        self.assertTrue(internal)
        self.assertEqual(internal & globals_, set())

    def test_both_externs_are_declared_before_the_first_section(self):
        externs = {l.split()[1] for l in self.preamble if l.startswith('.extern')}
        self.assertEqual(externs, set(EXTERNS))

    def test_no_blank_lines(self):
        self.assertTrue(all(l.strip() for l in self.lines))


class RuntimeObjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        with open(RUNTIME_PATH, 'r', encoding='utf-8', newline=None) as f:
            text = f.read()
        source = os.path.join(cls._tmp.name, 'runtime.basm')
        with open(source, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        result = subprocess.run([sys.executable, ASSEMBLER, '--obj', 'runtime.basm'], cwd=cls._tmp.name,
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError('bc81asmc --obj failed: ' + result.stdout + result.stderr)
        with open(os.path.join(cls._tmp.name, 'runtime.o'), 'rb') as f:
            cls.records = bof.read_records(f.read())

    def sections(self):
        '''[(name, [records of the section])] in file order.'''
        result = []
        for r in self.records:
            if r.tag == bof.TAG_SECTSTAT:
                result.append((r.fields['name'], []))
            elif result:
                result[-1][1].append(r)
        return result

    def test_module_and_sections_follow_the_source(self):
        self.assertEqual(self.records[0].fields['module'], 'RUNTIME')
        expected = [ENTRY_SECTION] + [f.name for f in runtime_fragments]
        self.assertEqual([r.fields['name'] for r in self.records if r.tag == bof.TAG_SECTSTAT], expected)
        self.assertEqual(sum(1 for r in self.records if r.tag == bof.TAG_SECTABS), 0)

    def test_every_routine_is_global_in_its_own_section(self):
        for name, records in self.sections():
            globals_ = [r.fields['name'] for r in records if r.tag == bof.TAG_GLOBL]
            if name in ('os_metacall', ENTRY_SECTION):
                self.assertEqual(globals_, [], name)
            else:
                self.assertEqual(globals_, [name], name)

    def test_externs_are_declared(self):
        externs = {r.fields['name'] for r in self.records if r.tag == bof.TAG_EXTRN}
        self.assertTrue(set(EXTERNS) <= externs)

    def test_section_fixups_reach_exactly_the_derived_dependencies(self):
        sections = self.sections()
        symbols = []
        global_in = {}
        label_in = {}
        for name, records in sections:
            for r in records:
                if r.tag == bof.TAG_GLOBL:
                    global_in[r.fields['name']] = name
                elif r.tag == bof.TAG_LABEL:
                    label_in[r.fields['n']] = name
        for r in self.records:
            if r.tag == bof.TAG_EXTRN:
                symbols.append(r.fields['name'])

        def target_section(target):
            if target & bof.LOCAL_LABEL_FLAG:
                return label_in[target & ~bof.LOCAL_LABEL_FLAG & 0xFFFF]
            return global_in.get(symbols[target])   # None: an extern defined by the program, not a section

        reached = {}
        for name, records in sections:
            reached[name] = set()
            code = b''
            for r in records:
                targets = []
                if r.tag == bof.TAG_CODE:
                    code = r.fields['bytes']
                elif r.tag in bof.FIX_OFFSET_ONLY:
                    targets = [code[o] << 8 | code[o + 1] for o in r.fields['offsets']]
                elif r.tag in bof.FIX_SPAN:
                    targets = [t for _, t in r.fields['entries']]
                for t in targets:
                    found = target_section(t)
                    if found is not None and found != name:
                        reached[name].add(found)
        has_code = {name: any(r.tag == bof.TAG_CODE for r in records) for name, records in sections}
        for f in runtime_fragments:
            # a section that only holds a `.def` (os_metacall) has no code: the assembler folds the constant
            # into the caller, so the reference leaves no fixup
            expected = {d for d in f.deps if has_code[d]}
            self.assertEqual(reached[f.name], expected, f.name)
        self.assertEqual(reached[ENTRY_SECTION], set())
        self.assertTrue(any(reached[f.name] for f in runtime_fragments))


if __name__ == '__main__':
    unittest.main()
