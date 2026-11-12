import argparse
import os
import sys
import traceback
from pathlib import Path
import bc_log
from bc_ast import *
from bc_grammar import program
from parsy import ParseError, line_info_at

sys.setrecursionlimit(2000)

codeSegment = 0x1000
heapSegment = 0x3000
codeLimit = None

def read_input_file(fname):
    with open(fname, 'r', encoding='utf8') as file_handle:
        return file_handle.read()

def compile(ast, verbose):
    bc_log.set_verbose(verbose)
    context = Context(codeSegment, heapSegment, False, codeLimit)
    
    bc_log.trace("{}".format(ast))
    try:
        ast.emit(context)

        context.add_preamble()
        context.add_data_segment()
        context.add_stdlib()
    except Exception as ex:
        if len(context.errors) > 0:
            # a consequence of an error that was already reported when it was recorded
            pass
        elif isinstance(ex, CompilerError):
            bc_log.error('internal error: {}'.format(ex))
        else:
            raise
        if bc_log.is_verbose():
            traceback.print_exc()
        sys.exit(1)
    
    if len(context.errors) > 0:
        # every error was already reported by Context.add_error
        sys.exit(1)
    bc_log.trace('No errors')
    
    return context.basm

def save_output_file(fname, code):
    with open(fname, 'w', encoding='utf8') as file_handle:
        return file_handle.write(code)

def preprocess(input, verbose, defaultdir):
    bc_log.set_verbose(verbose)
    bc_log.trace('Preprocessing file')

    global codeLimit
    codeLimit = None  # #codelimit is per compile, unlike #code/#heap

    lines = input.splitlines()

    newlines = []
    defines = {}
    deforder = []
    i = 0
    while(i < len(lines)):
        newline = lines[i].strip()

        if(newline.startswith('#define')):
            spacepos = newline.rindex(' ')
            deffrom = newline[8:spacepos]
            defto = newline[spacepos+1:]
            defines[deffrom] = defto
            deforder = sorted(defines.keys(), reverse=True)
            i += 1
            continue

        if(newline.startswith('#include')):
            fname = newline[9:]
            bc_log.trace('Including file {}'.format(fname))
            content = read_input_file(os.path.join(defaultdir, fname))
            j = 1
            for contentline in content.splitlines():
                lines.insert(i + j, contentline)
                j += 1
            i += 1
            continue

        if(newline.startswith('#codelimit')):
            addr = newline[11:]
            codeLimit = int(addr, 16)
            bc_log.trace('Code limit was set to 0x{0:04x}'.format(codeLimit))
            i += 1
            continue

        if(newline.startswith('#code')):
            addr = newline[6:]
            global codeSegment
            codeSegment = int(addr, 16)
            bc_log.trace('Code segment was set to 0x{0:04x}'.format(codeSegment))
            i += 1
            continue
        
        if(newline.startswith('#heap')):
            addr = newline[6:]
            global heapSegment
            heapSegment = int(addr, 16)
            bc_log.trace('Heap segment was set to 0x{0:04x}'.format(heapSegment))
            i += 1
            continue

        if(newline.startswith('//')):
            i += 1
            continue

        for key in deforder:
            val = defines[key]
            newline = newline.replace(key, val)

        if(len(newline) > 0):
            newlines.append(newline)
        i += 1

    return """
""".join(newlines)

def report_parse_error(input, ex, verbose):
    (line, col) = line_info_at(input, ex.index)  # 0-based, in the preprocessed source
    lines = input.splitlines()
    expected = str(ex).rsplit(' at ', 1)[0]
    bc_log.error('syntax error at preprocessed line {0}, column {1}: {2}'.format(line + 1, col + 1, expected))
    bc_log.error_context(lines[line] if line < len(lines) else '', col + 1)
    if verbose:
        first = max(line - 2, 0)
        for i, errLine in enumerate(lines[first:line + 20], first):
            bc_log.stderr('ERR {0}: {1}'.format(i, errLine))
        bc_log.stderr(str(ex))
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description='bc - b language compiler for bc8183 cpu v 1.3.1 (240927)')
    parser.add_argument('infile', type=str,
        help='input file name')
    parser.add_argument('--verbose', action='store_true',
        help='Be more verbose')
    parser.add_argument('--btap', action='store_true',
        help='Save btap file [OBSOLETE]')
    args = parser.parse_args()
    infile = args.infile
    verbose = args.verbose
    bc_log.configure(verbose, infile)
    bc_log.trace('Reading input file {}'.format(infile))
    input = read_input_file(infile)
    input = preprocess(input, verbose, os.path.dirname(infile))
    if(verbose):
        infilegen = Path(infile).with_suffix(".genb")
        bc_log.trace('Saving generated input file to {0}'.format(infilegen))
        save_output_file(infilegen, input)
    bc_log.trace('Parsing code')
    try:
        ast = program.parse(input)
    except ParseError as ex:
        report_parse_error(input, ex, verbose)
        sys.exit(1)

    bc_log.trace('Generating code')
    output = compile(ast, verbose)
    outfile = Path(infile).with_suffix(".basm")
    bc_log.trace('Saving output file {}'.format(outfile))
    header = "; generated by bc from {0} - do not edit\n".format(Path(infile).name)
    save_output_file(outfile, header + output)
    bc_log.trace('Done!')
    if not verbose:
        bc_log.info('bc: {0} -> {1}'.format(infile, outfile))

if __name__ == "__main__":
    main()
