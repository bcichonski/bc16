# Progress — 59 CPU RET With Push Frames: Single Push Stops the CPU

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | CPU: RET stops on a single push frame + tests | — | Medium | Done | sonnet; started 2026-11-20 UTC; finished 2026-11-20 UTC (~9 min); new src/bc64/tests/test_cpu_ret_frames.py; wave 1 test-guard PASS, run_tests.py exit 0 (assembler 6 / e2e 1 expected failures, pre-existing) |
| T2 | Document the RET rule | — | Low | Done | haiku; started 2026-11-20 UTC; finished 2026-11-20 UTC; docs in 01-emulator, E4, bc64/CLAUDE.md, roadmap step 10; wave 1 PASS |
