# Progress — 69 Compiler unknown-operator error missing attribute

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Raise `CompilerError` for an unknown binary operator, plus unit tests | — | Low | Done | haiku, started 18:42Z, finished 18:51Z Done; test-guard: src/bc/tests/bc_codegen_tests.py (existing import line edited) → restored; retry on sonnet started 18:51Z, finished 19:00Z Done (escalated haiku→sonnet); wave test-guard PASS; run_tests exit 0 (xfail 7: assembler 6, e2e 1), code_size delta +0 |
| T2 | Docs: internal unknown-operator error | — | Low | Done | haiku, started 18:42Z, finished 18:43Z; docs only |
