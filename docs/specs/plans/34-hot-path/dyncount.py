#!/usr/bin/env python3
"""Spike #34 (T3): instructions per call and dynamic call counts of poke16, peek16, gt16, gteq16, eq16.

Run from the repo root:   python3 docs/specs/plans/34-hot-path/dyncount.py
Writes:                   docs/specs/plans/34-hot-path/dyncount.md

Throw-away measurement tooling, no production change. What it does:
  1. copies src/ to a temp dir and builds ROM, bdos, utilities, apps and both discs there
     (the repo tree is never written to; the emulator and assembler are imported from the repo's src/);
  2. micro-benchmarks every routine under three delivery options in the real emulator, on the real ROM image,
     counting the executed instructions from the `cal` at the use site up to the return to the caller:
        rom    runtime stub (mov a,<idx>; psh a; pop f; cal :os_metacall; ret) -> os_metacall -> os_call -> var_oscall -> ROM body
        copy   the ROM body copied into the program, called directly
        inline the body without cal/ret (every `ret` that is not the last exit becomes a jump to the end)
  3. runs scripted sessions (boot, `ls`, a texted session) in-process on the built discs and counts, by PC, every entry to
     the routines in the loaded program images (bdos and the user program in 0x6000, identified by image) and in the ROM.
"""
import collections
import contextlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
SRC = os.path.join(REPO, "src")
OUT_MD = os.path.join(HERE, "dyncount.md")

ROUTINES = ["poke16", "peek16", "gt16", "gteq16", "eq16"]
INDEX = {"poke16": 0x09, "peek16": 0x0A, "gt16": 0x21, "gteq16": 0x22, "eq16": 0x23}
TODAY = {"poke16": "copy", "peek16": "copy", "gt16": "rom", "gteq16": "rom", "eq16": "rom"}
OPTIONS = ["rom", "copy", "inline"]
OPT_NAME = {"rom": "1 ROM call", "copy": "2 private copy", "inline": "3 inline"}
USER_BASE = 0x6000
BDOS_PROGRAM = "bdos"
USER_PROGRAMS = ["ls", "cp", "format", "rm", "cha", "cat", "helloworld", "texted", "theodore", "calc"]


# ----------------------------------------------------------------------------- tool loading


def load_tools():
    """Import the repo's assembler (patched in memory to also return the label table) and emulator."""
    sys.path.insert(0, SRC)
    sys.path.insert(0, os.path.join(SRC, "bc81asmc"))
    text = open(os.path.join(SRC, "bc81asmc", "bc81asmc.py"), encoding="utf8").read()
    marker = "    return context\n\ndef save_output_file"
    assert marker in text, "assembler layout changed: cannot expose the label table"
    text = text.replace(marker, "    context.labeladdresses = labeladdresses\n" + marker)
    asm = type(sys)("bc81asmc_patched")
    asm.__file__ = os.path.join(SRC, "bc81asmc", "bc81asmc.py")
    exec(compile(text, asm.__file__, "exec"), asm.__dict__)
    spec = importlib.util.spec_from_file_location("bc64_main", os.path.join(SRC, "bc64.py"))
    emu = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(emu)
    from bc64 import bc64_env, bc8183_cpu
    return asm, emu, bc64_env, bc8183_cpu


ASM, EMU, ENV, CPU = load_tools()


def assemble(text):
    """Assemble source text; return (start address, bytes, {label: address})."""
    with contextlib.redirect_stdout(io.StringIO()):
        ast = ASM.program.parse(text)
        context = ASM.compile(ast, False)
    return context.startaddr, bytes(context.bytes), dict(context.labeladdresses)


def assemble_file(path):
    return assemble(open(path, encoding="utf8").read())


# ----------------------------------------------------------------------------- build in a temp copy


def build_temp_copy(tmp):
    """Copy src/ to tmp/src and build ROM, bdos, tools, apps and discs there. Returns tmp/src."""
    dst = os.path.join(tmp, "src")
    shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "cpudebug.log"))
    for script in ("buildos", "buildtools", "buildapps", "makedisc"):
        text = open(os.path.join(dst, script), encoding="utf8", newline="").read().replace("\r", "")
        result = subprocess.run(["bash", "-c", text], cwd=dst, capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit("build step %s failed:\n%s\n%s" % (script, result.stdout[-2000:], result.stderr[-2000:]))
    return dst


# ----------------------------------------------------------------------------- micro-benchmarks


def extract_rom_body(rom_src, label):
    """The ROM routine starting at `label:` up to the next `;=====` separator (comments dropped)."""
    match = re.search(r"^%s:.*?(?=^;=====)" % re.escape(label), rom_src, re.S | re.M)
    assert match, "ROM routine %s not found" % label
    lines = [re.sub(r"\s*;.*$", "", line).rstrip() for line in match.group(0).splitlines()]
    return "\n".join(line for line in lines if line.strip())


def private_copy(rom_src, routine):
    body = extract_rom_body(rom_src, routine)
    if routine == "eq16":
        # the ROM eq16 shares gteq16's false exit; a private copy needs its own
        body = body.replace(":gteq16_false", ":eq16_false")
    return body


def rom_stub(routine):
    return ("%s_stub: mov a, 0x%02x\n psh a\n pop f\n cal :os_metacall\n ret" % (routine, INDEX[routine]))


# Inline variants. `mov`/`xor` set the flags, so `xor a` + `jmr z` and `mov a,1` + `jmr nz` are the unconditional
# jumps to the join label (an unconditional jump costs no extra instruction after the result is loaded).
INLINE = {
    "poke16": "mov #dsdi, cs\n inc dsdi\n mov #dsdi, ci",
    "peek16": "mov cs, #dsdi\n inc dsdi\n mov ci, #dsdi",
    "gt16": ("mov a, cs\n sub ds\n jmr c, :f\n jmr nz, :t\n mov a, ci\n sub di\n jmr c, :f\n jmr nz, :t\n"
             "f: xor a\n jmr z, :e\n t: mov a, 0x01\n e:"),
    "gteq16": ("mov a, cs\n sub ds\n jmr c, :f\n jmr nz, :t\n mov a, ci\n sub di\n jmr c, :f\n jmr nz, :t\n"
               "t: mov a, 0x01\n jmr nz, :e\n f: xor a\n e:"),
    "eq16": ("mov a, cs\n sub ds\n jmr nz, :f\n mov a, ci\n sub di\n jmr nz, :f\n"
             "t: mov a, 0x01\n jmr nz, :e\n f: xor a\n e:"),
}


def cmp_case(routine, cs, ci, ds, di):
    """Path class of a comparison by its inputs (same function for the micro-benchmark and the dynamic run)."""
    if routine == "eq16":
        return "hi differs" if cs != ds else ("hi equal, lo differs" if ci != di else "equal")
    if cs < ds:
        return "hi <"
    if cs > ds:
        return "hi >"
    return "hi equal, lo <" if ci < di else ("equal" if ci == di else "hi equal, lo >")


CASES = {
    "gt16": [("hi <", 0x10, 0x50, 0x20, 0x10), ("hi >", 0x30, 0x00, 0x20, 0xFF), ("hi equal, lo <", 0x20, 0x10, 0x20, 0x50),
             ("equal", 0x20, 0x50, 0x20, 0x50), ("hi equal, lo >", 0x20, 0x60, 0x20, 0x50)],
    "eq16": [("hi differs", 0x10, 0x50, 0x20, 0x50), ("hi equal, lo differs", 0x20, 0x10, 0x20, 0x50),
             ("equal", 0x20, 0x50, 0x20, 0x50)],
}
CASES["gteq16"] = CASES["gt16"]
CASES["poke16"] = [("-", 0x12, 0x34, 0x70, 0x00)]
CASES["peek16"] = [("-", 0x00, 0x00, 0x70, 0x00)]


def expected_a(routine, cs, ci, ds, di):
    left, right = (cs << 8) | ci, (ds << 8) | di
    return int({"gt16": left > right, "gteq16": left >= right, "eq16": left == right}[routine])


def new_machine(rom_path, no_floppy=True, env=None):
    env = env or ENV.ScriptedEnvironment(debug=False)
    computer = EMU.Bc64(env, False, no_floppy)
    EMU.import_rom(rom_path, env, computer.mem)
    computer.write_top_kil()
    return computer, env


def quiet(cpu):
    cpu.print_context = lambda: None  # the per-instruction debug formatting is only noise here


def bench(rom_path, routine, option, case):
    """Executed instructions from the use site to the instruction after it, in the emulator. Checks the result."""
    name, cs, ci, ds, di = case
    rom_src = ROM_SRC
    if option == "inline":
        site = INLINE[routine]
        tail = ""
    elif option == "copy":
        site = "cal :%s" % routine
        tail = private_copy(rom_src, routine)
    else:
        site = "cal :%s_stub" % routine
        tail = rom_stub(routine)
    source = (".org 0x6000\n.def os_metacall, 0x0008\n mov cs, 0x%02x\n mov ci, 0x%02x\n mov ds, 0x%02x\n mov di, 0x%02x\n"
              "site: %s\nafter: nop\n kil\n%s\n" % (cs, ci, ds, di, site, tail))
    source = "\n".join(line for line in source.splitlines() if line.strip()) + "\n"
    start, code, labels = assemble(source)
    computer, _ = new_machine(rom_path)
    mem, cpu = computer.mem, computer.cpu
    for i, byte in enumerate(code):
        mem.write_byte(start + i, byte)
    mem.write_byte(0x7000, 0x12)
    mem.write_byte(0x7001, 0x34)
    quiet(cpu)
    cpu.pc.set(start)
    cpu.inc_pc(0)
    count, counting = 0, False
    for _ in range(100000):
        pc = cpu.pc.get()
        if pc == labels["site"]:
            counting = True
        if pc == labels["after"]:
            break
        cpu.run_next_opcode()
        count += counting
    else:
        raise AssertionError("benchmark did not finish: %s %s" % (routine, option))
    regs = cpu.regs
    if routine == "poke16":
        assert (mem.read_byte(0x7000), mem.read_byte(0x7001)) == (cs, ci), "poke16 %s wrong" % option
    elif routine == "peek16":
        assert (regs[CPU.Bc8183.CS].get(), regs[CPU.Bc8183.CI].get()) == (0x12, 0x34), "peek16 %s wrong" % option
    else:
        assert regs[CPU.Bc8183.A].get() == expected_a(routine, cs, ci, ds, di), "%s %s %s wrong result" % (routine, option, name)
    return count


# ----------------------------------------------------------------------------- dynamic counts


class Counter:
    """Hooks the CPU loop: counts entries to the routine addresses of the loaded images and of the ROM."""

    def __init__(self, rom_labels, programs, rom_image):
        self.programs = programs  # name -> (start, bytes, labels)
        self.rom_labels = rom_labels
        self.var_oscall = rom_labels["var_oscall"]
        self.os_call = rom_labels["os_call"]
        self.static = {}
        for routine in ROUTINES:
            self.static.setdefault(rom_labels[routine], []).append(("rom", None, routine))
        self.static.setdefault(self.os_call, []).append(("oscall", None, None))
        bd_start, _, bd_labels = programs[BDOS_PROGRAM]
        for routine in ROUTINES:
            self.static.setdefault(bd_labels[routine], []).append(("prog", BDOS_PROGRAM, routine))
        self.user = None
        self.watch = dict(self.static)
        self.calls = collections.Counter()      # (program, routine) -> program-level calls
        self.cases = collections.Counter()      # (program, routine, case) -> calls
        self.rom_via = collections.Counter()    # routine -> ROM body entries through var_oscall (os_metacall)
        self.rom_direct = collections.Counter() # routine -> ROM body entries by a direct cal inside the ROM
        self.metacalls = 0
        self.meta_index = collections.Counter()
        self.instructions = 0
        self.user_runs = collections.Counter()

    def identify(self, mem):
        raw = mem.mem
        best = None
        for name in USER_PROGRAMS:
            start, code, _ = self.programs[name]
            if bytes(raw[start:start + len(code)]) == code:
                best = name
                break
        if best is None:  # image already touched: fall back to a long prefix
            for name in USER_PROGRAMS:
                start, code, _ = self.programs[name]
                if bytes(raw[start:start + 256]) == code[:256]:
                    best = name
                    break
        self.user = best or "unknown"
        self.user_runs[self.user] += 1
        self.watch = dict(self.static)
        if best:
            labels = self.programs[best][2]
            for routine in ROUTINES:
                self.watch.setdefault(labels[routine], []).append(("prog", best, routine))

    def run(self, computer):
        cpu, mem = computer.cpu, computer.mem
        quiet(cpu)
        pc = cpu.pc
        regs = cpu.regs
        CS, CI, DS, DI, F = CPU.Bc8183.CS, CPU.Bc8183.CI, CPU.Bc8183.DS, CPU.Bc8183.DI, CPU.Bc8183.F
        watch = self.watch
        cpu.inc_pc(0)
        prev = -1
        n = 0
        try:
            while not cpu.kill:
                p = pc.get()
                if p == USER_BASE:
                    self.identify(mem)
                    watch = self.watch
                tags = watch.get(p)
                if tags:
                    for kind, prog, routine in tags:
                        if kind == "prog":
                            self.calls[(prog, routine)] += 1
                            if routine in CASES and len(CASES[routine]) > 1:
                                case = cmp_case(routine, regs[CS].get(), regs[CI].get(), regs[DS].get(), regs[DI].get())
                                self.cases[(prog, routine, case)] += 1
                            else:
                                self.cases[(prog, routine, "-")] += 1
                        elif kind == "rom":
                            (self.rom_via if prev == self.var_oscall else self.rom_direct)[routine] += 1
                        else:
                            self.metacalls += 1
                            self.meta_index[regs[F].get()] += 1
                cpu.run_next_opcode()
                prev = p
                n += 1
        except ENV.EndOfInput:
            pass
        self.instructions = n


SESSIONS = [
    ("boot", "boot bdos only (type `exit`)", b"exit\n"),
    ("ls", "boot bdos, `ls`, `exit`", b"ls\nexit\n"),
    ("texted", "boot bdos, texted on B: insert 3 lines, save, load, print, quit (from test_e2e_texted)",
     b"b:\ntexted\ni 10 10\nfirst line\nsecond line\nthird line\n\ns note.txt\nl note.txt\np 0 65535\nq\nexit\n"),
]


def run_session(build_src, rom_labels, programs, script):
    rom = os.path.join(build_src, "bc81asmc", "bcOS", "bcos_v1_2_0.b81")
    with tempfile.TemporaryDirectory() as tmp:
        a, b = os.path.join(tmp, "a.bdd"), os.path.join(tmp, "b.bdd")
        shutil.copyfile(os.path.join(build_src, "os.bdd"), a)
        shutil.copyfile(os.path.join(build_src, "utils.bdd"), b)
        keys, out = os.path.join(tmp, "keys.txt"), os.path.join(tmp, "out.txt")
        open(keys, "wb").write(script)
        env = ENV.ScriptedEnvironment(debug=False, disk_a=a, disk_b=b, input_source=keys, output_path=out,
                                      tape_dir=tmp)
        computer, env = new_machine(rom, no_floppy=False, env=env)
        counter = Counter(rom_labels, programs, None)
        try:
            with contextlib.redirect_stdout(io.StringIO()):  # the emulated printer echoes to stdout
                counter.run(computer)
        finally:
            env.close()
        for routine in ("gt16", "gteq16", "eq16"):
            stubs = sum(n for (p, r), n in counter.calls.items() if r == routine)
            assert stubs == counter.rom_via[routine], "%s: %d stub entries but %d ROM body entries via var_oscall" % (
                routine, stubs, counter.rom_via[routine])
        counter.output = open(out, "rb").read()
    return counter


# ----------------------------------------------------------------------------- report


def main():
    global ROM_SRC
    ROM_SRC = open(os.path.join(SRC, "bc81asmc", "bcOS", "bcos.basm"), encoding="utf8", newline="").read().replace("\r", "")
    with tempfile.TemporaryDirectory() as tmp:
        built = build_temp_copy(tmp)
        rom_path = os.path.join(built, "bc81asmc", "bcOS", "bcos_v1_2_0.b81")
        _, _, rom_labels = assemble(ROM_SRC)
        assert rom_labels["os_metacall"] == 0x0008
        programs = {}
        for name in [BDOS_PROGRAM] + USER_PROGRAMS:
            programs[name] = assemble_file(os.path.join(built, "bdos", name + ".basm"))

        # 1. instructions per call
        cost = {}  # (routine, option) -> {case: instructions}
        for routine in ROUTINES:
            for option in OPTIONS:
                cost[(routine, option)] = {c[0]: bench(rom_path, routine, option, c) for c in CASES[routine]}

        # 2. dynamic calls
        results = {}
        for key, _, script in SESSIONS:
            results[key] = run_session(built, rom_labels, programs, script)

    md = render(cost, results)
    with open(OUT_MD, "w", encoding="utf8", newline="\n") as handle:
        handle.write(md)
    print(md)


def fmt_range(values):
    lo, hi = min(values), max(values)
    return str(lo) if lo == hi else "%d-%d" % (lo, hi)


def render(cost, results):
    out = []
    w = out.append
    w("# Spike #34: instructions per call and dynamic call counts (T3)\n")
    w("Generated by `python3 docs/specs/plans/34-hot-path/dyncount.py` (run from the repo root). Measured in the emulator "
      "(`src/bc64/`, in-process) on the ROM and discs built in a temp copy of `src/`; nothing in the repo tree is written.\n")
    w("## 1. Instructions per call\n")
    w("Executed instructions from the `cal` at the use site up to and including the return to the caller (inline: from the "
      "first body instruction to the one after the body). Today's option is marked with `*`.\n")
    w("- **1 ROM call**: runtime stub `mov a,<idx>; psh a; pop f; cal :os_metacall; ret` -> `os_metacall` (0x0008) -> `os_call` "
      "(saves 5 regs, looks up `os_metatab`, ROM `cal :poke16` into `var_oscalladdr`, restores) -> `cal :var_oscall` -> ROM body -> returns. "
      "Index poke16 0x09, peek16 0x0a, gt16 0x21, gteq16 0x22, eq16 0x23.")
    w("- **2 private copy**: the ROM body copied into the program (comparisons: its own `*_false` label for eq16), `cal :routine` at the use site.")
    w("- **3 inline**: the body without `cal`/`ret`. A non-final exit becomes an unconditional jump to the end, written as the "
      "flag-setting result load followed by `jmr z`/`jmr nz` (`mov`/`xor` set the flags), so it costs the same instruction the `ret` did; "
      "the last exit falls through.\n")
    w("| routine | today | 1 ROM call | 2 private copy | 3 inline |")
    w("|---|---|---|---|---|")
    for routine in ROUTINES:
        cells = []
        for option in OPTIONS:
            v = fmt_range(cost[(routine, option)].values())
            cells.append(v + ("*" if TODAY[routine] == option else ""))
        w("| %s | %s | %s |" % (routine, OPT_NAME[TODAY[routine]], " | ".join(cells)))
    w("\nSingle-path routines (poke16, peek16) have one number; the comparisons are reported as min-max over their paths. Per path:\n")
    w("| routine | path | 1 ROM call | 2 private copy | 3 inline |")
    w("|---|---|---|---|---|")
    for routine in ROUTINES:
        for case in CASES[routine]:
            name = case[0]
            w("| %s | %s | %s |" % (routine, name, " | ".join(
                str(cost[(routine, o)][name]) + ("*" if TODAY[routine] == o else "") for o in OPTIONS)))
    w("")

    w("## 2. Dynamic call counts\n")
    w("Method: the emulator loop is hooked in-process and counts every instruction fetch whose PC is the address of a routine, "
      "using the symbol addresses the assembler reports for each program image (bdos at 0x0f00; the user program loaded at 0x6000 is "
      "identified by comparing the memory image with each built program when execution enters 0x6000) and for the ROM. "
      "A *program call* is an entry to the routine label inside a loaded program: for peek16/poke16 that is the private copy, for "
      "gt16/gteq16/eq16 it is the ROM-call stub. ROM bodies entered through `var_oscall` (ROM-call dispatch) are counted separately and "
      "equal the stub entries (asserted by the script); ROM bodies entered by a direct `cal` inside the ROM (including `os_call`'s own `cal :poke16`) are "
      "not affected by the options and are listed as information.\n")
    w("Sessions (keys typed in a scripted run on temp copies of `os.bdd`/`utils.bdd`):\n")
    for key, desc, script in SESSIONS:
        w("- `%s`: %s (`%s`) - %s instructions executed" % (key, desc, script.decode().replace("\n", "\\n"), format(results[key].instructions, ",")))
    w("")
    w("Sanity checks per session: ROM `os_call` entries (all os_metacall services) and ROM bodies reached via `var_oscall` vs stub entries "
      "(equal when every program-level comparison goes through its stub):\n")
    w("| session | os_metacall entries | user programs seen |")
    w("|---|---|---|")
    for key, _, _ in SESSIONS:
        r = results[key]
        w("| %s | %d | %s |" % (key, r.metacalls, ", ".join("%s x%d" % kv for kv in sorted(r.user_runs.items())) or "-"))
    w("")
    for key, desc, _ in SESSIONS:
        r = results[key]
        w("### Session `%s`\n" % key)
        progs = sorted({p for p, _ in r.calls})
        w("Program calls per routine and program:\n")
        w("| routine | " + " | ".join(progs) + " | total | ROM body via metacall | ROM body direct (info) |")
        w("|---|" + "---|" * (len(progs) + 3))
        for routine in ROUTINES:
            total = sum(r.calls[(p, routine)] for p in progs)
            w("| %s | %s | %d | %d | %d |" % (routine, " | ".join(str(r.calls[(p, routine)]) for p in progs), total,
                                              r.rom_via[routine], r.rom_direct[routine]))
        w("")
        w("Total instruction delta per option (sum over the session's program calls of (instructions of the option for that call's path "
          "- instructions of today's option); negative = fewer instructions than today). The path of each comparison call is classified "
          "from the registers at the routine's entry; poke16/peek16 have a single path.\n")
        w("| routine | calls | today | 1 ROM call | 2 private copy | 3 inline |")
        w("|---|---|---|---|---|---|")
        grand = {o: 0 for o in OPTIONS}
        grand_today = 0
        for routine in ROUTINES:
            by_case = collections.Counter()
            for (p, rt, case), n in r.cases.items():
                if rt == routine:
                    by_case[case] += n
            calls = sum(by_case.values())
            today = sum(n * cost[(routine, TODAY[routine])][c] for c, n in by_case.items())
            grand_today += today
            cells = []
            for o in OPTIONS:
                total = sum(n * cost[(routine, o)][c] for c, n in by_case.items())
                delta = total - today
                grand[o] += delta
                cells.append("%+d" % delta if o != TODAY[routine] else "0 (today)")
            w("| %s | %d | %s instr | %s |" % (routine, calls, format(today, ","), " | ".join(cells)))
        w("| **all five** | | %s instr | %s |" % (format(grand_today, ","), " | ".join(
            "%+d" % grand[o] for o in OPTIONS)))
        w("")
        w("Mixed result per option applied to **all five** routines at once: total delta vs today = " +
          ", ".join("%s: %+d" % (OPT_NAME[o], grand[o]) for o in OPTIONS) +
          " (session total %s instructions; best option -> %.1f%% of the session)." % (
              format(r.instructions, ","), 100.0 * min(grand.values()) / r.instructions))
        w("")
        if r.meta_index:
            top = ", ".join("0x%02x x%d" % kv for kv in r.meta_index.most_common(8))
            w("os_metacall services in this session (index x count, top 8): %s.\n" % top)
        cases = collections.defaultdict(collections.Counter)
        for (p, rt, case), n in r.cases.items():
            cases[rt][case] += n
        w("Path mix of the comparison calls: " + "; ".join(
            "%s: %s" % (rt, ", ".join("%s %d" % kv for kv in sorted(cases[rt].items()))) for rt in ("gt16", "gteq16", "eq16")) + ".\n")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
