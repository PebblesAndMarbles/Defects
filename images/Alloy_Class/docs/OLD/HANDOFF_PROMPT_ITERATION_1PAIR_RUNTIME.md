# Handoff: Prompt Iteration Toward 1-Pair Runtime Optimization

Date: 2026-07-26
Owner context: BE Alloy Phase 1 rapid iteration

## Purpose

This handoff documents how prompt design evolved from Doruk and Rob's original examples to the current implementation, and how to optimize 1-pair runtime without breaking end-to-end flow (VLM call -> classify/caption outputs -> HTML review).

## Original Context References

Primary source references in this workspace:

- Doruk + Rob email/context capture:
  - images/Alloy_Class/Current_Ask.txt
- Team notes / recommendations:
  - images/Alloy_Class/Aksoy_and_Rob.md
- Doruk-style batch script baseline:
  - images/Alloy_Class/vision_defect_batch_unzipped/vision_defect_batch.py
- Rob-style captioning baseline:
  - images/Alloy_Class/trey_01_captioning.ipynb

Current pipeline files:

- Structured classify batch:
  - images/Alloy_Class/pipelines/classify_phase1_batch.py
- Caption batch:
  - images/Alloy_Class/pipelines/caption_phase1_batch.py
- Combined HTML report:
  - images/Alloy_Class/reporting/build_phase1_html_report.py
- End-to-end orchestrator:
  - images/Alloy_Class/tools/run_raw_stage_batch.py

Runtime + prompt configs:

- Phase 1 prompt/settings:
  - images/Alloy_Class/config/phase1_settings.json
- Stage A/B prompt suites:
  - images/Alloy_Class/config/stage_ab_prompt_tests.json
  - images/Alloy_Class/config/stage_ab_prompt_tests_context_v2.json

## What Doruk and Rob Proposed (Baseline)

### Doruk baseline

From Current_Ask and the attached script:

- Use Alloy vision endpoint for batch processing.
- Enforce structured JSON for downstream automation.
- Keep prompt and schema editable for iterative tuning.
- Consider multi-image input support and evaluator loops.

In code form (vision_defect_batch.py):

- Direct HTTP call to /api/vision.
- response_format=json_schema strict output.
- Single-pass defect summary schema.

### Rob baseline

From Current_Ask and notebook workflow:

- Start with high-signal descriptive captioning on single image.
- Iterate prompts and model choice quickly.
- Use output richness to judge whether fine-bin discrimination is achievable.
- Keep reviewability high before hard-constraining taxonomy.

In code form today:

- caption_phase1_batch.py keeps a freeform descriptive prompt style.

## What Changed In Current Implementation

### High-level delta

The current implementation combines Doruk + Rob ideas, with additional controls for production-like iteration:

- Pair-aware BF/DF processing (2/3 pairing) instead of image-only batch.
- Raw transient image option with strict mode (burned vs raw control).
- Optional metadata prompt augmentation in classify.
- End-to-end orchestration including HTML packaging.
- Frozen pair lists (1/5/20) for repeatable, low-overhead iteration.

### Detailed delta table

1) Input granularity
- Doruk baseline: image-by-image batch over input folder.
- Rob baseline: one image notebook example.
- Current: BF/DF paired runs with max_pairs controls and frozen subsets.

2) Prompt style
- Doruk baseline: concise defect analysis prompt with fixed schema.
- Rob baseline: rich descriptive captioning prompt.
- Current classify: schema-oriented defect classifier prompt (`phase1_v1`) with review_required/confidence behavior.
- Current caption: Rob-style descriptive prompt retained.

3) Structured constraints
- Doruk baseline: strict JSON schema in direct API payload.
- Current classify: strict JSON intent via prompt + parser extraction and structured record emission.
- Current stage A/B: explicit allowed-value logic and two-stage semantics.

4) Context injection
- Doruk baseline: image-only prompt+schema.
- Rob baseline: image-only descriptive context.
- Current classify: optional metadata append per image (SIZE_X, SIZE_Y, SIZE_D, AREA, MANUAL_OPTICAL_CLASS) as non-binding context.

5) Runtime controls
- Doruk baseline: timeout + skip existing outputs.
- Current: strict raw mode, local short staging paths, pair filtering (SMP/BEEP), timing breakdown, and frozen pair-mode.

6) Reporting loop
- Doruk baseline: JSON outputs for downstream tools.
- Rob baseline: human-readable narrative output.
- Current: both JSONL and paired HTML side-by-side with caption + structured fields + reviewer flags.

## Current Prompt Surfaces Affecting 1-Pair Runtime

Prompt-related knobs that can alter both latency and quality:

1) Classify prompt text complexity
- File: config/phase1_settings.json
- Key: prompt
- Impact: longer instruction text can increase prompt-token load and model reasoning time.

2) Optional metadata append
- File: pipelines/classify_phase1_batch.py
- Function: _prompt_with_optional_metadata(...)
- Impact: adds per-image prompt length (token and latency increase), often improves disambiguation.

3) Completion token ceiling
- Classify/caption currently call max_completion_tokens=500.
- Impact: larger upper bound can increase tail latency/cost in difficult cases.

4) Stage A/B prompt depth
- Files: config/stage_ab_prompt_tests*.json
- Impact: richer two-stage semantics can improve class quality, but add latency and output length.

## Why 1-Pair Optimization Must Separate Prompt Time From Pipeline Time

For 1-pair runs, measured total runtime is not pure model runtime unless selection/copy/raw/report overhead is controlled.

Already addressed:

- Frozen pair lists exist for 1/5/20:
  - images/Alloy_Class/config/frozen_pairs/smp_pairs_1.csv
  - images/Alloy_Class/config/frozen_pairs/smp_pairs_5.csv
  - images/Alloy_Class/config/frozen_pairs/smp_pairs_20.csv
- Orchestrator supports --pair-list-csv to bypass manifest scan.
- Report supports structured path sourcing for fast E2E review.

This means 1-pair runtime can now focus on:

- classify prompt + output behavior
- caption prompt + output behavior
- raw download path behavior

## Practical 1-Pair Prompt Iteration Strategy

Use a fixed 1-pair image set and change one prompt factor at a time.

Recommended phases:

1) Baseline classify+caption
- Keep current phase1_v1 prompt and caption prompt.
- Keep frozen 1-pair set.

2) Prompt compression pass
- Shorten classify instruction wording while preserving output keys/rules.
- Goal: reduce prompt tokens and latency without quality regression.

3) Metadata gating pass
- Compare with and without metadata append.
- Goal: quantify whether metadata helps enough to justify runtime overhead.

4) Output ceiling pass
- Evaluate lower max_completion_tokens caps for classify and caption.
- Goal: trim long-tail response time while preserving required fields.

5) Stage A/B selective use
- Use stage A/B only when baseline classify is uncertain or flagged.
- Goal: pay complexity only on hard cases.

## Suggested Experiment Logging Fields (for handoff continuity)

Track these per run:

- run_id
- prompt_version (classify)
- caption prompt variant ID
- max_completion_tokens per call
- metadata_append_enabled (Y/N)
- raw_mode (strict/non-strict)
- total runtime
- classify runtime
- caption runtime
- html runtime
- review_required rate
- bf/df disagreement rate
- smp_to_beep_suspect count

## Working Examples Mapping (Doruk/Rob -> Current)

Doruk example maps to:

- structured output intent:
  - images/Alloy_Class/pipelines/classify_phase1_batch.py
- batch automation and resumability:
  - images/Alloy_Class/tools/run_raw_stage_batch.py

Rob example maps to:

- descriptive captioning path:
  - images/Alloy_Class/pipelines/caption_phase1_batch.py
- side-by-side human review output:
  - images/Alloy_Class/reporting/build_phase1_html_report.py

Combined today:

- one orchestrated loop from image pair selection to final HTML review.

## Immediate Next-Step Recommendation

For fastest optimization toward 1-pair runtime:

1) Keep frozen pair list + structured image-path report mode.
2) Create prompt variants that only modify classify prompt length/verbosity.
3) Hold all else constant and compare runtime + review flags.
4) Introduce metadata append only if it measurably improves disagreement/review outcomes.

This preserves the original Doruk/Rob intent while giving a controlled path to lower runtime and stable quality.

## Execution Summary Update (2026-07-26)

This section captures the actual runtime experiments executed in this workspace and where outputs were written.

### What Was Implemented

1) Completion token ceiling made configurable
- classify now reads `max_completion_tokens` from settings (default 500).
- caption now supports `--max-completion-tokens` CLI flag (default 500).

2) Per-image timing telemetry added
- classify writes per-row `timing_seconds` with:
  - `raw_download`
  - `inference`
  - `row_total`
- caption writes per-row `timing_seconds.row_total`.

3) HTML path robustness fix for UNC vs local-drive mix
- report builder now handles cross-mount path cases (UNC report dir with `C:` image files) by falling back to URI path when Windows `relpath` cannot be computed.

### What Was Varied

Controlled variables:
- Frozen pair lists with `--pair-list-csv`:
  - `config/frozen_pairs/smp_pairs_1.csv`
  - `config/frozen_pairs/smp_pairs_5.csv`
- Raw mode enabled with strict requirement (`--require-raw`).
- classify-only timing matrix used `--skip-caption --skip-html` for prompt-speed isolation.

Experiment variants:
1) `baseline`
- prompt version: `phase1_v1`
- classify max completion tokens: 500

2) `prompt_short`
- prompt version: `phase1_v1_short`
- shortened classify instruction text
- classify max completion tokens: 500

3) `cap180`
- prompt version: `phase1_v1`
- classify max completion tokens: 180

### Key Runtime Results

Initial p1+p5 matrix (3 repeats each):
- artifact: `images/Alloy_Class/artifacts/clean_runtime_matrix_agg_20260726.csv`

Highlights:
- p1 baseline classify median: 11.015 s
- p5 baseline classify median: 39.709 s total for 5 pairs
- p5 baseline per-pair avg total: about 9.581 s/pair from 3-run aggregate

Extended p5 stabilization run (8 repeats each variant):
- artifact: `images/Alloy_Class/artifacts/clean_runtime_matrix_agg_20260726_p5_r8.csv`

p5 (8-run) summary:
- baseline: median classify 40.541 s, p90 41.482 s, per-pair avg total 9.685 s, outliers 0
- prompt_short: median classify 39.610 s, p90 65.414 s, per-pair avg total 10.212 s, outliers 1
- cap180: median classify 44.221 s, p90 61.253 s, per-pair avg total 11.265 s, outliers 0

Interpretation:
- baseline p5 shows stable tails and lower per-pair total runtime than p1 baseline because fixed overhead is amortized over more pairs.
- prompt_short and cap180 still show occasional higher-tail behavior in p5 despite similar or better medians in some runs.

### Output Locations

Primary summary artifacts:
- `images/Alloy_Class/artifacts/clean_runtime_matrix_rows_20260726.csv`
- `images/Alloy_Class/artifacts/clean_runtime_matrix_agg_20260726.csv`
- `images/Alloy_Class/artifacts/clean_runtime_matrix_rows_20260726_p5_r8.csv`
- `images/Alloy_Class/artifacts/clean_runtime_matrix_agg_20260726_p5_r8.csv`
- `images/Alloy_Class/artifacts/clean_runtime_matrix_agg_20260726_p5_r8.json`

Example run output roots:
- `images/Alloy_Class/outputs/raw_runs/clean_mx_20260726_p1_baseline_r1/`
- `images/Alloy_Class/outputs/raw_runs/clean_mx_20260726_p5_baseline_r8/`

### Note On Image Copying And HTML Path Source

Updated preferred behavior:
- keep local short-path staging copy for inference only.
- do not copy burned/source library images into run outputs when not needed.
- prefer report image resolution from structured records (UNC/library paths).

Current recommended orchestrator flags:
- `--no-copy-burned`
- `--report-image-path-source structured`

Rationale:
- preserves end-to-end VLM->report loop.
- avoids redundant burned-image duplication in run folders.
- keeps HTML aligned to source-of-truth library paths in manifest-derived records.
- for stricter UNC-image preference, use report path-source controls and/or update orchestration to preserve original UNC source path in structured records.
