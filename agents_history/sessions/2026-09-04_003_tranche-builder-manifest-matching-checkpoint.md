---
session_id: 2026-09-04_003
title: Tranche Builder Manifest Matching Checkpoint
date: 2026-09-04
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: GPT-5.4 mini
triggered_by: manual-checkpoint
status: complete
original_goal: Fix build_beep_labeling_tranche.py so it correctly matches raw-cache manifest rows and verify tranche 0014 regenerates cleanly from disk.
---

## Original Goal
Trace why tranche 0014 was redownloading cases that appeared to exist in the raw cache, then fix the tranche builder so it recognizes the manifest format and resumes pulling cases from disk.

## Completed Tasks
- [x] Inspected the tranche builder join path and the raw-cache manifest layout.
- [x] Patched `images\Alloy_Class\tools\build_beep_labeling_tranche.py` to use a normalized `wafer_key + inspection_time + defect_id` join key plus `image_id`-specific bright/dark lookups.
- [x] Added `_inspection_time_norm()` and `_join_key()` helpers so the builder and missing-row diagnostics use the same normalization logic.
- [x] Kept the `C:\RAW_IMAGES` cache-root default and preserved redownload as a fallback only when `--allow-redownload` is set.
- [x] Added explicit logging for missing manifest join rows before any redownload attempt.
- [x] Verified the focus pair `7706480_20260409_174745_679` resolves to both manifest rows with `download_status=ok`.
- [x] Confirmed tranche 0014 regenerates cleanly from disk after stale outputs were removed, and the report/portal connection remains intact.
- [x] Reviewed and corrected the session notes so the recorded status matches the actual builder behavior.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\tools\build_beep_labeling_tranche.py` | Modified | Replaced the merge-style manifest attachment with explicit normalized join-key lookups against `C:\RAW_IMAGES\manifest.csv`; added missing-row diagnostics. |
| `images\Alloy_Class\outputs\beep_evidence\tranche_0014_cases.csv` | Modified | Regenerated from disk after the tranche-builder fix. |
| `agents_history\sessions\2026-09-04_003_tranche-builder-manifest-matching-checkpoint.md` | Created | Formal checkpoint log for this session. |
| `agents_history\index.md` | Modified | Added the new 2026-09-04_003 session row. |
| `agents_history\file_map.md` | Modified | Registered the workspace files touched in this session. |

## Files Affected (referenced but not modified)
None beyond the files above.

## Bugs Encountered
### BUG-001: Manifest rows were not being matched by the tranche builder
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\tools\build_beep_labeling_tranche.py`
- **Root Cause:** The previous attachment path was too dependent on the old merge-style flow and did not robustly normalize the manifest join fields in the same way as the manual trace.
- **Fix Applied:** Added normalized join-key helpers and explicit bright/dark lookups keyed by `image_id`.
- **Notes:** The builder now logs missing manifest rows before attempting any fallback redownload.

## Excursions / Scope Creep Discovered
- Reviewed the session log and plan notes to make sure the recorded state matched the actual tranche-builder behavior.

## Open Threads
- None.

## Key Decisions Made
- Keep `--allow-redownload` as a fallback only; do not make redownload the primary path when manifest rows are missing.
- Use one normalized join key for both tracing and matching so the code path mirrors the manual provenance check.
- Leave the `C:\RAW_IMAGES` default in place so the builder continues to prefer the persistent raw-cache layout.

## Recommended Re-Entry
**Load these files for context:**
- `images\Alloy_Class\tools\build_beep_labeling_tranche.py`
- `images\Alloy_Class\outputs\beep_evidence\tranche_0014_cases.csv`

**Suggested starting prompt:**
> "Review `images\Alloy_Class\tools\build_beep_labeling_tranche.py` and confirm the manifest-match logic still uses the normalized join key plus image-id-specific lookups, then decide whether any follow-up cleanup is needed for the tranche 0014 output files."

## Notes for Future Agent
- The fix is already in place; do not reintroduce the old merge-style attachment path unless there is a concrete regression.
- The tranche builder now reports missing manifest rows explicitly before any fallback redownload attempt.
