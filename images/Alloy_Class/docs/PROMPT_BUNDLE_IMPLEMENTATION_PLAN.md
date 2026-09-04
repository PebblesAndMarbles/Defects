# Prompt Bundle Implementation Plan

## Goal

Make each benchmark run write a run-local prompt bundle that captures the exact Stage A and Stage B prompt text, the prompt version identifiers, and the execution flags that affect what the model actually sees.

This is intended to make prompt-engineering experiments auditable run by run, so FP/FN changes can be traced back to the precise prompt and stage-configuration state used for that run.

## Why this is needed

Today, the benchmark run folders already contain:

- the staged input pairs under `inputs/`
- the run manifest
- the stage A/B results JSONL
- the scoring outputs

But the exact prompt text is still only stored in the checked-in config file, and the run folder does not contain a dedicated prompt artifact. That makes it harder to answer questions like:

- Which exact prompt text was used for this run?
- Was Stage A BF-only or BF+DF?
- Was Stage B single-image or multi-image?
- Did the run use raw FTP re-downloads, and was raw fallback allowed?
- Which prompt version produced the observed FP/FN behavior?

## Proposed artifact

Write a new file into each run folder:

- `prompt_bundle.json`

Optional companion file for easy reading:

- `prompt_bundle.txt`

The JSON file should be the source of truth. The text file is only for quick inspection.

## Recommended contents

The JSON should include at least:

- `run_id`
- `created_at_utc`
- `config_path`
- `config_name`
- `suite_name`
- `model_name`
- `stage_a_prompt_version`
- `stage_b_prompt_version`
- `stage_a_prompt`
- `stage_b_prompt`
- `stage_a_brightfield_only`
- `stage_b_multi_image`
- `raw_image_mode`
- `raw_strict`
- `raw_stage_a_only`
- `raw_keep_temp`
- `input_folder`
- `output_folder`
- `run_manifest_path`
- `notes`

If available from the config or run context, also include:

- `max_completion_tokens`
- `max_pairs`
- `raw_manifest_csv`
- `raw_temp_dir`
- `raw_app_name`
- `raw_technology`

## Suggested structure

The bundle should preserve both the exact prompt text and a short explanation of the logic.

Example shape:

```json
{
  "run_id": "benchmark_nbc52_tier1_v3_stageA_BF_only_stageB_multi_v2",
  "created_at_utc": "2026-08-11T17:23:41.142312+00:00",
  "config_path": ".../stage_ab_prompt_tests_substrate_tier1_v3.json",
  "suite_name": "stage_ab_substrate_tier1_v3",
  "model_name": "gpt-5.4-mini",
  "stage_a": {
    "prompt_version": "stageA_substrate_tier1_v1",
    "prompt": "..."
  },
  "stage_b": {
    "prompt_version": "stageB_substrate_tier1_v3",
    "prompt": "..."
  },
  "execution_flags": {
    "raw_image_mode": true,
    "raw_strict": false,
    "raw_stage_a_only": false,
    "stage_a_brightfield_only": true,
    "stage_b_multi_image": true
  },
  "paths": {
    "input_folder": "...",
    "output_folder": "...",
    "run_manifest_path": "..."
  },
  "notes": [
    "Stage A is BF-only in this run.",
    "Stage B uses BF+DF multi-image submission.",
    "Raw FTP download fallback was allowed for failures."
  ]
}
```

## Implementation points

### 1. Build the bundle from the loaded config and CLI/runtime flags

Add a small helper in `images/Alloy_Class/reporting/run_stage_ab_prompt_tests.py` that constructs a prompt bundle dictionary after config load and argument parsing.

That helper should pull:

- prompt versions and prompt text from the config JSON
- run-level flags from the current arguments
- config metadata like `suite_name`, `models`, `max_completion_tokens`, and `max_pairs`
- the final resolved paths for the run folder and config file

### 2. Write the bundle once per run

Write `prompt_bundle.json` into the run output folder before the first model call.

If `prompt_bundle.txt` is also produced, write it from the same dictionary so the text version cannot drift from the JSON.

### 3. Make the bundle part of run provenance

Record the bundle path in the run manifest, or at minimum ensure the run manifest references it indirectly.

Recommended addition to `run_manifest.json`:

- `prompt_bundle_path`

### 4. Keep the prompt bundle separate from per-row results

Do not duplicate the full prompt text into every JSONL row.

Per-row results should keep only:

- prompt version ids
- the effective inference image paths
- the output JSON payloads
- any row-specific raw-image metadata

The bundle should be the single run-level source of prompt text.

## Raw-image policy recommendation

If the goal is to ensure the model only sees raw FTP-redownloaded images, add a strict mode path alongside the bundle work.

Recommended behavior:

- `raw_image_mode = true`
- `raw_strict = true`
- if any raw download fails, fail the run instead of falling back to staged inputs

If fallback remains allowed, record that clearly in the prompt bundle and manifest so the run cannot be misread later.

## Suggested code changes

Minimal slice:

- `run_stage_ab_prompt_tests.py`
  - add `build_prompt_bundle(...)`
  - add `write_prompt_bundle(...)`
  - include `prompt_bundle_path` in the manifest update
- `run_benchmark_vlm.py`
  - if it owns the run folder setup, ensure it forwards any needed manifest fields
- optional docs update in `PROMPT_ITERATION_REGISTRY.md`
  - note that `prompt_bundle.json` is the run-local prompt provenance artifact

## Validation plan

After implementation, verify one benchmark run produces:

- `run_manifest.json`
- `prompt_bundle.json`
- `stage_ab_results/stage_ab_results.jsonl`
- `stage_ab_results/stage_ab_summary.json`
- scoring outputs

Then confirm the bundle contains:

- exact Stage A and Stage B prompt text
- prompt version identifiers
- the BF-only / multi-image flags
- the raw-image mode flags

## Acceptance criteria

- Each finalized benchmark run writes a run-local `prompt_bundle.json`.
- The bundle contains the exact prompt text used for the run.
- The bundle records the stage and raw-image flags that affect model input.
- The run manifest references the prompt bundle path.
- The registry can point to the run folder and rely on the bundle for prompt provenance.
- A reviewer can reconstruct the prompt-engineering state of any run without opening the source config file.

## Open decision

Decide whether the raw policy should default to strict fail-closed behavior for future benchmark runs.

If yes, that should be a separate small change, because it changes run semantics and should be validated independently from the prompt-bundle addition.
