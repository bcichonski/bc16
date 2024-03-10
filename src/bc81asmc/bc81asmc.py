import argparse
import os
from pathlib import Path
from bc81asmc_ast import *
from bc81asmc_grammar import program

def read_input_file(fname):
    with open(fname, 'r', encoding='utf8') as file_handle:
        return file_handle.read()

def compile(ast, verbose):
    context = CodeContext()
    labeladdresses = {}
    if verbose:
            print('1st pass')
    for line in ast:
        if verbose:
            print('0x{0:04x} {1:16s}: {2}'.format(context.curraddr, getattr(line, 'label', ''), line))
        if(hasattr(line,'label')):
            labeladdresses[line.label] = context.curraddr
        line.emit(context)

    if verbose:
            print('2nd pass')

    for labelref in context.labels:
        (addr,label,ltype) = labelref
        defref = context.defs.get(label)
        if defref is not None:
            labeladdr = defref
        else:
            labeladdr = labeladdresses[label]
        if not labeladdr:
            raise Exception('Label {0} not defined'.format(label))
        if ltype == 'hi':
            hiaddr = context.hi(labeladdr)
            if verbose:
                print('store hi({0})={1} at 0x{2:04x}'.format(label, hiaddr, addr))
            context.emit_byte_at(addr, hiaddr)
        elif ltype == 'lo':
            loaddr = context.lo(labeladdr)
            if verbose:
                print('store lo({0})={1} at 0x{2:04x}'.format(label, loaddr, addr))
            context.emit_byte_at(addr, loaddr)
        elif ltype == 'lorel':
            addrdiff = labeladdr - addr + 1
            if verbose:
                print('store rel({0})={1} at 0x{2:04x}'.format(label, addrdiff, addr))
            if(addrdiff < -0x7f or addrdiff > 0x7f):
                raise Exception('Label {0} too far away for relative jump {1} bytes'.format(label, addrdiff))
            if(addrdiff < 0):
                addrdiff = (-addrdiff) | 0x80 
            context.emit_byte_at(addr, addrdiff)

    print('Code length: {0} labels: {1}'.format(len(context.bytes), len(labeladdresses)))
    
    return context

def save_output_file(fname, code):
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
    preamble = get_preamble(short_fname, context)
    with open(fname, 'wb') as file_handle:
        file_handle.write(btapify(preamble))
        return file_handle.write(btapify(context.bytes))

def main():
    parser = argparse.ArgumentParser(description='bc81asmc - an assembler for bc8181 cpu v.1.0.0 (180908)')
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
    ast = program.parse(input)
    print('Generating code')
    output = compile(ast, args.verbose)
    
    outfile = Path(args.infile).with_suffix(".btap")
    _, short_fname = os.path.split(Path(args.infile).with_suffix(""))
    save_output_btap(outfile, short_fname, output)

    print('Done!')

if __name__ == "__main__":
    main()
