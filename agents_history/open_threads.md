# Open Threads

**Workspace:** BE Defects Workspace
**Last Updated:** 2026-09-04 (session log for 2026-09-04_001)

---

## Priority Key
- 🔴 Blocking - something is broken or will break
- 🟡 Important - needed soon but not blocking
- 🟢 Nice to Have - low urgency
- ⚫ Deferred - consciously parked, revisit later

---

## Open

### THREAD-001 🟡 — `build_benchmark_candidates.py` not yet built
- **Opened:** 2026-08-08
- **Session:** 2026-08-08_002
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\docs\BENCHMARK_CANDIDATE_TOOL_SCOPE.md`, `images\Alloy_Class\reporting\` (output dir)
- **Summary:** Scope document for `build_benchmark_candidates.py` was written and reviewed by the task-originating agent, but the script itself was not built. This is the primary deliverable for the next Alloy_Class benchmark session.
- **Details:**
  - 14-day manifest filter; BF/DF pair extraction
  - source_pool tagging: `factory_beep` / `non_beep_control` / `ambiguous`
  - Pair key: (WAFER_KEY, INSPECTION_TIME, DEFECT_ID)
  - Two-tier join strategy for coordinates
  - CLASS null handling required
  - factory_beep <30% is advisory warning, not hard fail
  - Outputs: `benchmark_candidates_14day.csv` + `benchmark_review_14day.html`
- **Re-entry prompt:**
  > "Read `images/Alloy_Class/docs/BENCHMARK_CANDIDATE_TOOL_SCOPE.md` in full, then implement `build_benchmark_candidates.py` in `images/Alloy_Class/reporting/` per the spec."

---

### THREAD-002 🟡 — Manifest metadata backfill lag (SUBENTITY / LOT7 / coordinates null for recent rows)
- **Opened:** 2026-08-08
- **Session:** 2026-08-08_002
- **Priority:** 🟡 Important
- **File(s):** `html\INLINE_CHAMBER_EVENT_REPORT.py`, upstream manifest pipeline (unknown file)
- **Summary:** Recent manifest rows have ~100% null values for SUBENTITY, LOT7, WAFER_X_MM, WAFER_Y_MM. Current workaround infers these from file path and filename inside the report generator. This is fragile — any naming convention change will silently break coordinate placement.
- **Details:**
  - BUG-002 and BUG-003 (session 2026-08-08_002) are resolved with inference hacks
  - Root fix requires upstream pipeline to populate these fields at manifest ingest time
  - Until fixed, SVG wafermap dots may be absent for any defect with no coordinate match
- **Re-entry prompt:**
  > "The inline HTML report generator (`html/INLINE_CHAMBER_EVENT_REPORT.py`) infers SUBENTITY and LOT7 from file path and filename because these columns are null in recent manifest rows. Review the manifest pipeline to find where backfill should be applied and implement a fix."

---

### THREAD-005 🔴 — Texture reference snip: multi-image Stage B pipeline support
- **Opened:** 2026-08-10
- **Session:** 2026-08-10_001
- **Priority:** 🔴 Blocking (blocks v4 prompt iteration)
- **File(s):** `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`
- **Summary:** Extract a clean SiO reference crop from the corner of the BF image and pass it as a 3rd image in the Stage B API call. The `_call_image` function currently accepts exactly 2 images (BF + DF). Multi-image support is required before the texture reference crop experiment (v4) can be run.
- **Details:**
  - Texture reference crop is the highest-leverage next step per user direction
  - Crop source: corner region of BF image where substrate is cleanly exposed
  - Stage B call signature must be extended to accept an optional list of supplementary images
  - May require changes to both `_call_image` and the Stage B prompt template
- **Re-entry prompt:**
  > "Read `images/Alloy_Class/reporting/run_stage_ab_prompt_tests.py` in full. Modify `_call_image` to accept an optional third image argument. Add logic to extract a clean SiO reference crop from the BF image corner and pass it to Stage B as a texture reference. Update the Stage B prompt to instruct the model to compare the defect region against the reference crop."

### ~~THREAD-005~~ ✅ RESOLVED — Texture reference snip: multi-image Stage B pipeline support
- **Resolved:** 2026-08-11
- **Session:** 2026-08-11_001
- **Notes:** Backend vision endpoint accepts `images: [b64, b64]`; the benchmark harness now uses the direct multi-image payload for Stage B. The small BF/DF pilot succeeded.

---

### THREAD-006 🟡 — BC check detection gap (comparator boundary line)
- **Opened:** 2026-08-10
- **Session:** 2026-08-10_001
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v3.json`
- **Summary:** The `bc` evidence check fires on only 6/32 nbc/possible_beep rows in the NBC52 run. 16+ missed rows have adjudicated `cbl=yes` (comparator boundary line confirmed) but model returns `bc=no`. Current prompt language is not eliciting the right visual search.
- **Details:**
  - `bc` check definition in v3: single-edge contact with comparator boundary is sufficient
  - Despite this relaxation, 26/32 nbc/possible_beep rows return `bc=no`
  - 22 FN rows: all return all checks=no; 8 of these have `bc=unclear` from model
  - Needs prompt redesign to describe the comparator boundary more concretely
- **Re-entry prompt:**
  > "Review the v3 Stage B prompt `bc` check definition in `stage_ab_prompt_tests_substrate_tier1_v3.json`. The check fires on only 6/32 nbc/possible_beep rows despite 87% of the population having adjudicated `cbl=yes`. Draft 2-3 alternative prompt phrasings that describe the comparator boundary line more concretely and test on pilot12."

---

### THREAD-007 🟡 — Stage A confounder language leaking into Stage B isl detection
- **Opened:** 2026-08-10
- **Session:** 2026-08-10_001
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`
- **Summary:** When `sa_confounder_type=offset_surface_lines`, Stage A rationale text is included verbatim in the Stage B prefix. This may cause the model to anchor on the confounder label and suppress `isl` detection despite the v3 guard, because the model "already knows" the image has surface lines.
- **Details:**
  - v3 guard added to prevent confounder label from suppressing the call
  - Rationale text verbatim inclusion was a design choice for Stage B context — may need revisiting
  - Could be tested by masking confounder type from Stage B prefix for a subset of OSL rows
- **Re-entry prompt:**
  > "In `run_stage_ab_prompt_tests.py`, find where Stage A rationale/confounder text is injected into Stage B prefix. Test a variant where `sa_confounder_type` is masked or paraphrased in the prefix for rows where `sa_confounder_type=offset_surface_lines`. Compare isl firing rate against unmasked baseline on NBC52."

---

### THREAD-008 ⚫ — sr (sunken_residual) detection ceiling: 0% firing rate
- **Opened:** 2026-08-10
- **Session:** 2026-08-10_001
- **Priority:** ⚫ Deferred
- **File(s):** `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v3.json`
- **Summary:** The `sr` evidence check fires 0% across all 52 NBC52 rows. Sunken residual is either below model visual resolution, a format issue (BF vs DF channel), or the prompt description is insufficient. Deprioritization from scoring contract is under consideration.
- **Details:**
  - 0/52 rows return `sr=yes`; some return `sr=unclear` but none fire
  - No adjudicated rows have strong sr signal available for comparison
  - May be intrinsically undetectable at current image quality/zoom
- **Re-entry prompt:**
  > "Review the `sr` check definition in `stage_ab_prompt_tests_substrate_tier1_v3.json`. Identify 3-5 adjudicated rows where `sunken_residual_continuity_present=yes` and manually inspect BF/DF images to determine if sunken residual is visually distinguishable at current image resolution. If not, remove `sr` from the evidence scoring contract."

---

### THREAD-009 🟡 — BMK_0037 relabeling question (possible_beep vs indeterminate)
- **Opened:** 2026-08-10
- **Session:** 2026-08-10_001
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv`, `images\Alloy_Class\artifacts\benchmark_pairs_nbc_focus52.csv`
- **Summary:** BMK_0037 is in the eval split and was called `possible_beep` by the v3 model. It is adjudicated as `possible_beep` with `moderate` gt_evi, but has particle morphology. This is a borderline case — if relabeled `indeterminate`, the v3 FP count drops by 1 and precision improves. User must review the image before the next benchmark comparison.
- **Details:**
  - Current label: `possible_beep` (moderate confidence)
  - v3 call: `possible_beep` — model agrees with current label (not a FP under current label)
  - Actually: this is classified as FP because model evidence doesn't match gt_evi pattern expected for NBC/possible_beep
  - Resolution: user reviews BMK_0037 BF/DF images and decides: keep label, relabel to `indeterminate`, or mark as `edge_case`
- **Re-entry prompt:**
  > "Retrieve the BF and DF images for BMK_0037 from `benchmark_pairs_nbc_focus52.csv`. Review the image pair and decide whether the adjudicated label `possible_beep` (moderate gt_evi) is correct or whether it should be changed to `indeterminate`. Update `benchmark_v1_frozen.csv` if relabeling is needed."

---

### THREAD-016 🟢 — Build per-class truth table for BEEP/SMALL_PARTICLE (EDI vs NCDD)
- **Opened:** 2026-08-08
- **Session:** 2026-08-08_012
- **Priority:** 🟢 Nice to Have
- **File(s):** `debug_logs\8M5CL_NCDD.log`, `debug_logs\ediQuery#306.log`
- **Summary:** Follow-on from the GAJT/WIJT EDI vs NCDD forensic analysis — build an explicit per-class truth table showing exact expected values for no-property row, class-missing, WAFER_TOTAL row, and normal classified row, for both EDI and NCDD columns separately. Was noted as a useful follow-on but not built during the original session.
- **Details:**
  - Was flagged in the original session log's Open Threads but never registered here or in `index.md` — added now during the 2026-08-26 logging health reconciliation pass.
- **Re-entry prompt:**
  > "Using the EDI vs NCDD SQL comparison in `agents_history\sessions\2026-08-08_012_gajt-wijt-edi-vs-ncdd-forensic-analysis.md`, build a per-class truth table for BEEP and SMALL_PARTICLE covering no-property row, class-missing, WAFER_TOTAL row, and normal classified row cases."

---

### THREAD-017 🟢 — Locate EDI WIJT JSL config on remote scheduler
- **Opened:** 2026-08-08
- **Session:** 2026-08-08_012
- **Priority:** 🟢 Nice to Have
- **File(s):** `BE_QUERY_FILES\8M5CL_NCDD_SHORT.jsl`, `BE_QUERY_FILES\8M6CL_NCDD_SHORT.jsl`
- **Summary:** The EDI WIJT JSL config is not present in the local workspace; the EDI job runs from a remote scheduler location (`\\shuser-Prod...\ScheduledGAJTvWIJTJobs\`). Confirm the path and decide whether a local copy should be pulled for documentation purposes.
- **Details:**
  - Was flagged in the original session log's Open Threads but never registered here or in `index.md` — added now during the 2026-08-26 logging health reconciliation pass.
- **Re-entry prompt:**
  > "Confirm whether the EDI WIJT JSL config still lives at `\\shuser-Prod...\ScheduledGAJTvWIJTJobs\` and decide whether to pull a local read-only copy into the workspace for documentation."

---

### THREAD-011 🟡 — v13 describe-then-classify architecture not yet promoted to production default
- **Opened:** 2026-08-26
- **Session:** 2026-08-26_003
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v13.json`, `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`, `images\Alloy_Class\tools\run_benchmark_vlm.py`
- **Summary:** The describe-then-classify architecture (Call 2 derived from V11 Stage B prompt) is validated on the 15-pair offset-surface-lines benchmark (`beep_fn_rate` 0.3571 -> 0.0, only miss is the accepted `BMK_0008` edge case) and is wired into the production runner behind `--stage-b-describe-then-classify`, but has NOT been made the default. Config `v12` is presumably still what any production/scheduled runs use.
- **Details:**
  - Head-to-head run: `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v13_compare\`
  - Written up in `images\Alloy_Class\docs\v12_post_mortem.md`, "Addendum 2026-08-26 (4)"
  - Decision is explicitly deferred to the user per the plan's original scope boundary
- **Re-entry prompt:**
  > "Review `v12_post_mortem.md`'s Addendum 2026-08-26 (4) v12/v13 comparison. Decide whether to promote `stage_ab_prompt_tests_substrate_tier1_v13.json` and `--stage-b-describe-then-classify` to the production default, and if so, identify every call site that currently defaults to v12."

---

### THREAD-012 🟡 — Phase 5 consolidated external-facing report never finalized/sent
- **Opened:** 2026-08-26
- **Session:** 2026-08-26_003
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\docs\v12_post_mortem.md`, `images\Alloy_Class\docs\iGPT_VLM_Chat_Diagnostics.md`
- **Summary:** The plan's Phase 5 called for a consolidated external-facing report plus three specific questions to the Alloy codebase owners (image transformation, `finish_reason` availability, and the deterministic-looking empty-response pattern). This was partially satisfied via post-mortem addenda but never consolidated into one standalone report or actually sent anywhere.
- **Details:**
  - The three open technical questions for Alloy codebase owners remain unasked
  - Post-mortem addenda (2), and (4) contain the raw material needed to draft this report
- **Re-entry prompt:**
  > "Consolidate the Phase 0/1 and Phase 4 addenda in `v12_post_mortem.md` into a single standalone report for the Alloy codebase owners, including the three open questions about image transformation, `finish_reason` availability, and the empty-response pattern."

---

### THREAD-013 🟢 — BMK_0008 root cause not investigated beyond "accepted edge case"
- **Opened:** 2026-08-26
- **Session:** 2026-08-26_003
- **Priority:** 🟢 Nice to Have
- **File(s):** `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v13_compare\`
- **Summary:** `BMK_0008` is the only miss on the full v13 15-pair benchmark run (moved `beep_fp_rate` from 0/1 to 1/1). The user has accepted it as a known, deliberately-labeled tricky/edge case, but no deeper investigation was done into why it still misclassifies while 3 other wall-adjacent particle controls (`BMK_0020`, `BMK_0024`, `BMK_0100`) succeeded.
- **Details:**
  - Statistically insignificant at n=1, but worth understanding if v13 is promoted
- **Re-entry prompt:**
  > "Investigate why `BMK_0008` still misclassifies under the v13 describe-then-classify architecture while the other 3 wall-adjacent particle controls (`BMK_0020`, `BMK_0024`, `BMK_0100`) succeeded. Compare Call 1/Call 2 responses directly."

---

### THREAD-014 🟢 — Mid-sentence-truncation empty-response variant never reproduced
- **Opened:** 2026-08-26
- **Session:** 2026-08-26_003
- **Priority:** 🟢 Nice to Have
- **File(s):** `images\Alloy_Class\outputs\probes\phase1_max_token_test_20260826\`
- **Summary:** The original session's mid-sentence-truncation variant of the empty-response bug (distinct from full omission) was never reproduced in the fresh instrumented Phase 1 data (n=20 per token budget). Flagged as an open, unresolved detail, not closed out.
- **Details:**
  - Phase 1 confirmed full-omission empty responses at 400 tokens (5/20, 25%) resolved at 1800 tokens (0/20)
  - The separate truncation-mid-sentence variant was not observed in this instrumented batch
- **Re-entry prompt:**
  > "Review `images\\Alloy_Class\\outputs\\probes\\phase1_max_token_test_20260826\\` raw data for any mid-sentence-truncated (as opposed to fully empty) responses. If none are present, design a targeted reproduction attempt for the truncation variant specifically."

---

### THREAD-015 ⚫ — score_benchmark_run.py boolean `False` review_required mis-flagged as missing
- **Opened:** 2026-08-26
- **Session:** 2026-08-26_003
- **Priority:** ⚫ Deferred
- **File(s):** `images\Alloy_Class\tools\score_benchmark_run.py`
- **Summary:** The stage_b contract-check heuristic evaluates `str(False or "")`, which truthiness-collapses to `""`, causing legitimate boolean `False` `review_required` values to be flagged as "missing" fields. Minor and unrelated to the v12/v13 comparison's headline metrics; explicitly left unfixed as out of scope.
- **Details:**
  - Noted during Phase 4 scoring of the v13 head-to-head run
  - Does not affect `beep_fn_rate`, `coarse_class_agreement_rate`, or the other headline metrics reported this session
- **Re-entry prompt:**
  > "In `score_benchmark_run.py`'s stage_b contract-check heuristic, fix the `str(False or \"\")` truthiness bug so boolean `False` `review_required` values are not flagged as missing."

---

### THREAD-018 🔴 — Fundamental FP/FN trade-off unresolved across both prompt lineages
- **Opened:** 2026-08-27
- **Session:** 2026-08-27_001
- **Priority:** 🔴 Blocking (motivated the 08-30 strategic pivot proposal; central open technical problem of the session)
- **File(s):** `images\Alloy_Class\tools\probe_describe_then_classify_v14.py`, `images\Alloy_Class\tools\probe_beep_lexicon_v1.py`, `images\Alloy_Class\tools\probe_beep_lexicon_v2.py`, `images\Alloy_Class\docs\v12_post_mortem.md`
- **Summary:** Every attempt this session to tighten evidence criteria to reduce false positives also measurably increased false negatives (and vice versa), across both the V11-derived prompt lineage (v14: 3/21 FP fixed but 3/5 FN cases regressed) AND the from-scratch lexicon iteration (v1 -> v2's shadow-neglect and boundary-conformance changes made FP rate worse -- 0.538 vs 0.385 -- while FN rate stayed flat at 0.40).
- **Details:**
  - Echoes an analogous historical finding already in `docs\v12_post_mortem.md` about V12's stricter guidance having the same two-sided effect -- never resolved for the V11-derived prompt lineage, and now recurring in the fresh lexicon lineage too.
  - Directly motivated the user's 08-30 strategic pivot proposal (manual disposition + decoupled fine-bin VLM tagging, see THREAD-021).
- **Re-entry prompt:**
  > "This session found that every attempt to tighten evidence criteria to reduce false positives also increased false negatives, across both the V11-derived prompt lineage and the from-scratch BEEP lexicon (v1 -> v2). See `docs\v12_post_mortem.md` for the analogous V12 precedent. Before attempting further prompt patches, consider whether the binary disposition task has a ceiling that prompt engineering alone cannot cross."

---

### THREAD-019 🟡 — v1 -> v2 lexicon FP-rate regression not yet diagnosed
- **Opened:** 2026-08-29
- **Session:** 2026-08-27_001
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\tools\probe_beep_lexicon_v1.py`, `images\Alloy_Class\tools\probe_beep_lexicon_v2.py`, `images\Alloy_Class\outputs\probes\scored\beep_lexicon_v1_20260828_full31\`, `images\Alloy_Class\outputs\probes\scored\beep_lexicon_v2_20260829_full31\`
- **Summary:** `probe_beep_lexicon_v2.py` was run on the same 31-case set as v1 and produced a worse FP rate (0.538 vs. v1's 0.385) with FN rate unchanged at 0.40. No case-level diagnosis of which specific cases flipped from correct to incorrect, or why, has been performed.
- **Details:**
  - v2 incorporated user-authored lexicon fixes for shadow/sunken-residual confusion and boundary-conformance/ISL-continuity gaps (from 15 pieces of portal feedback on the v1 run).
  - Related to THREAD-018 (fundamental trade-off) but this is the concrete, ready-to-pick-up next action.
- **Re-entry prompt:**
  > "We ran `tools\probe_beep_lexicon_v2.py` on the same 31-case set as v1 and got FP rate 0.538 (worse than v1's 0.385) with FN rate unchanged at 0.4. Nobody has looked into which specific cases flipped from correct to incorrect between v1 and v2, or why. Compare `outputs\probes\scored\beep_lexicon_v1_20260828_full31\` against `outputs\probes\scored\beep_lexicon_v2_20260829_full31\` case-by-case and diagnose root cause before making further lexicon changes."

---

### THREAD-020 🟡 — User has not yet reviewed the v2 HTML report or submitted portal feedback
- **Opened:** 2026-08-29
- **Session:** 2026-08-27_001
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\outputs\probes\scored\beep_lexicon_v2_20260829_full31\`
- **Summary:** The v2 HTML report was regenerated with the feedback widget and opened in the user's browser, but as of session end the user had not yet reviewed it or submitted feedback.
- **Details:**
  - The feedback-portal backend was restarted pointed at the v2 run's own feedback CSV before this happened.
- **Re-entry prompt:**
  > "Check `outputs\probes\scored\beep_lexicon_v2_20260829_full31\probe_review_feedback.csv` for new submissions before proceeding with anything lexicon-related."

---

### THREAD-021 🟡 — Strategic pivot decision pending (manual disposition + decoupled fine-bin VLM tagging)
- **Opened:** 2026-08-30
- **Session:** 2026-08-27_001
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\docs\TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md`
- **Summary:** The user was considering pivoting from binary pre/post-etch VLM disposition toward two decoupled tracks: (a) manual disposition performed by the user personally via the existing HTML+feedback-portal tooling, focused on post-etch (true particle) populations, and (b) a separate VLM fine-bin multi-label tagging effort (example labels: Occlusion, Morphology, number of continuous defects, Is a sphere) across the full ~6,487-defect SMALL_PARTICLE population, to support statistical correlation against process drivers (chamber, PM/part-installation history, litho scanner) and to build a case for ruling out certain particle morphologies from pre-etch consideration entirely.
- **Details:**
  - `TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md` was authored to inform this decision, deliberately containing no plan or recommendations, per explicit repeated user instruction.
  - Existing infrastructure that would carry over: `material_defects[]` array concept, morphology taxonomy already in the lexicon, the generic scoring/HTML/feedback pipeline.
- **Re-entry prompt:**
  > "The user was considering pivoting from binary pre/post-etch VLM disposition toward two decoupled tracks: (a) manual disposition performed by the user personally via the existing HTML+feedback-portal tooling, focused on post-etch (true particle) populations, and (b) a separate VLM fine-bin multi-label tagging effort (example labels: Occlusion, Morphology, number of continuous defects, Is a sphere) across the full ~6,487-defect SMALL_PARTICLE population, to support statistical correlation against process drivers (chamber, PM/part-installation history, litho scanner) and to build a case for ruling out certain particle morphologies from pre-etch consideration entirely. See `images\Alloy_Class\docs\TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md` for the current-state tooling inventory prepared to inform this decision. The user had NOT yet asked for an actual plan to be drafted as of this session's end -- confirm before proceeding to plan-writing or implementation."

---

### THREAD-022 🟢 — Litho-scanner metadata correlation unconfirmed
- **Opened:** 2026-08-30
- **Session:** 2026-08-27_001
- **Priority:** 🟢 Nice to Have
- **File(s):** `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py`, `BE_QUERY_FILES\surf_scan_coordinates.py`
- **Summary:** A quick read-only audit of `BE_QUERY_FILES\*.py` found no existing join between BE/etch-chamber defect records and litho-scanner identity.
- **Details:**
  - Relevant to the "are spheres only appearing on chambers with a specific incoming litho scanner" correlation axis from THREAD-021's tagging proposal.
- **Re-entry prompt:**
  > "A quick read-only audit of `BE_QUERY_FILES\*.py` found no existing join between BE/etch-chamber defect records and litho-scanner identity. If the 'incoming litho scanner' correlation axis from the tagging plan is pursued, this will likely need new data plumbing."

---

### THREAD-023 🟢 — PM-counter part-installation granularity unconfirmed
- **Opened:** 2026-08-30
- **Session:** 2026-08-27_001
- **Priority:** 🟢 Nice to Have
- **File(s):** `BE_QUERY_FILES\surf_scan_elwc_pm_pilot.py`, `BE_QUERY_FILES\surf_scan_elwc_pm_stage_backfill.py`
- **Summary:** These files track PM mechanical-cycle counters per chamber over time, but it was not confirmed whether this data also captures discrete part-swap/installation events vs. only cumulative cycle counts.
- **Details:**
  - Relevant to the "are porous particles only appearing on chambers with a specific pilot part installed" correlation axis from THREAD-021's tagging proposal.
- **Re-entry prompt:**
  > "`BE_QUERY_FILES\surf_scan_elwc_pm_pilot.py` and `surf_scan_elwc_pm_stage_backfill.py` track PM mechanical-cycle counters per chamber over time, but it was not confirmed whether this data also captures discrete part-swap/installation events vs. only cumulative cycle counts. Needs closer inspection if the 'chambers with this pilot part installed' correlation axis is pursued."

---

### THREAD-024 🟡 — Alloy VLM truncated/empty responses at 1800-token budget
- **Opened:** 2026-08-28
- **Session:** 2026-08-27_001
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\tools\probe_beep_lexicon_v1.py`, `images\Alloy_Class\tools\probe_beep_lexicon_v2.py`
- **Summary:** The Alloy VLM occasionally returns truncated or fully empty responses even at the standing 1800-max-completion-token budget (2 of 31 cases in the v1 run, 6 of 31 in the v2 run). Workaround is manually retrying the specific failed case_id(s) at a higher budget (2400 worked both times); no root cause diagnosed.
- **Details:**
  - Getting worse across runs (2 -> 6 of 31) rather than better, which is itself unexplained.
- **Re-entry prompt:**
  > "The Alloy VLM occasionally returns truncated or fully empty responses even at 1800 max_completion_tokens (2/31 in the v1 lexicon run, 6/31 in v2). Investigate whether this is prompt-length-related, image-payload-related, or an Alloy-side issue, rather than continuing to manually retry at 2400 tokens."

---

### THREAD-025 🟢 — Model non-determinism on borderline/duplicate test cases
- **Opened:** 2026-08-27
- **Session:** 2026-08-27_001
- **Priority:** 🟢 Nice to Have
- **File(s):** `images\Alloy_Class\tools\probe_describe_then_classify_v14.py`, `images\Alloy_Class\tools\probe_beep_lexicon_v1.py`
- **Summary:** Identical image pair, prompt, and model produced different verdicts across duplicate test entries within the same run batch (`BMK_0008` and `BMK_0011` specifically).
- **Details:**
  - `BMK_0008`/`BMK_0011` are intentionally dual-listed in `TEST_CASES` as same-batch repeatability spot-checks -- this is by design, but the non-determinism it revealed is a real open question.
- **Re-entry prompt:**
  > "`BMK_0008` and `BMK_0011` are intentionally dual-listed in the lexicon probe test-case sets as repeatability spot-checks, and produced different verdicts across duplicate entries in the same batch. Determine whether this is pure sampling variance or indicates a borderline-case sensitivity worth addressing in the lexicon."

---

### THREAD-026 🟡 — Decide whether to wire the direct INSP_ELEMENT EDX join into the OX pilot pipeline
- **Opened:** 2026-08-31
- **Session:** 2026-08-31_001
- **Priority:** 🟡 Important
- **File(s):** `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_coordinates.py`, `BE_QUERY_FILES\surf_scan_coordinates.py`
- **Summary:** The EDX LAYER_ID investigation for lot D629T8V0 confirmed that `UDB.INSP_ELEMENT` elemental data already joins directly to the original UDE scan's `WAFER_KEY`/`INSPECTION_TIME`/`DEFECT_ID`, matching production's `_fetch_edx_data()` pattern in `BE_QUERY_FILES\surf_scan_coordinates.py` exactly. The user was asked whether to wire this join into the OX pilot pipeline now, or hold off until the pilot's imaging scope is defined -- no answer given as of session end.
- **Details:**
  - No separate EDX-submission LAYER_ID is needed; the join is a direct key match against the existing scan record.
  - Three candidate LAYER_ID guesses (`6BARESI_EDX_UDC`, `6OXIDE_EDX_UDC_100`, `MBTW_MPLVCAOX450_EDX`) were all confirmed not to exist in `UDB.INSP_WAFER_SUMMARY`.
  - `MBTW_EDX_API` is a real but unrelated layer (different tool family, SRC403/SRC414 inspect equipment) with zero rows for this lot.
- **Re-entry prompt:**
  > "Read `rollups/1K_OX_PILOT_PIPELINE/ox_pilot_config.py` and `ox_pilot_coordinates.py` in full, plus `_fetch_edx_data()` in `BE_QUERY_FILES/surf_scan_coordinates.py`. Decide whether to wire the direct `UDB.INSP_ELEMENT` EDX join into the OX pilot pipeline now, following the same pattern as production, or hold off until the pilot's imaging scope is defined."

---

### THREAD-027 🟢 — Optional cleanup: dead inline-style code paths or progress wording
- **Opened:** 2026-09-04
- **Session:** 2026-09-04_001
- **Priority:** 🟢 Nice to Have
- **File(s):** `images\Alloy_Class\tools\build_small_particle_raw_cache.py`
- **Summary:** The flat `RAW_IMAGES` refactor validated cleanly on the 100-group pilot, but there may still be dead inline-style code paths or progress-message wording that can be trimmed for clarity.
- **Details:**
  - No functional issue remains from the pilot validation.
  - This is purely cleanup-oriented and can be deferred.
- **Re-entry prompt:**
  > "Review `images\\Alloy_Class\\tools\\build_small_particle_raw_cache.py` for dead inline-style branches left behind by the RAW_IMAGES refactor, and decide whether the progress message should be simplified to better match the flat download flow."

---

  ### ~~THREAD-010~~ ✅ RESOLVED — Prompt iteration registry follow-up
  - **Resolved:** 2026-08-11
  - **Session:** 2026-08-11_004
  - **Notes:** Closed after the prompt-bundle provenance work confirmed the run-local artifact path and updated the registry guidance to point at `prompt_bundle.json` / `prompt_bundle.txt`.

  ## Resolved

  | Thread ID | Title | Resolved Date | Session | Notes |
  |-----------|-------|---------------|---------|-------|

---

### ~~THREAD-003~~ ✅ RESOLVED — Benchmark schema contract drift (template vs builder output vs adjudication columns)
- **Opened:** 2026-08-09
- **Session:** 2026-08-09_002
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\artifacts\benchmark_slice_v1_template.csv`, `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv`, `images\Alloy_Class\tools\build_benchmark_candidates.py`, `images\Alloy_Class\docs\BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md`
- **Summary:** The active adjudication CSV includes additional adjudication/evidence columns beyond the baseline template contract. The template, builder output contract, and workflow docs need one authoritative column spec to prevent regen drift or accidental column loss.
- **Details:**
  - Current candidate CSV carries expanded signature/evidence fields and optional derived columns.
  - Template baseline is not yet guaranteed to match live working contract.
  - Regeneration risk: builder may overwrite or reorder columns unless contract is synchronized.
- **Re-entry prompt:**
  > "Compare `benchmark_slice_v1_template.csv`, `benchmark_candidates_14day.csv`, and `build_benchmark_candidates.py` output logic. Produce one canonical column contract, update template/docs/tooling to match, and verify no adjudication fields are dropped on regeneration."

---

### ~~THREAD-004~~ ✅ RESOLVED — Adjudication shorthand and free-text anomalies need normalization before scoring
- **Opened:** 2026-08-09
- **Session:** 2026-08-09_002
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv`, `images\Alloy_Class\docs\ADJUDICATION_WORKSHEET_ONE_PAGER.md`
- **Summary:** Active adjudication rows include shorthand codes and narrative variability. These need normalization to canonical values before split/final scoring to avoid metric distortion.
- **Details:**
  - Shorthand is allowed during fast entry by design, but analysis expects normalized enums.
  - Long free-text notes contain occasional malformed/transcription-like content.
  - A normalization/QA pass is required before freezing the eval snapshot.
- **Re-entry prompt:**
  > "Normalize adjudication fields in `benchmark_candidates_14day.csv` to canonical enum values, isolate/repair anomalous free-text rows, then regenerate split preview and produce a frozen eval-ready snapshot with QA checks."

---

## Resolved

| Thread ID | Title | Resolved Date | Session | Notes |
|-----------|-------|---------------|---------|-------|
| THREAD-003 | Benchmark schema contract drift | 2026-08-10 | 2026-08-10_001 | Template updated to 44 cols; schema doc sections 5C/5E/6/10B/10C/11 updated; tool scope doc annotated |
| THREAD-004 | Adjudication shorthand normalization | 2026-08-10 | 2026-08-10_001 | 1595 cells expanded across 11 columns via normalize_benchmark_adjudication.py; 0 unrecognized values; backup preserved |
| THREAD-005 | Texture reference snip: multi-image Stage B pipeline support | 2026-08-11 | 2026-08-11_001 | Backend accepts `images: [b64, b64]`; pilot succeeded |
