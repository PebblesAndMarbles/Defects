# Open Threads

**Workspace:** BE Defects Workspace
**Last Updated:** 2026-09-12 (session log for 2026-09-12_001)

---

## Priority Key
- 🔴 Blocking - something is broken or will break
- 🟡 Important - needed soon but not blocking
- 🟢 Nice to Have - low urgency
- ⚫ Deferred - consciously parked, revisit later

---

## Open

### THREAD-034 🟡 — Two parallel BOST/APEX_ENTITY sessions found un-logged in agents_history
- **Opened:** 2026-09-10
- **Session:** 2026-09-10_001
- **Priority:** 🟡 Important
- **File(s):** `BOST\alias_operation_registry.csv`, `BOST\definition_registry_process_defn.csv`, `BOST\definition_registry_treatment_rules.csv`, `BOST\step4_treatment_rules_pilot.py`, `BOST\registry\diag_track_a_vs_track_b.py`, `BOST\docs\`, `BOST\archive\`, `WDS\APEX_ENTITY\`
- **Summary:** End-of-session directory listings surfaced two substantial bodies of work in this workspace that were never logged in `agents_history`: (1) a "BOST Enrichment Registry -- Dual-Track Implementation" session (Track A process-definition registry + Track B treatment rules, plus an archive reorganization that moved this session's diagnostic scripts into `BOST\archive\old_diag_scripts\`), and (2) a separate "APEX_ENTITY Enrichment" session under `WDS\APEX_ENTITY\` (numbered scripts 01-10, handoff doc, README). Neither has a session log, index row, or file_map entries.
- **Details:**
  - Confirmed via session-store search (session IDs `a89ff76a-...` for the BOST dual-track work and `a31810c8-...` for APEX_ENTITY) that these are real, separate conversations, not fabricated.
  - Do not claim credit for this work in future BOST-related logs; it needs its own retroactive session log(s).
- **Status:** Partially resolved 2026-09-14_003 — the WDS/APEX_ENTITY half is now captured in a formal checkpoint log; the BOST dual-track half still needs its own retroactive log.
- **Re-entry prompt:**
  > "Two un-logged parallel sessions exist in this workspace: a BOST 'Dual-Track Implementation' (Track A process-defn registry + Track B treatment rules, under `BOST\` including `alias_operation_registry.csv`, `definition_registry_process_defn.csv`, `definition_registry_treatment_rules.csv`, `step4_treatment_rules_pilot.py`, `BOST\archive\`, `BOST\docs\`) and a separate 'APEX_ENTITY Enrichment' session under `WDS\APEX_ENTITY\`. Write retroactive session logs for both, following the retroactive logging workflow in `AGENT_RULES.md`."

### ~~THREAD-034~~ ✅ RESOLVED — Two parallel BOST/APEX_ENTITY sessions found un-logged in agents_history
- **Resolved:** 2026-09-14_003 (WDS/APEX_ENTITY half)
- **Session:** 2026-09-10_001 and 2026-09-14_003
- **Summary:** The WDS/APEX_ENTITY unlogged-session gap has been captured in a formal checkpoint log. The remaining BOST dual-track half still needs its own retroactive session log.
- **Details:**
  - The APEX_ENTITY enrichment history now has a checkpoint entry at `2026-09-14_003`.
  - Keep THREAD-034 open only for the BOST dual-track half until that log is written.

### THREAD-035 🟢 — User's planned separate enrichment work across the same 10 full-flow aliases
- **Opened:** 2026-09-10
- **Session:** 2026-09-10_001
- **Priority:** 🟢 Nice to Have
- **File(s):** `BOST\step3_wide_table_build.py`, `BOST\BOST_ENRICHMENT_REGISTRY_PLAN.md`
- **Summary:** The user stated they will separately enrich other items across the same 10 full-flow aliases (e.g. tool/chamber columns from a separate query), but this was not started in this conversation.
- **Details:**
  - No scope or design has been captured yet for this follow-on enrichment.
- **Re-entry prompt:**
  > "The user planned to separately enrich additional items (e.g. tool/chamber columns) across the same 10 full-flow BOST aliases used in `BOST\step3_wide_table_build.py`. Ask for the specific scope before starting."

### THREAD-036 ⚫ — decoder_client cannot recover Treatment Rule data; ask Dave/Kahtan directly
- **Opened:** 2026-09-12
- **Session:** 2026-09-12_001
- **Priority:** ⚫ Deferred
- **File(s):** `BOST2\DECODER_CLIENT_STATUS.md`, `BOST2\pilot_decoder_client_coverage.py`, `dev\wds-decoder-cache\loader\ingest.py`, `WDS\decoder_client_comms\DG_email.txt`, `WDS\decoder_client_comms\DG_Teams.txt`
- **Summary:** Triple-confirmed (source code, Dave Gaibler's own comparison harness, live pilot query) that `decoder_client`'s WDS cache only ever ingests `B_WAFER_PROCESS_DEFN` (old system) and contains zero data for Treatment-Rule-migrated definitions. Not a viable path to close the BOST coverage gap as of the `main` branch commit `faa8a41` (2026-09-08). Parked, not abandoned, per Dave's email ("we are just finalizing that utility").
- **Details:**
  - Live pilot against 5 known-problem wafers: `GQ1KC483JKB3` returned 0/2621 populated columns; `EQUIP:AMECT_LINERS`, `EQUIP:AMECT_LIDS`, `EQUIP:HRVA_LEOCB_1278`, `PROCESS:80P_ROADRUNNER` etc. do not appear as columns at all.
  - Isolated venv (`WDS\venv_decoder_client\`) and vendored clone (`dev\wds-decoder-cache\`) are left in place for a future re-test at low cost.
- **Re-entry prompt:**
  > "Ask Dave Gaibler or Kahtan Al Jewary directly whether decoder_client's `loader` has been (or will be) extended to ingest `B_WAFER_TREATMENT_DATA_V`/`B_WAFER_TREATMENT_RULES`. If yes, re-run `BOST2\pilot_decoder_client_coverage.py` (venv already set up at `WDS\venv_decoder_client\`) against the same known-problem wafers to re-validate. See `BOST2\DECODER_CLIENT_STATUS.md` for full context."

### ~~THREAD-037~~ ✅ RESOLVED — BOST dry-run coverage gap (LOT-vs-WAFER_ID join key)
- **Opened:** 2026-09-12
- **Resolved:** 2026-09-12
- **Session:** 2026-09-12_001 through 2026-09-12_002 (query-level unit tests + two fix rounds)
- **Summary:** The actual root cause turned out to be different from the originally-suspected
  `_extract_def_name_from_track_b()`/`_normalize_layer_agnostic_definition()` collision bug (that
  code path was already neutralized in an earlier refactor). Query-level diagnostics proved the
  real issue was the pipeline joining Track A/Track B BOST data back to the input on `LOT` text,
  while a wafer's LOT designation can legitimately change between operations/systems (tool-error
  rework, process-development splits/merges) even though the physical wafer never changes. Two
  fix attempts (LOT7-alias fix, then a `[:8]` fixed-width normalization) each closed part of the
  gap but left a residual mismatch, until the join was switched to `WAFER_ID + LAYER` only (LOT
  kept for output/display, dropped from the merge key). Final full-pipeline run confirmed
  `1142/1142 matched, 0 unmatched, match_rate=1.0`, independently reproduced by a standalone
  diagnostic extractor script.
- **Details:**
  - Full write-up and diagnostic scripts: `BOST\docs\HANDOFF_120_GAP_LOT7_JOIN_FIX.md`,
    `BOST\registry\diag_extract_unmatched_120_keys.py`,
    `BOST\registry\diag_unmatched_gap_query_probe.py`,
    `BOST\registry\diag_round2_gap_classification.py`.
  - Domain takeaway worth reusing elsewhere: any BE/BOST script that joins wafer-level data across
    operations/systems by LOT text should be treated as suspect for this same class of bug —
    WAFER_ID (physical wafer serial) is the stable join key, not LOT in any form.

### THREAD-028 🟡 — Decide whether the canonical v9 generic-description probe should become the default production prompt/config everywhere it is invoked
- **Opened:** 2026-09-06
- **Session:** 2026-09-06_001
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\config\generic_description_prompt_v9.json`, `images\Alloy_Class\reporting\build_generic_description_html_report.py`, `images\Alloy_Class\tools\probe_generic_description.py`, `images\Alloy_Class\tools\build_small_particle_raw_cache.py`, `outputs\defects\DEFECT_COORDINATES_EXTENDED.csv`, `BE_QUERY_FILES\DEFECT_COORDINATES_RECLASS_LOG.csv`
- **Summary:** The generic-description probe is now anchored on the v9 prompt config, the production coordinate enrichment plus reclass fallback path is in place, and the HTML report layout has been adjusted to show the case-id plus description in the title cell with the outer Case Review wrapper removed. A 30-case validation run completed successfully, but the remaining decision is whether to make this the default probe/report path everywhere it is invoked.
- **Details:**
  - The layout change appears ready, but promotion should be deliberate rather than implicit.
  - If the prompt/config is promoted, downstream call sites and any documentation that still imply the older probe state may need a follow-up sweep.
- **Re-entry prompt:**
  > "Review the generic-description probe and HTML report flow after the successful 30-case validation. Decide whether the v9 prompt config should become the default everywhere the probe is invoked, and if so, update any call sites or docs that still point at the older probe state."

### THREAD-029 🟡 — Decide whether to continue with chunked/incremental VLM submission or move to Step 3's filterable HTML feedback portal
- **Opened:** 2026-09-07
- **Session:** 2026-09-07_001
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\docs\HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md`, `images\Alloy_Class\tools\enrich_production_with_vlm_attributes.py`
- **Summary:** Step 2 enrichment now has a populated `truth_alignment_state` column, the handoff note has been cleaned up, and the next logical branch is intentionally left open: either design chunked/incremental VLM submission or move on to Step 3's filterable HTML feedback portal.
- **Details:**
  - The checkpoint records both the enrichment semantics and the handoff cleanup.
  - The next step should be chosen deliberately rather than implied by the handoff.
- **Re-entry prompt:**
  > "Review the current Step 2 truth-alignment enrichment state and the cleaned handoff note, then decide whether to continue with chunked/incremental VLM submission or move to Step 3's filterable HTML feedback portal."

### THREAD-030 🟡 — Align documentation and handoff text to the registry-preserving generic-description artifact
- **Opened:** 2026-09-09
- **Session:** 2026-09-09_001
- **Priority:** 🟡 Important
- **File(s):** `images\Alloy_Class\tools\consolidate_generic_description_registry.py`, `images\Alloy_Class\docs\HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md`
- **Summary:** The registry-preserving rewrite of the generic-description consolidation script is the validated canonical artifact, the processed registry row count is 806, and the earlier 10,895-row production-expansion result was rejected as the wrong target. The remaining handoff task is to make sure documentation points at the registry-preserving artifact rather than the failed left-join variant.
- **Details:**
  - Keep the 806-row processed-registry result as the checkpoint reference state.
  - Preserve the enriched-column set in the handoff so future agents do not regress to the wrong output shape.
- **Re-entry prompt:**
  > "Update the Alloy generic-description handoff so it points at the registry-preserving consolidation artifact in `images\\Alloy_Class\\tools\\consolidate_generic_description_registry.py`, not the rejected 10,895-row production-expansion variant. Keep the validated 806-row processed registry and the enriched CSV column set as the canonical state."

### THREAD-031 🟢 — Decide whether the 4 filtered VLM report subsets should become a recurring/persistent Step 3 artifact
- **Opened:** 2026-09-09
- **Session:** 2026-09-09_004
- **Priority:** 🟢 Nice to Have
- **File(s):** `images\Alloy_Class\tools\consolidate_generic_description_registry.py`, `.github\prompts\planStep3VlmHtmlReports.prompt.md`
- **Summary:** `consolidate_generic_description_registry.py` already produces 4 filtered CSV+HTML subset reports (circle, `defect_count_gt1`, `truth_alignment_state=mismatched`, `current_reclass != SMALL_PARTICLE`) as one-off test-run artifacts under `C:\RAW_IMAGES\generic_description_registry\generic_description_consolidated_v9_test3\generic_description_v9_enriched\`. These overlap conceptually with the separately-planned Step 3 filterable HTML feedback portal. Decide whether to fold this ad-hoc filtering into that planned portal, or keep it as a lightweight recurring script output.
- **Details:**
  - Verified these 4 report files genuinely exist and are non-hollow (confirmed 2026-09-09_004).
  - Step 3's portal plan (`planStep3VlmHtmlReports.prompt.md`) already covers filtering/cohort views more generally; this thread is about not duplicating that work.
- **Re-entry prompt:**
  > "Review the 4 filtered subset reports already produced by `consolidate_generic_description_registry.py` and decide whether to fold this filtering approach into the planned Step 3 portal (`planStep3VlmHtmlReports.prompt.md`) or keep it as a separate recurring script."

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
| THREAD-032 | BOST Aug 28 coverage cutoff | 2026-09-10 | 2026-09-10_002 | Source data gap confirmed as legitimate; 146 empty wafers have zero BOST definitions in source system; not a pipeline defect |
| THREAD-033 | BOST registry design items | 2026-09-10 | 2026-09-10_002 | BOST dual-track schema validated and aligned; definition name format conversion implemented; definition_type column infrastructure ready for future use |
