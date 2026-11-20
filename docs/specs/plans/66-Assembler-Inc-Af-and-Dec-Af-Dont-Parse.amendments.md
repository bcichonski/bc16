# Amendment requests — 66 Assembler: inc af and dec af don't parse

## A1 — 2026-11-20 — requested by owner (mid-run instruction)
uncovered-AC — reject every other 16-bit ALU op with destination `af` too, not only `inc`/`dec` — owner in the /grind session: "make other arithmetic blocked on af"; same reason as the issue comment (the 16-bit result overwrites the flags in `f`)
