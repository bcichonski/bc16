# Amendments — 113 BOF v1 and the B calling convention ABI

## A1 — 2026-11-24 — requested by owner (PR #183 review note)
contradiction — Replace the `SECT` record (`5e`, `flags(1) [address(2)] name`) with two tags, as other BOF records do: `55` SECTSTAT (`name`, relocatable section) and `5a` SECTABS (`address(2) name`, absolute section). No flags byte. — Owner: "if sect is only 0 or 1 we can do as in other places and have separate instructions SECTSTAT and SECTABS so split 5e into 55 and 5a"
