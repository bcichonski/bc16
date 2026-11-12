# Progress — 12 Replace the Python 3.7 Pipfile with a top-level pyproject.toml

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | pyproject.toml, launcher module and its tests; delete the old declarations | — | Medium | Done | sonnet, started 13:44 UTC, finished 13:47 UTC; 9 new launcher tests; test-guard PASS; run_tests.py ALL PASSED (wave 1) |
| T2 | CI installs the project and checks the four commands | T1 | Low | Done | haiku, started 13:49 UTC, finished 13:50 UTC; actionlint clean (awaiting wave barrier) |
| T3 | Docs and design decisions show the new install, run and test commands | T1 | Medium | Done | sonnet, started 13:49 UTC, finished 13:52 UTC; 13 docs updated, commands checked in python:3.14-slim venv; grep clean (awaiting wave barrier); rework r1: CI bullet claims both jobs check the commands — sonnet, started 14:03 UTC, finished 14:04 UTC; test-guard PASS |
| T4 | Acceptance checks: fresh venv on 3.10/3.14, all suites, byte-identical rebuild | T1 | Medium | Done | sonnet, started 13:49 UTC, finished 13:58 UTC; 3.10 + 3.14 fresh venv: pip install -e OK, 4 commands OK from /tmp, run_tests ALL PASSED (338/11/203/58/39) on both; rebuild new cmds vs old: 52 outputs byte-identical; vs commit: only pre-existing bcos.btap drift (+ CRLF-only .basm from autocrlf checkout) |
