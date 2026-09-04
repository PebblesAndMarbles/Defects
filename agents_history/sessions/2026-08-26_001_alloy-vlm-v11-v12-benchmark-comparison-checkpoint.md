---
session_id: 2026-08-26_001
title: Alloy VLM V11/V12 Benchmark Comparison Checkpoint
date: 2026-08-26
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: GPT-5.4 mini
triggered_by: manual-checkpoint
status: complete
original_goal: Record the V11/V12 prompt-contract work, the one-pair smoke validations, and the 15-pair offset-surface-lines benchmark comparison.
---

## Original Goal
Capture the current Alloy Class VLM state after the V11/V12 prompt-contract iterations, the one-pair smoke tests, and the 15-pair benchmark comparisons on the offset-surface-lines slice.

## Completed Tasks
- [x] Created a tracked V11 config variant for the offset-surface-lines prompt line with rationale placed last in the output contract.
- [x] Ran a one-pair smoke test on V11 and confirmed the reordered contract executed cleanly.
- [x] Ran the 15-pair offset-surface-lines benchmark on V11 and scored it successfully with zero contract failures.
- [x] Created a tracked V12 config variant with additional prompt guidance and output-contract tightening.
- [x] Ran a one-pair smoke test on V12 and confirmed it executed cleanly.
- [x] Ran the 15-pair offset-surface-lines benchmark on V12 and scored it successfully with zero contract failures.
- [x] Compared V11 vs V12 on the same 15-pair slice and confirmed identical coarse agreement, FN rate, and FP rate.
- [x] Confirmed V12 slightly worsened evidence agreement versus V11 on this slice, so V11 remains the safer baseline.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v11.json` | Created / Modified | Tracked V11 config variant with reordered Stage B contract and rationale last |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v12.json` | Created / Modified | Tracked V12 config variant with additional prompt guidance and same contract budget |
| `images\Alloy_Class\tools\run_benchmark_vlm.py` | Modified | Added support for frozen pair CSVs using `bright_path` / `dark_path` fallback columns |
| `agents_history\sessions\2026-08-26_001_alloy-vlm-v11-v12-benchmark-comparison-checkpoint.md` | Created | Formal checkpoint log for the V11/V12 benchmark comparison |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\config\stage_ab_prompt_tests_offset_surface_lines_15_claude_sonnet_4_6_v10.json` | Source prompt body used to seed the V11/V12 offset-surface-lines comparison line | No |
| `images\Alloy_Class\artifacts\benchmark_offset_surface_lines_yes_15.csv` | 15-pair ground-truth slice used for both benchmark runs | No |
| `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v11_compare` | V11 benchmark output root and scoring artifacts | No |
| `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v12_compare` | V12 benchmark output root and scoring artifacts | No |
| `images\Alloy_Class\outputs\raw_runs\smp_frozen1_v11_smoke_rerun` | One-pair V11 smoke validation output | No |
| `images\Alloy_Class\outputs\raw_runs\smp_frozen1_v11_v11_smoke_rerun` | V11 smoke output root, used as a validation step in the workflow | No |
| `images\Alloy_Class\outputs\raw_runs\smp_frozen1_v11_smoke_rerun` | V11 smoke artifact root used to validate the config before the 15-pair run | No |
| `images\Alloy_Class\outputs\raw_runs\smp_frozen1_v11_smoke_rerun\stage_ab_results\benchmark_score_summary.json` | V11 smoke scoring summary | No |
| `images\Alloy_Class\outputs\raw_runs\smp_frozen1_v11_smoke_rerun\stage_ab_results\stage_ab_results.jsonl` | V11 smoke row outputs | No |
| `images\Alloy_Class\outputs\raw_runs\smp_frozen1_v12_smoke_rerun` | V12 smoke artifact root used to validate the copied prompt body | No |
| `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v11_compare\stage_ab_results\benchmark_score_summary.json` | V11 15-pair scoring summary | No |
| `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v12_compare\stage_ab_results\benchmark_score_summary.json` | V12 15-pair scoring summary | No |
| `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v11_compare\stage_ab_results\benchmark_scored_rows.csv` | V11 scored rows | No |
| `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v12_compare\stage_ab_results\benchmark_scored_rows.csv` | V12 scored rows | No |
| `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv` | Prior baseline mentioned during comparison work | No |

## Bugs Encountered
### BUG-001: UNC output path typo during smoke and benchmark launches
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v11.json`, `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v12.json`
- **Root Cause:** A duplicated `ORAnalysis$` segment in the output-folder UNC path caused `run_benchmark_vlm.py` to fail before staging.
- **Fix Applied:** Re-ran the smoke and benchmark commands with the correct UNC or workspace-relative output path.
- **Notes:** The failure was environmental/command-string related, not a prompt-contract regression.

### BUG-002: V11/V12 comparison showed no benchmark improvement on tune FN rate
- **Status:** Unresolved
- **File(s):** `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v11.json`, `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v12.json`
- **Root Cause:** The added V12 guidance did not improve the tune-split false-negative rate on the 15-pair offset-surface-lines slice.
- **Fix Applied:** None; V11 retained as the safer baseline because V12 slightly worsened evidence agreement.
- **Notes:** Both V11 and V12 remained contract-clean with zero raw-text fallback rows.

## Excursions / Scope Creep Discovered
- Investigated the earlier BF/DF routing concern and verified the issue was not in `stage_b_input_paths` for the benchmark harness used here.
- Confirmed that the key gain from the prompt work was contract stability, not recall improvement on the tune slice.

## Open Threads
- [ ] Improve the tune-split FN rate without reintroducing raw-text fallbacks.
- [ ] Decide whether the offset-surface-lines line should stay on V11 or be superseded by a future V13 that targets the tune failures more directly.
- [ ] THREAD-001 remains open: `build_benchmark_candidates.py` still not built.
- [ ] THREAD-002 remains open: manifest metadata backfill lag for recent rows.
- [ ] THREAD-006 remains open: `bc` detection gap.
- [ ] THREAD-007 remains open: Stage A confounder language may still suppress `isl` detection.
- [ ] THREAD-008 remains deferred: `sr` detection ceiling.
- [ ] THREAD-009 remains open: BMK_0037 relabeling question.

## Key Decisions Made
- Keep the output contract order with `rationale` last so the model can finish the structured fields earlier under the same token budget.
- Avoid increasing `max_completion_tokens`; use prompt-ordering and prompt-compression first.
- Treat V11 as the safer baseline for the offset-surface-lines slice because V12 preserved parse stability but did not improve FN behavior.
- Preserve the benchmark slice and scoring artifacts as the primary comparison signal, rather than relying on smoke-test impressions alone.

## Recommended Re-Entry
**Load these files for context:**
- `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v11.json`
- `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v12.json`
- `images\Alloy_Class\config\stage_ab_prompt_tests_offset_surface_lines_15_claude_sonnet_4_6_v10.json`
- `images\Alloy_Class\artifacts\benchmark_offset_surface_lines_yes_15.csv`
- `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v11_compare\stage_ab_results\benchmark_score_summary.json`
- `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v12_compare\stage_ab_results\benchmark_score_summary.json`

**Suggested starting prompt:**
> "Continue the Alloy VLM prompt-comparison work from the V11/V12 offset-surface-lines checkpoint, review the scored summaries for both runs, and decide whether a V13 prompt should target tune-split FN reduction while keeping the zero contract-failure behavior."

## Notes for Future Agent
- The V11 and V12 15-pair runs both scored cleanly with zero contract failures.
- The V12 prompt body is a tracked variant in the V11/V12 line; it did not improve the tune split on this slice.
- V11 is the safer baseline if a future rerun is needed before additional prompt iteration.
