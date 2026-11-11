# Progress — 90 Build cleanup: GitHub Release zips, committed-output rules, tests in <tool>/tests

Plan revision: A1
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Move every tool's tests into its tests/ folder; run_tests.py, CI and docs follow | — | Medium | Done | sonnet, started 14:25 UTC, finished 14:37 UTC; baseline emulator 345/3xf, ftool 84, assembler 231/7xf, compiler 64, e2e 63/1xf — same after move; test-guard PASS; run_tests ALL PASSED (wave 1); committed b19c4d7 |
| T2 | Ignore rules, untracking, stale files, CI build step + guards, run_tests.py hint | T1 | Medium | Done | sonnet, started 14:41 UTC, finished 14:51 UTC; 44 files untracked, 4 stale deleted; temporary `!release/**` negation (T5 removes it + release guards); run_tests hint + 5 tests; fresh-clone checks a/b/c OK; test-guard PASS; run_tests ALL PASSED 350/84/231/66/63 (wave 2); committed cc79433 |
| T3 | Generated .basm header in bc.py | T1 | Low | Done | haiku, started 14:41 UTC, finished 14:42 UTC; header added in main(); 2 new tests; test-guard PASS; wave 2 ALL PASSED; committed 7ba4e54 |
| T4 | scripts/make_release.py (bc64 + legacy zips, notes), its tests and release.yml | T2 | High | Done | opus, started 14:56 UTC, finished 15:05 UTC; 36 tests in scripts/tests; release suite (unit); release.yml build+publish jobs; tests.yml unit fetch-depth 0; zips boot (bc64 headless, bc16 pty); test-guard PASS; wave 3 ALL PASSED; committed; reset by A1 (bc32 ROM from 6304761); A1 re-run: opus, started 15:36 UTC, finished 15:42 UTC; bc32 ROM from 6304761, 37 release tests, bc32 zip boots bDOS 1.0; test-guard PASS; release suite OK |
| T5 | Delete release/, drop the release guard, rewrite the docs and G9 | T3, T4 | Medium | Done | sonnet, started 15:10 UTC, finished 15:16 UTC; release/ deleted, guards + gitignore TODO removed; README Releases + owner publish steps; G9 rewritten, G12 added, G3 reworded; test-guard PASS; wave 4 ALL PASSED; committed |
| T6 | Acceptance checks: fresh clone, full pipeline, three zips booted, actionlint | T5 | Medium | Done | sonnet, started 15:20 UTC, finished 15:31 UTC: Blocked (SPEC: wrong-fact bc32 ROM 7d4cda9 crashes, 6304761 boots); checks 1-4, 5 (3.14), 6 bc64/bc16 (hello world from tape), 7 OK; reset by A1; A1 re-run: sonnet, started 15:44 UTC, finished 16:00 UTC; checks 1-7 PASS on 34db31e (3.14 + 3.10 ALL PASSED 351/84/231/66/37/63; bc64/bc32/bc16 zips boot; pipeline clean status; actionlint clean) |
