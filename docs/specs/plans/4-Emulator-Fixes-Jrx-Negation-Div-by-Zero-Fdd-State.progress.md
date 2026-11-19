# Progress — 4 Emulator Fixes: JRX Negation, Div by Zero, FDD State

Plan revision: A2
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | JRX: negation from the test code; unknown EXT sub-opcode stops cleanly | — | Medium | Done | sonnet, started 12:23Z, finished 12:25Z (unit green except T3-area test at the time) |
| T2 | Div/mod by zero sets the overflow flag | T1 | Medium | Done | reset by A1 (not started yet); sonnet, started 12:29Z, finished 12:32Z; wave 2 test-guard PASS, run_tests all PASS |
| T3 | FDD: unhandled byte sets the drive-failure state | — | Low | Done | haiku r2 started 12:29Z finished 12:31Z; haiku, started 12:23Z, finished 12:29Z: Blocked (SPEC: test-conflict test_commands_are_ignored_while_in_failure_state); test-guard PASS (vs base ref; snapshot tree vanished); reset by A2 (fix + other test edits already in tree) |
| T4 | Docs, design decision E10, and the shipped-code check | T1, T2, T3 | Low | Done | haiku, started 12:36Z, finished 12:44Z; AC3 grep 0 negated jrx in 15 .basm; run_tests ALL PASSED |
