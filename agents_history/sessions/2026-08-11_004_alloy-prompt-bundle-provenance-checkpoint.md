---
session_id: 2026-08-11_004
title: Alloy Prompt Bundle Provenance Checkpoint
date: 2026-08-11
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: GPT-5.4 mini
triggered_by: manual-checkpoint
status: complete
original_goal: Implement a run-local prompt bundle for Alloy Stage A/B benchmark runs and record the provenance in the session history.
---

## Original Goal
Record the prompt-bundle provenance implementation so each finalized benchmark run writes a run-local prompt artifact containing the exact Stage A and Stage B prompt text, prompt version identifiers, execution flags, and the resolved run paths.

## Completed Tasks
- [x] Added run-local prompt bundle construction in `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`
- [x] Wrote `prompt_bundle.json` and `prompt_bundle.txt` once per run before model calls begin
- [x] Included prompt version IDs, prompt text, execution flags, and run paths in the bundle
- [x] Forwarded the run root from `images\Alloy_Class\tools\run_benchmark_vlm.py` into the stage runner
- [x] Added `prompt_bundle_path` provenance fields to the benchmark run manifest
- [x] Updated `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md` to point at the run-local provenance artifact

## Files Modified

| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | Modified | Added prompt-bundle builder/writer helpers and run-level provenance fields |
| `images\Alloy_Class\tools\run_benchmark_vlm.py` | Modified | Forwarded `--run-root-folder` and recorded prompt-bundle paths in the benchmark manifest |
| `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md` | Modified | Registry guidance now points to `prompt_bundle.json` / `prompt_bundle.txt` |
| `agents_history\sessions\2026-08-11_004_alloy-prompt-bundle-provenance-checkpoint.md` | Created | Formal checkpoint log for the prompt-bundle provenance implementation |

## Files Affected (referenced but not modified)

| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\docs\PROMPT_BUNDLE_IMPLEMENTATION_PLAN.md` | Implementation plan that drove the change | No |
| `images\Alloy_Class\artifacts\prompt_iteration_registry.csv` | Existing registry tracker referenced by the updated docs | No |
| `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv` | Existing benchmark baseline context for the run pipeline | No |

## Bugs Encountered

### BUG-001: None recorded in this checkpoint
- **Status:** Resolved
- **File(s):** None
- **Root Cause:** Not applicable for this log entry.
- **Fix Applied:** Not applicable.
- **Notes:** This checkpoint records a provenance implementation rather than a runtime bug fix.

## Excursions / Scope Creep Discovered

- None

## Open Threads

- [x] **THREAD-010** — Prompt iteration registry follow-up resolved by the prompt-bundle provenance work

## Key Decisions Made

- Keep the prompt bundle run-local and write it before the first model call so the exact prompts are captured even if the run later fails.
- Record the prompt-bundle paths in the manifest so run provenance can be reconstructed from the benchmark root without opening source config files.
- Preserve the current raw-image semantics and only document them in the bundle; do not change fail-open/fail-closed behavior in the same change.

## Recommended Re-Entry

**Load these files for context:**
- `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`
- `images\Alloy_Class\tools\run_benchmark_vlm.py`
- `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md`

**Suggested starting prompt:**
> "Continue from the Alloy prompt-bundle provenance checkpoint, verify that the run-local bundle is emitted in the benchmark output root, and decide whether the raw-image policy should remain unchanged or be tightened in a separate follow-up."

## Notes for Future Agent

- The bundle is the new single source of truth for run-level prompt provenance.
- The run manifest now points at the bundle, but the bundle itself owns the exact prompt text.