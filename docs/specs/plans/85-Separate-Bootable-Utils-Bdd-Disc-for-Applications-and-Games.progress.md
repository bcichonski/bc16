# Progress — 85 Separate bootable utils.bdd disc for applications and games

Plan revision: A0
Wave snapshot: —

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Build utils.bdd from a second manifest, with structure and solo-boot tests | — | Medium | Done | sonnet; started 2026-11-12 15:25 UTC; finished 15:33 UTC; test-guard PASS; verify (run_tests.py) PASS — ALL PASSED |
| T2 | Run every TextEd e2e test in the default A/B setup | T1 | Medium | Done | sonnet; started 2026-11-12 15:45 UTC; finished 15:58 UTC; test-guard PASS; verify (run_tests.py) PASS — ALL PASSED |
| T3 | Remove TEXTED from os.bdd, update os-side tests and goldens | T2 | Medium | Done | sonnet; started 2026-11-12 16:05 UTC; finished 16:26 UTC; bdos_ls golden hand-edited (update mode stopped at a marker); test-guard PASS; verify PASS — ALL PASSED |
| T4 | Docs: two-disc layout, default A/B session, pipeline | T3 | Low | Done | haiku; started 2026-11-12 16:35 UTC; finished 16:38 UTC; test-guard PASS; unit PASS (docs only); rework r1: TEXTED at= claim in 05-bdos.md (haiku, 16:55–16:57 UTC), verify PASS |
