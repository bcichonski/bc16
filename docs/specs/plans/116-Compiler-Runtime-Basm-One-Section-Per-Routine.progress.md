# Progress — 116 Compiler runtime in runtime.basm, one section per routine

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | runtime.basm, the loader, RUNTIME.O build, tests | — | Medium | Done | sonnet; started 2026-11-25 13:13 UTC; finished 13:19 UTC; deviation: asm_labels moved to new bc_labels.py (circular import), bc_ast re-exports; test-guard PASS; verify.sh UNSUPPORTED -> haiku verifier PASS (unit 1517, happy 52, changed 132 + 1 xfail test_tape_round_trip; code_size +0) |
| T2 | Docs: compiler doc, src/bc/CLAUDE.md, C11, root CLAUDE.md | T1 | Low | Done | haiku; started 2026-11-25 13:23 UTC; finished 13:25 UTC; docs only (4 files); test-guard PASS; unit exit 0 |
