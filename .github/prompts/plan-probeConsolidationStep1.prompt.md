## Plan: Probe Consolidation Step 1

Consolidate the versioned generic-description probe scripts into one config-driven entrypoint that preserves v8 behavior, normalizes the local-cache pairing key, and automatically generates the HTML review report in the same run.

**Steps**
1. Confirm the canonical script location and migration shape.
1. Use [images/Alloy_Class/tools/probe_generic_description_v8.py](images/Alloy_Class/tools/probe_generic_description_v8.py) as the behavior baseline, and place the new canonical entrypoint in [images/Alloy_Class/tools/probe_generic_description.py](images/Alloy_Class/tools/probe_generic_description.py) so the repo follows the current tools layout without introducing a new root-level module.
1. Leave [probe_generic_description_v1.py](images/Alloy_Class/tools/probe_generic_description_v1.py) through [v7.py](images/Alloy_Class/tools/probe_generic_description_v7.py) in place in `tools/` -- no archive move (there is no existing archive-folder precedent in this project). The new unversioned script becomes the only one anyone runs going forward; v1-v7 remain purely as historical reference.
1. Extract prompt and runtime settings into JSON config files modeled after [images/Alloy_Class/config/stage_ab_prompt_tests_substrate_tier1_v12.json](images/Alloy_Class/config/stage_ab_prompt_tests_substrate_tier1_v12.json), with prompt version, model, token limits, and prompt text as data.
1. Keep the v8 prompt text unchanged in the first config so the refactor is behavior-preserving, and define the new script so future prompt revisions require config-only changes.
1. Reuse the current v8 execution flow for parsing, retry-on-empty response, JSONL output, and manifest CSV output; the goal is consolidation, not a behavior rewrite.
1. Port the normalized join-key helpers from [images/Alloy_Class/tools/build_beep_labeling_tranche.py](images/Alloy_Class/tools/build_beep_labeling_tranche.py) into the probe pairing path so local-cache grouping uses the same `wafer_key + inspection_time + defect_id` normalization instead of the raw inspection-time string.
1. Fix the opportunistic manifest field mismatch while touching the pairing path so the local-cache fallback reads the actual `source_filespec` column instead of the older fallback name.
1. Wire the canonical probe script to call `build_report()` directly via Python import (not a CLI subprocess call) from [images/Alloy_Class/reporting/build_generic_description_html_report.py](images/Alloy_Class/reporting/build_generic_description_html_report.py) after writing the JSONL and manifest CSV, passing the probe's own case_id-keyed manifest CSV as `pilot_manifest_csv`, so one command produces the reviewable HTML output.
1. Keep the HTML builder unchanged if possible and treat it as a reusable reporting backend, with the probe script responsible for orchestration only.
1. Add a final status print that clearly points to the JSONL, manifest CSV, and generated HTML paths.
1. Verify the consolidated script against a known good local-cache batch, ideally the same 400-case slice used for v8, and compare outputs against the reference run aside from timestamps and path-format churn.
1. Search for references to the retired versioned scripts before moving them so archival does not break any docs or automation.

**Relevant files**
- [images/Alloy_Class/tools/probe_generic_description_v8.py](images/Alloy_Class/tools/probe_generic_description_v8.py) - baseline behavior, CLI, local-cache selection, retry logic, and output contract.
- [images/Alloy_Class/tools/probe_generic_description_v1.py](images/Alloy_Class/tools/probe_generic_description_v1.py) through [v7.py](images/Alloy_Class/tools/probe_generic_description_v7.py) - scripts to archive after consolidation.
- [images/Alloy_Class/tools/build_beep_labeling_tranche.py](images/Alloy_Class/tools/build_beep_labeling_tranche.py) - source for the normalized join-key helpers.
- [images/Alloy_Class/reporting/build_generic_description_html_report.py](images/Alloy_Class/reporting/build_generic_description_html_report.py) - existing schema-agnostic HTML report builder to reuse unchanged.
- [images/Alloy_Class/config/stage_ab_prompt_tests_substrate_tier1_v12.json](images/Alloy_Class/config/stage_ab_prompt_tests_substrate_tier1_v12.json) - config shape precedent for prompt/model/token settings.
- [images/Alloy_Class/docs/HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md](images/Alloy_Class/docs/HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md) - source handoff and scope boundaries for Step 1.

**Verification**
1. Run the consolidated probe on the reference local-cache slice and confirm it emits JSONL, manifest CSV, and HTML in one invocation.
1. Diff the new JSONL and manifest CSV against the v8 reference run, ignoring timestamp-only differences, to confirm the refactor preserved behavior.
1. Confirm the HTML file opens and reflects the same cases and attributes as the prior manual two-step flow.
1. Grep for the archived script names before and after the move to confirm only intentional references remain.

**Decisions**
- Scope is Step 1 only: consolidation, config externalization, join-key normalization, and one-command HTML generation.
- Prompt content stays unchanged for the first config revision.
- Step 2 and Step 3 remain deferred until the Step 1 output shape is stable.
- The new entrypoint should live under `tools/` unless a later folder-taxonomy decision explicitly moves it.

**Resolved decisions (previously open)**
1. Archive location: resolved as option (b) -- no archive folder. `images/Alloy_Class/OLD/` does not exist and has no precedent for this use; v1-v7 stay in `tools/` untouched as historical reference, and Step 3 above reflects this.
2. HTML-builder integration: resolved to call `build_report()` via direct Python import rather than the CLI, avoiding the CLI's `--pilot-manifest-csv` required-arg friction; Step 8 above reflects this.
