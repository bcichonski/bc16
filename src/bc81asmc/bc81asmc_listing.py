'''Listing (.lst) and symbol map (.map) text for bc81asmc.

Pure functions: no printing, no file I/O. They read what compile() leaves on the CodeContext
(`line_records`, `label_addresses`, `defs`, `bytes`, `startaddr`), after pass 2, so the listing
shows the final, patched bytes.

Map format (one symbol per line, sorted by value, then name):
    ; bc81asmc map <source file name>
    ; org 0xHHHH end 0xHHHH
    0xHHHH <label|def> <name>
Listing row: `HHHH  HH HH HH HH  <source line>` (address and bytes columns blank when the line has none).
'''
from dataclasses import dataclass
from typing import List, NamedTuple

BYTES_PER_ROW = 4
BYTES_WIDTH = BYTES_PER_ROW * 3 - 1
KIND_LABEL = 'label'
KIND_DEF = 'def'


@dataclass(frozen=True)
class LineRecord:
    '''Where one source line landed: its 1-based number and the address span [start, end) it emitted.'''
    lineno: int
    start: int
    end: int
    has_label: bool = False
    is_org: bool = False


class Symbol(NamedTuple):
    name: str
    value: int
    kind: str


class SymbolMap(NamedTuple):
    source: str
    org: int
    end: int
    symbols: List[Symbol]

    def value_of(self, name):
        for symbol in self.symbols:
            if symbol.name == name:
                return symbol.value
        raise KeyError(name)


def symbols_of(context):
    '''Labels and .def constants of a compiled context, sorted by value, then name.'''
    symbols = [Symbol(name, value, KIND_LABEL) for name, value in context.label_addresses.items()]
    symbols += [Symbol(name, value, KIND_DEF) for name, value in context.defs.items()]
    return sorted(symbols, key=lambda s: (s.value, s.name))


def format_map(source_name, context):
    org = context.startaddr
    end = org + len(context.bytes)
    lines = ['; bc81asmc map {0}'.format(source_name),
             '; org 0x{0:04x} end 0x{1:04x}'.format(org, end)]
    lines += ['0x{0:04x} {1} {2}'.format(s.value, s.kind, s.name) for s in symbols_of(context)]
    return '\n'.join(lines) + '\n'


def read_map(text):
    '''Parses format_map() text into a SymbolMap (source, org, end, symbols).'''
    source = None
    org = end = None
    symbols = []
    for number, raw in enumerate(text.splitlines(), 1):
        row = raw.strip()
        if not row:
            continue
        if row.startswith(';'):
            parts = row[1:].split()
            if parts[:2] == ['bc81asmc', 'map']:
                source = ' '.join(parts[2:])
            elif len(parts) == 4 and parts[0] == 'org' and parts[2] == 'end':
                org, end = int(parts[1], 16), int(parts[3], 16)
            continue
        parts = row.split()
        if len(parts) != 3 or parts[1] not in (KIND_LABEL, KIND_DEF):
            raise ValueError('bad map line {0}: {1!r}'.format(number, raw))
        symbols.append(Symbol(parts[2], int(parts[0], 16), parts[1]))
    if source is None or org is None or end is None:
        raise ValueError('map header missing')
    return SymbolMap(source, org, end, symbols)


def _row(address, data, source):
    addr = '{0:04x}'.format(address) if address is not None else ' ' * 4
    hexes = ' '.join('{0:02x}'.format(b) for b in data).ljust(BYTES_WIDTH)
    return '{0}  {1}  {2}'.format(addr, hexes, source).rstrip()


def format_listing(source_text, context):
    '''One row per source line, in order; a .db longer than 4 bytes continues on address+bytes rows.'''
    records = {r.lineno: r for r in context.line_records}
    org = context.startaddr
    source_lines = source_text.split('\n')
    if source_lines and source_lines[-1] == '':
        source_lines.pop()
    rows = []
    for lineno, text in enumerate(source_lines, 1):
        text = text.rstrip()
        record = records.get(lineno)
        if record is None:
            rows.append(_row(None, b'', text))
            continue
        data = bytes(context.bytes[record.start - org:record.end - org]) if record.end > record.start else b''
        if not (data or record.has_label or record.is_org):
            rows.append(_row(None, b'', text))
            continue
        rows.append(_row(record.start, data[:BYTES_PER_ROW], text))
        for offset in range(BYTES_PER_ROW, len(data), BYTES_PER_ROW):
            rows.append(_row(record.start + offset, data[offset:offset + BYTES_PER_ROW], ''))
    return '\n'.join(rows) + '\n' if rows else ''
