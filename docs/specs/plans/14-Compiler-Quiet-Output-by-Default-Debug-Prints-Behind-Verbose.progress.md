# Progress — 14 Compiler: quiet output by default, debug prints behind --verbose

Plan revision: A0

Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Logging helper and quiet compiler (bc.py + bc_ast.py) | — | Medium | Done | sonnet; started 2026-11-12 ~10:05Z, finished ~10:08Z; test-guard PASS; verify.sh UNSUPPORTED → run_tests.py --group unit ALL PASSED; before/after 10/10 basm + verbose stdout + genb identical |
| T2 | Launchers and docs | T1 | Low | Done | haiku; started 2026-11-12 ~10:12Z, finished ~10:14Z; test-guard PASS; run_tests.py --group unit ALL PASSED; full build in temp copy OK, compiler prints 10 summary lines |
