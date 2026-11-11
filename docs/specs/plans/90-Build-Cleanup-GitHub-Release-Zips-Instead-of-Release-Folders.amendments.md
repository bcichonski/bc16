# Amendment requests — 90 Build cleanup

## A1 — 2026-11-11 — requested by T6
wrong-fact — take the bc32 ROM for the bc32-v1.0 zip from the release commit `6304761` (`src/bc81asmc/bcOS/bcos_v1_1_1.b81`), not from `7d4cda9` — evidence: `git show 7d4cda9:src/bc81asmc/bcOS/bcos_v1_1_1.b81` (md5 4ca24d13…) crashes the bc32 emulator at start ("exception at 9049", IndexError in bc32_mem.py); the copy at `6304761` (md5 238ceac8…) boots "bcOS 1.1 … bDOS 1.0 shell" and lists the disc; `git log` shows `b9f2fe6` (2024-10-27, "fix: loading problem, fopenr missing new param") changed that ROM after the bc32 release
