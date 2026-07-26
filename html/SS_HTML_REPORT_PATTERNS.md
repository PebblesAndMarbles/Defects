# SS HTML Report Patterns and Handoff Notes

This note captures the current standards and implementation patterns used by the SurfScan HTML reports.

## 1. General HTML Styling We Closed In On

### Page and Layout
- Dark theme baseline:
  - page background: `#10161d`
  - panel background: `#0f151c`
  - borders: `#24303b`
  - primary text: `#e6edf3`
  - accent text: `#98d8c8`
- Fixed header bar at top with compact metadata.
- Viewport-filling frame below header.
- Left panel for wafermap + coordinate/summary table.
- Right panel for image grid.
- Internal panel scrolling preferred over full-page scrolling on desktop.
- Responsive fallback (`max-width: 1100px`) allows stacked layout and page scrolling.

### Table and Image Presentation
- Sticky table headers for scrollable panes.
- Compact spacing for laptop-friendly usage.
- Defect ID column kept narrow in chamber-event image table.
- Missing image cells explicitly rendered as `missing`/dash placeholder.
- Images lazy-loaded and linked to local source path/URI.

### Wafermap Visual Conventions
- Wafer boundary circle at radius 150 mm.
- Plot limits effectively clipped to near `-151..151`.
- Grid retained for spatial context.
- In current chamber-event report:
  - imaged points plotted as blue circles
  - non-imaged points plotted as gray x markers
  - defect labels for imaged points only using leader lines and collision-avoidance placement.

## 2. Gotchas and Matching Patterns (Coords CSV, Manifest, Filesystem Images)

### Core Matching Problem
Image files, manifest rows, and SS coordinate rows are not consistently keyed by a single stable ID. Matching requires multi-key normalization and fallback logic.

### Required Normalization Patterns
- Normalize timestamp strings to canonical `YYYY-MM-DD HH:MM:SS` before keying.
- Normalize IDs via string cleanup and numeric canonicalization (`"2.0" -> "2"`).
- Normalize wafer keys and defect IDs from both manifest and coordinates.

### Event Scoping Pattern
- Use event token from filename (`yymmdd_hhmm`) to scope manifest/image candidates.
- Optional file mtime date filter is only a disambiguation fallback, not the primary selector.

### Coordinate Join Pattern
- Build event key sets from manifest:
  - `(INSPECTION_TIME, WAFER_KEY, DEFECT_ID)`
  - `(INSPECTION_TIME, WAFER_ID, DEFECT_ID)`
- Match coordinate rows using normalized timestamp + either wafer-key path or wafer-id path.

### Image Slot Mapping Pattern
- Canonical image slots expected: `[8, 2, 3, 4]`.
- Actual image IDs can be offset in source inventory.
- Infer best offset and map actual IDs back to canonical slots before rendering table columns.

### Element Composition Pattern
- EDX values sourced from `EDX_ELEM*_...` columns.
- Sort positive element components by descending value.
- Format label output consistently (symbol-only or symbol+tuple depending on report mode).

### Known Failure Modes and Mitigations
- Empty report images when relying only on date filter:
  - Mitigation: drive by event token first; date filter optional.
- Coordinate mismatch due to timestamp formatting differences:
  - Mitigation: strict timestamp normalization before matching.
- Duplicate manifest rows for same defect/image family:
  - Mitigation: deterministic dedup prior to report row building.
- Large coordinates CSV memory pressure:
  - Mitigation in element report: stream/parse coordinates file rather than loading full DataFrame.

## 3. SurfScan HTML Report Generators

### SS_CHAMBER_EVENT_REPORT.py
- Purpose:
  - Single chamber + single event token report.
  - Produces wafermap plus image-slot table and coordinate table.
- Inputs:
  - image inventory under `images/surf_scan/<CHAMBER>`
  - `outputs/surf_scan/SS_EDX_IMAGES.csv`
  - `outputs/surf_scan/SS_COORDINATES.csv`
- Output default:
  - `html/adhoc_chamber_events`
- CLI support includes:
  - `--chamber`
  - `--event-token`
  - `--target-date` (optional)
  - `--out-dir`

### SS_ELEMENT_REPORT.py
- Purpose:
  - Cross-chamber element-driven report (lookback window).
  - Uses SVG wafermap overlay and chamber color coding.
- Inputs:
  - `outputs/surf_scan/SS_EDX_IMAGES.csv`
  - `outputs/surf_scan/SS_COORDINATES.csv`
  - image folders under `images/surf_scan/*`
- Output default:
  - `html/adhoc_elements`
- CLI support includes:
  - `--elements`
  - `--lookback-days`
  - `--out-dir`

## Rename Convention Applied
- `CHAMBER_EVENT_REPORT.py` -> `SS_CHAMBER_EVENT_REPORT.py`
- `ELEMENT_REPORT.py` -> `SS_ELEMENT_REPORT.py`

This prefix is intended to keep SurfScan-specific standalone tools clearly distinguishable from future inline-report generators.
