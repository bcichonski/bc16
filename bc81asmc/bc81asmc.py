import argparse
from pathlib import Path
from bc81asmc_ast import *
from bc81asmc_grammar import program

def read_input_file(fname):
    with open(fname, 'r', encoding='utf8') as file_handle:
        return file_handle.read()

def compile(ast, verbose):
    context = CodeContext()
    for line in ast:
        if verbose:
            print('{0:04x} {1}'.format(context.curraddr, line))
        line.emit(context)
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
