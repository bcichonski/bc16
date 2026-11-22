# Progress — 67 Assembler: clr af accepted but crashes

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | clr rejects af and non-pairs with clear messages | — | Medium | Done | rework r1 done (sonnet): moved TestClrRegisterForm above __main__; test-guard PASS; verify PASS; earlier: sonnet, started/finished 2026-11-22; test-guard PASS; wave verify PASS (run_tests exit 0, 7 pre-existing xfails; code_size delta 0); first run killed by env (exit 144), retried |
| T2 | Docs: Errors table, A9 decision, assembler CLAUDE.md | — | Low | Done | haiku, started/finished 2026-11-22; wave verify PASS |
