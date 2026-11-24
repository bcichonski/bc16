# Progress — 61 FDD: a DMA address whose high byte is 0xf0 is taken as a PING command

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Parameter bytes are data in every multi-byte FDD state | — | Medium | Done | sonnet, started 07:24 UTC, finished 07:38 UTC; test-guard PASS; run_tests.py ALL PASSED (verify.sh UNSUPPORTED for pure Python; 1 pre-existing e2e xfail: tape round trip) |
