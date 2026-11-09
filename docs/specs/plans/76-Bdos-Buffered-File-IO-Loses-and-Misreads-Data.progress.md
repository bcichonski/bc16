# Progress — 76 bdos: Buffered File I/O Loses and Misreads Data

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Fix bdio buffered read/write/close/open, rebuild bdos, patch os.bdd, refresh smoke | — | High | Done | opus; started 11:22 finished 11:27 UTC (wave 1); spike round trip OK, BUFTEST.DAT 5 sectors; test-guard PASS; wave verify PASS (run_tests.py all) |
| T2 | E2E round-trip test of the buffered API | T1 | Medium | Done | sonnet; started 11:31 finished 11:34 UTC (wave 2); fails on old os.bdd; test-guard PASS; wave verify PASS |
| T3 | Document the buffered contract | — | Low | Done | haiku; started 11:22 finished 11:25 UTC (wave 1); docs subsection + table rows |
