# SURF Operations and Hardening

## Operator Flow

1. Run one-time seed/backfill when initializing or repairing historical state.
2. Run daily incremental scheduler entrypoint for steady-state.
3. Review run summary/artifacts and monitor quality signals.

## Primary Commands

- Daily incremental: [BE_QUERY_FILES/surf_scan_daily.py](../../BE_QUERY_FILES/surf_scan_daily.py)
- Seed/backfill: [BE_QUERY_FILES/surf_scan_seed.py](../../BE_QUERY_FILES/surf_scan_seed.py)
- ELWC RF stage/apply backfill utility: [BE_QUERY_FILES/surf_scan_elwc_pm_stage_backfill.py](../../BE_QUERY_FILES/surf_scan_elwc_pm_stage_backfill.py)

## Artifacts

- [artifacts/surf_scan_run_artifacts.json](../../artifacts/surf_scan_run_artifacts.json)
- [artifacts/surf_scan_run_summary.json](../../artifacts/surf_scan_run_summary.json)
- [artifacts/surf_scan_elwc_pm_stage_full_summary.json](../../artifacts/surf_scan_elwc_pm_stage_full_summary.json)
- [artifacts/surf_scan_elwc_pm_stage_apply_summary.json](../../artifacts/surf_scan_elwc_pm_stage_apply_summary.json)

## Readiness and Monitoring Focus

1. Confirm daily scheduler health and step durations.
2. Track coordinates/metrics row deltas and schema contract.
3. Track FTP failure indicators and source-not-found image signals.
4. Verify prune behavior and retention policy outcomes.
5. Keep rollback strategy for restoring prior canonical outputs/manifests.

## Current Top Risks

1. External DB and FTP dependencies remain primary operational risk.
2. Fail-tolerant image behavior can hide partial download gaps if transfer metrics are not monitored.
3. Schema drift risk exists if RF-only counter contract is not audited.
