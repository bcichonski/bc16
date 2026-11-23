# Progress — 34 Spike: hot-path runtime routines

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Static use census and byte model per option | — | Medium | Done | sonnet, started 14:57Z, finished 15:00Z; census.py/census.md, 18 programs ; wave1 guard PASS, run_tests exit 0 (1 xfail) |
| T2 | Built prototypes of each option (temp copy) with real sizes and a smoke run | — | High | Done | opus, started 14:57Z, finished 16:12Z; overrun (74 min, active); prototypes.py/prototypes.md, 5 variants all smoke-pass |
| T3 | Instructions per call and dynamic call counts in the emulator | — | Medium | Done | sonnet, started 14:57Z, finished 15:05Z; dyncount.py/dyncount.md |
| T4 | Write-up with numbers and a recommendation per routine | T1, T2, T3 | Medium | Done | sonnet, started 16:20Z, finished 19:25Z; 34-hot-path-notes.md |
