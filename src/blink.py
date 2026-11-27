"""blink.py, the bc16 reference linker for BOF v1 objects (#117).

It implements the algorithm BLINK will use (docs/analysis/07-self-hosted-compiler.md, "What the
linker does" and "Linker algorithm (BLINK)") on top of `bof.read_records` (G15):

1. the module list starts `RUNTIME`, `NAME`; pass 1 reads every module in order and appends each
   `de` (NEED) name not listed yet. `NAME` is the file `name.o`, searched in the main object's
   folder, then in the library folder (`src/bc/`, or `lib_dir`);
2. pass 1 collects the `ad` addresses, sections, globals, local labels and each section's
   references, and keeps every CODE record with its fix records for pass 2;
3. duplicate globals (also `__end`/`__heap`, which the linker defines) and conflicting `ad` values
   are errors;
4. mark: the roots are every SECTABS section, the entry (the first section of the first module)
   and the section defining `F_main` (D3); an undefined symbol used by a kept section is an error;
5. layout from `#code` (default 0x6000): the entry, then `F_main`'s section (D10), then the other
   kept SECTSTAT sections in module-list order, then section order. `__end` is the address after
   the last placed byte, `__heap` the `#heap` address (D12);
6. size checks: over 32,640 bytes, or the end reaching `#heap` / `#codelimit`.

`link_layout()` runs steps 1-6 and returns a `Link`. Every error found is collected in
`Link.errors` as a complete `blink: error: ...` line (D8); nothing is written by this part.
When a module is missing or unreadable, mark, layout and the size checks are skipped
(`Link.incomplete`): their errors would only follow from the missing module.
Pass 2 (fixups, image, CLI) builds on `Link.kept`, `Section.chunks` and `Link.target_address`.
"""

import os

import bof

DEFAULT_CODE = 0x6000
MAX_IMAGE_SIZE = 32640          # 255 sectors of 128 bytes, the file-system limit
FIRST_MODULE = 'RUNTIME'
MAIN_SYMBOL = 'F_main'
END_SYMBOL = '__end'
HEAP_SYMBOL = '__heap'
LINKER_SYMBOLS = (END_SYMBOL, HEAP_SYMBOL)
ERROR_PREFIX = 'blink: error: '
DEFAULT_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bc')
COMMAND_LINE = 'the command line'


def object_file_name(module):
    """The file holding module `module`: `name.o`, lower case, as `bc81asmc --obj` writes it."""
    return module.lower() + '.o'


class Fix:
    """One fix entry of a CODE record: `kind` (a `bof.FIX_*`), `offset` in the record and the
    16-bit `target` (read from the placeholder for ABS16/REL15)."""

    def __init__(self, kind, offset, target):
        self.kind = kind
        self.offset = offset
        self.target = target

    def __repr__(self):
        return 'Fix(%s, %d, %04x)' % (bof.RECORD_NAMES[self.kind], self.offset, self.target)


class Chunk:
    """One CODE record of a section: its `offset` in the section, its `data` and its `fixes`."""

    def __init__(self, offset, data):
        self.offset = offset
        self.data = bytes(data)
        self.fixes = []


class Section:
    """One section of a module. `absolute` is True for SECTABS (then `address` is fixed by the
    object); for SECTSTAT `address` is assigned by the layout (None while unplaced)."""

    def __init__(self, module, index, name, absolute, address=None):
        self.module = module
        self.index = index
        self.name = name
        self.absolute = absolute
        self.address = address
        self.size = 0
        self.chunks = []
        self.globals = []           # (name, offset)
        self.refs = []              # fix targets in order of first use, no repeats
        self.kept = False

    def __repr__(self):
        return 'Section(%s.%s)' % (self.module.name, self.name)

    def describe(self):
        return "section '%s' of module %s" % (self.name, self.module.name)


class Module:
    """One object read by pass 1."""

    def __init__(self, name, path, needed_by):
        self.name = name            # from the header once read, otherwise the list name
        self.list_name = name       # the name in the module list (command line or NEED)
        self.path = path
        self.needed_by = needed_by
        self.symbols = []           # EXTRN names: symbol k is symbols[k]
        self.sections = []
        self.labels = {}            # local label n -> (section, offset)
        self.needs = []
        self.addrs = []             # (kind, value)
        self.absolutes = []         # (name, value) from ABS records

    def target_name(self, target):
        """Readable name of a fix target: the symbol name, or `MODULE label n`."""
        if target & bof.LOCAL_LABEL_FLAG:
            return '%s label %d' % (self.name, target & ~bof.LOCAL_LABEL_FLAG & 0xFFFF)
        if target < len(self.symbols):
            return self.symbols[target]
        return '%s symbol %d' % (self.name, target)


class Definition:
    """A global: in `section` at `offset`, or absolute with `value` (ABS record or linker)."""

    def __init__(self, name, module=None, section=None, offset=0, value=None):
        self.name = name
        self.module = module        # None for a linker-defined symbol
        self.section = section
        self.offset = offset
        self.value = value

    def owner(self):
        return 'the linker' if self.module is None else 'module %s' % self.module.name


class Link:
    """The result of `link_layout`. `ok` is True when `errors` is empty."""

    def __init__(self, name, main_dir, lib_dir):
        self.name = name
        self.main_dir = main_dir
        self.lib_dir = lib_dir
        self.modules = []
        self.globals = {}           # name -> Definition
        self.addrs = {}             # ADDR kind -> (value, module name)
        self.entry = None
        self.main_section = None
        self.kept = []              # kept sections in layout order: placed SECTSTAT, then SECTABS
        self.dropped = []           # dropped sections, module/section order
        self.code = DEFAULT_CODE
        self.size = 0               # bytes of the appended image (SECTSTAT sections)
        self.end = DEFAULT_CODE     # address after the last placed byte
        self.symbols = {}           # name -> address of every resolved global
        self.errors = []
        self.incomplete = False     # a module is missing or unreadable: no mark/layout was done

    @property
    def ok(self):
        return not self.errors

    @property
    def placed(self):
        """The kept SECTSTAT sections in image order."""
        return [s for s in self.kept if not s.absolute]

    def error(self, message):
        self.errors.append(ERROR_PREFIX + message)

    def target_address(self, module, target):
        """Address of fix `target` of `module` after the layout, or None if unresolved."""
        if target & bof.LOCAL_LABEL_FLAG:
            hit = module.labels.get(target & ~bof.LOCAL_LABEL_FLAG & 0xFFFF)
            if hit is None or hit[0].address is None:
                return None
            return hit[0].address + hit[1]
        if target >= len(module.symbols):
            return None
        return self.symbols.get(module.symbols[target])


# ---------------------------------------------------------------------------------------
# Pass 1
# ---------------------------------------------------------------------------------------
def find_object(module, main_dir, lib_dir):
    """Path of `module`'s object: the main folder first, then the library folder; None if absent."""
    file_name = object_file_name(module)
    for folder in (main_dir, lib_dir):
        path = os.path.join(folder, file_name)
        if os.path.isfile(path):
            return path
    return None


def _add_ref(section, target):
    if target not in section.refs:
        section.refs.append(target)


def read_module(link, module, data):
    """Pass 1 for one object: fill `module` from its bytes. Errors go to `link`; returns False
    when the object can't be used at all."""
    try:
        records = bof.read_records(data)
    except bof.BofError as e:
        link.error('module %s: bad object %s: %s' % (module.name, module.path, e))
        return False
    module.name = records[0].fields['module']
    section = None
    chunk = None
    for r in records[1:]:
        f = r.fields
        tag = r.tag
        if tag in bof.FIX_SPAN:
            if tag in bof.FIX_OFFSET_ONLY:
                entries = [(o, chunk.data[o] << 8 | chunk.data[o + 1]) for o in f['offsets']]
            else:
                entries = f['entries']
            for offset, target in entries:
                chunk.fixes.append(Fix(tag, offset, target))
                _add_ref(section, target)
            continue
        chunk = None
        if tag == bof.TAG_EXTRN:
            module.symbols.append(f['name'])
        elif tag == bof.TAG_NEED:
            module.needs.append(f['name'])
        elif tag == bof.TAG_ADDR:
            module.addrs.append((f['kind'], f['value']))
        elif tag in (bof.TAG_SECTSTAT, bof.TAG_SECTABS):
            absolute = tag == bof.TAG_SECTABS
            section = Section(module, len(module.sections), f['name'], absolute,
                              f['address'] if absolute else None)
            module.sections.append(section)
        elif tag == bof.TAG_ABS:
            module.absolutes.append((f['name'], f['value']))
        elif tag in (bof.TAG_GLOBL, bof.TAG_LABEL, bof.TAG_CODE):
            if section is None:
                link.error('module %s: %s record at offset %d is outside a section'
                           % (module.name, r.name, r.offset))
                return False
            if tag == bof.TAG_GLOBL:
                section.globals.append((f['name'], section.size))
            elif tag == bof.TAG_LABEL:
                if f['n'] in module.labels:
                    link.error('module %s: local label %d is defined twice' % (module.name, f['n']))
                module.labels[f['n']] = (section, section.size)
            else:
                chunk = Chunk(section.size, f['bytes'])
                section.chunks.append(chunk)
                section.size += len(chunk.data)
    return True


def _read_modules(link, name):
    name = name.upper()
    queue = [(FIRST_MODULE, COMMAND_LINE), (name, COMMAND_LINE)]
    listed = {FIRST_MODULE.upper(), name.upper()}
    i = 0
    while i < len(queue):
        mod_name, needed_by = queue[i]
        i += 1
        path = find_object(mod_name, link.main_dir, link.lib_dir)
        if path is None:
            link.incomplete = True
            link.error('module %s not found (%s, needed by %s)'
                       % (mod_name, object_file_name(mod_name), needed_by))
            continue
        with open(path, 'rb') as fh:
            data = fh.read()
        module = Module(mod_name, path, needed_by)
        if not read_module(link, module, data):
            link.incomplete = True
            continue
        link.modules.append(module)
        for need in module.needs:
            if need.upper() not in listed:
                listed.add(need.upper())
                queue.append((need.upper(), 'module %s' % module.name))


def _collect_addrs(link):
    for module in link.modules:
        for kind, value in module.addrs:
            seen = link.addrs.get(kind)
            if seen is None:
                link.addrs[kind] = (value, module.name)
            elif seen[0] != value:
                link.error('conflicting %s: %04x in module %s, %04x in module %s'
                           % (bof.ADDR_KINDS[kind], seen[0], seen[1], value, module.name))


def _define(link, definition):
    name = definition.name
    seen = link.globals.get(name)
    if seen is not None:
        if seen.module is definition.module:
            link.error('duplicate symbol %s: defined twice in module %s' % (name, seen.module.name))
        else:
            link.error('duplicate symbol %s: defined by %s and %s'
                       % (name, seen.owner(), definition.owner()))
        return
    link.globals[name] = definition


def _collect_globals(link):
    for name in LINKER_SYMBOLS:
        link.globals[name] = Definition(name)
    for module in link.modules:
        for section in module.sections:
            for name, offset in section.globals:
                _define(link, Definition(name, module, section, offset))
        for name, value in module.absolutes:
            _define(link, Definition(name, module, value=value))


# ---------------------------------------------------------------------------------------
# Mark
# ---------------------------------------------------------------------------------------
def _target_section(link, module, target):
    """(section the target lives in or None, undefined-name or None)."""
    if target & bof.LOCAL_LABEL_FLAG:
        hit = module.labels.get(target & ~bof.LOCAL_LABEL_FLAG & 0xFFFF)
        if hit is None:
            return None, module.target_name(target)
        return hit[0], None
    if target >= len(module.symbols):
        return None, module.target_name(target)
    name = module.symbols[target]
    definition = link.globals.get(name)
    if definition is None:
        return None, name
    if name == HEAP_SYMBOL and definition.module is None and bof.ADDR_HEAP not in link.addrs:
        return None, name           # D12: no #heap, no __heap
    return definition.section, None


def _mark(link):
    sections = [s for m in link.modules for s in m.sections]
    roots = [s for s in sections if s.absolute]
    first = link.modules[0] if link.modules else None
    if first is not None and first.list_name == FIRST_MODULE:
        if first.sections:
            link.entry = first.sections[0]
            roots.insert(0, link.entry)
        else:
            link.error('module %s has no sections: there is no entry' % first.name)
    main = link.globals.get(MAIN_SYMBOL)
    if main is None:
        link.error('undefined symbol %s' % MAIN_SYMBOL)
    elif main.section is None:
        link.error('symbol %s of %s is not in a section' % (MAIN_SYMBOL, main.owner()))
    else:
        link.main_section = main.section
        roots.append(main.section)
    work = []
    for s in roots:
        if not s.kept:
            s.kept = True
            work.append(s)
    while work:
        section = work.pop()
        for target in section.refs:
            dest, _ = _target_section(link, section.module, target)
            if dest is not None and not dest.kept:
                dest.kept = True
                work.append(dest)
    reported = set()
    for section in sections:
        if not section.kept:
            continue
        for target in section.refs:
            _, undefined = _target_section(link, section.module, target)
            if undefined is not None and (undefined, section.module.name) not in reported:
                reported.add((undefined, section.module.name))
                link.error('undefined symbol %s (used by module %s)' % (undefined, section.module.name))


# ---------------------------------------------------------------------------------------
# Layout and size checks
# ---------------------------------------------------------------------------------------
def _layout(link):
    sections = [s for m in link.modules for s in m.sections]
    if bof.ADDR_CODE in link.addrs:
        link.code = link.addrs[bof.ADDR_CODE][0]
    order = []
    for first in (link.entry, link.main_section):
        if first is not None and first.kept and not first.absolute and first not in order:
            order.append(first)
    order += [s for s in sections if s.kept and not s.absolute and s not in order]
    address = link.code
    for s in order:
        s.address = address
        address += s.size
    link.size = address - link.code
    link.end = address
    link.kept = order + [s for s in sections if s.kept and s.absolute]
    link.dropped = [s for s in sections if not s.kept]
    for name, definition in link.globals.items():
        if definition.module is None:
            continue
        if definition.section is None:
            link.symbols[name] = definition.value
        elif definition.section.kept:
            link.symbols[name] = definition.section.address + definition.offset
    link.symbols[END_SYMBOL] = link.end
    if bof.ADDR_HEAP in link.addrs:
        link.symbols[HEAP_SYMBOL] = link.addrs[bof.ADDR_HEAP][0]


def _check(link):
    if link.size > MAX_IMAGE_SIZE:
        link.error('program too big: %d bytes, at most %d' % (link.size, MAX_IMAGE_SIZE))
    if link.end > 0x10000:
        link.error('image end %05x is beyond the address space' % link.end)
    for kind in (bof.ADDR_HEAP, bof.ADDR_CODELIMIT):
        if kind in link.addrs:
            limit = link.addrs[kind][0]
            if link.end >= limit:
                link.error('image end %04x reaches %s %04x' % (link.end, bof.ADDR_KINDS[kind], limit))
    spans = [(link.code, link.end, 'the program image')] if link.size else []
    spans += [(s.address, s.address + s.size, s.describe())
              for s in link.kept if s.absolute and s.size]
    for i, (a0, a1, what_a) in enumerate(spans):
        for b0, b1, what_b in spans[i + 1:]:
            if a0 < b1 and b0 < a1:
                link.error('%s (%04x-%04x) overlaps %s (%04x-%04x)'
                           % (what_a, a0, a1 - 1, what_b, b0, b1 - 1))


def link_layout(name, lib_dir=None):
    """Pass 1, mark, layout and size checks for main object `name` (a module name or a path,
    with or without `.o`). Returns a `Link`; `Link.errors` holds every error found."""
    if name.lower().endswith('.o'):
        name = name[:-2]
    main_dir = os.path.dirname(name) or '.'
    module = os.path.basename(name)
    link = Link(module, main_dir, lib_dir if lib_dir is not None else DEFAULT_LIB_DIR)
    _read_modules(link, module)
    if not link.modules:
        return link
    _collect_addrs(link)
    _collect_globals(link)
    if link.incomplete:
        return link                 # undefined symbols and sizes would only be noise
    _mark(link)
    _layout(link)
    _check(link)
    return link
