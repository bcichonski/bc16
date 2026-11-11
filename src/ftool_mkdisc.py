"""Build a bdos disc image (.bdd) from a text disc manifest: `ftool mkdisc MANIFEST OUT.bdd`.

Manifest format (one file per line, `#` starts a comment, blank lines are ignored):

    NAME.EXT  SOURCE  ATTRIBS  [PLACE]

* NAME.EXT - disc name, 1-8 characters + optional extension of 0-3 characters,
  `A-Z` / `0-9` only (upper-cased by the tool).
* SOURCE   - file path relative to the manifest's directory.
* ATTRIBS  - letters from `R W X S` in any order.
* PLACE    - `boot`, `system`, an explicit `T/S` start (decimal), or empty (automatic).

The first file line must be the `boot` file and the second the `system` file.
`DISC.CAT` is never listed: the tool writes it itself (catalog v1, see bdos/bdio.b).

Everything is validated before anything is written: on any error `MkdiscError`
is raised and the output file is neither created nor modified.

This module has no side effects on import (ftool.py does, it runs main()).
"""

import os
import re
import tempfile

from bc64 import bc64_io

SECTOR_SIZE = bc64_io.FloppyDriveV1.SECTOR_SIZE  # 128
SECTORS = bc64_io.FloppyDriveV1.SECTORS          # sectors per track
TRACKS = bc64_io.FloppyDriveV1.TRACKS
DISC_SECTORS = SECTORS * TRACKS                  # 1024
IMAGE_SIZE = DISC_SECTORS * SECTOR_SIZE          # 131072

# Catalog v1 (bdos/bdioh.b BDIO_FCAT_*): track 0 sector 1 .. track 1 sector 15.
CATALOG_START = 1                                # linear sector 0/1
CATALOG_SECTORS = 2 * SECTORS - 1                # 31
ENTRY_SIZE = 16
CATALOG_ENTRIES = CATALOG_SECTORS * SECTOR_SIZE // ENTRY_SIZE  # 248
MAX_USED_ENTRIES = CATALOG_ENTRIES - 1           # 247: one entry must stay empty
MAX_FILE_SECTORS = 255                           # 1-byte length field
NAME_LEN = 8
EXT_LEN = 3

# Boot loader (bdos/boot.basm): reads linear sectors 0x20..0xbf (2/0..11/15).
BOOT_SECTOR = 0
BOOT_SIGNATURE = bytes([0xbd, 0x05, 0x01, 0x01])
SYSTEM_START = 2 * SECTORS                       # 32
SYSTEM_SECTORS = 160                             # whole loader range
FIRST_AUTO_SECTOR = SYSTEM_START + SYSTEM_SECTORS  # 192 = 12/0

ATTRIBUTES = {'R': 0x01, 'W': 0x02, 'X': 0x04, 'S': 0x80}
CATALOG_NAME = ('DISC', 'CAT')
CATALOG_ATTRIBS = ATTRIBUTES['S'] | ATTRIBUTES['R']

PLACE_BOOT = 'boot'
PLACE_SYSTEM = 'system'

_NAME_RE = re.compile(r'^([A-Z0-9]{1,8})(?:\.([A-Z0-9]{0,3}))?$')
_PLACE_RE = re.compile(r'^(\d+)/(\d+)$')


class MkdiscError(Exception):
    """A manifest or source problem; the message names the line/file and the limit."""


class ManifestLine:
    def __init__(self, lineno, name, ext, source, attribs, place):
        self.lineno = lineno
        self.name = name        # upper-case, unpadded
        self.ext = ext          # upper-case, unpadded, may be ''
        self.source = source    # absolute/joined path
        self.attribs = attribs  # attribute byte
        self.place = place      # 'boot', 'system', (track, sector) or None

    @property
    def disc_name(self):
        return '{}.{}'.format(self.name, self.ext) if self.ext else self.name


class CatalogEntry:
    def __init__(self, number, start, length, attribs, name, ext, data):
        self.number = number
        self.start = start      # linear sector
        self.length = length    # sectors
        self.attribs = attribs
        self.name = name
        self.ext = ext
        self.data = data        # bytes written from start (None for DISC.CAT)

    @property
    def track(self):
        return self.start // SECTORS

    @property
    def sector(self):
        return self.start % SECTORS

    @property
    def end(self):
        return self.start + self.length


def _parse_name(text, where):
    match = _NAME_RE.match(text.upper())
    if not match:
        raise MkdiscError('{}: bad name "{}" (expected 1-8 + 0-3 characters A-Z/0-9)'.format(where, text))
    return match.group(1), match.group(2) or ''


def _parse_attribs(text, where):
    value = 0
    for letter in text.upper():
        if letter not in ATTRIBUTES:
            raise MkdiscError('{}: unknown attribute "{}" in "{}" (allowed: R W X S)'.format(where, letter, text))
        value |= ATTRIBUTES[letter]
    if value == 0:
        raise MkdiscError('{}: empty attributes (allowed: R W X S)'.format(where))
    return value


def _parse_place(text, where):
    if text is None:
        return None
    if text in (PLACE_BOOT, PLACE_SYSTEM):
        return text
    match = _PLACE_RE.match(text)
    if not match:
        raise MkdiscError('{}: bad place "{}" (expected boot, system or T/S)'.format(where, text))
    track, sector = int(match.group(1)), int(match.group(2))
    if track >= TRACKS or sector >= SECTORS:
        raise MkdiscError('{}: start {}/{} outside the disc ({} tracks x {} sectors)'.format(
            where, track, sector, TRACKS, SECTORS))
    return track, sector


def parse_manifest(manifest_path):
    """Parse the manifest into ManifestLine objects (no source files are read)."""
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except OSError as e:
        raise MkdiscError('{}: cannot read manifest ({})'.format(manifest_path, e.strerror or e))

    base = os.path.dirname(os.path.abspath(manifest_path))
    lines = []
    seen = {CATALOG_NAME: 'reserved for the catalog'}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        content = raw.split('#', 1)[0].strip()
        if not content:
            continue
        where = '{}:{}'.format(manifest_path, lineno)
        columns = content.split()
        if len(columns) not in (3, 4):
            raise MkdiscError('{}: malformed line "{}" (expected NAME.EXT SOURCE ATTRIBS [PLACE])'.format(
                where, content))
        name, ext = _parse_name(columns[0], where)
        if (name, ext) in seen:
            raise MkdiscError('{}: duplicate name "{}" ({})'.format(where, columns[0].upper(), seen[(name, ext)]))
        seen[(name, ext)] = 'already on line {}'.format(lineno)
        attribs = _parse_attribs(columns[2], where)
        place = _parse_place(columns[3] if len(columns) == 4 else None, where)

        index = len(lines)
        if index == 0 and place != PLACE_BOOT:
            raise MkdiscError('{}: the first file must be the boot file (PLACE boot)'.format(where))
        if index == 1 and place != PLACE_SYSTEM:
            raise MkdiscError('{}: the second file must be the system file (PLACE system)'.format(where))
        if index >= 2 and place in (PLACE_BOOT, PLACE_SYSTEM):
            raise MkdiscError('{}: "{}" is only allowed on the {} file line'.format(
                where, place, 'first' if place == PLACE_BOOT else 'second'))

        source = os.path.join(base, columns[1])
        lines.append(ManifestLine(lineno, name, ext, source, attribs, place))

    if len(lines) < 2:
        raise MkdiscError('{}: the manifest must list at least the boot and the system file'.format(manifest_path))
    return lines


def _read_source(line, manifest_path):
    where = '{}:{}'.format(manifest_path, line.lineno)
    try:
        with open(line.source, 'rb') as f:
            data = f.read()
    except OSError as e:
        raise MkdiscError('{}: cannot read source file {} ({})'.format(where, line.source, e.strerror or e))
    if not data:
        raise MkdiscError('{}: source file {} is empty (a 0-sector entry would end the catalog)'.format(
            where, line.source))
    return data, where


def _sectors(size):
    return (size + SECTOR_SIZE - 1) // SECTOR_SIZE


def plan_disc(manifest_path):
    """Parse, size and place everything; return the list of CatalogEntry (entry order).

    Raises MkdiscError on the first problem; nothing is written."""
    lines = parse_manifest(manifest_path)

    used = len(lines) + 1  # + DISC.CAT
    if used > MAX_USED_ENTRIES:
        raise MkdiscError('{}: catalog full: {} entries used, at most {} allowed'.format(
            manifest_path, used, MAX_USED_ENTRIES))

    entries = []
    boot_line, system_line = lines[0], lines[1]

    data, where = _read_source(boot_line, manifest_path)
    if len(data) != SECTOR_SIZE:
        raise MkdiscError('{}: boot file {} is {} bytes, it must be exactly {}'.format(
            where, boot_line.source, len(data), SECTOR_SIZE))
    if data[-len(BOOT_SIGNATURE):] != BOOT_SIGNATURE:
        raise MkdiscError('{}: boot file {} does not end with the signature BD 05 01 01'.format(
            where, boot_line.source))
    entries.append(CatalogEntry(0, BOOT_SECTOR, 1, boot_line.attribs, boot_line.name, boot_line.ext, data))

    entries.append(CatalogEntry(1, CATALOG_START, CATALOG_SECTORS, CATALOG_ATTRIBS,
                                CATALOG_NAME[0], CATALOG_NAME[1], None))

    data, where = _read_source(system_line, manifest_path)
    if _sectors(len(data)) > SYSTEM_SECTORS:
        raise MkdiscError('{}: system file {} is {} sectors, the boot loader range holds at most {}'.format(
            where, system_line.source, _sectors(len(data)), SYSTEM_SECTORS))
    entries.append(CatalogEntry(2, SYSTEM_START, SYSTEM_SECTORS, system_line.attribs,
                                system_line.name, system_line.ext, data))

    next_free = FIRST_AUTO_SECTOR
    for number, line in enumerate(lines[2:], start=3):
        data, where = _read_source(line, manifest_path)
        length = _sectors(len(data))
        if length > MAX_FILE_SECTORS:
            raise MkdiscError('{}: {} is {} sectors, a file holds at most {}'.format(
                where, line.disc_name, length, MAX_FILE_SECTORS))
        if line.place is None:
            start = next_free
        else:
            track, sector = line.place
            start = track * SECTORS + sector
            if start < next_free:
                raise MkdiscError('{}: start {}/{} is before the next free sector {}/{}'.format(
                    where, track, sector, next_free // SECTORS, next_free % SECTORS))
        end = start + length
        if end > DISC_SECTORS:
            raise MkdiscError('{}: {} ({} sectors from {}/{}) does not fit: it ends past sector {}'.format(
                where, line.disc_name, length, start // SECTORS, start % SECTORS, DISC_SECTORS))
        entries.append(CatalogEntry(number, start, length, line.attribs, line.name, line.ext, data))
        next_free = end

    return entries


def encode_catalog(entries):
    """Catalog v1 bytes (31 sectors): every entry numbered, unused entries otherwise zero."""
    catalog = bytearray(CATALOG_SECTORS * SECTOR_SIZE)
    for number in range(CATALOG_ENTRIES):
        catalog[number * ENTRY_SIZE] = number
    for entry in entries:
        offset = entry.number * ENTRY_SIZE
        catalog[offset:offset + 5] = bytes([entry.number, entry.track, entry.sector, entry.length, entry.attribs])
        name = entry.name.ljust(NAME_LEN) + entry.ext.ljust(EXT_LEN)
        catalog[offset + 5:offset + ENTRY_SIZE] = name.encode('ascii')
    return bytes(catalog)


def build_image(manifest_path):
    """Return the complete disc image bytes for the manifest (raises MkdiscError)."""
    entries = plan_disc(manifest_path)
    image = bytearray(IMAGE_SIZE)
    for entry in entries:
        if entry.data is not None:
            offset = entry.start * SECTOR_SIZE
            image[offset:offset + len(entry.data)] = entry.data
    catalog_offset = CATALOG_START * SECTOR_SIZE
    image[catalog_offset:catalog_offset + CATALOG_SECTORS * SECTOR_SIZE] = encode_catalog(entries)
    return bytes(image)


def _output_mode(out_path):
    # mkstemp creates 0600; give the image the mode a plain open() would (keep an existing file's).
    if os.path.exists(out_path):
        return os.stat(out_path).st_mode & 0o7777
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def mkdisc(manifest_path, out_path):
    """Validate the manifest, then write the image to out_path in one step."""
    image = build_image(manifest_path)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    try:
        fd, tmp_path = tempfile.mkstemp(prefix='.mkdisc-', suffix='.tmp', dir=out_dir)
    except OSError as e:
        raise MkdiscError('{}: cannot write output ({})'.format(out_path, e.strerror or e))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(image)
        os.chmod(tmp_path, _output_mode(out_path))
        os.replace(tmp_path, out_path)
    except OSError as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise MkdiscError('{}: cannot write output ({})'.format(out_path, e.strerror or e))
    return image
