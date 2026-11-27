"""Label scanning of assembly text (shared by bc_ast and the runtime loader bc_stdlib)."""
import re

LABEL_DEF = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*):')
DEF_DIRECTIVE = re.compile(r'^\s*\.def\s+([A-Za-z_][A-Za-z0-9_]*)')
LABEL_REF = re.compile(r':([A-Za-z_][A-Za-z0-9_]*)')

def strip_asm_comment(line):
    '''One assembly line without its `;` comment; a `;` inside a quoted literal is not a comment.'''
    quote = None
    for i, c in enumerate(line):
        if quote is not None:
            if c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c == ';':
            return line[:i]
    return line

def asm_labels(text):
    '''(defined labels, referenced labels) of assembly text, comments excluded.

    A definition is `name:` at the start of a line (after whitespace; an instruction may follow)
    or `.def name, ...`; a reference is any `:name` token. Over-approximating references is safe.'''
    defined = set()
    referenced = set()
    for line in text.splitlines():
        line = strip_asm_comment(line)
        match = LABEL_DEF.match(line) or DEF_DIRECTIVE.match(line)
        if match is not None:
            defined.add(match.group(1))
        referenced.update(LABEL_REF.findall(line))
    return defined, referenced
