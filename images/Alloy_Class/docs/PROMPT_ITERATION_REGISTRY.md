# Alloy Prompt Iteration Registry

This is the lightest-weight tracking format for VLM prompt experiments in this workspace.

Keep one row per finalized run instance. The goal is to separate the input slice, the execution manifest, the scored output, and the summary metrics without creating a new reporting pipeline.

## Recommended fields

| run_id | parent_iteration | prompt_family | prompt_version | input_slice_csv | scored_rows_csv | score_summary_json | prompt_bundle_json | prompt_bundle_txt | pairs_tested | model | config_path | run_manifest | raw_image_mode | stage_a_brightfield_only | stage_b_multi_image | coarse_agreement | beep_fn_rate | beep_fp_rate | review_calibration | notes |
|---|---|---|---|---|---|---|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|
| benchmark_nbc52_tier1_v3_stageA_BF_only_stageB_multi | 0 | substrate tier1 v3 | stageA/B v3 | [benchmark_pairs_nbc_focus52.csv](../artifacts/benchmark_pairs_nbc_focus52.csv) | benchmark_scored_rows.csv | benchmark_score_summary.json | prompt_bundle.json | prompt_bundle.txt | 52 | `gpt-5.4-mini` | [stage_ab_prompt_tests_substrate_tier1_v3.json](../config/stage_ab_prompt_tests_substrate_tier1_v3.json) | run_manifest.json | `raw-image-mode` | `true` | `true` | 0.4615 | 0.6875 | 0.3 | 0.5 | earlier run with Stage A brightfield-only and Stage B multi-image |
| benchmark_nbc52_tier1_v3_stageA_BF_only_stageB_multi_v2 | 0 | substrate tier1 v3 | stageA/B v3 | [benchmark_pairs_nbc_focus52.csv](../artifacts/benchmark_pairs_nbc_focus52.csv) | benchmark_scored_rows.csv | benchmark_score_summary.json | prompt_bundle.json | prompt_bundle.txt | 52 | `gpt-5.4-mini` | [stage_ab_prompt_tests_substrate_tier1_v3.json](../config/stage_ab_prompt_tests_substrate_tier1_v3.json) | run_manifest.json | `raw-image-mode` | `true` | `true` | 0.5577 | 0.5938 | 0.2 | 0.4231 | corrected runner behavior; Stage A suppressed on DF, Stage B still BF+DF |

## What to record per run instance

- run_id
- parent_iteration or compare_to_run_id
- prompt family in one short phrase
- prompt version or variant ID
- input_slice_csv for the campaign selector slice
- scored_rows_csv for the per-row output
- score_summary_json for the metrics summary
- prompt_bundle_json and prompt_bundle_txt for exact prompt provenance
- pairs_tested
- model
- config_path and run_manifest
- raw_image_mode, stage_a_brightfield_only, and stage_b_multi_image
- the main metric block: coarse agreement, BEEP false negative rate, BEEP false positive rate, and review calibration
- brief note on the main change

## Suggested convention

- Keep the row-level scored CSV immutable once a run is finalized.
- Keep the summary JSON alongside it in the same run output folder.
- If a run is rescored, write a new run instance row instead of overwriting the prior one.
- Keep `parent_iteration` or `compare_to_run_id` explicit when the same slice is rerun with only prompt or stage configuration changes.

## Current tracking guidance

The current tooling already supports the needed split:

- `images/Alloy_Class/tools/run_benchmark_vlm.py` writes the run outputs.
- `images/Alloy_Class/tools/score_benchmark_run.py` writes per-row scored CSV plus summary JSON.
- The run folder now stores `prompt_bundle.json` and `prompt_bundle.txt` as the run-local prompt provenance artifact.

That means the registry should stay shallow: one short row per run instance, with the slice, execution manifest, scored output, and summary metrics separated into their own columns.

## CSV tracker

Use `images/Alloy_Class/artifacts/prompt_iteration_registry.csv` as the machine-editable tracker.

Suggested columns:

- run_id
- parent_iteration
- prompt_family
- prompt_version
- input_slice_csv
- scored_rows_csv
- score_summary_json
- prompt_bundle_json
- prompt_bundle_txt
- pairs_tested
- model
- config_path
- run_manifest
- raw_image_mode
- stage_a_brightfield_only
- stage_b_multi_image
- coarse_agreement
- beep_fn_rate
- beep_fp_rate
- review_calibration
- note

Keep the CSV rows aligned with the table above. If a later run has explicit scored-row outputs, point `scored_rows_csv` at the scored CSV and leave `input_slice_csv` as the campaign selector input.
Use `prompt_bundle_json` and `prompt_bundle_txt` to point at the run-local prompt provenance files for each finalized run instance.
