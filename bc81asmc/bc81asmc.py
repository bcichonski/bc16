import argparse
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

    if verbose:
            print('done code length: {0} labels: {1}'.format(len(context.bytes), len(labeladdresses)))
    
    return context.bytes

def save_output_file(fname, code):
    with open(fname, 'wb') as file_handle:
        return file_handle.write(code)

def main():
    parser = argparse.ArgumentParser(description='bc81asmc - an assembler for bc8181 cpu v.0.1.0 (180908)')
    parser.add_argument('infile', type=str,
        help='input file name')
    parser.add_argument('--verbose', action='store_true',
        help='Be more verbose')
    args = parser.parse_args()
    print('Reading input file {}'.format(args.infile))
    input = read_input_file(args.infile)
    print('Parsing code')
    ast = program.parse(input)
    print('Generating code')
    output = compile(ast, args.verbose)
    outfile = Path(args.infile).with_suffix(".b81")
    print('Saving output file {}'.format(outfile))
    save_output_file(outfile, output)
    print('Done!')

if __name__ == "__main__":
    main()
