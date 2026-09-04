---
session_id: 2026-08-08_004
title: VLM Metadata Backfill + UNKNOWN Image Folder Bug Fix
date: 2026-08-08
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 4.6
triggered_by: manual-checkpoint
status: complete
original_goal: Backfill VLM classifier metadata columns into the defect coordinates pipeline and fix UNKNOWN image folder routing bug
retroactive: true
logged_date: 2026-08-08
---

## Original Goal
Enrich the defect coordinates pipeline with optical/size metadata columns from `UDB.INSP_DEFECT`
to support VLM classifier training.  Entry condition was that `DEFECT_COORDINATES_EXTENDED.csv`
had no size or optical columns — only geometry and classification labels.  Expected to be a
two-phase SQL + backfill task; the UNKNOWN folder bug was discovered as a consequence of
post-backfill pipeline runs.

## Completed Tasks
- [x] Explored `UDB.INSP_DEFECT` schema via `schema_explorer.py` and `metadata_explorer.py` to identify available columns
- [x] Defined `METROLOGY_COLS = ["SIZE_X", "SIZE_Y", "SIZE_D", "AREA", "MANUAL_OPTICAL_CLASS"]` in `DEFECT_COORDINATES_QUERY.py`
- [x] Added SQL projections for METROLOGY_COLS in `_fetch_defect_coords()`
- [x] Created and ran `backfill_vlm_metadata.py` — 10,203 metadata records retrieved, 99.1% populated
- [x] Identified SIZE_Z (0% populated) and ROUGH_BIN_CLASS (all zeros) as spurious; removed both
- [x] Created and ran `remove_size_z_column.py` and `remove_rough_bin_class_column.py` to clean production CSV
- [x] Added one-line note to `PIPELINE_DESIGN.md` that defect coordinate stage retrieves VLM metadata columns
- [x] Root-caused UNKNOWN image folder bug: column collision in three image-helper functions causing `row.get("LOT7", "UNK")` to return None
- [x] Fixed all three functions (`_reorganize_images`, `_filter_new_images`, `_backfill_local_image_paths`) to exclude already-present columns before merging
- [x] Fixed manifest pre-filter bug: `_filter_defects_needing_images()` was treating null-LOCAL_IMAGE_FILE rows as covered
- [x] Created and ran `cleanup_unknown_images.py` — 38 UNKNOWN files deleted, UNKNOWN/ folder removed, 38 manifest rows cleared
- [x] Ran three verification pipeline runs confirming correct routing and 0 UNKNOWN paths

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py` | Modified | Added METROLOGY_COLS; SQL projections; 3 image-function merge fixes; manifest pre-filter null fix |
| `outputs\defects\DEFECT_COORDINATES_EXTENDED.csv` | Modified | VLM metadata backfilled (SIZE_X/Y/D/AREA/MANUAL_OPTICAL_CLASS); SIZE_Z and ROUGH_BIN_CLASS removed; 35 columns final |
| `outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv` | Modified | 38 UNKNOWN-path manifest rows cleared to null |
| `PIPELINE_DESIGN.md` | Modified | One-line note added: defect coordinate stage now retrieves VLM metadata columns |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `BE_QUERY_FILES\metadata_explorer.py` | Used for DB schema discovery during investigation | No |
| `BE_QUERY_FILES\backfill_vlm_metadata.py` | Executed to populate VLM columns in production CSV | No |
| `BE_QUERY_FILES\remove_size_z_column.py` | Executed to drop SIZE_Z from production CSV | No |
| `BE_QUERY_FILES\remove_rough_bin_class_column.py` | Executed to drop ROUGH_BIN_CLASS from production CSV | No |
| `BE_QUERY_FILES\cleanup_unknown_images.py` | Executed to delete UNKNOWN images and clear manifest rows | No |
| `images\defects\UNKNOWN\` | Deleted (38 jpg files + folder) | No — folder confirmed absent post-cleanup |

## New Utility Scripts Created
| File | Change Type | Notes |
|------|-------------|-------|
| `BE_QUERY_FILES\schema_explorer.py` | Created | One-off DB schema discovery tool for UDB.INSP_DEFECT |
| `BE_QUERY_FILES\metadata_explorer.py` | Created | Interactive metadata column explorer; retained as utility |
| `BE_QUERY_FILES\backfill_vlm_metadata.py` | Created | One-time backfill of VLM metadata columns into production CSV; retained for re-runs |
| `BE_QUERY_FILES\remove_size_z_column.py` | Created | One-time column removal utility |
| `BE_QUERY_FILES\remove_rough_bin_class_column.py` | Created | One-time column removal utility |
| `BE_QUERY_FILES\cleanup_unknown_images.py` | Created | One-time UNKNOWN folder cleanup; retained for audit trail |

## Bugs Encountered

### BUG-001: UNKNOWN image folder — column collision in merge helpers
- **Status:** Resolved
- **File(s):** `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py`
- **Root Cause:** `_enrich_image_rows_with_defect_context()` adds context columns (LOT7, WAFER_ID, CLASS, LAYER, SUBENTITY, SUBENTITY_END_TIME) to `image_df`. Three downstream functions — `_reorganize_images()`, `_filter_new_images()`, `_backfill_local_image_paths()` — each attempted to merge those same columns again from `defects_result`, producing pandas suffix columns (LOT7_x / LOT7_y). `_build_image_destination()` used `row.get("LOT7", "UNK")` which resolved to None for the suffixed variants, causing all path tokens to fall back to defaults and routing every image to `UNKNOWN/000000_0000_UNK_UNKNOWN_UNK_UNKNOWN_{did}_{iid}.jpg`.
- **Fix Applied:** In each of the three functions, compute `wanted` as only those context columns not already present in `img.columns`. Skip the merge entirely if `wanted` is empty.
- **Notes:** Fix is additive and non-breaking — if context columns are already present, merge is skipped cleanly.

### BUG-002: Manifest pre-filter treating null LOCAL_IMAGE_FILE as covered
- **Status:** Resolved
- **File(s):** `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py`
- **Root Cause:** `_filter_defects_needing_images()` built its "already covered" set from manifest rows without filtering out rows where LOCAL_IMAGE_FILE was null or blank. The 38 rows that had been cleared to null after UNKNOWN cleanup were still treated as covered, preventing re-download.
- **Fix Applied:** Added filter to exclude null/blank LOCAL_IMAGE_FILE rows before building the coverage set.
- **Notes:** Without this fix, clearing a manifest path does not trigger re-download on next run.

## Excursions / Scope Creep Discovered
- SIZE_Z column existed in schema but was 0% populated for all queried wafers — trimmed before shipping
- ROUGH_BIN_CLASS column was all zeros (not populated in production data) — trimmed before shipping

## Open Threads
- [ ] THREAD-006: 14 manifest rows still pending — FTP server unavailable for those older wafers. Will resolve on future pipeline runs when images become accessible. No action required now.

## Key Decisions Made
- `METROLOGY_COLS` final set: `["SIZE_X", "SIZE_Y", "SIZE_D", "AREA", "MANUAL_OPTICAL_CLASS"]` — SIZE_Z and ROUGH_BIN_CLASS explicitly excluded as zero/unpopulated in production data
- UNKNOWN folder cleanup was destructive (38 files deleted) but all had manifest coverage or correct-name counterparts on disk — confirmed before deletion
- Merge-skip strategy (vs. rename/drop) chosen for UNKNOWN fix because it is safe if context is already present and does not require restructuring the enrichment flow

## Recommended Re-Entry
**Load these files for context:**
- `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py`
- `outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv`
- `PIPELINE_DESIGN.md`

**Suggested starting prompt:**
> "Session 2026-08-08_004 completed VLM metadata backfill and fixed the UNKNOWN image folder
> routing bug. DEFECT_COORDINATES_EXTENDED.csv has 35 columns and 99.1% VLM metadata coverage.
> The image manifest has 2,447 rows, 2,433 confirmed on disk, 0 UNKNOWN paths, 14 pending FTP.
> The 14 pending rows are THREAD-006. What do you want to work on next?"

## Notes for Future Agent
- The three merge-skip fixes in `DEFECT_COORDINATES_QUERY.py` are intentional — do not revert them if you see `wanted` being filtered before merge. This prevents the column collision that caused the UNKNOWN bug.
- `backfill_vlm_metadata.py` can be re-run safely if new rows need metadata populated — it merges by (WAFER_KEY, DEFECT_ID) and does not overwrite non-null values.
- `cleanup_unknown_images.py` is retained as an audit trail — do not delete it even though the cleanup is complete.
- Final CSV state: `DEFECT_COORDINATES_EXTENDED.csv` — 10,416 rows, 35 columns. `DEFECT_COORDINATES_EXTENDED_IMAGES.csv` — 2,447 rows, 35 columns + image manifest columns.
