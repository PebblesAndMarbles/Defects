---
session_id: 2026-08-10_001
title: Alloy VLM Prompt Engineering — Benchmark Readiness, Labeling Consistency, Baseline + v2/v3 Prompt Iteration, NBC52 Scale Run
date: 2026-08-09
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 4.6
triggered_by: manual-checkpoint
status: complete
original_goal: Transition from benchmark infrastructure build-out into structured VLM prompt engineering and measured evaluation against adjudicated benchmark labels.
retroactive: true
logged_date: 2026-08-10
---

## Original Goal
Transition from benchmark infrastructure build-out into structured VLM prompt
engineering and measured evaluation against adjudicated benchmark labels.
Entry condition: benchmark CSV was populated with adjudicated rows but schema
was unvalidated, shorthand was un-normalized, no train/eval split existed, and
no scoring infrastructure existed to measure prompt changes against ground truth.

---

## Completed Tasks

- [x] Audit benchmark schema across docs, template CSV, and live benchmark CSV
- [x] Identify 9 columns added during adjudication not present in template/schema doc
- [x] Update BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md (sections 5C, 5E, 6, 10B, 10C, 11)
- [x] Update benchmark_slice_v1_template.csv from 35 → 44 columns
- [x] Update BENCHMARK_CANDIDATE_TOOL_SCOPE.md to note template update
- [x] Close THREAD-003 (schema contract drift) and THREAD-004 (shorthand normalization)
- [x] Create normalize_benchmark_adjudication.py — expanded 1,595 cells across 11 columns; 0 unrecognized values; auto-backup created
- [x] Run assign_benchmark_split.py: 104 tune / 41 eval (seed=1278, deterministic)
- [x] Create benchmark_v1_frozen.csv (versioned freeze after normalization + split)
- [x] Create benchmark_pairs_v1.csv (all 145 rows), benchmark_pairs_pilot12.csv (12 balanced eval rows)
- [x] Create run_benchmark_vlm.py — stages images from pair list CSV, invokes Stage A/B pipeline, writes benchmark_id_lookup.csv
- [x] Create score_benchmark_run.py — joins JSONL to benchmark CSV via bright_image_name stem, computes FN/FP/disagreement/review_required calibration by split
- [x] Add per-pair/per-role progress logging to run_stage_ab_prompt_tests.py
- [x] Create benchmark_pairs_nbc_focus52.csv (32 nbc/possible_beep + 20 nbc/particle)
- [x] Create benchmark_pairs_full145.csv (all 145 rows)
- [x] Run comprehensive label analysis by (source_pool, coarse_class) — identified two structurally distinct BEEP populations
- [x] Run v1 baseline prompt on pilot12 (burned images, Tier 1): 58% class agreement, 50% FN, 33% FP, 8% evidence agreement
- [x] Run v2 prompt (3 named evidence checks + occlusion guard fix + location-not-proxy rule): fixed 1 FP, caused 1 regression
- [x] Run v2 with raw images: minimal change — raw mode not the limiting factor
- [x] Run v3 prompt (threshold calibration: 1 yes = moderate; SiO vs particle texture discrimination; single-edge bc sufficient): fixed BMK_0001 FN, created BMK_0037 new FP, same overall accuracy 7/12
- [x] Create stage_ab_prompt_tests_substrate_tier1_v2.json and _v3.json config files
- [x] Run v3 on NBC52 scale run (52 pairs, raw mode): recovery 10/32 = 31%; FP 6/20 = 30%
- [x] Generate nbc52_review_table.csv, nbc52_full_vlm_output.csv
- [x] Identify detection ceiling: binary detection confirmed — any check firing → always correct; no checks firing → always missed

---

## Files Modified

| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\docs\BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md` | Modified | Sections 5C, 5E (new), 6, 10B, 10C, 11 updated; section 11 retitled from "Proposed" to "Adopted 2026-08-09" |
| `images\Alloy_Class\docs\BENCHMARK_CANDIDATE_TOOL_SCOPE.md` | Modified | Annotated to note template update to 44 cols |
| `images\Alloy_Class\artifacts\benchmark_slice_v1_template.csv` | Modified | Expanded 35 → 44 columns; 9 adjudication fields reconciled |
| `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv` | Modified | Shorthand normalized (1,595 cells); benchmark_split column assigned (104 tune / 41 eval) |
| `agents_history\open_threads.md` | Modified | THREAD-003 and THREAD-004 marked resolved in resolved table |
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | Modified | Per-pair/per-role progress logging added |

---

## Files Created

| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\tools\normalize_benchmark_adjudication.py` | Created | Normalizes shorthand to canonical enum values; creates .bak backup automatically |
| `images\Alloy_Class\tools\run_benchmark_vlm.py` | Created | Stages images from pair list CSV + invokes Stage A/B pipeline + writes benchmark_id_lookup.csv |
| `images\Alloy_Class\tools\score_benchmark_run.py` | Created | Joins JSONL to benchmark CSV via bright_image_name stem; computes FN/FP/disagreement/review_required by split |
| `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv` | Created | Versioned freeze: post-normalization, post-split, 145 rows |
| `images\Alloy_Class\artifacts\benchmark_pairs_v1.csv` | Created | All 145 adjudicated pairs with benchmark_id, split, coarse_class, source_pool |
| `images\Alloy_Class\artifacts\benchmark_pairs_pilot12.csv` | Created | 12-row balanced pilot set; all eval split; used for v1/v2/v3 prompt iteration |
| `images\Alloy_Class\artifacts\benchmark_pairs_nbc_focus52.csv` | Created | 52-row NBC focus set: 32 nbc/possible_beep + 20 nbc/particle |
| `images\Alloy_Class\artifacts\benchmark_pairs_full145.csv` | Created | All 145 pairs; used for full benchmark runs |
| `images\Alloy_Class\artifacts\benchmark_pairs_nbc_focus52_remaining.csv` | Created | Remaining NBC52 rows after pilot12 exclusion |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v2.json` | Created | v2 prompt config: 3 named evidence checks, occlusion guard fix, location-not-proxy rule |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v3.json` | Created | v3 prompt config: threshold calibration (1 yes = moderate), SiO texture discrimination, single-edge bc; max_pairs=200 |

---

## Files Affected (referenced but not modified)

| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | Core runner for all v1/v2/v3 benchmark test runs | Modified (progress logging); further changes expected for v4 (multi-image) |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v1.json` | Baseline v1 prompt config used as starting point for v2 iteration | No |
| `images\Alloy_Class\docs\ADJUDICATION_WORKSHEET_ONE_PAGER.md` | Referenced during label analysis for adjudication guidance | No |

---

## Bugs Encountered

### BUG-001: v1 occlusion guard too aggressive (false negatives)
- **Status:** Resolved (v2)
- **File(s):** `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v1.json`
- **Root Cause:** Occlusion guard language in v1 Stage B prompt caused model to suppress possible_beep calls whenever any occlusion signal was present, even partial occlusion
- **Fix Applied:** Revised guard in v2 to require full/majority occlusion; partial occlusion does not suppress call

### BUG-002: v1 particle location (in_trench) used as BEEP proxy (false positives)
- **Status:** Resolved (v2)
- **File(s):** `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v1.json`
- **Root Cause:** Stage B prompt did not explicitly state that in-trench location is not sufficient evidence for possible_beep; model was using location as a proxy
- **Fix Applied:** Added explicit location-not-proxy rule in v2

### BUG-003: v2 regression on BMK_0039
- **Status:** Unresolved / Deferred
- **File(s):** `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v2.json`
- **Root Cause:** Unknown; v2 evidence check additions caused BMK_0039 to flip from correct to incorrect — likely evidence checks are firing in an unexpected interaction
- **Fix Applied:** None yet; tracked as part of ongoing prompt iteration

### BUG-004: sr (sunken_residual) detection ceiling — 0% firing rate
- **Status:** Deferred (THREAD-008)
- **File(s):** `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v3.json`
- **Root Cause:** Unknown — either below model visual resolution, image format issue, or prompt language insufficient to elicit sr detection
- **Fix Applied:** None; deprioritization from scoring contract under consideration

---

## Excursions / Scope Creep Discovered

- Texture reference snip idea (extract clean SiO reference crop from BF image corner for Stage B third image) — out of scope for this session; queued as THREAD-005
- Stage A confounder rationale text verbatim-included in Stage B prefix — potential interference with isl detection for offset_surface_lines confounders; queued as THREAD-007

---

## Open Threads

- [ ] **THREAD-005** — Texture reference snip: extract clean SiO reference crop from corner of BF image; include as 3rd image in Stage B call. Requires pipeline change to `run_stage_ab_prompt_tests.py` `_call_image` to support multi-image input. This is the highest-leverage next step per user direction. *(v4/v5 scope)*
- [ ] **THREAD-006** — BC check detection gap: `bc` fires on only 6/32 nbc/possible_beep rows; 16+ missed rows have adjudicated `cbl=yes` but `bc=no`. Prompt language is not eliciting the right visual search for comparator boundary lines. *(blocking nbc/possible_beep recall)*
- [ ] **THREAD-007** — Stage A confounder language leaking into Stage B: when `sa_confounder_type=offset_surface_lines`, Stage A rationale text (included verbatim in Stage B prefix) may suppress `isl` detection despite the v3 guard. *(investigate in v4)*
- [ ] **THREAD-008** — sr (sunken_residual) detection ceiling: fires 0% across all 52 NBC rows. Either below model resolution or image format issue. Consider deprioritizing from scoring contract until a path to detection is identified.
- [ ] **THREAD-009** — BMK_0037 relabeling question: particle with moderate gt_evi was called `possible_beep` by v3 model. User to review image and decide whether label should be updated to `indeterminate`. *(affects eval set — review before next benchmark run)*

---

## Key Decisions Made

- Raw images are the default going forward for all benchmark runs (raw mode tested; confirmed not the limiting factor for fine-scale evidence detection)
- Priority is `nbc/possible_beep` recovery (misclassified small BEEPs), not `factory_beep` verification — the factory_beep population is already well-represented in production pipelines
- Evidence check framework (3 named checks → strength rules → classification) is the right architecture; detection ceiling for `bc` and `sr` is a prompt/resolution problem, not an architecture problem
- `isl` (isolated surface lines) is the most reliable check but covers only ~30% of NBC52 cases; `bc` coverage needs improvement to reach meaningful recall
- Texture reference crop (v4/v5) is the highest-leverage next step; pipeline must be modified to support 3-image Stage B calls before v4 can be tested
- Two structurally distinct BEEP populations confirmed and documented:
  - `factory_beep/possible_beep` (n=45): offset_surface_lines dominant (75%), high confidence (93%), large particles spanning multiple comparators
  - `nbc/possible_beep` (n=32): comparator_boundary_line dominant (87%), more medium confidence (41%), small particles with precise geometric boundary matching
  - Both adjudicated `possible_beep` but require different detection strategies

---

## Recommended Re-Entry

**Load these files for context:**
- `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v3.json`
- `images\Alloy_Class\tools\score_benchmark_run.py`
- `images\Alloy_Class\artifacts\benchmark_pairs_nbc_focus52.csv`
- `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`
- `images\Alloy_Class\docs\BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md`

**Suggested starting prompt:**
> "Read `images/Alloy_Class/config/stage_ab_prompt_tests_substrate_tier1_v3.json` and
> `images/Alloy_Class/reporting/run_stage_ab_prompt_tests.py` in full.
> The NBC52 scale run at v3 achieved 31% nbc/possible_beep recovery and 30% FP rate.
> Detection is binary: any evidence check firing → correct; no checks firing → always missed.
> The bc check fires on only 6/32 recovered rows despite 87% of NBC/possible_beep rows having
> adjudicated cbl=yes. The top priorities are:
> (1) THREAD-005: modify _call_image to support 3 images so a texture reference crop can be passed in Stage B (v4),
> (2) THREAD-006: improve bc check prompt language to close the comparator boundary line detection gap,
> (3) THREAD-007: investigate whether Stage A offset_surface_lines rationale text suppresses isl detection in Stage B.
> Begin with (1) — the pipeline change."

---

## Notes for Future Agent

- The `benchmark_pairs_nbc_focus52.csv` is the primary test set for nbc/possible_beep recovery work. Do not modify the split assignments or benchmark_ids without regenerating from `benchmark_v1_frozen.csv`.
- All run outputs are written to `C:/temp/alloy_benchmark/` (local, not on UNC share). These folders contain JSONL, score CSVs, and review tables but are not version-controlled. Back up any important run before rerunning with the same config name.
- The scoring contract currently has 3 evidence checks: `isl` (isolated surface lines), `bc` (boundary/comparator), `sr` (sunken residual). The `sr` check is dead weight at current model capability — weight it accordingly in analysis.
- BMK_0037 is a borderline case in the eval set. If it gets relabeled to `indeterminate`, the FP count for v3 drops by 1. Resolve THREAD-009 before the next formal benchmark comparison.
- The `run_stage_ab_prompt_tests.py` `_call_image` function currently accepts exactly 2 images (BF + DF). Multi-image support is needed for v4 (THREAD-005) before the texture reference crop can be tested.
