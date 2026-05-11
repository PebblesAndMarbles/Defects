# JSL Modification Checklist

Use this checklist before and after any edit to Fleet/Chamber dispo scripts.

## Before editing

1. Identify target script and mode:
- [AMEct 1278 Inline Defects Fleet Dispo.jsl](../../AMEct%201278%20Inline%20Defects%20Fleet%20Dispo.jsl)
- [AMEct 1278 Inline Defects Chamber Dispo.jsl](../../AMEct%201278%20Inline%20Defects%20Chamber%20Dispo.jsl)

2. Confirm expected behavior type:
- source selection
- filtering
- chart formatting
- wafermap formatting
- selection synchronization

3. Record baseline outputs:
- subset counts
- visible trend panes
- visible wafermap panes

## During editing

1. Keep changes localized to one concern.
2. Do not change both filtering and sync logic in one pass.
3. Preserve ORIGINAL_ROW_NUMBER behavior unless intentionally redesigning key mapping.
4. If touching fleet chart data sources, re-check handler attachment tables.
5. If touching wafermap formatting, handle both list and single report object shapes.
6. If touching row-height alignment, keep trend as source-of-truth and avoid resizing wafermap/variability data frames directly.

## After editing

1. Open script and run with integrated source.
2. Validate no missing-column runtime errors.
3. Validate subset counts are non-zero where expected.
4. Validate selection sync from trend to wafermap points.
5. Validate image folder button still opens [images/defects](../../images/defects).
6. Validate status filter modes still match labels.
7. Validate window renders all three metric sections (SUM/SMP/BEEP).
8. Validate wafermap marker mapping:
- BEEP uses cross-style marker
- SMALL_PARTICLE uses dot marker
9. Validate Black Wafermap Markers checkbox behavior in both scripts.
10. Validate cross-column row-height alignment for a high-cardinality legend case.

## Release gate

Mark complete only when:
- all checks pass in a clean JMP session
- no new warnings in the log window
- behavior is consistent across at least one 8M5CL and one 8M6CL layer view
