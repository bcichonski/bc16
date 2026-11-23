#!/usr/bin/env python3
"""Spike #34, T1: static use census and byte model for poke16, peek16, gt16, gteq16, eq16.

Run from the repo root (throw-away tooling, never part of production):
    python3 docs/specs/plans/34-hot-path/census.py
It writes docs/specs/plans/34-hot-path/census.md. Nothing outside that folder is written: the sources
are copied to a temp dir and compiled there (same program list and temp-copy method as
scripts/code_size.py, which is imported by file path).

How use counts are obtained and attributed
  A "use" is a call site `cal :<routine>` or `clr :<routine>` in the generated .basm. The routine body
  itself (the `poke16:` label of the runtime) is not a use. The programs are compiled in-process
  (bc.preprocess / parse / compile) with the compiler's Context.emit and Context.prepend wrapped so every
  emitted text fragment is tallied under the origin that produced it. No text matching is done on the
  final .basm, so the attribution does not depend on indentation or formatting:
    (a) codegen   - the fragment came from bc_ast.py: comparisons, unary `#`, the main prologue.
    (b) runtime   - the fragment is the stdlib template (Context.add_stdlib): calls made by the runtime
                    routines themselves (stackvar*, stackoffs*, stackhead*, mseek, ...). Constant per
                    program because the whole runtime is appended to every program. It is additionally
                    split per runtime routine from the template text (a routine starts at the first
                    label after a `;=============` separator line).
    (c) library   - the fragment came from STATEMENT_ASM, i.e. a B `asm "cal :..."` string, including the
                    src/bdos/std.b wrappers peek16()/poke16() and bdio/stdio/stdmem code.
  Cross-check: the three tallies must add up to the number of call sites found by a regex over the final
  .basm (stdlib bodies included); the script aborts otherwise.

Byte model (all lengths come from the real assembler src/bc81asmc, snippets are assembled, never counted
by hand)
  option 1  ROM call:     runtime keeps a stub `mov a,<idx>; psh a; pop f; cal :os_metacall; ret`
                          (idx from os_metatab in bcos.basm); every use stays `cal` (or `clr` in the runtime).
  option 2  private copy: the ROM routine body (with ret) is copied into the runtime; uses stay `cal`/`clr`.
  option 3  inline:       the body without ret replaces every use; no runtime routine. The comparison
                          bodies are re-laid-out with unique labels and fall through with a=0/1
                          (`xor a; jmr z,:end` idiom); they are modelled snippets, T2 builds the real ones.
  today:    poke16, peek16 = option 2 (private copy); gt16, gteq16, eq16 = option 1 (already ROM stubs).
  Modelled total of a program for routine r and option o =
      real assembled program size - cost(r, today) + cost(r, o)
      cost(r, o) = runtime bytes(o) + uses_cal * per_use(o, cal) + uses_clr * per_use(o, clr)
  The other four routines stay at today's option. The runtime is part of every program whether used or not,
  so its stubs/bodies are counted once per program (option 3 removes them).
  "After #17" (not implemented, modelled): the runtime-internal peek16/poke16 uses made by the
  stackvar*/stackoffs*/stackhead* helpers (the per-variable-access path) are removed, every other use is
  kept. Their today-cost is subtracted from the baseline; what replaces them in #17 is NOT modelled, so the
  view isolates the effect of the remaining uses and is not a prediction of the total size after #17.
Caveat: ROM call clobbers differ (os_call pushes/pops registers, `pop f` sets flags); a variant is only
trusted once T2 smoke-tests it.
"""

import contextlib
import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, os.path.join(ROOT, "src", "bc"))

ROUTINES = ("poke16", "peek16", "gt16", "gteq16", "eq16")
INDEX = {"poke16": 0x09, "peek16": 0x0a, "gt16": 0x21, "gteq16": 0x22, "eq16": 0x23}
TODAY = {"poke16": 2, "peek16": 2, "gt16": 1, "gteq16": 1, "eq16": 1}
HEADLINE = ("bdos/bdos", "bdos/texted", "bdos/ls")
ORIGINS = ("codegen", "runtime", "library")
CALL_RE = re.compile(r"^[ \t]*(?:\w+:[ \t]*)?(cal|clr)[ \t]+:(\w+)", re.MULTILINE)
STACK_PREFIXES = ("stackvar", "stackoffs", "stackhead")

# Hand-laid-out inline bodies (no ret, unique labels), assembled by the real assembler.
INLINE = {
    "poke16": "mov #dsdi, cs\ninc dsdi\nmov #dsdi, ci\n",
    "peek16": "mov cs, #dsdi\ninc dsdi\nmov ci, #dsdi\n",
    "gt16": ("mov a, cs\nsub ds\njmr c, :F\njmr nz, :T\nmov a, ci\nsub di\njmr c, :F\njmr nz, :T\n"
             "F: xor a\njmr z, :E\nT: mov a, 0x01\nE:\n"),
    "gteq16": ("mov a, cs\nsub ds\njmr c, :F\njmr nz, :T\nmov a, ci\nsub di\njmr nc, :T\n"
               "F: xor a\njmr z, :E\nT: mov a, 0x01\nE:\n"),
    "eq16": ("mov a, cs\nsub ds\njmr nz, :F\nmov a, ci\nsub di\njmr z, :T\n"
             "F: xor a\njmr z, :E\nT: mov a, 0x01\nE:\n"),
}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_size = load_module("_census_code_size", os.path.join(ROOT, "scripts", "code_size.py"))


def asm_len(text):
    """Bytes the real assembler produces for the snippet."""
    asm, grammar = code_size.load_assembler()
    with contextlib.redirect_stdout(io.StringIO()):
        context = asm.compile(grammar.program.parse(".org 0x6000\n" + text), False)
    return len(context.bytes)


def rom_bodies():
    """The ROM routine texts (with ret) from bcos.basm."""
    path = os.path.join(ROOT, "src", "bc81asmc", "bcOS", "bcos.basm")
    with open(path, encoding="utf8") as handle:
        lines = handle.read().replace("\r\n", "\n").split("\n")
    bodies = {}
    for name in ROUTINES:
        start = next(i for i, line in enumerate(lines) if line.startswith(name + ":"))
        out, rets = [], 0
        for line in lines[start:]:
            if line.startswith(";="):
                break
            out.append(re.sub(r";.*$", "", line))
            if line.strip() == "ret" or re.search(r":\s*ret\s*$", line):
                rets += 1
        bodies[name] = "\n".join(out).replace("gteq16_false", "eq16_false") if name == "eq16" else "\n".join(out)
    # the ROM table order check: index of each routine in os_metatab
    return bodies


def check_metatab():
    path = os.path.join(ROOT, "src", "bc81asmc", "bcOS", "bcos.basm")
    with open(path, encoding="utf8") as handle:
        text = handle.read()
    start = text.index("os_metatab:")
    names = []
    for line in text[start:].split("\n"):
        if ".db" in line:
            names += [item.strip().lstrip(":") for item in line.split(".db")[1].split(";")[0].split(",")]
        elif names and not line.strip().startswith(";"):
            break
    for name, idx in INDEX.items():
        if names[idx] != name:
            raise SystemExit("os_metatab[0x%02x] is %s, expected %s" % (idx, names[idx], name))


def byte_model():
    """Return {routine: {1|2|3: {'runtime': n, 'cal': n, 'clr': n}}} from assembled snippets."""
    nop = asm_len("nop\n")
    cal = asm_len("cal :x\nx: nop\n") - nop
    clr = asm_len("clr :x\nx: nop\n") - nop
    bodies = rom_bodies()
    model = {}
    for name in ROUTINES:
        stub = "mov a, 0x%02x\npsh a\npop f\ncal :os_metacall\nret\n" % INDEX[name]
        stub_len = asm_len(".def os_metacall, 0x0008\n" + name + ": " + stub)
        copy_len = asm_len(bodies[name] + "\n")
        inline_len = asm_len(INLINE[name]) - (nop if INLINE[name].rstrip().endswith("E:") else 0)
        model[name] = {
            1: {"runtime": stub_len, "cal": cal, "clr": clr},
            2: {"runtime": copy_len, "cal": cal, "clr": clr},
            3: {"runtime": 0, "cal": inline_len, "clr": inline_len},
        }
    return model


def runtime_split():
    """Per runtime routine: {routine: {name: uses}} from the stdlib template text."""
    from bc_stdlib import stdlib_template
    current, split, armed = None, {r: {} for r in ROUTINES}, False
    for line in stdlib_template.split("\n"):
        if line.startswith(";="):
            armed = True
            continue
        label = re.match(r"^(\w+):", line)
        if label and armed:
            current, armed = label.group(1), False
        for kind, target in CALL_RE.findall(line):
            if target in split:
                split[target][current] = split[target].get(current, 0) + 1
    return split


def compile_programs(tmp_programs):
    """Compile each program in-process with origin-tallying wrappers. Return {id: (basm, tally)}."""
    import bc
    import bc_ast
    import bc_log
    state = {"origin": "codegen", "tally": None}

    def count(text):
        for _, target in CALL_RE.findall(text):
            if target in ROUTINES:
                key = (state["origin"], target)
                state["tally"][key] = state["tally"].get(key, 0) + 1

    ctx = bc_ast.Context
    orig_emit, orig_prepend, orig_stdlib = ctx.emit, ctx.prepend, ctx.add_stdlib
    orig_asm = bc_ast.STATEMENT_ASM.emit

    def emit(self, code):
        count(code)
        return orig_emit(self, code)

    def prepend(self, code):
        count(code)
        return orig_prepend(self, code)

    def add_stdlib(self):
        saved, state["origin"] = state["origin"], "runtime"
        try:
            return orig_stdlib(self)
        finally:
            state["origin"] = saved

    def asm_emit(self, context):
        saved, state["origin"] = state["origin"], "library"
        try:
            return orig_asm(self, context)
        finally:
            state["origin"] = saved

    ctx.emit, ctx.prepend, ctx.add_stdlib = emit, prepend, add_stdlib
    bc_ast.STATEMENT_ASM.emit = asm_emit
    out = {}
    try:
        for program, path in tmp_programs.items():
            state["tally"] = {}
            bc.codeSegment, bc.heapSegment, bc.codeLimit = 0x1000, 0x3000, None
            bc_log.configure(False, path)
            with open(path, encoding="utf8") as handle:
                source = bc.preprocess(handle.read(), False, os.path.dirname(path))
            with contextlib.redirect_stderr(io.StringIO()):
                ast = bc.program.parse(source)
                basm = bc.compile(ast, False)
            out[program] = ("; generated\n" + basm, state["tally"])
    finally:
        ctx.emit, ctx.prepend, ctx.add_stdlib = orig_emit, orig_prepend, orig_stdlib
        bc_ast.STATEMENT_ASM.emit = orig_asm
    return out


def collect():
    programs = code_size.discover(ROOT)
    with tempfile.TemporaryDirectory(prefix="census_") as tmp:
        copies = {}
        for prefix, rel in code_size.SOURCE_DIRS:
            folder = os.path.join(ROOT, rel)
            os.makedirs(os.path.join(tmp, prefix))
            for name in os.listdir(folder):
                if name.endswith(".b"):
                    shutil.copyfile(os.path.join(folder, name), os.path.join(tmp, prefix, name))
        for program in programs:
            copies[program] = os.path.join(tmp, *program.split("/")) + ".b"
        compiled = compile_programs(copies)
    data = {}
    for program, (basm, tally) in compiled.items():
        regex = {}
        for _, target in CALL_RE.findall(basm):
            if target in ROUTINES:
                regex[target] = regex.get(target, 0) + 1
        for name in ROUTINES:
            got = sum(tally.get((o, name), 0) for o in ORIGINS)
            if got != regex.get(name, 0):
                raise SystemExit("%s: %s tally %d != basm call sites %d" % (program, name, got, regex.get(name, 0)))
        _, size = code_size.assemble(basm)
        data[program] = {"size": size, "tally": tally}
    return data


def uses(tally, name, after17, split):
    """(cal uses, clr uses): runtime-origin uses are the runtime's `clr`, others are `cal`."""
    codegen = tally.get(("codegen", name), 0)
    library = tally.get(("library", name), 0)
    runtime = tally.get(("runtime", name), 0)
    if after17 and name in ("peek16", "poke16"):
        runtime -= sum(n for r, n in split[name].items() if r and r.startswith(STACK_PREFIXES))
    return codegen + library, runtime


def cost(model, name, option, ucal, uclr):
    m = model[name][option]
    return m["runtime"] + ucal * m["cal"] + uclr * m["clr"]


def total(info, model, split, name, option, after17):
    base_cal, base_clr = uses(info["tally"], name, False, split)
    cal17, clr17 = uses(info["tally"], name, after17, split)
    return info["size"] - cost(model, name, TODAY[name], base_cal, base_clr) + cost(model, name, option, cal17, clr17)


OPT = {1: "1 ROM call", 2: "2 private copy", 3: "3 inline"}


def mark(name, option):
    return OPT[option] + (" (today)" if TODAY[name] == option else "")


def render(data, model, split):
    out = ["# Spike #34 census: static use counts and byte model", "",
           "Generated by `python3 docs/specs/plans/34-hot-path/census.py` (see its docstring for the method). "
           "All byte lengths come from the real assembler. Today: poke16/peek16 = option 2 (private copy), "
           "gt16/gteq16/eq16 = option 1 (ROM stub, already).", ""]
    out += ["## 1. Byte model per routine and option", "",
            "| routine | option | runtime bytes | bytes per use (`cal`) | per use in runtime (`clr`) |",
            "| :--- | :--- | ---: | ---: | ---: |"]
    for name in ROUTINES:
        for option in (1, 2, 3):
            m = model[name][option]
            out.append("| %s | %s | %d | %d | %d |" % (name, mark(name, option), m["runtime"], m["cal"], m["clr"]))
    out += ["", "Option 3 has no runtime routine; its per-use size is the inline body without `ret` "
            "(comparison bodies are modelled with unique labels and fall-through, `xor a; jmr z` idiom).", ""]
    out += ["## 2. Runtime-internal uses by runtime routine (constant per program)", "",
            "| routine | uses inside runtime routines | of which stackvar*/stackoffs*/stackhead* |", "| :--- | :--- | ---: |"]
    for name in ROUTINES:
        stack = sum(n for r, n in split[name].items() if r and r.startswith(STACK_PREFIXES))
        detail = ", ".join("%s x%d" % (r, n) for r, n in split[name].items()) or "none"
        out.append("| %s | %s | %d |" % (name, detail, stack))
    out.append("")
    out += ["## 3. Headline programs", ""]
    for program in HEADLINE:
        out += program_tables(program, data[program], model, split, level=3)
    out += ["## 4. Appendix: all programs", "",
            "### 4.1 Static use counts (codegen / runtime-internal / library+app)", "",
            "| program | size | " + " | ".join(ROUTINES) + " |",
            "| :--- | ---: | " + " | ".join("---:" for _ in ROUTINES) + " |"]
    for program, info in data.items():
        cells = ["%d / %d / %d" % tuple(info["tally"].get((o, n), 0) for o in ORIGINS) for n in ROUTINES]
        out.append("| %s | %d | %s |" % (program, info["size"], " | ".join(cells)))
    out += ["", "### 4.2 Modelled program size per routine and option (other routines at today)", ""]
    for after17 in (False, True):
        out += ["**%s**" % ("After #17 (modelled)" if after17 else "Today"), "",
                "| program | size today | " + " | ".join("%s o%d" % (n, o) for n in ROUTINES for o in (1, 2, 3)) + " |",
                "| :--- | ---: | " + " | ".join("---:" for _ in range(15)) + " |"]
        for program, info in data.items():
            cells = [str(total(info, model, split, n, o, after17)) for n in ROUTINES for o in (1, 2, 3)]
            out.append("| %s | %d | %s |" % (program, info["size"], " | ".join(cells)))
        out.append("")
    out += ["### 4.3 All five routines at one option (modelled)", "",
            "| program | today | all opt 1 | all opt 2 | all opt 3 | all opt 1 after #17 | all opt 2 after #17 | all opt 3 after #17 |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for program, info in data.items():
        cells = [str(all_total(info, model, split, o, a)) for a in (False, True) for o in (1, 2, 3)]
        out.append("| %s | %d | %s |" % (program, info["size"], " | ".join(cells)))
    out += ["", "## 5. How the \"after #17\" view is modelled", "",
            "#17 is not implemented. The model removes the runtime-internal `peek16`/`poke16` calls made by the "
            "`stackvar*`, `stackoffs*` and `stackhead*` helpers (the per-variable-access path; the counts are in "
            "section 2) and keeps every other use (codegen `#`/comparisons/prologue, library `asm` code, mseek, ...). "
            "The removed calls are subtracted at today's per-use cost; whatever #17 puts in their place is not "
            "modelled. Option totals are then computed over the remaining uses.", ""]
    return "\n".join(out) + "\n"


def all_total(info, model, split, option, after17):
    result = info["size"]
    for name in ROUTINES:
        base_cal, base_clr = uses(info["tally"], name, False, split)
        cal17, clr17 = uses(info["tally"], name, after17, split)
        result += cost(model, name, option, cal17, clr17) - cost(model, name, TODAY[name], base_cal, base_clr)
    return result


def program_tables(program, info, model, split, level):
    out = ["### %s (size today %d bytes)" % (program, info["size"]), "",
           "| routine | codegen | runtime-internal | library/app | total uses | "
           "runtime-internal after #17 |", "| :--- | ---: | ---: | ---: | ---: | ---: |"]
    for name in ROUTINES:
        c, r, l = (info["tally"].get((o, name), 0) for o in ORIGINS)
        out.append("| %s | %d | %d | %d | %d | %d |" % (name, c, r, l, c + r + l, uses(info["tally"], name, True, split)[1]))
    out += ["", "| routine | option | total today | total after #17 (modelled) |", "| :--- | :--- | ---: | ---: |"]
    for name in ROUTINES:
        for option in (1, 2, 3):
            out.append("| %s | %s | %d | %d |" % (name, mark(name, option),
                                                  total(info, model, split, name, option, False),
                                                  total(info, model, split, name, option, True)))
    out += ["", "| all five at | total today | total after #17 (modelled) |", "| :--- | ---: | ---: |"]
    for option in (1, 2, 3):
        out.append("| %s | %d | %d |" % (OPT[option], all_total(info, model, split, option, False),
                                         all_total(info, model, split, option, True)))
    out.append("")
    return out


def main():
    check_metatab()
    model = byte_model()
    split = runtime_split()
    data = collect()
    text = render(data, model, split)
    target = os.path.join(HERE, "census.md")
    with open(target, "w", encoding="utf8", newline="\n") as handle:
        handle.write(text)
    sys.stdout.write("wrote %s (%d programs)\n" % (target, len(data)))


if __name__ == "__main__":
    main()
