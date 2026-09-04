---
session_id: 2026-08-15_001
title: Alloy Claude Sonnet 4.6 Offset Surface Lines Recall Checkpoint
date: 2026-08-15
time_start: 23:00
time_end: 23:30
agent: GitHub Copilot
model: Claude Sonnet 4.6
triggered_by: manual-checkpoint
status: partial
original_goal: Measure vlm_ec_inset_surface_lines recall on the 15 gt_offset_surface_lines_present=yes rows using Claude Sonnet 4.6.
# retroactive: true
# logged_date: 2026-08-15
---

## Original Goal
Run a focused recall check on the offset-surface-lines-positive slice and make sure the scoring CSV carries both ground truth and VLM evidence columns.

## Completed Tasks
- [x] Created a one-row smoke test to validate Claude Sonnet 4.6 model acceptance.
- [x] Built an evidence-aware v7 smoke config that emits `evidence_check_inset_surface_lines`, `evidence_check_boundary_conformance`, and `evidence_check_sunken_residual`.
- [x] Created a 15-row benchmark slice containing only rows with `gt_offset_surface_lines_present=yes`.
- [x] Ran the 15-row Claude Sonnet 4.6 slice successfully.
- [x] Scored the run against `benchmark_v1_frozen.csv`.
- [x] Confirmed the scoring CSV populates both GT columns and VLM evidence columns on the evidence-aware config.
- [x] Measured `vlm_ec_inset_surface_lines` recall on the 15-row slice as 1/15 = 0.0667.
- [x] Cloned the optimized substrate Tier 1 prompt into a v8 config and updated the model target to Claude Sonnet 4.6.
- [x] Created a v8 sibling of the 15-image offset-surface-lines submission config and aligned its suite name to the v8 iteration.
- [x] Validated both new v8 JSON configs parse and preserve the expected model/version fields.
- [x] Executed the v8 15-image submission end to end through the Alloy benchmark runner.
- [x] Scored the v8 run against `benchmark_v1_frozen.csv` with zero unmatched VLM keys.
- [x] Captured the v8 aggregate metrics: coarse class agreement 0.2000, evidence agreement 0.0667, review calibration 0.5333.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\config\stage_ab_prompt_tests_smoke_v7_claude_sonnet_4_6_min.json` | Created | Minimal valid evidence-aware smoke config for Claude Sonnet 4.6 |
| `images\Alloy_Class\config\stage_ab_prompt_tests_offset_surface_lines_15_claude_sonnet_4_6.json` | Created | 15-row slice config for recall-focused run |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v8.json` | Created | Versioned clone of the optimized substrate Tier 1 prompt with Claude Sonnet 4.6 |
| `images\Alloy_Class\config\stage_ab_prompt_tests_offset_surface_lines_15_claude_sonnet_4_6_v8.json` | Created | Versioned 15-image submission config for the v8 iteration |
| `images\Alloy_Class\artifacts\benchmark_pairs_one_row_v7_test.csv` | Created | One-row smoke test slice |
| `images\Alloy_Class\artifacts\benchmark_offset_surface_lines_yes_15.csv` | Created | 15-row benchmark slice filtered on `gt_offset_surface_lines_present=yes` |
| `C:\Temp\alloy_benchmark\offset_surface_lines_15_claude_sonnet_4_6_v8\offset_surface_lines_15_claude_sonnet_4_6_v8\stage_ab_results\stage_ab_results.jsonl` | Created | V8 submission output JSONL |
| `C:\Temp\alloy_benchmark\offset_surface_lines_15_claude_sonnet_4_6_v8\offset_surface_lines_15_claude_sonnet_4_6_v8\scoring\benchmark_scored_rows.csv` | Created | Per-row scored comparison CSV for v8 |
| `C:\Temp\alloy_benchmark\offset_surface_lines_15_claude_sonnet_4_6_v8\offset_surface_lines_15_claude_sonnet_4_6_v8\scoring\benchmark_score_summary.json` | Created | Aggregate score summary for v8 |
| `agents_history\index.md` | Modified | Added 2026-08-15 checkpoint session row |
| `agents_history\file_map.md` | Modified | Recorded new session log and working files |
| `agents_history\sessions\2026-08-15_001_alloy-claude-sonnet-4-6-offset-surface-lines-recall-checkpoint.md` | Created | Formal checkpoint log |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv` | Frozen benchmark source for scoring | No |
| `images\Alloy_Class\tools\run_benchmark_vlm.py` | Launcher used for the slice run | No |
| `images\Alloy_Class\tools\score_benchmark_run.py` | Scorer used for the recall measurement | No |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v7.json` | Baseline v7 evidence-aware prompt source | No |

## Bugs Encountered
### BUG-001: Long JSON prompt draft introduced invalid control characters
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\config\stage_ab_prompt_tests_smoke_v7_claude_sonnet_4_6.json`
- **Root Cause:** The first draft of the evidence-aware smoke config embedded literal newlines in the JSON string.
- **Fix Applied:** Replaced it with a smaller valid minimal config that preserves the required evidence check keys.
- **Notes:** This was a config-formatting issue, not a runner or scorer failure.

### BUG-002: First score pass used the wrong benchmark CSV
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\artifacts\benchmark_pairs_one_row_test.csv`, `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv`
- **Root Cause:** The scorer was first pointed at the 1-row pair-list CSV instead of the frozen benchmark CSV.
- **Fix Applied:** Rescored against `benchmark_v1_frozen.csv`.
- **Notes:** This was why the first scored row appeared to lack GT fields.

## Excursions / Scope Creep Discovered
- The smoke run initially exposed that the older v1 config schema did not emit the evidence-check fields needed for row-level recall analysis.
- The one-row sanity test was useful to confirm that `claude-sonnet-4-6` is accepted by the Alloy backend.

## Open Threads
- [ ] Decide whether to compare the same 15-row slice against `gpt-5.4-mini` after the v8 baseline is captured.
- [ ] Decide whether to broaden the recall test to the full 52-row NBC focus set.

## Key Decisions Made
- Use a minimal evidence-aware v7 smoke config for recall testing instead of the older v1 schema.
- Keep the recall test isolated to the 15 rows with `gt_offset_surface_lines_present=yes` so the measurement is directly interpretable.
- Treat the scoring CSV as valid only when it is joined to `benchmark_v1_frozen.csv`, not to the pair-list CSV.

## Recommended Re-Entry
**Load these files for context:**
- `images\Alloy_Class\config\stage_ab_prompt_tests_offset_surface_lines_15_claude_sonnet_4_6.json`
- `images\Alloy_Class\config\stage_ab_prompt_tests_smoke_v7_claude_sonnet_4_6_min.json`
- `images\Alloy_Class\artifacts\benchmark_offset_surface_lines_yes_15.csv`
- `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv`

**Suggested starting prompt:**
> "Review the 15-row offset-surface-lines recall slice, compare the Claude Sonnet 4.6 result against gpt-5.4-mini on the same slice, and decide whether the next step should be model comparison or prompt refinement."

## Notes for Future Agent
The key result is that `vlm_ec_inset_surface_lines` recall on the 15 GT-positive rows remained 1/15 = 0.0667 on the Claude Sonnet 4.6 v8 run. The scoring CSV now includes both GT and VLM evidence columns on the evidence-aware config, so the measurement path is working end to end.