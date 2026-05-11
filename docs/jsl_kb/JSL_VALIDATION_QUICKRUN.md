# JSL Validation Quick Runbook

Use this short runbook after any script change.

## 1) Pre-check files

Confirm integrated files exist:
- [outputs/wafer/8M5CL_8M6CL_EXTENDED.csv](../../outputs/wafer/8M5CL_8M6CL_EXTENDED.csv)
- [outputs/defects/DEFECT_COORDINATES_EXTENDED.csv](../../outputs/defects/DEFECT_COORDINATES_EXTENDED.csv)

If missing/stale, run update pipeline first:
- [BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py](../../BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py)

## 2) Chamber script quick validation

Run:
- [AMEct 1278 Inline Defects Chamber Dispo.jsl](../../AMEct%201278%20Inline%20Defects%20Chamber%20Dispo.jsl)

Check:
1. Dialog options render (source, team member, overrides, status).
2. CHAMBER column behavior:
- selected chambers retain chamber ID
- others marked FLEET
3. Toggle Show FLEET Coordinates and verify point inclusion changes.
4. Click trend points and verify wafermap coordinate selection updates.
5. Open DefectImages button launches [images/defects](../../images/defects).
6. Verify wafermap marker mapping:
- BEEP appears as cross-style marker
- SMALL_PARTICLE appears as dot marker
7. Toggle Black Wafermap Markers and verify wafermap points switch to black.
8. Use a high-cardinality legend case and verify row heights align across trend/wafermap/variability columns.

## 3) Fleet script quick validation

Run:
- [AMEct 1278 Inline Defects Fleet Dispo.jsl](../../AMEct%201278%20Inline%20Defects%20Fleet%20Dispo.jsl)

Check:
1. Grouping combo is populated.
2. No Splines checkbox toggles trend fit behavior.
3. Status filter modes produce expected row suppression.
4. Summary subsets SUM/SMP/BEEP have expected non-zero rows.
5. Selecting points in SUM/SMP/BEEP trend/variability updates coord selections.
6. Open DefectImages button launches [images/defects](../../images/defects).
7. Verify wafermap marker mapping:
- BEEP appears as cross-style marker
- SMALL_PARTICLE appears as dot marker
8. Toggle Black Wafermap Markers and verify wafermap points switch to black.
9. Use a high-cardinality legend case and verify row heights align across trend/wafermap/variability columns.

## 4) Pass/fail criteria

Pass when:
- no runtime error dialogs
- all three metric sections render
- selection synchronization works
- status mode semantics match labels

Fail when:
- empty wafermaps unexpectedly
- selection does not propagate
- missing-column errors
- chart formatting errors for single-layer or single-report cases

## 5) If failure occurs

Use:
- [JSL_TROUBLESHOOTING_PLAYBOOK.md](JSL_TROUBLESHOOTING_PLAYBOOK.md)
