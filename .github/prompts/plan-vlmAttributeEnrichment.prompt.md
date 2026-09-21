## Plan: VLM Attribute Enrichment for Production CSVs

Step 2 should be an adhoc enrichment/export pass, not a scheduled pipeline change yet. The core implementation is: read the production defect CSV, join the canonical generic-description VLM output by the normalized `(wafer_key, inspection_time, defect_id)` key, apply BEEP-ground-truth exclusions when calculating particle-rate metrics, and preserve the full structured VLM attribute payload so downstream analysis can slice by specific attributes like circles, jagged, `defect_count > 1`, and clumped.

**Steps**
1. Lock the input/output contract before coding. Use the Step 1 canonical probe output as the VLM source of truth, and choose one production source CSV to enrich first rather than trying to backfill every downstream table at once. Reuse the normalized join helper pattern already proven in `images/Alloy_Class/tools/probe_generic_description.py` and `images/Alloy_Class/tools/build_beep_labeling_tranche.py`, so the join key is derived the same way everywhere.
2. Build the enrichment lookup layer. Load the production CSV, the VLM JSONL/manifest pair, and `outputs/beep_evidence/beep_evidence_ground_truth.csv`; dedupe the BEEP ground truth by latest `submitted_at_utc`, then construct a join map keyed by normalized `(wafer_key, inspection_time, defect_id)`. Keep a clear join-status field so missing VLM rows are visible instead of silently dropped.
3. Emit a row-preserving enriched CSV. For each production defect row, copy the original columns and append all structured VLM fields verbatim, plus run metadata such as prompt version, model, probe run timestamp, and source probe path. Keep the coarse VLM verdict and the structured attributes together; do not compress them into a single derived label because the user wants attribute-specific metrics later.
4. Add metric outputs for true-particle tracking. Produce a compact summary CSV or JSON that buckets by inspection date/time and reports total defects, GT-BEEP-excluded counts, true-particle counts, overall true-particle rate, and attribute frequencies for the VLM fields of interest. The denominator for particle-rate metrics should exclude defects whose ground truth says BEEP, not just rows where the factory `CLASS` is non-particle.
5. Validate with a narrow slice first, then broaden. Run the enrichment on a small date slice or limited defect subset, verify join counts against known keys, confirm GT-BEEP exclusions match the evidence file, and check that the preserved VLM attribute columns survive unchanged from the probe output. If the slice behaves, rerun on the full intended production window.

**Relevant files**
- `images/Alloy_Class/docs/HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md` — Step 2 requirements and dependency notes.
- `images/Alloy_Class/tools/probe_generic_description.py` — canonical probe output schema and normalized join helper to reuse.
- `images/Alloy_Class/tools/build_beep_labeling_tranche.py` — source for the shared normalized join-key pattern.
- `images/Alloy_Class/reporting/build_beep_misclassified_report.py` — concrete example of joining `beep_evidence_ground_truth.csv` back to tranche data.
- `images/Alloy_Class/docs/HANDOFF_BEEP_MISCLASSIFIED_REPORT.md` — confirms the BEEP ground-truth file shape and dedupe expectations.
- `images/Alloy_Class/outputs/beep_evidence/beep_evidence_ground_truth.csv` — exclusion source for true-particle metrics.
- `outputs/defects/DEFECT_COORDINATES_EXTENDED.csv` — likely production-side enrichment target.

**Verification**
1. Compare join counts on a small slice against known keys and confirm the normalized join key matches between production rows and VLM rows.
2. Check that rows labeled BEEP in `beep_evidence_ground_truth.csv` are excluded from the true-particle denominator in the summary metrics.
3. Confirm the enriched CSV preserves every structured VLM field from the probe output and does not collapse them into a coarse-only export.
4. Inspect a few joined rows manually in the output CSV to verify the correct VLM attributes land on the intended production defect keys.

**Decisions**
- Start with an adhoc exporter, not the scheduled BE query pipeline.
- Preserve all structured VLM attributes instead of collapsing them to a coarse-only label.
- Use BEEP ground truth as the correction source for true-particle metrics.
- Keep join failures explicit so key drift or missing probe coverage is diagnosable.
