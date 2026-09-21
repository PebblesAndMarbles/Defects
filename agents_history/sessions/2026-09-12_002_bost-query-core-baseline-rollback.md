---
session_id: 2026-09-12_002
title: BOST Query Core Baseline Rollback and WIJT Import Cleanup
date: 2026-09-12
time_start: 19:00
time_end: 21:15
agent: GitHub Copilot
model: GPT-5.4 mini
triggered_by: manual-checkpoint
status: partial
original_goal: Re-establish a clean pre-WIJT diagnostic baseline and isolate the Track A / Track B query core behind the remaining 120 missing BOST keys.
retroactive: true
logged_date: 2026-09-12
---

## Original Goal
Rollback the WIJT-specific additions made while investigating the remaining BOST coverage gap, then return to a clean diagnostic state so the unresolved 120-key issue could be inspected without wide-builder noise.

## Completed Tasks
- [x] Confirmed that the missing 120 keys were not caused by LOT7 scope widening.
- [x] Confirmed that the missing 120 keys were not caused by sync-definition preservation, Track A/Track B merge behavior, or the wide/export writeout path.
- [x] Inspected the definition-name to value-column mapping and verified it was one-to-one in the exported map.
- [x] Removed WIJT-specific Track B additions, including sync metadata, alias joins, and prefetch-scope overrides.
- [x] Deleted dead WIJT helper functions that were no longer used in the baseline path.
- [x] Ran repeated syntax checks and rollout reruns after each rollback slice to confirm behavior.
- [ ] Fully isolate the query core against the earlier clean diagnostic baseline.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `BOST\adhoc_bost_gate_rollout.py` | Modified | Added and later removed WIJT-specific query additions; restored toward the baseline diagnostic path; current code still needs query-core isolation work. |
| `agents_history\sessions\2026-09-12_002_bost-query-core-baseline-rollback.md` | Created | Formal checkpoint log for the rollback and inspection work. |
| `agents_history\index.md` | Modified | Added the 2026-09-12_002 session row. |
| `agents_history\file_map.md` | Modified | Added/updated file-map rows for the BOST rollout file and the rerun artifacts. |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `BOST\wijt_BOST3.log` | Used as the WIJT semantic reference trace for the imported query shape. | No |
| `BOST\wijt_BOST3_lotlist.txt` | Context file for the current editor state and lot-lineage comparisons. | No |
| `BOST\adhoc_bost_pilot_enriched_8M5CL_8M6CL.csv` | Rerun output used to verify the current pilot shape after rollback slices. | No |
| `BOST\adhoc_bost_enriched_dryrun_8M5CL_8M6CL.csv` | Rerun output used to verify the dry-run key counts. | No |
| `artifacts\adhoc_bost_pilot_summary.json` | Validation summary for the pilot gate after the rollback work. | No |
| `artifacts\adhoc_bost_dryrun_summary.json` | Validation summary for the full dry run after the rollback work. | No |
| `artifacts\adhoc_bost_full_summary.json` | Latest end-to-end summary used to confirm the key delta remained 1022/1142. | No |
| `artifacts\adhoc_bost_definition_columns.csv` | Diagnostic artifact used to verify the definition-name to value-column mapping. | No |

## Bugs Encountered
### BUG-001: WIJT import slices temporarily changed the wide output shape
- **Status:** Resolved
- **File(s):** `BOST\adhoc_bost_gate_rollout.py`
- **Root Cause:** WIJT-specific replay and wide-builder experiments changed the value-column projection and briefly collapsed/expanded the wide output shape.
- **Fix Applied:** Rolled back the WIJT-specific additions and wide-builder experiment, then validated the rollback with repeated compile and rollout runs.
- **Notes:** The 120-key issue remained unchanged, which is why query-core isolation is still pending.

### BUG-002: Dead WIJT helper code remained in the rollout file after rollback
- **Status:** Resolved
- **File(s):** `BOST\adhoc_bost_gate_rollout.py`
- **Root Cause:** `_load_wijt_lot_list()`, `_load_wijt_prefetch_scope()`, and `_run_wijt_style_treatment_query()` were no longer referenced but still present.
- **Fix Applied:** Removed the unused helpers and cleaned the surrounding WIJT-specific comments.
- **Notes:** This was cleanup only; it did not affect the coverage gap.

## Excursions / Scope Creep Discovered
- The attempt to mirror WIJT wholesale introduced a wide-builder experiment that obscured the row-level coverage problem.
- The definition-name to value-column mapping was not the missing-key root cause, even though it helped explain the 8-column artifact state.

## Open Threads
- [ ] THREAD-037: Fix known `_extract_def_name_from_track_b()` layer-agnostic-normalization data-loss bug in `BOST\adhoc_bost_gate_rollout.py` — the real fixable root cause of the remaining coverage gap.

## Key Decisions Made
- Keep the BOST rollout harness local and treat WIJT as a semantic reference, not a wholesale replacement.
- Restore the baseline diagnostic shape before attempting any more query-core changes.
- Keep THREAD-037 open because the remaining coverage gap is still unresolved.

## Recommended Re-Entry
**Load these files for context:**
- `BOST\adhoc_bost_gate_rollout.py`
- `BOST\wijt_BOST3.log`
- `artifacts\adhoc_bost_full_summary.json`

**Suggested starting prompt:**
> "Continue from the cleaned BOST baseline and isolate the Track A / Track B query core against the remaining 120 missing keys. Focus on the row-level coverage delta, not the wide-pivot or export layers."

## Notes for Future Agent
The rollback work confirmed the key-count delta stayed at 1022/1142 through LOT7 scoping, sync-definition work, and merge/writeout inspection. The session should be continued by fixing the data-loss bug called out in THREAD-037, not by reintroducing the WIJT replay helpers.