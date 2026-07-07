# SURF Scan Manifest Discrepancy Handoff

## Purpose
This document captures the discrepancy we observed between the SURF image manifest and the actual files present in chamber image folders. It is intended as handoff context for a troubleshooting/debugging agent.

## Affected manifest
- Source manifest: outputs/surf_scan/SS_EDX_IMAGES.csv
- Primary symptom area: SURF scan chamber image libraries under images/surf_scan/<PRIMARY_EQUIP>

## What we observed
We confirmed multiple mismatch modes between the manifest and the actual chamber folders.

### 1. Stale manifest paths
Some manifest rows contained LOCAL_IMAGE_FILE values that no longer existed on disk.

Concrete example:
- The path below appeared in report output as a valid link but the file did not exist when checked:
- \orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\surf_scan\AME419_PM3\260324_1742_D344TD1_217_10_3.jpg

Result:
- Broken clickable links in HTML output when the report trusted manifest paths directly.

Mitigation implemented in report workflow:
- Selected report scripts now validate image paths before emitting links, or render the cell as missing.

### 2. Event-mixing collisions from reused wafers
We confirmed that the same wafer/defect identifiers can recur across repeated test-wafer runs.

User context that explains the pattern:
- The same lots/wafers are reused for repeated test wafer events.
- A wafer can run a SURF scan, go to regen, and later be used again.

Why this matters:
- Joining images only on WAFER_KEY + DEFECT_ID (+ IMAGE_ID) is unsafe.
- That looser join can mix image slots from different inspection events and even different chambers into the same HTML row.

Concrete case we investigated:
- A row incorrectly combined images from:
  - AME411_PM4
  - AME409_PM2
- This was traced back to repeated wafer reuse and insufficient join context.

Mitigation implemented in report workflow:
- Event-aware join keys were introduced for the YPO defect report.
- Safer join dimensions used there:
  - WAFER_KEY
  - DEFECT_ID
  - IMAGE_ID
  - INSPECTION_TIME
  - WAFER_ID
  - PRIMARY_EQUIP

### 3. Manifest incompleteness despite on-disk files being present
We confirmed cases where files existed in the correct chamber folder but were not represented in the manifest rows for that chamber/event.

Most important confirmed case:
- Chamber report context: AME401_PM1
- Event token: 260609_1317
- Wafer: FK6EW656JKB5
- Defect: 11

Observed problem:
- The following files existed on disk in images/surf_scan/AME401_PM1:
  - 260609_1317_D344TD2_656_11_4.jpg
  - 260609_1317_D344TD2_656_11_8.jpg
- But the AME401_PM1 manifest subset only exposed IMAGE_ID 2 and 3 for that wafer/defect/event.
- Meanwhile, IMAGE_ID 4 and 8 for the same wafer/defect stem were still associated in the manifest with an older AME409_PM2 context.

Result:
- A manifest-only chamber report showed those 4/8 cells as missing even though the files were present in the AME401_PM1 folder.

Mitigation implemented in report workflow:
- For chamber/event reports, row scoping remains manifest-driven for wafer/event selection.
- But image slot filling was switched to folder inventory for the verified wafer/event subset, rather than trusting the manifest to enumerate all slots.

## Evidence collected during report development

### A. AME401_PM1, event token 260609_1317
Manifest-only version:
- Verified manifest rows: 47
- Rendered defect rows: 14
- Files expected from folder review: 68 files, 17 complete rows

Inventory-backed corrected version:
- Inventory files used: 68
- Rendered defect rows: 17

This confirmed that folder inventory contained more valid same-event images than the manifest subset exposed for that chamber.

### B. AME401_PM1, event token 260611_0547
- Verified manifest rows: 79
- Inventory files used: 100
- Wafers found: 9
- Rendered defect rows: 25

Interpretation:
- The chamber folder contained additional valid same-event files beyond direct manifest coverage.
- This reinforced the need for manifest-verified wafer/event scoping plus inventory-backed slot fill.

### C. AME403_PM2, event token 260610_1244
- Manifest rows in scope: 156
- Inventory files used: 192
- Rendered defect rows: 48

Interpretation:
- Same pattern: direct event folder inventory exceeded manifest-listed rows.

## Current working assumptions
1. SS_EDX_IMAGES.csv is useful for wafer/event scoping and metadata, but not always complete enough to enumerate every image file slot present on disk.
2. LOCAL_IMAGE_FILE can become stale relative to folder reality.
3. WAFER reuse across inspections means any join that ignores inspection context is unsafe.
4. Folder filenames themselves contain reliable event/lot/wafer-short/defect/image-id structure that can be used to recover complete row image sets.

## Filename pattern being used operationally
Current chamber report workflow parses filenames with this pattern:

```text
YYMMDD_HHMM_<LOT7>_<waferShort>_<defectId>_<imageId>.jpg
```

Example:

```text
260609_1317_D344TD2_656_11_4.jpg
```

Parsed fields:
- event token: 260609_1317
- lot token: D344TD2
- wafer short: 656
- defect id: 11
- image id: 4

## Report logic that currently works around the discrepancy
Current chamber/event reports use this two-stage strategy:

1. Manifest verification stage
- Filter SS_EDX_IMAGES.csv by PRIMARY_EQUIP
- Optionally filter by event token in LOCAL_IMAGE_FILE
- Require LOCAL_IMAGE_FILE to exist
- Require file modified date to match the target date
- Use surviving rows only to identify which wafers/events are in scope

2. Inventory-backed rendering stage
- Enumerate the chamber folder directly
- Parse filenames for the target event token
- Match files back to the verified wafer set using wafer-short token
- Group images into defect rows by wafer/event/defect
- Populate the four report columns using image IDs [8, 2, 3, 4]

This workflow is implemented in:
- rollups/AME401_PM1_RECENT_PMEASURED_REPORT.py

## Questions for a troubleshooting agent
1. Why are some valid chamber files missing from SS_EDX_IMAGES.csv for the same chamber/event while present on disk?
2. Are later image-organize or reconcile steps rewriting LOCAL_IMAGE_FILE ownership across chambers/events?
3. Does the manifest merge/dedup logic unintentionally preserve older rows for image IDs 4/8 while newer chamber/event rows only contribute 2/3?
4. Is there a known difference in how IMAGE_ID 2/3 versus 4/8 are queried or persisted?
5. Should the production manifest be reconciled from folder inventory, or should the image query stage be fixed upstream?

## Suggested troubleshooting starting points
- Compare image query/organize behavior in:
  - BE_QUERY_FILES/surf_scan_images.py
- Review any reconcile/prune logic that can rewrite or preserve LOCAL_IMAGE_FILE:
  - BE_QUERY_FILES/reconcile_prune_images.py
- Check whether image IDs 4 and 8 are dropped or mis-attributed during dedup/merge paths.
- Compare one problematic wafer/event across:
  - raw manifest rows
  - chamber folder inventory
  - any organize/reconcile intermediate outputs

## Known-good outputs that exposed and then worked around the issue
Representative outputs generated during investigation:
- rollups/ypo_defect_image_report_20260605_172242.html
- rollups/ame401_pm1_recent_pmeasured_report_20260609_151922.html
- rollups/ame401_pm1_recent_pmeasured_report_20260609_152735.html
- rollups/ame401_pm1_recent_pmeasured_report_20260611_111141.html
- rollups/ame403_pm2_recent_pmeasured_report_20260611_112618.html

The 20260609_152735 AME401 report was the first corrected inventory-backed version that aligned with the observed 68-file / 17-row expectation.
