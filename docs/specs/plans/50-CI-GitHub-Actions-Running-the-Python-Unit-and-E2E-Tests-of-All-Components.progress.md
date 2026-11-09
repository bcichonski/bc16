# Progress — 50 CI: GitHub Actions running the Python unit and e2e tests

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Runner: component suites, `--group`, job summary | — | Medium | Done | sonnet, started 09:58, finished 10:02; guard PASS; run_tests PASS (3.14 + 3.10 docker); verify.sh n/a (UNSUPPORTED, pure Python) |
| T2 | Workflow `tests.yml` (unit matrix, e2e with smoke refresh and failure artifact) | T1 | Medium | Done | sonnet, started 10:05, finished 10:10; actionlint clean; steps dry-run green; artifact patch proven non-empty; guard PASS |
| T3 | Docs: badge, CI rules in `CLAUDE.md`, toolchain analysis | T2 | Low | Done | haiku, started 10:12, finished 10:14; docs only, reviewed diff; guard PASS; rework r1: stale CLAUDE.md smoke/e2e suite statement (haiku, started 10:20, finished 10:21; guard PASS; run_tests PASS; verification r2 PASS) |
