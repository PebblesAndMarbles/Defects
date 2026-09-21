
# Handoff: Probe Consolidation (Step 1) + VLM Enrichment/Tracking (Step 2) + Filterable Feedback Portal (Step 3)

**Written:** 2026-09-04
**Source:** `docs/VLMat90percentNEXT_STEPS.md` (user's status/direction note) + review of `tools/probe_generic_description_v1.py`..`v8.py`, `reporting/build_generic_description_html_report.py`, `tools/build_small_particle_raw_cache.py`, `tools/build_beep_labeling_tranche.py`.

**Principle goals for whoever picks this up:**
1. Manage sprawl (one canonical prompt/schema pipeline instead of 8 versioned files).
2. Minimize workflow friction — a single command should submit VLM calls **and** produce the reviewable HTML, not two manual steps.
3. Steps 2 and 3 are intentionally under-specified below because their design depends on decisions made in Step 1 (final output schema, config format, whether raw-cache is the only path). Do not over-plan them yet — just enough to not lose the thread.

---

## Answered up front: does the current probe use the RAW cache?

Yes. `tools/probe_generic_description_v8.py --use-local-cache` reads `C:\RAW_IMAGES\manifest.csv` (built/maintained by `tools/build_small_particle_raw_cache.py`) and calls the VLM directly on cached local files — no redownload, no burned-image staging. Without the flag it falls back to the older pilot-manifest + on-demand raw-download path (`_download_raw_image_to_temp`, from `classify_phase1_batch.py`).

This has already been run successfully at n=400 (`outputs/probes/generic_description_v8_localcache_400.jsonl` + matching `_manifest.csv` + `_review.html`), so the pairing logic works in practice today. Both hardening notes below were resolved as part of Step 1 (see the Step 1 status update).

> **UPDATE 2026-09-06 — both resolved in `tools/probe_generic_description.py`:** the local-cache pairing now groups on the normalized `_join_key()` (ported from `build_beep_labeling_tranche.py`) instead of the raw `inspection_time` string, and `_select_local_cache_pairs()` now reads the real `source_filespec` manifest column directly (with the old `image_filespec`/`IMAGE_FILESPEC` names kept only as a last-resort fallback).

---

## Current state inventory (as of 2026-09-04)

- **Probe scripts:** `tools/probe_generic_description_v1.py` through `v8.py` — each a full copy of the prior version with the prompt string edited inline. v8 is the only one with `--use-local-cache`; v1-v7 assume the older pilot-manifest/raw-download flow.
- **HTML report builder:** `reporting/build_generic_description_html_report.py` already exists and is schema-agnostic (renders whatever keys are in the parsed JSON, no hardcoded field list) — this is reusable as-is for Step 1, it does not need to be rewritten, just wired to run automatically.
- **Feedback loop artifacts that already exist but were never formalized:** `outputs/probes/generic_description_v1_pilot_feedback.csv` and `generic_description_v7_pilot_feedback.csv` — manual feedback was captured at least twice already via the feedback-portal widget baked into the HTML report, but there's no script that reads these back into prompt iteration decisions. Worth surfacing to the user if Step 1 touches this area, since it's relevant prior art for Step 3.
- **Config precedent to reuse:** `config/stage_ab_prompt_tests_substrate_tier1_v12.json` — the Stage A/B pipeline already uses a JSON config keyed by `prompt_version` + `prompt` text + model/token settings. The generic-description consolidation should follow this same shape rather than inventing a new one.
- **Raw cache builder:** `tools/build_small_particle_raw_cache.py` (refactored 2026-09-04_001 session, validated on 100 and 471-group runs) is the manifest source of truth going forward — `C:\RAW_IMAGES\manifest.csv`.

---

## Step 1: Consolidate `probe_generic_description_v1..v8.py` into one config-driven, one-command tool

### STATUS: COMPLETE (2026-09-06)
Built as `tools/probe_generic_description.py`, config-driven via `--prompt-config` (default `config/generic_description_prompt_v8.json`; `config/generic_description_prompt_v9.json` also exists and is used explicitly for the latest validation run). One invocation now produces the JSONL, the pair-level manifest CSV, and the HTML review (`build_report()` imported directly from `reporting/build_generic_description_html_report.py`, no subprocess/CLI hop) — confirmed by a 30-case `--use-local-cache` validation run where all three output files share the same write timestamp. `_join_key()`/`_inspection_time_norm()` were ported in for the local-cache pairing (resolving the raw-string grouping hardening note below), and the `source_filespec` manifest-column mismatch was also fixed. Archive decision resolved as option (b): `probe_generic_description_v1.py`..`v8.py` remain untouched in `tools/` as historical reference; no archive folder was created. As a bonus, the script also picked up production-coordinate enrichment (`DEFECT_COORDINATES_EXTENDED.csv`) and a reclass-log fallback (`DEFECT_COORDINATES_RECLASS_LOG.csv`), joined on the same normalized key, filling in `wafer_id`/`size_x`/`size_y`/`size_d`/`area`/`finebin`/`inspect_time` for cases that came from production rows — this is metadata flowing *into* the probe, not VLM attributes flowing *out* to production yet, but it's directly reusable for Step 2's join. Open follow-up (not blocking): `THREAD-028` — whether the v9 config should become the script's hardcoded default (currently still v8 unless `--prompt-config` is passed explicitly).

### Original scope (for reference)
- New canonical script, e.g. `tools/probe_generic_description.py` (or promote to `pipelines/` per the existing `PROJECT_STRUCTURE.md` canonical-folder convention — pick one, don't leave it ambiguous).
- Prompt/schema text moves out of the `.py` file entirely into a config JSON, e.g. `config/generic_description_prompt_v8.json`, following the `stage_ab_prompt_tests_*.json` shape:
  ```json
  {
    "prompt_version": "generic_description_v8",
    "model": "gpt-5.4-mini",
    "max_completion_tokens": 1800,
    "retry_max_completion_tokens": 2400,
    "prompt": "<the full GENERIC_DESCRIPTION_PROMPT_V8 text, unchanged>"
  }
  ```
  This lets future prompt iterations (v9, v10, ...) be added as new config files with zero code changes, directly answering the user's "accepts new prompt revisions as a config" request.
- The script keeps all the existing v8 logic (local-cache selection, raw-download fallback, retry-on-empty-response, JSONL + manifest CSV output) — this is a refactor/consolidation, not a rewrite of working behavior.
- **One-command orchestration (the actual friction fix):** after writing the JSONL + manifest CSV, the script should invoke `reporting/build_generic_description_html_report.py` itself (either via direct Python import + function call, or `subprocess.run([...])` if that's cleaner given the two scripts currently live in separate directories with their own `sys.path` bootstrapping) so a single invocation produces the reviewable HTML at the end, instead of requiring a second manual command. Print the final HTML path clearly at the end of the run.
- Archive (do not delete) `probe_generic_description_v1.py`..`v7.py` — e.g. move to `tools/OLD/` or `docs/learnings/`, whichever matches how prior archival was done elsewhere in this repo (check `images/Alloy_Class/OLD/` for precedent before picking).
- Port the normalized `_join_key()`/`_inspection_time_norm()` helpers from `build_beep_labeling_tranche.py` into the local-cache pairing logic (see hardening note above).

### Explicitly out of scope for Step 1
- No prompt content changes — v8's prompt is carried over verbatim into the v8 config.
- No new evidence/attribute fields.
- No decision yet on where the consolidated script's config files should live long-term as part of the bigger `Phase 0.5` folder taxonomy (see `alloy_class_next_steps_plan.md` in repo memory) — just don't add new files at `Alloy_Class` root.

### Verification
- Re-run the consolidated tool against the same 400-case local-cache batch (or a smaller subset) and diff the resulting JSONL against `generic_description_v8_localcache_400.jsonl` field-for-field (excluding timestamps) to confirm the refactor is behavior-preserving.
- Confirm the one-command run produces both the JSONL/manifest CSV and a valid HTML file without a second manual invocation.
- Confirm archived v1-v7 files are not referenced anywhere else (`grep` for their filenames) before moving them.

---

## Step 1 continuation: chunked/incremental VLM submission (proposed 2026-09-07, not yet implemented)

User wants to submit the canonical probe in batches (e.g. ~400 defects at a time) going forward, each batch picking the *next* newest-first set of defects that have **not already been submitted to the VLM** in a prior run — the same newest-first-plus-exclusion idea `build_beep_labeling_tranche.py` uses, but applied to VLM probe runs rather than BEEP-labeling tranches.

**Important distinction, don't conflate the two:** `build_beep_labeling_tranche.py`'s exclusion logic checks against `beep_evidence_ground_truth.csv` and prior `tranche_*_cases.csv` files — that's the BEEP-labeling registry. There is currently **no equivalent "already VLM-processed" tracking** for `probe_generic_description.py`; every run just takes the newest N local-cache pairs matching the class/image-id/local-path filters, with no memory of prior runs. That's the actual gap to design here.

**Two implementation options (need a decision before building):**
1. **Registry file (recommended)** — a small persistent CSV, e.g. `outputs/probes/generic_description_processed_registry.csv`, columns `wafer_key, inspection_time, defect_id, join_key, prompt_version, run_jsonl_path, processed_at_utc`. After each run, `probe_generic_description.py` appends every successfully-completed case's join key. The next run loads the registry, excludes those join keys from `_select_local_cache_pairs()`'s candidate pool, then takes the next `--max-pairs` newest-first as it already does today. Self-maintaining — nothing to remember to pass on the command line.
2. **Glob prior outputs at runtime** — no persistent registry; accept one or more `--exclude-from-jsonl <path-or-glob>` arguments and build the exclusion set on the fly from listed prior runs each time. Simpler to build, but requires remembering every prior run's path and gets slower as history grows.

**Only register successes:** exclude a case from future chunks only when its record has `status == "ok"`. Cases that failed (e.g. `raw_download_failed`) should stay in the candidate pool so the next chunk naturally retries them, rather than being permanently skipped.

**Open questions before implementing:**
1. Confirm registry-file approach (option 1) over glob-based exclusion (option 2).
2. Confirm chunk size stays a per-run `--max-pairs` choice (already supported) rather than a fixed default.
3. Confirm this should be a new flag directly on `probe_generic_description.py` (e.g. `--processed-registry-csv <path>`, read for exclusion and appended after the run) rather than a separate pre-filter script — recommended, since `--use-local-cache` already owns the selection logic and this avoids adding yet another script.

---

## Step 2 (depends on Step 1, now unblocked): Enrich production CSVs with VLM attributes + track real particle rate excluding misclassified BEEPs

Step 1's output schema is now locked (see status above), so this can be picked up. Not designed yet beyond the notes below.

**Groundwork already available from Step 1** — `tools/probe_generic_description.py` already loads and joins `DEFECT_COORDINATES_EXTENDED.csv` + `DEFECT_COORDINATES_RECLASS_LOG.csv` on the normalized `(wafer_key, inspection_time, defect_id)` key to pull metadata *into* each probe case. Step 2 is the inverse direction (push VLM attributes *out* onto a production-facing CSV) but should reuse the same `_join_key()` helper and lookup-building pattern already proven there rather than re-deriving it.

**STATUS as of 2026-09-07: mostly built, one validation gap remains.** `tools/enrich_production_with_vlm_attributes.py` exists and its column shape is complete — the enriched CSV carries every VLM attribute (`coarse_shape`, `coarse_texture`, all `shape_*`/`texture_*` flags, `defect_count`, `location_relative`, `confidence`, etc.) plus join/provenance columns (`enrichment_status`, `truth_label`, `truth_is_beep`, `truth_alignment_state`, `current_class`, `current_reclass`, `vlm_prompt_version`). Join-key mechanics are proven solid against the 400-case `generic_description_v9` batch (400/400 joined, 0 missing, `truth_beep_rows=94`/`truth_non_beep_rows=306` stable across the last several dev iterations). **However, every dev iteration so far (`_enriched` through `_enriched_v9`) was run with `--production-csv` pointed at the VLM manifest CSV itself (a self-join), never at the real `outputs/defects/DEFECT_COORDINATES_EXTENDED.csv`.** That's the one remaining validation step before Step 2 can be called done — it costs no new VLM calls, just a different `--production-csv` argument against data already collected. Immediate next action: rerun against the real production CSV and inspect the real-world join/coverage rate (`filtered_out_rows` should no longer be 0 the way it trivially was in the self-join).

**Notes to preserve for whoever starts this:**
- Join key for enrichment should be `(wafer_key, inspection_time, defect_id)` — same key already used by `build_beep_labeling_tranche.py` and the local-cache pairing logic, so reuse the (now-shared, post-Step-1) normalized join helper rather than re-deriving it a third time.
- Ground truth for "real particle vs misclassified BEEP" already exists and is accumulating: `outputs/beep_evidence/beep_evidence_ground_truth.csv` (~1500 of 6000+ dispositioned as of this week per the user). Any "true particle metric over time" calculation should exclude defects where this ground truth says `BEEP`, not just trust the factory `CLASS` label.
- User's stated interest: track metrics for specific VLM-derived attributes over time too (circles, jagged, `defect_count > 1`, clumped), not just the overall particle-vs-BEEP split — so the enrichment output should preserve every structured attribute field from the probe output, not just a coarse classification.
- Likely adhoc/batch script rather than wired into the scheduled `BE_QUERY_FILES` pipeline at first, per the user's stated preference ("probably on adhoc basis to start until prompt is finalized").

---

## Step 3 (depends on Steps 1 & 2): Filterable HTML report / feedback portal for VLM labels

Not designed yet — also deliberately deferred, same reasoning as Step 2.

**Notes to preserve for whoever starts this:**
- There is real prior art to reuse, not build from scratch:
  - `reporting/build_generic_description_html_report.py` already renders per-case images + all structured attributes + a feedback-portal widget (imported from `build_probe_html_report.py`).
  - Two portals already exist as patterns: `reporting/feedback_portal/` (port 8000) and `reporting/beep_labeling_portal/` (port 8001). A third portal for this purpose should use **port 8002** and a clearly different name to avoid the exact mixup documented for the first two (`beep_evidence_labeling_tool.md` in repo memory — two near-identical portal folders on different ports caused a real submit failure once).
  - Feedback CSVs already exist from earlier ad-hoc use of the existing widget: `generic_description_v1_pilot_feedback.csv`, `generic_description_v7_pilot_feedback.csv`. Worth reviewing these before designing the new filter/grouping UI — they may already contain usable signal or reveal what the widget currently lacks.
- User's stated interest beyond a flat per-case list: **group by attribute** so filtered views can show something like "these attributes show BEEP evidence more often than others, and this specific image doesn't show evidence alone but is guilty by association" — i.e., an aggregate/cohort view layered on top of the existing per-case detail view, not a replacement for it.
- Depends on Step 2's enrichment output existing first, since the filtering/grouping needs real production-scale data (not just a 400-case pilot batch) to be useful.

---

## Recommended re-entry prompt for a fresh session
> "Read `docs/HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md` in full, then implement Step 1: consolidate `tools/probe_generic_description_v1.py`..`v8.py` into a single config-driven script with one-command VLM-submission + HTML-report generation, reusing `reporting/build_generic_description_html_report.py` unchanged."

## Re-entry prompt now that Step 2 is complete
> "Read `docs/HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md` in full, focusing on the Step 2 status update (2026-09-07) and the `_truth_bucket()` fix in `tools/enrich_production_with_vlm_attributes.py`. Step 1 and Step 2 are both complete and validated against the real production CSV and the 400-case `generic_description_v9` batch. Next up: either (a) the 'Step 1 continuation: chunked/incremental VLM submission' design section (needs the three open questions answered before building), or (b) Step 3's filterable HTML report/feedback portal, which now has real enriched production data to build against instead of just the 400-case pilot batch."

## Current next-step note
Step 1 and Step 2 are complete. The next branch is intentionally left open: either continue the chunked/incremental VLM submission design, or move on to Step 3's filterable HTML report/feedback portal now that enriched production data exists.

## STATUS UPDATE 2026-09-08: chunked submission built and hardened; consolidation step needed before enrichment can run on the full set

**Chunked/incremental submission is now built**, not just designed: `tools/run_generic_description_chunked.py` orchestrates repeated tranche runs against `tools/probe_generic_description.py --use-local-cache`, using a persistent registry CSV (`C:\RAW_IMAGES\generic_description_registry\generic_description_processed_registry.csv`) for exclusion, per the registry-file design chosen earlier in this doc.

**Three real bugs found and fixed today while running it for real:**
1. **Join-key precision mismatch (the actual root cause of duplicate VLM submissions).** `manifest.csv` stores the same timestamp two ways: `case_id` embeds full precision (`2026-09-01 19:15:17`), but the separate `inspection_time` column is truncated to the minute (`9/1/2026 19:15`, seconds always `:00`). The registry was always populated using the full-precision value, but `_select_local_cache_pairs()` computed its exclusion join-key from the truncated column, so exclusion silently never matched anything. Fixed in `_select_local_cache_pairs()` to derive the join-key timestamp from `case_id` (matching the registry) instead of the separate column.
2. **Manifest-CSV write crash on parsed-failure rows.** `csv.DictWriter` used only row 0's keys as the fixed column set, but rows with a VLM JSON-parse failure add an extra `raw_text` key via `_flatten_parsed_fields`, crashing `writerows()` on any later row that has it. Fixed to compute the fieldname union across all rows (plus `extrasaction="ignore"` as a backstop).
3. **Registry accumulated duplicates on every append.** `_append_processed_registry()` never checked for existing keys before writing (unlike the orchestrator's seed function, which does). Fixed to skip already-registered keys. One-time cleanup applied: registry deduped from 1199 -> 806 rows (backup at `generic_description_processed_registry_backup_before_dedupe.csv`), keeping the latest `processed_at_utc` per `join_key`.

**Current data status (as of 2026-09-08):** the processed registry has **806 clean, deduped defects**, all `prompt_version=generic_description_v9`, sourced from 3 distinct JSONL/manifest run-file pairs (all still present on disk):
- `C:\RAW_IMAGES\generic_description_registry\bootstrap_seed.jsonl` (7 rows won the dedupe)
- `C:\RAW_IMAGES\generic_description_registry\generic_description_next_generic_description_v9_20260908T044636Z\chunk_001\...jsonl` (400 rows)
- `C:\RAW_IMAGES\generic_description_registry\generic_description_next_generic_description_v9_20260908T052401Z\chunk_001\...jsonl` (399 rows)

**Important correction for whoever picks this up next:** the registry CSV is a provenance/tracking table only (`join_key`, `wafer_key`, `inspection_time`, `defect_id`, `prompt_version`, `status`, `run_jsonl_path`, `run_manifest_csv_path`, `processed_at_utc`) -- it does **not** contain the actual VLM attributes (`coarse_shape`, `defect_count`, etc.), and `tools/enrich_production_with_vlm_attributes.py` still only accepts one `--vlm-manifest-csv`/`--vlm-jsonl` pair at a time. **Enrichment cannot be pointed at the registry directly.**

**Concrete next action (not yet built):** a small consolidation step that walks the 806 registry rows, and for each `join_key` pulls the winning VLM record from its `run_jsonl_path`/`run_manifest_csv_path` (exactly the same lookup pattern already used for the chunk_001 crash-recovery earlier today), producing **one** clean, deduped JSONL + manifest CSV pair spanning all 3 source files. That consolidated pair can then feed directly into the existing, unmodified `enrich_production_with_vlm_attributes.py` -- no changes needed there.

