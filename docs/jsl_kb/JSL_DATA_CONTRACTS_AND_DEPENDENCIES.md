# JSL Data Contracts and Dependencies

## 1) Core table contracts

### Summary (NCDD) table contract

Typical required columns:
- LOT
- LOT7
- WAFER_ID
- LAYER
- SUBENTITY
- INSPECT_TIME
- STATUS
- SUM_NCDD
- SMP_NCDD
- BEEP_NCDD

Commonly used additional columns:
- PRODUCT
- PILOT_STATUS
- RECIPE
- SRCIP
- CCMR2
- ICCR2
- STATUS_BEEP
- STATUS_SMP

### Coordinates table contract

Typical required columns:
- LOT
- WAFER_ID
- LAYER
- CLASS
- STATUS
- WAFER_X_MM
- WAFER_Y_MM

Often present and used in integrated flow:
- INSPECT_TIME and/or INSPECTION_TIME
- STATUS_BEEP
- STATUS_SMP
- SUBENTITY

## 2) Key relationship assumptions

Shared matching assumptions in scripts:
- summary row and coordinate row can be associated by WAFER_ID + LAYER
- chamber script also derives ORIGINAL_ROW_NUMBER using that mapping

Risk:
- if WAFER_ID + LAYER is not unique across rows, row linkage may be lossy or last-write-wins

## 3) External file dependencies

Primary integrated inputs:
- [outputs/wafer/8M5CL_8M6CL_EXTENDED.csv](../../outputs/wafer/8M5CL_8M6CL_EXTENDED.csv)
- [outputs/defects/DEFECT_COORDINATES_EXTENDED.csv](../../outputs/defects/DEFECT_COORDINATES_EXTENDED.csv)

Pipeline producers:
- [BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py](../../BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py)
- [BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py](../../BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py)

Image path shortcut in UI:
- [images/defects](../../images/defects)

## 4) Script-specific behavior dependencies

### Fleet script

- depends on available column discovery to populate grouping combo box
- may create missing legend column in coords table by copying from summary via ORIGINAL_ROW_NUMBER
- expects summary subset tables for SUM/SMP/BEEP when installing handlers

### Chamber script

- depends on chamber ownership lists
- derives CHAMBER as either selected chamber list member or FLEET
- optional hiding of FLEET coordinates changes visible coordinate universe

## 5) Operational dependencies

- Scripts are intended to run in JMP with interactive report objects.
- Selection propagation relies on Make Row State Handler behavior.
- Report formatting assumes certain report tree object names and hierarchy remain stable.
