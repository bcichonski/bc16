# Progress — 37 bdos: build os.bdd from a disc manifest (ftool mkdisc)

Plan revision: A3
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | `ftool mkdisc`: manifest, placement, catalog v1, errors + unit tests | — | High | Done | opus, started 12:36Z, finished 12:40Z; wave 1 test-guard PASS, unit suite PASS (verify.sh UNSUPPORTED for this pure-Python repo; check = run_tests.py) |
| T2 | System disc from `disc.manifest`: makedisc, new os.bdd, smoke disc, layout-pinned tests | T1 | Medium | Done | sonnet, started 12:40Z, finished 12:47Z: Blocked (SPEC: .gitignore *.manifest ignores src/disc.manifest; bdos_hellowrd golden not in Tests to modify); reset by A1; re-dispatched sonnet 12:47Z; A2 (owner: .bddmanifest) relayed to the running agent (wave 2b, snapshot taken after the first attempt's edits); finished 12:58Z; wave 2 test-guard PASS, full run_tests PASS |
| T3 | e2e: new disc boots, `ls -a` shows every file with real sizes, every utility runs | T2 | Medium | Done | sonnet, started 12:58Z, finished 13:05Z; wave 3 test-guard PASS, full run_tests PASS |
| T4 | Docs: building os.bdd, layout, contracts, new-program steps, known failures | T2 | Low | Done | haiku, started 12:58Z, finished 13:00Z; wave 3 test-guard PASS, full run_tests PASS |
