# SURF Scan Pipeline Feature Docs

This folder is the feature-level context map for the BE SURF scan pipeline.

Primary design document:

- [SURF_SCAN_PIPELINE_DESIGN.md](../../SURF_SCAN_PIPELINE_DESIGN.md)

Use this folder when you are editing one SURF feature and want the smallest relevant context.

## Suggested Editing Path

1. Start with [SURF_SCAN_PIPELINE_DESIGN.md](../../SURF_SCAN_PIPELINE_DESIGN.md) for architecture-level contract and operator flow.
2. Jump to one topic file below for implementation-level detail.
3. Update only the topic file that matches your code change.

## Topic Documents

1. Runtime contract and defaults: [runtime_contract.md](runtime_contract.md)
2. Coordinates, metrics, and accumulation: [coordinates_and_metrics.md](coordinates_and_metrics.md)
3. ELWC RF counters and stage/apply: [elwc_rf_counters.md](elwc_rf_counters.md)
4. Images, manifest, and retention: [images_and_retention.md](images_and_retention.md)
5. Operations and hardening: [operations_and_hardening.md](operations_and_hardening.md)

## Coverage Boundaries

- SURF only: do not duplicate inline-defect implementation details.
- Keep each file focused and short to reduce context size for future edits.
- Keep rollout incident history in focused feature docs, not in Tier 2 summary.

## Ownership and Change Routing

| Change Type | Start Doc | Primary Code Touchpoints |
|---|---|---|
| Scheduler/runtime paths, lookbacks, retention defaults | [runtime_contract.md](runtime_contract.md) | [BE_QUERY_FILES/surf_scan_config.py](../../BE_QUERY_FILES/surf_scan_config.py), [BE_QUERY_FILES/surf_scan_daily.py](../../BE_QUERY_FILES/surf_scan_daily.py) |
| Query scope, dedup behavior, seed/incremental accumulation | [coordinates_and_metrics.md](coordinates_and_metrics.md) | [BE_QUERY_FILES/surf_scan_coordinates.py](../../BE_QUERY_FILES/surf_scan_coordinates.py), [BE_QUERY_FILES/surf_scan_seed.py](../../BE_QUERY_FILES/surf_scan_seed.py), [BE_QUERY_FILES/surf_scan_incremental.py](../../BE_QUERY_FILES/surf_scan_incremental.py) |
| RF-only counter contract, stage/apply merge semantics | [elwc_rf_counters.md](elwc_rf_counters.md) | [BE_QUERY_FILES/surf_scan_elwc_pm_stage_backfill.py](../../BE_QUERY_FILES/surf_scan_elwc_pm_stage_backfill.py), [BE_QUERY_FILES/surf_scan_elwc_pm_pilot.py](../../BE_QUERY_FILES/surf_scan_elwc_pm_pilot.py), [BE_QUERY_FILES/surf_scan_update.py](../../BE_QUERY_FILES/surf_scan_update.py) |
| Image query/download, manifest quality, prune behavior | [images_and_retention.md](images_and_retention.md) | [BE_QUERY_FILES/surf_scan_images.py](../../BE_QUERY_FILES/surf_scan_images.py), [BE_QUERY_FILES/surf_scan_update.py](../../BE_QUERY_FILES/surf_scan_update.py) |
| Readiness checks, monitoring, rollback, audits | [operations_and_hardening.md](operations_and_hardening.md) | [artifacts/surf_scan_run_summary.json](../../artifacts/surf_scan_run_summary.json), [artifacts/surf_scan_run_artifacts.json](../../artifacts/surf_scan_run_artifacts.json) |
