---
session_id: 2026-08-30_001
title: BEEP-vs-SMALL_PARTICLE Rapid Labeling Tool Build + Port-Mismatch Incident
date: 2026-08-30
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: unknown (not recorded live; logged retroactively from summary)
triggered_by: manual-checkpoint
status: complete
original_goal: Build a rapid manual BEEP-vs-SMALL_PARTICLE labeling tool the user can use to personally disposition the full historical SMALL_PARTICLE population, as a track decoupled from the parallel VLM probe/scoring pipeline work.
retroactive: true
logged_date: 2026-09-02
---

## Original Goal
Reviewed `images\Alloy_Class\docs\TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md` (an
existing inventory doc, not authored this session) and planned a new "rapid BEEP-vs-SMALL_PARTICLE
labeling tool" so the user could personally disposition the full historical SMALL_PARTICLE
population. This is explicitly separate from the VLM probe/scoring pipeline work also happening
in parallel this session under `generic_description_v*`/probe scripts -- that VLM work is a
distinct thread and is NOT covered by this checkpoint.

This session's work spanned build/plan/verify on 2026-08-30, continuing into real usage
(tranche_0001, tranche_0002, and the port-mismatch incident) on 2026-08-31, logged here as one
continuous session. Tranches 0003-0009 and a misclassified-tranches review artifact were built
in a separate, later chat session and are explicitly OUT OF SCOPE for this checkpoint -- they
will get their own checkpoint logged independently.

## Completed Tasks
- [x] Reviewed `images\Alloy_Class\docs\TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md` to inform the plan
- [x] Wrote full plan to session memory (`/memories/session/plan.md`) -- 3-piece tool design reusing existing Alloy_Class reporting/feedback-portal patterns and the BE_QUERY_FILES image pipeline
- [x] Corrected tranche ordering from an initial oldest-first draft to newest-INSPECTION_TIME-first per explicit user instruction
- [x] Confirmed via source read of `DEFECT_COORDINATES_QUERY.py`'s `_prune_old_images()` that `DEFECT_COORDINATES_EXTENDED_IMAGES.csv` is a rolling 60-day window (`IMAGE_RETENTION_DAYS=60`), NOT full history; switched primary population source to `DEFECT_COORDINATES_EXTENDED.csv` (coordinates-only, accumulated forever, verified rows back to 2025-01-23, has `LAYER` column)
- [x] Designed ground-truth CSV schema (`pair_key, wafer_key, inspection_time, defect_id, layer, label, reviewer, submitted_at_utc, tranche_id`); verified `(wafer_key, inspection_time, defect_id)` matches production's `_accumulate_coordinates()` dedup key exactly
- [x] Built `images\Alloy_Class\tools\build_beep_labeling_tranche.py` -- selects next ~100 unlabeled SMALL_PARTICLE pairs from `DEFECT_COORDINATES_EXTENDED.csv`, newest-first, excluding anything already in ground truth or any prior `tranche_*_cases.csv`
- [x] Built `images\Alloy_Class\reporting\build_beep_labeling_report.py` -- HTML report, one row per case, bright+dark images, two-option radio (SMALL_PARTICLE/BEEP), tabindex=0 rows only so Tab moves case-to-case, ArrowLeft=SMALL_PARTICLE/ArrowRight=BEEP with auto-advance, localStorage-cached selections, single "Submit All" batch button
- [x] Built `images\Alloy_Class\reporting\beep_labeling_portal\` -- new Flask backend on port 8001, routes `POST /submit_labels` (batch) + `GET /labels`, appends to `outputs\beep_evidence\beep_evidence_ground_truth.csv`; launcher scripts `run_portal.ps1`/`run_portal.cmd` copied/adapted from `feedback_portal`'s pattern
- [x] Fixed BUG-A: path-resolution bug in `build_beep_labeling_tranche.py` (`BE_ROOT` computed one directory level too shallow)
- [x] Fixed BUG-B: data-pair-key HTML attribute double-JSON-encoding bug in `build_beep_labeling_report.py`
- [x] Built, reported, and round-tripped `tranche_0001` (100 real cases, newest-first from 2026-08-29) through the backend with a smoke test (2 rows), then cleaned up before real use
- [x] Verified exclusion logic by rebuilding a tranche after labeling: previously-served/labeled `pair_key`s correctly excluded from the next batch
- [x] Diagnosed and fixed BUG-C (real incident): user double-clicked the wrong portal launcher (port 8000, old `feedback_portal`) instead of the new `beep_labeling_portal` (port 8001); reassured user labels were safe (localStorage only clears on a successful submit); shipped a live backend-status banner in `build_beep_labeling_report.py` that fetches `API_BASE + "/"` on page load and shows a named-mismatch warning instead of failing silently at submit time
- [x] User completed tranche_0001 (100 cases, ~8 min, 74 SMALL_PARTICLE / 26 BEEP) and tranche_0002 (100 cases, confirmed submitted; ground truth CSV verified at 200 total rows)
- [x] Proposed (not yet built) an optional `--since-days N` cutoff flag for `build_beep_labeling_tranche.py` in response to the user's throughput-math concern (~6,500 total population, ~8-9 hours to exhaust full history)
- [x] Provided the user a repeatable 2-command tranche-to-tranche cycle
- [x] Wrote repo memory `/memories/repo/beep_evidence_labeling_tool.md` (new, durable summary going forward; session-scoped `/memories/session/plan.md` will be cleared after the conversation ends)

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\tools\build_beep_labeling_tranche.py` | Created | Selects next ~100 unlabeled SMALL_PARTICLE pairs, newest-`INSPECTION_TIME`-first, from `DEFECT_COORDINATES_EXTENDED.csv`; excludes prior ground-truth/tranche rows; has an untested `--allow-redownload` flag (see THREAD-027) |
| `images\Alloy_Class\reporting\build_beep_labeling_report.py` | Created | HTML tranche report: bright+dark images, 2-option radio, keyboard nav (Tab=case, Left=SMALL_PARTICLE, Right=BEEP, auto-advance), localStorage cache, batched "Submit All"; later patched with a live backend-status banner (BUG-C fix) |
| `images\Alloy_Class\reporting\beep_labeling_portal\` (backend, `run_portal.ps1`, `run_portal.cmd`) | Created | New Flask backend, port 8001, sibling of `feedback_portal` (port 8000); `POST /submit_labels` (batch) + `GET /labels`; appends to `outputs\beep_evidence\beep_evidence_ground_truth.csv` |
| `outputs\beep_evidence\beep_evidence_ground_truth.csv` | Created | Ground-truth CSV; schema `pair_key, wafer_key, inspection_time, defect_id, layer, label, reviewer, submitted_at_utc, tranche_id`; 200 rows after tranche_0001 + tranche_0002 submission |
| `images\Alloy_Class\outputs\beep_evidence\tranche_0001_cases.csv` / `tranche_0001_report.html` | Created | First real tranche (100 cases, 2026-08-29 newest-first slice); 74 SMALL_PARTICLE / 26 BEEP; report HTML predates the BUG-C status-banner fix and was NOT regenerated in place (file-locked while open in browser) -- exact output subdirectory reconstructed from session summary, not independently re-verified this checkpoint |
| `images\Alloy_Class\outputs\beep_evidence\tranche_0002_cases.csv` / `tranche_0002_report.html` | Created | Second real tranche (100 cases); report HTML includes the BUG-C status-banner fix; exact output subdirectory reconstructed from session summary, not independently re-verified this checkpoint |
| `/memories/repo/beep_evidence_labeling_tool.md` | Created | Durable repo-memory summary: build summary, two-portals/ports gotcha, first-run results, deferred items |
| `/memories/session/plan.md` | Created (session-scoped) | Full build plan and decision log; session-scoped, will be cleared after the originating conversation ends -- repo memory file above is the durable pointer going forward |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\docs\TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md` | Existing inventory doc reviewed to inform the plan (not authored this session) | No |
| `outputs\defects\DEFECT_COORDINATES_EXTENDED.csv` | Confirmed full accumulated history (rows back to 2025-01-23, has `LAYER`); chosen as primary population source | No |
| `outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv` | Confirmed (via `_prune_old_images()` read) to be a rolling 60-day window, NOT full history; rejected as population source | No |
| `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py` | Source read for `_fetch_image_metadata`/`_download_images`/`_reorganize_images` (reused best-effort by `--allow-redownload`) and `_prune_old_images`/`_accumulate_coordinates` (dedup-key verification) | No |
| `images\Alloy_Class\reporting\feedback_portal\` (incl. `run_portal.cmd`, port 8000) | Older probe-review portal; pattern reused for the new `beep_labeling_portal` launcher scripts; also the launcher the user mistakenly double-clicked, causing BUG-C | No |

## Bugs Encountered
### BUG-A: `build_beep_labeling_tranche.py` path-resolution error
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\tools\build_beep_labeling_tranche.py`
- **Root Cause:** `BE_ROOT` was computed one directory level too shallow (`parents[0]` instead of `parents[1]` from the `Alloy_Class` root)
- **Fix Applied:** Corrected to `parents[1]`
- **Notes:** Found during end-to-end verification against real production data on 2026-08-30.

### BUG-B: double-JSON-encoded `pair_key` in report HTML attribute
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\reporting\build_beep_labeling_report.py`
- **Root Cause:** `pair_key` was being JSON-encoded twice before being embedded as a `data-pair-key` HTML attribute, leaving literal quote characters in the DOM attribute/localStorage key
- **Fix Applied:** Removed the redundant encoding step

### BUG-C: user launched the wrong portal backend (port 8000 vs 8001)
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\reporting\build_beep_labeling_report.py`, `images\Alloy_Class\reporting\feedback_portal\run_portal.cmd`, `images\Alloy_Class\reporting\beep_labeling_portal\run_portal.cmd`
- **Root Cause:** User double-clicked `reporting\feedback_portal\run_portal.cmd` (the older probe-review backend, port 8000) instead of `reporting\beep_labeling_portal\run_portal.cmd` (port 8001). "Submit All" failed with a silent connection error after the user had already labeled 100 cases (tranche_0001). Diagnosed from the pasted terminal log showing port 8000 and `probe_review_feedback.csv` target strings.
- **Fix Applied:** `build_beep_labeling_report.py` now emits a live backend-status banner that fetches `API_BASE + "/"` on page load and shows a red warning naming the exact mismatch (wrong report_id, or unreachable) instead of failing silently later at submit time. Fix applies starting tranche_0002 onward -- `tranche_0001_report.html` was NOT force-regenerated in place because the file was lock-protected while open in the user's browser; the lock-safe writer's `_rev2.html` fallback was generated and then deliberately deleted again to avoid orphaning the user's in-progress localStorage state under a different `file://` origin/path.
- **Notes:** User's 100 labeled selections in tranche_0001 were confirmed safe throughout -- localStorage only clears on a *successful* submit, so nothing was lost. This is a real production incident, not a hypothetical.

## Excursions / Scope Creep Discovered
- The VLM probe/scoring pipeline work (`generic_description_v*`/probe scripts) was happening in parallel this session but is a distinct, separate thread and is explicitly NOT covered by this checkpoint.
- Tranches 0003-0009 and a misclassified-tranches-review HTML artifact exist in the repo now, but were built in a separate, later chat session that has its own checkpoint to be logged independently. This checkpoint does not claim credit for or attempt to describe that work.

## Open Threads
- [ ] THREAD-027 -- `--allow-redownload` path in `build_beep_labeling_tranche.py` remains completely untested against a live DB/SecureFTP connection
- [ ] THREAD-028 -- Optional `--since-days N` cutoff flag for the tranche builder: proposed in response to the ~8-9 hour full-history throughput concern, not yet built, awaiting user decision
- [ ] THREAD-029 -- Production merge-back script (joining `beep_evidence_ground_truth.csv` onto `DEFECT_COORDINATES_EXTENDED*.csv`/production analyses): explicitly out of scope by user decision, not designed
- [ ] THREAD-030 -- Tranche file lifecycle/cleanup: no explicit "close out" step for fully-labeled tranches; acceptable for now, flagged as revisit-only-if-it-becomes-a-problem

## Key Decisions Made
- Tranche ordering corrected from an initial oldest-first draft to newest-`INSPECTION_TIME`-first per explicit user instruction, so new manifest additions surface first instead of languishing behind a year-and-a-half backlog.
- Primary population source switched from `DEFECT_COORDINATES_EXTENDED_IMAGES.csv` (confirmed rolling 60-day window) to `DEFECT_COORDINATES_EXTENDED.csv` (confirmed full accumulated history) after the user correctly suspected the former was not full history; confirmed via source read of `_prune_old_images()` (`IMAGE_RETENTION_DAYS=60`).
- Ground-truth CSV kept fresh and minimal (`pair_key, wafer_key, inspection_time, defect_id, layer, label, reviewer, submitted_at_utc, tranche_id`) rather than reusing a heavier existing schema; `layer` added redundantly (duplicable from the key) per explicit user request purely for easy sanity-checking.
- Keyboard mapping fixed as Left=SMALL_PARTICLE, Right=BEEP with auto-advance; submission model fixed as batched "Submit All" rather than per-selection auto-post.
- Production merge-back script explicitly deferred/declared out of scope per user decision -- not designed or attempted this session (see THREAD-029).
- Did NOT force-regenerate the user's already-open `tranche_0001_report.html` in place after the BUG-C fix, and did NOT keep the lock-safe `_rev2.html` fallback -- deleted it again to avoid orphaning the user's in-progress localStorage state under a different `file://` origin/path. The BUG-C banner fix intentionally applies starting tranche_0002 onward only; a future agent should not "fix" tranche_0001's report to add the banner without understanding this was a deliberate choice.
- `--allow-redownload` was left deliberately untested rather than blocking the build on a live DB connection, since newest-first cases already had local images and the flag was not needed for tranche_0001/0002.

## Recommended Re-Entry
**Load these files for context:**
- `/memories/repo/beep_evidence_labeling_tool.md`
- `images\Alloy_Class\tools\build_beep_labeling_tranche.py`
- `images\Alloy_Class\reporting\build_beep_labeling_report.py`
- `images\Alloy_Class\reporting\beep_labeling_portal\`
- `outputs\beep_evidence\beep_evidence_ground_truth.csv`

**Suggested starting prompt:**
> "Read `/memories/repo/beep_evidence_labeling_tool.md` for the BEEP-vs-SMALL_PARTICLE labeling tool built on 2026-08-30/31. Decide on THREAD-028 (`--since-days N` cutoff flag) before generating further tranches, and confirm whether THREAD-027 (`--allow-redownload`) needs testing yet."

## Notes for Future Agent
- Two separate Flask portals now exist side by side: `reporting\feedback_portal\` (port 8000, older probe-review tool) and `reporting\beep_labeling_portal\` (port 8001, this session's tool). They have near-identical launcher script names (`run_portal.cmd`/`run_portal.ps1`) in sibling directories -- this is the exact confusion that caused BUG-C. Do not consolidate or rename without confirming with the user first, since both are actively in use.
- `tranche_0001_report.html` intentionally does NOT have the BUG-C status banner that `tranche_0002_report.html` and later reports have. This is a known, accepted inconsistency (file was lock-protected in-browser at fix time) -- do not treat it as a bug to silently patch.
- This checkpoint is retroactive and reconstructed from a user-supplied summary, not from live chat transcript review. Exact output subdirectory paths for the tranche CSV/HTML pairs were inferred from context (`outputs\beep_evidence\` alongside the ground-truth CSV) and were not independently re-verified against the live filesystem during this logging pass -- a future agent should confirm the real paths before relying on them.
- Tranches 0003-0009 and a misclassified-tranches-review HTML artifact exist in the repo from a separate, later session and are NOT described here -- look for that session's own checkpoint rather than assuming this log covers them.
