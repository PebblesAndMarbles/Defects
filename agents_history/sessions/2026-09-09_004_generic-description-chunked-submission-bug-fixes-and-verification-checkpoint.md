---
session_id: 2026-09-09_004
title: Generic Description Chunked Submission Bug Fixes and Verification Checkpoint
date: 2026-09-09
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 4.6
triggered_by: manual-checkpoint
status: complete
original_goal: Fix real duplicate-submission and crash bugs found while running the chunked generic-description VLM pipeline against production data, recover affected data without re-spending API calls, clean up the processed registry, and reconcile/verify the multiple prior-agent checkpoint logs describing this same effort into one coherent record.
---

## Original Goal
Continue the Alloy_Class generic-description chunked/incremental VLM submission work (`tools/run_generic_description_chunked.py` + registry-based exclusion in `tools/probe_generic_description.py`), which had already been built by other agent sessions per the handoff doc's "Step 1 continuation" design. While running it for real against production data, debug and fix the actual duplicate-submission and crash bugs encountered, recover any in-flight work without wasting API spend, and -- since three other checkpoint logs describing adjacent/overlapping parts of this same effort appeared around the same time -- verify their claims against real on-disk artifacts before writing a final reconciled checkpoint.

## Completed Tasks
- [x] Fixed a preflight-check tautology bug in `tools/run_generic_description_chunked.py` (`--pfc` compared an unfiltered, wrongly-sorted reimplementation against the registry instead of the real exclusion-aware selection logic).
- [x] Found and fixed the actual root cause of duplicate VLM submissions in `tools/probe_generic_description.py`: `_select_local_cache_pairs()` computed its exclusion join-key from the manifest's separate `inspection_time` column (truncated to the minute), while the registry was always populated using the full-precision timestamp embedded in `case_id` -- the two join keys never matched, so exclusion silently never worked. Fixed to derive the join-key timestamp from `case_id` consistently. Verified directly against real data (two user-reported duplicate cases, then a live registry check showing zero overlap on the next 400 candidates).
- [x] Fixed a manifest-CSV write crash (`ValueError: dict contains fields not in fieldnames: 'raw_text'`) caused by `csv.DictWriter` using only row 0's keys as the fixed column set, when parsed-failure rows add an extra `raw_text` key. Fixed to compute the fieldname union across all rows.
- [x] Fixed the processed registry silently accumulating duplicates on every append (`_append_processed_registry()` never checked for existing keys, unlike the orchestrator's seed function). Fixed to skip already-registered keys.
- [x] Recovered a crashed 400-case chunk (`.../20260908T052401Z/chunk_001/`) entirely from its already-complete JSONL (400 rows, 399 `ok`) without any new VLM calls: rebuilt the manifest CSV (first attempt only matched 238/400 image paths due to a join-key inconsistency in the recovery script itself, caught and fixed to 400/400), registered the 399 successful cases, rebuilt the HTML review.
- [x] Performed a one-time registry cleanup: deduped `generic_description_processed_registry.csv` from 1199 -> 806 rows (backup preserved as `generic_description_processed_registry_backup_before_dedupe.csv`).
- [x] Confirmed to the user that the existing `run_generic_description_chunked.py` command (with its original `--seed-jsonl`) needs no modification to continue further tranches -- the registry at `--registry-root` already reflects the full accumulated state, and re-seeding from the old file is a harmless no-op.
- [x] Updated `images/Alloy_Class/docs/HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md` with a full status section covering all of the above.
- [x] Verified three other checkpoint logs written around the same time by other agent sessions (`2026-09-09_001`, `2026-09-09_002_generic-description-registry-bootstrap-and-tranche-fix`, `2026-09-09_003`) against real on-disk artifacts, since their "Files Modified" sections mostly/only listed `agents_history\` files (a known hollow-log red flag) and one of them (a duplicate of `_003`, wrongly also numbered `_002`) was a literal byte-for-byte duplicate causing a session-ID collision. Confirmed via direct file inspection that all three real logs are legitimate and grounded:
  - `_001`'s claim of an 806-row, registry-preserving consolidation (vs. a rejected 10,895-row left-join variant) is confirmed by `generic_description_consolidated_v9_test3/generic_description_v9_consolidation_summary.json` (`registry_rows: 806, consolidated_jsonl_rows: 806, consolidated_manifest_rows: 806, "join_mode": "registry-preserving"`).
  - `_002` (`generic-description-registry-bootstrap-and-tranche-fix.md`) matches this session's own firsthand knowledge of `run_generic_description_chunked.py`'s registry-workspace/seed-copy/`--pfc` design.
  - `_003`'s claim of 4 filtered HTML reports (circle, `defect_count_gt1`, `truth_alignment_state=mismatched`, `current_reclass != SMALL_PARTICLE`) is confirmed by the actual files present in `generic_description_consolidated_v9_test3/generic_description_v9_enriched/`.
- [x] Verified the broader follow-on checkpoint state remains coherent with the 2026-09-09 fixes: the handoff doc still describes the registry-preserving bridge from the deduped 806-row registry into downstream enrichment, and the surf-scan backfill summary artifact is still present on disk for the event-wafer/time-window-fix branch.
- [x] Deleted the duplicate/orphaned session log (`2026-09-09_002_alloy-generic-description-chunked-submission-follow-through-checkpoint.md`) that was never actually referenced in `index.md`/`file_map.md` and was byte-for-byte identical to `_003`.
- [x] Fixed a duplicated `THREAD-029` entry and stale "Last Updated" headers in `open_threads.md`/`index.md`.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\tools\probe_generic_description.py` | Modified | Join-key precision fix in `_select_local_cache_pairs()`, manifest-CSV union-fieldnames write fix, `_append_processed_registry()` dedup-on-write fix. |
| `images\Alloy_Class\tools\run_generic_description_chunked.py` | Modified | Preflight-check fix: imports and reuses the real `_select_local_cache_pairs()` instead of a drifted, non-discriminating reimplementation. |
| `images\Alloy_Class\docs\HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md` | Modified | Added a full "STATUS UPDATE 2026-09-08" section documenting all bugs/fixes/current data status. |
| `C:\RAW_IMAGES\generic_description_registry\generic_description_processed_registry.csv` | Modified (data) | Deduped 1199 -> 806 rows; backup preserved alongside it. |
| `C:\RAW_IMAGES\generic_description_registry\generic_description_next_generic_description_v9_20260908T052401Z\chunk_001\*_manifest.csv`, `*_review.html` | Modified (data) | Recovered/rewritten after the manifest-CSV crash, using the already-complete JSONL (no new VLM calls). |
| `agents_history\sessions\2026-09-09_002_alloy-generic-description-chunked-submission-follow-through-checkpoint.md` | Deleted | Byte-for-byte duplicate of `_003`; never referenced in `index.md`/`file_map.md`; was causing a session-ID collision with the legitimate `_002` bootstrap log. |
| `agents_history\open_threads.md` | Modified | Removed duplicated `THREAD-029` block, fixed stale "Last Updated" header, added `THREAD-031`. |
| `agents_history\index.md` | Modified | Fixed stale "Last Updated" header; new row for this session (see below). |
| `agents_history\file_map.md` | Modified | Registered this session's file changes. |
| `agents_history\sessions\2026-09-09_004_generic-description-chunked-submission-bug-fixes-and-verification-checkpoint.md` | Created | This checkpoint log. |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\tools\consolidate_generic_description_registry.py` | Verified (via its test-run summary.json and output files) as a real, non-hollow, registry-preserving implementation. Not modified this session. | No |
| `images\Alloy_Class\tools\enrich_production_with_vlm_attributes.py` | Downstream enrichment consumer of the consolidated JSONL/manifest; unchanged. | No |
| `agents_history\sessions\2026-09-09_001_alloy-generic-description-registry-consolidation-checkpoint.md` | Verified legitimate; no changes needed. | No |
| `agents_history\sessions\2026-09-09_002_generic-description-registry-bootstrap-and-tranche-fix.md` | Verified legitimate; kept as the real `_002`. | No |
| `agents_history\sessions\2026-09-09_003_alloy-generic-description-chunked-submission-follow-through-checkpoint.md` | Verified legitimate; kept as-is. | No |
| `artifacts\surf_scan_event_wafer_backfill_summary.json` | On-disk summary artifact for the surf-scan event-wafer backfill / time-window-fix state. | No |

## Bugs Encountered
### BUG-001: Preflight check (`--pfc`) never actually tested the real exclusion path
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\tools\run_generic_description_chunked.py`
- **Root Cause:** `_select_local_cache_pairs_preview()` was a separate reimplementation that never applied the registry exclusion set and sorted by the wrong key (the concatenated `join_key` string instead of `(inspection_time, wafer_key, defect_id)`), making the check either a guaranteed false-positive or non-discriminating either way.
- **Fix Applied:** Import and reuse the real `_select_local_cache_pairs()` from `probe_generic_description.py` directly, passing the actual exclusion set.
- **Notes:** This fix alone did not resolve the actual duplicate-submission bug (see BUG-002); it only made the safety check trustworthy.

### BUG-002: Join-key precision mismatch caused real duplicate VLM submissions
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\tools\probe_generic_description.py`
- **Root Cause:** `C:\RAW_IMAGES\manifest.csv` stores the same timestamp two ways: `case_id` embeds full-precision seconds (e.g. `2026-09-01 19:15:17`), but the separate `inspection_time` column is truncated to the minute (e.g. `9/1/2026 19:15`, seconds always `:00`). The processed registry was always populated using the full-precision (case_id-derived) value, but `_select_local_cache_pairs()` computed its exclusion join-key from the truncated `inspection_time` column, so the exclusion check could never match -- every chunk silently reprocessed already-done defects.
- **Fix Applied:** `_select_local_cache_pairs()` now derives its join-key timestamp from `case_id` (via `_parse_case_id`), matching what the registry actually stores.
- **Notes:** Verified directly: two user-reported duplicate cases (`9231451/305`, `8553317/2371`) confirmed excluded after the fix; a live check against the real 407-entry registry at the time showed zero overlap with the next 400 candidates.

### BUG-003: Manifest-CSV write crash on parsed-failure rows
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\tools\probe_generic_description.py`
- **Root Cause:** The final manifest CSV writer used `list(output_manifest_rows[0].keys())` as the fixed `csv.DictWriter` fieldname set. Rows where the VLM's JSON response failed to parse add an extra `raw_text` key via `_flatten_parsed_fields()`, which successfully-parsed rows don't have -- `writer.writerows()` raised `ValueError: dict contains fields not in fieldnames: 'raw_text'` on any later row with that key.
- **Fix Applied:** Compute the fieldname set as the union of keys across all rows (plus `extrasaction="ignore"` as a defensive backstop, matching the pattern already used in `enrich_production_with_vlm_attributes.py`).
- **Notes:** This crash killed a real 400-case chunk mid-write (347/400 manifest rows survived) and prevented the registry append for that chunk entirely (see recovery below).

### BUG-004: Processed registry accumulated duplicates on every append
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\tools\probe_generic_description.py`
- **Root Cause:** `_append_processed_registry()` never checked for existing keys before writing, unlike the orchestrator's own seed function (`_seed_registry_from_jsonl()`), which does dedupe.
- **Fix Applied:** Load existing keys via `_load_processed_registry()` and skip any already present before appending.
- **Notes:** One-time cleanup applied to the already-accumulated registry: deduped 1199 -> 806 rows, keeping the latest `processed_at_utc` per `join_key`. Backup preserved.

## Excursions / Scope Creep Discovered
- Discovered and had to resolve a session-ID collision and a duplicate/hollow-looking checkpoint log from other agent sessions before this session's own checkpoint could be written cleanly. This required directly verifying three other agents' claims against real on-disk artifacts rather than trusting the logs at face value -- all three turned out to be legitimate, but the "Files Modified only lists agents_history files" heuristic alone was not sufficient to tell that without direct verification.
- The recovery script for the crashed chunk (BUG-003) initially had its own join-key bug (used the manifest-row's own truncated `inspection_time` field instead of the case_id-derived one), which had to be caught and fixed mid-recovery before it correctly restored all 400 image paths.

## Open Threads
- [ ] THREAD-028 (still open) -- decide whether the v9 prompt config should become `probe_generic_description.py`'s hardcoded default.
- [ ] THREAD-029 (still open) -- decide whether to continue chunked/incremental VLM submission or move to Step 3's filterable HTML feedback portal.
- [ ] THREAD-030 (still open, but substantially de-risked) -- the handoff doc now has a full status section reflecting the registry-preserving artifact and the real 806-row state; the remaining task is a final documentation pass to fully retire any references to the rejected 10,895-row variant.
- [ ] THREAD-031 (new) -- decide whether `consolidate_generic_description_registry.py`'s 4 filtered subset reports (circle, `defect_count_gt1`, `truth_alignment_state=mismatched`, `current_reclass != SMALL_PARTICLE`) should be folded into the separately-planned Step 3 portal, or kept as a lightweight recurring script.

## Key Decisions Made
- Verified rather than assumed: when three other agents' checkpoint logs looked structurally suspicious (hollow `Files Modified`, a literal duplicate, a session-ID collision), chose to directly confirm or refute their factual claims against real on-disk artifacts before writing a final reconciled log, rather than either blindly trusting them or discarding them.
- Kept the legitimate duplicate-named file (`_002_generic-description-registry-bootstrap-and-tranche-fix.md`) and deleted only the confirmed-redundant one (`_002_alloy-generic-description-chunked-submission-follow-through-checkpoint.md`, identical to `_003`).
- Recovered the crashed chunk from existing JSONL data rather than re-running the VLM, to avoid wasting API spend on already-obtained results.
- Applied a one-time registry dedupe plus a source-level fix, rather than just one or the other, since the source-level fix alone wouldn't clean up the already-corrupted 1199-row state, and a one-time cleanup alone wouldn't prevent recurrence.

## Recommended Re-Entry
**Load these files for context:**
- `images\Alloy_Class\docs\HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md`
- `images\Alloy_Class\tools\probe_generic_description.py`
- `images\Alloy_Class\tools\run_generic_description_chunked.py`
- `images\Alloy_Class\tools\consolidate_generic_description_registry.py`

**Suggested starting prompt:**
> "Read `docs/HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md` in full, focusing on the 2026-09-08 status update and this session's bug-fix summary. The chunked submission pipeline is now correctly deduplicating (806 clean registry entries as of this checkpoint), and `consolidate_generic_description_registry.py` has been verified as a real, working, registry-preserving consolidation + enrichment + filtered-reporting flow. Decide the next branch: THREAD-029 (more chunked submission vs. Step 3 portal), THREAD-030 (final handoff-doc cleanup), or THREAD-031 (fold the existing filtered reports into Step 3 or keep them separate)."

## Notes for Future Agent
- The processed registry's `join_key` must always be derived from `case_id` (full-precision timestamp), never from the manifest's separate `inspection_time` column (truncated to the minute) -- this exact mismatch caused real, silent duplicate VLM submissions once already. Any new code that computes join keys against `C:\RAW_IMAGES\manifest.csv` should be checked against this gotcha.
- Don't trust a checkpoint log's claims purely from its prose, especially when its `Files Modified` section only lists `agents_history\` files -- but also don't assume that pattern always means hollow/fabricated, as it did not in this case for three legitimate logs. Verify against real on-disk artifacts when in doubt (paths, row counts, and file existence are cheap and definitive to check).
- `consolidate_generic_description_registry.py` and its 4 filtered subset reports are real and working, but were built and validated by a different agent session than this one -- this session only verified them externally (row counts, file existence), not by reading its full implementation line-by-line.
- I did not find a distinct on-disk production-enrichment rerun artifact in this workspace scan, so I am not claiming one here; the checkpoint only records the verified registry/handoff state and the existing surf-scan summary artifact.
