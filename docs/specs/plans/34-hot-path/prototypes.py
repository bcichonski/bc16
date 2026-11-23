#!/usr/bin/env python3
"""Spike #34, task T2: built prototypes of the hot-path runtime routine options.

Run from the repo root:

    python3 docs/specs/plans/34-hot-path/prototypes.py [--no-e2e] [--keep] [--jobs N]

For every variant the script copies the sources (tracked + untracked, not ignored, without docs/)
to a fresh temp folder, applies the variant there, and then

  1. measures every program like scripts/code_size.py does (it imports that script by path and
     points it at the temp root: bc.py of the temp copy compiles, len(context.bytes) is the size);
  2. rebuilds the whole pipeline in the temp src/ (buildos, buildtools, buildapps, makedisc);
  3. boots the ROM of that copy with its os.bdd headless and runs `ls` and `hellowrd` (smoke);
  4. runs the e2e suite of that copy (`python3 run_tests.py --group e2e --no-build`), unless --no-e2e.

It writes docs/specs/plans/34-hot-path/prototypes.md. Nothing outside the temp folders is
written except that file; the temp folders are removed unless --keep is given.

Variants (the bcOS ROM is never changed; every variant runs on the same ROM):

  today       the sources as they are: peek16/poke16 private copies, gt16/gteq16/eq16 ROM stubs.
  pp_rom      peek16/poke16 as ROM call stubs (os_metacall index 0x0a / 0x09), option 1.
  pp_inline   peek16/poke16 inline at every use, no runtime body, option 3.
  cmp_copy    gt16/gteq16/eq16 as private copies of the ROM bodies (bcos.basm), option 2.
  cmp_inline  gt16/gteq16/eq16 inline at every use with unique labels, option 3.

Inline (option 3) is applied as a post-pass on the .basm that bc.py of the temp copy returns
(bc.py is patched there to call proto_inline.transform). Every `cal :R` / `clr :R` line becomes
the body of R, whatever produced it: the compiler codegen (EXPRESSION_BINARY.logic, unary #,
main prologue), the runtime (stackvar*, stackoffscalc*, mseek) and B `asm "cal :R"` lines
(std.b wrappers, stdio.b, stdmem.b, bdio.b, bdos.b). This yields the same bytes as emitting the
body at each site in the codegen and in the B sources. Standard library only.
"""

import argparse
import concurrent.futures
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
OUT_MD = os.path.join(HERE, "prototypes.md")
HEADLINE = ("bdos/bdos", "bdos/texted", "bdos/ls")
ROUTINES = ("peek16", "poke16", "gt16", "gteq16", "eq16")
BUILD_COMMAND = "./buildos && ./buildtools && ./buildapps && ./makedisc"
ROM_REL = os.path.join("src", "bc81asmc", "bcOS", "bcos_v1_2_0.b81")
SMOKE_KEYS = "ls\nhellowrd\nexit\n"
SMOKE_MARKERS = (b"A>ls", b"listing files of drive A:", b"HELLOWRD.PRG", b"catalog entries free",
                 b"A>hellowrd", b"bye!")
SMOKE_LIMIT = 100000000

VARIANTS = [
    ("today", "unchanged sources: peek16/poke16 = private copy (2), comparisons = ROM call (1)"),
    ("pp_rom", "peek16/poke16 = ROM call stub via os_metacall (index 0x0a / 0x09), option 1"),
    ("pp_inline", "peek16/poke16 = inline at every use, option 3"),
    ("cmp_copy", "gt16/gteq16/eq16 = private copy of the ROM bodies, option 2"),
    ("cmp_inline", "gt16/gteq16/eq16 = inline at every use (unique labels), option 3"),
]

# runtime blocks of bc_stdlib.py: (start marker, end marker), both at a ';=============' line
PP_BLOCK = ("; POKE16(#dsdi, csci)", "; READSTR(#dsdi, ci)")
CMP_BLOCK = ("; GT16(csci,dsdi)", "; STACKOFFSCALC(csci,a)")

PP_ROM_STUBS = """; POKE16(#dsdi, csci) - ROM call (prototype #34, option 1): os_metacall index 0x09
; OUT:  dsdi - address to store + 1, csci - unchanged, a - 0x09 (index), f - rubbish
poke16:        mov a, 0x09
               psh a
               pop f
               cal :os_metacall
               ret
;=============
; PEEK16(#dsdi) - ROM call (prototype #34, option 1): os_metacall index 0x0a
; OUT:  dsdi - address to read + 1, csci - value, a - 0x0a (index), f - rubbish
peek16:        mov a, 0x0a
               psh a
               pop f
               cal :os_metacall
               ret
"""

# post-pass module written into the temp src/bc/ for the inline variants; BODIES is filled in
PROTO_INLINE = r'''"""Prototype #34 (temp copy only): inline hot-path routines at every call site."""
import re

BODIES = %(bodies)r
ALIASES = %(aliases)r
CALL = re.compile(r"^(\s*)(?:cal|clr)\s+:(%(names)s)\s*$")
LABEL = re.compile(r"^(\w+):\s*(.*)$")
REF = re.compile(r":(\w+)")


def expand(name, n, indent):
    body = BODIES[name]
    prefix = "pi%%d_" %% n
    mapping = {label: prefix + label for label, _ in body if label}
    for alias, target in ALIASES.get(name, {}).items():
        mapping[alias] = prefix + target
    end = prefix + name + "_end"
    out, used_end = [], False
    for index, (label, instr) in enumerate(body):
        if instr == "ret":
            if index == len(body) - 1:
                instr = None
            else:
                previous = body[index - 1][1]
                if previous == "mov a, 0x01":
                    instr = "jmr nz, :" + end   # mov a, 0x01 leaves Z clear: always taken
                elif previous == "xor a":
                    instr = "jmr z, :" + end    # xor a leaves Z set: always taken
                else:
                    raise ValueError("cannot inline ret after %%r in %%s" %% (previous, name))
                used_end = True
        elif instr:
            def ref(match):
                if match.group(1) not in mapping:
                    raise ValueError("unresolved label %%s in %%s" %% (match.group(1), name))
                return ":" + mapping[match.group(1)]
            instr = REF.sub(ref, instr)
        text = indent
        if label:
            text = mapping[label] + ":" + (" " if instr else "")
        if instr:
            text += instr
        if text.strip():
            out.append(text)
    if used_end:
        out.append(end + ":")
    return out


def transform(basm):
    lines = basm.split("\n")
    out, counts, n = [], {}, 0
    for line in lines:
        match = CALL.match(line.rstrip("\r"))
        if match:
            n += 1
            name = match.group(2)
            counts[name] = counts.get(name, 0) + 1
            out.extend(expand(name, n, match.group(1) or "    "))
        else:
            out.append(line)
    summary = " ".join("%%s=%%d" %% (key, counts.get(key, 0)) for key in sorted(BODIES))
    return "; proto34 inlined: " + summary + "\n" + "\n".join(out)
'''


# ----------------------------------------------------------------------------- sources


def read_lf(path):
    with open(path, "r", encoding="utf8", newline="") as handle:
        return handle.read().replace("\r\n", "\n")


def write_lf(path, text):
    with open(path, "w", encoding="utf8", newline="\n") as handle:
        handle.write(text)


def rom_routines(root):
    """Return (copy_text, bodies): the GT16..EQ16 block of bcos.basm and per-routine bodies.

    bodies: {name: [(label or None, instruction or None)]} without comment lines."""
    text = read_lf(os.path.join(root, "src", "bc81asmc", "bcOS", "bcos.basm"))
    start = text.index("; #21: GT16(csci,dsdi)")
    start = text.rindex(";=============\n", 0, start)
    end = text.index(";=============\n", text.index("\neq16_false:"))
    block = text[start:end]
    bodies, current = {}, None
    for raw in block.split("\n"):
        line = raw.split(";", 1)[0].rstrip()
        if not line.strip():
            continue
        label, instr = None, line.strip()
        match = re.match(r"^(\w+):\s*(.*)$", line.strip())
        if match:
            label, instr = match.group(1), match.group(2).strip() or None
            if label in ("gt16", "gteq16", "eq16"):
                current = label
                bodies[current] = []
        if instr:
            instr = re.sub(r"\s*,\s*", ", ", re.sub(r"\s+", " ", instr))
        bodies[current].append((label, instr))
    return block, bodies


def runtime_bodies(root):
    """{peek16/poke16: body} from the private copies in bc_stdlib.py of root."""
    text = read_lf(os.path.join(root, "src", "bc", "bc_stdlib.py"))
    bodies = {}
    for name in ("poke16", "peek16"):
        start = text.index("\n%s:" % name) + 1
        end = text.index("\n", text.index("\n%s_ok:" % name) + 1)
        body = []
        for raw in text[start:end].split("\n"):
            line = raw.split(";", 1)[0].strip()
            match = re.match(r"^(\w+):\s*(.*)$", line)
            label, instr = (match.group(1), match.group(2).strip() or None) if match else (None, line)
            if label in (name,):
                label = None  # the entry label is not needed inline
            if label == name + "_ok":
                label = None  # never referenced
            if instr:
                body.append((label, re.sub(r"\s+", " ", instr)))
        bodies[name] = body
    return bodies


def replace_block(text, markers, replacement):
    begin = text.index(markers[0])
    begin = text.rindex(";=============\n", 0, begin) + len(";=============\n")
    finish = text.index(markers[1])
    finish = text.rindex(";=============\n", 0, finish)
    return text[:begin] + replacement + text[finish:]


def install_inline(root, bodies, aliases):
    bc_dir = os.path.join(root, "src", "bc")
    module = PROTO_INLINE % {"bodies": bodies, "aliases": aliases, "names": "|".join(sorted(bodies))}
    write_lf(os.path.join(bc_dir, "proto_inline.py"), module)
    bc_py = os.path.join(bc_dir, "bc.py")
    text = read_lf(bc_py)
    old = "    return context.basm\n"
    if text.count(old) != 1:
        raise RuntimeError("bc.py: cannot find the single 'return context.basm'")
    text = text.replace(old, "    import proto_inline\n    return proto_inline.transform(context.basm)\n")
    write_lf(bc_py, text)


def apply_variant(root, variant):
    """Edit the temp copy at root for the variant."""
    if variant == "today":
        return
    stdlib = os.path.join(root, "src", "bc", "bc_stdlib.py")
    text = read_lf(stdlib)
    if variant == "pp_rom":
        text = replace_block(text, PP_BLOCK, PP_ROM_STUBS)
    elif variant == "pp_inline":
        bodies = runtime_bodies(root)
        text = replace_block(text, PP_BLOCK, "")
        install_inline(root, bodies, {})
    elif variant == "cmp_copy":
        block, _ = rom_routines(root)
        body = block.split(";=============\n", 1)[1]
        text = replace_block(text, CMP_BLOCK,
                             "; GT16/GTEQ16/EQ16 - private copy of the bcOS ROM bodies (prototype #34, option 2)\n"
                             + body)
    elif variant == "cmp_inline":
        _, bodies = rom_routines(root)
        text = replace_block(text, CMP_BLOCK, "")
        # the ROM eq16 jumps to gteq16_false (same code as eq16_false: xor a, ret)
        install_inline(root, bodies, {"eq16": {"gteq16_false": "eq16_false"}})
    else:
        raise ValueError(variant)
    write_lf(stdlib, text)


def make_copy(dest):
    """Copy the tracked and untracked (not ignored) files, without docs/, to dest."""
    listing = subprocess.run(["git", "-C", REPO, "ls-files", "-co", "--exclude-standard", "-z"],
                             stdout=subprocess.PIPE, check=True, stdin=subprocess.DEVNULL)
    for rel in listing.stdout.decode("utf8").split("\0"):
        if not rel or rel.startswith("docs/") or not os.path.isfile(os.path.join(REPO, rel)):
            continue
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(os.path.join(REPO, rel), target)
    # the shell scripts of src/: LF endings (a CRLF checkout breaks bash) and executable
    src = os.path.join(dest, "src")
    for name in os.listdir(src):
        path = os.path.join(src, name)
        if os.path.isfile(path) and "." not in name:
            with open(path, "rb") as handle:
                data = handle.read()
            if data.startswith(b"#!"):
                with open(path, "wb") as handle:
                    handle.write(data.replace(b"\r\n", b"\n"))
                os.chmod(path, 0o755)


# ----------------------------------------------------------------------------- measuring


_CODE_SIZE = None


def code_size_module():
    global _CODE_SIZE
    if _CODE_SIZE is None:
        spec = importlib.util.spec_from_file_location(
            "_proto34_code_size", os.path.join(REPO, "scripts", "code_size.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CODE_SIZE = module
    return _CODE_SIZE


def measure(root):
    """{program: bytes}, {program: failure} for the copy at root (code_size.py's method)."""
    module = code_size_module()
    module.ROOT = root  # bc.py of the copy compiles; the assembler is unchanged in every variant
    results, failures = module.measure_all(root)
    return {key: value.size for key, value in results.items()}, failures


def run(cmd, cwd, timeout):
    started = time.time()
    try:
        done = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=timeout)
        return done.returncode, done.stdout.decode("utf8", "replace"), time.time() - started
    except subprocess.TimeoutExpired as error:
        out = (error.stdout or b"").decode("utf8", "replace")
        return -9, out + "\n[timeout after %ds]" % timeout, time.time() - started


def inline_counts(root):
    """{program: 'peek16=N ...'} from the '; proto34 inlined:' line of the built .basm files."""
    counts = {}
    folder = os.path.join(root, "src", "bdos")
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".basm") or not os.path.exists(os.path.join(folder, name[:-5] + ".b")):
            continue
        text = read_lf(os.path.join(folder, name))
        match = re.search(r"; proto34 inlined: (.*)", text)
        if match:
            counts["bdos/" + name[:-5]] = match.group(1).strip()
    return counts


def dot_count_only(out, test):
    """True when the failure block of test is a golden diff whose changed lines are all dot lines."""
    header = re.search(r"^(?:FAIL|ERROR): " + re.escape(test) + r"\s*$", out, re.MULTILINE)
    if header is None or not out[header.start():].startswith("FAIL"):
        return False
    block = out[header.end():]
    stop = re.search(r"^(?:={20,}|-{20,}\s*\nRan )", block, re.MULTILINE)
    block = block[:stop.start()] if stop else block
    block = "\n".join(line for line in block.splitlines() if not re.fullmatch(r"-{10,}", line))
    if "printer output differs from golden" not in block:
        return False
    changed = [line for line in block.splitlines()
               if line[:1] and line[:1] in "+-" and not line.startswith(("+++", "---"))]
    return bool(changed) and all(re.fullmatch(r"[+-]\r?\.+", line) for line in changed)


def smoke(root, e2e):
    """Build the pipeline in the copy, boot it, run ls + hellowrd, optionally the e2e suite."""
    result = {"build": None, "smoke": None, "e2e": None, "notes": []}
    src = os.path.join(root, "src")
    code, out, secs = run(["bash", "-c", BUILD_COMMAND], src, 1800)
    if code != 0:
        result["build"] = "FAIL (exit %d)" % code
        result["notes"].append("build output tail: " + " | ".join(out.strip().splitlines()[-6:]))
        return result
    result["build"] = "ok (%.0fs)" % secs
    result["inlined"] = inline_counts(root)

    with tempfile.TemporaryDirectory(prefix="proto34_smoke_") as tmp:
        keys = os.path.join(tmp, "keys.txt")
        write_lf(keys, SMOKE_KEYS)
        disk = os.path.join(tmp, "os.bdd")
        shutil.copyfile(os.path.join(src, "os.bdd"), disk)
        output = os.path.join(tmp, "out.txt")
        code, log, secs = run([sys.executable, os.path.join(src, "bc64.py"), os.path.join(root, ROM_REL),
                               "--disk-a", disk, "--input", keys, "--output", output,
                               "--max-instructions", str(SMOKE_LIMIT)], tmp, 900)
        printed = open(output, "rb").read() if os.path.exists(output) else b""
        missing = [m.decode() for m in SMOKE_MARKERS if m not in printed]
        if code == 0 and not missing:
            result["smoke"] = "pass"
        else:
            result["smoke"] = "FAIL"
            result["notes"].append("smoke: exit %d, missing markers %s; output tail: %r"
                                   % (code, missing, printed[-300:].decode("latin-1")))
        if os.path.exists(os.path.join(tmp, "cpudebug.log")):
            result["notes"].append("smoke: unexpected cpudebug.log (removed with the temp folder)")

    if e2e:
        code, out, secs = run([sys.executable, "run_tests.py", "--group", "e2e", "--no-build"], root, 3600)
        failed = sorted(set(re.findall(r"^(?:FAIL|ERROR): (\S+ \([^)]*\))", out, re.MULTILINE)))
        ran = re.findall(r"(Ran \d+ tests?[^\n]*)", out)
        summary = ran[-1].strip() if ran else "no test summary"
        if code == 0:
            result["e2e"] = "pass (%s, %.0fs)" % (summary, secs)
        else:
            counts = re.findall(r"^FAILED \(([^)]*)\)", out, re.MULTILINE)
            result["e2e"] = "FAIL (exit %d, %s%s)" % (code, summary.split(" in ")[0],
                                                      ", " + counts[-1] if counts else "")
            if failed:
                artefacts = [name for name in failed if dot_count_only(out, name)]
                real = [name for name in failed if name not in artefacts]
                if artefacts:
                    result["notes"].append(
                        "e2e failures that are only the progress-dot count of an unmasked golden "
                        "(bdio prints one dot per 8 sectors loaded, so a program that crosses a 1024-byte "
                        "boundary prints one dot more or less; size artefact, not a malfunction): "
                        + "; ".join(artefacts))
                if real:
                    result["notes"].append("e2e failures: " + "; ".join(real))
                result["e2e_real_failures"] = real
            else:
                result["notes"].append("e2e output tail: " + " | ".join(out.strip().splitlines()[-8:]))
    if os.path.exists(os.path.join(src, "cpudebug.log")):
        result["notes"].append("cpudebug.log appeared in the temp src/ (temp copy only)")
    return result


# ----------------------------------------------------------------------------- report


def fmt_delta(value):
    return "0" if value == 0 else "%+d" % value


def report(sizes, failures, smokes, e2e, started):
    names = [name for name, _ in VARIANTS]
    today = sizes["today"]
    programs = sorted(set().union(*(set(s) for s in sizes.values())) | set().union(*(set(f) for f in failures.values())))
    lines = ["# Spike #34 - built prototypes (T2)", "",
             "Generated by `python3 docs/specs/plans/34-hot-path/prototypes.py` (run from the repo root); "
             "do not edit by hand. Every variant is built in its own temp copy of the sources; the repo "
             "tree is not changed. Runtime: %.0f s." % (time.time() - started), "",
             "## Variants", "",
             "| variant | what changes (temp copy only) |", "| :--- | :--- |"]
    for name, text in VARIANTS:
        lines.append("| `%s` | %s |" % (name, text))
    lines += ["",
              "The bcOS ROM (`bcos.basm`, `bcos_v1_2_0.b81`) is **not** changed by any variant: every variant "
              "is rebuilt and booted on the same, unchanged ROM. Option 2 for peek16/poke16 and option 1 for "
              "the comparisons are `today`, so they are not separate variants.", ""]

    lines += ["## Headline sizes (bytes, real assembler output)", "",
              "| variant | bdos/bdos | bdos/texted | bdos/ls | bdos+texted+ls | delta vs today | all programs | delta vs today |",
              "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name in names:
        row = sizes[name]
        if any(p not in row for p in HEADLINE):
            lines.append("| `%s` | build failed: %s | | | | | | |" % (name, "; ".join(
                "%s: %s" % (k, v[:120]) for k, v in failures[name].items())))
            continue
        head = sum(row[p] for p in HEADLINE)
        head_today = sum(today[p] for p in HEADLINE)
        total = sum(row.values())
        total_today = sum(today[p] for p in row if p in today)
        lines.append("| `%s` | %d (%s) | %d (%s) | %d (%s) | %d | %s | %d | %s |" % (
            name, row[HEADLINE[0]], fmt_delta(row[HEADLINE[0]] - today[HEADLINE[0]]),
            row[HEADLINE[1]], fmt_delta(row[HEADLINE[1]] - today[HEADLINE[1]]),
            row[HEADLINE[2]], fmt_delta(row[HEADLINE[2]] - today[HEADLINE[2]]),
            head, fmt_delta(head - head_today), total, fmt_delta(total - total_today)))
    lines.append("")

    lines += ["## Smoke run per variant", "",
              "Build = `%s` in the temp `src/`. Smoke = boot the variant's ROM with its own `os.bdd` "
              "headless (`--disk-a`, keys `ls`, `hellowrd`, `exit`) and check the printer output for "
              "%s. e2e = `python3 run_tests.py --group e2e --no-build` inside the temp copy (the full "
              "e2e suite on that build). The e2e summary is quoted as run_tests.py prints it: an "
              "`expected failures=N` there is a test the suite pins as a known bug (the same in `today`), "
              "not a pass of that behaviour." % (BUILD_COMMAND, ", ".join("`%s`" % m.decode() for m in SMOKE_MARKERS)),
              "", "| variant | build | smoke (boot, ls, hellowrd) | e2e suite | verdict |",
              "| :--- | :--- | :--- | :--- | :--- |"]
    for name in names:
        s = smokes[name]
        built = bool(s["build"]) and s["build"].startswith("ok") and s["smoke"] == "pass"
        e2e_text = s["e2e"] or "not run"
        if not built:
            verdict = "**BROKEN**"
        elif not e2e or e2e_text.startswith("pass"):
            verdict = "works"
        elif "e2e_real_failures" in s and not s["e2e_real_failures"]:
            verdict = "works (e2e fails only on a size-dependent progress-dot count, see notes)"
        else:
            verdict = "**BROKEN**"
        lines.append("| `%s` | %s | %s | %s | %s |" % (name, s["build"], s["smoke"] or "not run",
                                                         e2e_text, verdict))
    notes = [(name, note) for name in names for note in smokes[name]["notes"]]
    if notes:
        lines += ["", "Notes:", ""]
        for name, note in notes:
            lines.append("- `%s`: %s" % (name, note.replace("|", "/")))
    lines.append("")

    lines += ["## Inlined call sites (built bdos programs, from the `; proto34 inlined:` line)", "",
              "| variant | program | sites replaced |", "| :--- | :--- | :--- |"]
    for name in ("pp_inline", "cmp_inline"):
        for program, text in sorted(smokes[name].get("inlined", {}).items()):
            lines.append("| `%s` | %s | %s |" % (name, program, text))
    lines.append("")

    lines += ["## All programs (bytes; delta vs today)", "",
              "| program | " + " | ".join("`%s`" % n for n in names) + " |",
              "| :--- | " + " | ".join("---:" for _ in names) + " |"]
    for program in programs:
        cells = []
        for name in names:
            if program in sizes[name]:
                value = sizes[name][program]
                if name == "today" or program not in today:
                    cells.append("%d" % value)
                else:
                    cells.append("%d (%s)" % (value, fmt_delta(value - today[program])))
            else:
                cells.append("FAILED")
        lines.append("| %s | %s |" % (program, " | ".join(cells)))
    lines.append("")
    fails = [(n, p, m) for n in names for p, m in failures[n].items()]
    if fails:
        lines += ["Build failures (code_size measurement):", ""]
        for name, program, message in fails:
            lines.append("- `%s` %s: %s" % (name, program, message.replace("\n", " ")[:300]))
        lines.append("")

    lines += ["## How each variant is built, and register/flag effects", "",
              "- **`pp_rom`**: the private `poke16`/`peek16` bodies in `bc_stdlib.py` are replaced by stubs "
              "in the style of the other ROM stubs (`mov a, 0x09|0x0a`, `psh a`, `pop f`, `cal :os_metacall`, "
              "`ret`). All callers keep calling `:poke16`/`:peek16` (codegen, runtime-internal `clr`, and the "
              "B `asm \"cal :peek16\"` lines), so the B asm uses go through the stub too; no source text changes. "
              "Effects: `os_call` saves/restores a, csci, dsdi, then calls the ROM body with a = the index, so "
              "after the call a = 0x09/0x0a and f is overwritten (index, then the ROM body's flags). The "
              "documented contract already says `a - rubbish`; the runtime callers that need a (stackoffscalc, "
              "stackoffsclc8) push it before the call. The smoke/e2e run is the check that no B asm caller "
              "depends on a or f across the call.",
              "- **`pp_inline`**: the bodies are removed from the runtime; every `cal :R`/`clr :R` line of the "
              "generated `.basm` (codegen, runtime-internal and B `asm` lines alike) becomes "
              "`mov cs, #dsdi / inc dsdi / mov ci, #dsdi` (peek16) or `mov #dsdi, cs / inc dsdi / mov #dsdi, ci` "
              "(poke16). Registers and flags at the end are exactly those of the private copy (the body is the "
              "same, minus `cal`/`ret`).",
              "- **`cmp_copy`**: the three stubs are replaced by the ROM text of `gt16`, `gteq16`, `eq16` copied "
              "from `bcos.basm` (labels unchanged; the ROM `eq16` jumps to `gteq16_false`, kept as is). Result "
              "registers/flags are those of the ROM call minus the dispatch (a, flags set by the body; f is no "
              "longer the index on entry, which the bodies overwrite anyway).",
              "- **`cmp_inline`**: the stubs are removed; every call line becomes the ROM body with labels "
              "renamed `pi<N>_<label>` (N unique per site), `eq16`'s `gteq16_false` mapped to its own "
              "`eq16_false`, and each inner `ret` replaced by a jump to `pi<N>_<name>_end`: after `mov a, 0x01` "
              "the jump is `jmr nz` (mov into a sets Z from the value, 1 -> Z clear), after `xor a` it is "
              "`jmr z`; a final `ret` is dropped. Relative jumps do not change flags, so a and all flags at the "
              "end are exactly those the ROM body returns (mseek's `clr :gteq16` / `jmr nz` relies on this).",
              "- The inline post-pass runs in the temp copy's `bc.py` (`return proto_inline.transform("
              "context.basm)`); that gives the same bytes as emitting the bodies in `bc_ast.py`, "
              "`bc_stdlib.py` and the B sources, and catches every origin in one place.",
              "- Calling a ROM body by its direct address is excluded (D4): only `os_metacall`, `os_metatab` "
              "and `os_vartab` are stable.", ""]
    write_lf(OUT_MD, "\n".join(lines))


# ----------------------------------------------------------------------------- main


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--no-e2e", action="store_true", help="skip the e2e suite per variant")
    parser.add_argument("--keep", action="store_true", help="keep the temp copies (paths printed)")
    parser.add_argument("--jobs", type=int, default=len(VARIANTS), help="variants built/smoked in parallel")
    args = parser.parse_args(argv)
    started = time.time()
    base = tempfile.mkdtemp(prefix="proto34_")
    roots = {}
    sizes, failures, smokes = {}, {}, {}
    try:
        for name, _ in VARIANTS:
            root = os.path.join(base, name)
            os.makedirs(root)
            make_copy(root)
            apply_variant(root, name)
            roots[name] = root
            sizes[name], failures[name] = measure(root)
            print("%-11s measured: %d programs, %d failures" % (name, len(sizes[name]), len(failures[name])),
                  flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            futures = {name: pool.submit(smoke, roots[name], not args.no_e2e) for name in roots}
            for name, future in futures.items():
                try:
                    smokes[name] = future.result()
                except Exception as error:  # report, never drop a variant
                    smokes[name] = {"build": "error", "smoke": None, "e2e": None,
                                    "notes": ["%s: %s" % (type(error).__name__, error)]}
                print("%-11s build=%s smoke=%s e2e=%s" % (name, smokes[name]["build"], smokes[name]["smoke"],
                                                         smokes[name]["e2e"]), flush=True)
        report(sizes, failures, smokes, not args.no_e2e, started)
        print("wrote %s" % os.path.relpath(OUT_MD, REPO))
    finally:
        if args.keep:
            print("temp copies kept in %s" % base)
        else:
            shutil.rmtree(base, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
