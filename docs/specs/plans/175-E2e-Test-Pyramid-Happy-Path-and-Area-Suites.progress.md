# Progress — 175 Test Pyramid: Happy-Path E2E on PRs, Full E2E per Area on Master

Plan revision: A3
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Area map, happy list, trigger rules and selector CLI | — | Medium | Done | sonnet, started 08:35, finished 08:37; guard PASS (snapshot vanished, checked vs base accc5c5); unit PASS |
| T2 | run_tests.py: --tier, --area, --jobs | T1 | High | Done | opus, started 08:41, finished 09:02; guard PASS; unit PASS; agent ran full (133, xfail 1) jobs1 516 s / default 136 s, happy 52 tests 46.6 s seq |
| T3 | CI workflow: happy job on PRs, per-area matrix on master | T1, T2 | Medium | Done | sonnet, started 09:04, finished 09:06; actionlint clean; guard PASS; unit PASS |
| T4 | Docs: test pyramid (README), CLAUDE.md, 01-emulator, G13 | T2, T3 | Medium | Done | sonnet, started 09:08, finished 09:11; guard PASS; unit PASS |
| T5 | P3 analysis: merge candidates | — | Low | Done | haiku, started 08:35, finished 08:39; guard PASS |
| T6 | run_tests.py --changed REF (A1) | T2 | Medium | Done | sonnet, started 09:20, finished 09:23; guard PASS; unit PASS |
| T7 | Docs: development loop, full suite only before the PR (A1) | T6, T4 | Low | Done | haiku, started 09:25, finished 09:29; guard PASS |
| T8 | CI: never cancel master runs (A2) | T3 | Low | Done | haiku, started 09:36, finished 09:37; reset by A3; haiku re-dispatch 09:41, finished 09:42; actionlint clean; guard PASS; unit PASS |
