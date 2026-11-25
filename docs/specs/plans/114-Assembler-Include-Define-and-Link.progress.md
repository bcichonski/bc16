# Progress — 114 Assembler: #include and #define from header files, and #link

Plan revision: A2
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Pre-pass: `#include`, `#define`, `#link`, header diagnostics and warnings | — | Medium | Done | sonnet; started 2026-11-25 10:35 UTC; finished 10:39 UTC; test-guard PASS; unit PASS (assembler 383); happy e2e PASS (agent). Directive lines become `;` lines for the parser (blank lines are a syntax error) |
| T2 | Defined names in numeric operands, width checks, operand diagnostics | T1 | Medium | Done | sonnet; started 2026-11-25 10:45 UTC; finished 10:53 UTC; test-guard PASS; unit PASS (assembler 409); happy + changed e2e PASS (agent; changed: 1 expected failure, tape round trip #32/#62) |
| T3 | Docs: `02-assembler.md`, decision A13, assembler `CLAUDE.md` | T2 | Low | Done | haiku; started 2026-11-25 10:56 UTC; finished 10:58 UTC; test-guard PASS; unit PASS (agent); docs only; rework r1 (verifier round 2): A13 "(Dn)" plan-id refs clash with bdos D1..D12; CLAUDE.md "blanked" vs ";" lines — haiku 11:55 UTC; rework r1 done 11:57 UTC, test-guard PASS, unit PASS |
| T4 | Library `.h` headers in `src/bdos/` (Amended in A1) | T2 | Medium | Done | added by A1; sonnet; started 2026-11-25 11:20 UTC; finished 11:28 UTC: Blocked (SPEC: test-conflict: 4 e2e copy steps, test_check_memory_map copy, printexecres_body); reset by A2; sonnet re-dispatch (no escalation) 11:35 UTC; finished 11:42 UTC; test-guard PASS (A1/A2 allowlist); unit/happy/changed PASS; byte-identical build; code_size --check: 11 programs "code changed, same size" (+0 B; LABELnnnn renumbering from prototypes) — recorded at finalize |
