---
session_id: 2026-08-11_003
title: Alloy Prompt Iteration Registry Checkpoint
date: 2026-08-11
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: GPT-5.4 mini
triggered_by: manual-checkpoint
status: complete
original_goal: Record the lightweight Alloy VLM prompt-iteration registry work and capture the current tracking convention.
---

## Original Goal
Document the registry-oriented Alloy VLM checkpoint after the lightweight prompt iteration tracker was added, with the intent to preserve the minimum metadata needed to trace finalized run instances, campaign slices, scored outputs, and summary metrics.

## Completed Tasks
- [x] Recorded that `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md` defines the run-centric registry schema
- [x] Recorded that `images\Alloy_Class\artifacts\prompt_iteration_registry.csv` is the machine-editable tracker
- [x] Recorded that the registry separates input slices, scored-row CSVs, summary JSONs, and execution flags
- [x] Recorded the finalized benchmark runs `benchmark_nbc52_tier1_v3_stageA_BF_only_stageB_multi` and `benchmark_nbc52_tier1_v3_stageA_BF_only_stageB_multi_v2`
- [x] Recorded the scored outputs and summary metrics for the two benchmark runs

## Files Modified

| File | Change Type | Notes |
|------|-------------|-------|
| `agents_history\sessions\2026-08-11_003_alloy-prompt-iteration-registry-checkpoint.md` | Created | Formal checkpoint log for the Alloy prompt-iteration registry work |
| `agents_history\index.md` | Modified | Added the session row for the registry work |
| `agents_history\file_map.md` | Modified | Added the checkpoint log and the registry files referenced by the checkpoint |
| `agents_history\open_threads.md` | Modified | Added the registry cleanup follow-up thread |

## Files Affected (referenced but not modified)

| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md` | Registry spec and rationale for the run-centric tracking format | No |
| `images\Alloy_Class\artifacts\prompt_iteration_registry.csv` | Machine-editable tracker created for the registry | No |
| `images\Alloy_Class\artifacts\benchmark_pairs_full145.csv` | Existing campaign CSV linked by the registry | No |
| `images\Alloy_Class\artifacts\benchmark_pairs_pilot12.csv` | Existing campaign CSV linked by the registry | No |
| `images\Alloy_Class\artifacts\benchmark_pairs_nbc_focus52.csv` | Existing campaign CSV linked by the registry | No |
| `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv` | Existing campaign CSV linked by the registry | No |
| `images\Alloy_Class\artifacts\phase1_quality_review_summary.json` | Existing review summary JSON linked by the registry | No |
| `images\Alloy_Class\artifacts\benchmark_candidates_14day_summary.json` | Existing review summary JSON linked by the registry | No |

## Bugs Encountered

### BUG-001: No implementation bug in this checkpoint
- **Status:** Resolved
- **File(s):** None
- **Root Cause:** Not applicable for this log entry.
- **Fix Applied:** Not applicable.
- **Notes:** This checkpoint records a documentation and tracking update, not a runtime failure.

## Excursions / Scope Creep Discovered

- No extra implementation work was pulled in beyond the registry cleanup and alignment to finalized run outputs.

## Open Threads

- [ ] **THREAD-010** — Normalize run labels and confirm whether any older registry entries should be migrated to the new run-centric schema

## Key Decisions Made

- Keep the prompt iteration registry shallow but run-centric.
- Reference existing campaign CSVs, scored-row outputs, summary JSONs, and run manifests directly.
- Preserve `stage_a_brightfield_only` and `stage_b_multi_image` so Stage A / Stage B behavior stays explicit.

## Recommended Re-Entry

**Load these files for context:**
- `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md`
- `images\Alloy_Class\artifacts\prompt_iteration_registry.csv`
- `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv`
- `images\Alloy_Class\artifacts\benchmark_candidates_14day_summary.json`

**Suggested starting prompt:**
> "Continue from the Alloy prompt-iteration registry checkpoint, verify the run-centric registry entries, and decide whether any older shallow rows should be migrated or left as historical references."

## Notes for Future Agent

- The registry is deliberately lightweight but now tracks finalized run instances directly.
- If older shallow rows remain useful as historical context, keep them only if they do not conflict with the run-centric rows.