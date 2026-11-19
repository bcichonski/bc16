# Progress — 111 bdos rm overwrite and ls free count

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Correct free position after rm + e2e for the three rm positions | — | High | Done | opus, started 12:06, finished 12:18 UTC; root cause: scanmem `<< 4` → `<< 8` only (rm.b unchanged); new test_e2e_rm_alloc.py (3 scenarios, create via `cp ls.prg new.prg`); test-guard PASS; barrier full run ALL PASSED (e2e 108) |
| T2 | `ls` free-sector count + e2e with known layouts | — | Low | Done | haiku, started 12:00, finished 12:06 UTC; test-guard PASS; agent full run ALL PASSED (e2e 105), re-verified at the T1 barrier; built os.bdd ends 36/10 (438 free), plan's 52/02 example is from the old layout |
| T3 | Document the free-position computation | T1, T2 | Low | Done | haiku, finished 12:24 UTC; docs only (05-bdos Allocation, 07 rows 1-2); test-guard PASS |
