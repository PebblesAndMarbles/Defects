# Inline Runtime Contract

## Execution Boundary

- JSL remains the raw acquisition boundary.
- Python pipeline starts after raw JSL CSV refresh.

## Required Runtime

- Interpreter: c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe
- Workspace root: \\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE

## Entrypoint

- Orchestrator: [BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py](../../BE_QUERY_FILES/8M5CL_8M6CL_UPDATE.py)

## Freshness Gate

The orchestrator enforces raw-input freshness before running downstream stages.

- Requires both JSL CSVs to exist.
- Rejects stale JSL inputs older than 7 days.

## Path Ownership

Use one shared path owner:

- [BE_QUERY_FILES/pipeline_config.py](../../BE_QUERY_FILES/pipeline_config.py)

This should remain the canonical source for output, artifact, image, and source path definitions.
