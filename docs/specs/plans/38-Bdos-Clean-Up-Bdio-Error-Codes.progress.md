# Progress — 38 bdos: clean up bdio error codes (duplicates and collisions)

Plan revision: A1
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Renumber codes, messages for changed codes, check test, rebuild | — | Medium | Done | sonnet, started 08:54 UTC; A1 scope change relayed to the running agent ~09:00 UTC; finished 09:08 UTC; test-guard PASS; unit PASS (agent full run exit 0) |
| T2 | e2e test of the by-hand error paths | T1 | Low | Done | haiku, started 09:09 UTC, finished 09:16 UTC; test-guard PASS; e2e --no-build PASS (agent) |
| T3 | Docs: error table and G7 | — | Low | Done | haiku, started 08:54 UTC, finished 08:57 UTC; reset by A1; re-dispatched haiku, finished 09:05 UTC test-guard PASS, wave verified |
