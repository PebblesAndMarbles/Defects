---
session_id: 2026-08-26_002
title: Alloy VLM FN Feature-Perception Probe Checkpoint
date: 2026-08-26
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 5
triggered_by: manual-checkpoint
status: complete
original_goal: Determine, via a small and cheap but verifiable ablation on the 5 known Alloy VLM false-negative cases, whether the Stage A/Stage B pipeline architecture itself (context dilution, JSON-contract overhead) is suppressing detections that the same underlying model (claude-sonnet-4-6) can otherwise perceive when prompted directly on individual images.
---

## Original Goal
This was a same-day follow-on to `2026-08-26_001`. The user asked me to review that
prior checkpoint plus `images\Alloy_Class\docs\v12_post_mortem.md` (a strategic ROI
analysis of next options for the Alloy VLM defect classifier, produced by an external
chat session where the user had engineered a prompt against individual images using
the same model, claude-sonnet-4-6). The user suspected the Stage A (substrate scout)
-> Stage B (defect classifier) architecture might be fundamentally flawed rather than
just needing more prompt engineering, since Stage A context didn't seem to add value
to Stage B. They asked for next steps with low VLM-submission load but verifiable,
specifically: individual-image tests that determine whether the VLM can be made to
observe specific features that an external chat session could correctly see and
process.

## Discovery / Investigation
- Explored the Alloy Class VLM pipeline architecture (subagent + direct file reads):
  Stage A (BF-only substrate scout, outputs JSON) -> its JSON output is serialized
  into Stage B's prompt as context -> Stage B (BF or BF+DF pair, ~15+ guidance
  blocks, strict JSON contract requiring all keys present and confidence as numeric
  float) -> scorer.
- Identified the 5 known false-negative cases from the v12 offset-surface-lines
  15-pair benchmark (ground truth `possible_beep`, pipeline called `particle`):
  `BMK_0050` (wafer 8487115/defect 916), `BMK_0029` (8533506/1032), `BMK_0009`
  (8438048/3110), `BMK_0005` (8441579/3139), `BMK_0001` (8425615/10911, eval split).
  All 10 BF/DF image files confirmed present on disk.
- Confirmed `outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv` has
  `SIZE_X`/`SIZE_Y`/`SIZE_D`/`AREA` + `WAFER_X`/`Y_MM` (a crop-based fix would be
  feasible later if needed, not modified this session).
- User pointed to `images\Alloy_Class\docs\iGPT_VLM_Chat1.md` and `Chat2.md` as the
  saved "external chat session" transcript. On inspection these turned out to be
  earlier v10-era passdown/analysis docs (benchmark scores, a BF/DF image-routing
  bug already resolved per the prior checkpoint) rather than a verbatim per-image
  "I can see X" visual transcript. `v12_post_mortem.md` itself appears to be the
  actual output of the individual-image prompt-engineering session the user
  described.
- Reviewed existing tooling patterns in
  `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` (`_call_image()`
  supporting both single-image and multi-image `[BF, DF]` submission,
  `_extract_json_payload()` for graceful free-text/JSON handling,
  `_load_env_from_supported_locations()`, `_load_image_manifest_index()`,
  `_download_raw_image_to_temp()` for raw/unburned image fallback via SecureFTP,
  `DEFAULT_RAW_MANIFEST`) and `images\Alloy_Class\tests\smoke_test_one_image.py`
  (minimal single-image call pattern) to model the new diagnostic script on.

## Completed Tasks
- [x] Asked 3 clarifying questions before planning: (1) whether the external
      session used the same images as the pipeline -- user confirmed same
      burned/staged images (slightly lower quality than "total substrate context"
      but no obstruction of the defect itself); (2) whether the user had the
      actual external prompt/transcript -- user pointed to `iGPT_VLM_Chat1.md` /
      `Chat2.md`, which turned out not to contain that verbatim transcript; (3)
      scope of FN targets -- user chose just the 5 known FN cases (declined
      broadening to true-positive controls).
- [x] Designed a "FN Feature-Perception Probe" plan (Phase 0 baseline / Phase 1
      isolated feature-probe ablation / Phase 2 interpret-and-decide) and saved it
      to `/memories/session/plan.md`; got user sign-off before building anything.
- [x] Created `images\Alloy_Class\tools\probe_fn_feature_perception.py`: an ad hoc,
      throwaway diagnostic script (not wired into the scored benchmark pipeline)
      that, for each of the 5 hardcoded FN cases, submits the BF+DF pair directly
      via the same `_call_image()` runtime helper imported from
      `reporting\run_stage_ab_prompt_tests.py`, using two variants: p1 (free-text
      description of the defect-to-wall junction zone, no Stage A context, no JSON
      contract) and p2 (narrow yes/no/unclear + describe question naming the
      specific missed feature per case). A p3 variant (raw/unburned image via
      SecureFTP, reusing `DEFAULT_RAW_MANIFEST` / `_download_raw_image_to_temp` /
      `_load_image_manifest_index`) was implemented but never exercised.
- [x] Verified the script compiles cleanly (`py_compile`) and that `--help`
      resolves all imports without executing any VLM calls.
- [x] Verified all 10 BF/DF image files referenced by the 5 hardcoded FN cases
      exist on disk (dry-run path check).
- [x] Phase 0: pulled the 5 FN rows verbatim (exact ground truth, pipeline
      classification, evidence-check fields, full rationale text) from
      `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v12_compare\stage_ab_results\benchmark_scored_rows.csv`
      and saved as the zero-new-calls baseline to
      `images\Alloy_Class\outputs\probes\fn_baseline_v12.json`.
- [x] Resolved an auth question before running real VLM calls: confirmed via
      `C:\Users\tbatson\My Programs\SQLPathFinder3\Python3\alloy\core\config.py`
      that `ALLOY_API_KEY="demo-sandbox-key-12345"` is a hardcoded generic default
      baked into the installed `alloy` package (not a per-user secret), so no env
      var setup was needed, per user instruction to verify and use it directly.
- [x] Ran a 1-call smoke test (`BMK_0050`, variant p1); succeeded and returned a
      response describing a wall-boundary interruption and material occupying the
      trench interior -- directly relevant to the missed BEEP signal.
- [x] Ran the full Phase 1 probe: 10 primary calls (5 cases x p1, p2). 4 of the 10
      came back as empty responses on first attempt (see BUG-001).
- [x] Retried the 4 empty cases individually: `BMK_0050`/p1 succeeded on retry #2;
      `BMK_0029`/p1 succeeded on retry #3; `BMK_0009`/p2 succeeded on retry #2;
      `BMK_0050`/p2 stayed empty across 4 consecutive attempts (unresolved). Total
      VLM calls across the session: 1 (smoke) + 10 (primary) + 6 (retries) = 17.
- [x] Consolidated all results (best/non-empty response per case+variant, with
      attempt counts) into
      `images\Alloy_Class\outputs\probes\fn_feature_probe_consolidated.jsonl`, and
      cleaned up scratch/retry JSONL files.
- [x] Analyzed the consolidated results against the Phase 0 baseline rationale.
- [x] Appended an "Addendum 2026-08-26" section directly to the existing
      `images\Alloy_Class\docs\v12_post_mortem.md` (not a new file) documenting the
      probe methodology, per-case findings table, the empty-response reliability
      anomaly, the conclusion, and a revised ROI/priority recommendation.
- [x] Updated `/memories/session/plan.md` with a "STATUS: Phase 0 + Phase 1
      COMPLETE" section summarizing outcomes and what's still open.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\tools\probe_fn_feature_perception.py` | Created | Ad hoc diagnostic script; throwaway, not wired into the scored benchmark pipeline; p1/p2 exercised, p3 (raw image via SecureFTP) implemented but unused |
| `images\Alloy_Class\outputs\probes\fn_baseline_v12.json` | Created | Phase 0 baseline: exact ground truth + pipeline rationale for the 5 FN cases |
| `images\Alloy_Class\outputs\probes\fn_feature_probe_consolidated.jsonl` | Created | Phase 1 consolidated probe results (best response per case/variant, with attempt counts) |
| `images\Alloy_Class\docs\v12_post_mortem.md` | Modified | Appended "Addendum 2026-08-26" section with probe methodology, findings table, and revised ROI/priority recommendation |
| `agents_history\sessions\2026-08-26_002_alloy-vlm-fn-feature-perception-probe-checkpoint.md` | Created | This checkpoint log |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `agents_history\sessions\2026-08-26_001_alloy-vlm-v11-v12-benchmark-comparison-checkpoint.md` | Prior checkpoint, starting context for this session | No |
| `images\Alloy_Class\docs\iGPT_VLM_Chat1.md` | Inspected per user pointer; turned out to be a v10-era passdown doc, not the expected per-image visual transcript | No |
| `images\Alloy_Class\docs\iGPT_VLM_Chat2.md` | Same as above | No |
| `images\Alloy_Class\docs\v10_Results_iGPT.md` | Reviewed for additional v10-era context | No |
| `images\Alloy_Class\docs\ALLOY_UPDATES.md` | Reviewed for architecture/folder conventions | No |
| `images\Alloy_Class\docs\PROJECT_STRUCTURE.md` | Reviewed for architecture/folder conventions | No |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v11.json` | Reviewed for current Stage A/B prompt content | No |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v12.json` | Reviewed for current Stage A/B prompt content | No |
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | Reviewed and reused (`_call_image`, `_extract_json_payload`, `_load_env_from_supported_locations`, `_load_image_manifest_index`, `_download_raw_image_to_temp`, `DEFAULT_RAW_MANIFEST`, `DEFAULT_GAJT_DLL_SEARCH_PATHS`) | No |
| `images\Alloy_Class\tests\smoke_test_one_image.py` | Reviewed as the minimal single-image call pattern reference | No |
| `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v12_compare\stage_ab_results\benchmark_scored_rows.csv` | Source of the Phase 0 baseline (read-only) | No |
| `outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv` | Confirmed column set (SIZE_X/Y/D/AREA, WAFER_X/Y_MM) for potential future crop work | No |
| `C:\Users\tbatson\My Programs\SQLPathFinder3\Python3\alloy\core\config.py` | Inspected to confirm `ALLOY_API_KEY` is a hardcoded generic default, not a per-user secret | No |

## Bugs Encountered
### BUG-001: Intermittent empty VLM responses (unresolved)
- **Status:** Unresolved
- **File(s):** `images\Alloy_Class\tools\probe_fn_feature_perception.py` (surfaced the issue; likely lives in the shared `_call_image()` runtime path in `reporting\run_stage_ab_prompt_tests.py` or upstream Alloy client)
- **Root Cause:** Unknown. ~40% of first-attempt calls in the Phase 1 batch returned an empty `response_text` with no error and estimated `completion_tokens=1`. Most resolved on retry (1-2 attempts).
- **Fix Applied:** None (workaround only) -- retried failed cases individually. `BMK_0050`/p2 (the narrow feature-question variant, asking about "narrow wall continuity or a concave terminus at the trench-comparator junction") returned empty across 4 consecutive identical attempts (same prompt, same images) -- not simple transient noise, may indicate a systematic issue with that specific prompt/image/model combination.
- **Notes:** Also noted a related process-level issue, not a VLM bug: earlier in the session, a terminal command running the full 10-call batch appeared to produce no output. Root cause was a second, unrelated terminal command issued before the first one finished, which interrupted (`KeyboardInterrupt`) the in-progress Python process. Lesson: do not issue a second sync terminal command while a long-running VLM batch script from a prior call may still be finishing.

## Excursions / Scope Creep Discovered
- Terminal history in this session shows an unrelated command that rewrote
  `BE_QUERY_FILES\DEFECT_COORDINATES_RECLASS_LOG.csv` (a reclass-log stale-row
  cleanup script). This was **not** run as part of this session's tasked work and
  is flagged as out-of-scope/unattributed terminal history rather than an
  accomplishment of this session.

## Open Threads
- [ ] Design and implement the trimmed/split Stage B prompt (fewer simultaneous
      guidance blocks and/or less injected Stage A context, or a two-step
      describe-then-classify call structure) and validate it against the same 5
      FN cases before scaling to the full 15-pair benchmark.
- [ ] Investigate BUG-001 (`BMK_0050`/p2 persistent empty-response anomaly and the
      broader ~40% first-attempt empty-response rate) as a contract-reliability
      issue independent of the FN root-cause question.
- [ ] Variant p3 (raw/unburned image fidelity control via SecureFTP) was
      implemented in `probe_fn_feature_perception.py` but never exercised --
      available as a fast follow if image fidelity ever becomes a live hypothesis
      again.
- [ ] `BMK_0009`'s "crescent-shaped" feature wording did not land in the p2 probe;
      consider re-probing this one case with different/looser feature phrasing
      before concluding it's a true non-perception case.
- [ ] THREAD-001 remains open: `build_benchmark_candidates.py` still not built.
- [ ] THREAD-002 remains open: manifest metadata backfill lag.
- [ ] THREAD-006 remains open: `bc` detection gap.
- [ ] THREAD-007 remains open: Stage A confounder language may still suppress
      `isl` detection.
- [ ] THREAD-008 remains deferred: `sr` detection ceiling.
- [ ] THREAD-009 remains open: `BMK_0037` relabeling question.

## Key Decisions Made
- Scope the diagnostic probe to only the 5 known FN cases (not the broader 15/20
  -pair sets), per explicit user choice, to keep VLM-submission load low.
- Build the probe as a throwaway ad hoc script in `tools\`, deliberately not
  integrated into the scored benchmark/contract pipeline.
- No changes made to production Stage A/B config files (v11/v12) in this session;
  any prompt/architecture changes are deferred to a follow-on phase pending this
  probe's findings.
- Record probe results as an addendum to the existing `v12_post_mortem.md` rather
  than creating a new standalone markdown file, per doc-creation constraints.
- Treat the hardcoded `demo-sandbox-key-12345` Alloy API key as safe to reuse
  directly (per explicit user instruction and direct inspection of the installed
  package), rather than requesting or handling any real secret.
- **What was rejected:** broadening the probe scope to include true-positive
  control cases in this pass -- user explicitly declined for now to keep the
  probe minimal.
- **Result reverses prior priority order:** this probe's finding (see below)
  de-prioritizes Option 5 (model upgrade) and Option 2/4 (crop/FFT preprocessing)
  from `v12_post_mortem.md`'s original ROI matrix as first moves, and promotes a
  lighter version of Option 1 (trim Stage B's prompt / split into a
  describe-then-classify two-step call) as the next concrete step, to be
  validated first on these same 5 cases before touching the full 15-pair
  benchmark.

## Key Finding / Result
4 of 5 known FN cases clearly surfaced the specific missed BEEP-indicating feature
(wall-boundary interruption, material intruding into/occupying the trench interior)
when the SAME model was given the SAME images but with Stage A context and the JSON
evidence-check contract stripped out and replaced with either a plain free-text
description prompt or a narrow targeted feature question:
- `BMK_0050`: pipeline said "uniformly dark... no wall continuity"; isolated probe
  said "boundary is interrupted by a bright protrusion... bright material visibly
  occupies part of the trench interior."
- `BMK_0029`: pipeline said "normally shaped... clear gap"; isolated free-text (p1)
  agreed with the pipeline, but the targeted p2 question surfaced it: "Yes. A
  distinct dark wedge-like void is visible... flanking the defect-wall junction."
- `BMK_0005`: pipeline said "clean particle contact... no wall continuity";
  isolated probe said "wall... is locally irregular and interrupted/obscured...
  extends slightly into the dark trench interior."
- `BMK_0001`: pipeline said "clean particle-to-trench contact"; isolated probe
  (both variants) said "the dark trench/line is interrupted... reappears on the
  right."
- `BMK_0009`: mixed/partial -- free-text noted a continuity anomaly, but the
  specific "crescent-shaped" guessed wording was answered "no" (likely a
  vocabulary mismatch in the probe's guessed feature description, not necessarily
  true non-perception).

Conclusion: this looks like a prompt/architecture framing-and-overhead problem
(Stage A context dilution, JSON-contract verbosity burying the salient
instruction) rather than a fundamental visual-perception ceiling of
claude-sonnet-4-6.

## Recommended Re-Entry
**Load these files for context:**
- `images\Alloy_Class\docs\v12_post_mortem.md` (includes the new Addendum 2026-08-26 section)
- `images\Alloy_Class\outputs\probes\fn_baseline_v12.json`
- `images\Alloy_Class\outputs\probes\fn_feature_probe_consolidated.jsonl`
- `images\Alloy_Class\tools\probe_fn_feature_perception.py`
- `/memories/session/plan.md` (session memory scope)

**Suggested starting prompt:**
> "Continue from the FN feature-perception probe checkpoint: design a trimmed or
> two-step Stage B prompt that removes the Stage A context dilution / JSON-contract
> overhead identified as the likely root cause, and validate it against the same 5
> known FN cases (BMK_0050, BMK_0029, BMK_0009, BMK_0005, BMK_0001) before scaling
> to the full 15-pair benchmark."

## Notes for Future Agent
- `images\Alloy_Class\docs\iGPT_VLM_Chat1.md` / `Chat2.md` are v10-era passdown docs,
  not a verbatim per-image visual transcript -- don't re-chase these looking for
  that transcript; `v12_post_mortem.md` is the actual output of that external
  session.
- `probe_fn_feature_perception.py` is intentionally a throwaway script outside the
  scored benchmark contract -- do not wire it into `run_benchmark_vlm.py` /
  `score_benchmark_run.py` without a deliberate decision to do so.
- The empty-response anomaly (BUG-001) is intermittent and not fully understood;
  budget for retries when running batches of VLM calls, and do not launch a second
  terminal command while a prior VLM batch script may still be finishing.
- The BE_QUERY_FILES/DEFECT_COORDINATES_RECLASS_LOG.csv rewrite visible in terminal
  history is unrelated to this session's work -- do not attribute it here without
  separate confirmation.
