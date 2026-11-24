import unittest

from bc_ast import asm_labels
from bc_stdlib import runtime_fragments
from tests.bc_assert_tests import assemble
from tests.bc_codegen_tests import compile_source


def fragment_names(basm):
    '''Names of the runtime fragments present in the output (a fragment is present when it defines its label).'''
    defined = asm_labels(basm)[0]
    return {f.name for f in runtime_fragments if f.name in defined}


class RuntimeFragmentTests(unittest.TestCase):
    def test_fragment_names_are_unique(self):
        names = [f.name for f in runtime_fragments]
        self.assertEqual(len(names), len(set(names)))

    def test_declared_dependencies_equal_referenced_fragments(self):
        owner = {}
        for fragment in runtime_fragments:
            for label in asm_labels(fragment.text)[0]:
                owner.setdefault(label, fragment.name)
        for fragment in runtime_fragments:
            referenced = {owner[label] for label in asm_labels(fragment.text)[1]
                          if label in owner and owner[label] != fragment.name}
            self.assertEqual(set(fragment.deps), referenced, fragment.name)

    def test_dependencies_name_existing_fragments_defined_earlier_or_data(self):
        names = {f.name for f in runtime_fragments}
        for fragment in runtime_fragments:
            for dep in fragment.deps:
                self.assertIn(dep, names, fragment.name)

    def test_unused_routines_are_absent_and_used_ones_present(self):
        basm = compile_source('byte main() { asm "cal :printstr"; return 1; }')
        present = fragment_names(basm)
        self.assertIn('printstr', present)
        self.assertIn('os_metacall', present)
        self.assertNotIn('printhex16', present)
        self.assertNotIn('mfill', present)
        self.assertNotIn('mseek', present)
        self.assertNotIn('strncpy', present)

    def test_minimal_program_has_no_stack_routines(self):
        basm = compile_source('byte main() { return 1; }')
        for name in fragment_names(basm):
            self.assertFalse(name.startswith('stackvar') or name.startswith('stackhead'), name)
        self.assertNotIn('stackoffscalc:', basm)
        self.assertNotIn('stackoffsclc8:', basm)

    def test_dependency_closure_is_emitted(self):
        # a local variable is read/written through the stackvar* routines
        basm = compile_source('byte main() { byte x; x = 1; return x; }')
        present = fragment_names(basm)
        self.assertTrue(any(n.startswith('stackvar') for n in present))
        for fragment in runtime_fragments:
            if fragment.name in present:
                for dep in fragment.deps:
                    self.assertIn(dep, present, '{0} needs {1}'.format(fragment.name, dep))

    def test_stack_head_move_pulls_its_dependencies(self):
        basm = compile_source('byte main() { asm "cal :stackheadrll8"; return 1; }')
        present = fragment_names(basm)
        for name in ('stackheadrll8', 'stackoffsclc8', 'poke16', 'peek16'):
            self.assertIn(name, present)
        self.assertNotIn('stackheadroll', present)

    def test_mseek_keeps_its_data_and_dependencies(self):
        basm = compile_source('byte main() { asm "cal :mseek"; return 1; }')
        present = fragment_names(basm)
        for name in ('mseek', 'poke16', 'peek16', 'gteq16', 'os_metacall', 'sys_seektmp'):
            self.assertIn(name, present)
        self.assertIn('sys_seektmp:', basm)

    def test_data_labels_only_when_referenced(self):
        basm = compile_source('byte main() { return 1; }')
        self.assertNotIn('sys_stdprntf:', basm)
        self.assertNotIn('sys_seektmp:', basm)
        basm = compile_source('byte main() { asm ".mv dsdi, :sys_stdprntf"; return 1; }')
        self.assertIn('sys_stdprntf:', basm)
        self.assertNotIn('sys_seektmp:', basm)

    def test_always_kept_tail(self):
        basm = compile_source('byte main() { return 1; }')
        self.assertIn('COMPILER ASM STDLIB', basm)
        self.assertEqual(basm.count('mov a, 0xff'), 4)
        self.assertIn('sys_heaphead:', basm)
        self.assertLess(basm.index('sys_heaphead:'), basm.index('sys_stackhead:'))
        self.assertLess(basm.index('sys_stackhead:'), basm.index('sys_codeend:'))
        lines = [l for l in basm.splitlines() if l.strip()]
        self.assertTrue(lines[-1].startswith('sys_codeend:'))
        self.assertTrue(lines[-2].replace(' ', '').startswith('sys_stackhead:nop'))

    def test_no_blank_lines_in_output(self):
        for source in ('byte main() { return 1; }', 'byte main() { byte x; x = 1; return "a"; }'):
            basm = compile_source(source)
            body = basm.lstrip('\n').rstrip('\n')
            self.assertNotIn('\n\n', body)
            self.assertNotIn('\n \n', body)


class RuntimeAssemblyTests(unittest.TestCase):
    def test_outputs_assemble(self):
        sources = [
            'byte main() { return 1; }',
            'byte main() { byte x; x = 1; return x; }',
            'byte main() { asm "cal :mseek"; asm "cal :printstr"; return 1; }',
            'byte main() { asm "cal :stackheadroll"; asm ".mv dsdi, :sys_stdprntf"; return 1; }',
        ]
        for source in sources:
            code, output = assemble(compile_source(source))
            self.assertEqual(code, 0, output)


if __name__ == '__main__':
    unittest.main()
