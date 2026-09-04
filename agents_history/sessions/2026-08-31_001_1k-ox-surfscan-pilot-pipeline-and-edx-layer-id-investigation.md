---
session_id: 2026-08-31_001
title: 1K OX SurfScan Pilot Pipeline Build + EDX LAYER_ID Investigation
date: 2026-08-31
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 5
triggered_by: manual-checkpoint
status: partial
original_goal: Scope and pilot a new "1K OX SurfScan" pipeline (LAYER_ID = 6OX450GTO_M025_PST) as a standalone, non-production build against the existing SURF_SCAN_PIPELINE_DESIGN.md architecture, then resolve an EDX LAYER_ID question raised for a specific lot.
retroactive: true
logged_date: 2026-09-02
---

## Original Goal
Determine whether a new SurfScan layer (`6OX450GTO_M025_PST`) could be supported by
a pipeline modeled on the existing production BARE SurfScan architecture
(`SURF_SCAN_PIPELINE_DESIGN.md`), without touching production `BE_QUERY_FILES`. Build
a standalone pilot to validate the approach, then separately investigate whether a
lot's EDX data requires a distinct EDX-submission `LAYER_ID` join.

## Completed Tasks
- [x] Scoped the "1K OX SurfScan" pipeline via a standalone smoke-test script (`scope_1k_ox_smoke_test.py`)
- [x] Confirmed AME-only chamber universe for this layer (`PROCESS_EQUIP_ID LIKE 'AME%'`); found 51 AME chambers + 3 non-AME GTO tools (`GTO441_PC3`, `GTO449_PC3`, `GTO449_PC5`) also on this layer
- [x] Identified the actual etch chamber recipe behind this layer (`M_UBE_MIMIC_R4`) via `F_WaferChamberHist` nearest-match against the ELWC join
- [x] Confirmed PM RF counter availability (`FullPMRFCounter`/`MiniPMRFCounter` via `F_ENTITYATTRIBUTEHIST`) for all 51 discovered AME chambers
- [x] Confirmed no sibling SEG/PRE layer is needed for this pipeline
- [x] Built standalone pilot pipeline under `rollups\1K_OX_PILOT_PIPELINE\` (config, coordinates/enrichment logic, seed/update CLI entrypoints)
- [x] Ran initial seed pull since floor timestamp `2026-08-05 14:38:48`, AME-only filter, SS0/SS1/SS7 run-grouping convention (ported from production BARE pipeline)
- [x] Diagnosed and fixed mixed `FULLPM_RF`/`MINIPM_RF` coverage bug (root cause: Full/Mini counter snapshots logged at distinct, alternating `TXN_DATE` values, ~10 min apart; single nearest-match against a wide pivot table starved one column)
- [x] Diagnosed and fixed missing pilot-status columns bug by porting `_add_pilot_status`/`_create_pilot_status_from_flags` from production `BE_QUERY_FILES\surf_scan_coordinates.py`, keyed against `BE_AME_PILOT_TURN_ON_DATES.csv` (`SUBENTITY == PROCESS_EQUIP`)
- [x] Re-ran seed and ran an update pull after both fixes; outputs regenerated (`OX_COORDINATES.csv`, `OX_METRICS.csv`)
- [x] Investigated EDX `LAYER_ID` question for lot `D629T8V0` (inspection time `2026-08-06 09:06:43`); tested 3 user-proposed candidate `LAYER_ID` guesses against `UDB.INSP_WAFER_SUMMARY` -- all confirmed non-existent
- [x] Confirmed EDX elemental data (`UDB.INSP_ELEMENT`) is already attached directly to the original UDE scan's `WAFER_KEY`/`INSPECTION_TIME`/`DEFECT_ID`, with no separate EDX-submission `LAYER_ID` needed -- matches production's `_fetch_edx_data()` join pattern in `BE_QUERY_FILES\surf_scan_coordinates.py` exactly
- [x] Found an unrelated real layer `MBTW_EDX_API` (different tool family, `SRC403`/`SRC414` inspect equipment) -- confirmed zero rows for this lot, not applicable
- [ ] Decide whether to wire the direct `INSP_ELEMENT` EDX join into the OX pilot pipeline now, or hold off until imaging scope is defined (open, unanswered as of session end)

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `rollups\1K_OX_PILOT_PIPELINE\scope_1k_ox_smoke_test.py` | Created | 4-step standalone scoping/smoke-test script (tool universe, AME defect sample, PM counter availability, ELWC join check) |
| `rollups\1K_OX_PILOT_PIPELINE\scope_1k_ox_smoke_test_summary.json` | Created | Scoping run output: 51 AME chambers, 3 non-AME GTO tools, `M_UBE_MIMIC_R4` recipe confirmed, 104 PM-counter-available chambers |
| `rollups\1K_OX_PILOT_PIPELINE\step1_tool_universe.csv` | Created | Step 1 raw output: PROCESS_EQUIP/INSPECT_EQUIP/RECIPE_ID universe for this layer |
| `rollups\1K_OX_PILOT_PIPELINE\step2_ame_defect_sample.csv` | Created | Step 2 raw output: AME-chamber defect join sample |
| `rollups\1K_OX_PILOT_PIPELINE\step3_pm_counter_availability.csv` | Created | Step 3 raw output: PM RF counter availability by chamber |
| `rollups\1K_OX_PILOT_PIPELINE\step4_elwc_join_check.csv` | Created | Step 4 raw output: ELWC chamber-history join check |
| `rollups\1K_OX_PILOT_PIPELINE\step5_actual_chamber_recipe_match.csv` | Created | Nearest-match result identifying `M_UBE_MIMIC_R4` as the real etch chamber recipe |
| `rollups\1K_OX_PILOT_PIPELINE\step6_related_layer_ids.csv` | Created | Check confirming no sibling SEG/PRE layer needed |
| `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_config.py` | Created | Shared config: `STEP_LAYER_ID=6OX450GTO_M025_PST`, `CHAMBER_RECIPE=M_UBE_MIMIC_R4`, `FLOOR_TIME=2026-08-05 14:38:48`, AME-only chamber filter, SS0/SS1/SS7 event map, pilot-status column config |
| `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_coordinates.py` | Created; later modified (bug fixes) | Core query/enrichment logic; seed/update modes; `_attach_pm_counters_nearest` rewritten to per-column independent nearest-match; `_add_pilot_status`/`_create_pilot_status_from_flags` ported from production |
| `rollups\1K_OX_PILOT_PIPELINE\run_seed.py` | Created | CLI entrypoint: full seed pull since `FLOOR_TIME`, overwrites outputs |
| `rollups\1K_OX_PILOT_PIPELINE\run_update.py` | Created | CLI entrypoint: incremental pull since `max(FLOOR_TIME, now - overlap_days)`, replaces overlap window, preserves older rows |
| `rollups\1K_OX_PILOT_PIPELINE\outputs\OX_COORDINATES.csv` | Created | Pilot coordinates output (post both bug fixes) |
| `rollups\1K_OX_PILOT_PIPELINE\outputs\OX_METRICS.csv` | Created | Pilot metrics output (post both bug fixes); 131 rows, 74 preserved from prior run on last update |
| `rollups\1K_OX_PILOT_PIPELINE\artifacts\ox_pilot_seed_summary.json` | Created | Seed-run summary: 51 chambers queried since floor time |
| `rollups\1K_OX_PILOT_PIPELINE\artifacts\ox_pilot_update_summary.json` | Created | Update-run summary: 7-day overlap window, 57 wafer-summary rows, 429 defect rows, 131 metrics rows post-merge |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_layer_id.py` | Created | Probe script: queries `UDB.INSP_WAFER_SUMMARY` around lot `D629T8V0`/scan time `2026-08-06 09:06:43` for candidate EDX layer rows; checks `MBTW_EDX_API` |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_layer_id_v2.py` | Created | Follow-on probe iteration |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_layer_id_v3.py` | Created | Follow-on probe iteration |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_layer_id_v4.py` | Created | Final probe iteration confirming `MBTW_EDX_API` returns zero rows for this lot |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q1_lot_window_layers.csv` | Created | Probe output: all LAYER_ID rows for the lot within a time window after the scan |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q2_lot_edx_layers.csv` | Created | Probe output: lot-scoped EDX-candidate layer check |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q3_fleet_edx_layers.csv` | Created | Probe output: fleet-wide EDX-candidate layer check |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q4_insp_element_direct.csv` | Created | Probe output confirming `UDB.INSP_ELEMENT` rows attach directly to the original scan's `WAFER_KEY`/`INSPECTION_TIME`/`DEFECT_ID` (no separate LAYER_ID needed) |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q5_baresi_udc_layers.csv` | Created | Probe output: existence check for `6BARESI_EDX_UDC` guess -- no rows |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q6_exact_guessed_layers.csv` | Created | Probe output: existence check for all 3 user-proposed candidate LAYER_IDs -- header only, no rows (none exist) |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q7_lot_full_history.csv` | Created | Probe output: full LAYER_ID history for the lot across all steps |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `SURF_SCAN_PIPELINE_DESIGN.md` | Architectural reference for the pilot pipeline design (run-grouping, event mapping, pilot-status pattern) | No |
| `BE_QUERY_FILES\surf_scan_coordinates.py` | Source of `_add_pilot_status`/`_create_pilot_status_from_flags` (ported) and `_fetch_edx_data()` (pattern match confirmed, not yet ported) | Possibly -- if EDX join is wired into the pilot (see Open Threads) |
| `BE_AME_PILOT_TURN_ON_DATES.csv` (outside workspace root, `Defects\BE_AME_PILOT_TURN_ON_DATES.csv`) | Pilot-status join source, keyed on `SUBENTITY == PROCESS_EQUIP` | No |

## Bugs Encountered
### BUG-001: Mixed FULLPM_RF/MINIPM_RF coverage after initial seed run
- **Status:** Resolved
- **File(s):** `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_coordinates.py`
- **Root Cause:** `FullPMRFCounter` and `MiniPMRFCounter` snapshots are logged at distinct, alternating `TXN_DATE` timestamps (never simultaneously, ~10 minutes apart). A single nearest-match against a wide pivot table landed on whichever counter was logged closest overall, leaving the other column null even when a nearby value existed for it.
- **Fix Applied:** Rewrote `_attach_pm_counters_nearest` to perform independent per-column `merge_asof` nearest-match, each using only its own non-null snapshots, instead of one merge against a wide pivot.
- **Notes:** This pattern (alternating counter snapshot timestamps) may recur for any future PM-counter attach logic modeled on this pipeline.

### BUG-002: Missing pilot-status columns after initial seed run
- **Status:** Resolved
- **File(s):** `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_coordinates.py`, `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_config.py`
- **Root Cause:** The pilot pipeline was built without porting the pilot-status derivation logic (`CCMR2`/`ICCR2`/`GF`/`CV`/`SRCIP`/`TS`/`PILOT_STATUS`/`DCS_POST_ICC_FIX`) present in the production BARE pipeline.
- **Fix Applied:** Ported `_add_pilot_status` and `_create_pilot_status_from_flags` from `BE_QUERY_FILES\surf_scan_coordinates.py`, keyed against `BE_AME_PILOT_TURN_ON_DATES.csv` (`SUBENTITY == PROCESS_EQUIP`).
- **Notes:** None.

## Excursions / Scope Creep Discovered
- The EDX LAYER_ID investigation for lot `D629T8V0` was a tangential question raised mid-session, unrelated to the OX pilot's core scoping/build work, but resolved within the same session.

## Open Threads
- [ ] Wire the direct `UDB.INSP_ELEMENT` EDX join into the OX pilot pipeline now, or hold off until imaging scope for the pilot is defined -- user has not yet answered (see THREAD-026 below)

## Key Decisions Made
- Kept the "1K OX SurfScan" pipeline entirely standalone under `rollups\1K_OX_PILOT_PIPELINE\`, deliberately NOT wired into production `BE_QUERY_FILES`, pending further validation.
- Confirmed no sibling SEG/PRE layer is needed for this pipeline (rejected building one).
- Chose per-column independent nearest-match for PM counters over a single wide-pivot merge, after confirming the alternating-timestamp root cause.
- Rejected all 3 user-proposed candidate EDX LAYER_ID guesses (`6BARESI_EDX_UDC`, `6OXIDE_EDX_UDC_100`, `MBTW_MPLVCAOX450_EDX`) after direct existence queries against `UDB.INSP_WAFER_SUMMARY` returned zero rows for each.
- Determined that no separate EDX-submission LAYER_ID is needed at all for this lot/pipeline -- `UDB.INSP_ELEMENT` already joins directly to the original UDE scan's `WAFER_KEY`/`INSPECTION_TIME`/`DEFECT_ID`, matching the existing production `_fetch_edx_data()` pattern exactly.
- `MBTW_EDX_API` was identified as a real, existing layer but explicitly rejected as inapplicable to this lot (different tool family, `SRC403`/`SRC414` inspect equipment, zero rows for lot `D629T8V0`).

## Recommended Re-Entry
**Load these files for context:**
- `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_config.py`
- `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_coordinates.py`
- `rollups\1K_OX_PILOT_PIPELINE\probe_edx_layer_id_v4.py`
- `BE_QUERY_FILES\surf_scan_coordinates.py` (for `_fetch_edx_data()` reference)

**Suggested starting prompt:**
> "Read `rollups/1K_OX_PILOT_PIPELINE/ox_pilot_config.py` and `ox_pilot_coordinates.py` in full, plus `_fetch_edx_data()` in `BE_QUERY_FILES/surf_scan_coordinates.py`. Decide whether to wire the direct `UDB.INSP_ELEMENT` EDX join into the OX pilot pipeline now, following the same pattern as production, or hold off until the pilot's imaging scope is defined."

## Notes for Future Agent
- The OX pilot pipeline is intentionally NOT wired into production `BE_QUERY_FILES` -- do not merge it in without explicit user direction.
- The per-column independent nearest-match fix for PM counters (`_attach_pm_counters_nearest`) is a deliberate design choice, not an oversight -- do not revert to a single wide-pivot merge.
- All EDX-layer-guess CSVs (`probe_edx_q5`/`q6`) confirming non-existent LAYER_IDs are retained as negative-result evidence; do not re-investigate those same 3 candidate names without new information.
