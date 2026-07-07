# HTML Reporting Workflows

## Purpose
This document summarizes the HTML reporting workflows implemented in this BE workspace for defect and SURF scan image review. It is intended as dashboard bootstrap context: what scripts exist, how they work, what design choices were made, and what tradeoffs have already been encountered.

This is not a final dashboard architecture document. It is a practical implementation summary of report-generation patterns already in use.

## Reporting families implemented so far
There are currently two main HTML report families relevant to this workspace.

### 1. Inline defect rollup reports
Primary script:
- rollups/CENTER_DEFECT_REPORT.py

Purpose:
- Build Center/Edge HTML reports from rollup CSVs.
- Render wafermaps plus image grids for inline defect data.

Source characteristics:
- Uses outputs/defects/DEFECT_COORDINATES_EXTENDED_IMAGES.csv as the image manifest.
- Uses rollup CSVs under rollups for source defect tables.

Image policy:
- Strictly requires both IMAGE_ID 2 and 3.
- Requires LOCAL_IMAGE_FILE to exist.
- Produces side-by-side brightfield/darkfield layout across 8M5CL and 8M6CL.

Layout characteristics:
- Includes wafermaps.
- Includes classification distribution tables.
- Includes image grids with per-cell labels.

### 2. SURF scan chamber/event image reports
Primary script:
- rollups/AME401_PM1_RECENT_PMEASURED_REPORT.py

Despite the filename, this script is now generalized and can build chamber reports for multiple PRIMARY_EQUIP values by CLI argument.

Purpose:
- Build focused HTML image reports for recent SURF scan events.
- Start from manifest verification, then render images grouped by wafer and defect.
- Support event-token scoping such as 260611_0547.

Representative outputs generated:
- rollups/ame401_pm1_recent_pmeasured_report_20260609_152735.html
- rollups/ame401_pm1_recent_pmeasured_report_20260611_111141.html
- rollups/ame403_pm2_recent_pmeasured_report_20260611_112618.html
- rollups/ame417_pm5_recent_pmeasured_report_20260611_142516.html

### 3. YPO-focused stacked EDX report
Primary script:
- rollups/YPO_DEFECT_IMAGE_REPORT.py

Purpose:
- Build a filtered HTML report from a stacked CSV subset, originally around YPO defects.
- Group by chamber/event/wafer.
- Render four SURF image slots.

This script is useful as a pattern for stacked defect data joined to SURF image manifests, even if the final dashboard does not use the same exact filtering logic.

Representative output:
- rollups/ypo_defect_image_report_20260605_172242.html

## Core design choices that were implemented

### 1. HTML is generated as standalone static files
All current report scripts generate standalone HTML files under rollups.

Benefits:
- Easy to email, archive, or open locally.
- Zero app server requirement.
- Fast iteration during workflow design.

Tradeoff:
- No centralized state, filtering backend, or dynamic querying.

### 2. Images are linked in place, not copied
Current reports intentionally reference existing image paths via file URIs.

Reasoning:
- Minimize network-drive duplication.
- Avoid slow copy operations.
- Keep report generation lightweight on disk usage.

Implication:
- If source files move or disappear, stale links can occur unless validated first.

### 3. Four-image SURF layout standard
For SURF scan reporting, the current standard image column order is:
- base8
- base2
- base3
- base4

This was chosen after iterative refinement during user review.

### 4. Fixed-height image rendering
Later report revisions standardized display using fixed-height image boxes across columns.

Reasoning:
- Some columns, especially base8, visually appeared mismatched when width was allowed to dominate.
- Fixed-height boxes produced more consistent side-by-side review.

### 5. Timestamped output filenames
Generated reports use timestamped output names.

Reasoning:
- Preserve snapshots of each run.
- Avoid accidental overwrite during iteration.
- Make handoff and comparison easier.

### 6. Chamber/event reports are now inventory-backed after manifest verification
This is the most important workflow refinement.

Original naive design:
- Use manifest rows directly to populate image slots.

Problem:
- The manifest was not always complete or accurate enough for all image slots.

Current improved design:
1. Use the manifest to verify wafer/event scope.
2. Use the chamber folder inventory to enumerate actual files for the verified event.
3. Build rows from parsed filenames rather than trusting the manifest to enumerate every image slot.

This current design is the most effective pattern for chamber/event image reviews.

## Script inventory and roles

### rollups/CENTER_DEFECT_REPORT.py
Role:
- Inline defect Center/Edge report builder.

Key behaviors:
- Reads inline rollup CSVs.
- Builds wafermaps.
- Uses strict manifest image existence policy.
- Renders 8M5CL/8M6CL side-by-side images.

Useful reusable ideas:
- normalize_key helper for stable joins.
- Manifest dedup by newest INSPECTION_TIME.
- HTML image-cell and static report structure patterns.

### rollups/YPO_DEFECT_IMAGE_REPORT.py
Role:
- Stacked CSV to SURF-image report for targeted defect subsets.

Key behaviors implemented over the iteration:
- ELEMENT filter for YPO.
- Duplicate detection and optional collapse by PRIMARY_EQUIP + INSPECTION_TIME + WAFER_ID + DEFECT_ID.
- Event-aware join keys to avoid repeated-wafer cross-event image mixing.
- Stale-link pruning by validating selected paths before HTML emission.
- Strict drop of rows with any missing image.
- Four-image display with base8 first.

Useful reusable ideas:
- Event-aware manifest key design.
- Explicit missing/stale-link accounting.
- Tight report row inclusion criteria.

### rollups/AME401_PM1_RECENT_PMEASURED_REPORT.py
Role:
- Generalized chamber/event report generator for SURF images.

Current capabilities:
- Supports arbitrary chamber via --primary-equip.
- Supports optional event token via --event-token.
- Supports optional slot mapping via preset chamber map or --slot-map override.
- Uses manifest verification plus inventory-backed slot fill.
- Groups by wafer and defect.
- Renders four image columns in order base8/base2/base3/base4.

This is currently the best starting point for dashboard-oriented chamber event review.

## Current command-line workflow

### Example: AME401_PM1 event-scoped run
```powershell
& "c:\users\tbatson\My Programs\SQLPathFinder3\Python3\python.exe" ".\rollups\AME401_PM1_RECENT_PMEASURED_REPORT.py" --target-date 2026-06-11 --event-token 260611_0547
```

### Example: AME403_PM2 event-scoped run
```powershell
& "c:\users\tbatson\My Programs\SQLPathFinder3\Python3\python.exe" ".\rollups\AME401_PM1_RECENT_PMEASURED_REPORT.py" --primary-equip AME403_PM2 --target-date 2026-06-11 --event-token 260610_1244
```

### Example: AME417_PM5 event-scoped run
```powershell
& "c:\users\tbatson\My Programs\SQLPathFinder3\Python3\python.exe" ".\rollups\AME401_PM1_RECENT_PMEASURED_REPORT.py" --primary-equip AME417_PM5 --target-date 2026-05-22 --event-token 260521_0849
```

### Optional slot map override
```powershell
--slot-map "061:10,176:11,210:12"
```

## Workflow details by script

### Workflow A: Inline Center/Edge report generation
1. Read rollup CSVs.
2. Normalize defect keys.
3. Load inline image manifest.
4. Keep only rows with required image pairs.
5. Build wafermaps.
6. Render HTML with summary and image grid.

Use when:
- Working with inline defect rollup outputs.
- Need layer-specific wafermaps and pairwise image review.

### Workflow B: Stacked defect to SURF image report
1. Read stacked source CSV.
2. Apply defect-level filtering.
3. Detect duplicates if needed.
4. Build event-aware manifest lookup.
5. Validate image paths to prune stale links.
6. Drop rows with missing required slots if strict completeness is desired.
7. Render grouped HTML.

Use when:
- Starting from a defect selection table rather than a chamber event folder.
- Need a more logic-heavy join between analytical defect rows and image manifest rows.

### Workflow C: Chamber/event image report
1. Read SS_EDX_IMAGES.csv.
2. Filter by PRIMARY_EQUIP.
3. Optionally filter by event token.
4. Verify LOCAL_IMAGE_FILE existence and modified date.
5. Identify wafer set in scope.
6. Scan chamber folder inventory for the same event token/date.
7. Parse filenames into wafer-short / defect / image-id components.
8. Rebuild defect rows from inventory.
9. Sort wafers by provided slot mapping when available.
10. Render static HTML.

Use when:
- Need a chamber-focused view of all images from a specific run.
- Manifest may be incomplete for enumerating all files.
- Slot ordering matters for operator review.

## Important design lessons learned

### 1. Manifest verification is necessary but not sufficient
The manifest is still useful for scoping, but direct folder inventory is often the better source of truth for actual report image slots.

### 2. Reused wafers require event-aware joins
Repeated test wafer reuse means joins must include inspection/event context, not just wafer/defect identifiers.

### 3. Slot ordering is user-facing and operationally important
For chamber event reports, users review wafers in tool slot order, not arbitrary wafer-id sort order.

The generalized chamber report script now supports this via:
- chamber-specific presets
- CLI slot-map override

### 4. Report inclusion policy should be explicit
Different workflows needed different policies:
- inline reports used strict image-pair requirements
- chamber/event reports kept partial rows when inventory existed
- YPO report eventually became strict and dropped any row with missing image slots

This likely becomes a configurable dashboard behavior later.

## Dashboard bootstrap recommendations
If building an HTML dashboard or moving toward a richer application, these existing pieces are the best starting points.

### Recommended reuse
- Reuse chamber/event report logic from rollups/AME401_PM1_RECENT_PMEASURED_REPORT.py
- Reuse event-aware join logic concepts from rollups/YPO_DEFECT_IMAGE_REPORT.py
- Reuse inline manifest normalization helpers from rollups/CENTER_DEFECT_REPORT.py

### Recommended architecture direction
1. Keep a verification layer separate from rendering.
2. Separate manifest-scoped metadata from folder-inventory image enumeration.
3. Treat slot mapping as configuration, not hardcoded logic.
4. Treat report inclusion policy as a configurable option.
5. Keep timestamped outputs or snapshots for debug comparability.

### Candidate future abstractions
- shared report utilities module for:
  - normalize_key
  - parse_time
  - path_to_uri
  - event token parsing
  - filename parsing
  - slot-map parsing
- report configuration file per chamber/event family
- one shared HTML template rather than repeated inline HTML strings
- a run-summary JSON sidecar for each report

## Current limitations
1. Most scripts are still single-file generators with inline HTML strings.
2. Slot mappings are only partially formalized.
3. Chamber report filename still reflects its origin name even though it is now generalized.
4. Report scripts are optimized for fast operational iteration, not yet for maintainable dashboard componentization.
5. No shared templating engine is in use yet.

## Files to review first for dashboard work
- rollups/AME401_PM1_RECENT_PMEASURED_REPORT.py
- rollups/YPO_DEFECT_IMAGE_REPORT.py
- rollups/CENTER_DEFECT_REPORT.py
- outputs/surf_scan/SS_EDX_IMAGES.csv
- images/surf_scan/<PRIMARY_EQUIP>
- docs/SURF_SCAN_MANIFEST_DISCREPANCY_HANDOFF.md

## Suggested immediate next step for dashboard design
Build around the chamber/event report workflow first.

Reason:
- It is currently the most operationally aligned workflow.
- It already supports chamber scope, event-token scope, slot ordering, and inventory-backed completeness.
- It directly matches the type of operator review requests that have been coming up in practice.
