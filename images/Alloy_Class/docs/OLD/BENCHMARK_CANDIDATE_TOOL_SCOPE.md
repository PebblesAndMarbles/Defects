# Benchmark Candidate HTML Review Tool — Task Scope

**Date:** 2026-08-02  
**Workspace root:** `\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE`  
**Python interpreter:** `c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe`

---

## Objective

Build a benchmark candidate preparation pipeline that:

1. **Selects** all BF/DF image pairs from the last **14 days** of the defect image manifest.
2. **Outputs** a pre-filled candidate CSV matching the schema in `benchmark_slice_v1_template.csv`.
3. **Generates** an HTML review report so the operator can visually inspect all pairs and mark exclusions before finalising the benchmark slice.

---

## Implementation Status (2026-08-02)

Implemented scripts:
- `images/Alloy_Class/tools/build_benchmark_candidates.py`
- `images/Alloy_Class/tools/assign_benchmark_split.py`

Implemented outputs:
- `images/Alloy_Class/artifacts/benchmark_candidates_14day.csv`
- `images/Alloy_Class/reporting/benchmark_review_14day.html`
- `images/Alloy_Class/artifacts/benchmark_candidates_14day_summary.json`

Optional post-adjudication split output:
- `images/Alloy_Class/artifacts/benchmark_candidates_14day_split_preview.csv`

Implemented behavior deltas (final state):
- HTML card order exactly matches CSV row order (`benchmark_candidates_14day.csv`).
- Header is scrollable (non-sticky) to maximize image viewport.
- Card/image layout tightened for less empty horizontal space in 2-column viewing.
- Invalid path/subentity tokens (`nan`, `none`, `null`, `unknown`) are sanitized and excluded from candidate emission.

Run commands:

```powershell
cd "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE"
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "images/Alloy_Class/tools/build_benchmark_candidates.py"
```

```powershell
cd "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE"
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "images/Alloy_Class/tools/assign_benchmark_split.py" --input-csv "images/Alloy_Class/artifacts/benchmark_candidates_14day.csv" --output-csv "images/Alloy_Class/artifacts/benchmark_candidates_14day_split_preview.csv" --eval-ratio 0.3 --seed 1278
```

---

## Key Files and Paths

| File | Purpose |
|------|---------|
| `outputs/defects/DEFECT_COORDINATES_EXTENDED_IMAGES.csv` | Image manifest — primary source (INSPECTION_TIME, LOCAL_IMAGE_FILE, CLASS, FINEBIN, WAFER_KEY, DEFECT_ID, SUBENTITY, LOT7, ACTUAL_LOT) |
| `outputs/defects/DEFECT_COORDINATES_EXTENDED.csv` | Coordinate/metrics CSV — used to enrich with WAFER_X_MM/Y, LAYER, INSPECT_TOOL |
| `images/Alloy_Class/artifacts/benchmark_slice_v1_template.csv` | Target schema (header row + 3 example rows); output must match this column set. **Updated 2026-08-09**: template now includes 4 additional required observation fields (`notes_needed`, `sunken_residual_continuity_present`, `comparator_boundary_line_present`, `mult_particles_present`) and 5 optional fields (`pre_etch_geometry_match`, `evidence_coherence`, `evidence_localization`, `particle_edge_morphology`, `particle_morphology_match_to_beep_like`). If `build_benchmark_candidates.py` is re-run it must emit all 44 columns. |
| `images/Alloy_Class/docs/BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md` | Full schema definitions and field guidance |

---

## Source Pool Tagging

Map manifest fields to `source_pool` column:

| Manifest CLASS | FINEBIN | source_pool |
|---|---|---|
| `BEEP` | not `LOWCONF` and not blank | `factory_beep` |
| `BEEP` | `LOWCONF` | `ambiguous` |
| `BEEP` | blank/null | `factory_beep` (default; no low-confidence signal present) |
| `SMALL_PARTICLE` | any | `non_beep_control` |
| null/blank | any | `other` |
| anything else | any | `other` |

Log a frequency table of any unseen `CLASS` values in the run summary.

---

## Manifest Data Quality Note — CRITICAL

The manifest's `SUBENTITY`, `LOT7`, `ACTUAL_LOT`, and coordinate columns (`WAFER_X_MM`, `WAFER_Y_MM`) are **null for real image rows** — the pipeline only populates them for older-format rows. You must infer them:

- **SUBENTITY**: `os.path.basename(os.path.dirname(LOCAL_IMAGE_FILE))` — the image's parent folder name.
- **LOT7**: third underscore-delimited field of the filename, e.g. `260728_0728_D618239_...` → `D618239`.
- **Inspection recipe (BF/DF)**: fifth field of the filename: `SMP` or `BEEP`. NOT the manifest `CLASS` column (which is the defect class, not the recipe).  
  - image_id=2 → BF (bright field) → `bright_image_path`  
  - image_id=3 → DF (dark field) → `dark_image_path`
- **ACTUAL_LOT, WAFER_X_MM/Y, LAYER, INSPECT_TOOL**: join with `DEFECT_COORDINATES_EXTENDED.csv`. Use a **two-tier join strategy**:
  1. Primary join on `WAFER_KEY + INSPECTION_TIME + DEFECT_ID` when all three keys are present in both sources.
  2. Fallback join on inferred `SUBENTITY + LOT7` only when the primary keys are missing in the manifest.
  Log the fallback-join row count in the run summary for transparency.

Rows where the inferred SUBENTITY is `UNKNOWN` or blank should be **dropped** (pipeline attribution failure — no longer occurs after bug fix, but guard remains needed).

---

## Output 1 — Candidate CSV

**Path:** `images/Alloy_Class/artifacts/benchmark_candidates_14day.csv`

Column set: all columns from `benchmark_slice_v1_template.csv` header.

Pre-fill rules:
- `benchmark_id`: assign sequentially `BMK_0001`, `BMK_0002`, ... sorted by INSPECTION_TIME desc, then SUBENTITY, then DEFECT_ID.
- `split`: leave blank (operator assigns during adjudication).
- `source_pool`: assign per table above.
- `selection_batch`: `14day_{YYWW}` where YYWW = year+ISO week of most recent INSPECTION_TIME in the slice.
- `wafer_key`, `inspection_time`, `defect_id`: from manifest (WAFER_KEY, INSPECTION_TIME, DEFECT_ID).
- `pair_key`: `{WAFER_KEY}_{YYYYMMDD_HHMMSS}_{DEFECT_ID}` (timestamp normalized, no spaces).
- `bright_image_name`, `dark_image_name`: basename of image_id=2 and image_id=3 files.
- `bright_image_path`, `dark_image_path`: full UNC paths.
- `query_site`: from manifest `SITE` column if available.
- `tool_name`: from `INSPECT_TOOL` in coordinates CSV.
- `chamber`: inferred SUBENTITY.
- `factory_class_label`: manifest `CLASS` column.
- `manual_optical_class`: manifest `MANUAL_OPTICAL_CLASS` column (if populated).
- All `stage_a_*`, `stage_b_*`, `adjudicated_*`, `failure_mode_*`, `notes_short`: leave blank.

One row per **unique (WAFER_KEY, INSPECTION_TIME, DEFECT_ID)** — including INSPECTION_TIME prevents merging repeated inspections of the same defect ID across events. Both image paths go in the same row.

Include only pairs where **both** BF (image_id=2) and DF (image_id=3) files exist on disk. Log any pairs with only one image.

---

## Output 2 — HTML Review Report

**Path:** `images/Alloy_Class/reporting/benchmark_review_14day.html`  
**Self-contained**: inline SVG wafermaps, images linked by UNC path (no base64 — files are local).

### Page structure

- Scroll header (non-sticky): "Benchmark Candidates — 14-Day Pool · N pairs · YYYY-MM-DD"
- Stats bar: counts by source_pool (factory_beep / non_beep_control / ambiguous / other).
- One **card** per defect pair in the exact same order as `benchmark_candidates_14day.csv`.

### Card layout (per defect pair)

```
┌─────────────────────────────────────────────────────────────────┐
│  BMK_0001  │  AME427_PM3  │  D618239  │  Defect 42  │  BEEP ← factory_class │  2026-07-28
├────────────────────────────┬────────────────────────────────────┤
│  BF (image_id=2)           │  DF (image_id=3)                   │
│  [image, clickable]        │  [image, clickable]                │
└────────────────────────────┴────────────────────────────────────┘
```

- Each image: ~240 × 240 px, click opens full-size.
- Source pool badge: colour-coded pill (factory_beep = blue, non_beep_control = green, ambiguous = amber, other = gray).
- Factory class label always shown (informed review).
- Card background: dark theme consistent with existing inline defect reports (`#0f151c` background, `#e6edf3` text).

### Summary table at page top

Counts by (source_pool × chamber) — quick completeness check for the operator.

---

## Implementation Notes

### Script location
`images/Alloy_Class/tools/build_benchmark_candidates.py`

This script performs **candidate generation and HTML packaging only**. No adjudication, no model inference. Adjudication fields are intentionally blank in all outputs.

Companion script for split assignment after adjudication:
- `images/Alloy_Class/tools/assign_benchmark_split.py`
- Deterministic stratification keys: `source_pool`, `chamber`, `adjudicated_coarse_class`
- Output `split` values: `tune` / `eval`

### Dependencies
Standard library + `pandas` only. No external ML or DB calls.

### Suggested internal structure
```
build_benchmark_candidates.py
  load_manifest(csv_path, lookback_days=14)  # filter, infer SUBENTITY/LOT7
  enrich_from_coords(mdf, coords_csv)        # join for WAFER_X_MM/Y, INSPECT_TOOL, ACTUAL_LOT
  assign_source_pool(mdf)                    # CLASS + FINEBIN → source_pool
  build_pair_rows(mdf)                       # one row per (WAFER_KEY, INSPECTION_TIME, DEFECT_ID)
  write_candidate_csv(rows, out_path)
  render_html(rows, out_path)
  main()
```

Note:
- This scope intentionally uses a 14-day candidate horizon. If another template mentions 7-day defaults, this document overrides that for this run.

### Re-run behaviour
Both output files are overwritten on each run. No timestamping — the operator versions by copying the CSV before adjudication (per workflow doc §9).

---

## Clarifications Already Resolved

| Question | Answer |
|---|---|
| Lookback window | **14 days** (not 7) — wider pool so operator can exclude biased wafers |
| HTML card detail | **Full card** per pair: BF \| DF images side by side + metadata visible |
| Factory class visible | **Yes** — informed review |
| Pre-selection | **No** — show all available pairs; operator excludes during adjudication |
| BEEP count in 7d pool | ~38 BEEP + ~76 SMALL_PARTICLE = ~57 pairs; 14d will be larger |

---

## Verification Steps (for new agent)

1. Run `build_benchmark_candidates.py` — confirm no errors and both outputs written.
2. Check `benchmark_candidates_14day.csv`:
   - No blank `benchmark_id`, `bright_image_path`, `dark_image_path`.
   - Both image files exist on disk for every row.
   - source_pool distribution makes sense (factory_beep ≥ 30% of total is the quality target).
3. Open `benchmark_review_14day.html` in a browser — confirm all images load, cards show factory class + chamber + BMK_id.
4. Confirm HTML card order matches `benchmark_candidates_14day.csv` row order.
5. Confirm CSV column set exactly matches `benchmark_slice_v1_template.csv` header.
6. *(Advisory, not hard failure)* If `factory_beep` < 30% of total pairs, emit a warning in the run summary and continue.

### Reviewer quick-check commands

Run generation:

```powershell
cd "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE"
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "images/Alloy_Class/tools/build_benchmark_candidates.py"
```

Validate CSV <-> HTML order and counts:

```powershell
cd "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE"
@'
import pandas as pd
import re

csv_path = r"images/Alloy_Class/artifacts/benchmark_candidates_14day.csv"
html_path = r"images/Alloy_Class/reporting/benchmark_review_14day.html"

df = pd.read_csv(csv_path, dtype=str).fillna("")
csv_ids = df["benchmark_id"].tolist()
text = open(html_path, "r", encoding="utf-8").read()
html_ids = re.findall(r"<div class='meta'>(BMK_\d{4})</div>", text)
print("csv_rows", len(csv_ids))
print("html_cards", len(re.findall(r"<section class='card'>", text)))
print("match_all", csv_ids == html_ids)
'@ | Set-Content -Path "images/Alloy_Class/artifacts/_verify_bmk_order_tmp.py" -Encoding UTF8
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "images/Alloy_Class/artifacts/_verify_bmk_order_tmp.py"
Remove-Item "images/Alloy_Class/artifacts/_verify_bmk_order_tmp.py"
```

Current known advisory status from latest run:
- `factory_beep_share` is below target 30% threshold, warning-only by design.

---
