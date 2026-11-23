# Progress — 43 bdos: shared argument-parsing library

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Command-table e2e test and golden recorded on the unported tools | — | Medium | Done | sonnet; started 10:37Z, finished 11:04Z; test-guard PASS; run_tests exit 0 (1 xfail: bcos tape round trip #32/#62); golden sha256 9e26ed02…; committed |
| T2 | `bdosargs.b` library; port `cp`, `rm`, `cha`, `cat` | T1 | High | Done | opus; started 11:04Z, finished 11:18Z; test-guard PASS; run_tests exit 0 (1 xfail #32/#62); golden unchanged; sizes cp +628 rm +507 cha +548 cat +469 (D-3 expectation 'should shrink' wrong); cp keeps terminator before target word; committed |
| T3 | Port `ls` and `format` | T2 | Medium | Done | sonnet; started 11:18Z, interrupted by API rate limit, resumed 13:52Z, finished 14:05Z; test-guard PASS; run_tests exit 0 (1 xfail #32/#62); golden unchanged; sizes ls +992 format +970; committed |
| T4 | Size report, docs and decision D10 | T3 | Low | Done | haiku; started 13:59Z, finished 14:03Z; after merge of origin/master 4befc1d; decision id D11 (D10 taken by #112); code_size --record once (6 rows); unit exit 0; committed; rework r1: D11 cites plan-local ids; haiku 14:12Z–14:14Z Done (out-of-scope D10 edits reverted by orchestrator); committed |
