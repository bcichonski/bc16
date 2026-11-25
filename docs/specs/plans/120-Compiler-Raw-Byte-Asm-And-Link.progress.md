# Progress — 120 Compiler: raw-byte asm statement and #link

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Assembler: `.db hi(:name)` / `lo(:name)` | — | Medium | Done | sonnet, started 18:38, finished 18:43; test-guard PASS (vs base ref: wave snapshot tree vanished, virtiofs); unit PASS (verify.sh UNSUPPORTED → run_tests.py --group unit); rework r1: .db docs row missing comma before :label (sonnet), done 19:02, test-guard PASS, full suite PASS |
| T2 | Compiler: raw-byte `asm` statement and `#link` | T1 | Medium | Done | sonnet, started 18:43, finished 18:49; wave 2 test-guard PASS (vs base ref), unit PASS |
| T3 | Docs: compiler reference and decision C10 | T1 | Low | Done | haiku, started 18:43, finished 18:44 wave 2 PASS; review: B example uses `;` instead of `//` for comments; rework r1: B example comments ; -> // (haiku), done 19:02, test-guard PASS, full suite PASS |
