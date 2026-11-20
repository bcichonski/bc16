# Progress — 66 Assembler: inc af and dec af don't parse

Plan revision: A1
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Grammar order + reject `inc af`/`dec af` with a clear diagnostic, with tests | — | Medium | Done | sonnet, 10:06–10:17; 252 asm tests (6 xfail, pre-existing), run_tests exit 0 (7 xfail pre-existing), build byte-identical; wave 1 test-guard PASS |
| T2 | Docs: assembler reference, decision A8, assembler CLAUDE.md | — | Low | Done | haiku, Done 10:09 (+rework r1 encoding bytes 5F AD 10); reset by A1; A1 re-run haiku 10:15–10:16 Done ; wave 1 test-guard PASS; rework r1 (verifier): orphan line in 02-assembler.md, stale README limitation — haiku — Done; verification round 2 PASS |
| T3 | Reject every other 16-bit ALU op on `af` (A1), with tests | T1 | Medium | Done | added by A1; sonnet, 10:18–10:26; asm 257 (6 xfail #11), run_tests exit 0 (1 e2e xfail test_tape_round_trip), byte-identical, revert-checked; wave 2 test-guard PASS |
