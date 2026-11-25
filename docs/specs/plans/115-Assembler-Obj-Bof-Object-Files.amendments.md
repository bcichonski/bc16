# Amendment requests — 115 Assembler --obj writes BOF object files

## A1 — 2026-11-25 — requested by owner (mid-run, via side-agent note: "can it be relaxed anyhow?")
contradiction — relax the D5/D11 ordering rules where possible — owner asked whether `.global`/`.extern`-before-use, `.def`-before-use and "`.assert` naming a label is an error in a relocatable file" can be relaxed, because `runtime.basm` (#116) and every later assembly module must follow them

## A2 — 2026-11-25 — requested by owner (mid-run, via side-agent note: "what can be done about it?" on object size)
wrong-fact — doc 07/G15 estimate a .o at 1.2–1.3 × the code size; measured with --obj it is 1.7–1.9 × (bcos 1.77, boot 1.89, helloworld 1.67) — record the measurement and the options (backward relative fill ~1%; two-pass BASM ~1.4–1.5 ×)
