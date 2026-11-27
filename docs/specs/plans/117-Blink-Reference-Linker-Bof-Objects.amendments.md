# Amendment requests — 117 blink.py reference linker for BOF objects

## A1 — 2026-11-27 — requested by T3
test-conflict — T3's DoD registers `test_e2e_blink` in `src/tests/e2e_areas.py` under area `assembler`, but the protected test `src/tests/test_areas.py::MapTests.test_assembler_has_no_e2e_module` asserts that area `assembler` has no e2e module — `python3 run_tests.py --group unit` fails with `'assembler' unexpectedly found in ['assembler', 'bcos', 'bdos', 'compiler', 'emulator']`; the e2e test itself passes (`--group e2e --area assembler`: 1 test OK).
