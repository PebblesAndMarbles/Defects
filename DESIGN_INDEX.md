# BE Pipeline Design Index

This index is the top-level discovery point for pipeline design documentation in this workspace.

## Available Design Documents

1. Inline Defect Pipeline Design
   - [INLINE_PIPELINE_DESIGN.md](INLINE_PIPELINE_DESIGN.md)
2. SURF Scan Pipeline Design
   - [SURF_SCAN_PIPELINE_DESIGN.md](SURF_SCAN_PIPELINE_DESIGN.md)
3. SURF Feature-Level Design Notes
   - [docs/surf_scan_pipeline/README.md](docs/surf_scan_pipeline/README.md)
4. Inline Feature-Level Design Notes
   - [docs/inline_pipeline/README.md](docs/inline_pipeline/README.md)

## When To Use Which Document

1. Use [INLINE_PIPELINE_DESIGN.md](INLINE_PIPELINE_DESIGN.md) for the JSL-driven inline defect pipeline (8M5CL/8M6CL wafer, defect, image, and benchmark flow).
2. Use [SURF_SCAN_PIPELINE_DESIGN.md](SURF_SCAN_PIPELINE_DESIGN.md) for the UDB-driven SURF scan pipeline (seed/incremental coordinates, EDX/image flow, and 60-day image retention).
3. Use [docs/surf_scan_pipeline/elwc_rf_counters.md](docs/surf_scan_pipeline/elwc_rf_counters.md) for ELWC RF stage/apply behavior and RF-only production counter contract.
4. Use [docs/inline_pipeline/README.md](docs/inline_pipeline/README.md) when editing one specific inline feature and you want the smallest relevant context.