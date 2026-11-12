# Progress — 7 Emulator memory must be the full 64 KB (0x0000–0xffff)

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | 64 KB memory, constants, KIL at 0xffff, full dump | — | Medium | Done | sonnet, started 10:44 UTC, finished 10:49 UTC; test-guard PASS; run_tests.py ALL PASSED (wave 1) |
| T2 | Clean stop on stack access outside memory; empty-stack dump; DMA wrap | T1 | Medium | Done | sonnet, started 10:50 UTC, finished 10:57 UTC; test-guard PASS; run_tests.py ALL PASSED (wave 2). Finding: monitor q is not an empty-stack RET — it prints 'fatal error F0 at FF0C' and halts via bcOS KIL; d 00 is an empty-stack RET (stderr stop line) |
| T3 | End-to-end: monitor q / bad-argument stop cleanly; memory-map rebuild check | T2 | Medium | Done | sonnet, started 10:59 UTC, finished 11:03 UTC; test-guard PASS (docstring allowed); run_tests.py ALL PASSED (wave 3); smoke transcript identical; rebuild: only pre-existing bcos.btap drift, identical to base rebuild |
| T4 | Docs and design decisions agree with the code | T2 | Low | Done | haiku, started 10:59 UTC, finished 11:01 UTC; test-guard PASS; run_tests.py ALL PASSED (wave 3) |
