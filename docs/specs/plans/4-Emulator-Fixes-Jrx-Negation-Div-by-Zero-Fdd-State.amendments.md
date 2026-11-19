# Amendments — 4 Emulator Fixes

## A1 — 2026-11-19 — requested by owner (bcichonski, in the /grind session)

contradiction — D4/T2/T4/§2.4/§3.1: division and modulo by zero must not stop the CPU; they must "set the flag program checks" (owner decision, verbatim: "my decision: set the flag program checks"). Change D4 to: 16-bit div/mod with a zero divisor sets the OVERFLOW flag (O=1), leaves the destination pair unchanged, does not stop the CPU, and continues with the next instruction; programs test it with `jmp o`/`jrx o`. Update T2 (DoD, tests, Tests to modify), T4 (E10 text, 01-emulator.md wording, roadmap row: decided by the owner) and §2.4/§3.1 accordingly — evidence: owner statement in the run; issue item 3 already offers "set a flag (e.g. overflow)"; set_flags16 clears O for every in-range 16-bit result, so O after div/mod is a reliable error indicator.

## A2 — 2026-11-19 — requested by T3

test-conflict — add `src/bc64/tests/test_devices.py :: test_commands_are_ignored_while_in_failure_state` to T3's Tests to modify — it pins that a READSECT byte sent in STATE_READ_FAILURE (0xe2) is ignored; with the D5 fall-through fix that byte now sets STATE_DRIVE_FAILURE (0xe1) (`225 != 226`). Full e2e (103 tests) passes with the fix, so bcOS/bdos do not rely on the ignored byte.
