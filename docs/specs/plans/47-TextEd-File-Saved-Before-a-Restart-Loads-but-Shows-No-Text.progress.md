# Progress — 47 TextEd: file saved before a restart loads but shows no text

Plan revision: A2
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | TextEd load: buffered chunked read, store lines, replace, errors | — | High | Done | rework r1 done 14:20 UTC (docs only: 05-bdos.md TextEd file format, design-decisions D6); test-guard PASS; wave verify: unit PASS, code unchanged since full-suite PASS; rework r1: D1 format not documented (05-bdos.md, design-decisions.md); opus; re-dispatched 14:19 UTC (wave 6); earlier: opus; started 12:11 UTC (wave 1); paused by API rate limit, resumed same agent 13:30 UTC; finished 13:45 UTC; texted.btap 14310 B (fits 112 sectors); spike round trip OK; also fixed 2 insertLineBuf bugs, 80-char input; test-guard PASS; wave verify PASS (run_tests.py all) |
| T2 | Rebuild the system disc with texted and keep TEST.B | T1, T4 | Medium | Done | sonnet; started 13:48 UTC (wave 2) ; finished 13:56 UTC Blocked (SPEC: cat -c output changes on fresh makedisc; stale generated files; CAT.PRG 62 sectors); test-guard PASS; reset by A1 (partial work kept in tree); re-dispatched sonnet 14:00 UTC (wave 4); finished 14:06 UTC Blocked (SPEC: CP.PRG 57 vs 56 breaks expectedFailure cp test); reset by A2; tree already in A2 end state (CP 56) — confirmed by wave barrier instead of no-op re-dispatch; test-guard PASS; wave verify PASS (run_tests.py all, e2e 32 OK) |
| T3 | e2e: save → restart → load scenarios for TextEd | T2 | Medium | Done | reset by A1 (DoD amended); sonnet; started 14:07 UTC (wave 5); finished 14:17 UTC; 5 tests + texted_roundtrip golden, ~42 s; mutation-checked; test-guard PASS; wave verify PASS (run_tests.py all, e2e 37 OK) |
| T4 | cat -c prints text records whole across sector boundaries | — | Medium | Done | added by A1; sonnet; started 13:57 UTC finished 14:00 UTC (wave 3); cat build 62 sectors; spike: records whole, binary -b identical; test-guard PASS; wave verify PASS (unit group; e2e deferred to T2 since the disc is mid-rebuild) |
