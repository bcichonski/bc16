"""Build a bdos disc image (.bdd) from a text disc manifest: `ftool mkdisc MANIFEST OUT.bdd`.

Manifest format (one file per line, `#` starts a comment, blank lines are ignored):

    NAME.EXT  SOURCE  ATTRIBS  [key=value ...]

* NAME.EXT - disc name, 1-8 characters + optional extension of 0-3 characters,
  `A-Z` / `0-9` only (upper-cased by the tool).
* SOURCE   - file path relative to the manifest's directory (`-` for the catalog).
* ATTRIBS  - letters from `R W X S` in any order.
* options, in any order, each at most once:
    role=boot|catalog|system  the three special entries (see below)
    at=T/S                    exact start (decimal track/sector); never before the end of
                              the previous slot, and inside the disc
    max=N                     the file must be at most N sectors (N <= 255); reserves an
                              N-sector slot, so the next file without at= starts after it.
                              Without max the slot is the file's own size.

The first three lines are the role=boot, role=catalog and role=system files, in that
order (catalog entries 0, 1, 2); no other line has a role. The roles keep their hardware
rules, and a manifest that contradicts them is refused:

* boot    - at=0/0 max=1, a 128-byte file ending with the signature BD 05 01 01.
* catalog - DISC.CAT, source `-`, at=0/1 max=31 (catalog v1, see bdos/bdio.b); the tool
            writes its content itself.
* system  - at=2/0 and max <= 160 (the boot loader range); catalogued with length max
            (the file is zero-padded).

Every other file is catalogued with its real size. Files without at= follow back to
back after the previous slot.

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

ATTRIBUTES = {'R': 0x01, 'W': 0x02, 'X': 0x04, 'S': 0x80}
CATALOG_NAME = ('DISC', 'CAT')

ROLE_BOOT = 'boot'
ROLE_CATALOG = 'catalog'
ROLE_SYSTEM = 'system'
ROLES = (ROLE_BOOT, ROLE_CATALOG, ROLE_SYSTEM)  # must be the first three lines, in this order
NO_SOURCE = '-'
OPTION_KEYS = ('role', 'at', 'max')

_NAME_RE = re.compile(r'^([A-Z0-9]{1,8})(?:\.([A-Z0-9]{0,3}))?$')
_PLACE_RE = re.compile(r'^(\d+)/(\d+)$')


class MkdiscError(Exception):
    """A manifest or source problem; the message names the line/file and the limit."""


class ManifestLine:
    def __init__(self, lineno, name, ext, source, attribs, role, start, max_sectors):
        self.lineno = lineno
        self.name = name        # upper-case, unpadded
        self.ext = ext          # upper-case, unpadded, may be ''
        self.source = source    # absolute/joined path, None for the catalog
        self.attribs = attribs  # attribute byte
        self.role = role        # 'boot', 'catalog', 'system' or None
        self.start = start      # at=: linear start sector or None
        self.max_sectors = max_sectors  # max= or None

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


def _parse_at(text, where):
    match = _PLACE_RE.match(text)
    if not match:
        raise MkdiscError('{}: bad value "{}" for at (expected T/S, decimal)'.format(where, text))
    track, sector = int(match.group(1)), int(match.group(2))
    if track >= TRACKS or sector >= SECTORS:
        raise MkdiscError('{}: start {}/{} outside the disc ({} tracks x {} sectors)'.format(
            where, track, sector, TRACKS, SECTORS))
    return track * SECTORS + sector


def _parse_max(text, where):
    if not re.match(r'^\d+$', text) or int(text) < 1:
        raise MkdiscError('{}: bad value "{}" for max (expected a number of sectors, 1-{})'.format(
            where, text, MAX_FILE_SECTORS))
    value = int(text)
    if value > MAX_FILE_SECTORS:
        raise MkdiscError('{}: max={} is more than a file can hold ({} sectors)'.format(
            where, value, MAX_FILE_SECTORS))
    return value


def _parse_options(tokens, where):
    options = {}
    for token in tokens:
        key, eq, value = token.partition('=')
        if not eq or not value:
            raise MkdiscError('{}: malformed option "{}" (expected key=value)'.format(where, token))
        if key not in OPTION_KEYS:
            raise MkdiscError('{}: unknown option "{}" (allowed: {})'.format(where, key, ', '.join(OPTION_KEYS)))
        if key in options:
            raise MkdiscError('{}: duplicate option "{}"'.format(where, key))
        if key == 'role':
            if value not in ROLES:
                raise MkdiscError('{}: bad value "{}" for role (allowed: {})'.format(where, value, ', '.join(ROLES)))
            options[key] = value
        elif key == 'at':
            options[key] = _parse_at(value, where)
        else:
            options[key] = _parse_max(value, where)
    return options


def _check_role(line, where):
    """The hardware rules of the three special entries."""
    role, at, limit = line.role, line.start, line.max_sectors
    if role == ROLE_BOOT:
        if at != BOOT_SECTOR or limit != 1:
            raise MkdiscError('{}: role=boot needs at=0/0 max=1 (the boot ROM loads track 0 sector 0)'.format(where))
    elif role == ROLE_CATALOG:
        if at != CATALOG_START or limit != CATALOG_SECTORS:
            raise MkdiscError('{}: role=catalog needs at=0/1 max={} (catalog v1 is hard-coded in bdio)'.format(
                where, CATALOG_SECTORS))
    elif role == ROLE_SYSTEM:
        if at != SYSTEM_START:
            raise MkdiscError('{}: role=system needs at=2/0 (the boot loader reads from there)'.format(where))
        if limit is None or limit > SYSTEM_SECTORS:
            raise MkdiscError('{}: role=system needs max=N with N <= {} (the boot loader range 2/0..11/15)'.format(
                where, SYSTEM_SECTORS))


def parse_manifest(manifest_path):
    """Parse the manifest into ManifestLine objects (no source files are read)."""
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except OSError as e:
        raise MkdiscError('{}: cannot read manifest ({})'.format(manifest_path, e.strerror or e))

    base = os.path.dirname(os.path.abspath(manifest_path))
    lines = []
    seen = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        content = raw.split('#', 1)[0].strip()
        if not content:
            continue
        where = '{}:{}'.format(manifest_path, lineno)
        columns = content.split()
        if len(columns) < 3:
            raise MkdiscError('{}: malformed line "{}" (expected NAME.EXT SOURCE ATTRIBS [key=value ...])'.format(
                where, content))
        name, ext = _parse_name(columns[0], where)
        if (name, ext) in seen:
            raise MkdiscError('{}: duplicate name "{}" ({})'.format(where, columns[0].upper(), seen[(name, ext)]))
        seen[(name, ext)] = 'already on line {}'.format(lineno)
        attribs = _parse_attribs(columns[2], where)
        options = _parse_options(columns[3:], where)
        role = options.get('role')

        if (name, ext) == CATALOG_NAME and role != ROLE_CATALOG:
            raise MkdiscError('{}: DISC.CAT is the catalog: it needs role=catalog'.format(where))

        index = len(lines)
        if index < len(ROLES) and role != ROLES[index]:
            raise MkdiscError('{}: file {} of the manifest must have role={} (the first three files are boot, '
                              'catalog and system)'.format(where, index + 1, ROLES[index]))
        if index >= len(ROLES) and role is not None:
            raise MkdiscError('{}: role={} is only allowed on line {} of the file list'.format(
                where, role, ROLES.index(role) + 1))
        if role == ROLE_CATALOG and (name, ext) != CATALOG_NAME:
            raise MkdiscError('{}: role=catalog is only for DISC.CAT'.format(where))
        if (columns[1] == NO_SOURCE) != (role == ROLE_CATALOG):
            raise MkdiscError('{}: the source "-" is for (and only for) role=catalog'.format(where))

        line = ManifestLine(lineno, name, ext, None if role == ROLE_CATALOG else os.path.join(base, columns[1]),
                            attribs, role, options.get('at'), options.get('max'))
        if role:
            _check_role(line, where)
        lines.append(line)

    if len(lines) < len(ROLES):
        raise MkdiscError('{}: the manifest must list at least the boot, catalog and system file'.format(
            manifest_path))
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

    if len(lines) > MAX_USED_ENTRIES:
        raise MkdiscError('{}: catalog full: {} entries used, at most {} allowed'.format(
            manifest_path, len(lines), MAX_USED_ENTRIES))

    entries = []
    next_free = 0
    for number, line in enumerate(lines):
        where = '{}:{}'.format(manifest_path, line.lineno)
        if line.role == ROLE_CATALOG:
            data, size = None, CATALOG_SECTORS
            attribs = line.attribs
        else:
            data, where = _read_source(line, manifest_path)
            size = _sectors(len(data))
            attribs = line.attribs
        if line.role == ROLE_BOOT:
            if len(data) != SECTOR_SIZE:
                raise MkdiscError('{}: boot file {} is {} bytes, it must be exactly {}'.format(
                    where, line.source, len(data), SECTOR_SIZE))
            if data[-len(BOOT_SIGNATURE):] != BOOT_SIGNATURE:
                raise MkdiscError('{}: boot file {} does not end with the signature BD 05 01 01'.format(
                    where, line.source))
        if size > MAX_FILE_SECTORS:
            raise MkdiscError('{}: {} is {} sectors, a file holds at most {}'.format(
                where, line.disc_name, size, MAX_FILE_SECTORS))
        if line.max_sectors is not None and size > line.max_sectors:
            raise MkdiscError('{}: {} is {} sectors, more than max={}'.format(
                where, line.disc_name, size, line.max_sectors))

        slot = line.max_sectors if line.max_sectors is not None else size
        if line.role in (ROLE_BOOT, ROLE_CATALOG):
            length = slot
        elif line.role == ROLE_SYSTEM:
            length = line.max_sectors  # catalogued as the whole slot (zero-padded)
        else:
            length = size

        if line.start is None:
            start = next_free
        else:
            start = line.start
            if start < next_free:
                raise MkdiscError('{}: start {}/{} is before the next free sector {}/{} (the end of the '
                                  'previous slot)'.format(where, start // SECTORS, start % SECTORS,
                                                          next_free // SECTORS, next_free % SECTORS))
        end = start + slot
        if end > DISC_SECTORS:
            raise MkdiscError('{}: {} ({} sectors from {}/{}) does not fit: it ends past sector {}'.format(
                where, line.disc_name, slot, start // SECTORS, start % SECTORS, DISC_SECTORS))
        entries.append(CatalogEntry(number, start, length, attribs, line.name, line.ext, data))
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
