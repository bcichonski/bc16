# Amendment requests — #41

## A1 — 2026-11-23 — requested by T1
test-conflict — add `src/tests/test_bdioh_codes.py :: BdiohCodesTests.test_retired_and_free_values_are_not_used` to T1's Tests to modify, so the free range becomes 0xf4..0xfe and 0xf3 is allowed as `BDIO_FILE_DISC_FULL` — evidence: the test asserts no `BDIO_FILE_*`/… code >= 0xe0 lies in 0xf3..0xfe; the plan (§2.4, Decision 5, §3.1) assigns `BDIO_FILE_DISC_FULL = 0xf3` with that prefix on purpose; T1 currently lists Tests to modify: None.

## A2 — 2026-11-23 — requested by T4
test-conflict — add `src/tests/test_ftool_text.py :: CatalogTests.test_free_sector_uses_track_times_16` to T4's Tests to modify — evidence: the test puts one file at 62/0 length 8 and asserts the import lands at 62/8 (append-only); under the largest-gap rule the run 12/0..61/15 is longest, so the import goes to 12/0. Suggested rewrite: fill 12/0..61/15 so the tail at 62/8 is the largest gap, keeping the track*16 guard.
