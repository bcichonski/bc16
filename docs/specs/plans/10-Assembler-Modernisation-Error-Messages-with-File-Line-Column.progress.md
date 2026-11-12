# Progress — 10 Assembler Modernisation: Error Messages with file:line:column

Plan revision: A2
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Diagnostics module and source positions on the AST | — | Medium | Done | sonnet, started 2026-11-10 11:31, finished ~11:37; bc81asmc_diag.py + 18 tests; attrs lineno/col/label_col, label refs str-subclass .line/.col |
| T5 | Rename the duplicate labels in committed sources, regenerate outputs | — | Medium | Done | re-dispatch sonnet 11:40, finished ~11:44 (bcos first exec_load_end -> exec_load_err, bytes identical); wave 1 verify: test-guard PASS, run_tests ALL PASSED; earlier: sonnet, started 2026-11-10 11:31, finished 11:34: Blocked (SPEC: exec_load_ret already a label in bcos.basm); strings.b rename + 8 regenerated .basm done and byte-checked; reset by A1 |
| T2 | `compile()` collects positioned errors | T1, T5 | Medium | Done | re-dispatch sonnet 11:55-11:59 (5 listed tests updated, bc81asmc_compile_diag_tests.py, byte-identical 15/15); wave 2 verify: test-guard PASS, run_tests ALL PASSED; earlier: sonnet 11:50-11:52: Blocked (SPEC: test-conflict TestDirectives.test_def_takes_precedence_over_label); compile() diagnostics in place, 4 listed tests + new tests pending; reset by A2 |
| T3 | CLI: report to stderr, exit codes, `--verbose` traceback | T2 | Medium | Done | sonnet 12:02-12:06; bc81asmc_cli_tests.py (9); build check byte-identical; wave 3 verify: test-guard PASS, run_tests ALL PASSED |
| T4 | Documentation: Errors section, component rules, decision record | T3 | Low | Done | haiku 12:08-12:12; 02-assembler Errors section, CLAUDE.md, A6, analysis; wave 4 verify: test-guard PASS, run_tests ALL PASSED (agent) |
