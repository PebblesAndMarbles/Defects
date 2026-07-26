# SURF Runtime Contract

## Execution Boundary

- SURF core data is DB-first (no JSL pre-refresh dependency).
- Daily scheduled entrypoint is `surf_scan_daily.py`.

## Required Runtime

- Interpreter: c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe
- Workspace root: \\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE

## Primary Entrypoints

- [BE_QUERY_FILES/surf_scan_daily.py](../../BE_QUERY_FILES/surf_scan_daily.py)
- [BE_QUERY_FILES/surf_scan_seed.py](../../BE_QUERY_FILES/surf_scan_seed.py)
- [BE_QUERY_FILES/surf_scan_incremental.py](../../BE_QUERY_FILES/surf_scan_incremental.py)

## Shared Defaults Owner

- [BE_QUERY_FILES/surf_scan_config.py](../../BE_QUERY_FILES/surf_scan_config.py)

Current defaults include:

- seed lookback
- incremental lookback
- image retention days
- image query lookback
- image count thresholds
