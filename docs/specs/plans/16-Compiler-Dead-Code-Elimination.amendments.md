# Amendment requests — 16 Compiler: dead-code elimination

## A1 — 2026-11-24 — requested by T3
test-conflict — src/tests/test_e2e_layout_shift.py :: LayoutShiftTests.test_hellowrd_scenario_matches_golden and ::test_smoke_session_matches_transcript fail after the goldens were regenerated — evidence: HELLOWRD.PRG now loads in under 8 sectors, so it prints zero progress dots (an empty line, which DISC_MASKS' `^\.+$` mask leaves empty); the layout-shift disc grows HELLOWRD by 8 sectors, so it prints one dot line → `<dots>`; diff `+<dots>` at bdos_hellowrd line 11 and smoke_transcript line 45 (log scratchpad/t3_run2.log). Not in T3's Tests to modify; plan §1.2 trial did not see it because the trial goldens were not regenerated.
