# Inline Wafer Stage

## Stage Role

Primary wafer processor derives wafer-level defect metrics from merged JSL layer outputs.

Core modules:

- [BE_QUERY_FILES/modular_processor/main.py](../../BE_QUERY_FILES/modular_processor/main.py)
- [BE_QUERY_FILES/modular_processor/core/config.py](../../BE_QUERY_FILES/modular_processor/core/config.py)
- [BE_QUERY_FILES/modular_processor/processors/defect_processor.py](../../BE_QUERY_FILES/modular_processor/processors/defect_processor.py)

## Current Behavior

- Loads merged layer-level JSL outputs.
- Applies cleanup and rename logic.
- Writes consolidated wafer output with accumulation behavior.

## Output

- [outputs/wafer/8M5CL_8M6CL_EXTENDED.csv](../../outputs/wafer/8M5CL_8M6CL_EXTENDED.csv)

## Current Design Notes

- Accumulation is used instead of blind overwrite.
- Most optional enrichments are intentionally disabled in default update path for stability-first operation.

## Risks To Track

- Transitional legacy seed dependency should be retired once canonical output validation is complete.
- Dedup/count validation should be tracked by month and layer before removing migration bridges.
