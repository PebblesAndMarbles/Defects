# Fleet and Chamber Dispo JSL: Current Understanding

## Surf Scan Addendum (2026-04-27)

This addendum captures the current surf-scan state after the recent chamber/fleet convergence work.

### Active surf-scan scripts

- [AMEct 1278 Surf Scan Chamber Dispo.jsl](AMEct%201278%20Surf%20Scan%20Chamber%20Dispo.jsl)
- [AMEct 1278 Surf Scan Fleet Dispo.jsl](AMEct%201278%20Surf%20Scan%20Fleet%20Dispo.jsl)

### Current surf-scan architecture

- Both scripts now use EVENT as the primary by-group axis for trend/variability/wafermap rows.
- Fleet report structure has been aligned to chamber-style assembly:
  - one H List container with three fit groups (trend, wafermap, variability)
  - one metrics event-view table plus one coords event-view table
  - one summary-to-coordinates row-state handler using ORIGINAL_ROW_NUMBER mapping
- Both scripts support EVENT MODE filtering:
  - SS only
  - SEG only
  - SS and SEG

### Row alignment model

- Trend row height is treated as canonical.
- Variability and wafermap reports are padded/shrunk per rendered row to match trend row height.
- This alignment is applied after render (`Wait(0)`) to include JMP wrapper/legend expansion effects.

### Marker and legend behavior (surf-scan)

- Wafermap panels do not add row legends in fleet.
- Chamber wafermap styling no longer forces a solid marker theme on coordinates.
- Wafermap marker assignment should follow table-level point styling helper behavior (BEEP cross, small-particle dot, optional black-marker override).

This document captures my current understanding based on static review of:
- [AMEct 1278 Inline Defects Fleet Dispo.jsl](AMEct%201278%20Inline%20Defects%20Fleet%20Dispo.jsl)
- [AMEct 1278 Inline Defects Chamber Dispo.jsl](AMEct%201278%20Inline%20Defects%20Chamber%20Dispo.jsl)

## High-level purpose

Both scripts build JMP interactive dispo dashboards that combine:
- NCDD summary wafer-level metrics (SUM_NCDD, SMP_NCDD, BEEP_NCDD)
- Defect coordinate point clouds (WAFER_X_MM, WAFER_Y_MM)
- Linked interactions between trend/variability selections and wafer maps

They both create a single composite UI window containing:
- Info distributions
- Trend charts (by layer)
- Variability charts
- Wafer maps for ALL, SMP, and BEEP defects
- A button to open the defect image folder in Explorer

## Data sources and paths

Both scripts define two source families:
- 60-day source files under BE_60day
- integrated/extended source files under BE outputs

### Chamber script source behavior

In [AMEct 1278 Inline Defects Chamber Dispo.jsl](AMEct%201278%20Inline%20Defects%20Chamber%20Dispo.jsl), the source radio selection actively switches paths:
- Option 1: 60-day CSV + 60-day coordinates
- Option 2: integrated/extended CSV + integrated/extended coordinates

### Fleet script source behavior

In [AMEct 1278 Inline Defects Fleet Dispo.jsl](AMEct%201278%20Inline%20Defects%20Fleet%20Dispo.jsl), the dialog still shows source options, but current path assignment resolves to integrated/extended paths either way.

Interpretation: Fleet currently behaves as integrated-mode by default and in practice.

## Shared architecture pattern

Both scripts follow this pattern:
1. Show options dialog.
2. Open NCDD summary table and defect coordinates table.
3. Build ORIGINAL_ROW_NUMBER in coordinates table using WAFER_ID + LAYER mapping from summary table.
4. Apply status/fleet filters.
5. Build explicit _INCLUDE column in coordinates to avoid relying on hide/exclude transfer semantics.
6. Subset coordinates into ALL/SMP/BEEP tables.
7. Build charts and wafer maps.
8. Apply chart formatting helper functions.
9. Install row-state handlers to sync selection into coordinate subsets.
10. Write lightweight usage log entry to a backup text file.

Current formatting behavior also includes a trend-driven row-height synchronization pass:
- trend row rendered heights are measured after legends are applied
- corresponding variability and wafermap panels are aligned to those row heights
- alignment uses outer padding to avoid distorting chart geometry

## Chamber Dispo specifics

### Chamber ownership logic

In [AMEct 1278 Inline Defects Chamber Dispo.jsl](AMEct%201278%20Inline%20Defects%20Chamber%20Dispo.jsl):
- Team-member chamber lists are hardcoded (Trey, Kayden, Chang, Adi, Travis, Tyler, Mathius, Sashank, William, Minog).
- There are two overrides:
  - Full SUBENTITY comma list (highest priority)
  - AME4xx + PMnn composer
- CHAMBER column is generated as:
  - actual subentity if in selected chamber_list
  - FLEET otherwise

### Fleet visibility toggle in chamber mode

The checkbox Show FLEET Coordinates controls whether coordinate rows with CHAMBER == FLEET are hidden/excluded.

### Wafermap point styling toggles

Chamber includes a Black Wafermap Markers checkbox.
- when checked, wafermap points are forced to black
- when unchecked, normal color coding is retained

Marker mapping on wafermaps is currently:
- BEEP: cross-style marker
- SMALL_PARTICLE: dot marker

### Status filter options in chamber mode

Chamber has 4 status modes:
1. Hide Highfliers NOT in chamber list
2. Hide ALL Highfliers
3. Hide BASELINE rows
4. Hide/Exclude nothing

## Fleet Dispo specifics

### Dynamic grouping column

In [AMEct 1278 Inline Defects Fleet Dispo.jsl](AMEct%201278%20Inline%20Defects%20Fleet%20Dispo.jsl):
- The user selects a grouping/legend column from available columns discovered from source files.
- Script ensures that grouping column exists in coordinates table by backfilling from summary table via ORIGINAL_ROW_NUMBER if needed.

### Wafermap point styling toggles

Fleet includes a Black Wafermap Markers checkbox.
- when checked, wafermap points are forced to black
- when unchecked, normal color coding is retained

Marker mapping on wafermaps is currently:
- BEEP: cross-style marker
- SMALL_PARTICLE: dot marker

### No Splines option

Fleet includes a No Splines option. When checked, trend charts are generated without Fit Spline; otherwise splines are added.

### Advanced status filtering in fleet mode

Fleet has 9 status filter modes, including granular BEEP/SMP highflier and baseline controls.
It supports STATUS_BEEP/STATUS_SMP when present, with CLASS+STATUS fallback logic when those per-metric status columns are absent.

### Metric-specific summary alignment

Fleet computes legend|layer keys from coordinate subsets and builds summary subsets:
- Summary SUM
- Summary SMP
- Summary BEEP

This keeps trend/variability panes aligned to the exact coordinate coverage of each metric.

## Selection synchronization behavior

### Chamber script sync model

In [AMEct 1278 Inline Defects Chamber Dispo.jsl](AMEct%201278%20Inline%20Defects%20Chamber%20Dispo.jsl):
- One Make Row State Handler is attached to the main summary table.
- Selected summary rows propagate to all coordinate tables using ORIGINAL_ROW_NUMBER membership.

### Fleet script sync model

In [AMEct 1278 Inline Defects Fleet Dispo.jsl](AMEct%201278%20Inline%20Defects%20Fleet%20Dispo.jsl):
- Handlers are attached to metric summary subsets (SUM/SMP/BEEP), not the original dt.
- Propagation to coordinate tables is by WAFER_ID + LAYER key matching.

Reason this exists: trend/variability charts run from metric summary subsets in Fleet.

## Wafermap formatting notes

Both scripts:
- Normalize wafer map frame and axis extents
- Draw a wafer boundary circle
- Render all/smp/beep wafer maps by layer

Both scripts now prefer Marker Drawing Mode "Normal" for wafermaps.

To preserve table-level point styling controls, wafermap row legends are set to non-overriding behavior (or suppressed under black-marker mode).

Both scripts include row-height alignment between trend, variability, and wafermap columns using trend row rendered heights as the alignment source.

Fleet includes extra defensive handling for report object shape (single object vs list), matching the known JMP behavior where Report can return either form.

## Defect image folder integration

Both scripts define a button opening:
- \\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\defects

This matches your integrated migrated image location and current manifest/image workflow.

## Usage tracking logs

Both scripts append simple timestamp log entries.

- Chamber writes to:
  - \\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\backups\BEEP_SMP_LAYER_CHAMBER_log.txt
- Fleet writes to:
  - \\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\backups\INLINE_DEFECTS_FLEET_log.txt

## Practical caveats and assumptions

1. ORIGINAL_ROW_NUMBER mapping key is WAFER_ID + LAYER only.
If repeated wafer+layer rows exist, mapping may resolve to the last row encountered.

2. Fleet source selector currently appears effectively integrated-only by assignment logic.
If true source toggling is desired, path assignment should be revisited.

3. Selection sync behavior is intentionally different between scripts:
- Chamber syncs from main dt
- Fleet syncs from metric-specific summary subsets

This is consistent with each script's chart data source design.

## Current conclusion

- Chamber Dispo is chamber-owner oriented with explicit FLEET partitioning and optional fleet-point suppression.
- Fleet Dispo is cross-fleet exploratory analysis with dynamic grouping and metric-aware subset alignment.
- Both are now structurally compatible with your integrated BE outputs and defect image folder layout used by the Python pipeline.