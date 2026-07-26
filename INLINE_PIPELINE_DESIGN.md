# BE Defect Pipeline Design

Design index: [DESIGN_INDEX.md](DESIGN_INDEX.md)

## Purpose

This document describes the current design of the BE inline defect pipeline, the decisions made during consolidation, and the remaining work before the pipeline should be treated as production-ready.

The current intent is:

1. Use JMP JSL jobs to pull recent raw layer-level defect data.
2. Use Python to consolidate those raw layer files into a wafer-level metrics table.
3. Extend a defect-coordinate table from the wafer-level table using a bounded overlap window.
4. Maintain and update defect images using the coordinate table and image manifest.
5. Extend a rolling fleet benchmark CSV from the current wafer-level table.

The desired operator workflow is: run the 10-day JSL inputs first, then trigger one Python update entry point.

## Document Scope and Tiering

This document is the primary inline architecture and operations reference (Tier 2) and should remain concise enough for day-to-day use.

1. Keep core runtime topology, contracts, operator flow, and readiness checkpoints here.
2. Keep feature-specific deep context in [docs/inline_pipeline/README.md](docs/inline_pipeline/README.md) and its linked topic files (Tier 3 notes).
3. Keep SURF-specific design details in [SURF_SCAN_PIPELINE_DESIGN.md](SURF_SCAN_PIPELINE_DESIGN.md) and [docs/surf_scan_pipeline/README.md](docs/surf_scan_pipeline/README.md).

## Current Runtime Contract

- Required Python interpreter:
  `c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe`
- Workspace root:
  `\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE`
- Manual pre-step:
  refresh the raw JSL output files before invoking the Python orchestrator.

The orchestrator now enforces raw-input freshness:

- it validates the two JSL CSV inputs exist
- it rejects stale inputs older than 7 days
- it fails fast with an explicit runtime error if freshness checks fail

## High-Level Design Choices

### 1. Keep JMP JSL as the raw-data acquisition boundary

The JSL layer is still the correct place to acquire the raw defect data because it depends on an existing company plugin and associated business logic. Re-implementing or reverse-engineering that logic was intentionally avoided.

Implication:

- The Python pipeline begins after the JSL outputs are written.
- JSL scheduling, lookback windows, and plugin-specific options remain manual/configured outside Python.

### 2. Use one shared Python-side path configuration

The original code path had independent hard-coded network paths spread across multiple scripts. That made integration fragile and migration difficult.

This was consolidated into:

- [BE_QUERY_FILES/pipeline_config.py](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\pipeline_config.py)

That module now owns:

- workspace-relative output locations
- artifact manifest locations
- image destination root
- merged raw-source locations
- legacy image-source awareness for migration
- future root override capability via environment variables

### 3. Separate source scripts from generated artifacts

Generated outputs now live under a structured layout:

- `outputs/wafer`
- `outputs/defects`
- `outputs/benchmarks`
- `images/defects`
- `artifacts`

This keeps the code area separate from large generated datasets and makes later migration or scheduled execution less brittle.

### 4. Treat updates as incremental with overlap, not full replacement

The coordinate pipeline and image pipeline are not safe to run as naive append-only or replace-all jobs because recent wafers can be reclassified.

The design therefore uses overlap windows and deduplication precedence:

- recent data is reprocessed
- newer rows win when keys collide
- image metadata is accumulated via a manifest
- reclassified image files can be retired and replaced

### 5. Use orchestrated sequencing after JSL refresh

The desired operational direction is a single update command after the JSL refresh step. That is now implemented in:

- [BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py)

The orchestrator currently runs:

1. wafer update
2. defect coordinates update
3. image manifest sync + retention prune + inventory append
4. benchmark extension

## Current File and Module Roles

### Raw JSL Inputs

- [BE_QUERY_FILES/8M5CL_NCDD.jsl](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M5CL_NCDD.jsl)
- [BE_QUERY_FILES/8M6CL_NCDD.jsl](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M6CL_NCDD.jsl)

These produce the raw layer-level source CSVs that feed the Python pipeline.

### Shared Path and Layout Configuration

- [BE_QUERY_FILES/pipeline_config.py](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\pipeline_config.py)

This is the authoritative source for Python-side artifact locations.

### Wafer-Level Processor

- [BE_QUERY_FILES/modular_processor/main.py](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\modular_processor\main.py)
- [BE_QUERY_FILES/modular_processor/core/config.py](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\modular_processor\core\config.py)
- [BE_QUERY_FILES/modular_processor/processors/defect_processor.py](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\modular_processor\processors\defect_processor.py)

This stage:

- loads the merged layer-level JSL outputs
- applies rename and cleanup logic
- derives wafer-level defect metrics
- currently runs with most optional enrichment processors disabled in the update path

Important current design detail:

- The wafer output is now accumulated rather than blindly overwritten, because the raw JSL refresh window is smaller than the full retained wafer table.

### Defect Coordinate and Image Pipeline

- [BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py)

This stage:

- reads the current wafer-level extended CSV
- restricts queries to a recent overlap window
- resolves wafer inspections in UDB
- retrieves defect coordinate rows plus selected source metadata intended for downstream VLM analysis: SIZE_X, SIZE_Y, SIZE_D, AREA, MANUAL_OPTICAL_CLASS
- accumulates those rows into the consolidated defect-coordinate CSV
- optionally manages image metadata, downloads, reorganization, and cleanup

Current metadata-selection note:

- `SIZE_Z` was removed from the production CSV and query pipeline because observed values were effectively all zero in the reviewed data.
- `ROUGH_BIN_CLASS` was removed from the production CSV and query pipeline for the same reason.
- These fields are source-system defect metadata used as candidate inputs to a future VLM-assisted workflow; they are not outputs produced by a VLM stage in the current pipeline.
- Current recent image-manifest validation is acceptable for Alloy-side experimentation: 1232 recent coordinate rows with `IMAGE_COUNT > 0`, 1231 matched manifest rows, 1 missing row, 99.92% coverage.
- Historical image-manifest sparsity in enrichment columns is largely explained by inventory-only rows reconstructed from on-disk files rather than fresh coordinate joins.

### Benchmark Extension

- [BE_QUERY_FILES/modular_processor/EXTEND_BENCHMARK.py](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\modular_processor\EXTEND_BENCHMARK.py)
- [BE_QUERY_FILES/modular_processor/TIME_BIN_AGGREGATOR.py](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\modular_processor\TIME_BIN_AGGREGATOR.py)

This stage:

- uses the current wafer-level table as defect input
- derives any benchmark-only helper columns such as DEVICE, ZERO flags, and scan counts
- extends an existing fleet benchmark file from the latest completed cutoff

Important current design detail:

- The benchmark seed is no longer hard-coded to an obsolete February file.
- A seed can be explicitly overridden with `BE_BENCHMARK_SEED_PATH`.
- Otherwise the extender chooses the latest prior benchmark file in `outputs/benchmarks`.

### Orchestrator

- [BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py)

This is the intended operator entry point after the JSL inputs are refreshed.

### Image Manifest Sync and Prune Utility

- [BE_QUERY_FILES/reconcile_prune_images.py](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\reconcile_prune_images.py)

This utility is now called by the orchestrator on every run. It performs:

- manifest path reconciliation/backfill
- optional rename-to-expected-path when uniquely resolvable
- 60-day retention pruning
- inventory append so every on-disk image is represented in the manifest

## Current Output Layout

### Wafer Output

- [outputs/wafer/8M5CL_8M6CL_EXTENDED.csv](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED.csv)

This should be treated as the authoritative consolidated wafer-level output going forward.

### Defect Coordinate Output

- [outputs/defects/DEFECT_COORDINATES_EXTENDED.csv](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED.csv)

### Benchmark Outputs

- files in [outputs/benchmarks](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\benchmarks)

### Images

- [images/defects](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\defects)

Legacy image content was merged from:

- `\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE_60day\BE_60day_QUERY_FILES\DefectImages`

### Artifacts and Manifests

- [artifacts/main_run_artifacts.json](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\artifacts\main_run_artifacts.json)
- [artifacts/defect_coordinates_artifacts.json](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\artifacts\defect_coordinates_artifacts.json)
- [artifacts/benchmark_artifacts.json](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\artifacts\benchmark_artifacts.json)
- [artifacts/update_run_artifacts.json](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\artifacts\update_run_artifacts.json)

## Current Operational Flow

### Step 1. Run JSL refresh manually

The current operating model is still manual at the JSL boundary.

Expected raw inputs after JSL completes:

- [BE_QUERY_FILES/8M5CL_NCDD.csv](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M5CL_NCDD.csv)
- [BE_QUERY_FILES/8M6CL_NCDD.csv](\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M6CL_NCDD.csv)

### Step 2. Run Python update orchestrator

Current command:

```powershell
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py"
```

### Step 3. Inspect outputs and manifests

Expected result:

- wafer table updated
- coordinate table updated
- image manifest reconciled and appended to current on-disk inventory
- old image files pruned per retention policy
- benchmark extended
- manifests written to `artifacts`

## Current Configuration Choices

### Lookback and overlap assumptions

- JSL refresh target: 10-day lookback
- JSL input freshness gate in orchestrator: 7 days max age
- defect-coordinate overlap: 10 days
- image retention target: 60 days

These values were selected to keep database load bounded while still allowing reclassification updates to replace recent prior results.

### Optional processors disabled in main update path

In the current orchestrated run, most enrichment processors in the wafer pipeline are disabled. That was a deliberate choice to stabilize the core update path first.

Currently disabled in the default update flow:

- ELWC lookbacks
- ELWC2
- leak rate
- dry pump
- leak-by
- SPC monitor
- defect trends
- recoat

That means the current productionization effort is centered on the reliable baseline wafer table and downstream coordinate and benchmark propagation, not on all historical enrichments.

### Benchmark seed behavior

The benchmark extender now supports two modes:

1. explicit seed override via `BE_BENCHMARK_SEED_PATH`
2. automatic latest-prior-seed selection in `outputs/benchmarks`

This is important because earlier missing benchmark periods were caused by extending from an out-of-date historical seed file.

## Detailed Context Locations

Feature-specific implementation detail is intentionally kept outside this Tier 2 document.

Use [docs/inline_pipeline/README.md](docs/inline_pipeline/README.md) as the routing index, then go directly to:

1. runtime contract and path ownership:
  - [docs/inline_pipeline/runtime_contract.md](docs/inline_pipeline/runtime_contract.md)
2. wafer stage behavior and risks:
  - [docs/inline_pipeline/wafer_stage.md](docs/inline_pipeline/wafer_stage.md)
3. coordinate/image behavior and retention policy:
  - [docs/inline_pipeline/coordinates_and_images.md](docs/inline_pipeline/coordinates_and_images.md)
4. benchmark extension and continuity checks:
  - [docs/inline_pipeline/benchmark_stage.md](docs/inline_pipeline/benchmark_stage.md)
5. operations and production hardening tasks:
  - [docs/inline_pipeline/operations_and_hardening.md](docs/inline_pipeline/operations_and_hardening.md)

## Active Risks Snapshot

The key production risks are currently:

1. transitional legacy seed dependencies for wafer and coordinate accumulation
2. incomplete automated continuity/quality validation post-run
3. manual JSL pre-refresh boundary and image runtime dependency observability

See [docs/inline_pipeline/operations_and_hardening.md](docs/inline_pipeline/operations_and_hardening.md) for full actions and ownership routing.

## Tier 2 Readiness Checklist

Before treating this pipeline as production-ready:

1. JSL refreshes pass orchestrator freshness checks consistently.
2. End-to-end orchestrator completes reliably with expected artifacts.
3. Wafer and coordinate outputs are validated and legacy seed bridges are retired.
4. Benchmark continuity checks are automated and passing.
5. Image retention and manifest reconciliation behavior are monitored and stable.
6. Scheduled runbook/launcher is documented with explicit interpreter and workspace contract.

## Summary

Inline pipeline structure is now stable and operator-oriented at Tier 2.

Use this file for contract and flow, and use [docs/inline_pipeline/README.md](docs/inline_pipeline/README.md) for feature-depth editing paths.