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
- retrieves defect coordinate rows
- accumulates those rows into the consolidated defect-coordinate CSV
- optionally manages image metadata, downloads, reorganization, and cleanup

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

## Validation Work Already Done

The following improvements have already been validated during consolidation:

1. path ownership moved out of scattered hard-coded values and into shared configuration
2. image migration completed into the consolidated image destination
3. orchestrator entry point added and run successfully
4. benchmark seed handling corrected and validated using a repaired April 17 benchmark seed
5. benchmark DEVICE join failure fixed
6. wafer-output overwrite behavior corrected so the consolidated wafer output is accumulated instead of replaced by the latest raw refresh slice
7. defect-coordinate accumulation updated to use transitional dual seeds (legacy root + canonical outputs/defects) with deterministic dedup precedence
8. one-time coordinate backfill/merge executed into canonical outputs file, with backup created before overwrite and current canonical rows preferred on duplicate keys

## Known Remaining Risks

### 1. Wafer accumulation still relies on a legacy seed source during transition

The consolidated wafer output is now being accumulated against:

- the legacy root wafer file
- the new consolidated wafer file

This was necessary to recover previously missing rows during migration, but it is transitional. Production should not depend indefinitely on the legacy root file as a secondary seed.

### 2. Wafer deduplication needs one final validation pass

The wafer accumulation logic now produces a plausible reconciled union, but it should still be validated against expected wafer counts by time window and layer before the legacy seed dependency is removed.

### 2b. Coordinate accumulation now includes transitional legacy seeding

The defect-coordinate stage now mirrors wafer-stage migration behavior during transition:

- seed from legacy root `DEFECT_COORDINATES_EXTENDED.csv` when present
- seed from canonical `outputs/defects/DEFECT_COORDINATES_EXTENDED.csv`
- append current run results
- deduplicate by `(WAFER_KEY, INSPECTION_TIME, DEFECT_ID)` with last-write-wins ordering

Operational implication:

- canonical/current rows intentionally override legacy duplicates
- this should be treated as a temporary migration bridge and retired once confidence is established in canonical-only accumulation

### 3. JSL layer is still manual and external

The orchestrator depends on the operator having already refreshed the raw JSL CSVs. This is acceptable for now, but it is an operational dependency that should be documented clearly for scheduling.

### 4. Image runtime dependency is fail-open by design

The coordinate stage currently has `DOWNLOAD_IMAGES = True`, but SecureFTP/CLR runtime load is intentionally fail-open.

Implication:

- if the SecureFTP runtime is available, image metadata/download/reorg runs
- if unavailable, the run continues, and per-run manifest reconciliation still executes

This keeps the scheduled pipeline resilient, but image acquisition health must still be monitored.

### 5. Benchmark continuity should be checked automatically

The benchmark stage now uses a better seed selection strategy, but the pipeline still lacks a built-in post-run validation that explicitly checks for missing 7-day periods.

## Remaining Work Before Production

### Highest-priority remaining tasks

1. Validate the current consolidated wafer table against expected historical counts and confirm the accumulation result is correct by month and layer.
2. Remove dependence on the legacy root wafer CSV as an accumulation seed once confidence in the consolidated `outputs/wafer` file is sufficient.
3. Remove dependence on the legacy root coordinate CSV as an accumulation seed once confidence in the consolidated `outputs/defects` file is sufficient.
4. Add a post-run validation step that checks benchmark continuity, especially missing or partial 7-day periods.
5. Add explicit monitoring/alerting for image acquisition health (for example, zero-download streaks, unexpected unreferenced spikes, runtime dependency warnings).
6. Add a scheduler-friendly wrapper or runbook for VM execution using the required Python interpreter.

### Secondary hardening tasks

1. Make freshness windows configurable from one obvious operator surface.
2. Add a validation report comparing prior and current wafer outputs by normalized wafer key.
3. Add a validation report comparing benchmark periods before and after each extension run.
4. Add a validation report comparing prior and current coordinate outputs by normalized coordinate key.
5. Clean up any remaining obsolete direct-root outputs once the new layout is trusted.
6. Review whether additional processors should be re-enabled in the orchestrated path.

## Recommended Production Readiness Checklist

Before declaring the pipeline production-ready, confirm all of the following:

1. The JSL jobs are consistently writing refresh CSVs that pass the orchestrator freshness gate (<= 7 days old).
2. The orchestrator completes end-to-end without manual repair.
3. The consolidated wafer output is validated and no longer needs the legacy root file as a seed.
4. The consolidated defect-coordinate output is validated and no longer needs the legacy root file as a seed.
5. The defect-coordinate output remains stable under repeated overlap reruns.
6. The benchmark output is confirmed to have no missing weekly periods.
7. The operator run procedure is documented for both manual and scheduled runs.
8. Image handling behavior is documented as: runtime fail-open download + per-run manifest sync/prune/append.

## Recommended Next Implementation Steps

The next implementation tasks that would most improve production readiness are:

1. add a post-run benchmark-gap validator
2. add a post-run wafer-output validator by normalized key and month/layer
3. add a post-run coordinate-output validator by normalized coordinate key
4. retire the legacy root wafer and coordinate seeds once validation passes
5. add image-acquisition observability checks to scheduled monitoring
6. package the orchestrator into a VM scheduler wrapper with explicit environment settings

## Summary

The pipeline is now materially more coherent than the original disconnected script set:

- path ownership is centralized
- outputs are separated from source code
- images have been migrated
- benchmark seed selection is corrected
- a single Python update entry point exists
- artifact manifests are written for each stage

The main remaining work is not structural integration anymore. It is production hardening:

- final validation of the wafer accumulation contract
- benchmark continuity validation
- image-acquisition observability and alerting
- removal of transitional legacy dependencies

Once those are complete, the pipeline will be in a much stronger state for reliable scheduled execution.