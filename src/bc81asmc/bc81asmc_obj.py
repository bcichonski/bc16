"""Object mode of the assembler (`--obj`, #115): one parsed program -> one BOF v1 module (`src/bof.py`).

Pass 1 is the flat one (`first_pass` in bc81asmc.py), so every byte, placeholder and existing diagnostic
is the same as without `--obj`. Then:

- every name gets its class: global label or exported constant (`.global`), external (`.extern`), local
  constant (`.def`, resolved in place like flat mode), or local label (numbered 0, 1, 2... per module in
  order of first appearance, reference or definition);
- the object-mode rules are checked (declarations before use, `.org`/`.sect` placement, sections);
- every label reference becomes a fix entry (cal/.db :x -> ABS16, jrx/clr -> REL15, hi( ) -> HI8,
  lo( )/jmp -> LO8, jmr -> REL7, .mv -> HILO) and the records are written line by line in the order of
  the plan's section 2.4: NEED, section, GLOBL/LABEL, ABS, EXTRN, CODE.

The module does no I/O; `main()` in bc81asmc.py writes the file.
"""
import os

import bof
from bc81asmc_ast import (ORG, DEF, ASSERT, GLOBAL, EXTERN, SECT, NameRef, PAIR_ABS16, PAIR_HILO)
from bc81asmc_diag import Diagnostic, AssemblerError

# the 2-byte reference kinds and the 1-byte ones, as recorded by CodeContext
_KIND_FIX = {'hi': bof.FIX_HI8, 'lo': bof.FIX_LO8, 'lorel': bof.FIX_REL7, 'rel15': bof.FIX_REL15}
_PAIR_FIX = {PAIR_ABS16: bof.FIX_ABS16, PAIR_HILO: bof.FIX_HILO}


def module_name(path):
    """The header's module name: the source stem in upper case (`hello.basm` -> `HELLO`)."""
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem.upper()


def _pos(name, node):
    return (getattr(name, 'line', 0) or getattr(node, 'lineno', 0),
            getattr(name, 'col', 0) or getattr(node, 'col', 0))


class _Ref:
    """One use of a name on a line: a 1-byte reference or a hi/lo pair forming one fix."""

    def __init__(self, index, addr, name, kind, pair, line, col):
        self.index = index      # first index in context.labels
        self.addr = addr
        self.name = name
        self.kind = kind        # a CodeContext kind ('hi', 'lo', 'lorel', 'rel15')
        self.pair = pair        # PAIR_ABS16, PAIR_HILO or None
        self.line = line
        self.col = col


def _line_refs(context, span, refpos):
    """The uses of one line in reference order, a hi/lo pair of one use joined into one _Ref."""
    refs = []
    i = span.ref_start
    while i < span.ref_end:
        addr, name, kind = context.labels[i]
        line, col = refpos[i]
        pair = getattr(name, 'pair', None)
        if kind == 'hi' and pair is not None and i + 1 < span.ref_end and context.labels[i + 1][1] is name:
            refs.append(_Ref(i, addr, name, kind, pair, line, col))
            i += 2
            continue
        refs.append(_Ref(i, addr, name, kind, None, line, col))
        i += 1
    return refs


def compile_object(ast, verbose, module, defines=None, link_occurrences=None):
    """Assemble a parsed program into a BOF v1 module named `module`. Returns the CodeContext with the
    object bytes in `context.object_bytes` and the object-mode warnings in `context.warnings`.
    Raises AssemblerError (warnings included) on any error."""
    from bc81asmc import first_pass, patch_reference, evaluate_asserts
    from bc81asmc_ast import CodeContext

    context = CodeContext()
    context.define_table = defines
    context.link_occurrences = list(link_occurrences or [])
    context.link_names = []
    for occurrence in context.link_occurrences:
        if occurrence.name not in context.link_names:
            context.link_names.append(occurrence.name)
    first = first_pass(ast, verbose, context)
    diagnostics = first.diagnostics
    warnings = []
    labeladdresses = first.labeladdresses
    labellines = first.labellines
    deflines = first.deflines
    spans = first.spans
    lines_refs = [_line_refs(context, span, first.refpos) for span in spans]

    # -- declarations, sections and .org --------------------------------------------------------
    globals_ = {}           # name -> line of the first .global
    externs = {}            # name -> line of the first .extern
    sections = {}           # section name -> line it starts
    first_seen = {}         # name -> line of its first use or definition
    defs_seen = set()
    directive_line = None   # first .sect/.global/.extern line
    org_ok = False
    for span, refs in zip(spans, lines_refs):
        node = span.node
        lineno = getattr(node, 'lineno', 0)
        col = getattr(node, 'col', 0)
        if isinstance(node, ORG) and first.orgline == lineno:
            if directive_line is not None:
                diagnostics.append(Diagnostic(lineno, col,
                    '.org must come before .sect, .global and .extern with --obj (first one at line {0})'
                    .format(directive_line)))
            else:
                org_ok = True
        if isinstance(node, (GLOBAL, EXTERN, SECT)) and directive_line is None:
            directive_line = lineno
        if hasattr(node, 'label'):
            first_seen.setdefault(node.label, lineno)
        if isinstance(node, DEF):
            first_seen.setdefault(node.lbl, lineno)
            defs_seen.add(node.lbl)
        for ref in refs:
            if ref.name in deflines and ref.name not in defs_seen:
                diagnostics.append(Diagnostic(ref.line, ref.col,
                    "'{0}' is used before its .def (line {1}); with --obj a .def must come first"
                    .format(ref.name, deflines[ref.name])))
            first_seen.setdefault(ref.name, ref.line)
        if isinstance(node, (GLOBAL, EXTERN)):
            name = node.name
            nline, ncol = _pos(name, node)
            this, other = (globals_, externs) if isinstance(node, GLOBAL) else (externs, globals_)
            what = '.global' if isinstance(node, GLOBAL) else '.extern'
            if name in other:
                diagnostics.append(Diagnostic(nline, ncol,
                    "'{0}' is declared both .global and .extern (other declaration at line {1})"
                    .format(name, other[name])))
                continue    # the name keeps its first class: one error, not two
            if name in first_seen and name not in this:
                diagnostics.append(Diagnostic(nline, ncol,
                    "'{0} {1}' must come before the first use or definition of '{1}' (line {2})"
                    .format(what, name, first_seen[name])))
            this.setdefault(name, lineno)
    for span in spans:
        node = span.node
        if not isinstance(node, SECT):
            continue
        lineno = getattr(node, 'lineno', 0)
        nline, ncol = _pos(node.name, node)
        if org_ok:
            diagnostics.append(Diagnostic(getattr(node, 'lineno', 0), getattr(node, 'col', 0),
                ".sect is not allowed in an .org file with --obj (the file is one absolute section)"))
        elif node.name in sections:
            diagnostics.append(Diagnostic(nline, ncol,
                "duplicate section '{0}' (first started at line {1})".format(node.name, sections[node.name])))
        else:
            sections[node.name] = lineno
    for name, line in globals_.items():
        if name not in labellines and name not in deflines:
            node = next(s.node for s in spans if isinstance(s.node, GLOBAL) and s.node.name == name)
            nline, ncol = _pos(node.name, node)
            diagnostics.append(Diagnostic(nline, ncol, "'.global {0}' is never defined".format(name)))
    for span in spans:
        node = span.node
        lineno = getattr(node, 'lineno', 0)
        names = []
        if hasattr(node, 'label'):
            names.append((node.label, _pos(node.label, node) if getattr(node, 'label_col', None) is None
                          else (lineno, node.label_col)))
        if isinstance(node, DEF):
            names.append((node.lbl, _pos(node.lbl, node)))
        for name, (nline, ncol) in names:
            if name in externs:
                diagnostics.append(Diagnostic(nline, ncol,
                    "'{0}' is declared .extern (line {1}) and must not be defined in this module"
                    .format(name, externs[name])))

    def is_symbol(name):
        return name in globals_ or name in externs

    def is_local_def(name):
        return name in context.defs and not is_symbol(name)

    # -- pass 2: local .defs in place, undefined references -----------------------------------
    reported = set()
    for span, refs in zip(spans, lines_refs):
        for ref in refs:
            name = ref.name
            if is_local_def(name):
                indexes = [ref.index, ref.index + 1] if ref.pair else [ref.index]
                for i in indexes:
                    addr, label, ltype = context.labels[i]
                    if ltype in ('lorel', 'rel15') and not org_ok:
                        diagnostics.append(Diagnostic(ref.line, ref.col,
                            "relative jump to the constant ':{0}' needs an .org file with --obj".format(name)))
                        continue
                    message = patch_reference(context, addr, label, ltype, context.defs[name], verbose)
                    if message is not None:
                        diagnostics.append(Diagnostic(ref.line, ref.col, message))
            elif name not in labeladdresses and name not in externs and name not in context.defs:
                if (ref.line, ref.col, name) not in reported:
                    reported.add((ref.line, ref.col, name))
                    diagnostics.append(Diagnostic(ref.line, ref.col, "undefined label ':{0}'".format(name)))

    # -- .assert: evaluated in an .org file, skipped with a warning when it names a relocatable label --
    evaluate = []
    for node in first.asserts:
        relocatable = None
        for operand in (node.left, node.right):
            if isinstance(operand, NameRef) or not isinstance(operand, str) or not operand.startswith(':'):
                continue
            name = operand[1:]
            if name in context.defs:
                continue
            if name in externs or (name in labeladdresses and not org_ok):
                relocatable = operand
                break
        if relocatable is None:
            evaluate.append(node)
        else:
            line, col = _pos(relocatable, node)
            warnings.append(Diagnostic(line, col,
                ".assert not checked with --obj: '{0}' is relocatable".format(relocatable), 'warning'))
    evaluate_asserts(evaluate, context, labeladdresses, diagnostics)

    diagnostics.extend(context.operand_errors)
    if diagnostics:
        diagnostics = warnings + diagnostics
        diagnostics.sort(key=lambda d: (d.line, d.column))
        raise AssemblerError(diagnostics)

    # -- local label numbers: first appearance, reference or definition ----------------------
    local_numbers = {}
    for span, refs in zip(spans, lines_refs):
        node = span.node
        if hasattr(node, 'label') and not is_symbol(node.label):
            local_numbers.setdefault(node.label, len(local_numbers))
        for ref in refs:
            if not is_symbol(ref.name) and not is_local_def(ref.name):
                local_numbers.setdefault(ref.name, len(local_numbers))

    # -- records ---------------------------------------------------------------------------------
    try:
        writer = bof.BofWriter(module)
        needs = sorted(context.link_occurrences, key=lambda o: o.line)
        need_index = 0
        in_section = False
        for span, refs in zip(spans, lines_refs):
            node = span.node
            lineno = getattr(node, 'lineno', 0)
            while need_index < len(needs) and needs[need_index].line <= lineno:
                writer.need(needs[need_index].name.upper())
                need_index += 1
            if isinstance(node, SECT):
                writer.sectstat(node.name)
                in_section = True
            has_label = hasattr(node, 'label')
            has_bytes = span.byte_end > span.byte_start
            if (has_label or has_bytes) and not in_section:
                if org_ok:
                    writer.sectabs(context.startaddr, module)
                else:
                    writer.sectstat(module)
                in_section = True
            if has_label:
                if is_symbol(node.label):
                    writer.globl(node.label)
                else:
                    writer.label(local_numbers[node.label])
            if isinstance(node, DEF) and node.lbl in globals_:
                writer.abs_symbol(context.defs[node.lbl], node.lbl)
            targets = {}
            for ref in refs:
                if is_symbol(ref.name):
                    targets[ref.name] = writer.extrn(ref.name)
                elif not is_local_def(ref.name):
                    targets[ref.name] = bof.local_label_target(local_numbers[ref.name])
            if not has_bytes:
                continue
            data = bytearray(context.bytes[span.byte_start:span.byte_end])
            fixes = []
            for ref in refs:
                if ref.name not in targets:
                    continue
                target = targets[ref.name]
                offset = ref.addr - context.startaddr - span.byte_start
                kind = _PAIR_FIX[ref.pair] if ref.pair else _KIND_FIX[ref.kind]
                if kind in bof.FIX_OFFSET_ONLY:
                    data[offset] = (target >> 8) & 0xff
                    data[offset + 1] = target & 0xff
                    fixes.append((kind, offset))
                else:
                    data[offset] = 0
                    if kind == bof.FIX_HILO:
                        data[offset + 2] = 0
                    fixes.append((kind, offset, target))
            writer.code(bytes(data), fixes)
        while need_index < len(needs):
            writer.need(needs[need_index].name.upper())
            need_index += 1
        if org_ok and not in_section:
            writer.sectabs(context.startaddr, module)
        writer.end()
        context.object_bytes = writer.getvalue()
    except bof.BofError as error:
        raise AssemblerError(warnings + [Diagnostic(1, 1, 'cannot write the object file: {0}'.format(error.message))])

    context.label_addresses = labeladdresses
    context.warnings = warnings
    print('Code length: {0} labels: {1} sections: {2}'.format(
        len(context.bytes), len(labeladdresses), len(sections) + (1 if org_ok else 0)))
    return context
