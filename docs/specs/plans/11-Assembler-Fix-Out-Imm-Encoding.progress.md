# Progress — 11 Assembler: fix `out #r, imm` encoding

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Encode `out #r, 0xHH` as `Dr HH`, reject other port registers | — | Medium | Done | rework r1: stale #11 comment (agreement tests:251); sonnet, 18:52–18:53 UTC, comments reworded; test-guard PASS, run_tests.py exit 0 (1 xfail #32/#62). Earlier: sonnet, started 18:39 UTC, finished 18:42 UTC; Dr HH + rejection, 6 xfails now real; byte-identical build. Wave: test-guard PASS, run_tests.py exit 0 (1 xfail: tape round trip #32/#62) |
| T2 | Docs: instruction table, quirks, CLAUDE.md files, analysis, decision A10 | — | Low | Done | haiku, started 18:39 UTC, finished 18:40 UTC; docs in 8 files, A10 added |
