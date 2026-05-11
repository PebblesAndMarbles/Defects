# JSL Troubleshooting Playbook

## 1) Fast triage sequence

1. Confirm which script is failing:
- [AMEct 1278 Inline Defects Fleet Dispo.jsl](../../AMEct%201278%20Inline%20Defects%20Fleet%20Dispo.jsl)
- [AMEct 1278 Inline Defects Chamber Dispo.jsl](../../AMEct%201278%20Inline%20Defects%20Chamber%20Dispo.jsl)

2. Confirm active source mode (60-day vs integrated) and input file existence.

3. Confirm both tables open successfully:
- summary table (NCDD)
- coordinates table (DEFECT_COORDINATES)

4. Check required key columns exist before downstream logic:
- WAFER_ID
- LAYER
- STATUS
- CLASS (coords)
- WAFER_X_MM and WAFER_Y_MM (coords)

5. Confirm coordinate subset counts:
- All Coords
- SMP Coords
- BEEP Coords

6. Confirm selection handlers attach and fire.

## 2) Frequent failure patterns and likely causes

### A) Wafer map shows no points

Likely causes:
- _INCLUDE filter excludes everything
- selected status mode is too restrictive
- source mismatch (summary/coords out of sync)
- CHAMBER/FLEET hide options remove rows (chamber script)

Checks:
- print counts after _INCLUDE creation
- verify CLASS values present for SMP/BEEP subsets
- verify row counts in subset output tables

### B) Chart selection does not propagate to coordinates

Likely causes:
- handler attached to wrong table
- key mapping mismatch
- event not triggered from chart source table

Fleet-specific note:
- handlers must be attached to Summary SUM/SMP/BEEP tables (not original dt)

Chamber-specific note:
- handler attached to main dt using ORIGINAL_ROW_NUMBER

### C) Grouping column missing in fleet workflow

Likely causes:
- selected legend column exists in summary table but not coords table
- backfill logic failed due missing ORIGINAL_ROW_NUMBER or source column

Checks:
- verify legendcol1 exists in summary table
- verify coords gets new legendcol1 column when missing

### D) Single-layer wafer map formatting crashes

Likely cause:
- Report returns single object instead of list

Mitigation:
- normalize to list before For Each in Format_Wafermap

### E) Unexpected high baseline/highflier suppression

Likely causes:
- status mode mis-selected
- STATUS_BEEP/STATUS_SMP fallback behavior differs from expectation

Checks:
- print selected status mode
- verify STATUS, STATUS_BEEP, STATUS_SMP availability

### F) Row-height misalignment or chart elongation

Likely causes:
- trend row heights not captured after legend layout
- metric/layer key mismatch between trend and target panels
- data frame height being resized instead of using outer padding

Checks:
- verify trend row height map is populated for SUM/SMP/BEEP and each layer
- verify row keys match expected format metric|layer (for example SUM NCDD|8M5CL)
- verify variability/wafermap alignment path adds padding without stretching frame geometry

Mitigation:
- keep trend column as row-height source-of-truth
- align target columns using outer padding to preserve chart/wafermap shape

### G) Wafermap markers or colors not reflecting dialog options

Likely causes:
- report-level row legend overrides table-level marker/color states
- black-marker checkbox value not propagated from dialog result list

Checks:
- verify black-marker option is included in dialog return payload
- verify table-level marker assignment for BEEP and SMALL_PARTICLE runs before plotting
- verify wafermap formatter does not reapply overriding marker/color legends

## 3) Source and path issues

Verify these paths resolve before running in JMP:
- [outputs/wafer/8M5CL_8M6CL_EXTENDED.csv](../../outputs/wafer/8M5CL_8M6CL_EXTENDED.csv)
- [outputs/defects/DEFECT_COORDINATES_EXTENDED.csv](../../outputs/defects/DEFECT_COORDINATES_EXTENDED.csv)

Image folder shortcut target:
- [images/defects](../../images/defects)

If source files are stale or missing, run pipeline update first:
- [BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py](../../BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py)

## 4) Debug prints worth keeping

Useful temporary prints:
- selected source and filter options
- total rows in dt and dt_coords
- _INCLUDE=1 row count
- subset row counts for all/smp/beep
- selection sync key counts

## 5) Safe rollback strategy

1. Keep an untouched copy of script before edits.
2. Make one logical change at a time.
3. Re-run with a known stable source option.
4. Validate subset counts before validating UI formatting.
5. Revert only the latest logical chunk if behavior regresses.
