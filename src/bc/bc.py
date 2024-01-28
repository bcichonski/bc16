import argparse
import os
import sys
from pathlib import Path
from bc_ast import *
from bc_grammar import program

def read_input_file(fname):
    with open(fname, 'r', encoding='utf8') as file_handle:
        return file_handle.read()

def compile(ast, verbose):
    context = Context(0x1000, 0x3000, False)
    
    if(verbose):
        print("{}".format(ast))
    ast.emit(context)

    context.add_preamble()
    context.add_data_segment()
    context.add_stdlib()
    
    if len(context.errors) > 0:
        for error in context.errors:
            print('ERROR: {}'.format(error))
        sys.exit('There were compilation errors.')
    elif verbose:
        print('No errors')
    
    return context.basm

def save_output_file(fname, code):
    with open(fname, 'w') as file_handle:
        return file_handle.write(code)

def preprocess(input, verbose, defaultdir):
    if verbose:
        print('Preprocessing file')

    lines = input.splitlines()

    newlines = []
    defines = {}
    i = 0
    while(i < len(lines)):
        newline = lines[i].strip()

        if(newline.startswith('#define')):
            spacepos = newline.rindex(' ')
            deffrom = newline[8:spacepos]
            defto = newline[spacepos+1:]
            defines[deffrom] = defto
            i += 1
            continue

        if(newline.startswith('#include')):
            fname = newline[9:]
            if verbose:
                print('Including file {}'.format(fname))
            content = read_input_file(os.path.join(defaultdir, fname))
            j = 1
            for contentline in content.splitlines():
                lines.insert(i + j, contentline)
                j += 1
            i += 1
            continue

        for key in defines:
            val = defines[key]
            newline = newline.replace(key, val)

        if(len(newline) > 0):
            newlines.append(newline)
        i += 1

    return """
""".join(newlines)

def main():
    parser = argparse.ArgumentParser(description='bc - b language compiler for bc8181 cpu v 0.6.0 (240129)')
    parser.add_argument('infile', type=str,
        help='input file name')
    parser.add_argument('--verbose', action='store_true',
        help='Be more verbose')
    parser.add_argument('--btap', action='store_true',
        help='Save btap file [OBSOLETE]')
    args = parser.parse_args()
    infile = args.infile
    verbose = args.verbose
    print('Reading input file {}'.format(infile))
    input = read_input_file(infile)
    input = preprocess(input, verbose, os.path.dirname(infile))
    if(verbose):
        infilegen = Path(infile).with_suffix(".genb")
        print('Saving generated input file to {0}'.format(infilegen))
        save_output_file(infilegen, input)
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
