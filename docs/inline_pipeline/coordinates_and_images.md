# Inline Coordinates and Images Stage

## Stage Role

Coordinates stage expands wafer-level output into defect-level coordinate rows, then supports image-manifest and image-library maintenance.

Primary module:

- [BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py](../../BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py)

Related utility:

- [BE_QUERY_FILES/reconcile_prune_images.py](../../BE_QUERY_FILES/reconcile_prune_images.py)

## Current Behavior

- Reads current wafer output.
- Uses overlap window for bounded reprocessing.
- Queries defect coordinates and selected metadata fields.
- Accumulates canonical coordinate CSV with deterministic dedup precedence.

## Outputs

- [outputs/defects/DEFECT_COORDINATES_EXTENDED.csv](../../outputs/defects/DEFECT_COORDINATES_EXTENDED.csv)
- [images/defects](../../images/defects)

## Manifest and Retention

- Manifest reconciliation and inventory append run per orchestrator execution.
- Retention target is 60 days.
- Runtime image acquisition is intentionally fail-open if external image runtime dependencies are unavailable.

## Current Metadata Policy

- SIZE_Z removed from production coordinate flow.
- ROUGH_BIN_CLASS removed from production coordinate flow.
- Current source metadata selection retains fields intended for downstream VLM experimentation.
