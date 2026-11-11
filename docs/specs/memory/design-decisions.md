# Design Decisions

Standing technical decisions for the BC64 project: the patterns a plan should follow
rather than re-argue. This file is the **memory bank** that `create-spec-plan` reads before
drafting. The project has no async messaging, so there is no `async-operations.md`; the
nearest thing, the contracts between components, is recorded here under **Global**.

**Scope.** Durable choices that cut across stories. Story-specific design belongs in the
plan; a record of what was built belongs in `docs/CHANGELOG.md`; detailed behaviour belongs
in the reference pages `docs/01-emulator.md` … `docs/05-bdos.md`.

Sections follow the components (Global, Emulator, Assembler, Compiler, bcOS, bdos), and so
does the changelog tag list in `docs/changelog-entry-template.md`. Each decision is stated
as a rule, with its purpose, rationale, usage and trade-offs.

---

## Global

### G1. bcOS system-call numbers are a stable ABI
- **Purpose:** programs call the OS without knowing where its routines are in the ROM.
- **Rationale:** a jump table (`os_metatab`, reached through `os_metacall` at `0x0008`) lets
  bcOS change internally without breaking the compiler runtime, bdos or apps. Calling fixed
  addresses was the alternative, and it would break on every ROM change.
- **Usage:**
  - `F` = function number, then `cal :os_metacall`;
  - never reorder or remove entries; add new ones at the end or in free slots;
  - retired routines point at `os12_comperror`;
  - slot `0x37` is reserved for bdos.
- **Trade-offs:** about 10 extra instructions per call, and `F` must be loaded right before
  the `cal`.

### G2. The memory map is fixed; addresses are compile-time constants
- **Purpose:** every component knows where the others live without a loader or relocation.
- **Rationale:** relocatable executables and memory management are on the roadmap and need
  much more toolchain work. Fixed addresses keep the boot loader and shell tiny.
- **Usage:**
  - bcOS: `0x0000`
  - bdio variables: `0x0d80`
  - shell command line: `0x0dd2`
  - boot sector: `0x0e00`
  - bdos: `0x0f00`
  - file buffers: `0x5d00`
  - user programs: `0x6000`
  - CPU stack: from `0xfffe`, downwards
  - `0xffff`: `KIL` (reserved, the ultimate stop)

  Constants live in `bdioh.b`, `boot.basm`, and each program's `#code`/`#heap`. A change
  to the map is a cross-cutting story: update all of them plus `docs/05-bdos.md`.
  The map is checked at build time: `boot.basm` asserts the boot sector size (`<= 0x0e80`), the
  compiler asserts every program's image ends below its `#heap` and `bdos.b` ends below `0x5d00`
  (`#codelimit`), and bcOS's asserts follow once #30 lands (#8).
- **Trade-offs:** one program at a time. Growth in bcOS or bdos forces coordinated address
  moves.

### G3. Generated build outputs are committed with their sources
- **Purpose:** the repo is always runnable (ROM image + `os.bdd`) without rebuilding.
- **Rationale:** the toolchain is Windows/Git-Bash flavoured, and the disc image is
  assembled by hand-maintained scripts. Committing outputs also makes changes in generated
  code visible in review.
- **Usage:** after editing `.b`, `.basm` or `bcos.basm`, rebuild. Commit `.genb`, `.basm`,
  `.btap`, `.sector(s)`, `.b81` and `os.bdd` in the same change. Keep a rebuild that is only
  churn in a separate commit.
- **Trade-offs:** noisy diffs and binary churn in history.

### G4. Register convention: `csci` holds the value, `dsdi` the second operand or address, `A` the status
- **Purpose:** one calling convention shared by bcOS routines, the compiler runtime,
  compiled B code and the bdio API.
- **Rationale:** the bc8183 has few registers and only `csci`/`dsdi`/`af` work as 16-bit
  pairs. A fixed role for each keeps hand-written asm and generated code compatible.
- **Usage:**
  - expression results and function return values are in `csci`;
  - the right operand, or the memory address argument, is in `dsdi`;
  - 8-bit status and flags go in `A` (`0` = ok);
  - bdio: `A` = call, `CSCI` = param1, `DSDI` = param2;
  - routine headers document IN/OUT and which registers are clobbered ("rubbish").
- **Trade-offs:** values often have to be shuffled through push/pop; `F` can't hold data
  across instructions.

### G5. Relative offsets are sign-magnitude, not two's complement
- **Purpose:** one encoding for `jmr` (7-bit), `jrx`/`clr` (15-bit) and the register-relative
  forms.
- **Rationale:** a historical CPU design choice. The CPU, the assembler fix-ups and the tests
  all agree on it.
- **Usage:** bit 7 (or bit 15) is the sign and the rest is the magnitude. Any new relative
  instruction or tool must use the same encoding.
- **Trade-offs:** unusual. `-0` exists, and the range is ±127 / ±32767.

### G6. 16-bit values in memory are big-endian
- **Purpose:** one byte order everywhere.
- **Rationale:** it matches the instruction encoding (`hh ll` immediates) and keeps memory
  dumps readable.
- **Usage:** these are all high byte first:
  - `poke16`/`peek16`;
  - `.db :label`;
  - the `.btap` preamble address and length;
  - FDD DMA configuration;
  - packed bdio parameters (`track<<8|sector`, `handle<<8|count`).
- **Trade-offs:** none significant; just never assume little-endian, as on x86 or Z80.

### G7. Errors are returned as status codes, never raised
- **Purpose:** predictable error handling in assembly and B, where there are no exceptions.
- **Rationale:** there are no interrupts or exception mechanism. A status byte is the
  cheapest signal.
- **Usage:**
  - `0x00` = ok;
  - error codes are grouped by high nibble: `0x0X` command errors, `0xcX` catalog,
    `0xeX` drive/file, `0xfX` system;
  - bcOS: `error` prints and continues; `fatal` prints and halts;
  - B functions return a `result` byte that callers compare against named constants in
    `bdioh.b`;
  - new codes go into the existing ranges and into the docs.
- **Trade-offs:** callers must check every result; codes are reused across contexts (e.g.
  `0xe6`, `0xe7`).

### G8. No interrupts: devices are polled through status ports
- **Purpose:** keep the machine, the emulator and the OS single-threaded and deterministic.
- **Rationale:** the CPU has no interrupt line by design ("no interrupts" in every
  generation).
- **Usage:**
  - send a command with `out`, then read the status with `in` and test bits (e.g. FDD
    `status & 0xe0`);
  - multi-byte device commands are command byte + parameter bytes;
  - DMA (FDD only) is the one way a device touches memory.
- **Trade-offs:** busy-waiting, and there are no timers or background I/O. Networking
  (roadmap) will need a polling design too.

### G9. Machine generations are frozen as releases, and each tool carries a dated version
- **Purpose:** a completed machine generation (BC16, BC32) stays runnable while the next one
  evolves.
- **Rationale:** each generation changes the CPU, memory size and OS together.
- **Usage:**
  - `release/<gen>_v1.0/` is a full snapshot; never edit it;
  - the version strings carry a date: `bc … v1.3.1 (240927)`, `bc81asmc … v1.3 (240914)`,
    `bcOS 1.2.20241102`, boot loader `1.1.20240923`, CPU `version 1.2 (20240814)`;
  - bump them when the behaviour changes;
  - the README keeps a roadmap and notes per generation.
- **Trade-offs:** duplicated code across releases; fixes are not backported.

### G10. The toolchain is cross-hosted, pure Python, with `parsy` as the only dependency
- **Purpose:** anyone with Python can build and run the whole stack.
- **Rationale:** an assembler and compiler running on the BC64 itself is a later roadmap item
  (steps 8–9). Until then, the host tools must stay simple and portable.
- **Usage:**
  - no new third-party dependencies without a strong reason;
  - scripts and imports assume `src/` as the working directory;
  - keep the tools runnable on Linux as well as Git Bash (the `winpty` wrappers are a known
    wart).
- **Trade-offs:** slow emulation. Packaging is a root `pyproject.toml` (Python >= 3.10, `parsy`
  only) with the console commands `bc64`, `bc81asmc`, `bcc`, `ftool`; the flat-import tools stay in
  `src/`, only a launcher is packaged (editable install). Windows-only leftovers (`winpty`, still
  used by the bash scripts; `bcc` falls back to `python3`) need cleaning up.

### G11. One test runner; tests are silent and deterministic; known bugs are `expectedFailure` tests
- **Purpose:** one command gives one pass/fail signal for the whole stack, and known defects
  stay visible in the test suites until they are fixed.
- **Rationale:** the three suites use flat imports and need different working directories.
  `run_tests.py` at the repo root (standard library only) runs each suite as a subprocess in its
  own directory, so the suites never share module names or `sys.path`. A clean run should read
  as a result, not as log output, so a passing test prints nothing and does not depend on time,
  test order or files left in the tree.
- **Usage:**
  - `pip install -e .`, then `python3 run_tests.py` from the repo root runs every
    suite (CPython 3.10 and 3.13+ are both checked before a test or code change lands);
  - a test module is silent on a passing run: turn debug output off in the module rather than
    filtering it. Temporary files come from `tempfile`;
  - a known bug whose correct behaviour is decided by its issue gets a test of the correct
    behaviour, marked `@unittest.expectedFailure`, with the issue number in a comment. When the
    fix lands, the test reports an unexpected success and the marker is removed;
  - a known bug whose behaviour is still undecided gets a test that pins today's behaviour and
    names the issue; that test changes when the issue decides;
  - a production defect found by a test is reported (issue or plan note) and is not fixed in a
    test-only change.
- **Trade-offs:** an expected failure counts as a pass, so the marker must be removed when the
  fix lands or the signal goes stale. A pinned test can hold a bug in place until its issue
  decides.

---

## Emulator (`src/bc64.py`, `src/bc64/`)

### E1. One device class per peripheral, one fixed port each
- **Purpose:** add or change hardware without touching the CPU.
- **Rationale:** it mirrors real hardware: devices sit on an I/O bus and the CPU only sees
  port numbers.
- **Usage:**
  - subclass `IODevice`, set `DEFAULT_IO_PORT`, implement `read_byte()`/`write_byte()`;
  - register it in `Bc64.__init__`;
  - use a free port (`0x4`, `0x6`, `0x7`, `0x9`–`0xF`);
  - document the protocol in `docs/01-emulator.md`.
- **Trade-offs:** one device per port; no shared or bank-switched ports.

### E2. All host interaction goes through `Environment`
- **Purpose:** keep devices and the CPU platform-independent and testable.
- **Rationale:** console raw mode differs between Windows (`msvcrt`) and POSIX (`termios`);
  file access needs to be stubbable in tests.
- **Usage:** devices call `env.get_char/write_char/open_file_*/read_*/write_*/log`, never
  `open`/`print`/`input` directly.
- **Trade-offs:** an extra layer for trivial calls.

### E3. Opcode dispatch on the high nibble; each handler advances `PC` itself
- **Purpose:** a simple, table-driven decoder that matches the instruction encoding.
- **Rationale:** with 16 opcodes in the high nibble, the low nibble and later bytes are
  sub-operations. Variable-length instructions mean only the handler knows the length.
- **Usage:**
  - `create_instructions()` maps nibble → `op_*`;
  - handlers read `self.nextbyte` and call `inc_pc(n)` for each consumed byte (prefetch
    convention);
  - the 16-bit ALU extension sits under `CLC` with low nibble `F`;
  - new instructions go into a free sub-code or `EXT` (`0xE`), never a new top-level
    nibble.
- **Trade-offs:** handlers are easy to get off-by-one; tests per opcode are mandatory.

### E4. The CPU stack is tagged
- **Purpose:** the stack can be inspected and dumped, and `RET` works as an indirect jump.
- **Rationale:** it makes debugging much easier (`print_cpu_stack`). `RET` with two push
  frames on top jumps to the pushed address.
- **Usage:**
  - `PSH` frame = `0x10` + value (2 bytes);
  - `CAL` frame = `0xC0` + hi + lo (3 bytes);
  - keep these sizes when touching stack code, and in software that computes stack depth.
- **Trade-offs:** stack use is double what a plain stack needs.

### E5. Multi-byte device protocols are explicit state machines with a readable status
- **Purpose:** a predictable command/parameter sequence for complex devices.
- **Rationale:** without interrupts (G8), software drives the device byte by byte and polls
  its state.
- **Usage:**
  - model states as constants (`STATE_CFG1/2`, `STATE_RD1/2`, clock `STATE_TIME_*`);
  - a reset or command byte returns the device to a known state;
  - `read_byte()` always returns the current status, or the next data byte in a read
    sequence;
  - CPU tests build programs as raw byte lists in a small `MemBus`.
- **Trade-offs:** a wrong byte sequence leaves the device in an intermediate state; a reset
  command is the only recovery.

### E6. The emulator is intentionally slow; speed is not a goal
- **Purpose:** keep the emulator simple and readable rather than fast.
- **Rationale:** the BC64 should feel like a slow 8-bit machine (about 130k
  instructions/s today), and clear code matters more than throughput.
- **Usage:**
  - don't optimise the CPU or the devices as part of an unrelated story;
  - the measured hot spots and possible speed-ups are kept in the "Performance (deferred)"
    section of `docs/analysis/01-emulator.md`;
  - revisit only when automated end-to-end runs or the web console become impractically
    slow.
- **Trade-offs:** long automated runs take longer; a web build on WebAssembly will be
  slower still.

### E7. Headless mode runs the emulator from the command line with scripted input and output
- **Purpose:** a script can drive a whole bcOS session (boot a disc, type commands, capture the
  printer output), so tests and CI can run the real system.
- **Rationale:** the console needs a terminal and a person (raw `getch`, prompts on the
  console), so the system could only be tested by hand. Headless mode is a separate
  environment, so the console path stays as it was.
- **Usage:**
  - options: `--disk-a`/`--disk-b` (prompt answers), `--tape-dir`, `--input` (`-` for stdin),
    `--output`, `--max-instructions`, `--random-seed` (see below); headless when one of them is given or stdin is not a
    terminal, and piped stdin is typed as keys;
  - `ScriptedEnvironment` in `bc64_env.py` is one class built from the options; each feature
    is optional and independent;
  - every line ending in the input becomes one CR, the Enter key;
  - end of input is a clean stop with exit 0 and no memory dump; the dump stays on `KIL`;
  - exit codes: 0 halt or end of input, 1 exception, 2 usage error, 3 instruction limit;
  - `--max-instructions` switches to a limited run loop; without it `cpu.run()` is used as is;
  - disk prompts are matched by their text (`Disk A name:`);
  - `--random-seed N` (int >= 0, decimal or hex, bad value exit 2) seeds the port `0x05`
    `RandomGenerator`, so a test can get reproducible random numbers; without it the generator is
    seeded from the system. It works in console and headless mode and does not by itself select
    headless mode; `run_session(..., seed=N)` passes it.
- **Trade-offs:** the console and headless paths must be kept in step; a halt and end of input
  both exit 0, so a script must check its output as well as the code; the limited run loop
  repeats the CPU's run loop in `bc64.py`, so a change to `cpu.run()` must be mirrored there;
  prompt matching depends on the device's prompt text.

### E8. `--no-floppy` starts bcOS without a floppy drive
- **Purpose:** the monitor (ROM only, no disc) can be run and tested headless, without a disc image.
- **Rationale:** with the floppy device mapped, bcOS always tries to boot from the disc, so the monitor
  cannot be reached without one. `IOBus` raises `KeyError` on an unmapped port, so an absent drive needs
  a stand-in device on port `0x08`, not a missing one.
- **Usage:**
  - `--no-floppy` attaches `NoFloppyDrive` (in `bc64_io.py`): the status read is `0x00` (no READY bit),
    writes are ignored;
  - `FloppyDriveV1` is unchanged;
  - the option is a headless option and conflicts with `--disk-a`/`--disk-b` (usage error, exit 2).
- **Trade-offs:** a program that needs a disc cannot run in this mode; the stand-in only has to match
  the status byte that bcOS reads.

### E9. End-to-end tests boot the headless emulator from scripts and compare goldens byte for byte
- **Purpose:** bcOS, the bdos shell and the toolchain are tested the way a user runs them, through the
  real emulator.
- **Rationale:** unit tests cannot show that a boot, a typed command and the disc agree.
- **Usage:**
  - the harness is `src/e2e_harness.py`, a plain module (D2); the scenarios are `test_e2e_*.py` next to
    `bc64.py`, where the code they drive lives (co-location);
  - a scenario is a script `<scenario>.in.txt` and a golden `<scenario>.golden.txt` in
    `src/bc64/testdata/e2e/` (D3); the golden is compared byte for byte, and marker strings must appear;
  - discs (D4): monitor scenarios use `--no-floppy`; shell scenarios use a temp copy of the frozen
    `smoke.bdd`; the toolchain scenario uses a temp copy of the live `os.bdd` and compares only the
    program output;
  - goldens are regenerated with `BC64_UPDATE_GOLDEN=1` (D5) and reviewed before commit;
  - the instruction limit is about 10x the measured need, capped at 200M; exit 3 fails the test (D6);
  - a known bug is an `expectedFailure` that names its issue, not a dropped scenario (D7); a scenario
    with no bug is not written as a golden of broken output;
  - every run uses temp dirs, and the source discs and `cpudebug.log` are checked after each run; no
    apps scenarios (D8);
  - `run_tests.py` discovers the e2e modules like the other `test_*.py`, so it is the `/grind` check (D9).
- **Trade-offs:** goldens follow the emulator and bcOS, so an intended change means regenerating them;
  the frozen disc does not follow `os.bdd` rebuilds; each scenario costs seconds of run time.

---

## Assembler (`src/bc81asmc/`)

### A1. Grammar as parsy combinators; one AST dataclass per instruction with its own `emit`
- **Purpose:** adding an instruction is local and testable.
- **Rationale:** a parser-combinator grammar is compact. Putting encoding in the AST node
  keeps syntax and encoding side by side.
- **Usage:** a new instruction is:
  1. a grammar rule in `bc81asmc_grammar.py`, added to the `mnemonic` / `mCLC` alternatives
     (more specific forms first);
  2. a dataclass with `emit()` in `bc81asmc_ast.py`;
  3. constants matching `bc8183_cpu.py`;
  4. grammar tests in `bc81asmc_tests.py`.
- **Trade-offs:** parsy error messages are poor; the order of alternatives matters.

### A2. Two passes with placeholder fix-ups; `.def` constants share the label namespace
- **Purpose:** forward references without a symbol pre-scan.
- **Rationale:** emitting placeholders (`0xfa`) and patching them in pass 2 is the
  simplest way to handle forward references.
- **Usage:**
  - label operands are recorded as `(addr, label, kind)` with kind `hi`, `lo`, `lorel`
    or `rel15`;
  - out-of-range relative targets are positioned errors (A6);
  - `.assert` lines are evaluated in pass 2, after the patching, so they may use forward references (#8);
  - `.def` gives fixed external addresses (e.g. `os_metacall`, `bdos_bootaddr`) and is
    referenced like a label, `:name`; it shares the label namespace, so a repeated name is
    an error (A6).
- **Trade-offs:** label operands must be byte-aligned (no half-emitted nibble). There are no
  expressions like `label+1`.

### A3. A deliberately minimal language: no macros, no expressions
- **Purpose:** keep the assembler trivial and its output predictable byte for byte.
- **Rationale:** high-level structure belongs in the B compiler. The assembler is a
  near-1:1 mapping of the encoding.
- **Usage:**
  - the only directives are `.org`, `.db`, `.mv` (label → register pair), `.def` and `.assert`;
  - `.assert` is the one exception to "no expressions": it is a build-time check, not an expression
    language. It compares two operands (a `:name` or a literal, no arithmetic) and emits no bytes (#8);
  - lowercase only;
  - fixed-width hex: `0xHH`, `0xHHHH`, `#0xH`;
  - generated `.basm` must follow the same rules.
- **Trade-offs:** verbose hand-written asm, and idioms like `xor a` + `jmp z` for
  unconditional jumps.

### A4. One `.org`, contiguous output, one output format (`.btap`)
- **Purpose:** the assembler knows nothing about where its output ends up.
- **Rationale:** tape is the native medium of the machine. Conversion to ROM or disk sectors
  is a separate concern (`ftool.py`).
- **Usage:** a source file has a single `.org` at the top. The output is always `<name>.btap`
  (preamble + one byte per bit). Use `ftool btap2bin` for raw binaries.
- **Trade-offs:** `.btap` is 8× the size of the code; no sections or multiple segments.

### A5. Operand notation: pairs are concatenated, `#` dereferences, `:` references a label
- **Purpose:** read operands at a glance in both hand-written and generated code.
- **Rationale:** the CPU only addresses memory through register pairs. Naming the pair
  (`csci`, `dsdi`, `sssi`, `af`) makes that explicit.
- **Usage:**
  - `mov a, #dsdi` (memory), `mov #csci, a`;
  - `cal :label`, `jmp z, csci`;
  - port operands use `#` too: `in a, #ci`, `out #cs, a`.
- **Trade-offs:** `#` means both "memory" and "port" depending on the instruction.

### A6. Errors are positioned `file:line:col` diagnostics on stderr; parsing stops at the first syntax error, later passes collect
- **Purpose:** a user error names the place in the source it is about, so a generated `.basm`
  of thousands of lines can be debugged without counting characters.
- **Rationale:** the `file:line:col: error:` form is the GNU/gcc one, and 1-based lines and
  columns match editors, so terminals and IDEs can link to it (D1). parsy's `many()` cannot
  resume after a failed line without restructuring the grammar, so a syntax error stops the run
  (D2). Once parsing succeeds, both passes run to the end, so every undefined label shows up in
  one run. Duplicate labels and `.def` names are errors rather than "last one wins" (D3): the two
  duplicates in the committed sources were renamed, and every `.btap` stayed byte-identical.
  Diagnostics go to stderr; progress lines stay on stdout (D7).
- **Usage:**
  - the header is `<file>:<line>:<col>: error: <message>`, followed by the source line and a `^`
    caret; a tab counts as one column;
  - new checks report through `bc81asmc_diag.py` (see `src/bc81asmc/CLAUDE.md`);
  - a failed `.assert` is an `assertion failed: <l> <op> <r> (0xLLLL <op> 0xRRRR)` diagnostic at the
    first non-blank character of its line, reported with the other pass-2 errors (#8);
  - exit status `1` on any error, and no output file; `--verbose` adds the traceback after the
    diagnostics (`docs/02-assembler.md`, Errors).
- **Trade-offs:** only the first syntax error is shown per run. A duplicate definition now fails
  the build until it is renamed. The renamed first definition of `strnextword` is kept as dead
  code rather than deleted, because deleting it would change the size of every program.

---

## Compiler (`src/bc/`)

### C1. The compiler emits readable assembly text, not binary
- **Purpose:** the generated code can be inspected, diffed and hand-checked.
- **Rationale:** reusing the assembler avoids a second encoder, and `.basm` output doubles
  as documentation of the code generation.
- **Usage:** `bc.py` writes `.basm` (and `.genb`, the preprocessed source, with
  `--verbose`); `./bcc` chains it with the assembler. When debugging, read the `.genb` and
  the `.basm`, not just the `.b`.
- **Trade-offs:** two tool invocations per build; both grammars must agree on syntax.

### C2. Variables live on a software stack; the CPU stack holds only return addresses and temporaries
- **Purpose:** support recursion and many locals despite an 8-bit stack index and tagged
  frames.
- **Rationale:** CPU stack frames are 2–3 bytes per item (E4) and awkward to index.
  A separate stack (`sys_stackhead`, after the program image) with offset-based helpers
  is compact.
- **Usage:**
  - a call pushes a scope (moves `sys_stackhead` forward), stores the arguments as the
    callee's first locals, `cal`s, then pops the scope;
  - access goes through `stackvar*` helpers, using short-offset forms when the offset is
    under 127;
  - blocks don't open scopes.
- **Trade-offs:** each variable access is a subroutine call; the stack space isn't bounds
  checked.

### C3. Everything is evaluated as 16 bits; types only set storage width
- **Purpose:** a single code path for all expressions.
- **Rationale:** the bc8183 16-bit ALU makes word arithmetic as cheap as byte arithmetic, and
  type checking would add a lot of compiler code.
- **Usage:**
  - `byte` stores the low byte on assignment;
  - comparisons are unsigned;
  - there are no implicit conversions or type errors;
  - results of logical operators are `0`/`1` (`||` excepted: it's a bitwise OR).
- **Trade-offs:** no signed arithmetic and no type safety; mistakes show up at run time.

### C4. Code size is the optimisation metric; prefer native bc8183 instructions over runtime calls
- **Purpose:** fit bdos and the apps in a small address space (G2).
- **Rationale:** `history.txt` tracks every optimisation as bytes saved (e.g. bdos
  14339 → 13063).
- **Usage:**
  - emit native `add/sub/mul/div/mod/and/or/shl/shr csci, dsdi`;
  - load constant right operands straight into `dsdi`;
  - short-circuit comparisons with 0;
  - use relative `clr`/`jrx`;
  - measure any codegen change by the size of `bdos.btap`.
- **Trade-offs:** optimisations add special cases in `bc_ast.py`; test them on real programs
  (bdos, texted).

### C5. Modularity is textual: `#include`/`#define`, one image, no linker
- **Purpose:** keep the compiler single-file-in, single-file-out.
- **Rationale:** a linker and object format would double the toolchain. Textual inclusion
  is enough at this scale.
- **Usage:**
  - libraries are B source in `src/bdos/` (`std.b`, `stdio.b`, `strings.b`, `stdmem.b`,
    `bdosh.b`), included by path relative to the main file;
  - constants are `#define`s;
  - the asm runtime `bc_stdlib.py` is appended to every program;
  - removing unused code is roadmap step 5.
- **Trade-offs:** every program carries the whole of every included library; `#define`
  replaces text everywhere, including strings.

---

## bcOS (`src/bc81asmc/bcOS/`)

### O1. The ROM stays minimal; features go to libraries or bdos
- **Purpose:** keep bcOS under its fixed ceiling (it ends at about `0x0d6b`, and bdos
  variables start at `0x0d80`).
- **Rationale:** the ROM can't be updated by programs, and its size directly limits RAM
  for bdos and apps.
- **Usage:**
  - bcOS provides the monitor, terminal and tape I/O, hex parsing, comparisons, and the
    FDD boot hand-off;
  - anything disk- or file-related lives in bdos;
  - helpers that compiled code inlines better live in `bc_stdlib.py`;
  - **routines that exist in both the ROM and the compiler runtime are owned by the ROM**:
    the runtime calls them through `os_metacall` instead of carrying private copies
    (decided 2026-11-08, option (a); implementation #33). The hot paths (`poke16`/`peek16`,
    `gt16`/`gteq16`/`eq16`) stay as they are until the spike #34 decides between a ROM call,
    a private copy and an inline sequence.
- **Trade-offs:** a ROM call costs a dispatch through `os_metacall` per use, which is
  accepted (E6); until #33 lands, the duplication remains.

### O2. Every routine starts with a header comment that is its contract
- **Purpose:** callers in asm, the B runtime and bdos rely on exact register behaviour.
- **Rationale:** there is no type system or calling convention beyond G4, so the header
  comment is the only spec.
- **Usage:**
  ```
  ;=============
  ; #NN: NAME(args) - description
  ; IN:   reg - meaning
  ; OUT:  reg - result / preserved / rubbish
  ```
  `#NN` must equal the real `os_metatab` index. Update the header in the same change as the
  code.
- **Trade-offs:** comments can drift; review them as carefully as the code.

### O3. Removed routines keep their table slot and point at `os12_comperror`
- **Purpose:** old programs fail loudly instead of calling the wrong routine.
- **Rationale:** follows from G1. In 1.2 the software `inc16/dec16/add16/sub16/mul16/div16`
  were replaced by CPU instructions, but their slots stayed.
- **Usage:** to retire a routine, point its slot at `os12_comperror` (fatal `0xce`), keep the
  `; #NN: … - removed` header, and update `docs/04-bcos.md`.
- **Trade-offs:** dead slots take table space.

### O4. `error` continues, `fatal` halts; error codes come from one shared list
- **Purpose:** consistent user-visible failure behaviour.
- **Rationale:** the monitor must keep running after user mistakes, but must stop on
  corrupted state.
- **Usage:**
  - `error` (`0x15`) for recoverable problems such as a bad argument or a tape error;
  - `fatal` (`0x14`) for quit (`0xf0`), compatibility (`0xce`) and unexpected errors
    (`0xff`);
  - new codes go in `bcos.md` and `docs/04-bcos.md`.
- **Trade-offs:** messages are just codes ("error 03"); the user needs the docs to read them.

### O5. The monitor UI is single-letter commands with fixed-width hex arguments
- **Purpose:** the smallest possible parser in ROM.
- **Rationale:** only the first character is dispatched, and arguments are exactly
  4 (address/length) or 2 (byte) hex digits, parsed by `parsehex16/8`.
- **Usage:** new commands get an unused letter. They parse their arguments from
  `var_promptbuf` with `nextword` + `parsehex*`, and are listed in `data_help`, `bcos.md`
  and `docs/04-bcos.md`.
- **Trade-offs:** cryptic for users; no decimal input; a 32-character line limit.

---

## bdos (`src/bdos/`)

### D1. bdos is written in B; only the boot loader is assembly
- **Purpose:** use the OS to exercise the compiler, and keep OS code high-level.
- **Rationale:** the project's goal is a working language compiler. bdos is its biggest test
  and its main driver for optimisations (C4).
- **Usage:**
  - shell and bdio in `bdos.b`/`bdio.b`;
  - shared constants in `bdioh.b`;
  - `asm "…"` only for register-level glue (calls into bcOS, port I/O);
  - `boot.basm` has to fit in one 128-byte sector, so it stays assembly.
- **Trade-offs:** bdos size depends on compiler quality; compiler bugs surface as OS bugs.

### D2. A tiny shell; every real command is an external `.PRG`
- **Purpose:** keep the resident part small and make tools independently replaceable.
- **Rationale:** a micro-kernel style, as in early DOS/CP/M. Built-ins are limited to
  `exit`, `bcos`, `help` and `a:`/`b:`.
- **Usage:**
  - a program is `NAME.PRG` with the X attribute, built with `#code 0x6000`;
  - it reads its arguments from `BDIO_CMDPROMPTADDR` (`upstring` + `strnextword`);
  - it supports `-h` for usage and `[d:]` drive prefixes on file arguments;
  - it ends with a normal return;
  - it is added to `buildtools`/`buildapps`, `makedisc` (its `btap2bin` line) and `src/disc.bddmanifest`.
- **Trade-offs:** every command loads from disk; no pipes or scripts yet (roadmap).

### D3. BFS: flat catalog, contiguous files, append-only allocation
- **Purpose:** the simplest file system that supports create, read, write and delete.
- **Rationale:** a fixed 16-byte catalog entry (number, start track/sector, length in
  sectors, attributes, 8+3 name) needs no allocation bitmap.
- **Usage:**
  - names are upper case and space-padded (`"LS      PRG"`); use `bdio_fnormalize` to
    convert;
  - attributes are R `0x01`, W `0x02`, X `0x04`, S `0x80`;
  - new space is always allocated after the last used sector (`bdio_getfreesect`);
  - files are written append-only.
- **Trade-offs:**
  - fragmentation, since deleted space isn't reused;
  - at most 255 sectors (about 32 KB) per file and 248 entries per disk;
  - no directories or dates (bdos 2.0 roadmap).

### D4. One numbered dispatcher (`bdio_call`) with B wrappers; programs use only the wrappers
- **Purpose:** a stable bdos API reachable through the bcOS meta-call (G1, slot `0x37`).
- **Rationale:** the same indirection as bcOS lets bdos move internally. Packing arguments
  into `CSCI`/`DSDI` fits the register convention (G4).
- **Usage:**
  - call numbers live in `bdioh.b`: `0x0X` sectors and drives, `0x1X` files;
  - wrappers in `bdosh.b` pack the arguments (e.g. `(handle << 8) | sectors`);
  - extra parameters go through fixed variables (e.g. the length at `0x0d92`);
  - shell-only internals stay out of the dispatcher.
- **Trade-offs:** an extra indirection per call; argument packing is easy to get wrong in
  new wrappers.

### D5. Static resources in fixed memory, no dynamic allocation in the kernel
- **Purpose:** predictable memory use in a fixed map (G2).
- **Rationale:** a kernel heap allocator would cost code size and could fail at run time.
- **Usage:**
  - 1 write and 3 read file descriptors in fixed tables (`0x0d94`, `0x0da4`), 10 bytes
    each;
  - one 128-byte buffer per handle at `0x5d00`;
  - sector buffers at `0x0e00`/`0x0e80`;
  - opening more files returns an error rather than allocating;
  - `malloc` (`stdmem.b`) is for user programs, which choose their own `#heap`.
- **Trade-offs:** hard limits on open files; buffered I/O is limited to one sector of
  buffering per handle.

### D6. TextEd files keep the `0x13` line-end text format (#47, D1)
- **Purpose:** one stable on-disc format for TextEd text files.
- **Rationale:** `0x13` is the `CHAR_LF` of both `texted.b` and `cat.b`, so `cat -c` already
  shows the records as lines (` !ln`); existing files such as `TEST.B` and `saveLines` already
  use it. Switching to `0x0a` was rejected: it would break those files and `cat -c`, for no gain.
- **Usage:**
  - one record per line, `<decimal line number> <text>` followed by `0x13`;
  - one `0x00` after the last record, then zero padding to the end of the sector;
  - the loader stops at the first `0x00` or at the end of the file (format details in
    `docs/05-bdos.md`, TextEd file format).
- **Trade-offs:** not a plain-text format for host tools, which expect `0x0a` line ends.

### D7. Optional services are opt-in includes (#2)
- **Purpose:** a bdio call any program may use, whose wrapper lives in its own include file, so
  programs that do not use it do not grow.
- **Rationale:** the compiler links every function of every included file, so a wrapper added to
  `bdosh.b` or `std.b` grows every program (TEXTED has 2 bytes left in its disc slot). The RNG is
  a bdos call (`BDIO_RANDOM` = `0x1a`), not a bcOS call: ROM growth would change the free-memory
  line of every bcOS golden.
- **Usage:**
  - `#include bdosh.b`, then `#include random.b`; `random(max)` returns `0..max-1`, or the whole
    16-bit word for `max` = 0;
  - the include file contains no `#include` itself (duplicate definitions are build errors);
  - tests seed the emulator RNG with `--random-seed N` (see E7).
- **Trade-offs:** the caller must include the files in the right order; the modulo has a slight bias.

### D8. The system disc is built from a manifest by `ftool mkdisc` (#37)
- **Purpose:** catalog lengths and start tracks come from the real files, and a disc that does not fit fails the build.
- **Rationale:** the hand-made binary catalog drifted from the builds (`CP.PRG` was truncated, so `cp` failed). The tool places files back to back and checks every limit before it writes anything.
- **Usage:**
  - the manifest is `src/disc.bddmanifest`: one file per line, `NAME.EXT SOURCE ATTRIBS [PLACE]`; line 1 is the boot file and line 2 the system file;
  - `BDOS.SYS` covers the whole boot loader range, 160 sectors, zero after the bdos build;
  - all 248 catalog entries are numbered, as `format` does; at most 247 are used, so the catalog is never full;
  - all checks run before the output is written; a failed build writes no output file.
- **Trade-offs:** a file that grows moves the files after it. Old discs copied before #37 number only entries 0–15, so a 17th file would overwrite `BOOTSECT.BIN`'s entry: re-make them (see `docs/05-bdos.md`).
