# Raw Image Redownload Plan (Non-Burned Inputs)

## Why this matters
Current Alloy experimentation uses images from the maintained defect image library. These images can include burned-in black-box metadata overlays near the bottom of the frame. For substrate-pattern comprehension and context-aware modeling, raw non-burned images are preferred when available.

## Inline pipeline context
Image acquisition and manifest maintenance currently flow through the coordinates/images stage and reconciliation utility:
- `BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py`
- `BE_QUERY_FILES/reconcile_prune_images.py`

Design references:
- `INLINE_PIPELINE_DESIGN.md`
- `docs/inline_pipeline/coordinates_and_images.md`

## Current practical finding
The active 60-day manifest schema includes `IMAGE_FILESPEC` and local organized paths but may not have explicit raw-source path columns populated in all rows.

## New helper
Use this helper to prepare a redownload request table from the existing 60-day manifest:
- `tools/build_raw_redownload_manifest.py`

### Example command
```powershell
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" tools/build_raw_redownload_manifest.py `
  --input-csv "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv" `
  --output-csv "outputs/phase1_pairsafe/raw_redownload_manifest.csv" `
  --image-ids 2,3 `
  --only-missing-source-path
```

## What the helper outputs
The generated CSV includes request identifiers and source hints:
- `WAFER_KEY`, `INSPECTION_TIME`, `DEFECT_ID`, `IMAGE_ID`
- `IMAGE_SERVER_ID`, `IMAGE_FILESPEC`, `LOCAL_IMAGE_FILE`
- `REQUEST_KEY` for downstream retrieval joins
- `HAS_EXPLICIT_SOURCE_PATH` to flag whether explicit source path fields are present

## Recommended next technical step
Build a downloader that consumes `raw_redownload_manifest.csv` and uses canonical tuple keys (`WAFER_KEY`, `INSPECTION_TIME`, `DEFECT_ID`, `IMAGE_ID`) to query/retrieve non-burned source images through the same runtime-approved path used by the coordinates/image stage.

## Project-stage recommendation for the extended context discussion
Have the extended process-context discussion at the end of Phase 1B (before scaling beyond bounded cohorts and before Phase 2 contract freeze), then lock policy immediately before Phase 2 artifacts are frozen.

This timing ensures:
- enough empirical evidence from pair-safe runs,
- no late schema churn in Phase 2,
- context-aware handling of product/layer/wafer-position variability,
- explicit policy for expected near-center defect localization.
