# Progress — 64 Assembler label or .def at address 0x0000 reported as not defined

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Regression tests: address-0 targets across every reference kind | — | Low | Done | haiku, started 09:36, finished 09:40; 9 tests (TestAddressZeroTargets), mutation-checked; wave 1 test-guard PASS, run_tests.py exit 0 (verify.sh UNSUPPORTED → run_tests.py) |
| T2 | Docs: address 0 is a valid label / `.def` value | — | Low | Done | haiku, started 09:36, finished 09:37; docs/02-assembler.md Labels bullet + undefined-label row; wave 1 PASS |
