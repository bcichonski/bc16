# 175 P3: e2e merge candidates (analysis only)

**Status**: analysis for the owner (plan 175, task T5, decision D7). No test, code or other doc was changed; nothing is merged here.

## 1. How to read the numbers

*   **Timings** come from the measured logs of the 26 e2e modules (`--durations 0`, 6 modules in parallel, so every figure is inflated a little). The module totals add up to about 685 s in parallel; the CI `e2e` job ran about 567 s serially on master. Use the percentages, not the absolute seconds, when comparing with CI.
*   **Sessions** are counted from the module code: one `h.run_session` call is one emulator session (boot plus scripted keys). Counts are per test, after reading the module.
*   **Cost of a session**: a session has a fixed part and a work part. Measured fixed parts: a bDOS boot-and-exit session is about 0.6 s, a TextEd start-and-quit session is about 3.0 s (`test_e2e_texted_flows::test_startup_banner`), a calc start is about 2 s. The rest is emulated work (keys typed, files copied). Merging two sessions therefore saves only their fixed part, unless the merged sessions also repeat the same work.
*   **Key finding**: the largest savings do not come from joining different sessions. They come from **identical sessions run more than once** (same script, same disc), and from **a test whose checks are already a subset of another test's session**. Pure session merging saves little.
*   **Split estimates** (save half vs load half of a two-session test) are assumed to be even. They are not measured. Ranges in this file reflect that.

## 2. Current session map (sessions and seconds per module)

| Module | Tests | Sessions | Measured seconds (sum of tests) | Note |
| :--- | ---: | ---: | ---: | :--- |
| `test_e2e_bdos_cmdtable` | 2 | 1 (setUpClass) | 108.1 (module wall) | Largest single session in the suite; already one session |
| `test_e2e_texted` | 5 | 10 | 68.4 | Two sessions per test (save, then load) |
| `test_e2e_texted_flows` | 3 | 4 | 71.7 | `large_file` alone is 57.4 s |
| `test_e2e_rm_alloc` | 3 | 3 | 66.8 | Distinct disc states per test |
| `test_e2e_bdos` | 11 | 10 | 64.2 | Shell tests plus cp regression |
| `test_e2e_alloc_gap` | 5 | 5 | 52.3 | Distinct disc states per test |
| `test_e2e_ftool_text` | 3 | 3 | 20.8 | |
| `test_e2e_calc` | 8 | 6 | 18.0 | `bad` scenario runs twice |
| `test_e2e_compile_cycles` | 2 | 2 | 18.1 | |
| `test_e2e_texted_disc_full` | 2 | 2 | 26.0 | |
| `test_e2e_texted_commands` | 4 | 4 | 24.3 | |
| `test_e2e_bdos_args` | 6 | 1 (setUpClass) | 26.4 (module wall) | Six error-path commands in one session; cause of 26 s not measured |
| `test_e2e_layout_shift` | 4 | 3 | 17.3 | |
| `test_e2e_bdio_buffered` / `_errors` | 1 / 1 | 1 / 1 | 13.1 / 10.7 | |
| `test_e2e_disc` | 6 | 1 plus pure checks | 14.9 | |
| `test_e2e_theodore` | 6 | 6 | 13.4 | Seed-1 win session runs twice |
| `test_e2e_harness` | 35 | 3 real boots plus pure checks | 9.2 | 32 tests are pure Python |
| `test_e2e_utils_disc` | 10 | 3 | 4.0 | Structure checks take 0 s |
| `test_bc64_smoke` | 2 | 2 | 11.3 | |
| others (`bcos`, `rom`, `return`, `toolchain`, `ls_free`, `random`) | 1 to 5 each | 1 to 3 each | 0.3 to 8.4 each | Little to gain |

## 3. Candidates

Savings are estimated in seconds (parallel-inflated, same units as section 2). "Risk" is the coverage risk of the proposed change.

### 3.1 Recommended (duplicate work or strict subsets)

| # | Tests involved | Current sessions / seconds | Proposed merge | Est. saved | Coverage risk |
| :-: | :--- | :--- | :--- | ---: | :--- |
| A | `test_e2e_bdos::test_cp_then_cat_shows_same_text` (script `bdos_cp`) and `BdosCpRegressionTests::test_cp_same_drive_creates_identical_copy` (script `bdos_cp_same_drive`) | 2 / 12.7 + 14.1 | `bdos_cp` script is the same as `bdos_cp_same_drive` without the `ls` line. The first test's checks (cp then `cat -c copy.b` prints the text, markers, `bye!`) are all in the second test. Drop the first session (or point it at the second session's output). | 12.7 | Low. Strict subset. Needs owner approval because it removes a test. |
| B | `test_e2e_texted`: `test_save_restart_load_prints_same_lines`, `test_missing_file_prints_error_and_keeps_buffer`, `test_load_replaces_a_non_empty_buffer` | 6 / 34.8 (three identical save sessions, three loads) | One shared save session (same script in all three; `setUpClass` or a module cache), one load session that runs the three load scripts in order (`l note.txt` then the missing-file load, then the replace check), with the output split by markers. | about 20 (range 15 to 25) | Moderate. Buffer state is shared, so the order must keep "buffer non-empty before load" and "missing file keeps buffer" true. The error-count and section assertions must be scoped per part. |
| C | `test_e2e_texted`: `test_file_over_one_sector_with_80_character_lines` and `test_cat_c_shows_saved_records_whole` | 4 / 33.5 (two identical long-file save sessions, two loads) | One shared long-file save session. One load session: `l long.txt`, `p 0 65535`, `q`, then `cat -c b:long.txt`, `exit`. | about 15 (range 12 to 18) | Low to moderate. Same assertions, one session. |
| D | `test_e2e_ftool_text`: `test_imported_file_is_loaded_by_texted` (5.3 s) and `test_imported_file_saved_by_texted_exports_to_the_original` (8.6 s) | 2 / 13.9 | The load-only test's checks (printed records, "0004 lines loaded") are already produced by the combined session (`l note.txt`, then `s copy.txt`). Keep the load assertions in the combined test and drop the load-only session. | 5.3 | Low. Strict subset of the combined run. |
| E | `test_e2e_calc`: `test_bad_numbers` and `test_65535_is_accepted_and_65536_is_not` | 2 / 4.7 (same `bad` scenario) | Run the `bad` scenario once (shared by the two tests). Output is identical. | 2.3 | None. Same script, same output. |
| F | `test_e2e_theodore`: `test_seeded_game_north_south_found_bye` and the first half of `test_different_seeds_give_different_secret_stops` | 2 / 4.1 (same `theodore_win`, seed 1) | Share the seed-1 win session. | 2.1 | None. Same script, same seed, same output. |
| G | `test_e2e_harness`: `test_real_boot_returns_output_and_leaves_source_untouched` and `test_ls_line_of_every_planned_entry_is_in_a_real_ls_session` | 2 / 6.0 (both `ls` on `os.bdd`) | Keep one real `ls` boot. Check first that `disc_ls_all` output contains the `A>ls`, `HELLOWRD.PRG`, `bye!` markers of the other test (not verified here). | 2.7 | Low, if the markers are a subset. |

Subtotal, section 3.1: about 45 s (A 12.7, B about 20, C about 15, D 5.3, E 2.3, F 2.1, G 2.7; roughly 60 s if B and C reach the top of their ranges). Roughly 6 to 9 % of the measured total.

### 3.2 Optional (merge different scripts into one session)

| # | Tests involved | Current sessions / seconds | Proposed merge | Est. saved | Coverage risk |
| :-: | :--- | :--- | :--- | ---: | :--- |
| H | `test_e2e_texted_commands`: all four tests (save without name, load without name, name over 12 characters, insert/print/delete with missing numbers) | 4 / 24.3 | One texted session running the four command groups in sequence. Each check reads its own output section. | 7 to 9 | Moderate. Two tests assert "buffer kept" and need a known buffer state at their point in the sequence. |
| I | `test_e2e_texted_flows`: `test_startup_banner` (3.0 s) into `test_insert_print_delete_save_and_list` (11.4 s) | 2 / 14.4 | Put the banner check (`B>texted`, `TextEd v1.2`, `texted>q`) at the start of the edit session. | 2.5 to 3 | Low. |
| J | `test_e2e_calc`: `help`, `ops`, `divzero`, `bad`, `unknown` (5 sessions, about 2 s each) | 5 / about 11 | One calc session with the commands in order (`quit` stays separate, last). | about 6 (uncertain) | Moderate. Calc is a prompt loop, so each check must read its own section. |
| K | `test_e2e_bdos_args`, `test_e2e_utils_disc` `hellowrd_b`, `test_e2e_disc` `ls -a` | several | Not measured in detail. Each merge saves about one boot (0.5 to 1 s). | under 2 each | Low, but not worth the churn. |
| L | `test_e2e_bdos`: `test_texted_command_not_found_with_only_os_disc` (1.2 s) into `test_boot_prompt_and_exit` (0.6 s) | 2 / 1.8 | Append `texted` and `exit` to the boot script. | about 0.5 to 1 | Low, but the saving is tiny. |
| M | `test_e2e_bdos`: the six `BdosShellTests` sessions (boot, ls, cat, hellowrd, rm, errors) | 6 / 20.2 | One shell session. Work time stays the same; only five boots are saved. | about 3 | Moderate (goldens per scenario change). Not recommended. |

### 3.3 Not a merge, but the largest single lever

| # | Tests involved | Current sessions / seconds | Proposal | Est. saved | Coverage risk |
| :-: | :--- | :--- | :--- | ---: | :--- |
| N | `test_e2e_texted_flows::test_large_file_loads_after_restart` (40 typed records, about 4 sectors) | 2 / 57.4 | The save half types 40 long lines through the keyboard. Build the same 40-record file with `ftool import` (the way `test_e2e_ftool_text` already does) and keep only the load session. | about 25 to 30 (split not measured) | Moderate. The test would no longer exercise texted's own save of a 4-sector file. The 2-sector save in `test_e2e_texted` would still cover that path, but not at 4 sectors. Owner decision. |

### 3.4 Not recommended (no merge possible or no real saving)

| Tests involved | Why not |
| :--- | :--- |
| `test_e2e_rm_alloc` (3 tests, 66.8 s) and `test_e2e_alloc_gap` (5 tests, 52.3 s) | Each test starts from a different disc state (fill and remove patterns). A shared session would change the state the test is about. These are the heaviest modules after texted, so the lever is the emulator speed (P5), not merges. |
| `test_e2e_compile_cycles`, `test_e2e_toolchain`, `test_e2e_return`, `test_e2e_bdio_buffered`, `test_e2e_bdio_errors` | Different programs and discs. Each merge saves about one boot (under 1 s). |
| `test_bc64_smoke::test_built_disc_session_matches_transcript` (8.0 s) and `test_e2e_layout_shift::test_smoke_session_matches_transcript` (9.4 s) | Same smoke script, but on different discs (built vs shifted layout). Only one of them could go, and that drops either the built-disc transcript or the shifted-layout check. Coverage risk is high. |
| `test_e2e_bdos_cmdtable` (108 s, one session) | Already one session. Its cost is in the emulated commands (for example `format -q b:` and the copies). Profile it before proposing anything. |
| `test_e2e_bdos_args` (26 s, one session) | Already one session. Six error-path commands take 26 s, while a bDOS boot takes 0.6 s. The cause is not known. Check whether one command runs longer than expected. |

## 4. Edge cases better as unit tests

*   **Pure-Python checks inside e2e modules** cost almost nothing (32 of the 35 `test_e2e_harness` tests take about 0.1 s in total; the `test_e2e_disc` and `test_e2e_utils_disc` structure checks take 0 s). Moving them to unit tests would not save CI time. It would only make the e2e tier clearer. Owner's call, not a saving.
*   **Edge cases of the emulated programs cannot move to unit tests.** The argument rules of TextEd, the calc error messages, the bDOS command table, and the allocator behaviour all run in the real bDOS, TextEd, and calc binaries inside the emulator. No Python code exists to unit-test against. Only the host tools (`ftool`, `bc`, `bc81asmc`, the harness itself) have Python logic that unit tests could cover.
*   `test_e2e_ls_free` manifest checks and the `ftool` text conversion checks are partly Python-only. A unit test could cover the Python part; the emulator part stays in e2e.

## 5. Recommendation for the owner

1.  **Take section 3.1 first.** It removes about 45 to 60 s of work (roughly 6 to 9 % of the measured total) with no change in what is checked, apart from A (remove a strict-subset test, owner must approve) and B and C (rewrite the shared-buffer tests with scoped assertions). A, D, E, F and G are safe; B and C need care.
2.  **Decide N (large-file test, 57 s) separately.** It is the largest single lever in the suite but changes what the test covers. Owner decision.
3.  **Skip section 3.2 unless the CI is still too slow after 3.1 and N.** Each merge saves only a boot or a TextEd start, about 0.5 to 3 s each.
4.  **Do not merge the allocator, compile-cycle or smoke tests** (section 3.4).
5.  **Profile two outliers** before any further work: `test_e2e_bdos_cmdtable` (108 s) and `test_e2e_bdos_args` (26 s for six short commands).
6.  The bigger gain remains emulator speed and per-session cost (plan P4 and P5), not session count.
