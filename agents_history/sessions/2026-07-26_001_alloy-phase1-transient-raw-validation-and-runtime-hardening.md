---
session_id: 2026-07-26_001
title: Alloy Phase 1 Transient Raw Validation and Runtime Hardening
date: 2026-07-26
time_start: 20:00
time_end: 21:30
agent: GitHub Copilot
model: GPT-5.4
triggered_by: manual-checkpoint
status: complete
original_goal: Validate a transient raw-image workflow for Alloy Phase 1 classification while preserving burned-image linkage, then update runbook and promotion-status docs to reflect the validated runtime path.
retroactive: true
logged_date: 2026-08-09
---

## Original Goal
Phase 1 classification had reached a point where pair-safe capped runs were working, but the remaining runtime question was whether raw images could be downloaded just-in-time for inference and deleted immediately afterward without creating a persistent raw library. The session also needed to close the loop on ScriptHost-parity runtime validation and leave behind operational documentation that reflected the validated path.

## Completed Tasks
- [x] Implemented transient raw-image staging in `images\Alloy_Class\pipelines\classify_phase1_batch.py` so inference can use downloaded raw files while retaining burned-image provenance.
- [x] Added/confirmed pair-safe bounded execution behavior for first-pass BF/DF validation runs.
- [x] Built wheelhouse parity support tooling and verified ScriptHost interpreter bootstrap/import behavior for the approved offline baseline.
- [x] Generated a fresh bounded verification run proving raw download, inference, and temp-file deletion behavior end to end.
- [x] Hardened JSON settings loading to accept UTF-8 BOM content encountered in PowerShell-generated config files.
- [x] Updated Phase 1 operational docs and checklist to reflect transient raw validation status and the current runtime state.
- [x] Removed the one-off temporary verification settings file after validation.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\pipelines\classify_phase1_batch.py` | Modified | Added transient raw download/use/delete flow, raw provenance fields, summary counters, and BOM-safe JSON config loading. |
| `images\Alloy_Class\config\phase1_settings.json` | Modified | Added/updated pair-safe and transient raw runtime defaults used by the runner. |
| `images\Alloy_Class\docs\PHASE1_RUNBOOK.md` | Modified | Added bounded raw-mode run guidance and ScriptHost parity/bootstrap instructions. |
| `images\Alloy_Class\docs\WHEELHOUSE_BLOCKER_20260726.md` | Modified | Recorded parity unblock status and post-unblock transient raw validation evidence. |
| `images\Alloy_Class\docs\PHASE1_ACCEPTANCE_CHECKLIST.md` | Created / Modified | Added acceptance gates and updated current status after raw-mode validation. |
| `images\Alloy_Class\docs\RAW_IMAGE_REDOWNLOAD_PLAN.md` | Created | Documented strategy for requesting raw re-downloads without keeping a permanent raw image library. |
| `images\Alloy_Class\tools\wheelhouse_audit.py` | Created | Added offline wheelhouse coverage audit utility for lockfile parity checks. |
| `images\Alloy_Class\tools\build_raw_redownload_manifest.py` | Created | Added helper to build request manifests for raw-image re-download workflows. |
| `images\Alloy_Class\config\phase1_settings_raw_transient_verify.json` | Created / Deleted | Temporary fresh-output verification config used to force a non-skipped bounded raw-mode test. |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py` | Referenced for SecureFTP/raw retrieval pattern and existing image-download behavior. | No |
| `images\Alloy_Class\outputs\phase1_raw_transient_verify\phase1_results.jsonl` | Validation evidence confirming `processed=6`, `raw_used=6`, and `raw_deleted=6`. | No |
| `Shared_Docs\Alloy_Apps\_shared_runtime\constraints\requirements.lock.py311.txt` | Referenced during wheelhouse parity and bootstrap validation. | No |

## Bugs Encountered
### BUG-001: UNC wheelhouse parity gaps blocked ScriptHost bootstrap
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\tools\wheelhouse_audit.py`, `images\Alloy_Class\docs\WHEELHOUSE_BLOCKER_20260726.md`, `Shared_Docs\Alloy_Apps\_shared_runtime\constraints\requirements.lock.py311.txt`
- **Root Cause:** Required offline wheels for the pinned baseline were missing or mismatched, so `alloy` imports could not be trusted in the production-aligned interpreter.
- **Fix Applied:** Added a wheelhouse audit utility, aligned the offline package baseline, and re-verified bootstrap plus `from alloy.core.llm import image` import success.
- **Notes:** This session treated wheelhouse parity as a runtime-validation gate, not a stop-work condition for prompt/schema development.

### BUG-002: First transient raw verification run skipped all selected rows
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\config\phase1_settings_raw_transient_verify.json`, `images\Alloy_Class\outputs\phase1_raw_transient_verify\phase1_results.jsonl`
- **Root Cause:** Existing per-image outputs caused the bounded run to skip all selected images, so the raw-image path was never exercised.
- **Fix Applied:** Created a temporary settings file pointing to a fresh output folder and reran the bounded cohort.
- **Notes:** Future raw-mode verification should always use a fresh run output path or an explicit reprocess mechanism.

### BUG-003: PowerShell-generated temp settings file contained a UTF-8 BOM
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\pipelines\classify_phase1_batch.py`, `images\Alloy_Class\config\phase1_settings_raw_transient_verify.json`
- **Root Cause:** The runner loaded JSON with plain `utf-8`, which raised `JSONDecodeError` when the temporary file was written with a BOM.
- **Fix Applied:** Regenerated the temporary file without BOM and hardened JSON settings loading to `utf-8-sig`.
- **Notes:** This prevents the same failure class for future PowerShell-edited config files.

## Excursions / Scope Creep Discovered
- Formalized acceptance-gate tracking in `PHASE1_ACCEPTANCE_CHECKLIST.md` so runtime proof points would have a clear go/no-go home.
- Added a raw-image re-download planning document and helper script because raw-vs-burned provenance turned out to be an operational concern, not just a runner concern.

## Open Threads
- [ ] Scale beyond the 3-pair validation cohort and review classification quality thresholds on a larger acceptance batch.
- [ ] Consider adding an explicit force-reprocess flag if repeated bounded raw-mode verification becomes common.

## Key Decisions Made
- Use transient raw staging rather than maintaining a persistent raw-image library.
- Preserve the burned image as the stable artifact/reference path even when inference uses a raw temporary file.
- Keep pair-safe BF/DF gating and capped first-pass execution as the default operating mode for validation.
- Treat ScriptHost wheelhouse parity as a required production-style validation gate, but not as a reason to stop broader Phase 1 experimentation.

## Recommended Re-Entry
**Load these files for context:**
- `images\Alloy_Class\pipelines\classify_phase1_batch.py`
- `images\Alloy_Class\docs\PHASE1_RUNBOOK.md`
- `images\Alloy_Class\docs\PHASE1_ACCEPTANCE_CHECKLIST.md`
- `images\Alloy_Class\docs\WHEELHOUSE_BLOCKER_20260726.md`

**Suggested starting prompt:**
> "Read the Phase 1 runner and docs, then scale the validated pair-safe transient raw workflow beyond the 3-pair cohort and assess whether classification quality/review-rate metrics are strong enough to advance the Phase 1 acceptance gates."

## Notes for Future Agent
The important runtime proof from this session is not just that Alloy executed, but that raw staging stayed ephemeral: the bounded verification run completed with `processed=6`, `failed=0`, `skipped=0`, `raw_used=6`, and `raw_deleted=6`. The burned-image path remains the durable linkage field, while raw provenance is captured in output rows for traceability.