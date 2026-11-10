import argparse
import os
import sys
import traceback
import parsy
from pathlib import Path
from bc81asmc_ast import *
from bc81asmc_grammar import program
from bc81asmc_diag import Diagnostic, AssemblerError, format_diagnostics, parse_error_to_diagnostic

def read_input_file(fname):
    with open(fname, 'r', encoding='utf8') as file_handle:
        return file_handle.read()

def compile(ast, verbose):
    context = CodeContext()
    labeladdresses = {}
    labellines = {}
    deflines = {}
    refpos = []
    diagnostics = []
    asserts = []
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
        saved = (len(context.bytes), context.curraddr, context.currbyte, context.currhalf,
                 len(context.labels), context.startaddr)
        try:
            line.emit(context)
        except Exception as e:
            del context.bytes[saved[0]:]
            (_, context.curraddr, context.currbyte, context.currhalf, nlabels, _) = saved
            del context.labels[nlabels:]
            text = getattr(line, 'source', None) or str(line)
            reason = 'operand not supported by this instruction' if isinstance(e, KeyError) else str(e)
            diagnostics.append(Diagnostic(lineno, col,
                "cannot encode '{0}': {1}".format(text, reason)))
            if verbose:
                traceback.print_exc()
        for ref in context.labels[len(refpos):]:
            refpos.append((getattr(ref[1], 'line', 0) or lineno, getattr(ref[1], 'col', 0) or col))
        if context.curraddr > 0x10000 and not overflowed:
            overflowed = True
            diagnostics.append(Diagnostic(lineno, col, 'code exceeds the 64 KB address space (past 0xffff)'))

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
                diagnostics.append(Diagnostic(rline, rcol,
                    "label ':{0}' too far away for relative 7bit jump ({1} bytes)".format(label, addrdiff)))
                continue
            if(addrdiff < 0):
                addrdiff = (-addrdiff) | 0x80 
            context.emit_byte_at(addr, addrdiff)
        elif ltype == 'rel15':
            addrdiff = labeladdr - addr - 1
            if verbose:
                print('store rel15({0})={1} at 0x{2:04x}'.format(label, addrdiff, addr))
            if(addrdiff < -0x7fff or addrdiff > 0x7fff):
                diagnostics.append(Diagnostic(rline, rcol,
                    "label ':{0}' too far away for relative 15bit jump ({1} bytes)".format(label, addrdiff)))
                continue
            if(addrdiff < 0):
                addrdiff = (-addrdiff) | 0x8000
            context.emit_byte_at(addr, addrdiff >> 8)
            context.emit_byte_at(addr + 1, addrdiff & 0xff)     

    compare = {
        '=': lambda a, b: a == b, '!=': lambda a, b: a != b,
        '<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
        '>': lambda a, b: a > b, '>=': lambda a, b: a >= b }
    for node in asserts:
        values = []
        for operand in (node.left, node.right):
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

    if diagnostics:
        diagnostics.sort(key=lambda d: (d.line, d.column))
        raise AssemblerError(diagnostics)

    print('Code length: {0} labels: {1}'.format(len(context.bytes), len(labeladdresses)))
    
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

def main():
    parser = argparse.ArgumentParser(description='bc81asmc - an assembler for bc8183 cpu v1.3 (240914)')
    parser.add_argument('infile', type=str,
        help='input file name')
    parser.add_argument('--verbose', action='store_true',
        help='Be more verbose')
    parser.add_argument('--btap', action='store_true',
        help='Use btap file format')
    args = parser.parse_args()
    print('Reading input file {}'.format(args.infile))
    input = read_input_file(args.infile)
    print('Parsing code')
    try:
        ast = program.parse(input)
    except parsy.ParseError as error:
        report_errors([parse_error_to_diagnostic(error, input)], input, args)
    print('Generating code')
    try:
        output = compile(ast, args.verbose)
    except AssemblerError as error:
        report_errors(error.diagnostics, input, args)
    
    outfile = Path(args.infile).with_suffix(".btap")
    _, short_fname = os.path.split(Path(args.infile).with_suffix(""))
    save_output_btap(outfile, short_fname, output)

    print('Done!')

if __name__ == "__main__":
    main()
