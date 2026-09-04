---
session_id: 2026-08-11_002
title: Alloy VLM Stage A/B BF-Only Checkpoint
date: 2026-08-11
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: GPT-5.4 mini
triggered_by: manual-checkpoint
status: complete
original_goal: Record the completed BF-only Stage A / BF+DF Stage B benchmark work and capture the successful scoring comparisons.
---

## Original Goal
Document the latest Alloy VLM benchmark checkpoint after the BF-only Stage A / BF+DF Stage B mode was implemented, the benchmark run completed successfully, and both the frozen-score comparison and earlier comparison run were scored.

## Completed Tasks
- [x] Recorded the BF-only Stage A / BF+DF Stage B mode change in the session history
- [x] Recorded that `run_stage_ab_prompt_tests.py` now supports the BF-only / BF+DF benchmark path
- [x] Recorded that `run_benchmark_vlm.py` forwards the new mode through the benchmark runner
- [x] Recorded successful completion of `benchmark_nbc52_tier1_v3_stageA_BF_only_stageB_multi_v2`
- [x] Recorded scoring against `benchmark_v1_frozen.csv`
- [x] Recorded that the earlier `benchmark_nbc52_tier1_v3_stageA_BF_only_stageB_multi` run was also scored for comparison

## Files Modified

| File | Change Type | Notes |
|------|-------------|-------|
| `agents_history\sessions\2026-08-11_002_alloy-vlm-stage-ab-bf-only-bfdf-scoring-checkpoint.md` | Created | Formal checkpoint log for the BF-only Stage A / BF+DF Stage B benchmark work |
| `agents_history\index.md` | Modified | Added the new session row and updated the session log summary |
| `agents_history\file_map.md` | Modified | Added the new session log and benchmark files referenced by this checkpoint |
| `agents_history\open_threads.md` | Modified | Reflected the current thread state after the checkpoint |

## Files Affected (referenced but not modified)

| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | Source of the BF-only Stage A / BF+DF Stage B mode implementation | No |
| `images\Alloy_Class\tools\run_benchmark_vlm.py` | Forwards the benchmark mode into the runner | No |
| `images\Alloy_Class\artifacts\benchmark_nbc52_tier1_v3_stageA_BF_only_stageB_multi_v2` | Successful benchmark run recorded in the checkpoint | No |
| `images\Alloy_Class\artifacts\benchmark_nbc52_tier1_v3_stageA_BF_only_stageB_multi` | Earlier comparison run that was also scored | No |
| `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv` | Frozen scoring baseline used for the comparison | No |

## Bugs Encountered

### BUG-001: None recorded in this checkpoint
- **Status:** Resolved
- **File(s):** None
- **Root Cause:** Not applicable for this log entry.
- **Fix Applied:** Not applicable.
- **Notes:** This checkpoint is a status record for completed benchmark work rather than a debugging session.

## Excursions / Scope Creep Discovered

- None

## Open Threads

- [ ] **THREAD-006** — BC check detection gap still needs prompt refinement
- [ ] **THREAD-007** — Stage A confounder language may still leak into Stage B `isl` detection
- [ ] **THREAD-008** — `sr` detection ceiling remains deferred
- [ ] **THREAD-009** — BMK_0037 relabeling question remains pending user review

## Key Decisions Made

- Keep the BF-only Stage A / BF+DF Stage B mode as the benchmark path for the corrected NBC52 run.
- Preserve the earlier benchmark run as a scored comparison point rather than overwriting it.
- Treat this session as a checkpoint-only history update, not a code-edit session.

## Recommended Re-Entry

**Load these files for context:**
- `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`
- `images\Alloy_Class\tools\run_benchmark_vlm.py`
- `images\Alloy_Class\tools\score_benchmark_run.py`
- `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv`

**Suggested starting prompt:**
> "Continue from the BF-only Stage A / BF+DF Stage B benchmark checkpoint, review the scoring outputs for the corrected NBC52 run and the earlier comparison run, and decide whether the remaining open threads need prompt changes or label review."

## Notes for Future Agent

- The checkpoint records a successful corrected benchmark run plus a scored prior run for comparison.
- No open threads were resolved by this checkpoint; the session history was updated to reflect the current state only.
