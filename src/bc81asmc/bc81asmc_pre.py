"""The assembler pre-pass: `#include`, `#define` and `#link` lines (#114).

The pre-pass reads the main source line by line. A line whose first non-blank text is `#include`, `#define`
or `#link` (followed by a blank or the end of the line) is a directive; it is replaced by a bare `;` comment line in the
text handed to the parser, so every line number, listing row and diagnostic position of the main file stays the
same and a directive line has no address and no bytes. Every other line is passed on unchanged.

`#include NAME` reads a B header (blank lines, `//` comments, `#define`, `#include`, `#link` and one-line
prototypes, which are skipped); the file is looked up in the directory of the main source at every nesting level.
Headers never contribute code or lines to the parser text.

Define table API (for the resolution of names in operands, T2):

    result = prepass(text, path)
    result.text            the parser text (main file lines, directives blanked)
    result.defines         a DefineTable
    result.link_names      the #link names, first-seen order, no duplicates
    result.link_occurrences every #link in reading order, repeats included: LinkOccurrence(name, main-file line)
    result.diagnostics     errors and warnings, in reading order (Diagnostic.file/.text name a header)
    result.errors          True when there is any error (then the run must stop before parsing)

    define = result.defines.lookup('NAME', lineno)

`lookup(name, lineno)` returns the `Define` in effect on main-file line `lineno` (the last `#define NAME` taken
in reading order that takes effect at or before that line), or None. A define takes effect from the line after
its directive; every define of a header takes effect from the line after the `#include` line in the main file.
A `Define` has `name`, `value` (text, as written, without the trailing comment), `effective_line`, and the
`file`/`line` where it was written. Values are not checked here; the user of a name checks it.
"""
import os
import re
import sys
from collections import namedtuple

from bc81asmc_diag import Diagnostic

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.append(_SRC)

import bc8183_isa as isa

IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
DIRECTIVE = re.compile(r'([ \t]*)#(include|define|link)(?=[ \t]|$)')
PROTOTYPE = re.compile(r'(?:byte|word)[ \t]+[A-Za-z_][A-Za-z0-9_]*[ \t]*\([^()]*\)[ \t]*(?:\*\*\*)?[ \t]*;?[ \t]*(?://.*)?')
RESERVED = frozenset(isa.REGISTER_NAMES) | frozenset(isa.PAIR_NAMES)


# one `#link` line in reading order; `line` is the main-file line it belongs to (a header's #link: the #include line)
LinkOccurrence = namedtuple('LinkOccurrence', 'name line')


class Define:
    def __init__(self, name, value, effective_line, file, line):
        self.name = name
        self.value = value
        self.effective_line = effective_line
        self.file = file
        self.line = line

    def __repr__(self):
        return 'Define({0!r}, {1!r}, from line {2})'.format(self.name, self.value, self.effective_line)


class DefineTable:
    """All defines in reading order; `lookup` answers 'the define in effect at main-file line L'."""

    def __init__(self):
        self._by_name = {}

    def add(self, define):
        self._by_name.setdefault(define.name, []).append(define)

    def lookup(self, name, lineno):
        for define in reversed(self._by_name.get(name, ())):
            if define.effective_line <= lineno:
                return define
        return None

    def current(self, name):
        """The latest define of `name` in reading order (what the pre-pass has seen so far)."""
        entries = self._by_name.get(name)
        return entries[-1] if entries else None

    def names(self):
        return list(self._by_name)

    def __len__(self):
        return sum(len(v) for v in self._by_name.values())

    def __bool__(self):
        return bool(self._by_name)


class PrepassResult:
    def __init__(self):
        self.text = ''
        self.defines = DefineTable()
        self.link_names = []
        self.link_occurrences = []
        self.diagnostics = []

    @property
    def errors(self):
        return any(d.severity == 'error' for d in self.diagnostics)


def strip_comment(text, marker):
    """`text` without a trailing `marker` comment; a char literal ('x') may hold the marker."""
    pos = 0
    while pos < len(text):
        if text[pos] == "'" and pos + 2 < len(text) and text[pos + 2] == "'":
            pos += 3
            continue
        if text.startswith(marker, pos):
            return text[:pos]
        pos += 1
    return text


class _Prepass:
    def __init__(self, main_text, main_path):
        self.main_text = main_text
        self.main_path = main_path
        self.base_dir = os.path.dirname(main_path)
        self.result = PrepassResult()

    def diag(self, line, column, message, file=None, text=None, severity='error'):
        self.result.diagnostics.append(Diagnostic(line, column, message, severity, file, text))

    def run(self):
        lines = self.main_text.split('\n')
        out = []
        chain = [os.path.realpath(self.main_path)]
        for index, line in enumerate(lines):
            lineno = index + 1
            match = DIRECTIVE.match(line)
            if match is None:
                out.append(line)
                continue
            out.append(';')
            self.directive(match, line, lineno, ';', None, None, lineno, chain)
        self.result.text = '\n'.join(out)
        return self.result

    def directive(self, match, line, line_no, marker, file, text, main_line, chain):
        """Handles one directive line of the main file (file None) or of a header."""
        kind = match.group(2)
        column = match.start(2)  # 1-based column of the '#'
        body = strip_comment(line[match.end(2):], marker)
        where = dict(file=file, text=text)
        if kind == 'define':
            parts = body.strip().split(None, 1)
            if len(parts) < 2 or IDENTIFIER.fullmatch(parts[0]) is None:
                self.diag(line_no, column, 'malformed #define (expected: #define NAME value)', **where)
                return
            name, value = parts[0], parts[1].strip()
            namecol = line.index(name, match.end(2)) + 1
            if name in RESERVED:
                self.diag(line_no, namecol, "'{0}' is a register name and cannot be #defined".format(name), **where)
                return
            old = self.result.defines.current(name)
            if old is not None and old.value != value:
                self.diag(line_no, namecol, "'{0}' redefined: '{1}' replaces '{2}'".format(name, value, old.value),
                          severity='warning', **where)
            self.result.defines.add(Define(name, value, main_line + 1, file or self.main_path, line_no))
        elif kind == 'link':
            parts = body.split()
            if len(parts) != 1 or IDENTIFIER.fullmatch(parts[0]) is None:
                self.diag(line_no, column, 'malformed #link (expected: #link NAME)', **where)
                return
            self.result.link_occurrences.append(LinkOccurrence(parts[0], main_line))
            if parts[0] not in self.result.link_names:
                self.result.link_names.append(parts[0])
        else:
            parts = body.split()
            if len(parts) != 1:
                self.diag(line_no, column, 'malformed #include (expected: #include NAME)', **where)
                return
            namecol = line.index(parts[0], match.end(2)) + 1
            self.include(parts[0], line_no, namecol, file, text, main_line, chain)

    def include(self, name, line_no, column, file, text, main_line, chain):
        path = os.path.join(self.base_dir, name)
        real = os.path.realpath(path)
        where = dict(file=file, text=text)
        if real in chain:
            self.diag(line_no, column, "include cycle: '{0}' includes itself".format(name), **where)
            return
        try:
            with open(path, 'r', encoding='utf8') as handle:
                content = handle.read()
        except (OSError, UnicodeDecodeError) as error:
            reason = error.strerror if isinstance(error, OSError) and error.strerror else str(error)
            self.diag(line_no, column, "cannot read include file '{0}': {1}".format(name, reason), **where)
            return
        self.header(path, content, main_line, chain + [real])

    def header(self, path, content, main_line, chain):
        for index, line in enumerate(content.split('\n')):
            if line.endswith('\r'):
                line = line[:-1]
            line_no = index + 1
            stripped = line.strip()
            if not stripped or stripped.startswith('//'):
                continue
            match = DIRECTIVE.match(line)
            if match is not None:
                self.directive(match, line, line_no, '//', path, content, main_line, chain)
            elif PROTOTYPE.fullmatch(stripped) is None:
                self.diag(line_no, len(line) - len(line.lstrip()) + 1,
                          'unexpected line in a header (only #define, #include, #link and prototypes are allowed)',
                          file=path, text=content)


def prepass(text, path):
    """Runs the pre-pass over the main source `text` read from `path`; returns a PrepassResult."""
    return _Prepass(text, path).run()
