# Surf Scan Fleet Dispo Implementation To-Do

## Goal
Port the finalized Chamber surf-scan behavior into Fleet Dispo while keeping row-level layout parity, event-mode filtering, and stable trend/wafermap interaction.

## Scope Baseline
- Source behavior: Chamber script is the canonical reference.
- Target behavior: Fleet script matches Chamber for UI controls, filtering, ordering, formatting, and debug instrumentation (with fleet-specific naming/paths only where required).

## Current Status (2026-04-27)
- Chamber alignment model is validated:
  - Trend is the canonical row target.
  - Variability and wafermap are adjusted to match per-event trend row height.
  - Final summary parity confirmed in validation run:
    - raw(trend,var,wmap) = (1639,1639,1639)
    - rowsum(trend,var,wmap) = (1609,1609,1609)
    - chrome(trend,var,wmap) = (30,30,30)
- Chamber cleanup applied:
  - Build fingerprint updated to 2026-04-27B.
  - Verbose debug defaults set to off (summary output retained).
- Fleet copy script has instrumentation available, now defaulted to quiet mode.
  - Set `val_debug_layout = 1` only when collecting fleet diagnostics.

## To-Do (Priority Order)

### 1) Pre-Port Snapshot
- [x] Capture current Fleet script baseline with a build fingerprint print.
- [x] Confirm Fleet script input paths and output table naming conventions.
- [ ] Confirm no duplicate Fleet script copies are being launched.

### 2) Event Mode UI + Early Event Filtering
- [x] Add EVENT MODE radio box to Fleet modal:
  - SS only (default)
  - SEG only
  - SS and SEG
- [x] Map SS events: SS0, SS1, SS7.
- [x] Map SEG events:
  - M_GO_ALL_SEG
  - M_GO_C_SEG
  - M_GO_E_SEG
  - M_GO_M_SEG
  - M_LIFT10X_SEG
  - M_MECH_CYCLE_SEG
  - M_SFV10X_SEG
- [x] Apply post-import row deletion filter on metrics table for unselected events.
- [x] Apply post-import row deletion filter on coords table for unselected events.
- [x] Print one event-filter summary line (mode, kept events, removed row counts).

### 3) Deterministic Event Ordering
- [x] Build a single ordered event list from selected mode.
- [x] Apply the same custom EVENT order to all view tables used in report generation.
- [x] Avoid nested event spec structures that require double subscripting.

### 4) Data Mapping + Interaction Stability
- [x] Keep ORN mapping key as: WAFER_KEY|EVENT|INSPECTION_TIME.
- [x] Keep one metrics event-view table and one coords event-view table.
- [ ] Keep placeholder coord row insertion for missing events when needed.
- [x] Keep row-state handler sync pattern from summary to coords view.
- [ ] Verify callback prints selected summary rows, unique ORNs, matched coords rows.

### 5) Chart Formatting Parity
- [ ] Keep trend x tick labels non-angled.
- [ ] Keep trend marker drawing mode as Outlined.
- [x] Remove wafermap legends and avoid forcing a wafermap marker theme.
- [x] Keep y-axis max at 10 for trend/variability charts.
- [ ] Keep varchart per-group width setting.

### 6) Layout Alignment Parity
- [x] Keep trend frame target uniform by row (frame-height driven).
- [x] Keep row-level alignment routine using post-render heights.
- [x] Keep baseline auto-pad logic row-sum driven (not raw fitgroup delta driven).
- [x] Confirm no auto-padding occurs when row sums are already equal.

Fleet coding status note:
- Trend-canonical row-height alignment and nontrend pad/shrink logic are now implemented in `AMEct 1278 Surf Scan Fleet Dispo.jsl`.
- Runtime validation logs confirm elongated-row spacing is correct.
- Fleet report structure now matches chamber-style assembly (single H List box with trend/wafermap/variability fit groups).

### 7) Debug Output Parity
- [x] Add Fleet build fingerprint print.
- [x] Keep format debug lines for trend and variability report/frame heights.
- [x] Keep per-event layout debug line.
- [ ] Keep one final summary line with raw and row-sum values.

### 8) Validation Matrix
- [ ] Run with SS only and verify only SS events render.
- [ ] Run with SEG only and verify only SEG events render.
- [ ] Run with SS and SEG and verify combined ordering.
- [ ] Validate row parity from post(trend,var,wmap) debug tuples.
- [ ] Validate final summary row sums align.
- [ ] Validate interaction callback counts are plausible for fleet density.

### 9) Cleanup Before Production
- [x] Reduce debug noise to minimal required lines.
- [ ] Keep build fingerprint for runtime file verification.
- [ ] Remove stale/unused helper functions and constants.
- [ ] Re-check for no syntax errors.

## Fleet Next Pass (Execution Order)
1. Port chamber alignment strategy into fleet script core path:
  - trend-canonical target
  - var/wmap apply toward trend target
  - live post-render height reads in alignment
2. Keep fleet debug gates off by default; enable only for validation runs.
3. Add fleet final summary print matching chamber summary shape.
4. Run SS-only validation and compare per-event post(trend,var,wmap) tuples.
5. Run mixed-mode validation and verify interaction sync still behaves.

## Exit Criteria
- Fleet output matches Chamber behavior for event filtering, row alignment, marker/tick styling, and interaction sync.
- Final validation logs show stable row-level parity and no runtime errors.
