"""Diagnostics for the assembler: records, the error exception, the formatter and
the conversion of a parsy ParseError.

Lines and columns are 1-based (a tab counts as one column). Reusable by any check
that wants to report `file:line:col: error: message` (for example `.assert`).
"""
import bisect
import re
from dataclasses import dataclass

_NEWLINE = re.compile(r'\r\n|\r|\n')
_cache = {'stream': None, 'starts': None}


def _line_starts(text):
    """0-based offsets at which each line starts (cached for the last text)."""
    if _cache['stream'] is not text:
        _cache['starts'] = [0] + [m.end() for m in _NEWLINE.finditer(text)]
        _cache['stream'] = text
    return _cache['starts']


def line_col_at(text, index):
    """1-based (line, column) of a 0-based character index of `text`."""
    starts = _line_starts(text)
    row = bisect.bisect_right(starts, index) - 1
    return row + 1, index - starts[row] + 1


def split_lines(text):
    """The lines of `text` without their terminators (`\\r\\n`, `\\r`, `\\n`)."""
    return _NEWLINE.split(text)


@dataclass
class Diagnostic:
    line: int
    column: int
    message: str
    severity: str = 'error'


class AssemblerError(Exception):
    """Carries every diagnostic of an assembler run; str() lists the messages."""

    def __init__(self, diagnostics):
        self.diagnostics = list(diagnostics)
        super().__init__("\n".join(d.message for d in self.diagnostics))


def format_diagnostic(diagnostic, source, filename):
    """The three-line block: header, verbatim source line, caret line (no trailing newline)."""
    lines = split_lines(source)
    text = lines[diagnostic.line - 1] if 1 <= diagnostic.line <= len(lines) else ''
    prefix = text[:max(diagnostic.column - 1, 0)]
    prefix = prefix.ljust(max(diagnostic.column - 1, 0))
    caret = ''.join(c if c == '\t' else ' ' for c in prefix) + '^'
    header = '{0}:{1}:{2}: {3}: {4}'.format(
        filename, diagnostic.line, diagnostic.column, diagnostic.severity, diagnostic.message)
    return "\n".join((header, text, caret))


def format_diagnostics(diagnostics, source, filename):
    """All blocks, each terminated by a newline."""
    return ''.join(format_diagnostic(d, source, filename) + "\n" for d in diagnostics)


_TOKEN = re.compile(r'[^\s,;]+|[,;]')


def parse_error_to_diagnostic(error, source=None):
    """Converts a parsy ParseError into an `error` Diagnostic (see `syntax error:` rule)."""
    if source is None:
        source = error.stream
    index = error.index
    line, column = line_col_at(source, index)
    expected = sorted(str(e) if not isinstance(e, str) else e for e in error.expected)
    # parsy keeps `string()` expectations as quoted reprs and `.desc()` ones as plain text
    if 0 < len(expected) <= 5:
        if len(expected) == 1:
            what = 'expected ' + expected[0]
        else:
            what = 'expected ' + ', '.join(expected[:-1]) + ' or ' + expected[-1]
        message = 'syntax error: ' + what
    else:
        pos = index
        while pos < len(source) and source[pos] in ' \t':
            pos += 1
        if pos >= len(source):
            found = 'end of file'
        elif source[pos] in '\r\n':
            found = 'end of line'
        else:
            found = "'" + _TOKEN.match(source, pos).group(0) + "'"
        message = 'syntax error: unexpected ' + found
    return Diagnostic(line, column, message)
