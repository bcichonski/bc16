import argparse
import os
import sys
import traceback
import parsy
from pathlib import Path
from bc81asmc_ast import *
from bc81asmc_grammar import program
from bc81asmc_listing import LineRecord, format_listing, format_map
from bc81asmc_pre import prepass
from bc81asmc_diag import Diagnostic, AssemblerError, format_diagnostics, parse_error_to_diagnostic
from bc81asmc_obj import compile_object, module_name
import bof

def read_input_file(fname):
    with open(fname, 'r', encoding='utf8') as file_handle:
        return file_handle.read()

class FirstPass:
    """What pass 1 found: label addresses and lines, `.def` lines, the position of every label reference
    (parallel to `context.labels`), the diagnostics so far, the `.assert` nodes, the `.org` line, and per
    AST line a `LineSpan` (the node, its byte range in `context.bytes` and its range in `context.labels`)."""

    def __init__(self):
        self.labeladdresses = {}
        self.labellines = {}
        self.deflines = {}
        self.refpos = []
        self.diagnostics = []
        self.asserts = []
        self.orgline = None
        self.spans = []


class LineSpan:
    def __init__(self, node, byte_start, byte_end, ref_start, ref_end):
        self.node = node
        self.byte_start = byte_start
        self.byte_end = byte_end
        self.ref_start = ref_start
        self.ref_end = ref_end


def first_pass(ast, verbose, context):
    """Pass 1: emit every line with `0xfa` placeholders for label references. Shared by the flat and
    the object mode (--obj)."""
    result = FirstPass()
    labeladdresses = result.labeladdresses
    labellines = result.labellines
    deflines = result.deflines
    refpos = result.refpos
    diagnostics = result.diagnostics
    asserts = result.asserts
    overflowed = False
    if verbose:
            print('1st pass')
    for line in ast:
        if verbose:
            print('0x{0:04x} {1:16s}: {2}'.format(context.curraddr, getattr(line, 'label', ''), line))
        lineno = getattr(line, 'lineno', 0)
        col = getattr(line, 'col', 0)
        if hasattr(line, 'label'):
            name = line.label
            namecol = getattr(line, 'label_col', None) or col
            if name in labellines:
                diagnostics.append(Diagnostic(lineno, namecol,
                    "duplicate label '{0}' (first defined at line {1})".format(name, labellines[name])))
            elif name in deflines:
                diagnostics.append(Diagnostic(lineno, namecol,
                    "duplicate symbol '{0}' (first defined at line {1})".format(name, deflines[name])))
            else:
                labellines[name] = lineno
                labeladdresses[name] = context.curraddr
        if isinstance(line, DEF):
            name = line.lbl
            namecol = getattr(name, 'col', 0) or col
            if name in deflines or name in labellines:
                first = deflines[name] if name in deflines else labellines[name]
                diagnostics.append(Diagnostic(lineno, namecol,
                    "duplicate symbol '{0}' (first defined at line {1})".format(name, first)))
            else:
                deflines[name] = lineno
        if isinstance(line, ASSERT):
            asserts.append(line)
        if isinstance(line, ORG):
            skip = False
            if result.orgline is not None:
                diagnostics.append(Diagnostic(lineno, col,
                    'duplicate .org (first .org at line {0}); use .org once, at the top'.format(result.orgline)))
                skip = True
            elif context.bytes or labellines:
                diagnostics.append(Diagnostic(lineno, col, '.org must come before any code or label'))
                skip = True
            if skip:
                result.spans.append(LineSpan(line, len(context.bytes), len(context.bytes),
                                             len(context.labels), len(context.labels)))
                continue
            result.orgline = lineno
        saved = (len(context.bytes), context.curraddr, context.currbyte, context.currhalf,
                 len(context.labels), context.startaddr)
        startaddr = context.curraddr
        noperrors = len(context.operand_errors)
        try:
            line.emit(context)
        except Exception as e:
            del context.bytes[saved[0]:]
            (_, context.curraddr, context.currbyte, context.currhalf, nlabels, _) = saved
            del context.labels[nlabels:]
            del context.operand_errors[noperrors:]
            text = getattr(line, 'source', None) or str(line)
            reason = 'operand not supported by this instruction' if isinstance(e, KeyError) else str(e)
            diagnostics.append(Diagnostic(lineno, col,
                "cannot encode '{0}': {1}".format(text, reason)))
            if verbose:
                traceback.print_exc()
        if len(context.operand_errors) > noperrors:
            # a defined name failed to resolve: the line emits nothing, the errors are reported at the end
            del context.bytes[saved[0]:]
            (_, context.curraddr, context.currbyte, context.currhalf, nlabels, _) = saved
            del context.labels[nlabels:]
            context.startaddr = saved[5]
        if lineno:
            context.line_records.append(LineRecord(lineno,
                context.curraddr if isinstance(line, ORG) else startaddr,
                context.curraddr, hasattr(line, 'label'), isinstance(line, ORG)))
        result.spans.append(LineSpan(line, saved[0], len(context.bytes), saved[4], len(context.labels)))
        for ref in context.labels[len(refpos):]:
            refpos.append((getattr(ref[1], 'line', 0) or lineno, getattr(ref[1], 'col', 0) or col))
        if context.curraddr > 0x10000 and not overflowed:
            overflowed = True
            diagnostics.append(Diagnostic(lineno, col, 'code exceeds the 64 KB address space (past 0xffff)'))
    return result


def patch_reference(context, addr, label, ltype, labeladdr, verbose):
    """Pass 2 for one reference: write the value of `labeladdr` at `addr` by kind (`hi`, `lo`, `lorel`
    7-bit, `rel15`). Returns the error message of a relative jump out of range, else None."""
    if ltype == 'hi':
        hiaddr = context.hi(labeladdr)
        #print('store hi({0})={1:02x} at 0x{2:04x}'.format(label, hiaddr, addr))
        context.emit_byte_at(addr, hiaddr)
    elif ltype == 'lo':
        loaddr = context.lo(labeladdr)
        #print('store lo({0})={1:02x} at 0x{2:04x}'.format(label, loaddr, addr))
        context.emit_byte_at(addr, loaddr)
    elif ltype == 'lorel':
        addrdiff = labeladdr - addr + 1
        if verbose:
            print('store rel({0})={1} at 0x{2:04x}'.format(label, addrdiff, addr))
        if(addrdiff < -0x7f or addrdiff > 0x7f):
            return "label ':{0}' too far away for relative 7bit jump ({1} bytes)".format(label, addrdiff)
        if(addrdiff < 0):
            addrdiff = (-addrdiff) | 0x80 
        context.emit_byte_at(addr, addrdiff)
    elif ltype == 'rel15':
        addrdiff = labeladdr - addr - 1
        if verbose:
            print('store rel15({0})={1} at 0x{2:04x}'.format(label, addrdiff, addr))
        if(addrdiff < -0x7fff or addrdiff > 0x7fff):
            return "label ':{0}' too far away for relative 15bit jump ({1} bytes)".format(label, addrdiff)
        if(addrdiff < 0):
            addrdiff = (-addrdiff) | 0x8000
        context.emit_byte_at(addr, addrdiff >> 8)
        context.emit_byte_at(addr + 1, addrdiff & 0xff)
    return None


ASSERT_COMPARE = {
    '=': lambda a, b: a == b, '!=': lambda a, b: a != b,
    '<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
    '>': lambda a, b: a > b, '>=': lambda a, b: a >= b }


def evaluate_asserts(asserts, context, labeladdresses, diagnostics):
    """Evaluate `.assert` lines after patching; a failed one or an undefined operand is a diagnostic."""
    compare = ASSERT_COMPARE
    for node in asserts:
        values = []
        for operand in (node.left, node.right):
            if isinstance(operand, NameRef):
                values.append(context.number(operand, 16))
                continue
            if isinstance(operand, int) or hasattr(operand, 'value'):
                values.append(operand.value)
                continue
            name = str(operand)[1:]
            value = context.defs.get(name)
            if value is None:
                value = labeladdresses.get(name)
            if value is None:
                diagnostics.append(Diagnostic(getattr(operand, 'line', 0) or node.lineno,
                    getattr(operand, 'col', 0) or node.col, "undefined label ':{0}'".format(name)))
            values.append(value)
        if None in values:
            continue
        if not compare[node.op](values[0], values[1]):
            diagnostics.append(Diagnostic(node.lineno, node.col,
                "assertion failed: {0} {1} {2} (0x{3:04x} {1} 0x{4:04x})".format(
                    node.left, node.op, node.right, values[0], values[1])))


def compile(ast, verbose, defines=None, link_names=None, link_occurrences=None):
    """Two-pass compile of a parsed program. `defines` (a DefineTable) and `link_names` come from the pre-pass."""
    context = CodeContext()
    context.define_table = defines
    context.link_names = list(link_names or [])
    context.link_occurrences = list(link_occurrences or [])
    first = first_pass(ast, verbose, context)
    labeladdresses = first.labeladdresses
    refpos = first.refpos
    diagnostics = first.diagnostics

    if verbose:
            print('2nd pass')

    reported = set()
    for labelref, (rline, rcol) in zip(context.labels, refpos):
        (addr,label,ltype) = labelref
        # print(f"{addr:04x} {label} {ltype}")
        defref = context.defs.get(label)
        if defref is not None:
            labeladdr = defref
        else:
            labeladdr = labeladdresses.get(label)
        if labeladdr is None:
            # a use that emits hi and lo (cal, .db, .mv) is still one use
            if (rline, rcol, label) not in reported:
                reported.add((rline, rcol, label))
                diagnostics.append(Diagnostic(rline, rcol, "undefined label ':{0}'".format(label)))
            continue
        message = patch_reference(context, addr, label, ltype, labeladdr, verbose)
        if message is not None:
            diagnostics.append(Diagnostic(rline, rcol, message))

    evaluate_asserts(first.asserts, context, labeladdresses, diagnostics)

    diagnostics.extend(context.operand_errors)
    if diagnostics:
        diagnostics.sort(key=lambda d: (d.line, d.column))
        raise AssemblerError(diagnostics)

    context.label_addresses = labeladdresses
    print('Code length: {0} labels: {1}'.format(len(context.bytes), len(labeladdresses)))
    
    return context

def assemble_text(text, path, verbose=False, obj=False):
    """Pre-pass, parse and compile `text` (read from `path`). Returns the CodeContext, with the non-fatal
    warnings in `context.warnings`. Raises AssemblerError (warnings included, in reading order) on any error.
    With `obj`, the program is assembled into a BOF v1 module named after the file (`--obj`, #115): the
    bytes are in `context.object_bytes`."""
    pre = prepass(text, path)
    if pre.errors:
        raise AssemblerError(pre.diagnostics)
    warnings = [d for d in pre.diagnostics if d.severity == 'warning']
    print('Parsing code')
    try:
        ast = program.parse(pre.text)
    except parsy.ParseError as error:
        raise AssemblerError(warnings + [parse_error_to_diagnostic(error, pre.text)])
    print('Generating code')
    try:
        if obj:
            context = compile_object(ast, verbose, module_name(path), pre.defines, pre.link_occurrences)
        else:
            context = compile(ast, verbose, pre.defines, pre.link_names, pre.link_occurrences)
    except AssemblerError as error:
        raise AssemblerError(warnings + error.diagnostics)
    if obj:
        context.warnings = warnings + context.warnings
    else:
        context.warnings = warnings
    return context

def save_output_file(fname, code):
    print('Saving output file {0}...'.format(fname))
    with open(fname, 'wb') as file_handle:
        return file_handle.write(code)
    
def get_preamble(short_fname, context):
    result = bytearray()
    codeaddr = context.startaddr
    codelen = len(context.bytes)
    print("Creating btap file from {0:04x} for {1:04x}".format(codeaddr, codelen))
    result.extend([ 0x00, 0xff, 0x00, 0xff, 0xbc, 0x05, 
        context.hi(codeaddr), context.lo(codeaddr), 
        context.hi(codelen), context.lo(codelen), 0x00 ])
    fname_bytes = [ord(x) for x in short_fname]
    while len(fname_bytes) < 13:
        fname_bytes.append(0x00)
    result.extend(fname_bytes)
    return result

def btapify(bytes):
    result = bytearray()
    for byte in bytes:
        #print('byte: {0}'.format(byte))
        bits = [  byte & 0b00000001, 
                 (byte & 0b00000010) >> 1,
                 (byte & 0b00000100) >> 2,
                 (byte & 0b00001000) >> 3,
                 (byte & 0b00010000) >> 4,
                 (byte & 0b00100000) >> 5,
                 (byte & 0b01000000) >> 6,
                 (byte & 0b10000000) >> 7 ]
        #print('bits: {0}'.format(bits))
        result.extend(bits)
    return result
    
def save_output_btap(fname, short_fname, context):
    print('Saving output file {0}...'.format(fname))
    preamble = get_preamble(short_fname, context)
    with open(fname, 'wb') as file_handle:
        file_handle.write(btapify(preamble))
        return file_handle.write(btapify(context.bytes))

def report_errors(diagnostics, source, args):
    '''Prints the diagnostics to stderr (plus the traceback with --verbose) and exits with 1.'''
    sys.stdout.flush()
    sys.stderr.write(format_diagnostics(diagnostics, source, args.infile))
    if args.verbose:
        traceback.print_exc()
    sys.exit(1)

def dump_object(fname):
    """`--dump`: print the records of a BOF v1 file to stdout. Returns the exit status (1 with one error
    line on stderr when the file can't be read or is not BOF v1)."""
    try:
        with open(fname, 'rb') as file_handle:
            data = file_handle.read()
    except OSError as error:
        sys.stderr.write('{0}: error: cannot read the file: {1}\n'.format(fname, error.strerror))
        return 1
    try:
        text = bof.dump(data)
    except bof.BofError as error:
        sys.stderr.write('{0}: error: at byte offset {1}: {2}\n'.format(fname, error.offset, error.message))
        return 1
    sys.stdout.write(text)
    return 0

def main():
    parser = argparse.ArgumentParser(description='bc81asmc - an assembler for bc8183 cpu v1.3 (240914)')
    parser.add_argument('infile', type=str,
        help='input file name')
    parser.add_argument('--verbose', action='store_true',
        help='Be more verbose')
    parser.add_argument('--btap', action='store_true',
        help='Use btap file format')
    parser.add_argument('--lst', metavar='FILE', type=str, default=None,
        help='Write a listing (address, bytes, source) to FILE')
    parser.add_argument('--map', metavar='FILE', type=str, default=None,
        help='Write a symbol map (labels and .def constants by value) to FILE')
    parser.add_argument('--obj', action='store_true',
        help='Write a BOF v1 object file FILE.o instead of the .btap')
    parser.add_argument('--dump', action='store_true',
        help='Print the records of the BOF v1 object file given as infile')
    args = parser.parse_args()
    if args.obj and (args.lst or args.map):
        parser.error('--obj cannot be combined with --lst or --map')
    if args.dump and (args.obj or args.lst or args.map):
        parser.error('--dump cannot be combined with --obj, --lst or --map')
    if args.dump:
        sys.exit(dump_object(args.infile))
    print('Reading input file {}'.format(args.infile))
    input = read_input_file(args.infile)
    try:
        output = assemble_text(input, args.infile, args.verbose, obj=args.obj)
    except AssemblerError as error:
        report_errors(error.diagnostics, input, args)
    if output.warnings:
        sys.stderr.write(format_diagnostics(output.warnings, input, args.infile))

    if args.obj:
        save_output_file(Path(args.infile).with_suffix('.o'), output.object_bytes)
        print('Done!')
        return
    
    outfile = Path(args.infile).with_suffix(".btap")
    _, short_fname = os.path.split(Path(args.infile).with_suffix(""))
    save_output_btap(outfile, short_fname, output)
    if args.lst:
        save_output_file(args.lst, format_listing(input, output).encode('utf8'))
    if args.map:
        save_output_file(args.map, format_map(os.path.basename(args.infile), output).encode('utf8'))

    print('Done!')

if __name__ == "__main__":
    main()
