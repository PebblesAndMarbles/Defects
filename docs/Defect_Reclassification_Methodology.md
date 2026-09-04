# Defect Reclassification Methodology

## Purpose

This note captures the working methodology for detecting defect reclassification drift in the BE inline pipeline. The intent is to compare the current database classification against the production CSV state for a bounded recent window, with special attention to `BEEP` and `SMALL_PARTICLE`, while preserving the ability to catch later transitions into other classes.

The methodology is designed to support later implementation work across the inline defect flow, not just the coordinates query, but also downstream image burn-in, pruning, and storage behavior.

## Operating Principle

The recurring refresh should treat the database as the current source of truth for a recent lookback window, then compare the live DB classification against the production CSV state that may have been materialized days earlier.

Recommended refresh model:

1. Use a bounded lookback window for the current update cycle.
2. Query the DB for the defect scope of interest, with the class family in scope for the audit stream.
3. Compare DB results against the production coordinates CSV using stable defect keys.
4. Classify differences as `match`, `class_changed`, `manual_optical_disagrees`, `missing_in_db`, or `missing_in_production`.
5. Periodically widen the lookback window to catch late reclassifications that appear after the standard refresh interval.

Operational cadence:

1. Daily cron run: `RECENT_LOOKBACK_DAYS = 10` for the normal bounded refresh.
2. Weekly safety-net run: `DEFECT_COORDINATES_QUERY.py --backfill --backfill-lookback-days 210 --no-images` to revisit older rows and overwrite stale classifications when a late reclassification lands after the coords CSV was first written.
3. The backfill run should be images-off and should execute before manifest reconciliation so downstream path repair uses the latest class state.

For the recurring path, the normal working set is the `BEEP` / `SMALL_PARTICLE` family. The periodic wider sweep is the safety net for delayed class changes.

## Scope Guidance

This approach does not require the full 500-day production CSV to define the audit population. A class-scoped, lookback-bounded DB pull is sufficient for the recurring path because defects that have reclassified out of the `BEEP` / `SMALL_PARTICLE` family are no longer relevant to the normal refresh stream.

The broader sweep should be used only when the team wants to catch late reclassifications or validate that class changes are not being missed outside the standard lookback window.

## Relevant Files

### Core Inline Pipeline

- [INLINE_PIPELINE_DESIGN.md](../INLINE_PIPELINE_DESIGN.md) - pipeline-wide contract, operator flow, and current production readiness context.
- [docs/inline_pipeline/README.md](inline_pipeline/README.md) - entry map for the inline feature-level docs.
- [docs/inline_pipeline/coordinates_and_images.md](inline_pipeline/coordinates_and_images.md) - coordinates accumulation, image manifest reconciliation, and retention behavior.
- [docs/inline_pipeline/operations_and_hardening.md](inline_pipeline/operations_and_hardening.md) - operational checklist and readiness focus areas.
- [docs/inline_pipeline/runtime_contract.md](inline_pipeline/runtime_contract.md) - required interpreter, workspace, and freshness gate.

### Coordinate and Image Implementation

- [BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py](../BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py) - coordinates query, overlap window, defect accumulation, and image-manifest maintenance.
- [BE_QUERY_FILES/reconcile_prune_images.py](../BE_QUERY_FILES/reconcile_prune_images.py) - manifest reconciliation, retention pruning, and inventory append behavior.
- [BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py](../BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py) - orchestrator that sequences wafer, coordinates, image, and benchmark stages.
- [BE_QUERY_FILES/pipeline_config.py](../BE_QUERY_FILES/pipeline_config.py) - canonical path ownership for outputs, artifacts, and images.

### Supporting Audit Utilities

- [BE_QUERY_FILES/compare_defect_coordinates_mismatch.py](../BE_QUERY_FILES/compare_defect_coordinates_mismatch.py) - 14-day mismatch audit scaffold for production vs DB comparison.
- [BE_QUERY_FILES/query_by_class_direct.py](../BE_QUERY_FILES/query_by_class_direct.py) - direct class-based coordinate query helper.

### SURF Cross-Reference

- [SURF_SCAN_PIPELINE_DESIGN.md](../SURF_SCAN_PIPELINE_DESIGN.md) - useful comparison point for how SURF handles DB-first coordinates, incremental overlap, image retention, and periodic seed/backfill behavior.
- [docs/surf_scan_pipeline/README.md](surf_scan_pipeline/README.md) - SURF feature map and stage-level implementation context.

## Implementation Notes

The methodology should remain compatible with future extension into the full inline pipeline design:

1. Coordinate scope and class drift detection.
2. Image burn-in metadata updates for reclassified defects.
3. Image pruning and storage lifecycle changes when a defect moves out of the active family.
4. Future reporting and monitoring that can surface `BEEP` / `SMALL_PARTICLE` transitions as a focused subset of a broader drift audit.

The code and docs should stay aligned with a bounded, class-scoped refresh model for normal operation, while preserving a periodic backfill path for longer lookback validation.