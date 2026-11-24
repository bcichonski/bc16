# Amendment requests — 175

## A1 — 2026-11-24 — requested by owner (mid-run message)
missing-task — Local development runs unit tests + the happy-path e2e tier + the e2e areas affected by the change; the full suite (`python3 run_tests.py`) runs only once, just before pushing the PR. Add a `run_tests.py` option that selects the affected areas from the changes against a base ref (committed and uncommitted) using the T1 trigger rules, and document the development loop in README "Testing", root CLAUDE.md and G13 — evidence: owner message "also can we adjust the development to run the full suite only just before pushing the PR, and satisfy with areas / happy paths before?"

## A2 — 2026-11-24 — requested by verifier
contradiction — Master e2e selection can silently skip areas: `concurrency` has `cancel-in-progress: true` for every ref, so push A (e.g. bdos change) cancelled by a quick push B (docs only) leaves A's changes never e2e-tested, because B's `e2e-areas` diffs only `github.event.before..github.sha`. Limit cancel-in-progress to PR refs (or compute the base from the last successful run) — evidence: `.github/workflows/tests.yml` concurrency block and the `Select e2e areas` step (`BASE_SHA: ${{ github.event.before }}`); the plan has no concurrency text.

## A3 — 2026-11-24 — requested by orchestrator (pre-round-2 check)
wrong-fact — D11 says master pushes "queue in the same concurrency group", but GitHub keeps at most one pending run per concurrency group and cancels the older pending one when a newer run arrives, even with cancel-in-progress false; with three quick pushes the middle push is never e2e-tested. Give each push its own group (e.g. group key = ref for pull_request, run_id for push) and keep cancelling PR runs — evidence: GitHub Actions docs on `concurrency` ("any previously pending job or workflow in the concurrency group will be canceled"); `.github/workflows/tests.yml` concurrency block after T8.

## A4 — 2026-11-24 — requested by owner (after PR #176 opened)
missing-task — A red master area can be hidden: each master run selects areas only from its own push, so a following docs-only push runs no e2e and turns master green while the failure remains. Owner chose option 1: a nightly scheduled full e2e run of every area (plus manual workflow_dispatch), and README guidance that a red master run is fixed right away — evidence: side-agent note relayed by the owner; owner reply "option 1".

## A5 — 2026-11-24 — requested by owner (after PR #176 opened)
missing-task — Drop the Python 3.10 unit-test job from CI (unit runs on 3.14 only). Keep `requires-python >= 3.10` (not asked to change); docs that say 3.10 is tested/checked in CI must say CI checks 3.14 only — evidence: owner message "also we can drop unit tests for python 3.10".
