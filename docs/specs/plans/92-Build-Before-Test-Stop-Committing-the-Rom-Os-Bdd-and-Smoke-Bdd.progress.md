# Progress — 92 Build before test: stop committing the ROM, os.bdd and smoke.bdd

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | run_tests.py builds before e2e, --no-build | — | Medium | Done | sonnet, started 09:06, finished 09:08; test-guard PASS; run_tests.py PASS (wave 1) |
| T2 | e2e tests boot only the freshly built os.bdd; real-ROM tests move to e2e | — | Medium | Done | sonnet, started 09:06, finished 09:12; test-guard PASS; run_tests.py PASS (wave 1) |
| T3 | make_release.py bc64 zips the built ROM and os.bdd | — | Medium | Done | sonnet, started 09:06, finished 09:07; test-guard PASS; run_tests.py PASS (wave 1) |
| T4 | src/run prints the build command when outputs are missing | — | Low | Done | haiku, started 09:06, finished 09:07; test-guard PASS; run_tests.py PASS (wave 1) |
| T5 | Untrack the binaries, .gitignore, CI workflows | T1, T2, T3 | Medium | Done | sonnet, started 09:20, finished 09:29; test-guard PASS; agent ran run_tests.py ALL PASSED + fresh-clone CI e2e simulation + actionlint |
| T6 | Docs describe the build-before-test rule | T1, T2, T3, T4, T5 | Medium | Done | sonnet, started 09:31, finished 09:33; docs only; test-guard PASS |
