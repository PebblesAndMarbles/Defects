# BE SURF Scan Pipeline Design

Design index: [DESIGN_INDEX.md](DESIGN_INDEX.md)

## Purpose

This document describes the current design of the BE SURF scan pipeline, the consolidation decisions made so far, and the remaining considerations before long-term production operation.

The current intent is:

1. Query SURF scan wafer and defect data directly from UDB (no JMP plugin dependency for core metrics/coordinates).
2. Maintain a consolidated SURF coordinates CSV and SURF metrics CSV via seed and incremental modes.
3. Build stacked EDX outputs from the canonical coordinates output.
4. Download and organize SURF image subsets tied to EDX-imaged defects.
5. Enforce 60-day retention for SURF images in the network image library.
6. Produce a zero-timebin summary for downstream monitoring.

The desired operator workflow is:

1. Run one-time seed/backfill when initializing or recovering historical state.
2. Schedule a daily incremental run (7-day overlap window) for steady-state operation.

Feature-level SURF design details are maintained in:

- [docs/surf_scan_pipeline/README.md](docs/surf_scan_pipeline/README.md)

## Document Scope and Tiering

This document is the primary SURF architecture/operations reference (Tier 2) and should stay concise for day-to-day use.

1. Keep core runtime topology, contracts, and operator commands here.
2. Keep feature-specific implementation details in [docs/surf_scan_pipeline/README.md](docs/surf_scan_pipeline/README.md) and linked topic docs (Tier 3).
3. Keep inline-defect design content in [INLINE_PIPELINE_DESIGN.md](INLINE_PIPELINE_DESIGN.md); do not merge inline and SURF implementation detail into one document.

## Current Runtime Contract

- Required Python interpreter:
  c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe
- Workspace root:
  \\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE
- Daily scheduled entry point:
  BE_QUERY_FILES/surf_scan_daily.py

## High-Level Design Choices

### 1. DB-first SURF data acquisition boundary

Unlike inline defect processing (which depends on JSL plugin output as the raw boundary), SURF scan coordinates and wafer-level metrics are queried directly from UDB.

Implication:

- No JSL freshness gate is required for the SURF core pipeline.
- Scheduler reliability depends on DB and FTP availability rather than JSL pre-refresh timing.

### 2. Two lifecycle modes: seed and incremental

The pipeline supports:

- Seed/backfill mode for initialization and historical recovery.
- Incremental mode with a 7-day overlap window for daily runs.

Incremental accumulation uses overlap replacement and deterministic dedup precedence:

- preserve rows older than the overlap cutoff,
- replace rows within the overlap window with fresh query results,
- deduplicate by business keys with newest rows preferred.

### 3. Consolidated in-repo implementation

The SURF orchestrator no longer loads runtime modules from BE_60day. The current execution path uses local modules inside BE_QUERY_FILES.

### 4. Shared SURF configuration module

Shared SURF defaults were centralized into a dedicated configuration module so lookbacks, chamber list, SEG recipe sequence, and image thresholds are managed in one place.

### 5. Image retention tied to manifest inspection time

Image pruning is designed to honor the 60-day retention policy primarily via manifest INSPECTION_TIME (with filesystem mtime fallback for untracked files).

## Current File and Module Roles

### Shared Path and Artifact Configuration

- BE_QUERY_FILES/pipeline_config.py

Owns canonical workspace paths for outputs, images, and artifacts.

### Shared SURF Configuration

- BE_QUERY_FILES/surf_scan_config.py

Owns SURF defaults, including:

- seed and incremental lookbacks,
- image retention days,
- chamber filters,
- SS and SEG layer filters,
- SEG recipe sequence,
- image selection parameters.

### SURF Coordinates and Metrics Query Layer

- BE_QUERY_FILES/surf_scan_coordinates.py

This stage:

1. Queries INSP_WAFER_SUMMARY for SS and optional SEG events.
2. Queries INSP_DEFECT for adder defect coordinates.
3. Optionally queries INSP_ELEMENT for EDX columns.
4. Writes/accumulates:
   - outputs/surf_scan/SS_COORDINATES.csv
   - outputs/surf_scan/SS_METRICS.csv
   - outputs/surf_scan/SS_EDX.csv

### Ad Hoc Lightweight Recipe/Step Query

- BE_QUERY_FILES/surf_scan_lightweight_query.py

Use this helper when you need a fast, isolated pull for a specific recipe + step layer window without modifying production SS_COORDINATES/SS_METRICS.

Behavior:

1. Queries UDB.INSP_WAFER_SUMMARY for the requested lookback window, step layer, and optional lot/process/inspect equipment filters.
2. Auto-discovers a recipe-like summary column (RECIPE/SEQ_RECIPE/PROCESS_RECIPE/LOT_RECIPE/WAFER_RECIPE) and applies an exact recipe filter when provided.
3. Queries UDB.INSP_DEFECT for adder coordinates tied to the matched wafer inspections.
4. Writes standalone ad hoc outputs under outputs/surf_scan/ad_hoc:
  - *_METRICS.csv
  - *_COORDINATES.csv
  - *_SUMMARY.json

Example for 7-day request:

```powershell
c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe BE_QUERY_FILES/surf_scan_lightweight_query.py `
  --lookback-days 7 `
  --step-layer-id 6OX450GTO_M025_PST `
  --recipe 6OX450GTO_SAAA_M025_PST `
  --process-equip GTO111_PC1 `
  --inspect-equip UDE415 `
  --lot-id D619TNV0
```

### PM Counter Enrichment (Recurring)

- Primary production implementation:
  - BE_QUERY_FILES/surf_scan_elwc_pm_stage_backfill.py
  - BE_QUERY_FILES/surf_scan_elwc_pm_pilot.py (ELWC attach/fallback core)
- Counter source DB: D1D_PROD_XEUS_GAJT
- Counter source table: F_ENTITYATTRIBUTEHIST

Production counter contract:

- FULLPM_RF
- MINIPM_RF

Current recurring enrichment design:

1. Build staged ELWC-attached metrics in chunked windows keyed by SURF events.
2. Attach PM snapshots to ELWC events using backward/nearest/fallback semantics.
3. Apply staged values into production CSVs with preservation behavior for rows outside current stage scope.
4. Remove ELWC/STAGE_ELWC diagnostics from production outputs after apply.

Output files updated by apply:

- outputs/surf_scan/SS_METRICS.csv
- outputs/surf_scan/SS_COORDINATES.csv

Operational note:

- PM counters are sourced from XEUS history (Entity Attribute History), not from D1D_PROD_YAS_1278 dictionary-visible PM columns.
- surf_scan_coordinates.py still contains nearest-counter logic used by standalone/query-path generation, but recurring production refresh is driven by the ELWC stage/apply step in surf_scan_update.py.

### SURF Image Query and Organization Layer

- BE_QUERY_FILES/surf_scan_images.py

This stage:

1. Reads canonical SURF coordinates.
2. Selects imaged defects by IMAGE_COUNT criteria.
3. Queries INSP_WAFER_IMAGE for image filespecs.
4. Downloads via SecureFTP.
5. Organizes images into chamber subfolders.
6. Optionally annotates images with context and EDX summary.
7. Accumulates manifest at outputs/surf_scan/SS_EDX_IMAGES.csv.

### SURF Orchestrator

- BE_QUERY_FILES/surf_scan_update.py

This is the main orchestrator and currently runs steps in this order:

1. coordinates
2. elwc_rf_refresh
3. stacked_edx
4. zero_timebin
5. images (optional)
6. image_prune

It also writes an artifact manifest and summary JSON in artifacts.

### Mode-Specific Entrypoints

- BE_QUERY_FILES/surf_scan_seed.py
- BE_QUERY_FILES/surf_scan_incremental.py
- BE_QUERY_FILES/surf_scan_daily.py
- BE_QUERY_FILES/surf_scan_elwc_pm_stage_backfill.py (stage/apply backfill utility)

Daily entrypoint behavior:

- forces incremental mode,
- runs image stage by default,
- runs prune with standard retention behavior.

### Comparison Utility

- BE_QUERY_FILES/compare_surf_coordinates.py

Used for rigorous baseline vs consolidated output comparison.

## Current Output Layout

### Core SURF Outputs

- outputs/surf_scan/SS_COORDINATES.csv
- outputs/surf_scan/SS_METRICS.csv
- outputs/surf_scan/SS_EDX.csv
- outputs/surf_scan/SS_EDX_STACKED.csv
- outputs/surf_scan/SS_EDX_STACKED_Y.csv

### Image Outputs

- images/surf_scan
- outputs/surf_scan/SS_EDX_IMAGES.csv

### Timebin Outputs

- outputs/surf_scan/SS_ZEROS/SS_ZERO_fraction_by_event_entity_7day.csv
- outputs/surf_scan/SS_ZEROS/SS_ZERO_fraction_by_event_entity_7day_wide.csv

### Artifacts

- artifacts/surf_scan_run_artifacts.json
- artifacts/surf_scan_run_summary.json

## Current Operational Flow

### One-time or ad hoc backfill

Run seed with default seed lookback:

```powershell
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\surf_scan_seed.py"
```

Optional explicit lookback override (example):

```powershell
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\surf_scan_seed.py" --lookback-days 760
```

### Daily incremental run

```powershell
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\surf_scan_daily.py"
```

### One-time ELWC RF stage/apply backfill on existing SURF CSVs

```powershell
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\surf_scan_elwc_pm_stage_backfill.py" --lookback-days 270 --chunk-events 100 --apply-production
```

Backfill artifact output:

- artifacts/surf_scan_elwc_pm_stage_full_summary.json
- artifacts/surf_scan_elwc_pm_stage_apply_summary.json

## Current Defaults

From surf_scan_config:

- DEFAULT_SEED_LOOKBACK_DAYS = 760
- DEFAULT_INCREMENTAL_LOOKBACK_DAYS = 7
- DEFAULT_IMAGE_RETENTION_DAYS = 60
- DEFAULT_IMAGE_QUERY_LOOKBACK_DAYS = 90
- IMAGE_COUNT_MIN = 16
- DEFAULT_OVER16_DEFECTS = 20

## Detailed Context Locations

Feature-specific implementation detail is intentionally kept outside this Tier 2 document.

Use [docs/surf_scan_pipeline/README.md](docs/surf_scan_pipeline/README.md) as the routing index, then go directly to:

1. Runtime and defaults: [docs/surf_scan_pipeline/runtime_contract.md](docs/surf_scan_pipeline/runtime_contract.md)
2. Coordinates and metrics lifecycle: [docs/surf_scan_pipeline/coordinates_and_metrics.md](docs/surf_scan_pipeline/coordinates_and_metrics.md)
3. ELWC RF counter contract and stage/apply behavior: [docs/surf_scan_pipeline/elwc_rf_counters.md](docs/surf_scan_pipeline/elwc_rf_counters.md)
4. Image retrieval, manifest, and retention behavior: [docs/surf_scan_pipeline/images_and_retention.md](docs/surf_scan_pipeline/images_and_retention.md)
5. Operations, risks, and hardening tasks: [docs/surf_scan_pipeline/operations_and_hardening.md](docs/surf_scan_pipeline/operations_and_hardening.md)

RF counter context is maintained in [docs/surf_scan_pipeline/elwc_rf_counters.md](docs/surf_scan_pipeline/elwc_rf_counters.md).

## Active Risks Snapshot

The key production risks are currently:

1. external DB and FTP dependency volatility
2. partial image-transfer gaps in fail-tolerant daily runs
3. schema drift risk if RF-only counter policy is not audited continuously

## Tier 2 Readiness Checklist

Before treating SURF pipeline operation as production-stable:

1. Daily scheduler runs complete with expected artifacts and stable step durations.
2. Coordinates/metrics/derived outputs are updated with expected overlap and dedup behavior.
3. RF-only counter contract remains enforced in production outputs.
4. Image transfer failure indicators and prune outcomes are monitored.
5. Rollback procedure for canonical outputs and manifests is documented and testable.

## Summary

SURF pipeline architecture and operations are summarized here at Tier 2.

Use this file for runtime contract and operator flow, and use [docs/surf_scan_pipeline/README.md](docs/surf_scan_pipeline/README.md) for feature-depth editing paths.
