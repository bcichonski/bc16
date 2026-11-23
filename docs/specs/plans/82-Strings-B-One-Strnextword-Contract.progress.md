# Progress — 82 strings.b: one strnextword and a documented contract

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | One `strnextword` with a documented contract | — | Low | Done | haiku, started 18:42 UTC, finished 18:51 UTC; 9 programs −24 B; test-guard PASS; run_tests.py exit 0 (xfails: 6 assembler #11, 1 e2e tape #32/#62) |
| T2 | e2e tests: bdos tools with a missing argument | T1 | Medium | Done | sonnet, started 18:51 UTC, finished 19:02 UTC; new src/tests/test_e2e_bdos_args.py (6 tests, 1 session); test-guard PASS; run_tests.py exit 0 (xfails: 6 assembler #11, 1 e2e tape #32/#62) |
