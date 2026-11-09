# Progress — 3 Emulator Headless Mode: Disks, Tape, Keyboard and Output from the Command Line

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Scripted environment | — | Medium | Done | sonnet; started 08:45Z; finished 08:47Z; ScriptedEnvironment + EndOfInput in bc64_env.py; self-check run_tests OK; wave1 verify PASS (verify.sh UNSUPPORTED → verifier haiku) |
| T2 | Command line, limited run and exit codes | T1 | Medium | Done | sonnet; started 08:48Z; plan D3 amended by owner before start (piped stdin = keys); finished 08:50Z; argparse CLI + limited run + exit codes 0/1/2/3, test_bc64_cli.py (24 tests); also changed T1's EndOfInput to BaseException so the CPU's except Exception doesn't print a stack at end of input; self-check run_tests OK + manual piped sessions OK; wave2 verify PASS (verifier haiku) |
| T3 | End-to-end smoke test with expected transcript | T2 | Medium | Done | sonnet; started 08:50Z; finished 08:51Z; test_bc64_smoke.py + testdata (script, transcript, .gitattributes -text); ~7 s; self-check run_tests OK; wave3 verify PASS |
| T4 | Docs and decision record | T2 | Low | Done | haiku; started 08:50Z; finished 08:53Z; 01-emulator.md, CLAUDE.md, src/bc64/CLAUDE.md, design-decisions E7; example run checked; wave3 verify PASS (run_tests.py: 293/160/58 OK, python 3.14 only in sandbox; protected files unchanged) |
