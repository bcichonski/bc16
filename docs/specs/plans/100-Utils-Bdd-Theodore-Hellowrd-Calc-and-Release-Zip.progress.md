# Progress — 100 utils.bdd: theodore, hellowrd, bdos calc, release zip

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Port calc to bdos and ship CALC.PRG on utils.bdd, with e2e tests | — | Medium | Done | sonnet, started 12:37 UTC, finished 12:44 UTC; wave 1 test-guard PASS, full suite PASS |
| T2 | Move THEODORE to utils.bdd and add HELLOWRD there; os-side tests and goldens | T1 | Medium | Done | sonnet, started 12:48 UTC, finished 13:11 UTC; wave 2 test-guard PASS (vs base 3fc35bb: wave snapshot tree lost to virtiofs race), full suite PASS; bdos_ls golden hand-edited (--update-golden skipped it, marker first) |
| T3 | Release zip ships utils.bdd | — | Low | Done | haiku, started 12:37 UTC, finished 12:38 UTC; wave 1 test-guard PASS, full suite PASS |
| T4 | Docs | T1, T2, T3 | Low | Done | haiku, started 13:15 UTC, finished 13:23 UTC; wave 3 test-guard PASS, full suite PASS (--no-build, docs only) |
