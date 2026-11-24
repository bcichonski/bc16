# Progress — 5 Shared bc8183 ISA Table for the Emulator and the Assembler

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Shared ISA module with the form table, and its unit tests | — | High | Done | opus, started 10:21, finished 10:27 UTC; test-guard PASS; unit PASS (1220 tests) |
| T2 | Emulator uses the ISA | T1 | Medium | Done | sonnet, started 10:29, paused by usage limit 10:3x–12:01, finished 12:04 UTC; agent self-check: unit PASS; wave 2 test-guard PASS, unit PASS, e2e --changed PASS (133, 1 xfail tape) |
| T3 | Assembler uses the ISA | T1 | Medium | Done | sonnet, started 10:29, paused by usage limit until 12:01, finished 12:06 UTC; code_size delta 0; wave 2 test-guard PASS, unit PASS, e2e --changed PASS |
| T4 | Single-source and form-table guard tests, byte-identity check | T2, T3 | Medium | Done | sonnet, started 12:10, finished 12:16 UTC; 28/28 built files identical to base, code_size +0, happy e2e 52 OK; wave 3 test-guard PASS, unit PASS |
| T5 | Docs, CLAUDE.md files, design decision G14, analysis notes | T2, T3 | Medium | Done | sonnet, started 12:10, finished 12:12 UTC; wave 3 test-guard PASS, unit PASS |
