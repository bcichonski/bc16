# Progress — 8 Assembler Modernisation: .assert Directive to Enforce Memory-Map and ABI Addresses

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | `.assert` directive in the assembler | — | Medium | Done | sonnet, started 2026-11-10 15:06, finished 15:09; ASSERT node + pass-2 eval, bc81asmc_assert_tests.py (25); wave 1: test-guard PASS, run_tests ALL PASSED |
| T2 | Boot-loader asserts and the bcOS contract test | T1 | Medium | Done | sonnet, started 2026-11-10 15:10 , finished 15:13; boot.basm bd_end assert (btap identical), bc81asmc_contract_tests.py (5); wave 2: test-guard PASS, run_tests ALL PASSED |
| T3 | Compiler-emitted asserts, `#codelimit`, regenerated `.basm` | T1 | Medium | Done | sonnet, started 2026-11-10 15:10 , finished 15:15; sys_codeend assert + #codelimit, bdos.b 0x5d00, 9 .basm regenerated (btaps identical), bc_assert_tests.py; wave 2: test-guard PASS, run_tests ALL PASSED |
| T4 | Documentation and decision records | T2, T3 | Low | Done | haiku, started 2026-11-10 15:17 , finished 15:20; 8 doc files (02-assembler, 03-compiler, design-decisions A2/A3/A6/G2, 3 CLAUDE.md, analysis, root CLAUDE.md); wave 3: test-guard PASS, run_tests ALL PASSED |
