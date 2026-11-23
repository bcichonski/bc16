"""Host text files <-> TextEd files on a bdos disc image.

    ftool importtext DISC.bdd host.txt NAME.EXT
    ftool exporttext DISC.bdd NAME.EXT host.txt [--numbers]

A TextEd file (bdos/texted.b saveLines/readLines, decision D6) is a sequence of records
`<decimal line number> <text>` + 0x13, then one 0x00, zero padded to whole sectors.
importtext numbers the host lines 10, 20, 30 ... and adds a new catalog entry (attributes
R W) in the largest free gap of sectors 192..1023 (tie: lowest start), exactly where bdio puts a new file.
exporttext writes the text of a catalog entry back to the host, one LF-terminated line
per record.

Rules: a blank host line is stored as a one-space text (readLines skips records with no
text), so a host line that is exactly one space is refused; lines hold tab and printable
ASCII only, at most 80 bytes; at most 6553 lines; an existing name is never overwritten.
Everything is validated before anything is written: on any error `TextError` is raised and
the disc (import) or host file (export) is neither created nor modified.

This module has no side effects on import (ftool.py does, it runs main()).
"""

import os
import re
import tempfile

import ftool_mkdisc as mk

LINE_STEP = 10
MAX_LINE_LENGTH = 80          # texted.b MAXLINELENGTH
MAX_LINES = 6553              # 10 * 6553 = 65530 fits 16 bits
MAX_LINE_NUMBER = 65535
RECORD_END = 0x13
FILE_END = 0x00
BLANK_TEXT = b' '
NEW_FILE_ATTRIBS = mk.ATTRIBUTES['R'] | mk.ATTRIBUTES['W']
ALLOWED_BYTES = frozenset([0x09] + list(range(0x20, 0x7f)))

_RECORD_RE = re.compile(rb'^([0-9]{1,5}) (.*)$', re.DOTALL)


class TextError(Exception):
    """A disc, name or text problem; the message names the limit."""


def _name_of(text):
    try:
        name, ext = mk._parse_name(text, text)
    except mk.MkdiscError:
        raise TextError('bad name "{}" (expected 1-8 + 0-3 characters A-Z/0-9)'.format(text))
    if (name, ext) == mk.CATALOG_NAME:
        raise TextError('DISC.CAT is the catalog, it cannot be used as a text file')
    return name, ext


def _read_file(path, what):
    try:
        with open(path, 'rb') as f:
            return f.read()
    except OSError as e:
        raise TextError('{}: cannot read {} ({})'.format(path, what, e.strerror or e))


def _read_image(path):
    image = _read_file(path, 'disc image')
    if len(image) != mk.IMAGE_SIZE:
        raise TextError('{}: disc image is {} bytes, it must be exactly {}'.format(
            path, len(image), mk.IMAGE_SIZE))
    return image


def _write_atomic(path, data, what):
    out_dir = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp_path = tempfile.mkstemp(prefix='.ftool-', suffix='.tmp', dir=out_dir)
    except OSError as e:
        raise TextError('{}: cannot write {} ({})'.format(path, what, e.strerror or e))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.chmod(tmp_path, mk._output_mode(path))
        os.replace(tmp_path, path)
    except OSError as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise TextError('{}: cannot write {} ({})'.format(path, what, e.strerror or e))


class Entry:
    def __init__(self, index, start, length, attribs, name, ext):
        self.index = index
        self.start = start      # linear sector (track * 16 + sector)
        self.length = length
        self.attribs = attribs
        self.name = name
        self.ext = ext

    @property
    def end(self):
        return self.start + self.length


def read_catalog(image):
    """Return (used entries in order, index of the first free entry)."""
    used = []
    base = mk.CATALOG_START * mk.SECTOR_SIZE
    for index in range(mk.CATALOG_ENTRIES):
        raw = image[base + index * mk.ENTRY_SIZE:base + (index + 1) * mk.ENTRY_SIZE]
        if raw[3] == 0:
            return used, index
        text = raw[5:].decode('latin-1')
        used.append(Entry(index, raw[1] * mk.SECTORS + raw[2], raw[3], raw[4],
                          text[:mk.NAME_LEN].rstrip(), text[mk.NAME_LEN:].rstrip()))
    return used, mk.CATALOG_ENTRIES


def _largest_gap(used):
    """(start, length) of the longest free run in the allocatable area (tie: lowest start).

    Same rule as bdio: sectors below ALLOC_FIRST_SECTOR are always used, whatever the
    catalog says; extents are clipped to the disc. Length 0 when nothing is free.
    """
    first = mk.ALLOC_FIRST_SECTOR
    taken = bytearray(mk.DISC_SECTORS)
    for entry in used:
        for sector in range(entry.start, min(entry.end, mk.DISC_SECTORS)):
            taken[sector] = 1
    best_start, best_len = first, 0
    run_start = None
    for sector in range(first, mk.DISC_SECTORS + 1):
        if sector < mk.DISC_SECTORS and not taken[sector]:
            if run_start is None:
                run_start = sector
        elif run_start is not None:
            if sector - run_start > best_len:
                best_start, best_len = run_start, sector - run_start
            run_start = None
    return best_start, best_len


def _split_lines(data):
    lines = data.split(b'\n')
    if lines and lines[-1] == b'':
        lines.pop()
    return [line[:-1] if line.endswith(b'\r') else line for line in lines]


def encode_text(data):
    """Host text bytes -> (TextEd file bytes padded to whole sectors, line count)."""
    lines = _split_lines(data)
    if len(lines) > MAX_LINES:
        raise TextError('{} lines, at most {} fit (line numbers are 16 bit)'.format(len(lines), MAX_LINES))
    out = bytearray()
    for number, line in enumerate(lines, start=1):
        for byte in line:
            if byte not in ALLOWED_BYTES:
                raise TextError('line {}: byte 0x{:02x} is not allowed (only tab and printable ASCII)'.format(
                    number, byte))
        if len(line) > MAX_LINE_LENGTH:
            raise TextError('line {}: {} characters, at most {} (TextEd limit)'.format(
                number, len(line), MAX_LINE_LENGTH))
        if line == BLANK_TEXT:
            raise TextError('line {}: a line of exactly one space cannot be told from an empty line '
                            '(empty lines are stored as one space)'.format(number))
        out += str(number * LINE_STEP).encode('ascii') + b' ' + (line or BLANK_TEXT) + bytes([RECORD_END])
    out.append(FILE_END)
    sectors = (len(out) + mk.SECTOR_SIZE - 1) // mk.SECTOR_SIZE
    if sectors > mk.MAX_FILE_SECTORS:
        raise TextError('the text needs {} sectors, a file holds at most {}'.format(sectors, mk.MAX_FILE_SECTORS))
    out += bytes(sectors * mk.SECTOR_SIZE - len(out))
    return bytes(out), len(lines)


def import_text(disc_path, host_path, name_text):
    """Add the host text as a new TextEd file; return a one-line summary."""
    name, ext = _name_of(name_text)
    host = _read_file(host_path, 'host file')
    data, line_count = encode_text(host)
    sectors = len(data) // mk.SECTOR_SIZE
    image = _read_image(disc_path)

    used, free_index = read_catalog(image)
    for entry in used:
        if (entry.name, entry.ext) == (name, ext):
            raise TextError('{} already exists on the disc (it is never overwritten)'.format(
                '{}.{}'.format(name, ext) if ext else name))
    if free_index >= mk.MAX_USED_ENTRIES:
        raise TextError('catalog full: {} entries used, at most {} allowed'.format(
            free_index, mk.MAX_USED_ENTRIES))
    start, room = _largest_gap(used)
    if sectors > room:
        raise TextError('disc full: {} sectors needed, the largest free gap is {} sectors (at sector {})'.format(
            sectors, room, start))

    new = bytearray(image)
    offset = start * mk.SECTOR_SIZE
    new[offset:offset + len(data)] = data
    entry_offset = mk.CATALOG_START * mk.SECTOR_SIZE + free_index * mk.ENTRY_SIZE
    new[entry_offset:entry_offset + 5] = bytes([free_index, start // mk.SECTORS, start % mk.SECTORS,
                                                sectors, NEW_FILE_ATTRIBS])
    new[entry_offset + 5:entry_offset + mk.ENTRY_SIZE] = (
        name.ljust(mk.NAME_LEN) + ext.ljust(mk.EXT_LEN)).encode('ascii')
    _write_atomic(disc_path, bytes(new), 'disc image')
    return 'imported {} lines as {} ({} sectors at track {} sector {})'.format(
        line_count, '{}.{}'.format(name, ext) if ext else name, sectors, start // mk.SECTORS, start % mk.SECTORS)


def decode_text(data, numbers=False):
    """TextEd file bytes -> host text bytes (raises TextError on a malformed record)."""
    end = data.find(bytes([FILE_END]))
    body = data if end < 0 else data[:end]
    if not body:
        return b''
    records = body.split(bytes([RECORD_END]))
    if body[-1] == RECORD_END:
        records.pop()
    out = bytearray()
    for index, record in enumerate(records, start=1):
        match = _RECORD_RE.match(record)
        if not match or int(match.group(1)) > MAX_LINE_NUMBER:
            raise TextError('record {} is malformed (expected "<number up to {}> <text>")'.format(
                index, MAX_LINE_NUMBER))
        if numbers:
            out += record + b'\n'
        else:
            text = match.group(2)
            out += (b'' if text == BLANK_TEXT else text) + b'\n'
    return bytes(out)


def export_text(disc_path, name_text, host_path, numbers=False):
    """Write the text of a TextEd file on the disc to the host; return a one-line summary."""
    name, ext = _name_of(name_text)
    image = _read_image(disc_path)
    used, _ = read_catalog(image)
    label = '{}.{}'.format(name, ext) if ext else name
    for entry in used:
        if (entry.name, entry.ext) == (name, ext):
            break
    else:
        raise TextError('{} not found on the disc'.format(label))
    if entry.end > mk.DISC_SECTORS:
        raise TextError('{} runs past the end of the disc'.format(label))
    text = decode_text(image[entry.start * mk.SECTOR_SIZE:entry.end * mk.SECTOR_SIZE], numbers)
    _write_atomic(host_path, text, 'host file')
    return 'exported {} ({} lines)'.format(label, text.count(b'\n'))
