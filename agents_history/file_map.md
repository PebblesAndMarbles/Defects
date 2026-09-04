# File Modification Map

**Workspace:** BE Defects Workspace
**Last Updated:** 2026-09-04 (session log for 2026-09-04_001)

---

## How to Read This
- **Last Session** = most recent session that touched this file
- **All Sessions** = full history, oldest to newest
- **Status** = current known state of the file

| File (relative path) | Last Session | All Sessions | Status | Notes |
|----------------------|-------------|--------------|--------|-------|
| `.github\agents\session_logger.agent.md` | 2026-08-08_001 | 2026-08-08_001 | Active | Agent definition; requires VS Code reload to register |
| `agents_history\AGENT_RULES.md` | 2026-08-08_001 | 2026-08-08_001 | Active | Placeholders filled for this workspace |
| `agents_history\SESSION_KICKOFF.md` | 2026-08-08_001 | 2026-08-08_001 | Active | Paste-ready session start prompt |
| `agents_history\checkpoint_prompt.md` | 2026-08-08_001 | 2026-08-08_001 | Active | Paste-ready checkpoint prompt |
| `agents_history\index.md` | 2026-08-08_001 | 2026-08-08_001 | Active | Master session index |
| `agents_history\file_map.md` | 2026-08-08_001 | 2026-08-08_001 | Active | File modification map |
| `agents_history\open_threads.md` | 2026-08-08_001 | 2026-08-08_001 | Active | Thread registry; no threads yet |
| `agents_history\sessions\_template.md` | 2026-08-08_001 | 2026-08-08_001 | Active | Session log template |
| `agents_history\sessions\2026-08-08_001_session-logger-deployment.md` | 2026-08-08_001 | 2026-08-08_001 | Active | First session log |
| `html\INLINE_CHAMBER_EVENT_REPORT.py` | 2026-08-08_002 | 2026-08-08_002 | Active | Core single-chamber inline defect HTML report generator; pure SVG wafermaps |
| `html\INLINE_PRODUCTION_SUBENTITY_REPORTS.py` | 2026-08-08_002 | 2026-08-08_002 | Active | Fleet batch runner (51 chambers) + recent-lots report |
| `BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py` | 2026-08-08_002 | 2026-08-08_002 | Active | Added `_run_inline_html_reports` post-step |
| `docs\FLEET.txt` | 2026-08-08_002 | 2026-08-08_002 | Active | 51 chambers, one per line, `#` comment header |
| `html\INLINE_HTML_REPORT_PATTERNS.md` | 2026-08-08_002 | 2026-08-08_002 | Active | Implementation reference doc for inline HTML reports |
| `images\Alloy_Class\docs\BENCHMARK_CANDIDATE_TOOL_SCOPE.md` | 2026-08-08_002 | 2026-08-08_002 | Active | Scope doc for build_benchmark_candidates.py (THREAD-001) |
| `agents_history\sessions\2026-08-08_002_inline-html-reports-build-and-benchmark-scope.md` | 2026-08-08_002 | 2026-08-08_002 | Active | Session log for inline HTML reports build |
| `agents_history\sessions\2026-08-09_001_substrate-prompt-tier-test-20-image-raw-run.md` | 2026-08-09_001 | 2026-08-09_001 | Active | Session log for 20-pair substrate raw tier campaign |
| `agents_history\sessions\2026-08-09_002_alloy-benchmark-adjudication-schema-and-unc-publish.md` | 2026-08-09_002 | 2026-08-09_002 | Active | Checkpoint log for benchmark CSV workflow/schema simplification and UNC publish |
| `agents_history\sessions\2026-08-11_001_alloy-multi-image-vlm-pilot-and-checkpoint.md` | 2026-08-11_001 | 2026-08-11_001 | Active | Session log for the multi-image VLM pilot and checkpoint |
| `agents_history\sessions\2026-08-11_002_alloy-vlm-stage-ab-bf-only-bfdf-scoring-checkpoint.md` | 2026-08-11_002 | 2026-08-11_002 | Active | Session log for the BF-only Stage A / BF+DF Stage B benchmark checkpoint |
| `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv` | 2026-08-09_002 | 2026-08-09_002 | Active | Current adjudication working table; expanded evidence/signature columns present |
| `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv.pre_local_copy_20260809_195242.bak` | 2026-08-09_002 | 2026-08-09_002 | Active | Prepublish backup for active benchmark CSV |
| `images\Alloy_Class\docs\BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md` | 2026-08-09_002 | 2026-08-09_002 | Active | Primary benchmark schema and notes-light adjudication guidance |
| `images\Alloy_Class\docs\ADJUDICATION_WORKSHEET_ONE_PAGER.md` | 2026-08-09_002 | 2026-08-09_002 | Active | Compact adjudication guidance for comparator/occlusion decisions |
| `images\Alloy_Class\artifacts\benchmark_candidates_14day_summary.json` | 2026-08-09_002 | 2026-08-09_002 | Active | Summary metrics for current 14-day benchmark candidate output |
| `images\Alloy_Class\artifacts\benchmark_slice_v1_template.csv` | 2026-08-10_001 | 2026-08-09_002, 2026-08-10_001 | Active | Expanded 35→44 columns; 9 adjudication fields reconciled in 2026-08-10_001 |
| `images\Alloy_Class\docs\BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md` | 2026-08-10_001 | 2026-08-09_002, 2026-08-10_001 | Active | Sections 5C/5E/6/10B/10C/11 updated; section 11 retitled from Proposed to Adopted |
| `images\Alloy_Class\docs\BENCHMARK_CANDIDATE_TOOL_SCOPE.md` | 2026-08-10_001 | 2026-08-08_002, 2026-08-10_001 | Active | Annotated to note template update to 44 cols |
| `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv` | 2026-08-10_001 | 2026-08-09_002, 2026-08-10_001 | Active | Shorthand normalized (1595 cells); benchmark_split column added (104 tune / 41 eval) |
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | 2026-08-11_001 | 2026-08-09_001, 2026-08-10_001, 2026-08-11_001 | Active | Per-pair/per-role progress logging added; direct multi-image Stage B path validated |
| `agents_history\open_threads.md` | 2026-08-10_001 | 2026-08-08_001, 2026-08-10_001 | Active | THREAD-003/004 closed; THREAD-005 through THREAD-009 added |
| `images\Alloy_Class\tools\normalize_benchmark_adjudication.py` | 2026-08-10_001 | 2026-08-10_001 | Active | Normalizes adjudication shorthand to canonical enum values; auto-backup |  
| `images\Alloy_Class\tools\run_benchmark_vlm.py` | 2026-08-10_001 | 2026-08-10_001 | Active | Stages images from pair list CSV + invokes Stage A/B pipeline + writes id lookup |
| `images\Alloy_Class\tools\score_benchmark_run.py` | 2026-08-10_001 | 2026-08-10_001 | Active | Joins JSONL to benchmark CSV; computes FN/FP/calibration by split |
| `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv` | 2026-08-10_001 | 2026-08-10_001 | Active | Versioned freeze post-normalization + post-split; 145 rows; do not modify directly |
| `images\Alloy_Class\artifacts\benchmark_pairs_v1.csv` | 2026-08-10_001 | 2026-08-10_001 | Active | All 145 pairs with benchmark_id, split, coarse_class, source_pool |
| `images\Alloy_Class\artifacts\benchmark_pairs_pilot12.csv` | 2026-08-10_001 | 2026-08-10_001 | Active | 12-row balanced eval pilot set; used for v1/v2/v3 prompt iteration |
| `images\Alloy_Class\artifacts\benchmark_pairs_nbc_focus52.csv` | 2026-08-10_001 | 2026-08-10_001 | Active | 52-row NBC focus set: 32 nbc/possible_beep + 20 nbc/particle; primary test set |
| `images\Alloy_Class\artifacts\benchmark_pairs_full145.csv` | 2026-08-10_001 | 2026-08-10_001 | Active | All 145 pairs for full benchmark runs |
| `images\Alloy_Class\artifacts\benchmark_pairs_nbc_focus52_remaining.csv` | 2026-08-10_001 | 2026-08-10_001 | Active | NBC52 rows after pilot12 exclusion |
| `images\Alloy_Class\config\stage_ab_prompt_tests_smoke_v7_claude_sonnet_4_6_min.json` | 2026-08-15_001 | 2026-08-15_001 | Active | Minimal valid evidence-aware smoke config for Claude Sonnet 4.6 |
| `images\Alloy_Class\config\stage_ab_prompt_tests_offset_surface_lines_15_claude_sonnet_4_6.json` | 2026-08-15_001 | 2026-08-15_001 | Active | 15-row recall slice config for offset-surface-lines-positive rows |
| `images\Alloy_Class\artifacts\benchmark_offset_surface_lines_yes_15.csv` | 2026-08-15_001 | 2026-08-15_001 | Active | 15-row benchmark slice filtered to `gt_offset_surface_lines_present=yes` |
| `images\Alloy_Class\artifacts\benchmark_pairs_one_row_v7_test.csv` | 2026-08-15_001 | 2026-08-15_001 | Active | One-row smoke slice used to validate Claude Sonnet 4.6 acceptance |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v11.json` | 2026-08-26_001 | 2026-08-26_001 | Active | Tracked V11 offset-surface-lines prompt variant with reordered contract |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v12.json` | 2026-08-26_001 | 2026-08-26_001 | Active | Tracked V12 offset-surface-lines prompt variant with expanded guidance |
| `agents_history\sessions\2026-08-26_001_alloy-vlm-v11-v12-benchmark-comparison-checkpoint.md` | 2026-08-26_001 | 2026-08-26_001 | Active | Formal checkpoint for the V11/V12 benchmark comparison |
| `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v11_compare\stage_ab_results\benchmark_score_summary.json` | 2026-08-26_001 | 2026-08-26_001 | Active | Scored summary for the V11 15-pair comparison run |
| `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v12_compare\stage_ab_results\benchmark_score_summary.json` | 2026-08-26_001 | 2026-08-26_001 | Active | Scored summary for the V12 15-pair comparison run |
| `images\Alloy_Class\tools\probe_fn_feature_perception.py` | 2026-08-26_002 | 2026-08-26_002 | Active | Throwaway diagnostic script; probes the 5 known FN cases with Stage-A/JSON-contract stripped (p1/p2); p3 raw-image variant implemented but unused |
| `images\Alloy_Class\outputs\probes\fn_baseline_v12.json` | 2026-08-26_002 | 2026-08-26_002 | Active | Phase 0 baseline: ground truth + pipeline rationale for the 5 FN cases, zero new VLM calls |
| `images\Alloy_Class\outputs\probes\fn_feature_probe_consolidated.jsonl` | 2026-08-26_002 | 2026-08-26_002 | Active | Phase 1 consolidated probe results (best response per case/variant, attempt counts) |
| `images\Alloy_Class\docs\v12_post_mortem.md` | 2026-08-26_003 | 2026-08-26_002, 2026-08-26_003 | Active | Addendum 2026-08-26 appended (002); Addenda 2026-08-26 (2)/(4) appended in 2026-08-26_003 (Phase 0/1 max-token results; Phase 2/3 describe-then-classify results with in-place GT correction; Phase 4 v12/v13 comparison) |
| `agents_history\sessions\2026-08-26_002_alloy-vlm-fn-feature-perception-probe-checkpoint.md` | 2026-08-26_002 | 2026-08-26_002 | Active | Checkpoint log for the FN feature-perception probe |
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | 2026-08-26_003 | 2026-08-09_001, 2026-08-10_001, 2026-08-11_001, 2026-08-11_002, 2026-08-26_003 | Active | BUG-001 fix (`_extract_json_payload` native payload preservation); new diagnostic fields (`usage_source`, `error_class`, `empty_response`, `response_char_count`, `finish_reason`, `image_payload_diagnostics`); new `--stage-b-describe-then-classify` production mode with V11-derived Call 2 prompt builder |
| `images\Alloy_Class\tools\probe_fn_feature_perception.py` | 2026-08-26_003 | 2026-08-26_002, 2026-08-26_003 | Active | New diagnostic fields surfaced in output records; `DEFAULT_MAX_TOKENS` raised 400->1800 |
| `images\Alloy_Class\tools\probe_describe_then_classify.py` | 2026-08-26_003 | 2026-08-26_003 | Active | Phase 2/3 throwaway probe: neutral Call 1 observation + V11-derived Call 2 evidence-check framework; corrected for particle-control GT bug (BUG-002) |
| `images\Alloy_Class\tools\run_benchmark_vlm.py` | 2026-08-26_003 | 2026-08-10_001, 2026-08-11_002, 2026-08-26_003 | Active | Added `--stage-b-describe-then-classify` pass-through flag |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v13.json` | 2026-08-26_003 | 2026-08-26_003 | Active | Production config for the describe-then-classify architecture (Call 2 derived from V11) |
| `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md` | 2026-08-26_003 | 2026-08-26_003 | Active | New v13 row appended for `offset_surface_lines_15_v13_compare` |
| `images\Alloy_Class\artifacts\prompt_iteration_registry.csv` | 2026-08-26_003 | 2026-08-26_003 | Active | New row: `offset_surface_lines_15_v13_compare` |
| `images\Alloy_Class\outputs\probes\phase1_max_token_test_20260826\` (5 jsonl files) | 2026-08-26_003 | 2026-08-26_003 | Active | Raw Phase 1 max-token test data (400 vs 1800 max_completion_tokens, 40 bare calls) |
| `images\Alloy_Class\outputs\probes\phase3_describe_then_classify_20260826\` (3 jsonl files, one superseded) | 2026-08-26_003 | 2026-08-26_003 | Active | Phase 2/3 probe run outputs; one file superseded after the GT-selection bug correction |
| `images\Alloy_Class\outputs\raw_runs\offset_surface_lines_15_v13_compare\` | 2026-08-26_003 | 2026-08-26_003 | Active | Full 15-pair v13 benchmark run + score outputs, head-to-head against the v12 comparison run |
| `agents_history\sessions\2026-08-26_003_alloy-vlm-v13-describe-then-classify-diagnostics-checkpoint.md` | 2026-08-26_003 | 2026-08-26_003 | Active | Checkpoint log for the V13 describe-then-classify diagnostics + production promotion session |
| `agents_history\index.md` | 2026-08-26_003 | 2026-08-08_001, 2026-08-10_001, 2026-08-26_003 | Active | Added session row 2026-08-26_003 and THREAD-011 through THREAD-015 |
| `agents_history\sessions\2026-08-26_005_alloy-vlm-particle25-fp-share-pack-checkpoint.md` | 2026-08-26_005 | 2026-08-26_005 | Active | Checkpoint log for the particle-25 validation, scoring, and share-pack generation session |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v14.json` | 2026-08-27_001 | 2026-08-27_001 | Active | Doc-only config for the v14 patch of the V11-derived prompt lineage |
| `images\Alloy_Class\tools\probe_describe_then_classify_v14.py` | 2026-08-27_001 | 2026-08-27_001 | Active | VERDICT-line/hard-gate fix, trench-tone ban, sunken-residual texture correlation, Pathway 5 (mid-span bridging), boundary-ownership rewrites across Pathway 1-5 / SOURCE DISCRIMINATION / `evidence_check_boundary_conformance` |
| `images\Alloy_Class\docs\PROBE_OUTPUT_SCORING_AND_HTML_REPORT_GAP.md` | 2026-08-27_001 | 2026-08-27_001 | Active | Documents the two raw-output lineages and proposes the generic normalized contract |
| `images\Alloy_Class\tools\normalize_probe_output.py` | 2026-08-27_001 | 2026-08-27_001 | Active | Normalizes both raw-output lineages into the generic contract; built by a different agent per the gap doc's handoff spec |
| `images\Alloy_Class\tools\score_probe_run.py` | 2026-08-27_001 | 2026-08-27_001 | Active | Generic scorer for the normalized contract; built by a different agent |
| `images\Alloy_Class\reporting\build_probe_html_report.py` | 2026-08-27_001 | 2026-08-27_001 | Active | Generic HTML report builder for any probe/run output; built by a different agent |
| `images\Alloy_Class\docs\HANDOFF_PROBE_SCORING_AND_HTML_REPORTING.md` | 2026-08-27_001 | 2026-08-27_001 | Active | Documents the scoring/HTML tooling build; authored by a different agent |
| `images\Alloy_Class\tools\probe_beep_lexicon_v1.py` | 2026-08-27_001 | 2026-08-27_001 | Active | Fresh single-call architecture, `LEXICON_PROMPT_V1` (6,557 chars); imports test-case lists/`_pair_paths` from v14 script (deliberate deviation from duplicate-don't-import convention) |
| `images\Alloy_Class\tools\probe_beep_lexicon_v2.py` | 2026-08-27_001 | 2026-08-27_001 | Active | `LEXICON_PROMPT_V2` (7,531 chars); same architecture as v1 for controlled comparison |
| `images\Alloy_Class\docs\HANDOFF_HTML_FEEDBACK_PORTAL_INTEGRATION.md` | 2026-08-27_001 | 2026-08-27_001 | Active | Original handoff spec authored this session; a different specialized agent later appended an "implemented" status section |
| `images\Alloy_Class\reporting\feedback_portal\` (backend/main.py, run_portal.cmd, run_portal.ps1, requirements.txt, README.txt, data/) | 2026-08-27_001 | 2026-08-27_001 | Active | Local Flask backend + per-case feedback forms; built by a different specialized agent; CSV schema `case_id/reviewer/submitted_at_utc/agrees_with_vlm/corrected_class/comment/run_id` |
| `images\Alloy_Class\docs\TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md` | 2026-08-27_001 | 2026-08-27_001 | Active | Read-only tooling/methods inventory for the 08-30 strategic pivot decision; deliberately no plan/recommendations |
| `images\Alloy_Class\BEEP_Evidence copy.txt` | 2026-08-27_001 | 2026-08-27_001 | Active | Fresh, minimal, plain-lexicon disposition spec; authored by the user, not the agent |
| `images\Alloy_Class\BEEP_Evidence copy 2.txt` | 2026-08-27_001 | 2026-08-27_001 | Active | v2 lexicon incorporating shadow/boundary-conformance/ISL-continuity fixes; authored by the user, not the agent |
| `images\Alloy_Class\outputs\probes\scored\beep_lexicon_v1_20260828_full31\` | 2026-08-27_001 | 2026-08-27_001 | Active | Scored v1 lexicon run: TP 3, TN 16, FP 10, FN 2; FP rate 0.385 |
| `images\Alloy_Class\outputs\probes\scored\beep_lexicon_v2_20260829_full31\` | 2026-08-27_001 | 2026-08-27_001 | Active | Scored v2 lexicon run: TP 3, TN 12, FP 14, FN 2; FP rate 0.538 (regression, see THREAD-019) |
| `agents_history\sessions\2026-08-27_001_beep-lexicon-v1-v2-and-strategic-pivot-inventory.md` | 2026-08-27_001 | 2026-08-27_001 | Active | Retroactive checkpoint log for the v14 patch, lexicon v1/v2 rewrite, feedback portal rollout, and strategic pivot tooling inventory |
| `agents_history\index.md` | 2026-08-27_001 | 2026-08-08_001, 2026-08-10_001, 2026-08-26_003, 2026-08-27_001 | Active | Added session row 2026-08-27_001 and THREAD-018 through THREAD-025 |
| `agents_history\open_threads.md` | 2026-08-27_001 | 2026-08-08_001, 2026-08-10_001, 2026-08-26_003, 2026-08-27_001 | Active | Added THREAD-018 through THREAD-025 body entries |
| `agents_history\file_map.md` | 2026-08-27_001 | 2026-08-08_001, 2026-08-27_001 | Active | Added rows for this session's files |

---

## 2026-08-31_001 — 1K OX SurfScan Pilot Pipeline Build + EDX LAYER_ID Investigation

| File (relative path) | Last Session | All Sessions | Status | Notes |
|----------------------|-------------|--------------|--------|-------|
| `rollups\1K_OX_PILOT_PIPELINE\scope_1k_ox_smoke_test.py` | 2026-08-31_001 | 2026-08-31_001 | Active | 4-step standalone scoping/smoke-test script for the new layer |
| `rollups\1K_OX_PILOT_PIPELINE\scope_1k_ox_smoke_test_summary.json` | 2026-08-31_001 | 2026-08-31_001 | Active | Scoping run output: 51 AME chambers, 3 non-AME GTO tools, `M_UBE_MIMIC_R4` recipe confirmed |
| `rollups\1K_OX_PILOT_PIPELINE\step1_tool_universe.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Step 1 raw scoping output |
| `rollups\1K_OX_PILOT_PIPELINE\step2_ame_defect_sample.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Step 2 raw scoping output |
| `rollups\1K_OX_PILOT_PIPELINE\step3_pm_counter_availability.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Step 3 raw scoping output |
| `rollups\1K_OX_PILOT_PIPELINE\step4_elwc_join_check.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Step 4 raw scoping output |
| `rollups\1K_OX_PILOT_PIPELINE\step5_actual_chamber_recipe_match.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Nearest-match result identifying `M_UBE_MIMIC_R4` |
| `rollups\1K_OX_PILOT_PIPELINE\step6_related_layer_ids.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Confirms no sibling SEG/PRE layer needed |
| `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_config.py` | 2026-08-31_001 | 2026-08-31_001 | Active | Shared config: layer ID, chamber recipe, floor time, AME filter, event map, pilot-status config |
| `rollups\1K_OX_PILOT_PIPELINE\ox_pilot_coordinates.py` | 2026-08-31_001 | 2026-08-31_001 | Active | Core query/enrichment logic; BUG-001 (per-column nearest-match) and BUG-002 (pilot-status port) fixed in place |
| `rollups\1K_OX_PILOT_PIPELINE\run_seed.py` | 2026-08-31_001 | 2026-08-31_001 | Active | CLI entrypoint: full seed pull since FLOOR_TIME |
| `rollups\1K_OX_PILOT_PIPELINE\run_update.py` | 2026-08-31_001 | 2026-08-31_001 | Active | CLI entrypoint: incremental overlap-window update |
| `rollups\1K_OX_PILOT_PIPELINE\outputs\OX_COORDINATES.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Pilot coordinates output, post both bug fixes |
| `rollups\1K_OX_PILOT_PIPELINE\outputs\OX_METRICS.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Pilot metrics output, post both bug fixes; 131 rows after last update merge |
| `rollups\1K_OX_PILOT_PIPELINE\artifacts\ox_pilot_seed_summary.json` | 2026-08-31_001 | 2026-08-31_001 | Active | Seed-run summary |
| `rollups\1K_OX_PILOT_PIPELINE\artifacts\ox_pilot_update_summary.json` | 2026-08-31_001 | 2026-08-31_001 | Active | Update-run summary: 7-day overlap, 429 defect rows |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_layer_id.py` | 2026-08-31_001 | 2026-08-31_001 | Active | Probe iteration 1: candidate EDX layer existence checks for lot D629T8V0 |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_layer_id_v2.py` | 2026-08-31_001 | 2026-08-31_001 | Active | Probe iteration 2 |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_layer_id_v3.py` | 2026-08-31_001 | 2026-08-31_001 | Active | Probe iteration 3 |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_layer_id_v4.py` | 2026-08-31_001 | 2026-08-31_001 | Active | Final probe iteration; confirmed `MBTW_EDX_API` returns zero rows for this lot |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q1_lot_window_layers.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Probe output: LAYER_ID rows for the lot within a post-scan time window |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q2_lot_edx_layers.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Probe output: lot-scoped EDX-candidate layer check |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q3_fleet_edx_layers.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Probe output: fleet-wide EDX-candidate layer check |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q4_insp_element_direct.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Confirms direct `UDB.INSP_ELEMENT` join to the original scan key -- no separate LAYER_ID needed |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q5_baresi_udc_layers.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Existence check for `6BARESI_EDX_UDC` guess -- no rows |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q6_exact_guessed_layers.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Existence check for all 3 candidate LAYER_IDs -- no rows (none exist) |
| `rollups\1K_OX_PILOT_PIPELINE\probe_edx_q7_lot_full_history.csv` | 2026-08-31_001 | 2026-08-31_001 | Active | Full LAYER_ID history for the lot across all steps |
| `agents_history\sessions\2026-08-31_001_1k-ox-surfscan-pilot-pipeline-and-edx-layer-id-investigation.md` | 2026-08-31_001 | 2026-08-31_001 | Active | Retroactive checkpoint log for this session |
| `agents_history\index.md` | 2026-08-31_001 | 2026-08-08_001, 2026-08-10_001, 2026-08-26_003, 2026-08-27_001, 2026-08-31_001 | Active | Added session row 2026-08-31_001 and THREAD-026 |
| `agents_history\open_threads.md` | 2026-08-31_001 | 2026-08-08_001, 2026-08-10_001, 2026-08-26_003, 2026-08-27_001, 2026-08-31_001 | Active | Added THREAD-026 body entry |
| `agents_history\file_map.md` | 2026-08-31_001 | 2026-08-08_001, 2026-08-27_001, 2026-08-31_001 | Active | Added rows for this session's files |
| `images\Alloy_Class\tools\build_small_particle_raw_cache.py` | 2026-09-04_001 | 2026-09-04_001 | Active | Flat `RAW_IMAGES` raw-download flow restored; pilot validated clean |
| `agents_history\sessions\2026-09-04_001_small-particle-raw-cache-flat-raw-images-checkpoint.md` | 2026-09-04_001 | 2026-09-04_001 | Active | Formal checkpoint log for the small-particle raw-cache refactor session |
| `agents_history\index.md` | 2026-09-04_001 | 2026-08-08_001, 2026-08-10_001, 2026-08-26_003, 2026-08-27_001, 2026-08-31_001, 2026-09-04_001 | Active | Added session row 2026-09-04_001 and THREAD-027 |
| `agents_history\open_threads.md` | 2026-09-04_001 | 2026-08-08_001, 2026-08-10_001, 2026-08-26_003, 2026-08-27_001, 2026-08-31_001, 2026-09-04_001 | Active | Added THREAD-027 body entry |
| `agents_history\file_map.md` | 2026-09-04_001 | 2026-08-08_001, 2026-08-27_001, 2026-08-31_001, 2026-09-04_001 | Active | Added rows for this session's files |
| `.gitignore` | 2026-09-04_002 | 2026-09-04_002 | Active | Ignore rules referenced for generated `images\Alloy_Class\outputs\`, `rollups\`, and `html\adhoc_*` report directories |
| `html\adhoc_chamber_events\` | 2026-09-04_002 | 2026-09-04_002 | Active | Generated adhoc chamber HTML report directory referenced in the hygiene checkpoint |
| `html\adhoc_elements\` | 2026-09-04_002 | 2026-09-04_002 | Active | Generated adhoc element HTML report directory referenced in the hygiene checkpoint |
| `agents_history\sessions\2026-09-04_002_repo-hygiene-ignore-and-untrack-checkpoint.md` | 2026-09-04_002 | 2026-09-04_002 | Active | Formal checkpoint log for the repo-hygiene ignore/untrack maintenance pass |
| `agents_history\index.md` | 2026-09-04_002 | 2026-08-08_001, 2026-08-10_001, 2026-08-26_003, 2026-08-27_001, 2026-08-31_001, 2026-09-04_001, 2026-09-04_002 | Active | Added session row 2026-09-04_002 |
| `agents_history\file_map.md` | 2026-09-04_002 | 2026-08-08_001, 2026-08-27_001, 2026-08-31_001, 2026-09-04_001, 2026-09-04_002 | Active | Added rows for this session's logging files and hygiene targets |
| `SURF_SCAN_PIPELINE_DESIGN.md` | 2026-08-31_001 (referenced) | 2026-08-08_005, 2026-08-08_006, 2026-08-31_001 | Active | Architectural reference for the OX pilot design; not modified this session |
| `BE_QUERY_FILES\surf_scan_coordinates.py` | 2026-08-31_001 (referenced) | 2026-08-31_001 | Active | Source of ported pilot-status logic and the `_fetch_edx_data()` pattern match; not modified this session |

---

## Backfilled Entries (2026-08-26 Logging Health Reconciliation)

These rows cover sessions that existed as files in `sessions\` but were never registered in this map or in `index.md`. Backfilled retroactively; see `agents_history\sessions\2026-08-26_00X` for the reconciliation session log once written.

| File (relative path) | Last Session | All Sessions | Status | Notes |
|----------------------|-------------|--------------|--------|-------|
| `rollups\YPO_STATUS.py` | 2026-06-20_001 | 2026-06-20_001 | Active | YPO rollup script; first-observation selection + independent counter reset detection |
| `rollups\YPO\YPO_STATUS.csv` | 2026-06-20_001 | 2026-06-20_001 | Active | Summary output, one row per chamber first YPO observation |
| `rollups\YPO\YPO_STATUS_AUDIT.csv` | 2026-06-20_001 | 2026-06-20_001 | Active | Reset-candidate audit output |
| `images\Alloy_Class\pipelines\classify_phase1_batch.py` | 2026-07-26_002 | 2026-07-26_001, 2026-07-26_002 | Active | Transient raw-image staging + BOM-safe JSON loading (001); configurable max_completion_tokens + per-image timing telemetry (002) |
| `images\Alloy_Class\docs\PHASE1_RUNBOOK.md` | 2026-07-26_001 | 2026-07-26_001 | Active | Bounded raw-mode run guidance, ScriptHost parity/bootstrap instructions |
| `images\Alloy_Class\tools\wheelhouse_audit.py` | 2026-07-26_001 | 2026-07-26_001 | Active | Offline wheelhouse coverage audit utility |
| `images\Alloy_Class\pipelines\caption_phase1_batch.py` | 2026-07-26_002 | 2026-07-26_002 | Active | `--max-completion-tokens` CLI flag; row_total timing telemetry |
| `images\Alloy_Class\reporting\build_phase1_html_report.py` | 2026-07-26_002 | 2026-07-26_002 | Active | BUG-001 fix: cross-mount relpath crash guarded with try/except |
| `images\Alloy_Class\docs\HANDOFF_PROMPT_ITERATION_1PAIR_RUNTIME.md` | 2026-07-26_002 | 2026-07-26_002 | Active | Execution summary + runtime matrix results appended |
| `rollups\adhoc_inline_images\query_lot_all_images.py` | 2026-07-28_001 | 2026-07-28_001 | Active | Generalized single-LOT orchestration entry point |
| `rollups\adhoc_inline_images\generate_lot_html_report.py` | 2026-07-28_001 | 2026-07-28_001 | Active | HTML report generator grouped by layer/class |
| `rollups\adhoc_inline_images\README_USAGE.md` | 2026-07-28_001 | 2026-07-28_001 | Active | Expanded usage/architecture/troubleshooting guide |
| `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py` | 2026-08-08_004 | 2026-08-08_003, 2026-08-08_004 | Active | Dual-agent conflict resolved + manifest coverage check (003); METROLOGY_COLS + 3 image-merge fixes (004) |
| `BE_QUERY_FILES\backfill_vlm_metadata.py` | 2026-08-08_004 | 2026-08-08_003, 2026-08-08_004 | Active | SIZE_Z/ROUGH_BIN_CLASS cleanup (003); created as one-time VLM metadata backfill (004) |
| `BE_QUERY_FILES\metadata_explorer.py` | 2026-08-08_003 | 2026-08-08_003, 2026-08-08_004 | Active | SIZE_Z/ROUGH_BIN_CLASS cleanup (003); created for DB schema discovery (004) |
| `images\Alloy_Class\metadata\build_defect_size_metadata.py` | 2026-08-08_003 | 2026-08-08_003 | Active | Skip logic for incomplete manifest rows |
| `outputs\defects\DEFECT_COORDINATES_EXTENDED.csv` | 2026-08-08_004 | 2026-08-08_004 | Active | VLM metadata backfilled; SIZE_Z/ROUGH_BIN_CLASS removed |
| `outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv` | 2026-08-08_004 | 2026-08-08_003, 2026-08-08_004 | Active | Stale SIZE_Z column removed (003); 38 UNKNOWN-path rows cleared (004) |
| `BE_QUERY_FILES\cleanup_unknown_images.py` | 2026-08-08_004 | 2026-08-08_004 | Active | Deletes UNKNOWN images and clears manifest rows |
| `INLINE_PIPELINE_DESIGN.md` | 2026-08-08_005 | 2026-08-08_005 | Active | Renamed from PIPELINE_DESIGN.md; trimmed to Tier-2 summary |
| `SURF_SCAN_PIPELINE_DESIGN.md` | 2026-08-08_006 | 2026-08-08_005, 2026-08-08_006 | Active | Trimmed to Tier-2 summary (005); cross-referenced for EMSA pipeline context (006) |
| `DESIGN_INDEX.md` | 2026-08-08_005 | 2026-08-08_005 | Active | Updated to reflect three-tier doc structure |
| `docs\inline_pipeline\` (6 files) | 2026-08-08_005 | 2026-08-08_005 | Active | New Tier-3 feature-doc folder |
| `docs\surf_scan_pipeline\` (6 files) | 2026-08-08_005 | 2026-08-08_005 | Active | New Tier-3 feature-doc folder; absorbed deleted SURF_SCAN_PIPELINE_DESIGN_RF.md |
| `docs\EMSA_ACCESS.md` | 2026-08-08_006 | 2026-08-08_006 | Active | Primary subject of EMSA/EDX access investigation; no edits made |
| `BE_QUERY_FILES\surf_scan_images.py` | 2026-08-08_013 | 2026-08-08_006, 2026-08-08_013 | Active | Referenced for IMAGE_IDS_BASE gap (006); manifest/routing discrepancy fix applied (013) |
| `html\SS_INLINE_CHAMBER_REPORT.py` | 2026-08-08_007 | 2026-08-08_007 | Active | Per-chamber SS inline HTML report; CSS grid, SVG wafermap, EDX image integration |
| `html\SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py` | 2026-08-08_007 | 2026-08-08_007 | Active | Fleet runner, 47 chambers, 60-day default |
| `html\SS_CHAMBER_EVENT_REPORT.py` | 2026-08-08_007 | 2026-08-08_007 | Active | Bug fix: usecols on EDX load + traceback.print_exc() |
| `debug_logs\SS_IMAGE_CROSS_CHAMBER_ROUTING_BUG.md` | 2026-08-08_007 | 2026-08-08_007 | Active | Bug report; routing fix later applied in 2026-08-08_013 |
| `html\INLINE_CHAMBER_EVENT_REPORT.py` | 2026-08-08_008 | 2026-08-08_002, 2026-08-08_008 | Active | Atomic write, [WARN] logging, dead code removal (008) |
| `html\INLINE_PRODUCTION_SUBENTITY_REPORTS.py` | 2026-08-08_008 | 2026-08-08_002, 2026-08-08_008 | Active | Hard-coded 51-chamber FLEET list; removed FLEET_FILE dependency (008) |
| `BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py` | 2026-08-08_010 | 2026-08-08_002, 2026-08-08_008, 2026-08-08_010 | Active | Added inline HTML report post-step (002/008); added weekly zero-rate aggregator step 8 (010) |
| `artifacts\workspace_cleanup_inventory.csv` | 2026-08-08_009 | 2026-08-08_009 | Active | 717-row non-image file inventory with suggested actions |
| `dev\classify_be_query_files_pipeline_membership.py` | 2026-08-08_009 | 2026-08-08_009 | Active | Static import + subprocess classifier for pipeline membership |
| `artifacts\be_query_files_pipeline_membership.csv` | 2026-08-08_009 | 2026-08-08_009 | Active | INLINE=17, SURF=9, BOTH=2, NEITHER=47 |
| `BE_QUERY_FILES\utils\` (53 files) | 2026-08-08_009 | 2026-08-08_009 | Active | 53 NEITHER-classified files moved here; 9 later restored |
| `BE_QUERY_FILES\modular_processor\EXTEND_BENCHMARK.py` | 2026-08-08_010 | 2026-08-08_010 | Active | Fixed dual-metric dedup clobbering CLASS_BEEP=UNKNOWN bug |
| `BE_QUERY_FILES\EDI_BACKFILL.py` | 2026-08-08_010 | 2026-08-08_010 | Active | Backfill script; 9,800 BEEP_EDI records restored |
| `BE_QUERY_FILES\WEEKLY_ZERO_RATE_AGGREGATOR.py` | 2026-08-08_010 | 2026-08-08_010 | Active | Sunday-scheduled weekly zero-rate aggregator |
| `BE_QUERY_FILES\BACKFILL_WORKWEEK_COLUMNS.py` | 2026-08-08_010 | 2026-08-08_010 | Active | One-time backfill for PERIOD_END/YYYYWW columns |
| `rollups\PREvsPST\pre_only_coords_2026_long.csv` | 2026-08-08_011 | 2026-08-08_011 | Active | PRE-only 2026 coordinate-level extract |
| `rollups\PREvsPST\pre_only_coords_2026_wafer_summary.csv` | 2026-08-08_011 | 2026-08-08_011 | Active | Wafer-level dirtiest-wafer summary |
| `rollups\PREvsPST\pre_vs_pst_2026_only_input.csv` | 2026-08-08_011 | 2026-08-08_011 | Active | Prepared PRE-vs-PST 2026-only analysis input |
| `debug_logs\8M5CL_NCDD.log` | 2026-08-08_012 | 2026-08-08_012 | Active | Primary evidence for NCDD SQL forensic analysis |
| `debug_logs\ediQuery#306.log` | 2026-08-08_012 | 2026-08-08_012 | Active | Primary evidence for EDI SQL forensic analysis |
| `BE_QUERY_FILES\8M5CL_NCDD_SHORT.jsl` | 2026-08-08_012 | 2026-08-08_012 | Active | WIJT job spec confirmed CLASS_NCDD only |
| `BE_QUERY_FILES\surf_scan_update.py` | 2026-08-08_013 | 2026-08-08_013 | Active | Update-stage fix to reduce manifest drift |
| `BE_QUERY_FILES\reconcile_prune_images.py` | 2026-08-08_013 | 2026-08-08_003, 2026-08-08_013 | Active | INVENTORY_ONLY column tag (003); reconcile/prune fixes + active prune validation (013) |
| `agents_history\sessions\2026-08-11_003_alloy-prompt-iteration-registry-checkpoint.md` | 2026-08-11_003 | 2026-08-11_003 | Active | Checkpoint log for the prompt iteration registry work |
| `images\Alloy_Class\docs\PROMPT_ITERATION_REGISTRY.md` | 2026-08-11_004 | 2026-08-11_003, 2026-08-11_004, 2026-08-26_003 | Active | Registry schema defined (003); updated to point at prompt_bundle provenance (004); v13 row appended (2026-08-26_003) |
| `images\Alloy_Class\artifacts\prompt_iteration_registry.csv` | 2026-08-11_003 | 2026-08-11_003, 2026-08-26_003 | Active | Machine-editable tracker created (003); v13 row appended (2026-08-26_003) |
| `agents_history\sessions\2026-08-11_004_alloy-prompt-bundle-provenance-checkpoint.md` | 2026-08-11_004 | 2026-08-11_004 | Active | Checkpoint log for the prompt-bundle provenance implementation |
| `rollups\INLINE_MISMATCHES\INLINE_MISMATCH_BACKFILL_HANDOFF.md` | 2026-08-18_001 | 2026-08-18_001 | Active | Handoff note describing NCDD/inline mismatch schema and backfill recommendation |
| `rollups\INLINE_MISMATCHES\inline_mismatch_distribution.py` | 2026-08-18_001 | 2026-08-18_001 | Active | Added inspection-time tracking and daily timing plot |
| `agents_history\sessions\2026-08-18_001_inline-mismatch-backfill-handoff-checkpoint.md` | 2026-08-18_001 | 2026-08-18_001 | Active | Checkpoint log for the mismatch backfill handoff |
| `agents_history\sessions\2026-08-18_002_defect-reclassification-mismatch-audit-checkpoint.md` | 2026-08-18_002 | 2026-08-18_002 | Active | Renamed from `2026-08-18_001_...` during logging health reconciliation to resolve session ID collision |
| `agents_history\sessions\2026-08-26_004_agent-logging-system-health-audit-and-reconciliation.md` | 2026-08-26_004 | 2026-08-26_004 | Active | Checkpoint log for this reconciliation session |
| `agents_history\open_threads.md` | 2026-08-26_003 | 2026-08-08_001, 2026-08-10_001, 2026-08-26_003 | Active | Added THREAD-011 through THREAD-015 body entries |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v2.json` | 2026-08-10_001 | 2026-08-10_001 | Active | v2 prompt config: 3 named evidence checks, occlusion guard fix, location-not-proxy |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v3.json` | 2026-08-10_001 | 2026-08-10_001 | Active | v3 prompt config: threshold calibration, SiO texture discrimination; max_pairs=200 |
| `agents_history\sessions\2026-08-10_001_alloy-vlm-prompt-engineering-benchmark-readiness-nbc52.md` | 2026-08-10_001 | 2026-08-10_001 | Active | Session log for VLM prompt engineering and NBC52 scale run |
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | 2026-08-11_002 | 2026-08-10_001, 2026-08-11_002 | Active | BF-only Stage A / BF+DF Stage B mode implemented and forwarded |
| `images\Alloy_Class\tools\run_benchmark_vlm.py` | 2026-08-11_002 | 2026-08-10_001, 2026-08-11_002 | Active | Benchmark runner forwards BF-only Stage A / BF+DF Stage B mode |
| `images\Alloy_Class\tools\score_benchmark_run.py` | 2026-08-11_002 | 2026-08-10_001, 2026-08-11_002 | Active | Scoring against frozen benchmark baseline completed |
| `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv` | 2026-08-11_002 | 2026-08-10_001, 2026-08-11_002 | Active | Frozen scoring baseline used for checkpoint comparison |
| `images\Alloy_Class\artifacts\benchmark_nbc52_tier1_v3_stageA_BF_only_stageB_multi_v2` | 2026-08-11_002 | 2026-08-11_002 | Active | Corrected NBC52 benchmark run completed successfully |
| `images\Alloy_Class\artifacts\benchmark_nbc52_tier1_v3_stageA_BF_only_stageB_multi` | 2026-08-11_002 | 2026-08-11_002 | Active | Earlier benchmark run retained for comparison scoring |
| `rollups\INLINE_MISMATCHES\INLINE_MISMATCH_BACKFILL_HANDOFF.md` | 2026-08-18_001 | 2026-08-18_001 | Active | Handoff note for follow-on backfill / pipeline repair |
| `rollups\INLINE_MISMATCHES\inline_mismatch_distribution.py` | 2026-08-18_001 | 2026-08-18_001 | Active | Added inspection-time tracking and daily mismatch timing plot |
| `rollups\INLINE_MISMATCHES\inline_mismatch_distribution_summary.csv` | 2026-08-18_001 | 2026-08-18_001 | Active | Delta distribution summary statistics |
| `rollups\INLINE_MISMATCHES\inline_mismatch_histogram.png` | 2026-08-18_001 | 2026-08-18_001 | Active | Absolute-delta histogram |
| `rollups\INLINE_MISMATCHES\inline_mismatch_probability.png` | 2026-08-18_001 | 2026-08-18_001 | Active | Tail probability plot |
| `rollups\INLINE_MISMATCHES\inline_mismatch_timing.png` | 2026-08-18_001 | 2026-08-18_001 | Active | Daily mismatch timing / rate plot |
| `BE_QUERY_FILES\8M5CL_NCDD_EDI_LONG.csv` | 2026-08-18_001 | 2026-08-18_001 | Active | Stable nightly 180-day source for 8M5CL backfill |
| `BE_QUERY_FILES\8M6CL_NCDD_EDI_LONG.csv` | 2026-08-18_001 | 2026-08-18_001 | Active | Stable nightly 180-day source for 8M6CL backfill |
| `BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py` | 2026-08-18_001 | 2026-08-18_001 | Active | Referenced as the likely source-window change point |
| `outputs\defects\DEFECT_COORDINATES_EXTENDED.csv` | 2026-08-18_001 | 2026-08-18_001 | Active | Production metrics CSV compared against inline sources |

---

## Recently Modified (Last 30 Days)
| File | Date | Session | Change |
|------|------|---------|--------|
| `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv` | 2026-08-10 | 2026-08-10_001 | Modified + normalized |
| `images\Alloy_Class\docs\BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md` | 2026-08-10 | 2026-08-10_001 | Modified |
| `images\Alloy_Class\docs\BENCHMARK_CANDIDATE_TOOL_SCOPE.md` | 2026-08-10 | 2026-08-10_001 | Modified |
| `images\Alloy_Class\artifacts\benchmark_slice_v1_template.csv` | 2026-08-10 | 2026-08-10_001 | Modified (35→44 cols) |
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | 2026-08-10 | 2026-08-10_001 | Modified (progress logging) |
| `images\Alloy_Class\tools\normalize_benchmark_adjudication.py` | 2026-08-10 | 2026-08-10_001 | Created |
| `images\Alloy_Class\tools\run_benchmark_vlm.py` | 2026-08-10 | 2026-08-10_001 | Created |
| `images\Alloy_Class\tools\score_benchmark_run.py` | 2026-08-10 | 2026-08-10_001 | Created |
| `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv` | 2026-08-10 | 2026-08-10_001 | Created |
| `images\Alloy_Class\artifacts\benchmark_pairs_v1.csv` | 2026-08-10 | 2026-08-10_001 | Created |
| `images\Alloy_Class\artifacts\benchmark_pairs_pilot12.csv` | 2026-08-10 | 2026-08-10_001 | Created |
| `images\Alloy_Class\artifacts\benchmark_pairs_nbc_focus52.csv` | 2026-08-10 | 2026-08-10_001 | Created |
| `images\Alloy_Class\artifacts\benchmark_pairs_full145.csv` | 2026-08-10 | 2026-08-10_001 | Created |
| `images\Alloy_Class\artifacts\benchmark_pairs_nbc_focus52_remaining.csv` | 2026-08-10 | 2026-08-10_001 | Created |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v2.json` | 2026-08-10 | 2026-08-10_001 | Created |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v3.json` | 2026-08-10 | 2026-08-10_001 | Created |
| `agents_history\AGENT_RULES.md` | 2026-08-08 | 2026-08-08_001 | Created |
| `agents_history\SESSION_KICKOFF.md` | 2026-08-08 | 2026-08-08_001 | Created |
| `agents_history\checkpoint_prompt.md` | 2026-08-08 | 2026-08-08_001 | Created |
| `agents_history\index.md` | 2026-08-08 | 2026-08-08_001 | Created |
| `agents_history\file_map.md` | 2026-08-08 | 2026-08-08_001 | Created |
| `agents_history\open_threads.md` | 2026-08-08 | 2026-08-08_001 | Created |
| `agents_history\sessions\_template.md` | 2026-08-08 | 2026-08-08_001 | Created |
| `agents_history\sessions\2026-08-08_001_session-logger-deployment.md` | 2026-08-08 | 2026-08-08_001 | Created |
| `html\INLINE_CHAMBER_EVENT_REPORT.py` | 2026-08-08 | 2026-08-08_002 | Created |
| `html\INLINE_PRODUCTION_SUBENTITY_REPORTS.py` | 2026-08-08 | 2026-08-08_002 | Created |
| `BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py` | 2026-08-08 | 2026-08-08_002 | Modified |
| `docs\FLEET.txt` | 2026-08-08 | 2026-08-08_002 | Modified |
| `html\INLINE_HTML_REPORT_PATTERNS.md` | 2026-08-08 | 2026-08-08_002 | Created |
| `images\Alloy_Class\docs\BENCHMARK_CANDIDATE_TOOL_SCOPE.md` | 2026-08-08 | 2026-08-08_002 | Created |
| `agents_history\sessions\2026-08-08_002_inline-html-reports-build-and-benchmark-scope.md` | 2026-08-08 | 2026-08-08_002 | Created |

---

## Files With Open Issues
| File | Issue | Session Where Found | Status |
|------|-------|---------------------|--------|
| `html\INLINE_CHAMBER_EVENT_REPORT.py` | Coordinate inference from filename/path is a fragile workaround for manifest backfill lag (THREAD-002) | 2026-08-08_002 | Open |
| `images\Alloy_Class\docs\BENCHMARK_CANDIDATE_TOOL_SCOPE.md` | Script it describes (`build_benchmark_candidates.py`) not yet built (THREAD-001) | 2026-08-08_002 | Open |
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | `_call_image` must be extended to support 3 images for texture reference crop (THREAD-005) | 2026-08-10_001 | Resolved in 2026-08-11_001 |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v3.json` | v3 prompt has bc check detection gap (THREAD-006) and sr ceiling (THREAD-008) | 2026-08-10_001 | Open |
| `images\Alloy_Class\tools\probe_fn_feature_perception.py` | Intermittent empty VLM responses (~40% first-attempt rate, BMK_0050/p2 persistent across 4 attempts) — BUG-001, unresolved | 2026-08-26_002 | Resolved in 2026-08-26_003 — max-token hypothesis confirmed as a real contributing cause; `DEFAULT_MAX_TOKENS` raised 400->1800 |
| `images\Alloy_Class\tools\score_benchmark_run.py` | Boolean `False` `review_required` mis-flagged as missing due to `str(False or "")` truthiness (THREAD-015) | 2026-08-26_003 | Open (Deferred, out of scope) |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v13.json` | Validated on 15-pair benchmark but not yet promoted to production default (THREAD-011) | 2026-08-26_003 | Open |
