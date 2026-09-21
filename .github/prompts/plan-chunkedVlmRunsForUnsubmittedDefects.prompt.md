## Plan: Chunked VLM Runs for Unsubmitted Defects

Goal: extend the completed Step 1 probe workflow so it can keep issuing VLM calls for the next unsubmitted SMALL_PARTICLE defects, using a persistent processed-registry CSV to avoid reprocessing cases that already produced successful VLM output. Keep the current probe/enrichment contract intact, and make the new batch outputs easy to fold into the existing production enrichment path.

**Steps**
1. Lock the batch-selection contract for Step 1 continuation.
1. Define the batch unit as the next newest-first set of defects that have not yet been processed successfully by the canonical probe.
1. Treat `status == "ok"` as the only terminal success state for exclusion; failed or errored rows remain eligible for later retry.
1. Use a persistent registry CSV as the source of truth for processed cases, not ad hoc manual run bookkeeping.
1. Keep chunk size as the existing per-run `--max-pairs` control rather than introducing a fixed global batch size.

2. Add registry-driven exclusion to the canonical probe.
1. Extend [tools/probe_generic_description.py](tools/probe_generic_description.py) so local-cache selection can read a processed-registry CSV and exclude rows whose normalized join key already appears there.
1. Reuse the existing normalized join key helpers already in the probe: `_join_key()`, `_normalize_join_value()`, and `_inspection_time_norm()`.
1. Keep the current newest-first ordering in `_select_local_cache_pairs()` so the only new behavior is exclusion of already-processed cases before truncating to `--max-pairs`.
1. Add run metadata to the registry write path so each successful case records join key, prompt version, source manifest/run path, and processed timestamp.

3. Make additional VLM runs composable for enrichment.
1. Extend the probe output contract so each batch still writes the same JSONL and manifest CSV shape already consumed by Step 2.
1. Decide whether the enrichment step should accept a single run, a list of run files, or a directory/glob of run artifacts; prefer the simplest form that allows multiple batch outputs to be merged without manual CSV stitching.
1. Keep the enrichment join keyed on normalized `(wafer_key, inspection_time, defect_id)` so new batches can be appended without changing downstream logic.
1. Preserve the current attribute set and provenance columns in [tools/enrich_production_with_vlm_attributes.py](tools/enrich_production_with_vlm_attributes.py); the new work is about aggregation and coverage, not schema expansion.

4. Wire the orchestration path for repeated batch submission.
1. Add a clear command-line path for "process next chunk" runs, reusing the existing prompt config JSON as the stable control surface.
1. Make the default run path self-maintaining: load the registry, select the next unprocessed cases, submit them, then append successful joins back into the registry.
1. Keep the current one-command HTML report generation behavior intact after each batch so every chunk remains reviewable immediately.

5. Validate on a small incremental slice before scaling.
1. Run one small chunk against the local RAW cache and confirm the registry excludes those rows on the next invocation.
1. Confirm only successful rows are written to the registry and failed rows remain eligible on rerun.
1. Verify that enrichment can consume multiple batch outputs and still produce joined rows with the same join rate and provenance columns.
1. Check that the resulting batch outputs remain compatible with the existing HTML review report and Step 2 enrichment artifacts.

**Relevant files**
- [tools/probe_generic_description.py](tools/probe_generic_description.py) - canonical probe entrypoint; local-cache selection and output write path.
- [tools/enrich_production_with_vlm_attributes.py](tools/enrich_production_with_vlm_attributes.py) - Step 2 enrichment contract that should consume multiple batch outputs without schema drift.
- [docs/HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md](docs/HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md) - source handoff describing Step 1 continuation and the open registry choice.
- [config/generic_description_prompt_v8.json](config/generic_description_prompt_v8.json) - prompt/model/token config precedent for any new runtime knobs.
- [config/generic_description_prompt_v9.json](config/generic_description_prompt_v9.json) - latest validated prompt config example.
- `C:\RAW_IMAGES\` - actual default landing zone for chunked JSONL, manifest CSV, and HTML when `--use-local-cache` is set without an explicit `--output-jsonl` override (confirmed in `probe_generic_description.py`: the default resolves from `args.source_manifest_csv`'s parent, which defaults to `C:\RAW_IMAGES\manifest.csv`, and matches every real run done so far). The processed-registry CSV should live here too, not in `outputs/probes/`.

**Verification**
1. Run a small `--use-local-cache` batch and confirm the registry CSV receives only `status == "ok"` rows.
1. Re-run the same command and confirm the selected defect set advances to the next unprocessed rows.
1. Validate that the enrichment step still joins on normalized defect keys and that the output row count reflects all supplied batch artifacts.
1. Confirm the HTML review report is still produced automatically for each chunk.

**Decisions**
- Use a persistent processed-registry CSV rather than glob-based exclusion.
- Keep `--max-pairs` as the per-run batch-size control.
- Treat "additional image sets" here as the next unsubmitted defect chunks, not as a broader modality expansion.
- Keep the prompt config JSON as the primary runtime control surface.

**Further Considerations**
1. If you later want broad image-ID support beyond the current BF/DF pair, that should be a separate design track because `_select_local_cache_pairs()` and the RAW cache builder both currently assume image IDs 2 and 3.
1. If the registry file grows large, it may be worth adding a compact index or deduplication pass, but that is a later scaling concern rather than a first-step blocker.
