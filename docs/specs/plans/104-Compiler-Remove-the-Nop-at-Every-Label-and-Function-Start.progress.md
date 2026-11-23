# Progress — 104 Compiler: remove the nop at every label and function start

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Compiler and stdio.b write labels without `nop` | — | Medium | Done | sonnet, started 2026-11-23 10:41Z, finished 10:42Z; 4 listed tests adjusted, new bc_label_nop_tests.py (6 tests); wave 1 test-guard PASS, unit group PASS (1014 tests) |
| T2 | Rebuild, run the full suite, record the sizes | T1 | Medium | Done | sonnet, started 2026-11-23 10:44Z, finished 11:04Z; full suite exit 0 (1 xfail tape #32/#62 remains), toolchain_run golden `..`→`.`, sizes −1605 B, code_size.csv +18 rows; wave 2 test-guard PASS |
| T3 | Docs: compiler page and the design page's `.IR` table | — | Low | Done | haiku, started 2026-11-23 10:41Z, finished 10:45Z; 03-compiler, 07 .IR table + phase-1 bullet, decision C7 |
