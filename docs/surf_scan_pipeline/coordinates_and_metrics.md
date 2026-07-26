# SURF Coordinates and Metrics

## Stage Role

Queries SURF wafer/defect data and maintains canonical coordinates/metrics outputs with seed and incremental modes.

Primary modules:

- [BE_QUERY_FILES/surf_scan_coordinates.py](../../BE_QUERY_FILES/surf_scan_coordinates.py)
- [BE_QUERY_FILES/surf_scan_seed.py](../../BE_QUERY_FILES/surf_scan_seed.py)
- [BE_QUERY_FILES/surf_scan_incremental.py](../../BE_QUERY_FILES/surf_scan_incremental.py)

## Current Behavior

- Queries INSP_WAFER_SUMMARY and INSP_DEFECT.
- Optionally queries INSP_ELEMENT for EDX outputs.
- Uses overlap replacement and deterministic dedup precedence in incremental updates.

## Canonical Outputs

- [outputs/surf_scan/SS_COORDINATES.csv](../../outputs/surf_scan/SS_COORDINATES.csv)
- [outputs/surf_scan/SS_METRICS.csv](../../outputs/surf_scan/SS_METRICS.csv)
- [outputs/surf_scan/SS_EDX.csv](../../outputs/surf_scan/SS_EDX.csv)

## Related Derived Outputs

- [outputs/surf_scan/SS_EDX_STACKED.csv](../../outputs/surf_scan/SS_EDX_STACKED.csv)
- [outputs/surf_scan/SS_EDX_STACKED_Y.csv](../../outputs/surf_scan/SS_EDX_STACKED_Y.csv)
- [outputs/surf_scan/SS_ZEROS/SS_ZERO_fraction_by_event_entity_7day.csv](../../outputs/surf_scan/SS_ZEROS/SS_ZERO_fraction_by_event_entity_7day.csv)
- [outputs/surf_scan/SS_ZEROS/SS_ZERO_fraction_by_event_entity_7day_wide.csv](../../outputs/surf_scan/SS_ZEROS/SS_ZERO_fraction_by_event_entity_7day_wide.csv)

## Ad Hoc Query Helper

Use [BE_QUERY_FILES/surf_scan_lightweight_query.py](../../BE_QUERY_FILES/surf_scan_lightweight_query.py) for isolated recipe/step pulls without mutating canonical outputs.
