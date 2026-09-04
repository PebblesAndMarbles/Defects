# Handoff: v8 Claude Sonnet 4.6 Submission Shows Partial Empty Rows

## Problem Statement
The v8 15-image Alloy benchmark submission for Claude Sonnet 4.6 completed, but the scored CSV contains many rows with missing VLM judgment fields. The issue is not a full-run failure; it is a partial-output problem where some rows have complete Stage A / Stage B predictions and others are blank or only partially populated.

## What Happened
- Created `stage_ab_prompt_tests_substrate_tier1_v8.json` as a direct clone of the optimized v7 prompt config.
- Created `stage_ab_prompt_tests_offset_surface_lines_15_claude_sonnet_4_6_v8.json` for the 15-image slice.
- Ran the benchmark successfully with `claude-sonnet-4-6`.
- Scored the run against the canonical frozen benchmark CSV at [images/Alloy_Class/artifacts/benchmark_v1_frozen.csv](images/Alloy_Class/artifacts/benchmark_v1_frozen.csv).
- Observed that 7 of 15 scored rows are missing most or all `vlm_*` fields.

## Observed Symptoms
From `benchmark_scored_rows.csv`:
- `N Missing(vlm_coarse_class) = 7`
- `N Missing(vlm_blocked_etch_evidence) = 7`
- `N Missing(vlm_review_required) = 7`
- `N Missing(vlm_stage_a_confidence) = 6`
- `N Missing(vlm_stage_b_confidence) = 7`
- `N Missing(vlm_ec_inset_surface_lines) = 7`
- `N Missing(vlm_ec_boundary_conformance) = 7`
- `N Missing(vlm_ec_sunken_residual) = 7`
- `N Missing(vlm_rationale) = 7`

Verified comparison against the GPT-mini baseline CSV (`benchmark_nbc52_tier1_v7_stageA_BF_only_stageB_multi_v1/scoring/benchmark_scored_rows.csv`):
- Sonnet v8 has 15 scored rows, with 6 missing `vlm_*` fields for most outputs and 7 missing `vlm_stage_a_confidence`.
- GPT-mini has 52 scored rows and only 1 missing row for the same `vlm_*` judgment fields; `vlm_stage_a_confidence` is fully populated.
- Sonnet confidence values are often qualitative strings such as `high`, `medium`, `medium-high`, `moderate`, and `moderate-high`.
- GPT-mini confidence values are consistently numeric strings such as `0.77`, `0.82`, `0.90`, `0.95`.

## Key Evidence
The raw JSONL does not show a prompt-string construction failure. It shows mixed outcomes:
- Several rows contain full parsed `stage_a` and `stage_b` JSON objects.
- Some rows contain only `raw_text` / excerpt fragments instead of parsed fields.
- At least one pair (`260803_1800_D616465_064_SMP_8M6CL_10911`) has both brightfield and darkfield rows where Stage B is literally `Error: Server returned empty description`.

This suggests the issue is more likely a response-generation or parsing failure than a bad prompt bundle.

## Likely Root Cause
Most likely causes, in descending order:
1. Intermittent backend/model response failure for certain rows.
2. Runner/parser failing to convert malformed or truncated Stage B responses into structured fields.
3. Less likely: prompt/schema incompatibility causing the model to emit empty or unusable descriptions for some images.

The prompt bundle itself appears intact in `prompt_bundle.json`, so the prompt text is probably not the primary failure mode.

Additional interpretation:
- The Sonnet run is not just missing rows; it also appears less rule-consistent in field formatting.
- The most visible violation is `confidence`, which sometimes comes back as qualitative text instead of the expected numeric-style output used by the GPT-mini baseline.
- That suggests either the Sonnet prompt is insufficiently constraining the output contract, or the model is more prone to partial schema drift under this prompt bundle.
- Because GPT-mini largely stays numeric and populated under the similar pipeline, the regression looks model-sensitive rather than purely runner-wide.

## Best Discriminating Check
Re-run only the failing pair(s), especially:
- `260803_1800_D616465_064_SMP_8M6CL_10911`

If the same pair fails again with the same empty Stage B response, the issue is probably backend/model instability or a content-triggered failure.
If it succeeds on retry, the issue is likely transient or batch-related.

## Files To Inspect
- [stage_ab_prompt_tests_substrate_tier1_v8.json](images/Alloy_Class/config/stage_ab_prompt_tests_substrate_tier1_v8.json)
- [stage_ab_prompt_tests_offset_surface_lines_15_claude_sonnet_4_6_v8.json](images/Alloy_Class/config/stage_ab_prompt_tests_offset_surface_lines_15_claude_sonnet_4_6_v8.json)
- [prompt_bundle.json](C:\Temp\alloy_benchmark\offset_surface_lines_15_claude_sonnet_4_6_v8\offset_surface_lines_15_claude_sonnet_4_6_v8\prompt_bundle.json)
- [stage_ab_results.jsonl](C:\Temp\alloy_benchmark\offset_surface_lines_15_claude_sonnet_4_6_v8\offset_surface_lines_15_claude_sonnet_4_6_v8\stage_ab_results\stage_ab_results.jsonl)
- [benchmark_scored_rows.csv](C:\Temp\alloy_benchmark\offset_surface_lines_15_claude_sonnet_4_6_v8\offset_surface_lines_15_claude_sonnet_4_6_v8\scoring\benchmark_scored_rows.csv)
- [benchmark_score_summary.json](C:\Temp\alloy_benchmark\offset_surface_lines_15_claude_sonnet_4_6_v8\offset_surface_lines_15_claude_sonnet_4_6_v8\scoring\benchmark_score_summary.json)
- [benchmark_v1_frozen.csv](images/Alloy_Class/artifacts/benchmark_v1_frozen.csv) is the exact benchmark CSV path to use for scoring; do not search the temp run tree for a duplicate.

## Current Measured Metrics
For the full scored run:
- `pairs_scored = 15`
- `coarse_class_agreement_rate = 0.2000`
- `evidence_agreement_rate = 0.0667`
- `review_required_calibration_rate = 0.5333`
- `unmatched_vlm_keys = []`

## Recommended Next Step For Another Agent
1. Inspect the failing pair(s) in the raw JSONL and determine whether the empty response is reproducible.
2. Compare the prompt/rendered input for a failing pair against a successful pair.
3. Decide whether to:
   - retry the failing row(s),
   - force raw-image mode or stricter output capture,
   - tighten the Stage B prompt to explicitly forbid qualitative confidence text and require a numeric scalar, or
   - adjust the Stage B prompt for the specific failure trigger.
4. Use [images/Alloy_Class/artifacts/benchmark_v1_frozen.csv](images/Alloy_Class/artifacts/benchmark_v1_frozen.csv) as the scorer input when rerunning; that is the canonical frozen benchmark source.

## Feedback
The immediate feedback from this comparison is that Sonnet v8 appears less stable than the GPT-mini baseline on both completeness and schema adherence. The missing-row rate is substantially worse, and the filled rows show weaker compliance with the confidence-field contract. Before treating Sonnet as a valid replacement, the next iteration should likely add explicit output guards for confidence formatting and a stronger empty-response recovery path.

## v9 Follow-Up
I also reran the same 15-image submission as v9 with only `max_completion_tokens` increased from 600 to 900. That changed the behavior materially:
- The v9 run completed with only 1 missing scored row, down from 7 missing rows in v8.
- The scorer reported `stage_b_contract: raw_text_fallback_rows=2 rows_missing_required=2 non_numeric_confidence=22`, which means the run is much more complete but still not fully contract-clean.
- The launcher summary improved as well, with `stage_b_review_rate` rising to 0.9333 and `stage_b_possible_beep_rate` to 0.2667.
- The v9 scored CSV still contains qualitative confidence values such as `high`, `medium`, and `moderate-high`, so the confidence-format drift is not fully resolved by extra tokens alone.

Interpretation:
- Increasing the token budget to 900 appears to reduce outright blanking substantially.
- It does not fully fix schema adherence, because non-numeric confidence values and a small amount of fallback/raw-text behavior still remain.
- The next best follow-up is likely to keep the 900-token setting as the preferred baseline, then tighten the Stage B output contract specifically around confidence formatting and fallback handling.

## v9 Files / Results
- `images/Alloy_Class/config/stage_ab_prompt_tests_substrate_tier1_v9.json`
- `images/Alloy_Class/config/stage_ab_prompt_tests_offset_surface_lines_15_claude_sonnet_4_6_v9.json`
- `C:\Temp\alloy_benchmark\offset_surface_lines_15_claude_sonnet_4_6_v9\offset_surface_lines_15_claude_sonnet_4_6_v9\scoring\benchmark_scored_rows.csv`
- `C:\Temp\alloy_benchmark\offset_surface_lines_15_claude_sonnet_4_6_v9\offset_surface_lines_15_claude_sonnet_4_6_v9\scoring\benchmark_score_summary.json`

## Working Hypothesis
The prompt is not the main failure. The more plausible issue is intermittent model/server output failure on a subset of rows, with the scorer faithfully propagating blanks when Stage B parsing fails.
