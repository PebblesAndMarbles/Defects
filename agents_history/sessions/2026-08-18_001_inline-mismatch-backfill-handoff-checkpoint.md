---
session_id: 2026-08-18_001
title: INLINE Mismatch Backfill Handoff Checkpoint
date: 2026-08-18
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: GPT-5.4 mini
triggered_by: manual-checkpoint
status: partial
original_goal: Investigate the production-versus-inline NCDD mismatch pattern, document the findings, and prepare a handoff for backfill work.
retroactive: true
logged_date: 2026-08-18
---

## Original Goal
Confirm the mismatch pattern between production NCDD metrics and the inline correlation outputs, determine whether the timing points to lookback loss, and prepare a handoff document plus supporting artifacts for a follow-on backfill/pipeline update.

## Completed Tasks
- [x] Compared production BEEP_NCDD / SMP_NCDD against inline BEEP / SMALL_PARTICLE values at wafer-level keys.
- [x] Verified the join uses `LOT` / `ACTUAL_LOT@DEFECT`, `WAFER_ID`, `LAYER`, and `INSPECT_TIME` / `INSPECTION_TIME@DEFECT`.
- [x] Quantified the absolute delta distribution and confirmed it is mostly zero with a sparse right tail.
- [x] Added histogram, probability, and timing plots under `rollups\INLINE_MISMATCHES`.
- [x] Confirmed the mismatch onset is late April 2026, consistent with the current update-window change.
- [x] Verified the stable long-source CSVs (`8M5CL_NCDD_EDI_LONG.csv`, `8M6CL_NCDD_EDI_LONG.csv`) and their inspection-time spans.
- [x] Drafted a handoff document describing the schema, findings, and recommended backfill approach.
- [x] Isolated the remaining >1% events to three today-only wafer/time cases and marked them excused for now.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `rollups\INLINE_MISMATCHES\inline_mismatch_distribution.py` | Modified | Added inspection-time tracking and the daily timing plot for mismatch counts/rates |
| `rollups\INLINE_MISMATCHES\inline_mismatch_distribution_summary.csv` | Created / Updated | Summary statistics for the delta distribution |
| `rollups\INLINE_MISMATCHES\inline_mismatch_histogram.png` | Created / Updated | Histogram of absolute BEEP and SMP deltas |
| `rollups\INLINE_MISMATCHES\inline_mismatch_probability.png` | Created / Updated | Tail probability plot for the delta distribution |
| `rollups\INLINE_MISMATCHES\inline_mismatch_timing.png` | Created / Updated | Daily mismatch timing / rate plot |
| `rollups\INLINE_MISMATCHES\INLINE_MISMATCH_BACKFILL_HANDOFF.md` | Created | Handoff note for the follow-on backfill / pipeline agent |
| `agents_history\index.md` | Modified | Added this checkpoint to the session index |
| `agents_history\file_map.md` | Modified | Recorded the session log and touched files |
| `agents_history\sessions\2026-08-18_001_inline-mismatch-backfill-handoff-checkpoint.md` | Created | Formal checkpoint log |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py` | Likely source-window change point associated with late-April mismatches | Yes, for follow-on review |
| `BE_QUERY_FILES\8M5CL_NCDD_EDI_LONG.csv` | Stable nightly long-lookback source for 8M5CL backfill | Yes, for backfill implementation |
| `BE_QUERY_FILES\8M6CL_NCDD_EDI_LONG.csv` | Stable nightly long-lookback source for 8M6CL backfill | Yes, for backfill implementation |
| `outputs\defects\DEFECT_COORDINATES_EXTENDED.csv` | Production metrics CSV compared against inline sources | Yes, for future refresh / dedup repair |
| `rollups\INLINE_MODE_CORRELATIONS\8M5CL_NCDD_EDI_SHORT.csv` | Short inline comparison source used in the audit | No |
| `rollups\INLINE_MODE_CORRELATIONS\8M6CL_NCDD_EDI_SHORT.csv` | Short inline comparison source used in the audit | No |

## Bugs Encountered
### BUG-001: One-off shell quoting issue while checking long CSV spans
- **Status:** Resolved
- **File(s):** None
- **Root Cause:** The inline Python one-liner used a newline sequence that PowerShell passed through poorly.
- **Fix Applied:** Reran the inspection command in a safer single-line form.
- **Notes:** No data or file corruption occurred.

## Excursions / Scope Creep Discovered
- The timing analysis showed the mismatches begin in late April 2026, which makes this look like a source-window / refresh-window issue rather than a defect in the Python merge logic.
- A dedicated backfill document is now needed so a follow-on agent can implement the repair without re-deriving the audit context.
- Three >1% wafer/time events fell on 2026-08-18 and were reviewed as same-day exceptions. They are excused for now and should not be treated as the main backfill target.

## Open Threads
- [ ] Implement backfill logic that uses the stable long CSVs as the repair source.
- [ ] Update the production pipeline so late-arriving mismatches can be refreshed regularly.
- [ ] Decide whether the backfill should start at late April 2026 or use a slightly wider guard band.

## Key Decisions Made
- Treat the production Python merge/dedup logic as likely correct unless the backfill work finds a new defect.
- Use the stable nightly long-lookback CSVs as the authoritative source for repair work.
- Preserve the current audit artifacts so the follow-on agent can validate the repair against the same metric definitions.
- Excuse the three today-only >1% wafer/time events from the immediate remediation queue.

## Recommended Re-Entry
**Load these files for context:**
- `rollups\INLINE_MISMATCHES\INLINE_MISMATCH_BACKFILL_HANDOFF.md`
- `rollups\INLINE_MISMATCHES\inline_mismatch_distribution.py`
- `agents_history\index.md`
- `agents_history\file_map.md`

**Suggested starting prompt:**
> "Continue from the INLINE mismatch backfill handoff. Implement a repair path that uses the long 180-day CSVs as the authoritative source, backfill the late-April-and-later mismatches into the production metrics CSV, and update the refresh pipeline so these fixes can run regularly."

## Notes for Future Agent
The important context is that the mismatches are sparse, mostly zero, and begin in late April 2026. The stable long CSVs now exist at fixed paths and should be treated as the repair source for the backfill work.
