"""Single-source guard: the ISA numbers live only in src/bc8183_isa.py (plan 5, AC 1, section 2.4).

The four consumers (CPU, emulator, assembler AST, assembler grammar) are parsed with Python's
`ast`, never with a regex on text. The test fails when any of them defines an ISA constant
(opcode, register number, sub-op, mode bit, condition code, ALU op, stack tag, KIL byte) as an
integer literal. Precisely, it reports

  * an assignment at module level, or directly in the body of any class, whose value is built
    from integer literals only (`X = 0x10`, `X = -1`, `X = (1, 2)`, `X = 1 << 4`);
  * an integer literal used as a dict key (decode and ALU tables must be keyed by ISA names);
  * a set or tuple/list literal assigned at those places, covered by the first rule.

It does not look inside function bodies: bit masks of the nibble arithmetic (`& 0xf`, `>> 4`)
and data widths (`0xff`, `0xffff`) are not ISA values and stay legal there.

Allowed (ALLOWED_LITERALS, with the reason): `FlagsRegister.B0..B7` are bit positions of the
flags byte, not ISA values (D5); `MEMORY_SIZE`, `EXIT_*` are emulator settings, `LabelName`/`SourceName` `line` and
`col` are source positions, `Literal.value` is a parse default.
"""
import ast
import os
import unittest

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARDED_FILES = (
    'bc64/bc8183_cpu.py',
    'bc64.py',
    'bc81asmc/bc81asmc_ast.py',
    'bc81asmc/bc81asmc_grammar.py',
)

# (class name or None for module level, assigned name)
ALLOWED_LITERALS = {(None, 'MEMORY_SIZE'), (None, 'EXIT_OK'), (None, 'EXIT_LIMIT'),
                    ('LabelName', 'line'), ('LabelName', 'col'),
                    ('SourceName', 'line'), ('SourceName', 'col'), ('Literal', 'value')} | \
                   {('FlagsRegister', 'B%d' % bit) for bit in range(8)}


def is_int_literal_expr(node):
    """True for an expression made only of int literals and arithmetic on them."""
    if isinstance(node, ast.Constant):
        return type(node.value) is int
    if isinstance(node, ast.UnaryOp):
        return is_int_literal_expr(node.operand)
    if isinstance(node, ast.BinOp):
        return is_int_literal_expr(node.left) and is_int_literal_expr(node.right)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return bool(node.elts) and all(is_int_literal_expr(e) for e in node.elts)
    return False


def assigned_names(stmt):
    if isinstance(stmt, ast.Assign):
        targets = stmt.targets
    elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        targets = [stmt.target]
    else:
        return []
    return [t.id for t in targets if isinstance(t, ast.Name)]


def find_violations(source, filename='<source>'):
    """Return 'file:line: text' for every ISA-looking integer literal definition."""
    tree = ast.parse(source, filename)
    found = []

    def scan_body(body, owner):
        for stmt in body:
            value = getattr(stmt, 'value', None)
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and value is not None \
                    and is_int_literal_expr(value):
                for name in assigned_names(stmt):
                    if (owner, name) not in ALLOWED_LITERALS:
                        found.append('%s:%d: %s = <int literal>%s'
                                     % (filename, stmt.lineno, name,
                                        '' if owner is None else ' in class ' + owner))
            elif isinstance(stmt, ast.ClassDef):
                scan_body(stmt.body, stmt.name)

    scan_body(tree.body, None)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if key is not None and is_int_literal_expr(key):
                    found.append('%s:%d: int literal as dict key' % (filename, key.lineno))
    return found


class SingleSourceGuardTests(unittest.TestCase):
    def test_no_isa_integer_literals_in_the_consumers(self):
        for rel in GUARDED_FILES:
            with self.subTest(rel):
                with open(os.path.join(SRC_DIR, rel), encoding='utf-8') as f:
                    source = f.read()
                self.assertEqual(find_violations(source, rel), [])

    def test_the_guard_flags_class_and_module_level_literals(self):
        source = 'class Bc8183:\n    A = 0x1\n    B = isa.REG_A\n\nX = -1\nOK = isa.X\n'
        self.assertEqual(len(find_violations(source)), 2)

    def test_the_guard_flags_integer_dict_keys(self):
        source = 'def f():\n    return {0x10: 1, isa.OP_NOP: 2, "k": 3}\n'
        self.assertEqual(len(find_violations(source)), 1)

    def test_the_guard_allows_masks_in_functions_and_the_flag_bits(self):
        source = ('class FlagsRegister:\n    B0 = 0x0\n    B7 = 0x7\n\n'
                  'def f(x):\n    y = 0xf\n    return (x >> 4) & 0xf\n')
        self.assertEqual(find_violations(source), [])


if __name__ == '__main__':
    unittest.main()
