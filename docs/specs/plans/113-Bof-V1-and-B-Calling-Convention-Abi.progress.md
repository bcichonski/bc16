# Progress — 113 BOF v1 and the B calling convention ABI

Plan revision: A1
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | G15 BOF v1 decision + byte-exact hello .o in 07 | — | High | Done | opus, started 17:02, finished 17:06; HELLO.O 100 B; guard PASS, unit PASS (docs only) |
| T2 | G16 ABI + symbol names, C5/C2 notes, 03-compiler reference | T1 | Medium | Done | sonnet, started 17:06, finished 17:08; D6 probe: no truncation (quirk recorded); guard PASS, unit PASS |
| T3 | 02-assembler reference; make 07 and 08 agree with G15/G16 | T1, T2 | Medium | Done | sonnet, started 17:08, finished 17:09; links checked; guard PASS, unit PASS |
| T4 | Split SECT into SECTSTAT 55 / SECTABS 5a everywhere (A1) | T3 | Medium | Done | sonnet, started 18:28, finished 18:33; added by A1; HELLO.O 99 B; guard PASS, full suite PASS |
