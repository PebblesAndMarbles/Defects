# Inline Pipeline Feature Docs

This folder is the feature-level context map for the inline defect pipeline.

Primary design document:

- [INLINE_PIPELINE_DESIGN.md](../../INLINE_PIPELINE_DESIGN.md)

Use this folder when you are editing one feature and want the smallest relevant context.

## Suggested Editing Path

1. Start with [INLINE_PIPELINE_DESIGN.md](../../INLINE_PIPELINE_DESIGN.md) for pipeline-wide contract and operator flow.
2. Jump to one topic file below for implementation-level context.
3. Apply edits in code and update only the corresponding topic doc.

## Topic Documents

1. Runtime and path contract: [runtime_contract.md](runtime_contract.md)
2. Wafer update stage: [wafer_stage.md](wafer_stage.md)
3. Defect coordinates and images: [coordinates_and_images.md](coordinates_and_images.md)
4. Benchmark extension: [benchmark_stage.md](benchmark_stage.md)
5. Operations and production hardening: [operations_and_hardening.md](operations_and_hardening.md)

## Coverage Boundaries

- Inline only: this folder should not duplicate SURF implementation detail.
- Canonical references: prefer links to code under BE_QUERY_FILES and outputs under outputs.
- Keep each file focused and short to reduce prompt/context size during future edits.

## Ownership and Change Routing

Use this map to decide which doc to open first for a given change request.

| Change Type | Start Doc | Primary Code Touchpoints |
|---|---|---|
| Interpreter, workspace paths, output/artifact roots, freshness gates | [runtime_contract.md](runtime_contract.md) | [BE_QUERY_FILES/pipeline_config.py](../../BE_QUERY_FILES/pipeline_config.py), [BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py](../../BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py) |
| Wafer accumulation, layer cleanup, optional enrichment toggles | [wafer_stage.md](wafer_stage.md) | [BE_QUERY_FILES/modular_processor/main.py](../../BE_QUERY_FILES/modular_processor/main.py), [BE_QUERY_FILES/modular_processor/processors/defect_processor.py](../../BE_QUERY_FILES/modular_processor/processors/defect_processor.py) |
| Defect coordinate overlap, image joins, retention/reconcile behavior | [coordinates_and_images.md](coordinates_and_images.md) | [BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py](../../BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py), [BE_QUERY_FILES/reconcile_prune_images.py](../../BE_QUERY_FILES/reconcile_prune_images.py) |
| Benchmark seed selection, period extension, continuity checks | [benchmark_stage.md](benchmark_stage.md) | [BE_QUERY_FILES/modular_processor/EXTEND_BENCHMARK.py](../../BE_QUERY_FILES/modular_processor/EXTEND_BENCHMARK.py), [BE_QUERY_FILES/modular_processor/TIME_BIN_AGGREGATOR.py](../../BE_QUERY_FILES/modular_processor/TIME_BIN_AGGREGATOR.py) |
| Scheduling, readiness gates, post-run validation and monitoring | [operations_and_hardening.md](operations_and_hardening.md) | [BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py](../../BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py), [artifacts/update_run_artifacts.json](../../artifacts/update_run_artifacts.json) |
