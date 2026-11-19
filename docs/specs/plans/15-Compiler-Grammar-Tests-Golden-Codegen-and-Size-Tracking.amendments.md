# Amendment requests — 15 Compiler Grammar Tests, Codegen and Size Tracking

## A1 — 2026-11-19 — requested by repo owner (via /grind, after PR #135 opened)
- contradiction — the size/hash tracking must never fail CI; it is metrics only. Remove the repo-wide check (`RepoCheck.test_current_sources_match_the_committed_csv`) from the unit suite, keep `--check` as an optional local command, keep the CI report step informational, and update the docs that say the unit suite / CI fails until rows are recorded — evidence: owner: "it must not fail ci it is for metrics only"; PR #135 CI went red after #111 merged into master (bdio.b, ls.b changed) until rows were recorded.
