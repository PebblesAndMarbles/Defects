# APEX@ENTITY Enrichment Implementation

**Location**: `WDS/APEX_ENTITY/`  
**Target**: Enrich `outputs/wafer/8M5CL_8M6CL_EXTENDED.csv` with APEX@ENTITY chamber metadata  
**Status**: Ready for execution (2026-09-10)

---

## Quick Start

### Phase 1 — Scoping (Scripts 01-03)

Discover and validate APEX@ENTITY dataset structure:

```bash
# 1. Check WDS version
python 01_check_wds_versions.py --env rf3stg

# 2. Probe all 10 FULL_FLOW_ALIASES columns
python 02_probe_all_aliases.py --env rf3stg

# 3. Parse and validate schema consistency
python 03_parse_and_categorize_columns.py
```

**Expected outputs**:
- `artifacts/01_wds_version_check.txt` — resolved version
- `artifacts/02a_raw_columns_*.txt` — raw column probes per alias (10 files)
- `artifacts/02b_apex_entity_column_schema.csv` — summary schema
- `artifacts/03_apex_entity_schema.md` — human-readable documentation
- `artifacts/03_validation_report.txt` — consistency check

### Phase 2 — Pilot Validation (Scripts 04-07)

Validate APEX@ENTITY against production CSV on 10 pilot wafers:

```bash
# 4. Extract 10 pilot wafers from BOST registry
python 04_extract_pilot_wafers.py

# 5. Pull APEX@ENTITY for pilot wafers and match SUBENTITY slots
python 05_pull_and_match_pilot.py --env rf3stg

# 7. Validate match rate (decision gate: ≥95% to proceed)
python 07_validate_pilot_matches.py --threshold 95.0
```

**Expected outputs**:
- `04_pilot_wafers.csv` — manifest of 10 pilot wafers
- `artifacts/05a_pilot_raw_apex_entity_<TIMESTAMP>.csv` — raw WDS pulls (wide)
- `artifacts/05b_pilot_matched_wafers.csv` — matched slots + subfields
- `artifacts/07_pilot_validation_report.txt` — match rate + mismatches

**Decision gate** (Step 7):
- ✓ If match rate ≥ 95% → proceed to Phase 3
- ✗ If match rate < 95% → investigate mismatches before proceeding

### Phase 3 — Output Design (Documents 03, 08)

Design the enrichment output schema (no scripts; documents only):

- **`03_output_column_naming_convention.md`** — Defines 70 output columns (10 aliases × 7 cols/alias)
  - 5 core subfields per alias: `BATCH_IDLE`, `PRIOR_ALIAS`, `PROCESS_ORDER`, `SEQUENCE`, `UTILIZATION`
  - 2 audit columns per alias: `MATCHED_SLOT`, `WAFER_ENTITY_END_TIME`
  - Naming: `WDS_ENTITY_{ALIAS}_{SUBFIELD}`

- **`08_merge_strategy.md`** — Defines join key and cardinality
  - Join key: `LOT7` + `WAFER_ID` + `LAYER` (3-column composite)
  - Cardinality: Left-join production CSV with flattened WDS output
  - Result: Production CSV + 70 new WDS columns

### Phase 4 — Full Enrichment (Scripts 09-10)

Run full enrichment on all production CSV wafers:

```bash
# 9. Build and run end-to-end enrichment
python 09_enrich_production_csv.py --env rf3stg
    # Optional: --limit N (test with first N wafers)
    # Optional: --force (skip validation)

# 10. Validate output integrity
python 10_validate_output_integrity.py
```

**Expected outputs**:
- `artifacts/enriched_all_<TIMESTAMP>.csv` — enriched production CSV
- `artifacts/enrichment_full_report_<TIMESTAMP>.txt` — summary statistics
- `artifacts/enrichment_integrity_check.txt` — validation report

---

## File Structure

```
WDS/APEX_ENTITY/
├── 01_check_wds_versions.py                      (Phase 1, Step 1)
├── 02_probe_all_aliases.py                       (Phase 1, Step 2)
├── 03_parse_and_categorize_columns.py            (Phase 1, Step 3)
├── 04_extract_pilot_wafers.py                    (Phase 2, Step 4)
├── 05_pull_and_match_pilot.py                    (Phase 2, Steps 5-6)
├── 07_validate_pilot_matches.py                  (Phase 2, Step 7)
├── 09_enrich_production_csv.py                   (Phase 4, Steps 10-11)
├── 10_validate_output_integrity.py               (Phase 4, Step 12)
├── 03_output_column_naming_convention.md         (Phase 3, Step 8)
├── 08_merge_strategy.md                          (Phase 3, Step 9)
├── APEX_ENTITY_ENRICHMENT_HANDOFF.md             (Design reference)
├── artifacts/                                    (Generated outputs)
│   ├── (raw column probes, schemas, reports)
│   ├── (pilot validation results)
│   ├── enriched_all_<TIMESTAMP>.csv              (Final enriched CSV)
│   └── (integrity checks)
└── README.md (this file)
```

---

## Key Design Decisions

### Naming Convention
- Prefix: `WDS_ENTITY_` (distinguishes from native ENTITY/SUBENTITY columns)
- Infix: `{ALIAS}` (10 FULL_FLOW_ALIASES, no collision across aliases)
- Suffix: Subfield name (`BATCH_IDLE`, `MATCHED_SLOT`, etc.)

### Join Strategy
- Composite key: `(LOT7, WAFER_ID, LAYER)` — uniquely identifies a wafer
- Pattern: Left-join (preserve all production CSV rows, fill missing with NULL)
- Cardinality: Each wafer gains up to 70 new columns (10 aliases × 7 cols)

### Validation
- **Match rate threshold**: ≥ 95% (accept small discrepancy rate, investigate root causes)
- **Pilot scope**: 10 wafers from BOST registry pilot (consistency with other enrichments)
- **Output validation**: Row count, column presence, sample value plausibility

---

## Dependencies

### Environment
- Python 3.11+ (from `c:/users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe`)
- WDS client installed (from `dev/wds-clients/clients/python`)
- CA bundle at `WDS/wds_ca_bundle.pem` (generated per `wds_client_setup.md`)

### Packages
- `pandas` (for DataFrames, CSV I/O)
- `wds_client` (for WDS queries)
- `pyidealdata` (preinstalled, for IdealAPEX compatibility)

### Data
- Production CSV: `outputs/wafer/8M5CL_8M6CL_EXTENDED.csv` (input)
- BOST pilot wafers: `BOST/step1_recent_wafer_registry_pilot.py` (for 10-wafer pilot)

---

## Command Reference

### Phase 1: Scoping
```bash
cd WDS/APEX_ENTITY
python 01_check_wds_versions.py --env rf3stg
python 02_probe_all_aliases.py --env rf3stg
python 03_parse_and_categorize_columns.py
```

### Phase 2: Pilot Validation
```bash
python 04_extract_pilot_wafers.py
python 05_pull_and_match_pilot.py --env rf3stg
python 07_validate_pilot_matches.py --threshold 95.0
```

### Phase 4: Full Enrichment
```bash
# Test run with first 100 wafers
python 09_enrich_production_csv.py --env rf3stg --limit 100

# Full production run
python 09_enrich_production_csv.py --env rf3stg

# Validate output
python 10_validate_output_integrity.py
```

### Optional Flags
- `--env rf3prod` — Use production WDS environment (instead of rf3stg)
- `--no-cert-verify` — Disable SSL cert verification (not recommended)
- `--limit N` — Limit to first N wafers (for testing)
- `--force` — Skip validation, proceed even if match rate < 95%
- `--threshold T` — Custom match-rate threshold (default: 95.0)

---

## Troubleshooting

### WDS Connection Issues
- **SSL Cert Error**: Ensure `wds_ca_bundle.pem` exists and is current
  - Regenerate: `python -c "...cert bundle generation code..."`  (see `wds_client_setup.md`)
- **Kerberos Auth**: Ensure machine is domain-joined, ambient Windows Kerberos works
  - Test: `wds-client diagnose --env rf3stg` (from command line)

### Match Rate Too Low (< 95%)
- **Common cause**: SUBENTITY format mismatch (e.g., missing slot index in WDS data)
- **Investigation**: Review `artifacts/07_pilot_validation_report.txt` for mismatches
- **Fix**: Confirm SUBENTITY column name/format in both production CSV and WDS
- **Escalation**: Contact Kahtan Al Jewary (WDS owner) if systematic discrepancies

### Memory Issues on Large Datasets
- **Solution**: Run Phase 4 with `--limit N` in batches (e.g., first 500 wafers, then 501-1000)
- **Note**: Each alias requires a separate WDS query (cannot batch aliases), so performance is network-bound

### Column Naming Issues
- **Duplicate columns** (e.g., `_x`, `_y`): Indicates join collision
  - Cause: Column names already present in production CSV
  - Fix: Review production CSV schema, adjust naming convention if needed

---

## Next Steps After Enrichment

Once enrichment completes successfully:

1. **Validate** using `10_validate_output_integrity.py` (Phase 4, Step 12)
2. **Archive** enriched CSV to a permanent location (e.g., `outputs/wafer/archive/`)
3. **Integrate** into downstream analyses (e.g., defect correlation models)
4. **Monitor** match rate and column distributions over time (if refreshed periodically)

---

## References

- **Design document**: `APEX_ENTITY_ENRICHMENT_HANDOFF.md` (outlines scope and open questions)
- **Column naming precedent**: `BOST/BOST_ENRICHMENT_REGISTRY_PLAN.md` (section 3.2)
- **WDS client setup**: `/memories/repo/wds_client_setup.md` (SSL, auth, perf notes)
- **FULL_FLOW_ALIASES schema**: `WDS/FULL_FLOW_ALIASES_SCHEMA.md` (4 dataset families per alias)

---

**Status**: Ready for execution.  
**Last updated**: 2026-09-10  
**Maintained by**: BE enrichment team
