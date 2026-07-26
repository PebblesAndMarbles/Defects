# Inline HTML Reports Infrastructure — Scope & Design Questions

## 1. Reference Material Summary

### Existing SurfScan (SS) HTML Report Framework
Based on [SS_HTML_REPORT_PATTERNS.md](SS_HTML_REPORT_PATTERNS.md):

**Report Generators:**
- `SS_CHAMBER_EVENT_REPORT.py`: Single chamber + single event token
  - Inputs: image inventory, `SS_EDX_IMAGES.csv`, `SS_COORDINATES.csv`
  - Output: `html/adhoc_chamber_events`
  - CLI: `--chamber`, `--event-token`, `--target-date`, `--out-dir`
  - Visual: wafermap + image-slot table + coordinate table

- `SS_ELEMENT_REPORT.py`: Cross-chamber element-driven (7-day lookback window)
  - Not applicable to inline (no EDX/element analogue needed)

**Key Implementation Patterns:**
- Dark theme with fixed header + viewport-filling frame below
- Left panel: wafermap + coordinate/summary table
- Right panel: image grid (lazy-loaded)
- Sticky table headers for scrollable panes
- Wafermap conventions: blue circles (imaged points), gray x (non-imaged), leader lines for labels
- Multi-key normalization for matching images ↔ manifest ↔ coordinates (timestamp, wafer key, defect ID)
- Image slot mapping: canonical slots [8, 2, 3, 4] with offset inference

### Inline Defects Data Structure
From `outputs/defects/DEFECT_COORDINATES_EXTENDED.csv`:

**Columns** (relevant subset):
- `YYMM`, `LOT`, `ACTUAL_LOT`, `WAFER_ID`, `WAFER_KEY`
- `LAYER`, `INSPECTION_TIME`, `DEFECT_ID`
- `CLASS`, `FINEBIN`
- `WAFER_X_MM`, `WAFER_Y_MM`, `IMAGE_COUNT`
- `SUBENTITY` (chamber identifier)
- `RECIPE`, `SUBENTITY_END_TIME`, `INSPECT_TOOL`
- Various process flags (SUM_NCDD, PILOT_STATUS, BEEP_NCDD, SMP_NCDD, etc.)

**Image Organization:**
- Location: `images/defects/`
- Organized by chamber: `AME401_PM1/`, `AME403_PM1/`, ..., `AME427_PM6/` (50+ chambers)
- Naming pattern: `YYMMDD_HHMM_LOT_DEFECT_COUNT_SUBENTITY_LAYER_*.jpg`
  - Example: `260511_1207_D609195_248_SMP_8M5CL_2848_2.jpg`
  - Multiple image slots per defect (e.g., _2.jpg, _3.jpg for different inspection angles)

**Production Folder Structure** (Proposed):
- New folder: `Inline_Subentity_Reports/`
- Contents: Chamber-specific HTML files (one per chamber)

---

## 2. Scope: Proposed Inline HTML Reports

### 2.1 Ad-Hoc Report Generators

Create **INLINE_CHAMBER_EVENT_REPORT.py** with CLI support for three scopes:

1. **By Wafer**
   - Filter: `--wafer-key` or `--lot` + `--wafer-id`
   - Show: all defects in that wafer inspection
   - Output: `html/adhoc_chamber_events/`

2. **By Chamber**
   - Filter: `--chamber` (via SUBENTITY) + optional `--event-token` or `--target-date`
   - Show: all defects in that chamber/event combination
   - Output: `html/adhoc_chamber_events/`

3. **By Subentity** (Recipe/Process Step)
   - Filter: `--subentity` + optional `--target-date` + optional `--lookback-days`
   - Show: all defects for that process step in the window
   - Output: `html/adhoc_chamber_events/`

**Visual Structure** (mirroring SS_CHAMBER_EVENT_REPORT):
- Fixed header: metadata summary (chamber, date, wafer count, defect count, image count)
- Left panel: wafermap (with imaged/non-imaged points) + defect summary table
- Right panel: image grid showing all images for selected defect or LOT
- Sticky headers for scrollable panes

**Data Inputs:**
- `outputs/defects/DEFECT_COORDINATES_EXTENDED.csv`
- `images/defects/<CHAMBER>/` folders
- Optional: manifest file (if we create image metadata tracking like SS)

---

### 2.2 Production Report Generator

Create **INLINE_PRODUCTION_SUBENTITY_REPORTS.py** to generate chamber-specific reports combining all images in library.

**Per-Chamber Report Design:**
- Scope: all images for a single chamber (across all history in current library)
- Stacked layout: organize by LOT, then by WAFER within each LOT
- Content per LOT stack:
  - LOT metadata header
  - Wafermap (stacked wafermaps OK if multiple wafers per LOT)
  - Image grid (all images for defects in that LOT, arranged by wafer)
  - Summary statistics (defect count, image count, layer breakdown)
- Output: `Inline_Subentity_Reports/<CHAMBER>.html` (one file per chamber)

**Workflow:**
- Scheduled or on-demand execution
- Iterates over all chamber subdirectories in `images/defects/`
- Reads coordinates CSV, scans image inventory, groups by LOT
- Generates `Inline_Subentity_Reports/AME401_PM1.html`, etc.

**Visual Considerations:**
- Responsive layout (may need horizontal scrolling for large image counts)
- Collapsible LOT sections to avoid overwhelming single page
- Lightweight by default: lazy-load images, paginate by LOT
- Same dark theme as SS reports

---

## 3. Clarifying Questions

### A. Production Report Scope & Retention
1. Should chamber-specific production reports be **cumulative** (all historical images ever generated for that chamber) or **rolling window** (last 60 days like inline image retention)?
   - Cumulative: larger files but complete historical record per chamber
   - Rolling: matches pipeline retention policy, easier to regenerate

2. If cumulative, should we implement **incremental updates** (append new images) or **full regeneration** on each run?

### B. Data Organization & Filtering
3. Should SUBENTITY be the primary chamber identifier, or is there a dedicated CHAMBER column we should use instead?
   - Currently seeing `SUBENTITY` = "SMP_8M5CL", "SMP_8M6CL", etc.
   - Are CHAMBER and SUBENTITY equivalent, or should we distinguish them?

4. For production reports, should we **organize by LAYER** as well as LOT?
   - E.g., `8M5CL/LOT_A/` then `8M6CL/LOT_A/` to keep layer data separate?

### C. Wafermap & Image Rendering
5. For each LOT section in production reports, should we:
   - Generate **one combined wafermap** showing all defects from all wafers in that LOT?
   - Generate **one wafermap per wafer** within the LOT?
   - Generate **no wafermap** and rely only on image grid for quick reference?

6. Should inline image slot mapping (like SS's canonical [8, 2, 3, 4]) be configurable, or can we infer it from the filenames?
   - Current inline images appear to use `_2.jpg`, `_3.jpg` suffixes
   - Should we standardize a canonical set or auto-detect?

### D. Ad-Hoc Report Features
7. Should ad-hoc `--target-date` filtering support a **time range** (e.g., `--start-date` / `--end-date`) for broader queries?

8. Should ad-hoc reports **exclude** images below a quality threshold (e.g., very small images, corrupted files)?
   - How should we handle missing images gracefully (show placeholder, skip, note in summary)?

### E. Manifest & Image Tracking
9. Should we create an **image manifest file** (like SS uses `SS_EDX_IMAGES.csv`) to track:
   - Image metadata (path, file size, file date, coordinates row reference)
   - Validation/quality flags
   - Scan health per chamber/event?
   - Or rely on directory traversal + coordinates join only?

10. Should **image pruning** align with the 60-day inline retention policy, or should production reports be backed by an archive?

### F. Execution & Scheduling
11. Should production reports be:
    - **Pre-generated nightly** (requires a scheduled orchestrator entry point)?
    - **Generated on-demand** (user triggers manually or via HTTP endpoint)?
    - **Both** (nightly + ad-hoc)?

12. Should the ad-hoc report generator be integrated into the main `8M5CL_8M6CL_UPDATE.py` orchestrator, or remain standalone?

---

## 4. Implementation Milestones (Conditional)

Based on answers above, suggested order:

1. **Phase 1: Ad-hoc By-Chamber Report**
   - Minimal scope: single chamber + event token
   - Mirrors `SS_CHAMBER_EVENT_REPORT.py` structure
   - Validates image matching & wafermap logic

2. **Phase 2: Ad-hoc Extended Filtering**
   - Add --wafer-key, --subentity, --lookback-days variants
   - Test multi-wafer and cross-event aggregation

3. **Phase 3: Production Chamber Reports**
   - Batch generator over all chambers
   - LOT stacking + responsive layout
   - Integration with orchestrator (optional scheduling)

4. **Phase 4: Polish**
   - Image manifest if needed
   - Quality checks & error handling
   - Documentation & runbook

---

## 5. File & Folder Plan

### New Files (Proposed)

```
html/
  INLINE_HTML_REPORT_PATTERNS.md          # Implementation notes (parallel to SS_HTML_REPORT_PATTERNS.md)
  INLINE_CHAMBER_EVENT_REPORT.py          # Ad-hoc report generator
  adhoc_chamber_events/                   # Output folder (already exists, reuse)

BE_QUERY_FILES/
  INLINE_PRODUCTION_SUBENTITY_REPORTS.py # Production chamber report batch generator
  inline_config.py                        # Shared config for inline reporters (optional)

Inline_Subentity_Reports/                # NEW: Production output folder
  AME401_PM1.html
  AME401_PM2.html
  ...
  AME427_PM6.html
```

### Configuration

- Extend or create `BE_QUERY_FILES/pipeline_config.py` with inline-specific paths:
  - `INLINE_IMAGES_ROOT = "images/defects"`
  - `INLINE_DEFECT_COORDS_CSV = "outputs/defects/DEFECT_COORDINATES_EXTENDED.csv"`
  - `INLINE_ADHOC_OUTPUT_DIR = "html/adhoc_chamber_events"`
  - `INLINE_PRODUCTION_OUTPUT_DIR = "Inline_Subentity_Reports"`

---

## 6. Next Steps

1. **User input** on clarifying questions (Section 3 above)
2. **Detailed design document** for chosen scope
3. **Prototype ad-hoc report** (Phase 1)
4. **Iterate on visual design** with sample chamber data
5. **Integrate into orchestrator** (if scheduling desired)

---

*Document created: 2026-07-09*  
*Reference: SS_HTML_REPORT_PATTERNS.md, INLINE_PIPELINE_DESIGN.md, SURF_SCAN_PIPELINE_DESIGN.md*
