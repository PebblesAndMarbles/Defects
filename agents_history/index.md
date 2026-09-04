# Agent Session Index

**Workspace:** BE Defects Workspace
**Last Updated:** 2026-09-04 (session log for 2026-09-04_001)

---

## Active Open Threads (Master List)
These are unresolved items pulled from individual session logs.
Update this manually when a thread is resolved.

| Thread | Opened | Session | Status | Notes |
|--------|--------|---------|--------|-------|
| THREAD-001 | 2026-08-08 | 2026-08-08_002 | Open | `build_benchmark_candidates.py` not yet built; scope doc exists |
| THREAD-002 | 2026-08-08 | 2026-08-08_002 | Open | Manifest metadata backfill lag — SUBENTITY/LOT7/coords null for recent rows |
| THREAD-003 | 2026-08-09 | 2026-08-09_002 | Resolved | Closed 2026-08-10_001 — template updated to 44 cols; schema doc updated |
| THREAD-004 | 2026-08-09 | 2026-08-09_002 | Resolved | Closed 2026-08-10_001 — 1595 cells normalized; 0 unrecognized values |
| THREAD-005 | 2026-08-10 | 2026-08-10_001 | Open | Texture reference snip — multi-image Stage B pipeline support needed for v4 |
| THREAD-005 | 2026-08-11 | 2026-08-11_001 | Resolved | Closed 2026-08-11_001 — backend accepts `images: [b64, b64]`; multi-image Stage B pilot succeeded |
| THREAD-006 | 2026-08-10 | 2026-08-10_001 | Open | BC check detection gap — bc fires 6/32; 16+ missed with adjudicated cbl=yes |
| THREAD-007 | 2026-08-10 | 2026-08-10_001 | Open | Stage A confounder language may suppress isl detection in Stage B |
| THREAD-008 | 2026-08-10 | 2026-08-10_001 | Open (Deferred) | sr detection ceiling — 0% firing rate; deprioritization under consideration |
| THREAD-009 | 2026-08-10 | 2026-08-10_001 | Open | BMK_0037 relabeling question — user to review image before next benchmark run |
| THREAD-011 | 2026-08-26 | 2026-08-26_003 | Open | v13 describe-then-classify architecture validated but NOT promoted to production default — deferred to user |
| THREAD-012 | 2026-08-26 | 2026-08-26_003 | Open | Phase 5 consolidated external-facing report (3 questions to Alloy codebase owners) never finalized/sent |
| THREAD-013 | 2026-08-26 | 2026-08-26_003 | Open | BMK_0008 root cause not investigated beyond "known accepted edge case" |
| THREAD-014 | 2026-08-26 | 2026-08-26_003 | Open | Mid-sentence-truncation empty-response variant never reproduced in instrumented Phase 1 data |
| THREAD-015 | 2026-08-26 | 2026-08-26_003 | Open (Deferred) | score_benchmark_run.py boolean False review_required mis-flagged as missing (minor, out of scope) |
| THREAD-016 | 2026-08-08 | 2026-08-08_012 | Open | Build per-class truth table for BEEP/SMALL_PARTICLE showing exact expected EDI vs NCDD values across row cases |
| THREAD-017 | 2026-08-08 | 2026-08-08_012 | Open | Locate EDI WIJT JSL config on remote scheduler; decide if a local copy should be pulled for documentation |
| THREAD-018 | 2026-08-27 | 2026-08-27_001 | Open (Major) | Fundamental FP/FN trade-off unresolved across V11-derived and from-scratch lexicon prompt lineages |
| THREAD-019 | 2026-08-29 | 2026-08-27_001 | Open | v1 -> v2 lexicon FP-rate regression (0.385 -> 0.538) not yet case-level diagnosed |
| THREAD-020 | 2026-08-29 | 2026-08-27_001 | Open | User has not yet reviewed v2 HTML report or submitted portal feedback on it |
| THREAD-021 | 2026-08-30 | 2026-08-27_001 | Open | Strategic pivot decision (manual disposition + decoupled fine-bin VLM tagging) pending user confirmation |
| THREAD-022 | 2026-08-30 | 2026-08-27_001 | Open | Litho-scanner metadata correlation unconfirmed; no existing join found in BE_QUERY_FILES |
| THREAD-023 | 2026-08-30 | 2026-08-27_001 | Open | PM-counter part-installation granularity unconfirmed (cumulative counts vs. discrete swap events) |
| THREAD-024 | 2026-08-28 | 2026-08-27_001 | Open | Alloy VLM truncated/empty responses at 1800-token budget (workaround only, not root-caused) |
| THREAD-025 | 2026-08-27 | 2026-08-27_001 | Open | Model non-determinism on borderline/duplicate test cases (BMK_0008, BMK_0011) |
| THREAD-026 | 2026-08-31 | 2026-08-31_001 | Open | Decide whether to wire the direct INSP_ELEMENT EDX join into the OX pilot pipeline now, or hold off until imaging scope is defined |
| THREAD-027 | 2026-09-04 | 2026-09-04_001 | Open | Optional cleanup: remove dead inline-style code paths or adjust the progress-message wording in `images\Alloy_Class\tools\build_small_particle_raw_cache.py` |

---

## Session Log

| Session ID | Date | Title | Status | Key Files Touched | Open Threads |
|------------|------|-------|--------|-------------------|-------------|
| 2026-06-20_001 | 2026-06-20 | YPO Status Rollup and Audit Output Build | complete | `rollups\YPO_STATUS.py`, `rollups\YPO\YPO_STATUS.csv`, `rollups\YPO\YPO_STATUS_AUDIT.csv` | (none) |
| 2026-07-26_001 | 2026-07-26 | Alloy Phase 1 Transient Raw Validation and Runtime Hardening | complete | `images\Alloy_Class\pipelines\classify_phase1_batch.py`, `images\Alloy_Class\docs\PHASE1_RUNBOOK.md`, `images\Alloy_Class\docs\PHASE1_ACCEPTANCE_CHECKLIST.md`, `images\Alloy_Class\tools\wheelhouse_audit.py` | (none) |
| 2026-07-26_002 | 2026-07-26 | Runtime Optimization for 1-Pair Alloy Phase 1 Pipeline | complete | `images\Alloy_Class\pipelines\classify_phase1_batch.py`, `images\Alloy_Class\pipelines\caption_phase1_batch.py`, `images\Alloy_Class\reporting\build_phase1_html_report.py`, `images\Alloy_Class\docs\HANDOFF_PROMPT_ITERATION_1PAIR_RUNTIME.md` | (none) |
| 2026-07-28_001 | 2026-07-28 | Ad Hoc LOT Query Framework Implementation + HTML Report Validation | complete | `rollups\adhoc_inline_images\query_lot_all_images.py`, `rollups\adhoc_inline_images\generate_lot_html_report.py`, `rollups\adhoc_inline_images\README_USAGE.md` | (none) |
| 2026-08-08_001 | 2026-08-08 | Session Logger Agent Deployment | complete | `agents_history\AGENT_RULES.md`, `agents_history\index.md`, `agents_history\file_map.md`, `agents_history\open_threads.md`, `agents_history\sessions\_template.md` | (none) |
| 2026-08-08_002 | 2026-08-04 | Inline HTML Reports Infrastructure Build + Benchmark Candidate Tool Scope | complete | `html\INLINE_CHAMBER_EVENT_REPORT.py`, `html\INLINE_PRODUCTION_SUBENTITY_REPORTS.py`, `BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py`, `docs\FLEET.txt`, `html\INLINE_HTML_REPORT_PATTERNS.md`, `images\Alloy_Class\docs\BENCHMARK_CANDIDATE_TOOL_SCOPE.md` | THREAD-001, THREAD-002 |
| 2026-08-08_003 | 2026-08-08 | Defect Metadata Schema Cleanup + ScriptHost Parity Unblock | complete | `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py`, `BE_QUERY_FILES\backfill_vlm_metadata.py`, `BE_QUERY_FILES\metadata_explorer.py`, `images\Alloy_Class\metadata\build_defect_size_metadata.py` | (none) |
| 2026-08-08_004 | 2026-08-08 | VLM Metadata Backfill + UNKNOWN Image Folder Bug Fix | complete | `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py`, `outputs\defects\DEFECT_COORDINATES_EXTENDED.csv`, `outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv`, `BE_QUERY_FILES\cleanup_unknown_images.py` | (none) |
| 2026-08-08_005 | 2026-08-08 | Design Doc Reorganization — Tiered Inline + Surf Scan Pipeline Docs | complete | `INLINE_PIPELINE_DESIGN.md`, `SURF_SCAN_PIPELINE_DESIGN.md`, `DESIGN_INDEX.md`, `docs\inline_pipeline\`, `docs\surf_scan_pipeline\` | (none) |
| 2026-08-08_006 | 2026-08-08 | EMSA EDX Spectrum Access — Investigation and Summary | complete | `docs\EMSA_ACCESS.md`, `SURF_SCAN_PIPELINE_DESIGN.md`, `BE_QUERY_FILES\surf_scan_images.py` | (none) |
| 2026-08-08_007 | 2026-07-14 | SS Inline Chamber Report Build + Fleet Run | complete | `html\SS_INLINE_CHAMBER_REPORT.py`, `html\SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py`, `html\SS_CHAMBER_EVENT_REPORT.py`, `debug_logs\SS_IMAGE_CROSS_CHAMBER_ROUTING_BUG.md` | (none) |
| 2026-08-08_008 | 2026-07-09 | Inline HTML Reports — Robustness Fixes and Fleet Hard-coding | complete | `html\INLINE_CHAMBER_EVENT_REPORT.py`, `html\INLINE_PRODUCTION_SUBENTITY_REPORTS.py`, `BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py` | (none) |
| 2026-08-08_009 | 2026-08-08 | Workspace Cleanup Inventory + BE_QUERY_FILES Reorganization | complete | `artifacts\workspace_cleanup_inventory.csv`, `dev\classify_be_query_files_pipeline_membership.py`, `artifacts\be_query_files_pipeline_membership.csv`, `BE_QUERY_FILES\utils\` | (none) |
| 2026-08-08_010 | 2026-07-07 | CLASS_BEEP=UNKNOWN Fix + EDI Backfill + Weekly Zero-Rate Aggregator + Workweek Columns | complete | `BE_QUERY_FILES\modular_processor\EXTEND_BENCHMARK.py`, `BE_QUERY_FILES\EDI_BACKFILL.py`, `BE_QUERY_FILES\WEEKLY_ZERO_RATE_AGGREGATOR.py`, `BE_QUERY_FILES\BACKFILL_WORKWEEK_COLUMNS.py` | (none) |
| 2026-08-08_011 | 2026-08-08 | PRE-Only 2026 Adhoc Coordinates Pull + Dirtiest Wafer Summary | complete | `rollups\PREvsPST\pre_only_coords_2026_long.csv`, `rollups\PREvsPST\pre_only_coords_2026_wafer_summary.csv`, `rollups\PREvsPST\pre_vs_pst_2026_only_input.csv` | (none) |
| 2026-08-08_012 | 2026-08-08 | GAJT/WIJT EDI vs NCDD Metric Comparison — Forensic Analysis | complete | `debug_logs\8M5CL_NCDD.log`, `debug_logs\ediQuery#306.log`, `BE_QUERY_FILES\8M5CL_NCDD_SHORT.jsl`, `BE_QUERY_FILES\8M6CL_NCDD_SHORT.jsl` | THREAD-016, THREAD-017 |
| 2026-08-08_013 | 2026-08-08 | SS Manifest Discrepancy Investigation + Fixes + Post-Fix Audit | complete | `BE_QUERY_FILES\surf_scan_images.py`, `BE_QUERY_FILES\surf_scan_update.py`, `BE_QUERY_FILES\reconcile_prune_images.py` | (none) |
| 2026-08-09_001 | 2026-08-09 | Substrate Prompt Tier Test Campaign — 20-Image Raw Run + Ground Truth Schema | complete | `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`, `images\Alloy_Class\reporting\build_stage_ab_html_report.py`, `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v1.json`, `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier2_v1.json`, `images\Alloy_Class\docs\PLAN_SUBSTRATE_PROMPT_TEST_20_IMAGES.md`, `images\Alloy_Class\docs\SUBSTRATE_PROMPT_TIER20_RESULTS.md` | THREAD-020, THREAD-021, THREAD-022, THREAD-023, THREAD-024 |
| 2026-08-09_002 | 2026-08-09 | Alloy Benchmark CSV Workflow + Adjudication Schema Simplification + UNC Publish | complete | `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv`, `images\Alloy_Class\docs\BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md`, `images\Alloy_Class\docs\ADJUDICATION_WORKSHEET_ONE_PAGER.md`, `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv.pre_local_copy_20260809_195242.bak` | THREAD-003, THREAD-004 |
| 2026-08-10_001 | 2026-08-09 | Alloy VLM Prompt Engineering — Benchmark Readiness, Labeling Consistency, Baseline + v2/v3 Prompt Iteration, NBC52 Scale Run | complete | `images\Alloy_Class\tools\normalize_benchmark_adjudication.py`, `images\Alloy_Class\tools\run_benchmark_vlm.py`, `images\Alloy_Class\tools\score_benchmark_run.py`, `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv`, `images\Alloy_Class\artifacts\benchmark_pairs_v1.csv`, `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v2.json`, `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v3.json`, `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | THREAD-005, THREAD-006, THREAD-007, THREAD-008, THREAD-009 |
| 2026-08-11_001 | 2026-08-11 | Alloy Multi-Image VLM Pilot and Checkpoint | complete | `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`, `agents_history\sessions\2026-08-11_001_alloy-multi-image-vlm-pilot-and-checkpoint.md` | THREAD-006, THREAD-007, THREAD-008, THREAD-009 |
| 2026-08-11_002 | 2026-08-11 | Alloy VLM Stage A/B BF-Only Checkpoint | complete | `agents_history\sessions\2026-08-11_002_alloy-vlm-stage-ab-bf-only-bfdf-scoring-checkpoint.md` | THREAD-006, THREAD-007, THREAD-008, THREAD-009 |
| 2026-08-11_003 | 2026-08-11 | Alloy Prompt Iteration Registry Checkpoint | complete | `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md`, `images\Alloy_Class\artifacts\prompt_iteration_registry.csv` | THREAD-010 |
| 2026-08-11_004 | 2026-08-11 | Alloy Prompt Bundle Provenance Checkpoint | complete | `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`, `images\Alloy_Class\tools\run_benchmark_vlm.py`, `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md` | THREAD-010 |
| 2026-08-27_001 | 2026-08-27 | BEEP Lexicon V1/V2 Rewrite, Feedback Portal Rollout, and Strategic Pivot Tooling Inventory | partial | `agents_history\sessions\2026-08-27_001_beep-lexicon-v1-v2-and-strategic-pivot-inventory.md`, `images\Alloy_Class\tools\probe_describe_then_classify_v14.py`, `images\Alloy_Class\tools\probe_beep_lexicon_v1.py`, `images\Alloy_Class\tools\probe_beep_lexicon_v2.py`, `images\Alloy_Class\BEEP_Evidence copy.txt`, `images\Alloy_Class\BEEP_Evidence copy 2.txt`, `images\Alloy_Class\docs\TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md` | THREAD-018, THREAD-019, THREAD-020, THREAD-021, THREAD-022, THREAD-023, THREAD-024, THREAD-025 |
| 2026-08-15_001 | 2026-08-15 | Alloy Claude Sonnet 4.6 Offset Surface Lines Recall Checkpoint | partial | `agents_history\sessions\2026-08-15_001_alloy-claude-sonnet-4-6-offset-surface-lines-recall-checkpoint.md`, `images\Alloy_Class\config\stage_ab_prompt_tests_smoke_v7_claude_sonnet_4_6_min.json`, `images\Alloy_Class\config\stage_ab_prompt_tests_offset_surface_lines_15_claude_sonnet_4_6.json`, `images\Alloy_Class\artifacts\benchmark_offset_surface_lines_yes_15.csv` | (none) |
| 2026-08-18_001 | 2026-08-18 | INLINE Mismatch Backfill Handoff Checkpoint | partial | `agents_history\sessions\2026-08-18_001_inline-mismatch-backfill-handoff-checkpoint.md`, `rollups\INLINE_MISMATCHES\INLINE_MISMATCH_BACKFILL_HANDOFF.md`, `rollups\INLINE_MISMATCHES\inline_mismatch_distribution.py` | (none) |
| 2026-08-18_002 | 2026-08-18 | Defect Reclassification Mismatch Audit Checkpoint | partial | `agents_history\sessions\2026-08-18_002_defect-reclassification-mismatch-audit-checkpoint.md` | (none) |
| 2026-08-26_001 | 2026-08-26 | Alloy VLM V11/V12 Benchmark Comparison Checkpoint | complete | `agents_history\sessions\2026-08-26_001_alloy-vlm-v11-v12-benchmark-comparison-checkpoint.md`, `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v11.json`, `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v12.json`, `images\Alloy_Class\tools\run_benchmark_vlm.py`, `images\Alloy_Class\artifacts\benchmark_offset_surface_lines_yes_15.csv` | THREAD-001, THREAD-002, THREAD-005, THREAD-006, THREAD-007, THREAD-008, THREAD-009 |
| 2026-08-26_002 | 2026-08-26 | Alloy VLM FN Feature-Perception Probe Checkpoint | complete | `agents_history\sessions\2026-08-26_002_alloy-vlm-fn-feature-perception-probe-checkpoint.md`, `images\Alloy_Class\tools\probe_fn_feature_perception.py`, `images\Alloy_Class\outputs\probes\fn_baseline_v12.json`, `images\Alloy_Class\outputs\probes\fn_feature_probe_consolidated.jsonl`, `images\Alloy_Class\docs\v12_post_mortem.md` | THREAD-001, THREAD-002, THREAD-006, THREAD-007, THREAD-008, THREAD-009 |
| 2026-08-26_003 | 2026-08-26 | Alloy VLM V13 Describe-Then-Classify Diagnostics + Production Promotion Checkpoint | complete | `agents_history\sessions\2026-08-26_003_alloy-vlm-v13-describe-then-classify-diagnostics-checkpoint.md`, `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`, `images\Alloy_Class\tools\probe_describe_then_classify.py`, `images\Alloy_Class\tools\run_benchmark_vlm.py`, `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v13.json`, `images\Alloy_Class\docs\v12_post_mortem.md`, `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md` | THREAD-001, THREAD-002, THREAD-006, THREAD-007, THREAD-008, THREAD-009, THREAD-011, THREAD-012, THREAD-013, THREAD-014, THREAD-015 |
| 2026-08-26_004 | 2026-08-26 | Agent Logging System Health Audit and Reconciliation | complete | `agents_history\sessions\2026-08-26_004_agent-logging-system-health-audit-and-reconciliation.md`, `agents_history\index.md`, `agents_history\file_map.md`, `agents_history\open_threads.md`, `agents_history\sessions\2026-08-18_002_defect-reclassification-mismatch-audit-checkpoint.md` | THREAD-016, THREAD-017 |
| 2026-08-31_001 | 2026-08-31 | 1K OX SurfScan Pilot Pipeline Build + EDX LAYER_ID Investigation | partial | `agents_history\sessions\2026-08-31_001_1k-ox-surfscan-pilot-pipeline-and-edx-layer-id-investigation.md`, `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_config.py`, `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_coordinates.py`, `rollups\1K_OX_PILOT_PIPELINE\run_seed.py`, `rollups\1K_OX_PILOT_PIPELINE\run_update.py`, `rollups\1K_OX_PILOT_PIPELINE\scope_1k_ox_smoke_test.py`, `rollups\1K_OX_PILOT_PIPELINE\probe_edx_layer_id_v4.py` | THREAD-026 |
| 2026-09-04_001 | 2026-09-04 | Small Particle Raw Cache Flat RAW_IMAGES Checkpoint | complete | `images\Alloy_Class\tools\build_small_particle_raw_cache.py`, `agents_history\sessions\2026-09-04_001_small-particle-raw-cache-flat-raw-images-checkpoint.md` | THREAD-027 |
| 2026-09-04_002 | 2026-09-04 | Repo Hygiene Ignore and Untrack Checkpoint | complete | `agents_history\sessions\2026-09-04_002_repo-hygiene-ignore-and-untrack-checkpoint.md` | (none) |
| 2026-08-26_005 | 2026-08-26 | Alloy VLM Particle-25 FP Share Pack Checkpoint | complete | `agents_history\sessions\2026-08-26_005_alloy-vlm-particle25-fp-share-pack-checkpoint.md`, `images\Alloy_Class\docs\iGPT_v13_next_step.md`, `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v13_particle25.json`, `images\Alloy_Class\artifacts\iGPT_v13_FN_plan_rows.csv`, `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\scoring\benchmark_particle25_v13_fp21_share.jsonl` | THREAD-011, THREAD-012, THREAD-013, THREAD-014, THREAD-015 |

---

## Quick Reference: Sessions by Topic
Manually group sessions as patterns emerge.

### Logging System / Meta
- `2026-08-08_001` — Session Logger Agent Deployment (initial scaffolding, all agents_history files created)

### Inline HTML Reports Pipeline
- `2026-08-08_002` — Full build of INLINE_CHAMBER_EVENT_REPORT.py, fleet batch runner, RECENT_LOTS_7D bug fixes (5 bugs resolved)

### Benchmark Candidate Tool
- `2026-08-08_002` — Scope document created; build task is THREAD-001

### VLM Prompt Engineering (Alloy/Substrate)
- `2026-08-09_001` — Substrate prompt tier test campaign; 20-image raw run; ground truth schema
- `2026-08-09_002` — Benchmark CSV workflow; adjudication schema simplification; UNC publish
- `2026-08-10_001` — Benchmark readiness (normalize, split, freeze); v1/v2/v3 prompt iteration on pilot12; NBC52 scale run (31% recall, 30% FP); 5 open threads opened (THREAD-005 through THREAD-009)
- `2026-08-11_001` — Multi-image VLM pilot; direct `images` payload validated; THREAD-005 resolved
- `2026-08-11_002` — BF-only Stage A / BF+DF Stage B benchmark checkpoint; corrected NBC52 run succeeded; frozen scoring and earlier comparison scoring completed
- `2026-08-15_001` — Claude Sonnet 4.6 smoke test and 15-row offset-surface-lines recall slice; evidence-aware scoring path validated; recall = 1/15
- `2026-08-26_001` — V11/V12 Stage B prompt comparison on the 15-pair offset-surface-lines slice; V11 retained as safer baseline
- `2026-08-26_002` — FN feature-perception probe on the 5 known FN cases; found the failure is likely prompt/architecture framing overhead, not a visual-perception ceiling; reverses ROI priority in `v12_post_mortem.md`
- `2026-08-27_001` — v14 patch of the V11-derived Call 2 prompt (boundary-ownership fixes, Pathway 5); confirmed a fundamental FP/FN trade-off persists; abandoned the V11 lineage in favor of a fresh minimal plain-lexicon spec and single-call architecture (v1 -> v2); built and validated the generic scorer/HTML/feedback-portal pipeline; authored a tooling inventory to inform a proposed strategic pivot to manual disposition + decoupled fine-bin VLM tagging
- `2026-08-26_003` — Describe-then-classify (V11-derived Call 2) architecture validated on the 15-pair offset-surface-lines benchmark: beep_fn_rate 0.3571 -> 0.0; max-token hypothesis confirmed as a real contributing cause of empty responses; promoted into the production runner behind a new CLI flag but not yet made the default

### 1K OX SurfScan Pilot / EDX
- `2026-08-31_001` — Scoped and built a standalone "1K OX SurfScan" pilot pipeline (`LAYER_ID=6OX450GTO_M025_PST`) under `rollups\1K_OX_PILOT_PIPELINE\`, not wired into production; fixed PM RF counter and pilot-status bugs; resolved an EDX LAYER_ID question for lot D629T8V0 by confirming `UDB.INSP_ELEMENT` already joins directly to the original UDE scan
