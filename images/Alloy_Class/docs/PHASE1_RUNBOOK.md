# Phase 1 Runbook

This runbook executes Rob/Doruk-style image classification experiments in the current app folder while using shared UNC runtime tooling.

## Files
- Runner: `classify_phase1_batch.py`
- Rob-style caption runner: `caption_phase1_batch.py`
- Structured-run summary helper: `compare_phase1_runs.py`
- HTML report builder: `build_phase1_html_report.py`
- Defect-size metadata builder: `build_defect_size_metadata.py`
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

## Environment
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

## Run command
From `images/Alloy_Class`:

```powershell
python classify_phase1_batch.py --runtime-paths config/runtime_paths.json --phase1-settings config/phase1_settings.json
```

Rob-style captioning batch:

```powershell
python caption_phase1_batch.py --input-folder inputs --output-folder outputs/captions
```

Summarize structured run output:

```powershell
python compare_phase1_runs.py outputs/phase1/phase1_results.jsonl
```

Build paired HTML report:

```powershell
python build_phase1_html_report.py --inputs-dir inputs --caption-jsonl outputs/captions/caption_results.jsonl --structured-jsonl outputs/phase1/phase1_results.jsonl --output-html outputs/phase1_combined_report.html
```

Build optional defect metadata (from coordinates + image manifest):

```powershell
python build_defect_size_metadata.py --output-csv config/defect_size_metadata.csv
```

Run structured classification with optional defect metadata enrichment:

```powershell
python classify_phase1_batch.py --runtime-paths config/runtime_paths.json --phase1-settings config/phase1_settings.json --size-metadata-csv config/defect_size_metadata.csv
```

## Suggested first experiment
1. Place 5-10 representative images into `./inputs`.
2. Run once with default prompt.
3. Duplicate `phase1_settings.json` to a v2 prompt and rerun with a new run_id.
4. Compare class consistency, confidence, and review_required rates.
