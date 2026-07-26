# Inline Operations and Hardening

## Operator Flow

1. Run JSL refresh for raw layer CSVs.
2. Run Python orchestrator.
3. Review canonical outputs and artifact manifests.

Orchestrator:

- [BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py](../../BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py)

Artifacts:

- [artifacts/update_run_artifacts.json](../../artifacts/update_run_artifacts.json)
- [artifacts/main_run_artifacts.json](../../artifacts/main_run_artifacts.json)
- [artifacts/defect_coordinates_artifacts.json](../../artifacts/defect_coordinates_artifacts.json)
- [artifacts/benchmark_artifacts.json](../../artifacts/benchmark_artifacts.json)

## Current Contracts

- JSL freshness gate: 7 days
- Coordinate overlap: 10 days
- Image retention: 60 days

## Production Readiness Focus

1. Validate wafer accumulation by month and layer, then retire legacy seed bridge.
2. Validate coordinate accumulation and dedup behavior, then retire legacy seed bridge.
3. Add explicit benchmark continuity checks after each run.
4. Add image-acquisition observability for scheduled operation.
5. Keep scheduler wrapper and runbook aligned with required interpreter and workspace paths.

## Related References

- [INLINE_PIPELINE_DESIGN.md](../../INLINE_PIPELINE_DESIGN.md)
- [DESIGN_INDEX.md](../../DESIGN_INDEX.md)
