# APEX@ENTITY Enrichment — Scoping + Staged Implementation Plan

**Target production input**: `outputs/wafer/8M5CL_8M6CL_EXTENDED.csv`  
**All development scoped to**: `WDS/APEX_ENTITY/`  
**Design reference**: `WDS/APEX_ENTITY/APEX_ENTITY_ENRICHMENT_HANDOFF.md`  
**Column naming convention reference**: `BOST/BOST_ENRICHMENT_REGISTRY_PLAN.md` (multi-step alias prefixing pattern)

---

## Plan: APEX@ENTITY Enrichment — Scoping + Staged Implementation

**TL;DR**: Validate APEX@ENTITY column availability against known aliases, then implement staged enrichment (pilot 10 wafers → validate match rate → full enrichment) with flattened output merged into production CSV. All 5 subfields per matched chamber, prefixed by alias to avoid column-name collisions across 10 FULL_FLOW_ALIASES.

---

## Steps

### Phase 1 — Scoping + Environment Setup

1. **Verify APEX@ENTITY dataset version** — Query WDS to confirm `V6` is still current (use `wds_active_versions.get_current_wds()` pattern from `dev/idealapex/core_support/wds_active_versions.py`), not hardcoded. Create `WDS/APEX_ENTITY/01_check_wds_versions.py`.
   - *Output*: console log + one-line `.txt` artifact showing resolved version (e.g., `APEX@ENTITY current version: V6`).
   - *Depends on*: WDS client + CA bundle already configured (from `wds_client_setup.md`).

2. **Probe APEX@ENTITY columns for all 10 FULL_FLOW_ALIASES** — For each of the 10 aliases (5 M5 + 5 M6), use `client.row.columns()` with pattern `^APEX@ENTITY@{alias}@V6@`, ONE ALIAS PER CALL (see perf notes in `wds_client_setup.md`, critical for reliability). Reuse a real wafer per alias from the BOST pilot set to be consistent.
   - *Output*: Raw column lists saved to `WDS/APEX_ENTITY/02a_raw_columns_<ALIAS>.txt` (one per alias), for spot-checking; summary CSV `WDS/APEX_ENTITY/02b_apex_entity_column_schema.csv` listing all resolved columns with metadata (alias, segment count, field type: top-level vs. subentity).
   - *Script*: `WDS/APEX_ENTITY/02_probe_all_aliases.py`.
   - *Depends on Step 1* (resolved version).

3. **Parse and categorize columns** — From raw probes, extract and categorize:
   - Top-level fields: `ENTITY`, `OPERATION`, `PRODUCT`, `WAFER_ENTITY_END_TIME`.
   - Candidate-slot fields: `SUBENTITY_0..14` (each with 5 subfields: `BATCH_IDLE`, `PRIOR_ALIAS`, `PROCESS_ORDER`, `SEQUENCE`, `UTILIZATION`).
   - Validate that all 10 aliases have the same field structure (or document any deviations).
   - *Output*: `WDS/APEX_ENTITY/02b_apex_entity_column_schema.csv` (enriched with field categories).
   - *Depends on Step 2*.

### Phase 2 — Pilot Validation (10 Wafers)

4. **Extract pilot wafer list** — Reuse the 10 wafers from BOST registry pilot (`step1_recent_wafer_registry_pilot.py`, line ~50-60 or grep for `PILOT_WAFERS`). Create a two-column CSV (`WAFER_ID`, `LAYER`) as the pilot manifest in `WDS/APEX_ENTITY/04_pilot_wafers.csv`.
   - *Output*: `WDS/APEX_ENTITY/04_pilot_wafers.csv`.
   - *Depends on*: BOST pilot wafers being stable/documented.

5. **Pull APEX@ENTITY for pilot wafers, all 10 aliases** — For each pilot wafer:
   - Determine its layer (8M5CL → 5 aliases, 8M6CL → 5 aliases).
   - For each applicable alias, call `client.query.download_dataframe()` with `include_patterns=[f"^APEX@ENTITY@{alias}@V6@"]`.
   - Assemble one row per (wafer, alias) pair with all resolved columns.
   - Save raw pull as `WDS/APEX_ENTITY/05a_pilot_raw_apex_entity_<TIMESTAMP>.csv` (wide, unprocessed).
   - *Script*: `WDS/APEX_ENTITY/05_pull_pilot_apex_entity.py`.
   - *Depends on Steps 1–4*.

6. **Match SUBENTITY_N to actual chamber (resolution logic)** — For each (wafer, alias) row from Step 5:
   - Look up the wafer in `outputs/wafer/8M5CL_8M6CL_EXTENDED.csv` to find its `SUBENTITY` value (e.g., `AME403_PM4`).
   - Compare against the wafer's WDS `SUBENTITY_0..14` values (one of them should match).
   - Identify matching `N` (slot index).
   - Extract that slot's 5 subfields (`BATCH_IDLE`, `PRIOR_ALIAS`, `PROCESS_ORDER`, `SEQUENCE`, `UTILIZATION`) as the "matched chamber" metadata for this (wafer, alias) pair.
   - Log any mismatches (e.g., `SUBENTITY` not found in any slot) for review.
   - *Output*: `WDS/APEX_ENTITY/05b_pilot_matched_wafers.csv` with columns: `WAFER_ID`, `LOT7`, `LAYER`, `ALIAS`, `MATCHED_SLOT_INDEX`, `WDS_SUBENTITY`, `PRODUCTION_CSV_SUBENTITY`, `MATCH_STATUS` (OK/MISMATCH), plus all 5 matched-slot subfields.
   - *Script*: `WDS/APEX_ENTITY/05_pull_pilot_apex_entity.py` (same script as Step 5, adds matching logic).
   - *Depends on Steps 3–5*.

7. **Validate match rate + investigate mismatches** — Report:
   - Total pilot rows: 10 wafers × 5–10 aliases per layer = ~50–100 rows (exact count depends on wafer coverage).
   - Match-rate metric: `(OK rows / total rows) × 100%`.
   - Mismatch rows (if any): alias, wafer, expected `SUBENTITY`, WDS values that didn't match → surface for human review.
   - *Output*: Console summary + artifact `WDS/APEX_ENTITY/07_pilot_validation_report.txt` (match rate + any mismatches).
   - *Decision gate*: If match rate < 95%, halt and investigate before proceeding to full enrichment. If ≥ 95%, proceed to Phase 3.
   - *Depends on Step 6*.

### Phase 3 — Enrichment Output Shape + Column Naming

8. **Define output column naming scheme** — Using BOST multi-step alias-prefixing pattern, for each (wafer, alias) pair's matched-slot metadata, emit 5 new columns:
   - `WDS_ENTITY_{ALIAS}_BATCH_IDLE` (e.g., `WDS_ENTITY_E_8M5_HM_ETCH_BATCH_IDLE`)
   - `WDS_ENTITY_{ALIAS}_PRIOR_ALIAS`
   - `WDS_ENTITY_{ALIAS}_PROCESS_ORDER`
   - `WDS_ENTITY_{ALIAS}_SEQUENCE`
   - `WDS_ENTITY_{ALIAS}_UTILIZATION`
   - Also emit two validation/reference columns per alias: `WDS_ENTITY_{ALIAS}_MATCHED_SLOT` (slot index), `WDS_ENTITY_{ALIAS}_WAFER_ENTITY_END_TIME` (timestamp for audit).
   - *Rationale*: 
     - `WDS_ENTITY_` prefix distinguishes from production CSV's native `ENTITY`/`SUBENTITY`.
     - `{ALIAS}` segment ensures no collision across 10 aliases.
     - Follows BOST registry naming convention for multi-step columns (see `BOST_ENRICHMENT_REGISTRY_PLAN.md` section 3.2).
   - *Documentation*: Create `WDS/APEX_ENTITY/03_output_column_naming_convention.md` (rationale + list).
   - *Depends on Step 3* (column schema).

9. **Design merge strategy** — Define how to join WDS output back to `outputs/wafer/8M5CL_8M6CL_EXTENDED.csv`:
   - **Join key**: `LOT7` + `WAFER_ID` + `LAYER` (3-column composite, matches production CSV's existing PK scope).
   - **Cardinality**: Each wafer has up to 10 rows in WDS output (one per applicable alias), each producing 7 new columns (5 subfields + matched slot + end time). Production CSV has one row per wafer. After left-join on the composite key, each wafer row will gain up to 70 new columns (10 aliases × 7 cols/alias), or fewer if not all aliases covered for that wafer (e.g., 8M5CL wafers won't have M6 alias columns).
   - **Handle missing aliases**: If a wafer ran through only 3 out of 5 aliases, the remaining 2 aliases' columns get `NULL`/blank values (preserve row count in production CSV).
   - *Output*: `WDS/APEX_ENTITY/08_merge_strategy.md` (join logic + example schema).
   - *Depends on Steps 6–8*.

### Phase 4 — Full Enrichment Implementation

10. **Build end-to-end enrichment script** — Combine Steps 5–6 into a single, parameterized script `WDS/APEX_ENTITY/09_enrich_production_csv.py` that:
    - Takes input: path to production CSV (default `outputs/wafer/8M5CL_8M6CL_EXTENDED.csv`), optional wafer filter/limit (for staged rollout).
    - Pulls APEX@ENTITY for all specified wafers/aliases, performs slot matching, flattens to output columns (Step 8 naming).
    - Optionally applies a validation filter (e.g., match rate threshold, confidence checks).
    - Outputs enriched CSV to `WDS/APEX_ENTITY/artifacts/enriched_<TIMESTAMP>.csv`.
    - Logs: match-rate summary, any mismatches/anomalies, row counts before/after.
    - *Parallelization hint*: If processing many wafers, batch alias pulls (e.g., pull all aliases for wafers 1–50, then 51–100) to reduce context-switch overhead; keep one-alias-per-call pattern within each wafer batch.
    - *Depends on Steps 5–8*.

11. **Run full enrichment on all production CSV wafers** — Execute Step 10's script with no wafer filter (or staged batches if memory/perf concerns). Produce:
    - `WDS/APEX_ENTITY/artifacts/enriched_all_<TIMESTAMP>.csv` (all rows from production CSV + new columns).
    - `WDS/APEX_ENTITY/artifacts/enrichment_full_report_<TIMESTAMP>.txt` (summary: wafers processed, match rate, any anomalies).
    - *Depends on Step 10*.

12. **Validate output integrity** — Spot-check enriched CSV:
    - Row count matches input (no rows added/dropped during merge).
    - New columns present and populated as expected.
    - Sample 5–10 enriched rows: verify column values are sensible (e.g., `PROCESS_ORDER` is a small int, `UTILIZATION` is 0–1 range, timestamps parse).
    - *Output*: `WDS/APEX_ENTITY/artifacts/enrichment_integrity_check.txt`.
    - *Depends on Step 11*.

---

## Relevant Files

- **Design reference**: `WDS/APEX_ENTITY/APEX_ENTITY_ENRICHMENT_HANDOFF.md` — outlines all 4 open questions (confirm field semantics, candidate-set scope, match-rate thresholds, client setup).
- **Column naming precedent**: `BOST/BOST_ENRICHMENT_REGISTRY_PLAN.md` section 3.2 — multi-step alias-prefixing pattern for dynamic columns.
- **WDS client setup**: `WDS/wds_client_setup.md` (memory notes) — SSL cert bundle, one-alias-per-call pattern, pagination gotchas.
- **WDS schema reference**: `WDS/FULL_FLOW_ALIASES_SCHEMA.md` — comprehensive probe summary (4 dataset families per alias: FDC, LITHOSCANVIEW, ENTITY, modeling noise).
- **Pilot wafers**: `BOST/step1_recent_wafer_registry_pilot.py` — reuse the 10 pilot wafers for validation.
- **Production input**: `outputs/wafer/8M5CL_8M6CL_EXTENDED.csv` — will be enriched with new APEX@ENTITY columns.

---

## Verification

1. **Phase 1 verification** (scoping complete):
   - Step 1: `WDS/APEX_ENTITY/01_check_wds_versions.py` runs without error, outputs current version.
   - Step 2: `WDS/APEX_ENTITY/02b_apex_entity_column_schema.csv` has all 10 aliases with consistent field counts.
   - Step 3: Console review confirms field categories (top-level + 15 subentity slots × 5 subfields).

2. **Phase 2 verification** (pilot validation complete):
   - Step 4: `WDS/APEX_ENTITY/04_pilot_wafers.csv` has 10 wafer rows.
   - Step 5: `WDS/APEX_ENTITY/05a_pilot_raw_apex_entity_<TIMESTAMP>.csv` has data (non-empty, expected column structure).
   - Step 6: `WDS/APEX_ENTITY/05b_pilot_matched_wafers.csv` has match status for all wafers; console logs any mismatches.
   - Step 7: **Decision gate** — match rate ≥ 95%; if lower, investigation artifact summarizes discrepancies.

3. **Phase 3 verification** (output design complete):
   - Step 8: `WDS/APEX_ENTITY/03_output_column_naming_convention.md` lists all 70 output column names (10 aliases × 7 cols).
   - Step 9: `WDS/APEX_ENTITY/08_merge_strategy.md` illustrates join key + cardinality with example rows.

4. **Phase 4 verification** (full enrichment complete):
   - Step 10: `WDS/APEX_ENTITY/09_enrich_production_csv.py` runs without error on pilot subset; output has expected columns.
   - Step 11: `WDS/APEX_ENTITY/artifacts/enriched_all_<TIMESTAMP>.csv` exists, row count matches input.
   - Step 12: `WDS/APEX_ENTITY/artifacts/enrichment_integrity_check.txt` confirms row count, column presence, sample value plausibility.

---

## Decisions

- **Pilot wafer source**: Reuse BOST registry pilot (10 wafers) for consistency across enrichment projects.
- **Output fields**: All 5 subfields (BATCH_IDLE, PRIOR_ALIAS, PROCESS_ORDER, SEQUENCE, UTILIZATION) + 2 audit columns per alias, to maximize analytical value (defect correlation signals + validation).
- **Match-rate threshold**: ≥ 95% for proceeding to full enrichment (accept small discrepancy rate, but investigate root cause first).
- **Version strategy**: Resolve APEX@ENTITY version dynamically from WDS (don't hardcode `V6`); re-probe if versions change mid-project.
- **Staging approach**: Pilot → full enrichment (no intermediate stages), but script supports optional wafer filters for staged rollout if needed.

---

## Further Considerations

1. **Open question from handoff** — Confirm semantics with domain owner (Kahtan Al Jewary / Dave Gaibler):
   - Exact meaning of `PROCESS_ORDER` (wafer position in batch vs. across fleet?), `SEQUENCE` (rank among dispatch candidates?), `UTILIZATION` (% loaded vs. wall-clock utilization?).
   - Whether `PRIOR_ALIAS` refers to immediately-prior operation in *same chamber* (contamination signal) or wafer's own prior operation.
   - **Recommendation**: Add these as questions to an async ping to Kahtan; continue implementation in parallel assuming the "most likely" interpretations (based on field names), note assumptions in script docstrings, and validate semantics post-enrichment if possible.

2. **Candidate-set scope** — Handoff asks whether the full `SUBENTITY_0..14` candidate set (not just matched slot) has independent analytical value worth capturing (e.g., fleet loading context), or whether only the matched/used slot is worth carrying into production CSVs.
   - **Recommendation**: Defer to Phase 5. For Phase 4, focus only on the matched/used chamber (narrower scope, MVP). If future analysis finds fleet-loading context (e.g., "was the chamber undersaturated at dispatch time?") valuable, revisit to add candidate-set columns in a follow-up pass.

3. **Match rate investigation plan** — If Step 7 reveals mismatches:
   - First check: are mismatches from a specific alias or wafer pattern (e.g., all M6 wafers, or a specific chamber)?
   - If systematic (e.g., all M6 off by 1 slot), suggest alias-scoping or chamber-naming issue in WDS or BOST query.
   - If sporadic, may indicate real pipeline discrepancy (worth escalating to Kahtan); document + proceed cautiously.

---

**Status**: Ready for implementation. Start with Phase 1, Step 1.
