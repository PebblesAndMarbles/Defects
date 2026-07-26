# Inline Benchmark Stage

## Stage Role

Extends rolling fleet benchmark output from the current wafer table.

Primary modules:

- [BE_QUERY_FILES/modular_processor/EXTEND_BENCHMARK.py](../../BE_QUERY_FILES/modular_processor/EXTEND_BENCHMARK.py)
- [BE_QUERY_FILES/modular_processor/TIME_BIN_AGGREGATOR.py](../../BE_QUERY_FILES/modular_processor/TIME_BIN_AGGREGATOR.py)

## Current Behavior

- Uses current wafer output as source.
- Derives benchmark helper columns as needed.
- Extends latest available benchmark period.

## Seed Selection

- Override supported with BE_BENCHMARK_SEED_PATH.
- Otherwise stage auto-selects the latest prior benchmark in outputs/benchmarks.

## Outputs

- [outputs/benchmarks](../../outputs/benchmarks)

## Hardening Opportunity

- Add post-run benchmark continuity validation (missing/partial period detection).
