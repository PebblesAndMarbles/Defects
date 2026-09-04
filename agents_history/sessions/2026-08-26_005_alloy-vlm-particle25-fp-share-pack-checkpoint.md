---
session_id: 2026-08-26_005
title: Alloy VLM Particle-25 FP Share Pack Checkpoint
date: 2026-08-26
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: GPT-5.4 mini
triggered_by: manual-checkpoint
status: complete
original_goal: Build, run, score, and package a 25-case particle-only v13 describe-then-classify validation, then generate shareable artifacts for follow-on categorization of the false positives.
retroactive: true
logged_date: 2026-08-27
---

## Original Goal
The user asked to expand the earlier v13 work into a larger particle-only validation, score it, and then produce a shareable artifact for a follow-on diagnostic pass. The immediate follow-up became a request to package the 21 false positives so another agent could categorize them by pattern before any broader promotion decision.

## Discovery / Investigation
- Reviewed `images\Alloy_Class\docs\iGPT_v13_next_step.md` and the completed particle-25 run outputs to determine the next concrete validation step.
- Confirmed the v13 production config still capped the earlier benchmark path at `max_pairs: 15`, which explained why the first launch printed `[1/15]` even though the input list contained 25 rows.
- Created a dedicated 25-pair config variant: `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v13_particle25.json`.
- Launched the particle-only 25-case run with the describe-then-classify architecture and scored the resulting output against the frozen benchmark table.
- Parsed the raw JSONL output to extract `stage_b_call1_observation` text, which is the Call 1 observation field requested for the follow-on review.
- Generated two shareable diagnostics:
  - an 8-row excerpt CSV for the A/B/C sampling mix requested in `iGPT_v13_FN_plan.md`
  - a full 21-FP share pack in JSONL form for Option B handoff

## Completed Tasks
- [x] Read the FN plan in `images\Alloy_Class\docs\iGPT_v13_FN_plan.md` and the particle-25 scoring artifacts.
- [x] Built the dedicated 25-pair config so the particle-only run would not truncate at the older 15-pair cap.
- [x] Ran the 25-case particle-only describe-then-classify benchmark to completion in `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\`.
- [x] Scored the run successfully with `images\Alloy_Class\tools\score_benchmark_run.py`.
- [x] Confirmed the run-level summary: 25 scored pairs, 21 particle false positives, 4 correct particle calls, and a high particle FP rate on this slice.
- [x] Generated `images\Alloy_Class\artifacts\iGPT_v13_FN_plan_rows.csv` with 8 requested rows, including Call 1 observation text.
- [x] Generated `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\scoring\benchmark_particle25_v13_fp21_share.jsonl` plus the companion markdown handoff for the full 21 FP set.
- [x] Verified that the BMK_0034 row confusion was a visual scan issue, not an actual missing `vlm_coarse_class` field in the CSV.
- [x] Saved the formal checkpoint log and prepared to reconcile `index.md` and `file_map.md` so the session registry stays synchronized.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `agents_history\sessions\2026-08-26_005_alloy-vlm-particle25-fp-share-pack-checkpoint.md` | Created | Formal checkpoint for the particle-25 validation and share-pack work |
| `images\Alloy_Class\docs\iGPT_v13_next_step.md` | Modified | Reframed the next step to a 25-case particle-only validation |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v13_particle25.json` | Created | Dedicated 25-pair v13 config variant with `max_pairs: 25` |
| `images\Alloy_Class\artifacts\iGPT_v13_FN_plan_rows.csv` | Created | 8-row excerpt for the A/B/C diagnostic mix requested by the FN plan |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\stage_ab_results.jsonl` | Created | Completed 25-case raw run output consumed for scoring and Call 1 extraction |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\stage_ab_summary.json` | Created | Run summary artifact from the Stage A/B runner |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\scoring\benchmark_scored_rows.csv` | Created | Per-row scored output for the particle-25 run |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\scoring\benchmark_score_summary.json` | Created | Aggregate scored summary for the particle-25 run |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\scoring\benchmark_particle25_v13_fp21_share.jsonl` | Created | Shareable JSONL subset containing all 21 false-positive rows plus Call 1 observations |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\scoring\benchmark_particle25_v13_fp21_share.md` | Created | Human-readable handoff explaining the FP share pack |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify\benchmark_id_lookup.csv` | Created | Run-local lookup file used by the scorer |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\docs\iGPT_v13_FN_plan.md` | Source of the step-1 diagnostic request and the A/B/C case categories | No |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\scoring\benchmark_scored_rows.csv` | Source table used to select the 8-row excerpt and rank the false positives | No |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\stage_ab_results.jsonl` | Raw JSONL parsed to extract `stage_b_call1_observation` | No |
| `images\Alloy_Class\tools\run_benchmark_vlm.py` | Verified runner behavior and pair-count handling | No |
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | Verified direct runner behavior and stage_b output structure | No |
| `images\Alloy_Class\tools\score_benchmark_run.py` | Used to score the completed run | No |
| `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv` | Frozen benchmark ground truth used for scoring | No |
| `images\Alloy_Class\artifacts\benchmark_pairs_particle25.csv` | Particle-only pair list used for the run | No |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\` | Completed run folder, used to extract observations and scoring artifacts | No |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify\` | Wrapper folder used for the benchmark lookup CSV | No |

## Bugs Encountered
### BUG-001: Earlier v13 config still capped the run at 15 pairs
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v13.json`, `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v13_particle25.json`
- **Root Cause:** Reusing the original v13 config caused the runner to slice the 25-row input list down to 15 because `max_pairs` was still set to 15.
- **Fix Applied:** Created a dedicated particle-25 config with `max_pairs: 25`.
- **Notes:** This explained the `[1/15]` console output even though the input list correctly printed `pair_list_rows=25`.

### BUG-002: UNC output path typo in the rerun command
- **Status:** Resolved
- **File(s):** Terminal command for `run_stage_ab_prompt_tests.py`
- **Root Cause:** The first rerun used a duplicated `ORAnalysis$` segment in the output path, causing the runner to fail while creating the output folder tree.
- **Fix Applied:** Reran with the corrected UNC path.
- **Notes:** This was a command-entry error, not a code defect.

### BUG-003: Share-pack generation script f-string quoting error
- **Status:** Resolved
- **File(s):** Terminal command used to generate `benchmark_particle25_v13_fp21_share.jsonl`
- **Root Cause:** The first attempt to write the share-pack script used nested f-strings with conflicting quotes.
- **Fix Applied:** Reran the generator with simpler string concatenation.
- **Notes:** No data issue; only the wrapper script needed correction.

## Excursions / Scope Creep Discovered
- The initial attempt to inspect the particle-25 run looked like a possible malformed CSV row, but the BMK_0034 row was valid; the confusion came from line-length truncation and dense text columns.
- The session expanded from the original 25-case scoring task into a share-pack generation step because the user wanted an artifact that another agent could consume immediately for Step 1 categorization.

## Open Threads
- [ ] THREAD-011 remains open: v13 describe-then-classify is validated but not promoted to the production default.
- [ ] THREAD-012 remains open: Phase 5 consolidated external-facing report was never finalized/sent.
- [ ] THREAD-013 remains open: BMK_0008 root cause was not investigated beyond the accepted edge-case label.
- [ ] THREAD-014 remains open: the mid-sentence truncation variant was not reproduced in the instrumented Phase 1 data.
- [ ] THREAD-015 remains open and deferred: `score_benchmark_run.py` still mis-flags boolean `False` `review_required` values as missing.
- [ ] No new threads were opened in this session.

## Key Decisions Made
- Treated the 25-case particle-only validation as the correct next step rather than doing more prompt redesign before breadth testing.
- Created a dedicated 25-pair config rather than reusing the 15-pair v13 config, because the old config would have silently truncated the run.
- Kept the share-pack output machine-readable (`.jsonl`) so a follow-on agent can categorize the 21 false positives without manual transcription.
- **What was rejected:** did not regenerate the entire scoring pipeline just to make the CSV prettier; the actual fix was to verify the CSV field presence and produce a cleaner share pack for analysis instead.

## Recommended Re-Entry
**Load these files for context:**
- `images\Alloy_Class\docs\iGPT_v13_FN_plan.md`
- `images\Alloy_Class\artifacts\iGPT_v13_FN_plan_rows.csv`
- `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\scoring\benchmark_particle25_v13_fp21_share.jsonl`
- `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\scoring\benchmark_scored_rows.csv`
- `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\stage_ab_results.jsonl`

**Suggested starting prompt:**
> "Read `images/Alloy_Class/outputs/raw_runs/benchmark_particle25_v13_describe_then_classify_rerun2/scoring/benchmark_particle25_v13_fp21_share.jsonl` and categorize the 21 false positives into pattern buckets. Use the Call 1 observation text to decide whether the failure is mostly Call 1 over-description, Call 2 over-interpretation, or genuine boundary ambiguity."

## Notes for Future Agent
- The 25-pair particle validation is complete and scored; the important follow-on is pattern categorization of the 21 FPs, not rerunning the benchmark.
- `benchmark_particle25_v13_fp21_share.jsonl` is the cleanest handoff artifact for the next analysis step.
- `iGPT_v13_FN_plan_rows.csv` is the smaller 8-row excerpt requested for quick review and should remain aligned with the full FP share pack.
