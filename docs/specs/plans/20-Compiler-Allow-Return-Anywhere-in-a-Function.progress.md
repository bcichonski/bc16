# Progress — 20 Compiler: allow return anywhere in a function

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Compiler: single trailing ret, return guard, codegen tests, size record | — | Medium | Done | sonnet, started/finished 2026-11-23; test-guard PASS; compiler suite OK; agent full run_tests exit 0 (1 xfail: test_tape_round_trip #32/#62); size -292 B |
| T2 | e2e test: early returns in the emulator keep values and sys_stackhead | T1 | Medium | Done | sonnet, started/finished 2026-11-23; test-guard PASS; agent full run_tests exit 0 (e2e 124, 1 xfail test_tape_round_trip) |
| T3 | Docs: drop the restriction, decision C8 | T1 | Low | Done | haiku, started/finished 2026-11-23; decision C8 (free on origin/master); diff reviewed, in scope |
