"""Console-script launcher for the bc64 toolchain (bc64, bc81asmc, bcc, ftool).

The tools use flat imports and expect to be started as "python <path>/<script>.py", so the launcher
runs the existing scripts from the source tree next to this file exactly that way: the script's
directory first on sys.path, the script as __main__, the caller's working directory and
arguments untouched. Supported install: "pip install -e ." from a checkout.
"""
import os
import runpy
import subprocess
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))

INSTALL_HINT = "install with 'pip install -e .' from a checkout of the repository"

BCC_USAGE = "usage: bcc [-h] path/name\n"
BCC_HELP = (BCC_USAGE +
            "\nCompile path/name.b with bc.py and assemble the result path/name.basm with bc81asmc.py,\n"
            "writing name.basm and name.btap next to the source. Give the path without the\n"
            ".b extension, relative to the current directory.\n")


class SourceTreeMissing(Exception):
    pass


def _script(*parts):
    path = os.path.join(SRC_DIR, *parts)
    if not os.path.isfile(path):
        raise SourceTreeMissing("bc64 toolchain: cannot find %s; %s" % (path, INSTALL_HINT))
    return path


def _exit_code(code):
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    sys.stderr.write("%s\n" % (code,))
    return 1


def _run_script(script, argv):
    """Runs script in-process as __main__ and returns its exit status."""
    saved_argv, saved_path = sys.argv, list(sys.path)
    sys.argv = [script] + list(argv)
    sys.path.insert(0, os.path.dirname(script))
    try:
        runpy.run_path(script, run_name="__main__")
        return 0
    except SystemExit as stop:
        return _exit_code(stop.code)
    finally:
        sys.argv = saved_argv
        sys.path[:] = saved_path


def _launch(*script_parts):
    try:
        script = _script(*script_parts)
    except SourceTreeMissing as error:
        sys.stderr.write("%s\n" % error)
        return 1
    return _run_script(script, sys.argv[1:])


def bc64():
    return _launch("bc64.py")


def bc81asmc():
    return _launch("bc81asmc", "bc81asmc.py")


def ftool():
    return _launch("ftool.py")


def _run_child(script, *args):
    return subprocess.call([sys.executable, script] + list(args))


def bcc():
    args = sys.argv[1:]
    if args in (["-h"], ["--help"]):
        sys.stdout.write(BCC_HELP)
        return 0
    if len(args) != 1 or args[0].startswith("-"):
        sys.stderr.write(BCC_USAGE)
        return 2
    try:
        compiler = _script("bc", "bc.py")
        assembler = _script("bc81asmc", "bc81asmc.py")
    except SourceTreeMissing as error:
        sys.stderr.write("%s\n" % error)
        return 1
    code = _run_child(compiler, "--btap", args[0] + ".b")
    if code != 0:
        print("Error")
        return code
    return _run_child(assembler, "--verbose", "--btap", args[0] + ".basm")
