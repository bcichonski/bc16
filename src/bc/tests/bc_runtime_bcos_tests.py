"""Guard for the runtime <-> bcOS contract (#29).

The runtime fragments in bc_stdlib.py hard-code two things about the ROM:
  * `.def NAME, ADDR` - NAME must be a label of bcos.basm and ADDR its address in the assembled ROM;
  * `mov a|ci, 0xNN; psh ..; pop f; cal :os_metacall` - NN must select the expected os_metatab entry.
Both are derived here from the real bcos.basm at run time (nothing is hard-coded), so a bcOS change
that moves a label or reorders os_metatab fails this test instead of silently breaking programs.
"""
import os
import re
import unittest

from bc_stdlib import runtime_fragments
from tests.bc_assert_tests import assemble

BCOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'bc81asmc', 'bcOS', 'bcos.basm')

# fragment name -> os_metatab entries its os_metacall calls select, in order (default: [fragment name])
EXPECTED_ENTRIES = {'mem_cpy': ['setvarparam16', 'mem_xcpy']}

DEF_RE = re.compile(r'^\s*\.def\s+(\w+)\s*,\s*(0x[0-9a-fA-F]+|\d+)', re.MULTILINE)
INDEX_RE = re.compile(r'^\s*(?:\w+:)?\s*mov\s+(?:a|ci)\s*,\s*(0x[0-9a-fA-F]+|\d+)\s*(?:;.*)?$')
ASSERT_FAILED_RE = re.compile(r'assertion failed: :(\w+) = (0x[0-9a-fA-F]+) \((0x[0-9a-fA-F]+) = (0x[0-9a-fA-F]+)\)')


def read_bcos():
    with open(BCOS, encoding='utf-8', newline='') as f:
        return f.read().replace('\r\n', '\n')


def read_metatab(bcos):
    '''os_metatab entries in table order ('0x00' fillers keep their position).'''
    entries = []
    inside = False
    for line in bcos.split('\n'):
        if line.startswith('os_metatab:'):
            inside = True
        elif line.startswith('os_vartab:'):
            break
        if not inside:
            continue
        code = line.split(';')[0]
        if '.db' not in code:
            continue
        for item in code.split('.db', 1)[1].split(','):
            item = item.strip()
            if item:
                entries.append(item[1:] if item.startswith(':') else item)
    return entries


def check_defs(bcos, fragments):
    '''Errors for every `.def NAME, ADDR` of the fragments that is not the assembled address of bcOS label NAME.'''
    defs = [(f_name, name, int(addr, 0)) for f_name, text in fragments for name, addr in DEF_RE.findall(text)]
    asserts = ''.join('.assert :{0} = 0x{1:04x}\n'.format(name, addr) for _, name, addr in defs)
    code, out = assemble(bcos.rstrip('\n') + '\n' + asserts)
    failed = {m.group(1): m for m in ASSERT_FAILED_RE.finditer(out)}
    errors = []
    for f_name, name, addr in defs:
        if name in failed:
            errors.append("fragment '{0}': .def {1} found 0x{2:04x}, expected 0x{3:04x} (assembled address of bcos label)"
                          .format(f_name, name, addr, int(failed[name].group(3), 16)))
        elif "undefined label ':{0}'".format(name) in out:
            errors.append("fragment '{0}': .def {1} found 0x{2:04x}, expected a label of that name in bcos.basm"
                          .format(f_name, name, addr))
    if not errors and code != 0:
        errors.append('bcos.basm with the .def assertions did not assemble: ' + out)
    return errors, len(defs)


def metacall_indexes(text):
    '''Index loaded before each `cal :os_metacall` of the text (None when no `mov a|ci, N` is found).'''
    lines = text.split('\n')
    found = []
    for i, line in enumerate(lines):
        if not re.match(r'^\s*(?:\w+:)?\s*cal\s+:os_metacall\b', line):
            continue
        index = None
        for prev in reversed(lines[:i]):
            m = INDEX_RE.match(prev)
            if m:
                index = int(m.group(1), 0)
                break
        found.append(index)
    return found


def check_metacalls(metatab, fragments):
    '''Errors for every metacall whose index does not select the expected entry; also the number of metacalls matched.'''
    errors = []
    matched = 0
    callers = set()
    for f_name, text in fragments:
        if f_name == 'os_metacall':
            continue
        indexes = metacall_indexes(text)
        if not indexes:
            continue
        callers.add(f_name)
        expected = EXPECTED_ENTRIES.get(f_name, [f_name])
        if len(indexes) != len(expected):
            errors.append("fragment '{0}': found {1} os_metacall(s), expected {2}".format(f_name, len(indexes), len(expected)))
            continue
        for index, want in zip(indexes, expected):
            actual = metatab[index] if index is not None and index < len(metatab) else None
            if actual != want:
                errors.append("fragment '{0}': index {1} selects os_metatab entry {2}, expected {3}".format(
                    f_name, 'none' if index is None else '0x{0:02x}'.format(index), actual, want))
            else:
                matched += 1
    return errors, matched, callers


def runtime_texts():
    return [(f.name, f.text) for f in runtime_fragments]


class RuntimeBcosContractTests(unittest.TestCase):
    def test_defs_match_assembled_bcos_labels(self):
        errors, count = check_defs(read_bcos(), runtime_texts())
        self.assertEqual(errors, [])
        self.assertGreater(count, 0)

    def test_metacall_indexes_select_expected_entries(self):
        metatab = read_metatab(read_bcos())
        errors, matched, callers = check_metacalls(metatab, runtime_texts())
        self.assertEqual(errors, [])
        self.assertTrue(callers)
        self.assertEqual(matched, sum(len(EXPECTED_ENTRIES.get(n, [n])) for n in callers))

    def test_metatab_is_read_in_table_order(self):
        metatab = read_metatab(read_bcos())
        self.assertEqual(metatab[0:3], ['print_newline', 'print_space', 'printstr'])
        self.assertEqual(metatab[0x14], 'fatal')
        self.assertEqual(metatab[0x32], 'mem_xcpy')


class CheckerRejectsDoctoredFragmentTests(unittest.TestCase):
    def test_stale_def_is_reported(self):
        errors, _ = check_defs(read_bcos(), [('doctored', '.def var_promptbuf, 0x0bcf\n')])
        self.assertEqual(len(errors), 1)
        self.assertIn("'doctored'", errors[0])
        self.assertIn('var_promptbuf', errors[0])
        self.assertIn('0x0bcf', errors[0])

    def test_def_of_unknown_label_is_reported(self):
        errors, _ = check_defs(read_bcos(), [('doctored', '.def no_such_label, 0x0123\n')])
        self.assertEqual(len(errors), 1)
        self.assertIn('no_such_label', errors[0])

    def test_wrong_metacall_index_is_reported(self):
        text = next(t for n, t in runtime_texts() if n == 'printstr').replace('mov a, 0x02', 'mov a, 0x03')
        self.assertNotEqual(text, next(t for n, t in runtime_texts() if n == 'printstr'))
        errors, matched, _ = check_metacalls(read_metatab(read_bcos()), [('printstr', text)])
        self.assertEqual(matched, 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("'printstr'", errors[0])
        self.assertIn('0x03', errors[0])
        self.assertIn('printhex4', errors[0])
        self.assertIn('printstr', errors[0].split('expected')[1])


if __name__ == '__main__':
    unittest.main()
