# APEX@ENTITY Output Column Naming Convention

**Phase 3, Step 8 — Output Shape Definition**

Generated: 2026-09-10  
Reference design: `BOST/BOST_ENRICHMENT_REGISTRY_PLAN.md` (section 3.2 — multi-step alias-prefixing pattern)

---

## Overview

This document specifies the column naming scheme for enriching the production CSV (`outputs/wafer/8M5CL_8M6CL_EXTENDED.csv`) with APEX@ENTITY data.

**Key principle**: Avoid column-name collisions across the 10 FULL_FLOW_ALIASES by prefixing each set of alias-specific columns with `WDS_ENTITY_{ALIAS}_`.

---

## Column Naming Scheme

For each **FULL_FLOW_ALIAS** (10 total), produce **7 output columns**:

### Core Subfields (5 columns per alias)

These are extracted from the matched SUBENTITY slot's subfields:

| Column Name | Source | Description |
|---|---|---|
| `WDS_ENTITY_{ALIAS}_BATCH_IDLE` | `SUBENTITY_N@BATCH_IDLE` | Whether the matched chamber was batch-idle (no work queued) around wafer's run |
| `WDS_ENTITY_{ALIAS}_PRIOR_ALIAS` | `SUBENTITY_N@PRIOR_ALIAS` | Alias of the previous operation run in that chamber before this wafer |
| `WDS_ENTITY_{ALIAS}_PROCESS_ORDER` | `SUBENTITY_N@PROCESS_ORDER` | Wafer's position within its chamber run/batch |
| `WDS_ENTITY_{ALIAS}_SEQUENCE` | `SUBENTITY_N@SEQUENCE` | Chamber's rank/order among dispatch candidates |
| `WDS_ENTITY_{ALIAS}_UTILIZATION` | `SUBENTITY_N@UTILIZATION` | Chamber utilization metric around the time of wafer run |

### Audit Columns (2 columns per alias)

These enable validation and traceability:

| Column Name | Source | Description |
|---|---|---|
| `WDS_ENTITY_{ALIAS}_MATCHED_SLOT` | Matching algorithm | Slot index N (0-14) of the matched SUBENTITY_N |
| `WDS_ENTITY_{ALIAS}_WAFER_ENTITY_END_TIME` | Top-level field | Timestamp the wafer completed at this entity |

---

## Example Column Names

For alias `E_8M5_HM_ETCH`:

```
WDS_ENTITY_E_8M5_HM_ETCH_BATCH_IDLE
WDS_ENTITY_E_8M5_HM_ETCH_PRIOR_ALIAS
WDS_ENTITY_E_8M5_HM_ETCH_PROCESS_ORDER
WDS_ENTITY_E_8M5_HM_ETCH_SEQUENCE
WDS_ENTITY_E_8M5_HM_ETCH_UTILIZATION
WDS_ENTITY_E_8M5_HM_ETCH_MATCHED_SLOT
WDS_ENTITY_E_8M5_HM_ETCH_WAFER_ENTITY_END_TIME
```

---

## Full Column List (All 10 Aliases)

### M5 Layer (5 aliases × 7 columns = 35 columns)

**Alias: L_8M5_SIARC_DEP**
- `WDS_ENTITY_L_8M5_SIARC_DEP_BATCH_IDLE`
- `WDS_ENTITY_L_8M5_SIARC_DEP_PRIOR_ALIAS`
- `WDS_ENTITY_L_8M5_SIARC_DEP_PROCESS_ORDER`
- `WDS_ENTITY_L_8M5_SIARC_DEP_SEQUENCE`
- `WDS_ENTITY_L_8M5_SIARC_DEP_UTILIZATION`
- `WDS_ENTITY_L_8M5_SIARC_DEP_MATCHED_SLOT`
- `WDS_ENTITY_L_8M5_SIARC_DEP_WAFER_ENTITY_END_TIME`

**Alias: L_8M5_CHM_DEP**
- `WDS_ENTITY_L_8M5_CHM_DEP_BATCH_IDLE`
- `WDS_ENTITY_L_8M5_CHM_DEP_PRIOR_ALIAS`
- `WDS_ENTITY_L_8M5_CHM_DEP_PROCESS_ORDER`
- `WDS_ENTITY_L_8M5_CHM_DEP_SEQUENCE`
- `WDS_ENTITY_L_8M5_CHM_DEP_UTILIZATION`
- `WDS_ENTITY_L_8M5_CHM_DEP_MATCHED_SLOT`
- `WDS_ENTITY_L_8M5_CHM_DEP_WAFER_ENTITY_END_TIME`

**Alias: L_8M5_SED**
- `WDS_ENTITY_L_8M5_SED_BATCH_IDLE`
- `WDS_ENTITY_L_8M5_SED_PRIOR_ALIAS`
- `WDS_ENTITY_L_8M5_SED_PROCESS_ORDER`
- `WDS_ENTITY_L_8M5_SED_SEQUENCE`
- `WDS_ENTITY_L_8M5_SED_UTILIZATION`
- `WDS_ENTITY_L_8M5_SED_MATCHED_SLOT`
- `WDS_ENTITY_L_8M5_SED_WAFER_ENTITY_END_TIME`

**Alias: E_8M5_HM_ETCH**
- `WDS_ENTITY_E_8M5_HM_ETCH_BATCH_IDLE`
- `WDS_ENTITY_E_8M5_HM_ETCH_PRIOR_ALIAS`
- `WDS_ENTITY_E_8M5_HM_ETCH_PROCESS_ORDER`
- `WDS_ENTITY_E_8M5_HM_ETCH_SEQUENCE`
- `WDS_ENTITY_E_8M5_HM_ETCH_UTILIZATION`
- `WDS_ENTITY_E_8M5_HM_ETCH_MATCHED_SLOT`
- `WDS_ENTITY_E_8M5_HM_ETCH_WAFER_ENTITY_END_TIME`

**Alias: W_8M5_HM_CLN**
- `WDS_ENTITY_W_8M5_HM_CLN_BATCH_IDLE`
- `WDS_ENTITY_W_8M5_HM_CLN_PRIOR_ALIAS`
- `WDS_ENTITY_W_8M5_HM_CLN_PROCESS_ORDER`
- `WDS_ENTITY_W_8M5_HM_CLN_SEQUENCE`
- `WDS_ENTITY_W_8M5_HM_CLN_UTILIZATION`
- `WDS_ENTITY_W_8M5_HM_CLN_MATCHED_SLOT`
- `WDS_ENTITY_W_8M5_HM_CLN_WAFER_ENTITY_END_TIME`

### M6 Layer (5 aliases × 7 columns = 35 columns)

**Alias: L_8M6_SIARC_DEP**
- `WDS_ENTITY_L_8M6_SIARC_DEP_BATCH_IDLE`
- `WDS_ENTITY_L_8M6_SIARC_DEP_PRIOR_ALIAS`
- `WDS_ENTITY_L_8M6_SIARC_DEP_PROCESS_ORDER`
- `WDS_ENTITY_L_8M6_SIARC_DEP_SEQUENCE`
- `WDS_ENTITY_L_8M6_SIARC_DEP_UTILIZATION`
- `WDS_ENTITY_L_8M6_SIARC_DEP_MATCHED_SLOT`
- `WDS_ENTITY_L_8M6_SIARC_DEP_WAFER_ENTITY_END_TIME`

**Alias: L_8M6_CHM_DEP**
- `WDS_ENTITY_L_8M6_CHM_DEP_BATCH_IDLE`
- `WDS_ENTITY_L_8M6_CHM_DEP_PRIOR_ALIAS`
- `WDS_ENTITY_L_8M6_CHM_DEP_PROCESS_ORDER`
- `WDS_ENTITY_L_8M6_CHM_DEP_SEQUENCE`
- `WDS_ENTITY_L_8M6_CHM_DEP_UTILIZATION`
- `WDS_ENTITY_L_8M6_CHM_DEP_MATCHED_SLOT`
- `WDS_ENTITY_L_8M6_CHM_DEP_WAFER_ENTITY_END_TIME`

**Alias: L_8M6_SED**
- `WDS_ENTITY_L_8M6_SED_BATCH_IDLE`
- `WDS_ENTITY_L_8M6_SED_PRIOR_ALIAS`
- `WDS_ENTITY_L_8M6_SED_PROCESS_ORDER`
- `WDS_ENTITY_L_8M6_SED_SEQUENCE`
- `WDS_ENTITY_L_8M6_SED_UTILIZATION`
- `WDS_ENTITY_L_8M6_SED_MATCHED_SLOT`
- `WDS_ENTITY_L_8M6_SED_WAFER_ENTITY_END_TIME`

**Alias: E_8M6_HM_ETCH**
- `WDS_ENTITY_E_8M6_HM_ETCH_BATCH_IDLE`
- `WDS_ENTITY_E_8M6_HM_ETCH_PRIOR_ALIAS`
- `WDS_ENTITY_E_8M6_HM_ETCH_PROCESS_ORDER`
- `WDS_ENTITY_E_8M6_HM_ETCH_SEQUENCE`
- `WDS_ENTITY_E_8M6_HM_ETCH_UTILIZATION`
- `WDS_ENTITY_E_8M6_HM_ETCH_MATCHED_SLOT`
- `WDS_ENTITY_E_8M6_HM_ETCH_WAFER_ENTITY_END_TIME`

**Alias: W_8M6_HM_CLN**
- `WDS_ENTITY_W_8M6_HM_CLN_BATCH_IDLE`
- `WDS_ENTITY_W_8M6_HM_CLN_PRIOR_ALIAS`
- `WDS_ENTITY_W_8M6_HM_CLN_PROCESS_ORDER`
- `WDS_ENTITY_W_8M6_HM_CLN_SEQUENCE`
- `WDS_ENTITY_W_8M6_HM_CLN_UTILIZATION`
- `WDS_ENTITY_W_8M6_HM_CLN_MATCHED_SLOT`
- `WDS_ENTITY_W_8M6_HM_CLN_WAFER_ENTITY_END_TIME`

---

## Total Column Count

- **70 columns total** (10 aliases × 7 columns/alias)
- **35 for M5 layer** (only populated for 8M5CL wafers)
- **35 for M6 layer** (only populated for 8M6CL wafers)

---

## Rationale

### Prefix: `WDS_ENTITY_`

Distinguishes APEX@ENTITY enrichment from:
- Production CSV's native `ENTITY` and `SUBENTITY` columns
- Other WDS datasets (e.g., `WDS_FDC_*`, `WDS_LITHOSCANVIEW_*` — reserved for future enrichments)

### Infix: `{ALIAS}`

Ensures no collision across 10 aliases. For example:
- `WDS_ENTITY_E_8M5_HM_ETCH_BATCH_IDLE` vs.
- `WDS_ENTITY_W_8M5_HM_CLN_BATCH_IDLE`

are clearly distinct columns for different process steps on the same layer.

### Suffix: Field name (e.g., `BATCH_IDLE`, `MATCHED_SLOT`)

Maps directly to WDS `SUBENTITY_N@SUBFIELD` naming (minus the slot index), maintaining traceability to source data.

---

## Handling Missing Aliases

For a wafer that ran through only 3 out of 5 M5 aliases (e.g., missing `L_8M5_CHM_DEP` and `W_8M5_HM_CLN`):
- Those 2 aliases' 7 columns each (14 total) will be `NULL`/blank in the enriched CSV.
- Row count is preserved (no rows added/dropped during merge).
- This allows consistent schema across all wafers, even if not all aliases are represented for every wafer.

---

## Validation

Columns follow the naming pattern:
```
WDS_ENTITY_{FULL_FLOW_ALIASES_MEMBER}_{SUBFIELD|AUDIT_FIELD}
```

All column names are:
- **Predictable** (schema is fixed, not data-dependent)
- **Non-conflicting** (alias + field uniquely identify each column)
- **Traceable** (alias prefix connects back to WDS source)
- **Audit-friendly** (`MATCHED_SLOT`, `WAFER_ENTITY_END_TIME` enable validation)

---

**Status**: Approved for Phase 4 implementation.  
**Next step**: Phase 3, Step 9 (define merge strategy).
