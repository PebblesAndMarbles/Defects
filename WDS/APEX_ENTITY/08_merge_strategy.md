# APEX@ENTITY Merge Strategy

**Phase 3, Step 9 — Join Design**

Generated: 2026-09-10  
Reference: `03_output_column_naming_convention.md`

---

## Overview

This document specifies how to merge WDS APEX@ENTITY enrichment back into the production CSV (`outputs/wafer/8M5CL_8M6CL_EXTENDED.csv`).

---

## Join Key

**Composite primary key (3 columns)**:

| Column | Source | Cardinality | Notes |
|---|---|---|---|
| `LOT7` | Both CSVs | Partial key | Lot identifier (7-digit or similar) |
| `WAFER_ID` | Both CSVs | Partial key | Wafer slot identifier (e.g., GA7ZH534JKG7) |
| `LAYER` | Both CSVs | Partial key | Process layer (8M5CL or 8M6CL) |

**Composite cardinality**: `(LOT7, WAFER_ID, LAYER)` uniquely identifies a wafer in the production CSV.

**Rationale**:
- Production CSV has one row per wafer (one row per unique wafer-operation pair, actually, but LOT7+WAFER_ID+LAYER identifies the wafer).
- WDS APEX@ENTITY output will have **up to 10 rows per wafer** (one per alias), all with same LOT7+WAFER_ID+LAYER.
- After flattening WDS output (Step 5-6 produces one row per wafer with all 10 aliases' data), the join becomes a standard left-join on this 3-column key.

---

## Data Flow

### Before Enrichment

**Production CSV** (`outputs/wafer/8M5CL_8M6CL_EXTENDED.csv`):
```
YYMM | PERIOD_END | ... | LOT7 | WAFER_ID | LAYER | ... | ENTITY | SUBENTITY | ...
2505 | 2025-05-18 | ... | D412E29 | GA7ZH534JKG7 | 8M5CL | ... | AME409 | AME409_PM3 | ...
2505 | 2025-06-01 | ... | D412E29 | GA7ZH534JKG7 | 8M6CL | ... | AME427 | AME427_PM1 | ...
...
```

**WDS APEX@ENTITY (after flattening from Step 5-6)**:
```
WAFER_ID | LOT7 | LAYER | ALIAS | MATCHED_SLOT | WDS_ENTITY_E_8M5_HM_ETCH_BATCH_IDLE | ... (70 total APEX@ENTITY columns)
GA7ZH534JKG7 | D412E29 | 8M5CL | E_8M5_HM_ETCH | 2 | TRUE | ...
GA7ZH534JKG7 | D412E29 | 8M5CL | L_8M5_SIARC_DEP | 0 | FALSE | ...
...
GA7ZH534JKG7 | D412E29 | 8M6CL | E_8M6_HM_ETCH | 1 | NULL | ...
...
```

### After Enrichment

**Enriched Production CSV**:
```
YYMM | PERIOD_END | ... | LOT7 | WAFER_ID | LAYER | ... | ENTITY | SUBENTITY | ...
   | (existing columns from production CSV) | WDS_ENTITY_L_8M5_SIARC_DEP_BATCH_IDLE | ... | WDS_ENTITY_W_8M6_HM_CLN_WAFER_ENTITY_END_TIME
2505 | 2025-05-18 | ... | D412E29 | GA7ZH534JKG7 | 8M5CL | ... | AME409 | AME409_PM3 | ...
   | | FALSE | | TRUE | ...
2505 | 2025-06-01 | ... | D412E29 | GA7ZH534JKG7 | 8M6CL | ... | AME427 | AME427_PM1 | ...
   | | NULL | | NULL | ...
...
```

---

## Join Pattern

### SQL Pseudocode

```sql
SELECT
    prod.*,
    wds.WDS_ENTITY_L_8M5_SIARC_DEP_BATCH_IDLE,
    wds.WDS_ENTITY_L_8M5_SIARC_DEP_PRIOR_ALIAS,
    ... (70 APEX@ENTITY columns) ...
    wds.WDS_ENTITY_W_8M6_HM_CLN_WAFER_ENTITY_END_TIME
FROM production_csv AS prod
LEFT JOIN wds_enrichment AS wds
    ON prod.LOT7 = wds.LOT7
   AND prod.WAFER_ID = wds.WAFER_ID
   AND prod.LAYER = wds.LAYER
```

### Python (pandas) Pseudocode

```python
import pandas as pd

prod = pd.read_csv("outputs/wafer/8M5CL_8M6CL_EXTENDED.csv")
wds = pd.read_csv("WDS/APEX_ENTITY/artifacts/enriched_all_<TIMESTAMP>.csv")

# Merge on composite key
enriched = pd.merge(
    prod,
    wds,
    on=["LOT7", "WAFER_ID", "LAYER"],
    how="left"  # LEFT JOIN: preserve all production CSV rows
)

enriched.to_csv("outputs/wafer/8M5CL_8M6CL_EXTENDED_APEX_ENTITY_ENRICHED.csv", index=False)
```

---

## Cardinality Analysis

### Production CSV Rows
- **Input**: `N_prod` rows (one per wafer, or more if tracking multiple operations per wafer)
- **Output**: Same `N_prod` rows (left join preserves all input rows)

### WDS Enrichment Rows
- **Per wafer**: Up to 10 rows (one per applicable alias), flattened to 1 row with 70 WDS columns
- **Total**: ~`N_wafers` rows (assuming one row per unique wafer after flattening)
- **Applicable aliases per wafer**: 5 (8M5CL wafers have only M5 aliases, 8M6CL have only M6; flattening combines all into one row)

### Join Result
- **Rows**: `N_prod` (same as production CSV — left join)
- **Columns**: `N_prod_cols + 70` (all production columns + 70 WDS columns)

### Handling Missing Aliases
If a wafer ran through only 3 of 5 M5 aliases:
- The 2 missing aliases' 14 columns (`7 cols × 2 aliases`) will be `NULL` in the enriched CSV
- This is acceptable; the schema is consistent across all wafers

---

## Indexing & Performance

### Production CSV Join Preparation
1. Ensure `LOT7`, `WAFER_ID`, `LAYER` are present (they are, per current schema)
2. Create a composite index on production CSV before merge (if using database/SQL):
   ```sql
   CREATE INDEX prod_join_key ON production_csv(LOT7, WAFER_ID, LAYER);
   ```

### WDS Enrichment Join Preparation
1. The enrichment script (`09_enrich_production_csv.py` from Phase 4, Step 10) will produce WDS output with same 3-column key
2. Sort/index WDS output on same key for merge performance

### Merge Strategy
- **Preferred**: Use pandas `.merge()` (fast for CSVs up to ~1GB)
- **Alternative**: SQL if data volume requires it (less likely for this scope)

---

## Example Join Illustration

### Production CSV (simplified)

| LOT7 | WAFER_ID | LAYER | ENTITY | SUBENTITY |
|---|---|---|---|---|
| D412E29 | GA7ZH534JKG7 | 8M5CL | AME409 | AME409_PM3 |
| D412E29 | GA7ZH535JKD6 | 8M5CL | AME409 | AME409_PM4 |
| D412E29 | GA7ZH534JKG7 | 8M6CL | AME427 | AME427_PM1 |

### WDS Enrichment (simplified, flattened per wafer)

| LOT7 | WAFER_ID | LAYER | WDS_ENTITY_E_8M5_HM_ETCH_BATCH_IDLE | WDS_ENTITY_L_8M5_SIARC_DEP_BATCH_IDLE | ... |
|---|---|---|---|---|---|
| D412E29 | GA7ZH534JKG7 | 8M5CL | TRUE | FALSE | ... |
| D412E29 | GA7ZH535JKD6 | 8M5CL | FALSE | TRUE | ... |
| D412E29 | GA7ZH534JKG7 | 8M6CL | NULL | NULL | ... |

### Enriched CSV (after LEFT JOIN)

| LOT7 | WAFER_ID | LAYER | ENTITY | SUBENTITY | WDS_ENTITY_E_8M5_HM_ETCH_BATCH_IDLE | WDS_ENTITY_L_8M5_SIARC_DEP_BATCH_IDLE | ... |
|---|---|---|---|---|---|---|---|
| D412E29 | GA7ZH534JKG7 | 8M5CL | AME409 | AME409_PM3 | TRUE | FALSE | ... |
| D412E29 | GA7ZH535JKD6 | 8M5CL | AME409 | AME409_PM4 | FALSE | TRUE | ... |
| D412E29 | GA7ZH534JKG7 | 8M6CL | AME427 | AME427_PM1 | NULL | NULL | ... |

---

## Data Validation Post-Merge

### Row Count
- Verify `len(enriched) == len(prod)` (row count unchanged by left join)

### NULL Distribution
- M5 wafers (layer=8M5CL): M5 alias columns should have data, M6 alias columns should be NULL
- M6 wafers (layer=8M6CL): M6 alias columns should have data, M5 alias columns should be NULL
- Sample 5-10 wafers to spot-check this pattern

### Column Presence
- Verify all 70 APEX@ENTITY columns are present
- Verify no unexpected duplicates (e.g., `..._x`, `..._y` from duplicate column names)

---

## Output Location

**Enriched CSV**: `outputs/wafer/8M5CL_8M6CL_EXTENDED_APEX_ENTITY_ENRICHED_<TIMESTAMP>.csv`

(Keep the original production CSV intact; enriched version is a separate artifact for now. If validated, can replace original in production workflow.)

---

**Status**: Approved for Phase 4 implementation.  
**Next step**: Phase 4, Step 10 (build end-to-end enrichment script).
