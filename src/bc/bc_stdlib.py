"""Loader of the assembly runtime of the compiler, `runtime.basm` (next to this module).

runtime.basm is the single source of the runtime routines: a preamble (header comment, `.extern`,
`.global`), the always-emitted entry section (`.sect runtime_entry`: banner comment + 8-byte head) and
one `.sect NAME` per routine or data label. Everything before the first `.sect` is never emitted. Each
section after the entry section becomes a `Fragment`; its `deps` are the other fragments whose labels
its text references (derived here, they are the section's fixups in RUNTIME.O). The compiler emits only
the fragments referenced by the kept code plus the closure of their deps (Context.add_stdlib), in file
order. Always emitted besides: sys_heaphead data, sys_stackhead (last byte of the image), sys_codeend,
which the per-program `runtime_tail` template and add_stdlib generate.
"""
import os
import pathlib
from dataclasses import dataclass

from bc_labels import asm_labels

RUNTIME_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runtime.basm')
ENTRY_SECTION = 'runtime_entry'


class RuntimeSourceError(Exception):
    pass


@dataclass(frozen=True)
class Fragment:
    name: str
    text: str
    deps: tuple = ()


def parse_runtime(source, name='<runtime>'):
    """Parse runtime.basm text (or, when `source` is a path-like object, that file read with universal
    newlines) into (preamble, entry text, [Fragment]). Raises RuntimeSourceError on a malformed source."""
    if isinstance(source, os.PathLike):
        name = os.fspath(source)
        with open(source, 'r', encoding='utf-8', newline=None) as f:
            source = f.read()
    sections = []
    preamble = []
    for number, line in enumerate(source.splitlines(), 1):
        if line.startswith('.sect'):
            parts = line.split()
            if parts[0] != '.sect' or len(parts) != 2:
                raise RuntimeSourceError('{0}:{1}: expected ".sect NAME", got {2!r}'.format(name, number, line))
            if any(existing == parts[1] for existing, _ in sections):
                raise RuntimeSourceError('{0}:{1}: duplicate section {2}'.format(name, number, parts[1]))
            sections.append((parts[1], []))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    if not sections:
        raise RuntimeSourceError('{0}: no ".sect" line, nothing to load'.format(name))
    entry_name, entry_lines = sections[0]
    if entry_name != ENTRY_SECTION:
        raise RuntimeSourceError('{0}: the first section must be {1}, not {2}'.format(name, ENTRY_SECTION, entry_name))
    texts = [(section, ''.join(line + '\n' for line in lines)) for section, lines in sections[1:]]
    owner = {}
    for section, text in texts:
        for label in asm_labels(text)[0]:
            owner.setdefault(label, section)
    fragments = []
    for section, text in texts:
        deps = []
        for label in sorted(asm_labels(text)[1]):
            dep = owner.get(label)
            if dep is not None and dep != section and dep not in deps:
                deps.append(dep)
        fragments.append(Fragment(section, text, tuple(deps)))
    return '\n'.join(preamble) + '\n', ''.join(line + '\n' for line in entry_lines), fragments


_preamble, _entry, runtime_fragments = parse_runtime(pathlib.Path(RUNTIME_PATH))

# The entry section: its comment lines are the banner (emitted after a blank line), the rest the head.
_entry_lines = _entry.splitlines(True)
_banner_lines = [l for l in _entry_lines if l.lstrip().startswith(';')]
runtime_banner = '\n' + ''.join(_banner_lines)
# 8 bytes, no label, purpose undocumented - kept as the head of the runtime (assumption A-1 of #16)
runtime_head = ''.join(l for l in _entry_lines if not l.lstrip().startswith(';'))

# sys_heaphead data ({2}, {3} = heap segment address hi, lo), then sys_stackhead as the last byte
runtime_tail = """{1}:  .db 0x{2:02x}, 0x{3:02x}
{0}: nop
"""
