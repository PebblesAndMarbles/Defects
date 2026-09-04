---
session_id: 2026-08-26_003
title: Alloy VLM V13 Describe-Then-Classify Diagnostics + Production Promotion Checkpoint
date: 2026-08-26
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 5
triggered_by: manual-checkpoint
status: complete
original_goal: Build and execute a plan (shareable with the external reviewing agent for iterative review) addressing the diagnostics doc's suppression hypotheses (Stage A context poisoning, JSON-contract forced premature commitment, instruction-volume anchoring) and a separate suspected max-token empty-response reliability issue, then validate any fix on the known FN cases before deciding whether to promote it to production.
---

## Original Goal
This was a same-day follow-on to `2026-08-26_002`. The user shared positive results
from the prior FN feature-perception probe checkpoint plus external-agent feedback
in `images\Alloy_Class\docs\iGPT_VLM_Chat_Diagnostics.md`, and asked for a plan
addressing the diagnostics doc's hypotheses — both the suppression hypotheses
(Stage A context poisoning, JSON-contract forced premature commitment,
instruction-volume anchoring) and a separate "no response" / empty-response
reliability issue the user suspected was a max-token problem. The plan was to be
shareable with the external reviewing agent for iterative review.

## Discovery / Investigation
- Investigated the Alloy Class VLM pipeline empty-response bug path: `_call_image()`,
  `_extract_json_payload()`, `_extract_usage()` in
  `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`, and the installed
  `alloy.core.llm.core` package.
- Drafted a phased plan (Phase 0 instrumentation -> Phase 1 max-token test ->
  Phase 2 describe-then-classify script -> Phase 3 validation -> Phase 4 scale-up
  -> Phase 5 reporting), saved to `/memories/session/plan.md`.
- Got two rounds of external-agent review
  (`images\Alloy_Class\docs\iGPT_v13_plan_feedback.md`,
  `images\Alloy_Class\docs\iGPT_v13_plan_feedback2.md`) and incorporated both into
  the plan: Phase 0 image payload byte-length/ratio logging, Phase 1 bare-call
  token isolation, Phase 3 expanded/wall-adjacent particle controls, Phase 4 metric
  priority order (primary/secondary/tertiary), Phase 5 report framing — and
  critically, the second round's directive that Call 2 of the describe-then-classify
  architecture must be drafted from the V11 Stage B prompt
  (`stageB_substrate_tier1_v10`), NOT V12, since V11 had zero FP rate and V12's
  ~15 added guidance blocks caused an evidence-agreement regression on `BMK_0018`.
- Created an untitled scratch file `plan-alloyVlmV13Diagnostics.prompt.md` with the
  plan content per user request (in-memory only, not saved to disk — user was told
  its `untitled:` path is not a real filesystem path).

## Completed Tasks
- [x] Phase 0: instrumented `run_stage_ab_prompt_tests.py`. Found and fixed a real
      bug in `_extract_json_payload()` (see BUG-001). Added `usage_source`,
      `error_class`, `empty_response`, `response_char_count`, `finish_reason`,
      `image_payload_diagnostics` (per-image source bytes, base64 length, ratio)
      to `_call_image()`'s usage dict, fully backward-compatible (3-tuple return
      unchanged, `run_suite()` unaffected). Also extended
      `tools\probe_fn_feature_perception.py`'s per-call records with the same
      fields. Verified via a smoke test that reproduced the historically-persistent
      -empty `BMK_0050`/p2 case.
- [x] Phase 1: ran 40 bare calls (5 known FN cases x p1/p2 x 2 reps x
      {400, 1800} max_completion_tokens) to test the max-token hypothesis. Result:
      400 tokens -> 5/20 (25%) empty responses; 1800 tokens -> 0/20 (0%).
      `finish_reason` was `None` on all 40 calls (endpoint never exposes it).
      `encode_ratio` was consistently ~1.3333 (no evidence of image transformation).
      Hypothesis CONFIRMED as a real contributing cause. Raised
      `probe_fn_feature_perception.py`'s `DEFAULT_MAX_TOKENS` from 400 to 1800.
      Archived raw run data to
      `images\Alloy_Class\outputs\probes\phase1_max_token_test_20260826\`. Wrote
      up as "Addendum 2026-08-26 (2)" in `images\Alloy_Class\docs\v12_post_mortem.md`.
- [x] Phase 2: built `images\Alloy_Class\tools\probe_describe_then_classify.py` —
      Call 1 is a neutral free-observation prompt (no Stage A context, no JSON
      contract); Call 2's evidence-check framework is derived AT RUNTIME directly
      from `config\stage_ab_prompt_tests_substrate_tier1_v11.json`'s stage_b prompt
      (not hand-copied, not V12) by stripping the Stage-A-context sentence and
      injecting Call 1's observation instead.
- [x] Phase 3 (first pass): ran 5 FN cases + 4 "particle control" cases
      (`BMK_0008` plus 3 candidates selected from
      `artifacts\benchmark_candidates_14day.csv`). Initial result looked like a
      total failure — all 4 controls incorrectly flipped to `possible_beep`
      (100% FP rate) — written up as a FAIL in the post-mortem.
- [x] Corrected Phase 3 after BUG-002 was caught by the user (see below):
      re-selected 3 genuinely-adjudicated wall-adjacent particle controls
      (`BMK_0020`, `BMK_0024`, `BMK_0100`), re-ran them: all 3 correctly stayed
      `particle`. Corrected picture: 11/12 correct (5/5 FN flips + 3/3 corrected
      controls + 3/3 originally-mislabeled cases turn out correct too), with only
      `BMK_0008` still missing. This reversed the "FAIL" conclusion to a strong
      pass. Corrected the post-mortem addendum in place (struck through the wrong
      analysis rather than deleting it, added a visible correction section).
      Recorded the GT-column lesson (`adjudicated_coarse_class` vs
      `factory_class_label`/`source_pool`) in repo memory
      (`/memories/repo/alloy_class_vlm_architecture_investigation.md`, new
      section 10) to prevent recurrence.
- [x] Phase 4 (production promotion, after user confirmed `BMK_0008` is an
      accepted edge case and said proceed): added a
      `--stage-b-describe-then-classify` CLI flag to
      `run_stage_ab_prompt_tests.py` (threaded through `run_suite()`,
      `_parse_args()`, `main()`), with shared module-level helpers
      (`CALL1_OBSERVATION_PROMPT`, `_load_v11_stage_b_prompt()`,
      `_build_describe_then_classify_call2_prompt()`) now living in the production
      file rather than only the throwaway probe script. Added pass-through flag to
      `tools\run_benchmark_vlm.py`. Created new config
      `config\stage_ab_prompt_tests_substrate_tier1_v13.json`.
- [x] Ran the FULL 15-pair `offset_surface_lines_15` benchmark (same pair list
      CSV and flags as the existing v12 comparison run, for a clean head-to-head)
      via `run_benchmark_vlm.py` -> `score_benchmark_run.py`. Renamed the output
      run folder from an initially-misleading `v13_dryrun_1pair` name to
      `offset_surface_lines_15_v13_compare` (it had actually run all 15 pairs, not
      a 1-pair dry run as originally intended — naming mistake, not a data
      mistake).
- [x] Wrote up the full before/after comparison as "Addendum 2026-08-26 (4)" in
      `images\Alloy_Class\docs\v12_post_mortem.md`. Recorded the run in
      `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md`'s CSV tracker
      (`artifacts\prompt_iteration_registry.csv`, new row
      `offset_surface_lines_15_v13_compare`).
- [x] Updated `/memories/session/plan.md` throughout to track Phase 0-4 execution
      status. Told the user that v13 is validated but NOT yet promoted to the
      production default — that remains a follow-on decision.

## Key Finding / Result
v12 baseline -> v13, same 15 pairs:
- `beep_fn_rate`: 0.3571 -> 0.0 (primary metric; all known FNs including the 4
  tune-set ones now flip correct)
- `BMK_0001` (secondary, eval-split FN): flips correct
- `BMK_0018` `evidence_match` regression (tertiary metric): recovers
- `coarse_class_agreement_rate`: 0.6667 -> 0.9333
- `evidence_agreement_rate`: 0.5333 -> 0.80
- `review_required_calibration_rate`: 0.1333 -> 0.6667
- Only miss on the full benchmark: `BMK_0008` (the same accepted edge case), so
  `beep_fp_rate` moved from 0/1 to 1/1 (statistically insignificant at n=1,
  expected).
- Also noted a pre-existing, unrelated minor quirk in `score_benchmark_run.py`'s
  contract-check heuristic (flags boolean `False` `review_required` values as
  "missing" due to `str(False or "")` truthiness) — not fixed, out of scope,
  flagged only (see BUG-003).

Conclusion: the describe-then-classify architecture, with Call 2 derived from V11
(not V12), resolves the suppression hypotheses on this 15-pair slice without
introducing new false positives beyond the single pre-existing accepted edge case.
v13 is validated but NOT promoted to the production default.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | Modified | BUG-001 fix (`_extract_json_payload` native payload preservation) + new diagnostic fields + new `--stage-b-describe-then-classify` production mode with V11-derived Call 2 prompt builder |
| `images\Alloy_Class\tools\probe_fn_feature_perception.py` | Modified | New diagnostic fields surfaced in output records; `DEFAULT_MAX_TOKENS` raised 400->1800 |
| `images\Alloy_Class\tools\probe_describe_then_classify.py` | Created | Phase 2/3 throwaway probe; later corrected for the particle-control GT bug (BUG-002) |
| `images\Alloy_Class\tools\run_benchmark_vlm.py` | Modified | Added `--stage-b-describe-then-classify` pass-through flag |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v13.json` | Created | Production config for the describe-then-classify architecture |
| `images\Alloy_Class\docs\v12_post_mortem.md` | Modified | 3 new addenda appended (Phase 0/1 results; Phase 2/3 results with an in-place correction; Phase 4 results), consistent with the existing convention of appending rather than creating new files |
| `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md` | Modified | New v13 row appended |
| `images\Alloy_Class\artifacts\prompt_iteration_registry.csv` | Modified | New row: `offset_surface_lines_15_v13_compare` |
| `/memories/session/plan.md` | Created, then modified | Iteratively updated to track plan + execution status across all phases |
| `/memories/repo/alloy_class_vlm_architecture_investigation.md` | Modified | New section 10 added (GT-column lesson: `adjudicated_coarse_class` vs `factory_class_label`/`source_pool`) |
| `images\Alloy_Class\outputs\probes\phase1_max_token_test_20260826\*.jsonl` (5 files) | Created | Raw Phase 1 max-token test data |
| `images\Alloy_Class\outputs\probes\phase3_describe_then_classify_20260826\*.jsonl` (3 files, one superseded) | Created | Phase 2/3 probe run outputs |
| `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v13_compare\` | Created | Full 15-pair v13 benchmark run + score outputs |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\docs\iGPT_VLM_Chat_Diagnostics.md` | External-agent diagnostics doc; source of the suppression hypotheses this session's plan addressed | No |
| `images\Alloy_Class\docs\iGPT_v13_plan_feedback.md` | First round of external-agent plan review; incorporated | No |
| `images\Alloy_Class\docs\iGPT_v13_plan_feedback2.md` | Second round of external-agent plan review; incorporated (V11-not-V12 directive) | No |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v11.json` | Read for comparison and as the runtime source for Call 2's evidence-check prompt derivation | No |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v12.json` | Read for comparison; confirmed as the baseline NOT to derive Call 2 from | No |
| `C:\Users\tbatson\My Programs\SQLPathFinder3\Python3\alloy\core\llm\core.py` | Installed package, inspected (not edited) as part of the empty-response bug investigation | No |
| `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv` | Source of the (initially mis-selected, then corrected) particle controls for Phase 3 | No |
| `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv` | Benchmark ground truth, used for scoring | No |
| `images\Alloy_Class\artifacts\benchmark_offset_surface_lines_yes_15.csv` | Benchmark pair list, used for the v12/v13 head-to-head run | No |
| `plan-alloyVlmV13Diagnostics.prompt.md` (untitled scratch file) | Created in-memory per user request to hold the plan text; not a real filesystem path, not saved to disk | No |

## Bugs Encountered
### BUG-001: `_extract_json_payload()` silently discarded native response payload
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`
- **Root Cause:** `_extract_json_payload()` was discarding the full native response
  dict (silently dropping `usage`/`finish_reason`/etc.) whenever content resolved
  to a plain string, which is the normal case — root cause of why native token
  usage was never captured.
- **Fix Applied:** Preserved the native payload alongside the extracted content;
  added `usage_source`, `error_class`, `empty_response`, `response_char_count`,
  `finish_reason`, `image_payload_diagnostics` to `_call_image()`'s usage dict.
  Fully backward-compatible (3-tuple return unchanged, `run_suite()` unaffected).
- **Notes:** Found during Phase 0 instrumentation, before the max-token test
  could be trusted to report accurate token counts.

### BUG-002: Phase 3 particle-control selection used the wrong ground-truth column
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\tools\probe_describe_then_classify.py`,
  `images\Alloy_Class\docs\v12_post_mortem.md`
- **Root Cause:** My own mistake, caught by the user. In the first Phase 3 pass, I
  selected particle-control cases by filtering
  `artifacts\benchmark_candidates_14day.csv` on `factory_class_label` (a
  pre-adjudication sampling-pool label) instead of `adjudicated_coarse_class` (the
  real human-adjudicated ground truth, adjudicated by the user "TB"). This
  produced an entirely wrong "the architecture over-calls BEEP" conclusion.
- **Fix Applied:** Verified `BMK_0002`/`BMK_0004`/`BMK_0092` were actually GT
  `possible_beep`, not `particle`; only `BMK_0008` had correct GT (`particle`,
  a known accepted edge case). Re-selected 3 genuinely-adjudicated wall-adjacent
  particle controls (`BMK_0020`, `BMK_0024`, `BMK_0100`), re-ran them: all 3
  correctly stayed `particle`. Corrected the post-mortem addendum in place with
  visible strikethrough + a correction section rather than silently rewriting
  history. Recorded the GT-column lesson in
  `/memories/repo/alloy_class_vlm_architecture_investigation.md` (new section 10)
  to prevent recurrence.
- **Notes:** This reversed an initial "FAIL" conclusion (100% FP rate on
  controls) to a strong pass (11/12 correct). Future agents selecting benchmark
  controls MUST filter on `adjudicated_coarse_class`, never
  `factory_class_label`/`source_pool`.

### BUG-003: `score_benchmark_run.py` boolean `False` `review_required` mis-flagged as missing
- **Status:** Deferred (flagged, not fixed — out of scope for this session)
- **File(s):** `images\Alloy_Class\tools\score_benchmark_run.py`
- **Root Cause:** The stage_b contract-check heuristic evaluates
  `str(False or "")`, which truthiness-collapses to `""`, causing legitimate
  boolean `False` `review_required` values to be flagged as "missing" fields.
- **Fix Applied:** None — flagged in the post-mortem addendum, explicitly left
  unfixed as out of scope for this session.
- **Notes:** Minor and unrelated to the describe-then-classify work; does not
  affect the v12/v13 comparison's headline metrics.

## Excursions / Scope Creep Discovered
- None beyond the Phase 3 GT-selection bug (BUG-002), which was corrected within
  this same session rather than deferred.

## Open Threads
- [ ] v13 has NOT been promoted as the production default (config `v12` is still
      presumably what production/scheduled runs use, if any exist beyond this
      benchmark harness) — that promotion decision is explicitly deferred to the
      user. (THREAD-011)
- [ ] Phase 5 (consolidated external-facing report + the three specific questions
      to Alloy codebase owners about image transformation, `finish_reason`
      availability, and the deterministic-looking empty-response pattern) was
      partially done via the post-mortem addenda but never consolidated into a
      single standalone report or actually sent anywhere. (THREAD-012)
- [ ] `BMK_0008`'s specific reason for still misclassifying was never
      root-caused beyond "known tricky edge case, user-accepted" — no deeper
      investigation was done into why 3 other wall-adjacent particle controls
      succeeded while this one didn't. (THREAD-013)
- [ ] The original session's mid-sentence-truncation variant of the
      empty-response bug (distinct from full omission) was never reproduced in
      the fresh instrumented Phase 1 data (n=20 per budget) — flagged as an open,
      unresolved detail, not closed out. (THREAD-014)
- [ ] `score_benchmark_run.py`'s boolean `False` `review_required` heuristic bug
      (BUG-003) remains unfixed. (THREAD-015)
- [ ] THREAD-001 remains open: `build_benchmark_candidates.py` still not built.
- [ ] THREAD-002 remains open: manifest metadata backfill lag.
- [ ] THREAD-006 remains open: `bc` detection gap.
- [ ] THREAD-007 remains open: Stage A confounder language may still suppress
      `isl` detection.
- [ ] THREAD-008 remains deferred: `sr` detection ceiling.
- [ ] THREAD-009 remains open: `BMK_0037` relabeling question.

## Key Decisions Made
- Kept the empty-response/max-token track (Track 2) and the
  suppression-architecture track (Track 1) as independently verifiable phases
  per the externally-reviewed plan.
- Drafted Call 2's evidence framework from V11, not V12, per the second external
  review round — the single most important execution note in the plan.
- Promoted the two-call architecture into the production runner (not just a
  throwaway script) once Phase 3 validation passed, per user's explicit "proceed
  to Phase 4" instruction after accepting `BMK_0008` as a known edge case.
- **What was rejected:** did NOT promote v13 to be the new production default
  config — left as an explicit follow-on decision for the user, per the plan's
  original scope boundary.
- When the GT-mislabeling bug (BUG-002) was found, corrected the post-mortem
  document in place with visible strikethrough + correction section rather than
  silently rewriting history, to preserve an honest record.

## Recommended Re-Entry
**Load these files for context:**
- `images\Alloy_Class\docs\v12_post_mortem.md` (includes Addenda 2026-08-26 (2) and (4), and the corrected Phase 2/3 addendum)
- `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md` / `images\Alloy_Class\artifacts\prompt_iteration_registry.csv`
- `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v13.json`
- `images\Alloy_Class\tools\probe_describe_then_classify.py`
- `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` (`--stage-b-describe-then-classify` flag)
- `/memories/session/plan.md` and `/memories/repo/alloy_class_vlm_architecture_investigation.md` (session memory scope)

**Suggested starting prompt:**
> "Continue from the v13 describe-then-classify checkpoint: v13 is validated on
> the 15-pair offset-surface-lines benchmark (beep_fn_rate 0.3571 -> 0.0, only
> miss is the accepted BMK_0008 edge case) but not yet promoted to production.
> Decide whether to promote v13 as the default config, and/or consolidate the
> Phase 5 external-facing report with the three open questions for the Alloy
> codebase owners."

## Notes for Future Agent
- When selecting benchmark control/edge cases from
  `artifacts\benchmark_candidates_14day.csv`, ALWAYS filter on
  `adjudicated_coarse_class` (the real human-adjudicated ground truth), never
  `factory_class_label` or `source_pool` (pre-adjudication sampling-pool labels).
  This mistake (BUG-002) inverted an entire pass/fail conclusion in this session.
- Call 2 of the describe-then-classify architecture must always be derived from
  the V11 Stage B prompt, not V12 — V12's ~15 added guidance blocks caused a
  regression on `BMK_0018` and this is why the external reviewer flagged it
  explicitly in the second feedback round.
- `finish_reason` is never populated by the Alloy endpoint (`None` on all 40
  Phase 1 calls) — do not rely on it as a diagnostic signal without separately
  confirming the endpoint has started exposing it.
- v13 is validated but explicitly NOT the production default — do not assume it
  is live in any scheduled/production run without checking which config is
  actually wired in.
- The 2026-08-26 index/session-log backlog observation from this checkpoint: the
  master `agents_history\index.md` is missing several existing session log files
  (e.g. `2026-08-08_003` through `_013`, `2026-07-28_001`, and duplicate `_001`
  filenames exist for both `2026-08-15` and `2026-08-18`). This was flagged to the
  user but not repaired in this session — out of scope for this checkpoint.
