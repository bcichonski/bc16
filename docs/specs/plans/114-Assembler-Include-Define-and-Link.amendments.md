# Amendment requests — 114 Assembler: #include and #define from header files, and #link

## A1 — 2026-11-25 — requested by owner (mid-run)
missing-task — Owner: "we have no .h files yet, make sure to create them". Add a task that creates real `.h` headers for the shared B libraries in `src/bdos/` (the `#define`s moved out of each library `.b`, plus prototypes of its functions), has each library `.b` include its own `.h`, keeps every build output byte-identical, and adds an assembler test that every committed `src/bdos/*.h` is accepted as a header — evidence: no `*.h` file exists in the repo on master `97f23ad`; the plan's §1 put the split out of scope (#126).
test-conflict — `src/tests/test_bdioh_codes.py`, `src/tests/test_disc_layout_reserved.py` read the bdio `#define`s from `src/bdos/bdioh.b` by path; with A1 they live in `src/bdos/bdioh.h` — evidence: `BDIOH = …"bdos", "bdioh.b"` and `read("bdos", "bdioh.b")` in those files.

## A2 — 2026-11-25 — requested by T4
test-conflict — `src/tests/test_e2e_return.py`, `src/tests/test_e2e_toolchain.py`, `src/tests/test_e2e_random.py`, `src/tests/test_e2e_bdio_buffered.py`: each copies only `src/bdos/*.b` into a temp dir before compiling a program, so `bc` cannot find the new `X.h` included by `X.b` — evidence: `glob.glob(os.path.join(BDOS_DIR, "*.b"))` in each; happy tier fails `test_e2e_return`, `test_e2e_toolchain`.
test-conflict — `scripts/tests/test_check_memory_map.py` :: `FreshBuild.test_fresh_build_satisfies_the_memory_map` copies only `name.endswith(".b")` (+ boot.basm) from `src/bdos` — evidence: release suite error, `bc` can't find `std.h`.
test-conflict — `src/tests/test_bdioh_codes.py` :: `printexecres_body` reads the `bdio_printexecres(` body from `BDIOH`, which T4 (as listed) points at `bdioh.h`; the body stays in `bdioh.b` (D13 moves only defines and adds prototypes) — evidence: `test_changed_codes_have_a_message`, `test_disc_full_has_a_message` fail.
