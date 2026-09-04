# Plan: 20-Image Substrate Prompt Tier Test (Agent Handoff)

Date: 2026-07-26
Goal: test two substrate prompt tiers on a fixed 20-image set and compare quality/runtime.

## Scope

- Use existing frozen SMP 20-pair list as sampling source.
- Evaluate Tier 1 vs Tier 2 Stage A substrate prompts.
- Keep model fixed at gpt-5.4-mini.
- Keep output review path end-to-end (JSONL + HTML), with preference to UNC/library image paths in reports.

## Inputs

1. Pair list
- images/Alloy_Class/config/frozen_pairs/smp_pairs_20.csv

2. Prompt test configs
- images/Alloy_Class/config/stage_ab_prompt_tests_substrate_tier1_v1.json
- images/Alloy_Class/config/stage_ab_prompt_tests_substrate_tier2_v1.json

3. Runtime/orchestration
- images/Alloy_Class/tools/run_raw_stage_batch.py
- Use --no-copy-burned and --report-image-path-source structured

## Test Design

Run A: Tier 1 substrate suite
- Focus: stable coarse substrate extraction with low overhead

Run B: Tier 2 substrate suite
- Focus: adjudication logic for ambiguous/occluded/confounded cases

Hold constant:
- same image set
- same model
- same environment/interpreter

## Execution Steps (for assigned agent)

1) Prepare run workspace
- Confirm outputs folder for this campaign:
  - images/Alloy_Class/outputs/stage_ab_tests/substrate_tier_campaign_20/

2) Run Tier 1 Stage A/B test
- Use config:
  - config/stage_ab_prompt_tests_substrate_tier1_v1.json
- Use raw-first substrate flags:
  - --raw-image-mode
  - --raw-strict
  - --raw-stage-a-only
- Record output paths for:
  - stage_ab_results.jsonl
  - stage_ab_summary.json

3) Run Tier 2 Stage A/B test
- Use config:
  - config/stage_ab_prompt_tests_substrate_tier2_v1.json
- Use raw-first substrate flags:
  - --raw-image-mode
  - --raw-strict
  - --raw-stage-a-only
- Record output paths for:
  - stage_ab_results.jsonl
  - stage_ab_summary.json

4) Build review artifacts
- Generate side-by-side comparison HTML for Tier 1 vs Tier 2 outputs.
- Ensure HTML image links prefer structured/library paths (UNC), not burned-image copies.

## Evaluation Metrics

Primary quality metrics:
- Stage A field completeness rate
- Orientation consistency rate (horizontal/vertical/mixed/unknown)
- review_required rate (target: lower false escalation than current baseline)
- plausible comparator-use behavior in rationale
- candidate blocked-structure calls when comparators are visible

Secondary quality metrics:
- Stage B possible_beep rate
- Stage B indeterminate rate
- cross-stage conflict rate (strong blocked-etch with weak/unknown substrate context)

Runtime metrics:
- total suite runtime
- per-row average runtime
- p50/p90 row runtime if available

## Acceptance Criteria

Tier advancement recommendation should include:
- Which tier should be default for bulk throughput
- Which tier should be escalation-only
- Concrete escalation trigger proposal (for example: context_confidence < 0.75 or confounder present)

## Deliverables

1) Result summary markdown
- images/Alloy_Class/docs/SUBSTRATE_PROMPT_TIER20_RESULTS.md

2) Consolidated metrics table (csv or markdown)
- include Tier 1 vs Tier 2 side-by-side

3) Recommendation block
- default tier
- escalation criteria
- known failure modes

## Notes And Constraints

- Preference is to avoid copying burned/source images into run output folders.
- HTML/reporting should reference UNC library paths when available in structured outputs.
- Keep runs reproducible; do not change pair set during this campaign.
- For this campaign, substrate characterization (Stage A) should run on transient raw images only.
- Stage B may remain on staged/library image by default (`--raw-stage-a-only`) unless explicitly changed.










## Agent Answers / Decisions

1) Config files
- `config/stage_ab_prompt_tests_substrate_tier1_v1.json` exists.
- `config/stage_ab_prompt_tests_substrate_tier2_v1.json` exists.
- No additional config creation is required before execution.

2) `run_raw_stage_batch.py` flags
- `--report-image-path-source` already exists in orchestrator.
- `--no-copy-burned` already exists in orchestrator.
- `--require-raw` is independent and still recommended for strict transient-raw behavior.

3) Side-by-side HTML support
- Existing script is available:
  - `reporting/build_stage_ab_html_report.py`
- Use this for Tier 1 vs Tier 2 comparison HTML output.

4) Output folder disambiguation
- Use separate subfolders explicitly:
  - `outputs/stage_ab_tests/substrate_tier_campaign_20/tier1/`
  - `outputs/stage_ab_tests/substrate_tier_campaign_20/tier2/`
- Do not rely on shared filenames in one folder.

5) Baseline definition
- Baseline for "false escalation" should be Stage A `review_required` rate from the latest current suite output unless replaced by a curated labeled baseline.
- Current available reference summary:
  - `outputs/stage_ab_tests/stage_ab_summary.json`
- If a stricter baseline is required, establish it first from a frozen 20-image adjudicated set.

6) Agent execution defaults
- Interpreter:
  - `c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe`
- Model:
  - `gpt-5.4-mini` (from config)
- Pair set:
  - `config/frozen_pairs/smp_pairs_20.csv`
- Reporting preference:
  - structured/library path mode
  - avoid burned-image output duplication


## AGENT QUESTION

One minor thing to verify before starting: the --report-image-path-source structured flag — does it accept a --run-id that mirrors the tier name (e.g., substrate_tier1_20260726 / substrate_tier2_20260726) so the output subfolders are created automatically, or do you need to manually specify --output-dir pointing to the tier1/ and tier2/ paths?

## AGENT ANSWER

Short answer: manually set separate output folders for Tier 1 and Tier 2 when running the Stage A/B harness.

Important distinction:

1) `tools/run_raw_stage_batch.py`
- Has `--report-image-path-source` and `--run-id`.
- Creates run folder automatically as `output-root/run-id`.

2) `reporting/run_stage_ab_prompt_tests.py`
- Does not use `--report-image-path-source`.
- Uses `--output-folder` directly.
- `--run-id` is metadata in output records, not automatic directory partitioning.

Execution decision for this campaign:

- Tier 1 run:
  - `--output-folder images/Alloy_Class/outputs/stage_ab_tests/substrate_tier_campaign_20/tier1`
  - `--run-id substrate_tier1_20260726`

- Tier 2 run:
  - `--output-folder images/Alloy_Class/outputs/stage_ab_tests/substrate_tier_campaign_20/tier2`
  - `--run-id substrate_tier2_20260726`

This prevents filename collisions and keeps outputs cleanly separated for comparison.

## AGENT QUESTION 2

One question: what should --input-folder point to? The plan references smp_pairs_20.csv as the frozen pair source — does the inputs folder already contain those 20 images, or do they need to be staged from the frozen pair list first? If the run_stage_ab_prompt_tests.py script reads images directly from a folder, I need to know the correct input path before running.

## AGENT ANSWER 2

Short answer: stage the 20 pairs into a dedicated local input folder first, then point `--input-folder` to that staged folder.

Use this input folder for Stage A/B runs:
- `C:/temp/alloy_raw_stage/substrate_tier_campaign_20/inputs`

Important behavior clarifications:

1) Stage A/B harness input behavior
- `reporting/run_stage_ab_prompt_tests.py` reads images directly from `--input-folder`.
- It now supports transient raw download mode from manifest metadata.
- With `--raw-image-mode`, inference can use downloaded raw images instead of staged burned images.

2) Copy behavior expectation
- For Stage A/B testing, staging into local inputs is required (copy step exists).
- For raw-stage orchestration, `--no-copy-burned` means no burned image copy into run output folders, but local inference staging copy is still performed.

3) Raw-vs-burned VLM submit behavior
- Strict raw VLM submission is now available in Stage A/B harness with:
  - `--raw-image-mode --raw-strict`
- For substrate-only raw preference, use:
  - `--raw-stage-a-only`

4) HTML image-source expectation
- With current report settings, HTML can prefer structured paths and avoid run-output burned copies.
- Unless raw temp retention/report precedence is changed, HTML is expected to show burned/library-context images (for human review) rather than transient raw temp files that are deleted after inference.

---

## Campaign Status: COMPLETE (2026-07-27)

### Run-Condition Caveat (Added 2026-07-31)

The completed Tier 1/Tier 2 result artifacts in this section were generated with raw mode disabled:

- `raw_mode.enabled = false`
- `raw_mode.stage_a_only = false`
- `rows_used_transient_raw_stage_a = 0`

Therefore, these are valid staged/burned-input comparison results, but they do **not** satisfy the later policy preference of "Stage A substrate characterization on transient raw only".

Treat the current table as a pre-policy baseline and execute the rerun checklist below for policy-aligned results.

### Changes Made During Execution

1. **Stage A → Stage B injection** (`run_stage_ab_prompt_tests.py`)
   - Stage A JSON output now prepended to Stage B prompt as explicit context
   - Token cost increased ~50% per pair (expected; Stage B now has substrate prior)

2. **Numeric confidence standardized** (both tier configs)
   - `context_confidence` required as float 0.0–1.0; text values ("medium") disallowed

3. **`particle_location` added to Stage B** (both tier configs)
   - Values: `on_field`, `in_trench`, `bridging_trench`, `on_pattern_top`, `on_structure`, `unknown`

4. **`build_stage_ab_html_report.py` cross-mount fix**
   - `_img_tag` falls back to absolute `file://` URI when relpath fails across mounts (C:\ vs UNC)

### Final Run Results (Updated Configs)

| Metric | Tier 1 | Tier 2 |
|---|---|---|
| Stage A avg confidence | 0.854 | 0.880 |
| Stage B avg confidence | 0.871 | 0.825 |
| Stage B review_required rate | 45% | 40% |
| Stage B possible_beep rate | **12.5%** | **40%** |
| Total tokens / 20 pairs | 54,130 | 65,874 (+22%) |

### Escalation Triggers Proposed (Tier 1 → Tier 2)
- `review_required = true`
- `context_confidence < 0.75`
- `particle_location` in (`in_trench`, `bridging_trench`, `on_structure`)
- `blocked_etch_evidence = moderate`

### Assessment of Results

Infrastructure (orchestration, injection, reporting) is stable and repeatable. Prompts are **not production-ready**:
- Stage A descriptions remain generic ("trench/via-like"); not yet discriminating
- No labeled ground truth; cannot measure actual precision/recall on possible_beep calls
- Tier 2's 40% possible_beep rate likely contains noise; needs manual adjudication sample to calibrate

### Next Steps
1. Manually review HTML outputs; label a sample of possible_beep conclusions (20–30 cases)
2. Identify Stage A description failures → targeted prompt improvements
3. Consider separating Stage B into parallel {morphology, blocked_etch} classifiers
4. Add quantitative Stage A features (feature pitch, fill ratio)

### Deliverables Produced
- `images/Alloy_Class/docs/SUBSTRATE_PROMPT_TIER20_RESULTS.md`
- `images/Alloy_Class/outputs/stage_ab_tests/substrate_tier_campaign_20/tier1/` — JSONL, summary, HTML
- `images/Alloy_Class/outputs/stage_ab_tests/substrate_tier_campaign_20/tier2/` — JSONL, summary, HTML

## Raw-First Rerun Checklist (Stage A Substrate Policy)

Use this checklist to regenerate Tier 1/Tier 2 under the required condition:
- Stage A on transient raw image (`--raw-image-mode --raw-strict --raw-stage-a-only`)

1) Prepare clean output roots
- Tier 1 rerun folder:
  - `images/Alloy_Class/outputs/stage_ab_tests/substrate_tier_campaign_20_raw_stageA/tier1/`
- Tier 2 rerun folder:
  - `images/Alloy_Class/outputs/stage_ab_tests/substrate_tier_campaign_20_raw_stageA/tier2/`

2) Confirm staged input folder exists and contains the fixed 20 pairs (40 images)
- `C:/temp/alloy_raw_stage/substrate_tier_campaign_20/inputs`

3) Run Tier 1 with raw-first Stage A

`c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe images/Alloy_Class/reporting/run_stage_ab_prompt_tests.py --config images/Alloy_Class/config/stage_ab_prompt_tests_substrate_tier1_v1.json --input-folder C:/temp/alloy_raw_stage/substrate_tier_campaign_20/inputs --output-folder images/Alloy_Class/outputs/stage_ab_tests/substrate_tier_campaign_20_raw_stageA/tier1 --run-id substrate_tier1_rawStageA_20260731 --raw-image-mode --raw-strict --raw-stage-a-only`

4) Run Tier 2 with raw-first Stage A

`c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe images/Alloy_Class/reporting/run_stage_ab_prompt_tests.py --config images/Alloy_Class/config/stage_ab_prompt_tests_substrate_tier2_v1.json --input-folder C:/temp/alloy_raw_stage/substrate_tier_campaign_20/inputs --output-folder images/Alloy_Class/outputs/stage_ab_tests/substrate_tier_campaign_20_raw_stageA/tier2 --run-id substrate_tier2_rawStageA_20260731 --raw-image-mode --raw-strict --raw-stage-a-only`

5) Validate raw usage in both rerun summaries before interpretation
- In each `stage_ab_summary.json`, verify:
  - `raw_mode.enabled = true`
  - `raw_mode.strict = true`
  - `raw_mode.stage_a_only = true`
  - `raw_mode.rows_used_transient_raw_stage_a > 0`
  - `raw_mode.rows_used_transient_raw_stage_b = 0`

6) Build/refresh Tier 1 vs Tier 2 review HTML
- Use existing `reporting/build_stage_ab_html_report.py` workflow against rerun folders.

7) Update final results doc with policy-aligned table
- Write to:
  - `images/Alloy_Class/docs/SUBSTRATE_PROMPT_TIER20_RESULTS.md`
- Include explicit label: `raw-stageA-only rerun`.

8) Final acceptance gate
- Only use rerun metrics for tier default/escalation recommendation.
- Keep pre-policy (non-raw) campaign metrics as historical baseline.