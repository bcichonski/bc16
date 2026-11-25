"""BOF v1, the bc16 object file format: writer, reader and dump formatter.

The layout is frozen by design decision G15 (docs/specs/memory/design-decisions.md) and
described in docs/analysis/07-self-hosted-compiler.md ("Object file format"). A file is a
stream of records `tag(1) length(1) content[length]`; 16-bit values are big-endian.

`BofWriter` follows the G15 writing rules, so the same calls always give the same bytes:
the open CODE record is flushed when full, before every non-CODE record (D7 of story #115
adds NEED, ADDR and ABS to G15's list) and before a unit of bytes that would not fit whole;
its fix records follow it directly in tag order with offsets ascending.
`read_records` parses bytes back and `dump` formats them as text. Both raise `BofError`,
which carries the byte offset of the problem.

The module is plain Python with no imports from the tools, shared by the assembler
(src/bc81asmc/), blink.py and bc.
"""

VERSION = 0x01
MAX_CONTENT = 255

TAG_HEADER = 0xB0
TAG_EXTRN = 0xEE
TAG_NEED = 0xDE
TAG_ADDR = 0xAD
TAG_SECTSTAT = 0x55
TAG_SECTABS = 0x5A
TAG_GLOBL = 0x91
TAG_CODE = 0xC0
TAG_LABEL = 0x1A
TAG_ABS = 0xAB
TAG_ABS16 = 0xF1
TAG_REL15 = 0xF2
TAG_HI8 = 0xF8
TAG_LO8 = 0xF9
TAG_REL7 = 0xFA
TAG_HILO = 0xFB
TAG_END = 0xED

# Fix kinds are their tags. Written in this order after their CODE record.
FIX_ABS16 = TAG_ABS16
FIX_REL15 = TAG_REL15
FIX_HI8 = TAG_HI8
FIX_LO8 = TAG_LO8
FIX_REL7 = TAG_REL7
FIX_HILO = TAG_HILO
FIX_ORDER = (FIX_ABS16, FIX_REL15, FIX_HI8, FIX_LO8, FIX_REL7, FIX_HILO)
# Kinds whose placeholder holds the target: an entry is only the offset.
FIX_OFFSET_ONLY = (FIX_ABS16, FIX_REL15)
# Bytes a fix patches, counted from its offset: a placeholder is never split across records.
FIX_SPAN = {FIX_ABS16: 2, FIX_REL15: 2, FIX_HI8: 1, FIX_LO8: 1, FIX_REL7: 1, FIX_HILO: 3}

ADDR_CODE = 0
ADDR_HEAP = 1
ADDR_CODELIMIT = 2
ADDR_KINDS = {ADDR_CODE: '#code', ADDR_HEAP: '#heap', ADDR_CODELIMIT: '#codelimit'}

LOCAL_LABEL_FLAG = 0x8000

RECORD_NAMES = {
    TAG_HEADER: 'HEADER', TAG_EXTRN: 'EXTRN', TAG_NEED: 'NEED', TAG_ADDR: 'ADDR',
    TAG_SECTSTAT: 'SECTSTAT', TAG_SECTABS: 'SECTABS', TAG_GLOBL: 'GLOBL', TAG_CODE: 'CODE',
    TAG_LABEL: 'LABEL', TAG_ABS: 'ABS', TAG_ABS16: 'ABS16', TAG_REL15: 'REL15',
    TAG_HI8: 'HI8', TAG_LO8: 'LO8', TAG_REL7: 'REL7', TAG_HILO: 'HILO', TAG_END: 'END',
}


class BofError(ValueError):
    """A BOF file or writer call is invalid. `offset` is the byte offset in the file for a
    reader error and None for a writer error."""

    def __init__(self, message, offset=None):
        super().__init__(message if offset is None else 'offset %d: %s' % (offset, message))
        self.message = message
        self.offset = offset


def local_label_target(n):
    """The fix target of local label n."""
    if not 0 <= n < LOCAL_LABEL_FLAG:
        raise BofError('local label number out of range: %d' % n)
    return LOCAL_LABEL_FLAG | n


def _name_bytes(name, max_len, what):
    try:
        raw = name.encode('ascii')
    except UnicodeEncodeError:
        raise BofError('%s %r is not ASCII' % (what, name))
    if not raw:
        raise BofError('%s is empty' % what)
    if len(raw) > max_len:
        raise BofError('%s %r is too long (%d bytes, at most %d)' % (what, name, len(raw), max_len))
    return raw


def _u16(value, what):
    if not 0 <= value <= 0xFFFF:
        raise BofError('%s out of 16-bit range: %d' % (what, value))
    return bytes(((value >> 8) & 0xFF, value & 0xFF))


class BofWriter:
    """Builds one BOF v1 module in memory. Call `getvalue()` after `end()`."""

    def __init__(self, module):
        self._out = bytearray()
        self._code = bytearray()
        self._fixes = []            # (kind, offset in the open CODE record, target)
        self._symbols = {}          # name -> symbol number
        self._section_offset = 0    # offset of the next byte in the current section
        self._ended = False
        self._record(TAG_HEADER, bytes((VERSION,)) + _name_bytes(module, MAX_CONTENT - 1, 'module name'))

    # -- low level -------------------------------------------------------------------
    def _record(self, tag, content=b''):
        if len(content) > MAX_CONTENT:
            raise BofError('record %02x content is %d bytes, at most %d' % (tag, len(content), MAX_CONTENT))
        self._out += bytes((tag, len(content))) + content

    def _check_open(self):
        if self._ended:
            raise BofError('the module is already ended')

    def _begin_record(self):
        """Common start of every non-CODE record: the open CODE record is written first."""
        self._check_open()
        self.flush()

    # -- state -----------------------------------------------------------------------
    @property
    def section_offset(self):
        """Offset in the current section of the next code byte (pending bytes included)."""
        return self._section_offset

    @property
    def pending(self):
        """Number of bytes in the open CODE record."""
        return len(self._code)

    @property
    def symbols(self):
        """Symbol name -> number, for the names declared so far."""
        return dict(self._symbols)

    # -- records ---------------------------------------------------------------------
    def extrn(self, name):
        """Number of symbol `name`; a name seen for the first time writes its EXTRN record
        (flushing the open CODE record first), so numbers follow first use."""
        self._check_open()
        k = self._symbols.get(name)
        if k is not None:
            return k
        raw = _name_bytes(name, MAX_CONTENT, 'symbol name')
        self.flush()
        k = len(self._symbols)
        if k >= LOCAL_LABEL_FLAG:
            raise BofError('too many symbols')
        self._symbols[name] = k
        self._record(TAG_EXTRN, raw)
        return k

    def need(self, module):
        self._begin_record()
        self._record(TAG_NEED, _name_bytes(module, MAX_CONTENT, 'module name'))

    def addr(self, kind, value):
        self._begin_record()
        if kind not in ADDR_KINDS:
            raise BofError('unknown ADDR kind %r' % (kind,))
        self._record(TAG_ADDR, bytes((kind,)) + _u16(value, 'ADDR value'))

    def sectstat(self, name):
        self._begin_record()
        self._record(TAG_SECTSTAT, _name_bytes(name, MAX_CONTENT, 'section name'))
        self._section_offset = 0

    def sectabs(self, address, name):
        self._begin_record()
        self._record(TAG_SECTABS, _u16(address, 'section address')
                     + _name_bytes(name, MAX_CONTENT - 2, 'section name'))
        self._section_offset = 0

    def globl(self, name):
        self._begin_record()
        self._record(TAG_GLOBL, _name_bytes(name, MAX_CONTENT, 'symbol name'))

    def label(self, n):
        self._begin_record()
        if not 0 <= n < LOCAL_LABEL_FLAG:
            raise BofError('local label number out of range: %d' % n)
        self._record(TAG_LABEL, _u16(n, 'label number'))

    def abs_symbol(self, value, name):
        self._begin_record()
        self._record(TAG_ABS, _u16(value, 'ABS value') + _name_bytes(name, MAX_CONTENT - 2, 'symbol name'))

    def end(self):
        self._begin_record()
        self._record(TAG_END)
        self._ended = True

    # -- code ------------------------------------------------------------------------
    def code(self, data, fixes=()):
        """Append a unit of bytes (usually one source line) with its fix entries.

        `fixes` is a sequence of `(kind, offset)` or `(kind, offset, target)`; the offset is
        relative to the start of `data`, and `target` is not needed for ABS16 and REL15
        (their placeholder holds it). The unit is kept whole in one CODE record when it
        fits (the open record is flushed first if it does not). A unit longer than 255
        bytes is split at 255-byte boundaries, with a split point moved back so that no
        fix's placeholder is cut in two."""
        self._check_open()
        data = bytes(data)
        entries = self._check_fixes(data, fixes)
        if not data:
            return
        if len(data) <= MAX_CONTENT:
            if len(self._code) + len(data) > MAX_CONTENT:
                self.flush()
            self._append(data, entries)
            return
        self.flush()
        pos = 0
        while len(data) - pos > MAX_CONTENT:
            cut = pos + MAX_CONTENT
            for kind, off, _ in entries:
                if off < cut < off + FIX_SPAN[kind]:
                    cut = off
            if cut <= pos:
                raise BofError('a fix at offset %d cannot be kept whole in a record' % pos)
            self._append(data[pos:cut], [(k, o - pos, t) for k, o, t in entries if pos <= o < cut])
            self.flush()
            pos = cut
        self._append(data[pos:], [(k, o - pos, t) for k, o, t in entries if o >= pos])

    @staticmethod
    def _check_fixes(data, fixes):
        entries = []
        for fix in fixes:
            kind, off = fix[0], fix[1]
            target = fix[2] if len(fix) > 2 else 0
            if kind not in FIX_SPAN:
                raise BofError('unknown fix kind %r' % (kind,))
            if not 0 <= off or off + FIX_SPAN[kind] > len(data):
                raise BofError('fix at offset %d does not fit the %d bytes' % (off, len(data)))
            if kind not in FIX_OFFSET_ONLY and not 0 <= target <= 0xFFFF:
                raise BofError('fix target out of 16-bit range: %d' % target)
            entries.append((kind, off, target))
        return entries

    def _append(self, data, entries):
        base = len(self._code)
        self._code += data
        self._section_offset += len(data)
        self._fixes.extend((k, base + o, t) for k, o, t in entries)

    def flush(self):
        """Write the open CODE record and its fix records, if there are any bytes."""
        if not self._code:
            return
        self._record(TAG_CODE, bytes(self._code))
        for kind in FIX_ORDER:
            items = sorted((o, t) for k, o, t in self._fixes if k == kind)
            if not items:
                continue
            if kind in FIX_OFFSET_ONLY:
                chunk = [bytes((o,)) for o, _ in items]
            else:
                chunk = [bytes((o,)) + _u16(t, 'fix target') for o, t in items]
            size = len(chunk[0])
            per_record = MAX_CONTENT // size
            for i in range(0, len(chunk), per_record):
                self._record(kind, b''.join(chunk[i:i + per_record]))
        self._code = bytearray()
        self._fixes = []

    def getvalue(self):
        if not self._ended:
            raise BofError('the module has no END record yet')
        return bytes(self._out)


# ---------------------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------------------
class Record:
    """One parsed record: file `offset`, `tag`, raw `content` and decoded `fields`.

    Fields by tag: HEADER `version`, `module`; EXTRN/NEED/SECTSTAT/GLOBL `name`; ADDR `kind`,
    `value`; SECTABS `address`, `name`; LABEL `n`; ABS `value`, `name`; CODE `bytes`;
    ABS16/REL15 `offsets`; HI8/LO8/REL7/HILO `entries` as (offset, target) pairs; END none."""

    def __init__(self, offset, tag, content, fields):
        self.offset = offset
        self.tag = tag
        self.content = content
        self.fields = fields

    @property
    def name(self):
        return RECORD_NAMES[self.tag]

    def __repr__(self):
        return 'Record(%d, %s, %r)' % (self.offset, self.name, self.fields)

    def __eq__(self, other):
        return (isinstance(other, Record)
                and (self.offset, self.tag, self.content) == (other.offset, other.tag, other.content))

    __hash__ = None


def _text(content, start, offset, what):
    raw = content[start:]
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError:
        raise BofError('%s is not ASCII' % what, offset)
    return text


def _decode(offset, tag, content):
    c = content
    if tag in (TAG_EXTRN, TAG_NEED, TAG_SECTSTAT, TAG_GLOBL):
        if not c:
            raise BofError('%s record has no name' % RECORD_NAMES[tag], offset)
        return {'name': _text(c, 0, offset, 'name')}
    if tag == TAG_ADDR:
        if len(c) != 3:
            raise BofError('ADDR record must have 3 content bytes, has %d' % len(c), offset)
        if c[0] not in ADDR_KINDS:
            raise BofError('unknown ADDR kind %d' % c[0], offset)
        return {'kind': c[0], 'value': c[1] << 8 | c[2]}
    if tag in (TAG_SECTABS, TAG_ABS):
        if len(c) < 3:
            raise BofError('%s record needs a 2-byte value and a name' % RECORD_NAMES[tag], offset)
        key = 'address' if tag == TAG_SECTABS else 'value'
        return {key: c[0] << 8 | c[1], 'name': _text(c, 2, offset, 'name')}
    if tag == TAG_CODE:
        if not c:
            raise BofError('CODE record is empty', offset)
        return {'bytes': c}
    if tag == TAG_LABEL:
        if len(c) != 2:
            raise BofError('LABEL record must have 2 content bytes, has %d' % len(c), offset)
        return {'n': c[0] << 8 | c[1]}
    if tag in FIX_OFFSET_ONLY:
        if not c:
            raise BofError('%s record is empty' % RECORD_NAMES[tag], offset)
        return {'offsets': list(c)}
    if tag in FIX_SPAN:
        if not c or len(c) % 3:
            raise BofError('%s record length %d is not a positive multiple of 3'
                           % (RECORD_NAMES[tag], len(c)), offset)
        return {'entries': [(c[i], c[i + 1] << 8 | c[i + 2]) for i in range(0, len(c), 3)]}
    if tag == TAG_END:
        if c:
            raise BofError('END record must be empty', offset)
        return {}
    raise BofError('unknown record tag %02x' % tag, offset)


def read_records(data):
    """Parse a whole file into a list of `Record`. Raises `BofError` (with the byte offset)
    for a wrong first tag, a version other than 01, a truncated record, an unknown tag,
    a malformed record, bytes after END or a missing END."""
    data = bytes(data)
    records = []
    pos = 0
    ended = False
    code_len = None     # length of the CODE record the next fix records patch
    while pos < len(data):
        if ended:
            raise BofError('data after END record', pos)
        if len(data) - pos < 2:
            raise BofError('truncated record header', pos)
        tag, length = data[pos], data[pos + 1]
        if not records and tag != TAG_HEADER:
            raise BofError('not a BOF file: first tag is %02x, expected b0' % tag, pos)
        if records and tag == TAG_HEADER:
            raise BofError('second header record', pos)
        if pos + 2 + length > len(data):
            raise BofError('truncated record %02x: content needs %d bytes, %d left'
                           % (tag, length, len(data) - pos - 2), pos)
        content = data[pos + 2:pos + 2 + length]
        if tag == TAG_HEADER:
            if length < 2:
                raise BofError('header record has no version and module name', pos)
            if content[0] != VERSION:
                raise BofError('unsupported BOF version %02x, expected %02x' % (content[0], VERSION), pos)
            fields = {'version': content[0], 'module': _text(content, 1, pos, 'module name')}
        else:
            fields = _decode(pos, tag, content)
        if tag in FIX_SPAN:
            if code_len is None:
                raise BofError('%s record does not follow a CODE record' % RECORD_NAMES[tag], pos)
            if tag in FIX_OFFSET_ONLY:
                offs = fields['offsets']
            else:
                offs = [o for o, _ in fields['entries']]
            for o in offs:
                if o + FIX_SPAN[tag] > code_len:
                    raise BofError('%s offset %d is outside the %d-byte CODE record'
                                   % (RECORD_NAMES[tag], o, code_len), pos)
        elif tag == TAG_CODE:
            code_len = length
        else:
            code_len = None
        records.append(Record(pos, tag, content, fields))
        if tag == TAG_END:
            ended = True
        pos += 2 + length
    if not records:
        raise BofError('empty file: no header record', 0)
    if not ended:
        raise BofError('missing END record', len(data))
    return records


# ---------------------------------------------------------------------------------------
# Dump
# ---------------------------------------------------------------------------------------
def _hex(raw):
    return ' '.join('%02x' % b for b in raw)


def dump(data):
    """Format a BOF file as text, one line per record (a long CODE record wraps onto
    continuation lines). Raises `BofError` if the file is not valid BOF v1.

    Line: `OFFSET  TAG NAME     content`, the file offset and tag in hex. GLOBL, LABEL and
    CODE show their section offset as `@XXXX`; fix entries show `offset XX -> target` with
    the target as `symbol k 'name'` or `label n`."""
    records = read_records(data)
    symbols = []
    section_offset = 0
    code = b''
    lines = []

    def target_text(t):
        if t & LOCAL_LABEL_FLAG:
            return 'label %d' % (t & ~LOCAL_LABEL_FLAG & 0xFFFF)
        if t < len(symbols):
            return "symbol %d '%s'" % (t, symbols[t])
        return 'symbol %d (not declared)' % t

    for r in records:
        f = r.fields
        tag = r.tag
        if tag == TAG_HEADER:
            body = "version %02x module '%s'" % (f['version'], f['module'])
        elif tag == TAG_EXTRN:
            body = "symbol %d '%s'" % (len(symbols), f['name'])
            symbols.append(f['name'])
        elif tag in (TAG_NEED, TAG_SECTSTAT):
            body = "'%s'" % f['name']
            if tag == TAG_SECTSTAT:
                section_offset = 0
        elif tag == TAG_SECTABS:
            body = "address %04x '%s'" % (f['address'], f['name'])
            section_offset = 0
        elif tag == TAG_ADDR:
            body = '%s %04x' % (ADDR_KINDS[f['kind']], f['value'])
        elif tag == TAG_GLOBL:
            body = "'%s' @%04x" % (f['name'], section_offset)
        elif tag == TAG_LABEL:
            body = 'label %d @%04x' % (f['n'], section_offset)
        elif tag == TAG_ABS:
            body = "'%s' = %04x" % (f['name'], f['value'])
        elif tag == TAG_CODE:
            code = f['bytes']
            hexed = [_hex(code[i:i + 16]) for i in range(0, len(code), 16)]
            body = '@%04x %d bytes: %s' % (section_offset, len(code), hexed[0])
            section_offset += len(code)
        elif tag in FIX_OFFSET_ONLY:
            parts = []
            for o in f['offsets']:
                parts.append('offset %02x -> %s' % (o, target_text(code[o] << 8 | code[o + 1])))
            body = '; '.join(parts)
        elif tag in FIX_SPAN:
            body = '; '.join('offset %02x -> %s' % (o, target_text(t)) for o, t in f['entries'])
        else:
            body = ''
        lines.append(('%04x  %02x %-8s %s' % (r.offset, tag, r.name, body)).rstrip())
        if tag == TAG_CODE:
            pad = ' ' * 24
            lines.extend(pad + h for h in hexed[1:])
    return '\n'.join(lines) + '\n'
