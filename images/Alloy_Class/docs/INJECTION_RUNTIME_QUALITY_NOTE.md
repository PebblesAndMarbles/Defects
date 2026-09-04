# Phase 1 Input Injection, Runtime, and Quality Note

Date: 2026-07-26
Scope: Current behavior only (no execution changes in this note)

## 1) Does DEFECT_COORDINATES_EXTENDED_IMAGES.csv already contain image locations?

Yes.

- The pipeline reads LOCAL_IMAGE_FILE from:
  - outputs/defects/DEFECT_COORDINATES_EXTENDED_IMAGES.csv
- Current pair selection in the orchestrator uses that field directly and validates file existence.

So your premise is correct: random selection can be driven from this CSV alone.

## 2) Why current selection is not random

Current run orchestration is deterministic, not random.

In tools/run_raw_stage_batch.py:
- Rows are grouped by (WAFER_KEY, INSPECTION_TIME, DEFECT_ID)
- Only IMAGE_ID 2 and 3 are used (BF/DF pair requirement)
- Optional label filtering is applied by filename token (_SMP_ / _BEEP_)
- Keys are sorted reverse and the first N valid pairs are selected

This means selection behavior is:
- Pair-safe: yes
- Reproducible: yes
- Random: no

## 3) What is currently being injected into classify

Classification path: pipelines/classify_phase1_batch.py

### 3.1 Prompt injection

Base prompt comes from config/phase1_settings.json:
- prompt
- prompt_version

Per image call:
- alloy.core.llm.image(...)
- max_completion_tokens = 500

Optional appended context:
- If size metadata exists for the image, the script appends a text suffix:
  - "Additional defect metrology context from coordinates DB (use as supporting evidence, do not overfit): ..."
- Source of appended fields is config/defect_size_metadata.csv keyed by image_name.
- Included fields (when present): SIZE_X, SIZE_Y, SIZE_D, AREA, MANUAL_OPTICAL_CLASS

This is the main "input injection" beyond the base prompt.

### 3.2 Image content injection mode

When raw mode is enabled:
- Burned image name is mapped to manifest row via LOCAL_IMAGE_FILE basename
- IMAGE_FILESPEC and QUERY_SITE/SITE are used to transiently download raw image
- Inference uses raw image path instead of burned image
- In strict mode, failure to get raw causes row failure

This changes image input content itself (not just prompt text).

### 3.3 Pairing/selection constraints injected into classify run

The orchestrator rewrites run settings for classify:
- input_folder -> local staged input folder
- output_folder -> run-scoped structured output
- max_pairs -> CLI-selected value
- require_bf_df_pairs -> true

This is configuration injection at runtime (not model prompt text), but it strongly impacts throughput and sample mix.

## 4) What is currently being injected into caption

Caption path: pipelines/caption_phase1_batch.py

Per image call:
- alloy.core.llm.image(...)
- model default: gpt-5.4
- max_completion_tokens = 500

Prompt:
- Single default freeform caption prompt (SEM expert captioning instructions)
- No metrology append in this script
- No schema constraint in this script

So caption injection is currently:
- Base caption prompt only
- No extra DB metadata append

## 5) Why runtime can feel slower now

Runtime now includes more than just classify/caption model latency:

- Selection phase scans CSV rows and checks LOCAL_IMAGE_FILE existence on UNC paths
- Pair construction and label filtering
- Copy burned inputs and local staging copy
- Raw transient download + deletion lifecycle
- Classify call(s)
- Caption call(s)
- HTML assembly

Based on recent run summaries, select_pairs is a meaningful runtime share. That is expected with full-manifest UNC existence checks.

## 6) Random-from-CSV option: expected impact

### 6.1 Feasibility

Fully feasible with current data. No new source is required.

### 6.2 Runtime impact (expected)

Potentially faster selection if implemented as:
- streaming/reservoir sample of valid BF/DF groups
- early stop once N valid pairs found
- optional pre-filter by _SMP_ token before costly checks

Potentially slower if implemented as:
- randomize all rows first but still perform full existence checks on entire manifest

### 6.3 Quality impact (expected)

Random selection changes evaluation distribution.

Likely benefits:
- less recency/order bias
- broader morphology/site/time coverage (if stratified)

Likely risks:
- run-to-run variance increases
- harder direct comparison between prompt versions unless seed is fixed

Recommended practice for quality comparisons:
- fixed RNG seed
- frozen sampled pair list per experiment set
- optional stratification by class tokens/SMP-BEEP/time windows

## 7) Current injection inventory (quick checklist)

Classify currently injects:
- Base classifier prompt from phase1_settings.json
- Optional per-image metrology text append from defect_size_metadata.csv
- Raw-vs-burned image choice in raw mode
- Runtime settings overrides (max_pairs, require pairs, run-scoped IO)

Caption currently injects:
- Base freeform caption prompt only

Orchestrator currently injects:
- Deterministic pair selection policy
- Label filter policy (SMP/BEEP/ALL)
- Local staging + output roots
- Strict raw behavior flag

## 8) Answer to your specific question

- Yes, the extended defect CSV is sufficient to drive random selection.
- Current pipeline is deterministic by design, not random.
- The main prompt/context injection affecting classify quality/runtime is optional metrology append plus raw-image substitution mode.
- Caption currently uses only its base prompt and model call settings.
