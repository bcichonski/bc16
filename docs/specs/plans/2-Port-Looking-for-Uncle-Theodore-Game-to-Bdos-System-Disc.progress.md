# Progress — 2 Port "Looking for uncle Theodore" game to the bdos system disc

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Emulator `--random-seed` option + harness support | — | Medium | Done | sonnet, started 11:33Z, finished 11:38Z; guard PASS; run_tests PASS |
| T2 | bdos `BDIO_RANDOM` system call + `random.b` include, rebuilt bdos and disc | T1 | Medium | Done | sonnet, started 11:41Z, finished 11:47Z; bdos 0x0f00..0x53be, ROM/boot identical; guard PASS; run_tests PASS |
| T3 | theodore v1.1 on the system disc | T2 | Medium | Done | sonnet, started 11:50Z, finished 12:00Z; THEODORE 38 sectors at 53/0; full rebuild reproduces os.bdd; guard PASS; run_tests PASS |
| T4 | Docs: programs, disc layout, roadmap step 4 | T3 | Low | Done | haiku, started 12:03Z, finished 12:05Z; guard PASS; run_tests --group unit PASS (docs only) |
