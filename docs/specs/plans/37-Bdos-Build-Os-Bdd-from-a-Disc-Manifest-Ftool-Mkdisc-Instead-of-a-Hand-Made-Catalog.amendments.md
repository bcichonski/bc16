# Amendment requests — 37 bdos: build os.bdd from a disc manifest (ftool mkdisc)

## A1 — 2026-11-11 — requested by T2
missing-task — make `src/disc.manifest` trackable: add a `.gitignore` exception (e.g. `!src/disc.manifest`) to T2 — `.gitignore` line 31 `*.manifest` (PyInstaller block) ignores the new manifest, so it would never be committed
test-conflict — add `src/bc64/testdata/e2e/bdos_hellowrd.golden.txt` to T2's Tests to modify — with HELLOWRD.PRG at its real 14 sectors (was 15 in the hand catalog), `hellowrd`'s loading-progress line prints `.` instead of `..`; `test_e2e_bdos.BdosShellTests.test_hellowrd_prints_greeting` is the only failure of the full run

## A2 — 2026-11-11 — requested by owner (mid-run)
contradiction — replace A1's `.gitignore` exception with a different name: the manifest is `src/disc.bddmanifest` (extension `.bddmanifest`, not matched by `*.manifest`), `.gitignore` stays untouched — owner: ".manifest file ext can be changed to .bddmanifest for example"

## A3 — 2026-11-11 — requested by owner (mid-run)
uncovered-AC — T4 must document the catalog-numbering caveat for disc files that stay as they are — owner: "add this remark for currently held disc files that will stay"; verified: `git show HEAD:src/os.bdd` and `HEAD:src/bc64/testdata/smoke.bdd` number only entries 0–15 (232 entries hold 0), so on a copy of them the 17th file gets entry number 0 and overwrites BOOTSECT.BIN's entry; committed `src/bdos.bdd` and `release/bc32_v1.0/discs/bdos.bdd` number all 248 and are not affected

## A4 — 2026-11-11 — requested by owner (mid-run, after PR #88 opened)
missing-task — the manifest states the layout requirements itself: exact start (`at=T/S`) and a checked maximum length (`max=N`, reserves the slot) for selected files, including the boot sector, the catalog and BDOS.SYS; mkdisc enforces them — owner: "extend the manifest to contain exact sector / tracks for certain files and their max length to check"
missing-task — move the layout requirements from `src/bdos/bdos.md` ("disk format") and the `docs/05-bdos.md` layout table into `src/disc.bddmanifest`, leaving only a reference to the manifest in the docs — owner: "then put the requirements there from doc bdd.md leave only reference to the manifest"
