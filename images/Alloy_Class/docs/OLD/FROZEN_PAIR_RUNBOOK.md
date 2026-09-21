# Frozen Pair Runbook (SMP Dev Sets)

Date: 2026-07-26

## Goal

Eliminate repeated manifest-wide pair-selection overhead by using fixed, reusable pair lists.

## Frozen Pair Files

- 1 pair: images/Alloy_Class/config/frozen_pairs/smp_pairs_1.csv
- 5 pairs: images/Alloy_Class/config/frozen_pairs/smp_pairs_5.csv
- 20 pairs: images/Alloy_Class/config/frozen_pairs/smp_pairs_20.csv

Each CSV schema:
- pair_key
- bright_path
- dark_path

Paths are full manifest-backed image paths (same image library location currently used by report rendering).

## Runner Support Added

The orchestrator now accepts:
- --pair-list-csv <path_to_csv>
- --report-image-path-source <inputs|structured|auto>
- --no-copy-burned

When set:
- pair selection mode becomes frozen_pair_list
- manifest-wide selection scan is skipped
- HTML can resolve directly from structured-record image paths (burned_image_path/image_path)
- burned/source image duplication into run output can be disabled
- run summary includes:
  - pair_selection_mode
  - pair_list_csv
  - report_image_path_source
  - copy_burned_to_run

## Example Commands

Use the project python interpreter:
- c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe

### 1-pair dev smoke

c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe images/Alloy_Class/tools/run_raw_stage_batch.py \
  --python-exe "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" \
  --pair-list-csv "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\config\frozen_pairs\smp_pairs_1.csv" \
  --no-copy-burned \
  --report-image-path-source structured \
  --max-pairs 1 \
  --target-label SMP \
  --require-raw \
  --run-id smp_frozen1_dev \
  --local-work-root "C:\temp\alloy_raw_stage" \
  --output-root "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\outputs\raw_runs"

### 5-pair iteration set

c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe images/Alloy_Class/tools/run_raw_stage_batch.py \
  --python-exe "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" \
  --pair-list-csv "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\config\frozen_pairs\smp_pairs_5.csv" \
  --no-copy-burned \
  --report-image-path-source structured \
  --max-pairs 5 \
  --target-label SMP \
  --require-raw \
  --run-id smp_frozen5_dev \
  --local-work-root "C:\temp\alloy_raw_stage" \
  --output-root "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\outputs\raw_runs"

### 20-pair benchmark set

c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe images/Alloy_Class/tools/run_raw_stage_batch.py \
  --python-exe "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" \
  --pair-list-csv "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\config\frozen_pairs\smp_pairs_20.csv" \
  --no-copy-burned \
  --report-image-path-source structured \
  --max-pairs 20 \
  --target-label SMP \
  --require-raw \
  --run-id smp_frozen20_benchmark \
  --local-work-root "C:\temp\alloy_raw_stage" \
  --output-root "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\outputs\raw_runs"

## HTML Report Path Note

Recommended quick-iteration mode:
- --report-image-path-source structured

In this mode the report uses image paths from structured outputs first (burned_image_path/image_path), with fallback behavior still available in auto mode.
