# Phase 1 Runbook

This runbook executes Rob/Doruk-style image classification experiments in the current app folder while using shared UNC runtime tooling.

## Files
- Runner: `pipelines/classify_phase1_batch.py`
- Rob-style caption runner: `pipelines/caption_phase1_batch.py`
- Structured-run summary helper: `reporting/compare_phase1_runs.py`
- HTML report builder: `reporting/build_phase1_html_report.py`
- Defect-size metadata builder: `metadata/build_defect_size_metadata.py`
- Smoke test: `tests/smoke_test_one_image.py`
- Runtime config: `config/runtime_paths.json`
- Phase 1 settings: `config/phase1_settings.json`
- Shared requirements: `\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Shared_Docs\\Alloy_Apps\\_shared_runtime\\constraints\\requirements.lock.py311.txt`

Inline pipeline context references:

- `../../../docs/inline_pipeline/README.md`
- `../../../docs/inline_pipeline/coordinates_and_images.md`
- `../../../docs/inline_pipeline/runtime_contract.md`

## Inputs and outputs
- Input images: `./inputs`
- Output folder: `./outputs/phase1`
- Per-image output: `<image_key>.json`
- Batch log: `phase1_results.jsonl`
- Error log: `phase1_status.jsonl`

Pair safety defaults:
- `require_bf_df_pairs=true` (skip unpaired images by default)
- `max_pairs=5` (send a handful of BF/DF pairs first)

## Environment
Execution modes:

- Development mode (active now): run with a working Alloy environment for build/test iteration.
- ScriptHost parity mode (gated): run with the fixed interpreter only after wheelhouse coverage is complete.

Set API key in shell before run:

Reference shared guidance first:
- `\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Shared_Docs\Alloy_Apps\_shared_runtime\ALLOY_API_KEY_METHODS.md`

```powershell
$env:ALLOY_API_KEY = "<your-token>"
```

Alternative for repeat local runs while keeping secrets off UNC:

```powershell
$env:ALLOY_ENV_FILE = "C:\\path\\to\\local\\.env.context"
```

Example local `.env.context` contents:

```text
ALLOY_API_KEY=<your-token>
```

Behavior:
- the runner first loads `ALLOY_ENV_FILE` if provided
- then it looks upward from the current working directory for `.env` or `.env.context`
- existing environment variables are not overwritten

## Optional dependency bootstrap
Use shared wheelhouse bootstrap when needed:

```powershell
& "\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Shared_Docs\\Alloy_Apps\\_shared_runtime\\bootstrap\\install_from_wheelhouse.ps1" `
  -PythonExe "<python-exe>" `
  -WheelhousePath "\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Shared_Docs\\Alloy_Apps\\_shared_runtime\\wheelhouse\\py311" `
  -RequirementsFile "\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Shared_Docs\\Alloy_Apps\\_shared_runtime\\constraints\\requirements.lock.py311.txt"
```

ScriptHost-parity preflight (UNC-only dependencies):

```powershell
$py = "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe"
& $py tools/wheelhouse_audit.py `
  --requirements-lock "\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Shared_Docs\\Alloy_Apps\\_shared_runtime\\constraints\\requirements.lock.py311.txt" `
  --wheelhouse "\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Shared_Docs\\Alloy_Apps\\_shared_runtime\\wheelhouse\\py311"

& "\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Shared_Docs\\Alloy_Apps\\_shared_runtime\\bootstrap\\install_from_wheelhouse.ps1" `
  -PythonExe $py `
  -WheelhousePath "\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Shared_Docs\\Alloy_Apps\\_shared_runtime\\wheelhouse\\py311" `
  -RequirementsFile "\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Shared_Docs\\Alloy_Apps\\_shared_runtime\\constraints\\requirements.lock.py311.txt"

& $py -c "import alloy; from alloy.core.llm import image; print('alloy_import_ok=True')"
```

If wheelhouse audit reports missing packages, do not proceed with classification runs until UNC wheelhouse coverage is fixed.

Clarification:

- The above stop condition applies to ScriptHost-parity mode.
- Development mode can continue in parallel with the currently working Alloy API environment.

## Run command
From `images/Alloy_Class`:

```powershell
python pipelines/classify_phase1_batch.py --runtime-paths config/runtime_paths.json --phase1-settings config/phase1_settings.json
```

Limit to a smaller first pass (example: 3 pairs):

```powershell
python pipelines/classify_phase1_batch.py --runtime-paths config/runtime_paths.json --phase1-settings config/phase1_settings.json --max-pairs 3
```

Include unpaired images only when intentionally needed:

```powershell
python pipelines/classify_phase1_batch.py --runtime-paths config/runtime_paths.json --phase1-settings config/phase1_settings.json --allow-unpaired
```

Transient raw-image mode (download raw -> VLM inference -> delete raw temp):

```powershell
python pipelines/classify_phase1_batch.py --runtime-paths config/runtime_paths.json --phase1-settings config/phase1_settings.json --raw-image-mode --max-pairs 3
```

Notes:
- Burned library path remains the primary linkage record (`burned_image_path` in output).
- Raw file is staged temporarily and deleted after inference by default.
- Set `--raw-strict` to fail rows when raw download cannot be resolved.
- Set `--raw-keep-temp` only for debugging.

Rob-style captioning batch:

```powershell
python pipelines/caption_phase1_batch.py --input-folder inputs --output-folder outputs/captions
```

Summarize structured run output:

```powershell
python reporting/compare_phase1_runs.py outputs/phase1/phase1_results.jsonl
```

Build paired HTML report:

```powershell
python reporting/build_phase1_html_report.py --inputs-dir inputs --caption-jsonl outputs/captions/caption_results.jsonl --structured-jsonl outputs/phase1/phase1_results.jsonl --output-html outputs/phase1_combined_report.html
```

Build optional defect metadata (from coordinates + image manifest):

```powershell
python metadata/build_defect_size_metadata.py --output-csv config/defect_size_metadata.csv
```

Run structured classification with optional defect metadata enrichment:

```powershell
python pipelines/classify_phase1_batch.py --runtime-paths config/runtime_paths.json --phase1-settings config/phase1_settings.json --size-metadata-csv config/defect_size_metadata.csv
```

## Suggested first experiment
1. Place 5-10 representative images into `./inputs`.
2. Run once with default prompt.
3. Duplicate `phase1_settings.json` to a v2 prompt and rerun with a new run_id.
4. Compare class consistency, confidence, and review_required rates.
