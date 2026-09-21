## Plan: VLM Overhaul — Remaining Tracks (Housekeeping Tail, Prompt Iteration, Registry, Enrichment)

Housekeeping-driven git push is complete (`origin/master` at `393fb08`); this plan covers what's left of the original `VLM_Overhaul.md` ask. Scope decisions already made (see Decisions below) trim this to four ordered tracks: a small housekeeping tail, prompt finalization, a fresh registry, and coordinate/metrics enrichment with WDS/BOST. RAW_IMAGES→UNC migration is explicitly out of scope. Given the user is transitioning out of this area, bias toward the lightest path that produces a working analysis deliverable, not a broader refactor.

**Steps**
1. Track A — Stage A/B + benchmark-scoring housekeeping tail. **STATUS: DONE (commit `333a74a`, not yet pushed).**
   - Moved to `OLD/` (via `git mv`, history preserved) across `tools/`, `reporting/`, `pipelines/`, `config/`, `docs/`: `caption_phase1_batch.py`, `run_stage_ab_prompt_tests.py`... **correction found during execution: `run_stage_ab_prompt_tests.py` was NOT moved** — see exclusion note below. Moved: `build_stage_ab_html_report.py`, `build_phase1_html_report.py`, `compare_phase1_runs.py`, `review_phase1_quality.py`, `probe_alloy_image_response.py`, `probe_describe_then_classify.py` (+`_v14`), `probe_fn_feature_perception.py`, `probe_beep_lexicon_v1.py`/`v2.py`, `run_benchmark_vlm.py`, `score_benchmark_run.py`, `score_probe_run.py`, `normalize_probe_output.py`, `normalize_benchmark_adjudication.py`, `build_benchmark_candidates.py`, `assign_benchmark_split.py`, `image_fft.py`, `wheelhouse_audit.py`, `validate_alloy_usage_patch.py`, `build_raw_image_redownload_manifest.py` (confirmed superseded duplicate), all `stage_ab_prompt_tests_*.json`/`phase1_settings*.json` configs, `frozen_pairs/`, `inset_surface_line_modification.md`, and the matching docs (`ADJUDICATION_WORKSHEET_ONE_PAGER.md`, `BENCHMARK_CANDIDATE_TOOL_SCOPE.md`, `BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md`, `FROZEN_PAIR_RUNBOOK.md`, `HANDOFF_BENCHMARK_VLM_READINESS_AUDIT.md`, `HANDOFF_PROMPT_ITERATION_1PAIR_RUNTIME.md`, `PHASE1_ACCEPTANCE_CHECKLIST.md`, `PHASE1_RUNBOOK.md`, `PLAN_SUBSTRATE_PROMPT_TEST_20_IMAGES.md`, `PROMPT_HARDENING.md`, `SUBSTRATE_PROMPT_TIER20_RESULTS.md`, `WHEELHOUSE_BLOCKER_20260726.md`, `v12_post_mortem.md`).
   - **IMPORTANT EXCLUSION (do not move these two):** `pipelines/classify_phase1_batch.py` and `reporting/run_stage_ab_prompt_tests.py` were removed from the candidate list after grep confirmed both are live runtime imports of the current canonical `tools/probe_generic_description.py` (and `classify_phase1_batch.py` is also imported by `tools/build_small_particle_raw_cache.py`) — `run_stage_ab_prompt_tests.py` supplies `_call_image()`/`_load_env_from_supported_locations()` and `classify_phase1_batch.py` supplies raw-image-download config/helpers. The "abandon Stage A/B" decision applies to the prompt/config architecture, not to this shared utility code. Any future cleanup pass must re-check this before moving either file.
   - Verified via grep that no remaining live `.py` file (outside `OLD/`) imports any of the moved modules, and no live script references the moved config paths, before committing.
   - Gotcha for future agents on this UNC-share workspace: `git mv` does **not** auto-create a nonexistent destination directory here (fails with "No such file or directory" even though the source file exists) — `New-Item -ItemType Directory` the destination `OLD/` folder first, then `git mv`.
   - This is independent of Tracks B-D; safe to do in parallel or defer without blocking anything.
   - Not yet pushed — awaiting go-ahead.
2. Track B — Finalize the prompt iteration on `generic_description_v9`.
   - Flip `images/Alloy_Class/tools/probe_generic_description.py`'s hardcoded default from `config/generic_description_prompt_v8.json` to `config/generic_description_prompt_v9.json`, closing THREAD-028.
   - Do the next round of content revisions on the v9 prompt (the actual wording/schema changes the user wants), validating iteratively against the adhoc HTML review tooling that already exists (`reporting/build_generic_description_html_report.py`, `reporting/build_vlm_attributes_filterable_report.py`) rather than building new review tooling.
   - Treat this as the gating step for Track C — do not start a new registry until the prompt is considered final for this round.
3. Track C — Start a fresh registry once Track B is locked.
   - Per the user's decision, the new registry is intentional and timed to when prompt revisions are complete, so accumulated labels reflect only the revised prompt (not a mix of v9-pre-revision and v9-post-revision outputs).
   - Reuse the existing chunked/registry machinery (`tools/run_generic_description_chunked.py`, `tools/consolidate_generic_description_registry.py`) with a new registry root rather than building new infrastructure; do not silently merge old and new registry state.
   - Decide explicitly (don't assume) whether the old registry (`C:\RAW_IMAGES\generic_description_registry\`) is archived, left in place untouched, or referenced for before/after comparison.
4. Track D — Coordinates + metrics enrichment with WDS/BOST (the principal analysis deliverable).
   - Confirmed low-risk reuse path: `WDS/APEX_ENTITY/09_enrich_production_csv.py` and `BOST/adhoc_bost_gate_rollout.py` both already join on `(WAFER_ID, LAYER)`, and `outputs/defects/DEFECT_COORDINATES_EXTENDED.csv` already carries both of those exact columns natively. Coordinates enrichment is the same join logic already built for the metrics CSVs, just re-pointed at the coordinates CSV (or its VLM-enriched successor) instead of the wafer-level metrics CSV — per the user's "reuse existing methods" decision, do not redesign the join.
   - Produce a coords-level enriched CSV carrying VLM attributes (from Track C's registry, joined on the existing `(wafer_key, inspection_time, defect_id)` key already proven in `enrich_production_with_vlm_attributes.py`) plus the WDS/BOST wafer-level columns broadcast onto each defect row via `(WAFER_ID, LAYER)`.
   - Do a light verification pass confirming the coords-level WDS/BOST values match the already-existing metrics-level enrichment for the same wafer/layer (they should, since it's the same source data and same key) — this is a consistency check, not a re-architecture.
   - Only after the enriched dataset exists, explore aggregation patterns analogous to what's already been done for ground-truth labels (circles, `defect_count > 1`, small/large SMP metrics) against the VLM attribute set. This is intentionally open-ended per the user — don't over-plan the specific attribute combinations up front.

**Relevant files**
- `images/Alloy_Class/VLM_Overhaul.md` — original scope anchor for this whole effort.
- `images/Alloy_Class/tools/probe_generic_description.py` — prompt-config default to flip (Track B).
- `images/Alloy_Class/config/generic_description_prompt_v9.json` — prompt content to revise (Track B).
- `images/Alloy_Class/tools/run_generic_description_chunked.py`, `images/Alloy_Class/tools/consolidate_generic_description_registry.py` — registry machinery to reuse with a new root (Track C).
- `images/Alloy_Class/tools/enrich_production_with_vlm_attributes.py` — proven `(wafer_key, inspection_time, defect_id)` join pattern for VLM attributes (Track D).
- `WDS/APEX_ENTITY/09_enrich_production_csv.py`, `BOST/adhoc_bost_gate_rollout.py` — existing `(WAFER_ID, LAYER)` join logic to reuse against coordinates (Track D).
- `outputs/defects/DEFECT_COORDINATES_EXTENDED.csv` — coordinates enrichment target; already has `WAFER_ID`/`LAYER` columns.
- `images/Alloy_Class/docs/HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md` — background on the v9 pipeline and open THREAD-028.

**Verification**
1. Track A: `git mv`-based moves only; confirm no remaining references to moved files via grep before finalizing (same check pattern used for `build_raw_image_redownload_manifest.py`).
2. Track B: confirm `probe_generic_description.py` runs end-to-end against v9 by default with no `--prompt-config` flag; spot-check revised-prompt outputs via the existing HTML review tools before calling the revision final.
3. Track C: confirm the new registry root starts empty (or from an explicit, documented seed) and contains zero pre-revision-prompt rows before any bulk run.
4. Track D: for a small sample of wafers, confirm the coords-level WDS/BOST values match the existing metrics-level enrichment for the same `(WAFER_ID, LAYER)`; confirm VLM-attribute join coverage stats (joined vs. missing) are reported explicitly, not silently dropped.

**Decisions**
- Track A trimmed to the Stage A/B + benchmark-scoring `OLD/` move only; RAW_IMAGES→UNC migration is dropped from scope entirely (was for multi-user sharing, not gating).
- Join-key strategy: reuse existing per-pipeline join logic (WDS/BOST already on `(WAFER_ID, LAYER)`, VLM attributes already on `(wafer_key, inspection_time, defect_id)`) rather than standardizing keys across pipelines first.
- Plan is self-driven/lightweight — optimized for the user + agents finishing it directly, not for a successor picking it up cold.
- Single combined plan covering all four tracks rather than separate per-track plan files.
- Sequencing is B → C → D with A parallel/optional; do not start Track C before Track B is explicitly declared final.

**Further Considerations**
1. Exact scope of "final" for Track B's prompt revision isn't defined yet — needs an explicit go/no-go moment from the user before Track C starts, not an agent guessing readiness.
2. Track C's disposition of the old registry (archive vs. leave vs. keep for comparison) is unresolved — flag for a decision when Track C actually starts.
3. Track D's specific attribute-aggregation combinations are deliberately left open per the user; the enriched dataset should be built first, with aggregation exploration as a follow-on, not blocking the initial join.
