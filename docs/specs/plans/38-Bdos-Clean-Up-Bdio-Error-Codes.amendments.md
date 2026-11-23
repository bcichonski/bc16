# Amendment requests — 38 bdos: clean up bdio error codes

## A1 — 2026-11-23 — requested by owner (mid-run note)

- contradiction — D4 adds a `bdio_printexecres` message for every bdio error code; the owner wants messages for the changed codes only, to keep programs small ("only changes"). Change D4, §2.4 messages, T1 DoD/tests and T3 (docs table) accordingly. — evidence: owner reply 2026-11-23 to the side-agent note that every disc program grows by a few hundred bytes; AC 2 asks only for "each changed code has a matching message".
