# Progress — 41 bdos: reuse free disc space (largest free gap)

Plan revision: A2
Wave snapshot: 750e082d536ff9dec90a627b201243126fe96202 bc16

| Task | Title | Depends on | Complexity | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | bdio: largest-gap allocation, reserved area, disc full; ls and cp | — | High | Done | opus, started 13:57 UTC, finished 13:59 UTC; no files changed ; SPEC block (test_bdioh_codes free range) → reset by A1; re-dispatched opus 14:03 UTC ; finished 14:20 UTC; test-guard PASS (vs base, snapshot tree vanished); run_tests exit 0 (1 xfail: tape round trip #32/#62, pre-existing) |
| T2 | TextEd s reports disc full | T1 | Medium | Done | sonnet, started 14:22 UTC ; returned Blocked only because T4's in-flight test failed in its full run; wave barrier: test-guard PASS, run_tests exit 0 (1 xfail tape) |
| T3 | e2e: compile-pattern create/delete cycles don't fill the disc | T1 | Medium | Done | sonnet, started 14:45 UTC ; finished 15:11 UTC; test-guard PASS; agent full run exit 0 (1 xfail tape); new test ~170-190 s |
| T4 | ftool importtext uses the largest gap; reserved-range cross-check test | T1 | Medium | Done | sonnet, started 14:22, finished 14:25 UTC; rest of T4 implemented ; reset by A2; re-dispatched sonnet 14:27 UTC ; finished 14:29 UTC; unit exit 0 (wave barrier PASS) |
| T5 | Docs, design decision D11, code-size record | T1, T2, T3, T4 | Low | In progress | haiku, started 15:13 UTC |
