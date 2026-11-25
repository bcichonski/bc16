# Progress — 115 Assembler --obj writes BOF object files

Plan revision: A2
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | BOF v1 module: writer, reader, dump formatter | — | Medium | Done | sonnet, started 2026-11-25 12:04, finished 12:08; wave 1 PASS (test-guard vs 90fe5f1 after snapshot tree vanished; unit ALL PASSED; e2e happy exit 0; 29 flat outputs byte-identical) |
| T2 | Directives .global/.extern/.sect (flat no-ops) and #link occurrences | — | Medium | Done | sonnet, started 2026-11-25 12:04, finished 12:08; wave 1 PASS (test-guard vs 90fe5f1 after snapshot tree vanished; unit ALL PASSED; e2e happy exit 0; 29 flat outputs byte-identical) |
| T3 | Assembler object mode, --obj and --dump | T1, T2 | High | Done | A1 (relocatable .assert -> warning) applied before start; opus, started 2026-11-25 12:09, finished 12:20; wave 2 PASS (test-guard PASS; unit ALL PASSED, assembler 474; 29 flat outputs identical; e2e happy 52 OK; --changed 133 OK + 1 expected failure test_e2e_bcos.test_tape_round_trip #32/#62, master baseline) |
| T4 | Docs: 02-assembler.md, A14, G15/doc 07 clarification, CLAUDE.mds | T3 | Medium | Done | sonnet, started 2026-11-25 12:21, finished 12:24; wave 3 PASS (test-guard PASS, unit ALL PASSED, docs-only diff) |
