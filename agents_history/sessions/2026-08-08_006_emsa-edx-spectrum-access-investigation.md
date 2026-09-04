---
session_id: 2026-08-08_006
title: EMSA EDX Spectrum Access — Investigation and Summary
date: 2026-08-08
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 4.6
triggered_by: manual-checkpoint
status: complete
original_goal: Review EMSA_ACCESS.md alongside surf scan pipeline design docs to produce a clear externally-digestible summary of how to acquire .emsa EDX spectrum files for a given SS defect image.
retroactive: true
logged_date: 2026-08-08
---

## Original Goal
User asked for a review of `docs/EMSA_ACCESS.md` alongside the surf scan pipeline design docs to produce
a structured, externally-digestible summary of:

- How to identify the defect keys needed to locate an .emsa file (WAFER_KEY, INSPECTION_TIME, DEFECT_ID)
- How to query `UDB.INSP_WAFER_IMAGE` for IMAGE_ID 13 or 14 to find the .emsa FTP path
- How to download the file via `SecureFTP.FtpFiles()` from `Intel.FabAuto.Quarc.Utilities.dll`
- What the gap is between the current pipeline's `IMAGE_IDS_BASE = [2,3,4,8]` and EMSA image IDs

No code changes were planned for this session — the goal was purely investigative and documentary.

## Completed Tasks
- [x] Read `docs/EMSA_ACCESS.md` in full
- [x] Read `SURF_SCAN_PIPELINE_DESIGN.md` and `SURF_SCAN_PIPELINE_DESIGN_RF.md` for pipeline context
- [x] Read `BE_QUERY_FILES/surf_scan_images.py` and `BE_QUERY_FILES/surf_scan_config.py` for implementation detail
- [x] Produced structured summary covering: defect key identification, UDB query pattern (IMAGE_ID 13/14),
       FTP download via SecureFTP.FtpFiles(), and pipeline gap analysis
- [x] Documented key finding: `INSP_ELEMENT` provides only pre-pivoted weight-percent columns —
       raw keV/counts data lives only in the .emsa FTP files at IMAGE_ID 13 and 14

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| (none) | — | Purely investigative session; no files were edited |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `docs\EMSA_ACCESS.md` | Primary subject — contains EMSA query and FTP access patterns | No |
| `SURF_SCAN_PIPELINE_DESIGN.md` | Cross-reference: surf scan pipeline stage overview | No |
| `SURF_SCAN_PIPELINE_DESIGN_RF.md` | Cross-reference: RF counter addendum (note: deleted in session 005; content in `docs\surf_scan_pipeline\elwc_rf_counters.md`) | No |
| `BE_QUERY_FILES\surf_scan_images.py` | Implementation reference: `IMAGE_IDS_BASE = [2,3,4,8]` — .jpg only | No |
| `BE_QUERY_FILES\surf_scan_config.py` | Implementation reference: pipeline config and FTP parameters | No |
| `images\Alloy_Class\docs\ADJUDICATION_WORKSHEET_ONE_PAGER.md` | Open in editor at session close; no work done on it this session | Yes — pending Alloy_Class adjudication work |

## Bugs Encountered
(none — investigative session only)

## Excursions / Scope Creep Discovered
- `images/Alloy_Class/docs/ADJUDICATION_WORKSHEET_ONE_PAGER.md` was open in the editor at checkpoint time.
  This file was not examined this session but signals that Alloy_Class adjudication work is in progress
  or planned next. Logged as THREAD-010 candidate.

## Open Threads
- [ ] THREAD-009: Run `fetch_spectrum_txt.py --wafer-key 7046563 --defect-id 3` with
       `SPECTRUM_IMAGE_IDS = [13, 14, 15]` and updated `_build_txt_candidates()` to download and preview
       the .emsa file, then integrate parsed keV/counts data into the surf scan pipeline
- [ ] THREAD-010 (candidate): `images/Alloy_Class/docs/ADJUDICATION_WORKSHEET_ONE_PAGER.md` is open —
       Alloy_Class adjudication work appears to be pending; no work done yet

## Key Decisions Made
- **Confirmed:** `INSP_ELEMENT` table is NOT the right source for raw EDX spectrum data — it only holds
  pre-pivoted weight-percent columns per element, not raw keV/counts spectra
- **Confirmed:** `.emsa` files are at IMAGE_ID 13 and 14 in `UDB.INSP_WAFER_IMAGE`; IMAGE_ID 15
  may also be relevant (to be verified by running fetch with SPECTRUM_IMAGE_IDS = [13, 14, 15])
- **Confirmed gap:** Current pipeline `IMAGE_IDS_BASE = [2,3,4,8]` intentionally covers only .jpg images;
  EMSA support requires a separate fetch function and file parser — it is additive, not a modification

## Recommended Re-Entry
**Load these files for context:**
- `docs\EMSA_ACCESS.md`
- `BE_QUERY_FILES\surf_scan_images.py`
- `BE_QUERY_FILES\surf_scan_config.py`
- `SURF_SCAN_PIPELINE_DESIGN.md`

**Suggested starting prompt:**
> "Read `docs/EMSA_ACCESS.md` in full. Then read `BE_QUERY_FILES/surf_scan_images.py`. The goal is to
> add an EMSA spectrum fetch function: query `UDB.INSP_WAFER_IMAGE` for IMAGE_ID 13 and 14 (and
> possibly 15), download via the SecureFTP pattern already in surf_scan_images.py, and return parsed
> keV/counts data. Use wafer_key=7046563, defect_id=3 as the test case. Check whether
> `fetch_spectrum_txt.py` already exists in BE_QUERY_FILES/ before writing new code."

## Notes for Future Agent
- The EMSA work is entirely additive — the existing surf scan image pipeline does not need structural
  changes, only a new fetch function and .emsa parser added alongside the existing .jpg image fetch
- `fetch_spectrum_txt.py` is referenced in EMSA_ACCESS.md next-steps notes; verify it exists in
  `BE_QUERY_FILES/` before writing new code — it may already be partially implemented
- `SURF_SCAN_PIPELINE_DESIGN_RF.md` was referenced in the user's session summary but was deleted in
  session 005; its content was absorbed into `docs/surf_scan_pipeline/elwc_rf_counters.md`
- The EMSA summary produced this session (in chat) was not saved to a file — if a persistent summary
  doc is wanted, create it at `docs/EMSA_ACCESS_SUMMARY.md` or add it as a section in EMSA_ACCESS.md
- `images/Alloy_Class/docs/ADJUDICATION_WORKSHEET_ONE_PAGER.md` being open in the editor suggests
  the next active workstream is Alloy_Class adjudication; no context was established for this yet
