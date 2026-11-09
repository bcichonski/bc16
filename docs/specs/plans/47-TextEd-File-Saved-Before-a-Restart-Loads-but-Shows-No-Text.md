# TextEd: File Saved Before a Restart Loads but Shows No Text — Plan

**Plan Status**: `FINAL`

**Story Type**: `Internal`

**Plan Revision**: `A2`

> Was blocked on **#76** (bdos buffered file I/O). #76 merged into `bc64` on 2026-11-09 (PR #78),
> so OQ-1 is closed and this plan is `FINAL`. It covers the TextEd, disc and e2e work for #47.

---

## 1. Problem Statement

*   **Context**: TextEd v1.2 (`src/bdos/texted.b`) saves files (`s <file>`) through bdos buffered
    writes. Loading (`l <file>`) a saved file after a restart reports success but the buffer stays
    empty. A headless spike on the current `os.bdd` (2026-11-09) showed more than that:
    `TEXTED.PRG` on the disc is a **stale build without the `l` command** ("Unknown command."),
    with debug output on save. `texted.basm/.btap/.sectors` have never been committed (#1).
*   **Goal**: after `i` → `s file` → restart → `texted` → `l file`, `p` shows exactly the saved
    numbered lines. This must also work for files of several sectors and 80-character lines, and on
    the rebuilt system disc.
*   **In scope**: TextEd load path (open mode, chunked read, parsing, storing lines, replace
    semantics, error messages), `cat -c` display of text across sector boundaries (A1, D7),
    rebuild of every disc program from source and of `os.bdd` (A1, D5), preservation of the `TEST.B` sample
    file on the disc, an e2e save → restart → load test (owner comment on #47), docs.
*   **Out of scope**: the `CP.PRG` catalog truncation (56 vs a 57-sector build) behind #49's
    `expectedFailure` cp test — a follow-up (A2); the bdio buffered read/write bugs and their debug `printf`s (#76); changing
    `cat`'s other behaviour (its display of the trailing `#00` padding as `#00` stays; only the
    char-mode defects of D7 are fixed); saving over an existing file name
    (`bdio_fcreate` refuses, unchanged); the other bdos debug leftovers (#46).

### 1.1 Technical Summary

*   **Touched projects**: `src/bdos/texted.b` (+ generated outputs), `src/fcat0800.sector`,
    `src/makedisc`, `src/os.bdd`, `src/bc64/testdata/` (smoke disc/transcript, e2e goldens),
    new `src/test_e2e_texted.py`, `docs/05-bdos.md`, `docs/specs/memory/design-decisions.md`.
*   **New patterns / abstractions**: an e2e "restart" scenario. Two headless sessions run on the
    same disc copy; the first session's `inspect` hook hands its disc to the second.
*   **Infrastructure changes**: disc layout. `TEXTED.PRG` gets its full 112-sector slot from
    `fcat0800.sector` (100 on today's disc), and `TEST.B` becomes a `makedisc`-built file right after it.
*   **End-state observable behaviour**: `l <file>` prints `N lines loaded`, and `p 0 65535` prints
    the same lines as before the save. A missing file prints `error: E0 file not found` and leaves the
    buffer unchanged.

---

## 2. Architecture & Design

### 2.1 Architecture Overview

#### Involved components & owners

| Component | Technical Owner |
| :--- | :--- |
| TextEd (`src/bdos/texted.b`) | bcichonski |
| bdio buffered I/O (`src/bdos/bdio.b`), via #76 | bcichonski |
| Disc build (`src/makedisc`, `src/fcat0800.sector`, `src/os.bdd`) | bcichonski |
| e2e harness and tests (`src/e2e_harness.py`, `src/test_e2e_*.py`) | bcichonski |

#### C2 diagram

```mermaid
flowchart LR
  TE[TEXTED.PRG<br/>texted.b] -->|bdosh.b wrappers| BDIO[bdio_call<br/>bdio.b in BDOS.SYS]
  BDIO -->|FDD port 0x08| DISC[(os.bdd)]
  MK[makedisc + fcat0800.sector] --> DISC
  E2E[test_e2e_texted.py] -->|e2e_harness.run_session x2| EMU[bc64.py headless]
  EMU --> DISC
```

#### Flow diagram (load, happy path)

```mermaid
sequenceDiagram
  participant U as user
  participant T as texted
  participant B as bdio (buffered, #76)
  U->>T: l note.txt
  T->>B: fbinopenr(NOTE    TXT, BUFFERED)
  loop until 0 bytes or 0x00 record end
    T->>B: fbinbufread(h, chunk, n<=128)
    B-->>T: k bytes
    T->>T: split records at 0x13, parse "<n> <text>", insert line n
  end
  T->>B: fclose(h)
  T-->>U: "K lines loaded"
  U->>T: p 0 65535
```

### 2.2 External Contracts & Evidence

N/A — Internal story.

#### Source Conflict Log

| Topic | Story text | Repository | Resolution |
| :--- | :--- | :--- | :--- |
| `cat` shows lines | "#47 item 5: `cat` won't show the lines as lines" | `cat.b` also defines `CHAR_LF 0x13` and prints it as ` !ln` + newline. But char mode prints each 128-byte sector in 80-byte steps (`CHARPERLINE`), so the second step reads 32 bytes past the sector buffer, and it starts a new output line at every sector boundary. `bdos_cat.golden.txt` already shows the overread (`40 another looo…#00#00…` inside a record of `TEST.B`) | Keep the `0x13` format (D1); fix the char-mode display (D7, A1) so AC-4 holds |
| Disc built by `makedisc` | AC-6: "`os.bdd` rebuilt" | The committed `*.btap`/`boot.sector` of boot, ls, cp, helloworld, format, rm, cha are stale (a disc from them doesn't boot, `fatal error CE`); rebuilding from source reproduces today's on-disc bytes. Today's `CAT.PRG` matches no commit's build | Rebuild every program from source (D5, A1) |
| Cause of the empty load | open mode, records not stored, read length | Also: `bdio_fbinbufread` returns 0 on a fresh handle (#76), the disc's TEXTED has no `l`, and `loadFile` never sets `error`, so a missing file prints nothing | Split bdio into #76; the TextEd items are tasks here |

### 2.3 Key Code Pointers

*   `src/bdos/texted.b`: `loadFile`, `readLines` (load path); `saveFile`, `saveLines` (format
    producer); `insertLineBuf` (ordered insert, same number replaces); `deleteLines` (freeing lines);
    `main` (`PinputBuf` is `malloc(MAXLINELENGTH)` and filled by `readsn(…, MAXLINELENGTH)`; check the
    terminator fits).
*   `src/bdos/bdosh.b`: `bdio_fbinopenr`, `bdio_fbinbufread`, `bdio_fclose` wrappers.
*   `src/bdos/bdio.b`: `bdio_printexecres` (error text), buffered I/O (#76's contract).
*   `src/bdos/stdmem.b` (`malloc`/`mfree`), `src/bdos/strings.b` (`parsedecw`, `strnextword`, `strnlen8`).
*   `src/makedisc`, `src/fcat0800.sector`, `src/ftool.py` (`importsector`), `docs/05-bdos.md` (disc
    table, texted row, bdio API).
*   `src/e2e_harness.py` (`run_session(..., inspect=)`, `read_catalog`, `check_golden`),
    `src/test_e2e_bdos.py`, `src/bc64/testdata/e2e/`.

### 2.4 Key Algorithms / Rules (conceptual)

*   **File format (unchanged, D1)**: one record per line, `<decimal line number> <text>` followed
    by `0x13`. After the last record comes one `0x00`, then zero padding to the end of the sector.
*   **Load**: open the file in buffered mode. Read it in chunks of at most 128 bytes, and handle
    only the bytes each call returns. Build each record across chunk boundaries until `0x13`. Stop
    at the first `0x00` or when a read returns 0. For each record, parse the number up to the first
    space; the text is the rest. Insert it with the editor's normal ordered insert. A record with no
    valid number, or with empty text, is skipped. Text longer than `MAXLINELENGTH` is truncated, and
    the line buffer is never overrun.
*   **Replace semantics (D2)**: the buffer is cleared (lines freed, total reset) only after the
    file opened successfully, so a failed load leaves the buffer as it was.

### 2.5 Decisions & Assumptions

*   **D1 — Keep the on-disc text format** (`0x13` line end, final `0x00`). It keeps `cat -c`,
    existing files (`TEST.B`) and `saveLines` compatible, and it is the most conservative choice
    (#47 item 5 asked to decide). Record it in `docs/05-bdos.md` and as a design decision.
*   **D2 — `l` replaces the buffer**, as an editor's "load" usually does. Document it in
    `docs/05-bdos.md` and in texted's `h` text.
*   **D3 — Missing or unreadable file**: print the bdio error (`bdio_printexecres`, e.g.
    `error: E0 file not found`) and leave the buffer unchanged. The current code never sets `error`
    and prints nothing.
*   **D4 — Disc rebuild**: run a fresh `makedisc` from committed outputs, plus the texted build.
    `TEXTED.PRG` takes its 112-sector slot (45/0). `TEST.B` is kept **byte for byte** (its 2 sectors
    exported from today's `os.bdd` at 51/4, committed as a sector file). It becomes catalog entry 11
    in `fcat0800.sector` at 52/0, attributes `R W` (`0x03`), and `makedisc` imports it. It is a frozen
    sample that `test_e2e_bdos` and the smoke test rely on. Its legacy zero gap stays as it is.
    (A1, narrowed in A2) The catalog changes only for the files this story ships: `TEXTED.PRG`
    (112), `CAT.PRG` (its D7 build, 62 — the old 61 truncated it and `cat` crashed) and the new
    `TEST.B` entry. Every other entry keeps today's sector count. Where that is larger than the
    fresh build (`LS.PRG`, `HELLOWRD.PRG`, `BDOS.SYS`) it is harmless. `CP.PRG` stays at 56 although
    its build is 57: that truncation is the pre-existing cutoff behind #49's `expectedFailure`
    cp test, it is out of this story's scope, and it is reported as a follow-up (fixing it means
    changing that test's marker under its own issue). `docs/05-bdos.md` matches the catalog.
*   **D5 (amended in A1) — Rebuild every disc program from source** with the current toolchain
    (`boot.basm` re-assembled, ls/cp/helloworld/format/rm/cha/cat/texted through `bcc`), because
    the committed generated files are stale and a `makedisc` from them gives an unbootable disc.
    For the unchanged programs a fresh build reproduces today's on-disc bytes; that generated churn
    goes in a separate `chore:` commit (CLAUDE.md). Today's `CAT.PRG` can't be reproduced and is
    replaced by the D7 build, which is why `cat -c` goldens change.
*   **D6 — The maximum line length** is the longest line `i` accepts (`MAXLINELENGTH` = 80 through
    `readsn`). The e2e test uses lines of exactly that length.
*   **D7 (A1) — `cat -c` shows text records whole.** Char mode prints only the bytes actually read
    for each sector (no read past the 128-byte buffer) and keeps its column across sector
    boundaries, so a record that crosses a sector boundary prints on one output line (subject to
    cat's existing 80-column `!catln1`/`!catln2` wrap). Binary mode (`cat` without `-c`) and the
    `#xx` display of non-printable bytes are unchanged. `CAT.PRG` must still fit its 64-sector slot
    (41/0–44/15), and its catalog length is the length of its build.
*   **A1 (verified)** — #76 (PR #78, merged) delivers the buffered contract in `docs/05-bdos.md`:
    `bdio_fbinbufread(h, Pbuf, n)` returns bytes copied `1..n` in order, `0` = EOF or not buffered;
    `bdio_fclose` flushes a write handle. #76 patched only the `BDOS.SYS` slot of `os.bdd` (no full
    `makedisc`), so the disc still holds the stale `TEXTED.PRG` and `TEST.B` at 51/4: D4 is unchanged.
    The committed `bdos.btap` is #76's fresh build, so a fresh `makedisc` ships the same bdos.

---

## 3. Questions

### 3.1 Resolved

*   Format change to `0x0a`? No (D1). Replace or append? Replace (D2). Debug `printf`s? Moved to #76.
*   OQ-1 (merge #76 first): done, PR #78 merged into `bc64` 2026-11-09; A1 and D4 re-checked (see §2.5).

### 3.2 Open Questions

None.

---

## 4. Task Breakdown

| Task | Title | Depends on | Complexity |
| :--- | :--- | :--- | :--- |
| `T1` | TextEd load: buffered chunked read, store lines, replace, errors | — | `High` |
| `T2` | Rebuild the system disc with texted and keep `TEST.B` | `T1`, `T4` | `Medium` |
| `T3` | e2e: save → restart → load scenarios for TextEd | `T2` | `Medium` |
| `T4` | `cat -c` prints text records whole across sector boundaries | — | `Medium` |

### T1 — TextEd load works

*   **Goal**: `l <file>` loads a file saved by `s` into the editor (D2), so `p` prints it. A missing
    file prints an error (D3).
*   **Depends on**: — (#76 is on `bc64`).
*   **Complexity**: `High`. It is B (`<-` assigns, `=` compares, parenthesised comparisons, single
    `return`), it has no unit-test layer, and records cross chunk boundaries.
*   **Pointers**: §2.3 texted entries; build `cd src && bash <(tr -d '\r' < bcc) bdos/texted`.
*   **Definition of Done**:
    *   the load follows §2.4 and D1–D3, opening in buffered mode;
    *   the result is reported as `N lines loaded`;
    *   no out-of-bounds writes (line buffer, input buffer for 80 characters);
    *   `texted.genb/.basm/.btap` are built and committed;
    *   `TEXTED.PRG` still fits 112 sectors (check the `.btap` length);
    *   `docs/05-bdos.md` texted row and `h` text say "load replaces the buffer";
    *   a headless spike on a temp disc copy shows the round trip working.
*   **Tests expected**: none added here (no B unit harness). The spike above is the self-check; T3 adds the e2e tests.
*   **Tests to modify**: None.

### T2 — System disc rebuild with texted and `TEST.B`

*   **Amended in**: A2.
*   **Goal**: `os.bdd` holds the new `TEXTED.PRG`, T4's `CAT.PRG` and #76's `BDOS.SYS`, every
    program rebuilt from source (D5), `TEST.B` is preserved (D4), and CI's frozen-disc check passes.
*   **Depends on**: `T1`, `T4`.
*   **Complexity**: `Medium`.
*   **Pointers**: `src/makedisc`, `src/fcat0800.sector`, `src/ftool.py`, `src/bc64/CLAUDE.md`
    (smoke refresh), `.github/workflows/tests.yml` (e2e refresh and `git diff --exit-code`). The
    `ftool` and `makedisc` scripts are CRLF and call `winpty python`. Run them through CR-stripped
    copies that call `python3`, without committing those copies.
*   **Definition of Done**:
    *   `TEST.B`'s 2 sectors are exported from the pre-rebuild `os.bdd` (51/4) and committed;
    *   the catalog entry and `makedisc` import exist;
    *   every program's generated files are rebuilt from source (D5); a fresh `makedisc` produces a
        booting `os.bdd`. Its catalog lists entries 0–10 as in `docs/05-bdos.md` (TEXTED 112
        sectors, CAT 62, the other lengths as today, D4) plus `TEST.B` at 52/0, 2 sectors, `R W`;
    *   `TEST.B`'s bytes are unchanged, and `cat -c test.b` differs from today's only as D7
        intends (no `#00` inside a record; records crossing the sector boundary on one line);
    *   `smoke.bdd` and `smoke_transcript.txt` are refreshed (CI procedure);
    *   e2e goldens are regenerated with `BC64_UPDATE_GOLDEN=1`; the `bdos_ls`/`bdos_rm` diffs show only
        catalog and free-space lines, the `bdos_cat` diff only the D7 display change;
    *   the `docs/05-bdos.md` disc table lists `TEST.B`;
    *   `python3 run_tests.py < /dev/null` is green.
*   **Tests expected**: existing e2e suite green on the rebuilt disc.
*   **Tests to modify**:
    *   `src/bc64/testdata/e2e/bdos_ls.golden.txt` — the TEXTED and TEST.B catalog lines and the free sectors change with the rebuilt disc (AC-6, D4).
    *   `src/bc64/testdata/e2e/bdos_rm.golden.txt` — its `ls` listing changes for the same reason (AC-6, D4).
    *   `src/test_e2e_bdos.py :: BdosShellTests.test_ls_lists_catalog` — the `CATALOG_LINES` entries for `TEXTED  .PRG` and `TEST    .B` get the new size and start (AC-6, D4).
    *   `src/bc64/testdata/e2e/bdos_cat.golden.txt` (`BdosShellTests.test_cat_prints_text_file`) — `cat -c test.b` no longer shows overread `#00` bytes inside records nor breaks records at the sector boundary (AC-4, D7, A1). The test's `TEST_B_TEXT` markers stay as they are.

### T3 — e2e save → restart → load

*   **Amended in**: A1.
*   **Goal**: the owner's requested e2e smoke test. It saves in one emulator session and loads in a
    fresh one on the same disc.
*   **Depends on**: `T2`.
*   **Complexity**: `Medium`.
*   **Pointers**: `src/e2e_harness.py` (`run_session` with `inspect` copying `paths["a"]` out for
    the second session), `src/test_e2e_bdos.py` (style), `src/bc64/testdata/e2e/` (scripts/goldens).
    Avoid the known crashers (`src/bc64/CLAUDE.md`); texted's `q` is safe.
*   **Definition of Done**: a new `src/test_e2e_texted.py` covering:
    *   a simple save → restart → load where `p` shows identical lines (the owner's case);
    *   a file over 128 bytes that includes 80-character lines;
    *   a missing file giving an error with the buffer unchanged;
    *   a load into a non-empty buffer replacing it;
    *   `cat -c` after the restart showing every saved record's text with no `#00` inside it,
        including records that cross a sector boundary (D7). A record longer than 80 columns
        (`<n> ` + 80 characters) is wrapped by cat's `!catln1` at column 80, so compare the text with
        the wrap markers and line breaks removed; each record ends with ` !ln`;
    *   no `read md:` / `Pb:` debug text.

    Use markers and, where stable, goldens. The suite stays well within CI's 10-minute e2e timeout.
*   **Tests expected**: e2e, as listed.
*   **Tests to modify**: None.

### T4 — `cat -c` prints text records whole

*   **Amended in**: A1 (added).
*   **Goal**: AC-4 — `cat -c <file>` shows saved text correctly (D7).
*   **Depends on**: —.
*   **Complexity**: `Medium` (B quirks as in T1; small change).
*   **Pointers**: `src/bdos/cat.b` (`printfile`, `printbuf`, `printchars`); build
    `cd src && bash <(tr -d '\r' < bcc) bdos/cat`; `CHARPERLINE`, `INFILEBUF_ADDR`.
*   **Definition of Done**:
    *   char mode reads no byte beyond the sector just read, and keeps the output column across
        sectors (no line break at a sector boundary inside a record);
    *   binary mode output is unchanged;
    *   `cat.basm/.btap` rebuilt and committed; the build fits 64 sectors (report its sector count
        for T2's catalog entry);
    *   a headless spike on a temp disc copy shows `cat -c test.b` with records 30 and 40 free of
        `#00`, and a texted-saved file crossing a sector boundary printed whole.
*   **Tests expected**: none added here; T2 regenerates `bdos_cat` and T3 covers the texted file.
*   **Tests to modify**: None.

---

## 5. Verification

*   **Build** (from `src/`): `bash <(tr -d '\r' < bcc) bdos/<program>` for every disc program
    (`boot.basm` assembled), then a fresh `makedisc` (§T2, D5).
*   **Tests** (repo root): `python3 run_tests.py < /dev/null`, green.
*   **CI parity**: repeat the e2e job's smoke refresh locally. `git diff --exit-code src/bc64/testdata/` must be clean after commit.
*   **Observable**: the manual round trip: `texted`, `i 10 10`, lines, `s note.txt`, `q`,
    `exit`, reboot on the same disc, `texted`, `l note.txt`, `p 0 65535`.

---

## 6. Fact-Integrity Checklist

| Check | Yes / No / N/A | Notes |
| :--- | :--- | :--- |
| External contracts verified | N/A | Internal |
| Evidence sources reproducible | N/A | Internal |
| Identifier meaning evidenced | N/A | Internal |
| Every `Assumption` is linked to an Open Question (§3.2) | Yes | A1 verified after #76 merged |
| No unresolved Open Questions (for `FINAL`) | Yes | OQ-1 closed (#76 merged) |
| Each Decision states a single committed approach | Yes | D1–D7 |
| Tasks are independent, each with a Definition of Done and test expectations | Yes | sequential via disc state |
| Required infra reflected | N/A | no toggles / bicep |

**Self-review note**: the TextEd defects and the disc layout facts were verified by reading the code
and by a headless spike (2026-11-09, `bc64` @ 74a94bf):
*   the stale `TEXTED.PRG` has no `l`;
*   the fresh build is 0x36f0 bytes (110 sectors);
*   a fresh `makedisc` gives TEXTED 112 sectors and drops `TEST.B`.

Re-checked after #76 merged (`bc64` @ 9aefa13): A1 holds and #76 patched only `BDOS.SYS`, so the
plan went `FINAL` unchanged in scope. Take extra care with B buffer bounds in
T1 and with the golden diffs in T2.

---

## 7. Amendment Log

| Revision | Request | Decision | Plan changes |
| :--- | :--- | :--- | :--- |
| A0 | — | — | initial plan |
| A1 | test-conflict: `bdos_cat` golden / `test_cat_prints_text_file` change on a fresh `makedisc` (unreproducible `CAT.PRG`) | Accepted — AC-6 requires a rebuilt disc and today's `CAT.PRG` can't be rebuilt; with D7 the golden changes by design (AC-4) | D5 rewritten; `bdos_cat.golden.txt` added to T2's `Tests to modify` (markers unchanged); T2 amended |
| A1 | missing-change: `CAT.PRG` build is 62 sectors, catalog says 61 | Accepted — the catalog must match the build or `cat` crashes | D4 note: lengths follow builds; T2 DoD |
| A1 | missing-change: committed generated files stale, disc from them doesn't boot | Accepted — verified by T2's rebuild reproducing on-disc bytes | D5: rebuild every program from source, churn in a `chore:` commit; §5 build step |
| A1 | test-conflict (T3): `cat -c` breaks records at sector boundaries and shows `#00` inside them | Accepted as a code gap, not a test weakening — `printbuf` steps 80 bytes through a 128-byte buffer (32-byte overread) and `printfile` breaks the line per sector; AC-4 requires correct display | D7 added; Source Conflict Log; new T4 (cat fix); T2 depends on T4; T3 DoD restated for cat's 80-column wrap |
| A2 | test-conflict: D4 (A1) "every length equals its build" makes `CP.PRG` 57 and turns #49's `expectedFailure` `test_cp_then_cat_shows_same_text` into an unexpected success | Accepted by narrowing D4 — A1 over-reached: AC-6 needs texted/bdos shipped, not every catalog entry re-sized; changing cp's behaviour and that test's marker belongs to a separate issue. Not added to `Tests to modify` (no AC changes what the test asserts) | D4 narrowed (only TEXTED, CAT, TEST.B entries change; CP stays 56 as a reported follow-up); §1 out of scope; T2 DoD amended |
