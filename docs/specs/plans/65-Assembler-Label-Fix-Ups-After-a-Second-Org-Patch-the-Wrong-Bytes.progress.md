# Progress — 65 Assembler label fix-ups after a second .org patch the wrong bytes

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Reject a second or late `.org` in bc81asmc, with tests | — | Medium | Done | sonnet; wave 1 Done, guard PASS; rework r1 (sonnet): CLI test added in bc81asmc_cli_tests.py; full run_tests ALL PASSED (asm 6 xfail #11, e2e 1 xfail tape) |
| T2 | Docs: `.org` row, Errors table, decision A9 | T1 | Low | Done | haiku; started in parallel with T1 r1; rework r1 (haiku): dropped false 'blank lines' claim; guard PASS |
