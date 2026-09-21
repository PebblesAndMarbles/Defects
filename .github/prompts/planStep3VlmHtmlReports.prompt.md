## Plan: Step 3 VLM HTML Reports

Build a static, defect-by-defect HTML report for the enriched VLM production data. The report should reuse the existing Alloy/Class review patterns, but change the layout so the top of the page is a responsive brightfield/darkfield image grid with no metadata, then a scrollable detail section below for per-defect attributes, provenance, and reviewer comments. The first release is static HTML only; no new feedback backend is in scope unless that is later requested.

**Steps**
1. Confirm the input contract from Step 2 and the report consumer shape. Treat the enriched production CSV as the primary source, with the ground-truth BEEP CSV as an optional overlay for cohort counts and labeled/unlabeled filtering. Reuse the normalized join-key conventions already established in the probe/enrichment work so the report does not invent a new identity model.
2. Create a new HTML builder script, likely under `images/Alloy_Class/reporting/`, that follows the existing `build_generic_description_html_report.py` pattern but emits the new layout. It should load enriched rows, parse the VLM attributes, and generate a single static `.html` file with the same locked-file write fallback behavior used elsewhere in the repo.
3. Implement the responsive image grid header. The top section should show bright and dark images in a density-oriented grid that wraps and collapses as the window narrows, matching the layout intent from `html/SS_INLINE_CHAMBER_REPORT.py` (lines ~707-787: `display: grid`/`grid-template-columns: repeat(auto-fill, 93px)` thumbnail grid plus `display: flex`/`flex-wrap: wrap` sections) rather than its batch-wrapper caller `SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py`, which contains no HTML/CSS of its own. This section should intentionally suppress metadata so the page can be used for image-snipping and fast visual scanning.
4. Build the detail region below the grid. Reuse the per-case image-plus-attributes review pattern from `build_generic_description_html_report.py`, but place the details beneath the grid instead of alongside it. Keep the structured attributes table schema-agnostic enough to survive prompt/version changes, while giving first-class display to the VLM fields the user wants to filter on: shape flags, texture flags, defect_count buckets, confidence/review_required, and provenance columns.
5. Add client-side filtering and cohort views. Implement browser-side filters for the selected VLM attributes and basic production fields, then add a simple aggregate view that shows cohort counts and percentages by attribute and BEEP truth state. Keep the aggregation simple and deterministic: counts first, no weighting or normalization in the initial pass.
6. Make reviewer feedback comment-only and static. Reuse the existing comment-widget style from the generic-description report if needed, but do not add a new portal backend in this first pass. Preserve localStorage behavior if a per-session note or draft comment is useful, but the output should remain a static HTML file.
7. Wire the report to the existing pipeline entry point that already produces the enriched CSV. The HTML builder should be callable from the Step 2 workflow or a small wrapper so that report generation is one explicit step after enrichment, rather than a separate bespoke system.
8. Validate the output against real data. Check that the report renders with production-scale row counts, that the responsive image grid wraps correctly, that the detail section still shows all key VLM fields, and that filtering/cohort counts agree with the source CSVs on a small sampled slice before rolling it out to the full dataset.

**Relevant files**
- `images/Alloy_Class/reporting/build_generic_description_html_report.py` — reuse the existing report-building, image rendering, and locked-file write patterns.
- `images/Alloy_Class/reporting/build_beep_labeling_report.py` — reuse the client-side state and report-generation structure as a reference for list rendering and interactive controls.
- `images/Alloy_Class/tools/enrich_production_with_vlm_attributes.py` — Step 2 output contract and column names that Step 3 should consume.
- `images/Alloy_Class/outputs/beep_evidence/beep_evidence_ground_truth.csv` — optional truth overlay for cohort counts and labeled/unlabeled filtering.
- `html/SS_INLINE_CHAMBER_REPORT.py` — layout reference for the responsive image-grid behavior the user wants (the grid/flex CSS lives here, not in its batch-wrapper caller `SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py`).
- `images/Alloy_Class/reporting/build_probe_html_report.py` — shared image and HTML helper patterns.

**Verification**
1. Generate the report from a real enriched CSV sample and confirm the top image grid is responsive, metadata-free, and dense enough for snipping.
2. Confirm the detail section still renders the per-defect VLM attributes and provenance fields below the grid.
3. Exercise the filters on a small known slice and verify the displayed counts and cohorts match the source CSV rows.
4. Open the HTML in a browser and confirm the page remains usable at both wide and narrow widths.
5. If the report is later extended with a portal, add a separate validation step for the backend contract at that time instead of now.

**Decisions**
- Scope is static HTML only for this step.
- The report should emphasize cohort counts and percentages, not weighted scoring.
- First-class filters should include VLM shape flags, VLM texture flags, defect_count and confidence/review_required, truth columns, and provenance/time columns.
- The top image area should be an intentionally metadata-free, responsive grid for high-density visual review.

**Further Considerations**
1. If you want the filter set to be narrower than the full VLM schema, the best default is to expose all shape/texture booleans and bucketed count fields first, then add the rest after the first review pass.
2. If the report should eventually support reviewer submission, that should be a separate portal step so the static HTML layout can be stabilized first.