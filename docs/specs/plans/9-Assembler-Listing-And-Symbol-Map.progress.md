# Progress — 9 Assembler Listing and Symbol Map

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Assembler: `--lst`/`--map` output and map reader | — | Medium | Done | sonnet; started 17:05, finished 17:08 UTC; guard PASS, unit PASS (assembler 347) |
| T2 | Build scripts, `bcc` command and `.gitignore` | T1 | Low | Done | haiku; started 17:12, finished 17:13 UTC; guard PASS, unit PASS |
| T3 | G2 memory-map check script and its test | T1 | Medium | Done | sonnet; started 17:12, finished 17:14 UTC; guard PASS, unit PASS (release 79), check_memory_map OK on built tree |
| T4 | Docs: assembler doc, design decisions, CLAUDE.md files | T1, T2, T3 | Low | Done | haiku; started 17:16, finished 17:18 UTC; guard PASS, unit PASS |
