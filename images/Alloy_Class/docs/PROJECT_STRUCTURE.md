# Alloy_Class Project Structure

## Purpose
This document defines the canonical folder layout for Alloy defect-classification work and tracks migration from root-level scripts.

## Canonical folders
- `pipelines/`: classification and caption batch runners
- `reporting/`: HTML/report generation and run summaries
- `metadata/`: joins and metadata preparation from pipeline artifacts
- `utils/`: shared helpers used by 2+ modules
- `tools/`: one-off operational utilities and developer tooling
- `tests/`: smoke and validation scripts
- `config/`: runtime/configuration JSON and generated metadata CSVs
- `inputs/`: local working image inputs for experiments
- `outputs/`: generated model outputs, reports, and logs
- `docs/`: handoff, runbooks, and architecture references

## Migration table

| Old path | Canonical path | Status |
|---|---|---|
| `classify_phase1_batch.py` | `pipelines/classify_phase1_batch.py` | migrated; root copy removed |
| `caption_phase1_batch.py` | `pipelines/caption_phase1_batch.py` | migrated; root copy removed |
| `build_phase1_html_report.py` | `reporting/build_phase1_html_report.py` | migrated; root copy removed |
| `compare_phase1_runs.py` | `reporting/compare_phase1_runs.py` | migrated; root copy removed |
| `build_defect_size_metadata.py` | `metadata/build_defect_size_metadata.py` | migrated; root copy removed |
| `smoke_test_one_image.py` | `tests/smoke_test_one_image.py` | migrated; root copy removed |

## Command policy
- Use canonical script locations for all new docs, commands, and automation.
- Do not add new phase scripts to the Alloy_Class root.

## Output placement policy
- Keep classification JSON/JSONL outputs under `outputs/phase1/`.
- Keep caption outputs under `outputs/captions/`.
- Keep generated HTML reports under `outputs/` unless a dedicated reporting subfolder is introduced later.
- Keep generated metadata CSVs in `config/` unless promoted to a dedicated managed artifacts location.

## Next organization steps
1. Extract duplicated env and image-iteration helpers into `utils/` once pair-aware phase work starts touching multiple modules.
2. Add a lightweight package layout (`__init__.py`) only when import-sharing is needed beyond wrappers.
3. Keep root clear of executable phase scripts and enforce canonical placement during future additions.
