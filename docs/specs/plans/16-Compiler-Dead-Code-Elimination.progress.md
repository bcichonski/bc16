# Progress — 16 Compiler: dead-code elimination

Plan revision: A1
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Function-level dead-code elimination (chunks + label reachability) | — | High | Done | opus, started/finished 2026-11-23; guard PASS; unit group PASS (compiler 131); helloworld 1626→866, total −22103 B (runtime still whole) |
| T2 | Split the runtime into fragments with declared dependencies; emit only used ones | T1 | Medium | Done | sonnet, 2026-11-23; guard PASS (allow bc_codegen_tests.py, one assertion); unit PASS (compiler 143); helloworld 500, total 77385 |
| T3 | Full rebuild, system tests, size record | T2 | Medium | Done | sonnet run 1 (2026-11-23→24): Blocked (SPEC: test-conflict test_e2e_layout_shift hellowrd/smoke, zero-dot load line); alloc_gap fixture fixed, 5 goldens regenerated (dots only); reset by A1; run 2 sonnet 2026-11-24: Done; A1 compare_masked; run_tests exit 0 (e2e 133 OK, xfail 1 tape); smoke ls/cat/hellowrd/texted/calc/theodore OK; code_size --record 18 rows, helloworld 500 |
| T4 | Docs: compiler page, history, CLAUDE.md, design decisions C5/C9 | T2 | Low | Done | haiku, 2026-11-23; docs only (03-compiler.md, history.txt, bc CLAUDE.md, C5+C9); diff reviewed, in scope |
