---
session_id: 2026-09-09_002
title: Generic Description Registry Bootstrap and Tranche Fix
date: 2026-09-09
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: GPT-5.4 mini
triggered_by: manual-checkpoint
status: partial
original_goal: Make the generic-description chunked orchestrator preserve seed files in a dedicated registry folder, enforce first-run exclusion of already-processed pairs, and keep per-run HTML separate from accumulating JSONL/CSV outputs.
---

## Original Goal
Consolidate the generic-description tranche workflow so the accumulating state lives in a dedicated registry folder instead of cluttering `C:\RAW_IMAGES`, while preserving the seed tranche, keeping HTML per-run, and making the first tranche avoid previously processed pairs.

## Completed Tasks
- [x] Added a chunked generic-description orchestrator at `images\Alloy_Class\tools\run_generic_description_chunked.py`.
- [x] Moved accumulating tranche artifacts into a dedicated registry workspace rooted at `C:\RAW_IMAGES\generic_description_registry`.
- [x] Added seed-copy/bootstrap behavior so the original seed JSONL and manifest are copied into the registry workspace before the first chunk runs.
- [x] Added a preflight check (`--preflight-check` / `--pfc`) to fail fast if the first selected chunk overlaps already-processed seed keys.
- [x] Kept per-run HTML generation separate from the cumulative tranche JSONL/CSV outputs.
- [x] Verified the new orchestrator compiles cleanly after each major edit.
- [x] Investigated duplicate tranche behavior and confirmed the earlier overlap was due to selection/registry-state issues rather than the HTML output path.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\tools\run_generic_description_chunked.py` | Created / Modified | Added registry-workspace orchestration, seed copying, manifest snapshotting, cumulative tranche outputs, and preflight overlap checks. |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\tools\probe_generic_description.py` | Canonical probe entrypoint whose local-cache exclusion logic is driven by the registry CSV. | No |
| `images\Alloy_Class\tools\build_beep_labeling_tranche.py` | Reference pattern for newest-first tranche selection and exclusion of already-processed cases. | No |
| `images\Alloy_Class\docs\HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md` | Source handoff for the chunked/incremental VLM submission branch. | No |
| `C:\RAW_IMAGES\manifest.csv` | Source manifest used by the orchestrator; now snapshot-copied into the registry workspace. | No |
| `C:\RAW_IMAGES\generic_description_generic_description_v9_20260907T043608Z.jsonl` | Seed JSONL used to bootstrap the registry before the first tranche. | No |
| `C:\RAW_IMAGES\generic_description_generic_description_v9_20260907T043608Z_manifest.csv` | Seed manifest copied into the registry workspace as bootstrap provenance. | No |
| `C:\RAW_IMAGES\generic_description_registry\` | Dedicated accumulating output folder referenced by the orchestrator and seed-copy bootstrap. | Yes |

## Bugs Encountered
### BUG-001: First tranche overlapped already-seeded keys
- **Status:** Resolved in part / still under validation
- **File(s):** `images\Alloy_Class\tools\run_generic_description_chunked.py`
- **Root Cause:** The first tranche selection was not isolated enough from the already-seeded key set when the workspace still lived directly under `C:\RAW_IMAGES`; the chunked selection ended up re-serving many original pairs.
- **Fix Applied:** Moved the accumulating state into a dedicated registry workspace, copied the seed artifacts into that workspace, and added a `--pfc` preflight guard to abort on overlap.
- **Notes:** The earlier 400-pair run still showed heavy duplication; the current wrapper changes are intended to prevent recurrence, but the new bootstrap path still needs a fresh validation run.

### BUG-002: Registry folder sprawl at `C:\RAW_IMAGES`
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\tools\run_generic_description_chunked.py`
- **Root Cause:** Accumulating tranche files, bootstrap artifacts, and registry state were being written directly at the root of `C:\RAW_IMAGES`.
- **Fix Applied:** Introduced `C:\RAW_IMAGES\generic_description_registry` as the registry workspace.
- **Notes:** The image source remains `C:\RAW_IMAGES\images`; only the stateful tranche outputs moved.

## Excursions / Scope Creep Discovered
- The first pass at the chunked orchestrator surfaced a real overlap/duplication problem, which was worth tracing before continuing the registry-folder cleanup.
- The root `C:\RAW_IMAGES` directory contains a large number of older generic-description artifacts; the dedicated registry folder is the right containment boundary for the accumulating workflow.

## Open Threads
- [ ] THREAD-029 — Decide whether to continue with chunked/incremental VLM submission or move to Step 3's filterable HTML feedback portal.
- [ ] Validate the registry-workspace bootstrap end-to-end with a fresh run using the copied seed files and `--pfc` enabled.

## Key Decisions Made
- Keep the image source under `C:\RAW_IMAGES\images`, but move all accumulating tranche/registry artifacts into `C:\RAW_IMAGES\generic_description_registry`.
- Treat the seed tranche as bootstrap provenance by copying the seed JSONL and manifest into the registry workspace before the first run.
- Fail fast on the first chunk if its keys overlap the seeded registry set.
- Keep HTML per-run rather than accumulating it in the registry workspace.

## Recommended Re-Entry
**Load these files for context:**
- `images\Alloy_Class\tools\run_generic_description_chunked.py`
- `images\Alloy_Class\tools\probe_generic_description.py`
- `images\Alloy_Class\tools\build_beep_labeling_tranche.py`
- `agents_history\index.md`
- `agents_history\open_threads.md`

**Suggested starting prompt:**
> "Validate the registry-workspace chunked generic-description orchestrator after the seed-copy/bootstrap change. Confirm the first tranche avoids already-processed pairs and update the handoff if the registry folder contract needs any follow-up tightening."

## Notes for Future Agent
The critical behavior to preserve is the separation of concerns: `C:\RAW_IMAGES\images` remains the source image location, while `C:\RAW_IMAGES\generic_description_registry` holds the accumulating JSONL/CSV, bootstrap seed copies, and registry metadata. The preflight guard should stay enabled for the first tranche so overlap is detected before another large duplicate run can happen.