# SURF ELWC RF Counters

## Contract

Production SURF outputs enforce RF-only counters:

- FULLPM_RF
- MINIPM_RF

Legacy non-RF counters are excluded from production schema:

- FULLPM
- MINIPM
- CNTR_SS

## Stage/Apply Architecture

Primary modules:

- [BE_QUERY_FILES/surf_scan_elwc_pm_stage_backfill.py](../../BE_QUERY_FILES/surf_scan_elwc_pm_stage_backfill.py)
- [BE_QUERY_FILES/surf_scan_elwc_pm_pilot.py](../../BE_QUERY_FILES/surf_scan_elwc_pm_pilot.py)
- [BE_QUERY_FILES/surf_scan_update.py](../../BE_QUERY_FILES/surf_scan_update.py)

Two-phase model:

1. Build staged ELWC-attached RF values in scoped windows.
2. Apply staged RF values into production coordinates/metrics with preservation behavior outside stage scope.

## Production Outputs Updated by Apply

- [outputs/surf_scan/SS_METRICS.csv](../../outputs/surf_scan/SS_METRICS.csv)
- [outputs/surf_scan/SS_COORDINATES.csv](../../outputs/surf_scan/SS_COORDINATES.csv)

## Known Rollout Lessons Captured

- Fallback assignment must remain strict one-to-one to avoid ndarray assignment failures.
- Stage/apply merges should namespace/drop stale columns to avoid collision artifacts.
- Apply behavior must preserve existing historical RF values when stage data is missing outside active scope.
- Legacy nearest-only backfill tools should remain retired for production use.

