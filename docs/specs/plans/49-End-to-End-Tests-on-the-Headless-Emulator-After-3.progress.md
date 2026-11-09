# Progress — 49 End-to-End Tests on the Headless Emulator (after #3)

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Emulator `--no-floppy` option | — | Medium | Done | sonnet; started 09:25Z; finished 09:26Z; NoFloppyDrive in bc64_io.py, --no-floppy in bc64.py, tests in test_io.py + test_bc64_cli.py; self-check run_tests OK; wave1 verify PASS (verify.sh UNSUPPORTED; run_tests.py 317/160/58 OK) |
| T2 | E2E harness and golden mechanism | — | Medium | Done | sonnet; started 09:25Z; finished 09:27Z; e2e_harness.py (run_session, check_golden, golden_path, slow, read_catalog, disc_put) + 18 self-tests; wave1 verify PASS |
| T3 | bcOS monitor scenarios | T1, T2 | Medium | Done | sonnet; started 09:27Z; finished 09:28Z; test_e2e_bcos.py: unknown cmd + d/w/p goldens, tape round trip expectedFailure (#32/#62, TypeError in TapeRecorder.read_byte); 0.3 s; agent reported a stray src/bc64.dmp after run_tests (check in verify); wave2 verify PASS (run_tests 328/160/58 OK, e2e modules 35 s, no stray dmp) |
| T4 | bdos shell scenarios | T2 | Medium | Done | sonnet; started 09:27Z; finished 09:31Z; test_e2e_bdos.py: 7 scenarios on smoke.bdd (boot, ls, cat, hellowrd, rm+catalog, errors; cp expectedFailure); ~17 s; wave2 verify PASS (run_tests 328/160/58 OK, e2e modules 35 s, no stray dmp) |
| T5 | Whole-toolchain scenario | T2 | Medium | Done | sonnet; started 09:27Z; finished 09:29Z; test_e2e_toolchain.py + toolchain_prog.b + golden (prints 'toolchain ok', 55, 1037); ~3.5 s; no compiler bugs found; wave2 verify PASS (run_tests 328/160/58 OK, e2e modules 35 s, no stray dmp) |
| T6 | Docs and decision record | T1, T3, T4, T5 | Low | Done | haiku; started 09:31Z; finished 09:35Z; 01-emulator.md, 05-bdos.md, CLAUDE.md, src/bc64/CLAUDE.md, design-decisions E8/E9; documented commands run; wave3 verify PASS (run_tests 328/160/58 OK) |
