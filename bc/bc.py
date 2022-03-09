import argparse
from pathlib import Path
from bc_ast import *
from bc_grammar import program

def read_input_file(fname):
    with open(fname, 'r', encoding='utf8') as file_handle:
        return file_handle.read()

def compile(ast, verbose):
    context = Context()
    
    for token in ast:
        token.emit(context)
    
    return context.basm

def save_output_file(fname, code):
    with open(fname, 'w') as file_handle:
        return file_handle.write(code)

def main():
    parser = argparse.ArgumentParser(description='bc - b language compiler for bc8181 cpu v.0.1.0 (220309)')
    parser.add_argument('infile', type=str,
        help='input file name')
    parser.add_argument('--verbose', action='store_true',
        help='Be more verbose')
    args = parser.parse_args()
    infile = args.infile
    verbose = args.verbose
    #infile = './bc/code/declarations.b'
    #verbose = False
    print('Reading input file {}'.format(infile))
    input = read_input_file(infile)
    print('Parsing code')
    ast = program.parse(input)
    print('Generating code')
    output = compile(ast, verbose)
    outfile = Path(infile).with_suffix(".basm")
    print('Saving output file {}'.format(outfile))
    save_output_file(outfile, output)
    print('Done!')

if __name__ == "__main__":
    main()
