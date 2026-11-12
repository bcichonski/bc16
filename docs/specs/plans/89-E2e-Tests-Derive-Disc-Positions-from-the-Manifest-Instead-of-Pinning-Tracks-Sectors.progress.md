# Progress — 89 E2E tests: derive disc positions from the manifest

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Harness: DISC_MASKS, manifest helpers, ls_line; derive HELLOWRD in the harness self-test | — | Medium | Done | sonnet, started 11:45, finished 11:53; test-guard PASS; run_tests.py PASS (wave 1); rework r1: tests depend on BC64_UPDATE_GOLDEN (sonnet, 12:42–12:54; test-guard PASS; --update-golden + full run ALL PASSED) |
| T2 | Derived expectations and masked goldens in the e2e modules and the smoke test; regenerate stored goldens | T1 | Medium | Done | sonnet, started 11:57, finished 12:09; test-guard PASS; run_tests.py PASS (wave 2) |
| T3 | run_tests.py --update-golden and CI regenerate step | — | Medium | Done | sonnet, started 11:45, finished 11:47; test-guard PASS; run_tests.py PASS (wave 1) |
| T4 | Layout-shift e2e test (automated AC1) | T1, T2 | Medium | Done | sonnet, started 12:12, finished 12:18; test-guard PASS; run_tests.py --group e2e PASS (wave 3) |
| T5 | Docs: masks, derived expectations and the refresh command | T2, T3, T4 | Low | Done | haiku, started 12:22, finished 12:23; docs only; test-guard PASS |
