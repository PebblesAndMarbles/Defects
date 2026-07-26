# SURF Images, Manifest, and Retention

## Stage Role

Manages SURF image selection, retrieval, organization, manifest accumulation, and prune policy.

Primary module:

- [BE_QUERY_FILES/surf_scan_images.py](../../BE_QUERY_FILES/surf_scan_images.py)

Orchestrated via:

- [BE_QUERY_FILES/surf_scan_update.py](../../BE_QUERY_FILES/surf_scan_update.py)

## Current Behavior

- Selects imaged defects from canonical coordinates.
- Queries INSP_WAFER_IMAGE and downloads via SecureFTP.
- Organizes under chamber-oriented image library.
- Accumulates manifest rows in canonical image manifest CSV.
- Runs 60-day prune behavior based on manifest inspection time, with fallback behavior for untracked files.

## Outputs

- [images/surf_scan](../../images/surf_scan)
- [outputs/surf_scan/SS_EDX_IMAGES.csv](../../outputs/surf_scan/SS_EDX_IMAGES.csv)

## Operational Nuance

The image stage is intentionally fail-tolerant for continuity.

- Partial FTP failures can occur while the overall pipeline still completes.
- Monitoring should track failed transfer counts and source-not-found indicators.
