"""Output channels of the compiler (module-level state, set once by bc.main).

trace   -> stdout, only with --verbose (the text the compiler always used to print)
info    -> stdout, always (the one-line summary)
error / warning -> stderr, `<file>: error: <message>` (`<file>:<line>:<col>: error: ...`
                   once a location is given), same header as the assembler.
"""
import sys

_state = {'verbose': False, 'source': 'bc'}


def configure(verbose=False, source=None):
    _state['verbose'] = bool(verbose)
    if source is not None:
        _state['source'] = str(source)


def set_verbose(verbose):
    _state['verbose'] = bool(verbose)


def is_verbose():
    return _state['verbose']


def trace(message):
    if _state['verbose']:
        print(message)


def info(message):
    print(message)


def _diagnostic(severity, message, line=None, col=None):
    where = _state['source']
    if line is not None:
        where = '{0}:{1}:{2}'.format(where, line, col if col is not None else 1)
    print('{0}: {1}: {2}'.format(where, severity, message), file=sys.stderr)


def error(message, line=None, col=None):
    _diagnostic('error', message, line, col)


def warning(message, line=None, col=None):
    _diagnostic('warning', message, line, col)


def error_context(source_line, column):
    """Prints the offending source line and a caret under the 1-based column, to stderr."""
    prefix = source_line[:max(column - 1, 0)].ljust(max(column - 1, 0))
    caret = ''.join(c if c == '\t' else ' ' for c in prefix) + '^'
    print(source_line, file=sys.stderr)
    print(caret, file=sys.stderr)


def stderr(message):
    print(message, file=sys.stderr)
