import argparse
from pathlib import Path
from bc_ast import *
from bc_grammar import program

def read_input_file(fname):
    with open(fname, 'r', encoding='utf8') as file_handle:
        return file_handle.read()

def compile(ast, verbose):
    context = Context()
    
    if(verbose):
        print("{}".format(ast))
    ast.emit(context)

    context.add_preamble()
    context.add_data_segment()
    context.add_stdlib()
    
    if len(context.errors) > 0:
        for error in context.errors:
            print('ERROR: {}'.format(error))
    elif verbose:
        print('No errors')
    
    return context.basm

def save_output_file(fname, code):
    with open(fname, 'w') as file_handle:
        return file_handle.write(code)

def preprocess(input, verbose):
    if verbose:
        print('Preprocessing file')

    lines = input.splitlines()

    newlines = []
    defines = {}
    i = 0
    while(i < len(lines)):
        newline = lines[i].strip()

        if(newline.startswith('#define')):
            spacepos = newline.index(' ')
            deffrom = newline[8:spacepos-1]
            defto = newline[spacepos+1:]
            defines[deffrom] = defto

        if(newline.startswith('#include')):
            fname = newline[8:]
            if verbose:
                print('Including file {}'.format(fname))
            content = read_input_file(fname)
            lines.append(';INCLUDED FILE {}'.format(fname))
            for contentline in content.splitlines():
                lines.append(contentline)

        for key in defines:
            val = defines[key]
            newline = newline.replace(key, val)

        if(len(newline) > 0):
            newlines.append(newline)
        i += 1

    return """
""".join(newlines)

def main():
    parser = argparse.ArgumentParser(description='bc - b language compiler for bc8181 cpu v.0.1.0 (220309)')
    parser.add_argument('infile', type=str,
        help='input file name')
    parser.add_argument('--verbose', action='store_true',
        help='Be more verbose')
    """args = parser.parse_args()
    infile = args.infile
    verbose = args.verbose"""
    infile = './bc/code/strings.b'
    verbose = False
    print('Reading input file {}'.format(infile))
    input = read_input_file(infile)
    input = preprocess(input, verbose)
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
