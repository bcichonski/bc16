# Progress — 56 CPU/ISA register forms of SHL/SHR

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | CPU: tests for register-count shifts + corrected op_CLC comment | — | Medium | Done | sonnet, started 14:12, finished 14:13; replaced pinned test with test_single_byte_5d_5e_are_inc_dec + 6 ShiftFlagTests register-count tests |
| T2 | Assembler: emit tests for shl r / shr r | — | Low | Done | haiku, started 14:12, finished 14:13; TestShiftRegisterForms (4 emit) + TestShiftRegisterGrammar (2 parse) |
| T3 | Docs + design decision E15 | — | Low | Done | haiku, started 14:12, finished 14:14; rework r1 (haiku): broken E12 link in E15 -> in-file anchor |
