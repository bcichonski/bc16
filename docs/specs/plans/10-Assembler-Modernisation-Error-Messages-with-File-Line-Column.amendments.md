# Amendment requests — 10 Assembler Modernisation: Error Messages with file:line:column

## A1 — 2026-11-10 — requested by T5
wrong-fact — §3.1 "Renamed duplicates" / D3: the new name `exec_load_ret` for the first `exec_load_end` in `bcos.basm` is not free; pick an unused name — evidence: `src/bc81asmc/bcOS/bcos.basm` already defines `exec_load_ret:` (line 1273) and references it (`jmr z, :exec_load_ret`, line 1270), so the rename would create a new duplicate.

## A2 — 2026-11-10 — requested by T2
test-conflict — T2 Tests to modify: `src/bc81asmc/bc81asmc_emit_tests.py :: TestDirectives.test_def_takes_precedence_over_label` asserts that `.def thing, 0x4321` + label `thing:` assembles with the `.def` value — evidence: D3, T2 DoD and §3.1 make a label/`.def` clash a positioned error (`duplicate symbol 'thing' (first defined at line 2)`), so the test raises AssemblerError.
