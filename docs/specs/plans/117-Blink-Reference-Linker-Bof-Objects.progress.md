# Progress — 117 blink.py reference linker for BOF objects

Plan revision: A1
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Pass 1, mark and layout | — | High | Done | opus, started 12:49, finished 12:55; guard PASS, unit PASS (48 tests) 2026-11-27 (unblocked: #116 merged) |
| T2 | Pass 2, output and CLI | T1 | High | Done | opus, started 12:55, finished 13:01; guard PASS, unit PASS (86 blink tests) |
| T3 | AC-1 e2e: runtime.basm + hello.basm linked and run | T2 | Medium | Done | sonnet, started 13:01, finished 13:04; e2e --area assembler PASS (1 test), unit FAIL 1 (the protected test); reset by A1 (area compiler); sonnet re-dispatch started 13:04, finished 13:05; guard PASS, unit PASS, e2e --area compiler PASS |
| T4 | Docs: linker section in docs/03-compiler.md, G17 | T2 | Low | Done | haiku, started 13:01, finished 13:03; G17; doc diff reviewed (in scope) |
