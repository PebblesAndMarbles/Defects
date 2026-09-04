# Handoff: build a static report of BEEP-mislabeled images (tranches 1-5)

**Date:** 2026-09-01
**For:** the next agent picking up this specific report-building task
**Status:** planning/handoff only -- nothing built yet for this specific report

## Objective

Trey has completed manual keyboard-driven review of the first 5 rapid-labeling
tranches (`reporting/build_beep_labeling_report.py` / `reporting/beep_labeling_portal/`).
Every case in these tranches came from the `SMALL_PARTICLE` factory-classified
population (see `tools/build_beep_labeling_tranche.py`'s `CLASS_OF_INTEREST`), so
any case the reviewer labeled `BEEP` instead is, by construction, a case the
existing factory classifier got wrong -- a misclassification.

**Build a static (read-only, no feedback widget needed) HTML report showing only
those misclassified cases** -- images + metadata -- for Trey to review/share.

## Current data state (verified 2026-09-01)

- `outputs/beep_evidence/beep_evidence_ground_truth.csv` -- **500 rows total**,
  100 each from `tranche_0001` through `tranche_0005` (all 5 fully labeled, no
  gaps). Label counts: **143 `BEEP`**, 357 `SMALL_PARTICLE`. Zero duplicate
  `pair_key` rows currently, but the file is append-only by design (see below) --
  defensively sort by `submitted_at_utc` and keep the last row per `pair_key`
  rather than assuming no dupes will ever occur.
- Ground truth CSV columns: `pair_key, wafer_key, inspection_time, defect_id,
  layer, label, reviewer, submitted_at_utc, tranche_id`. **No image paths, no
  `lot`, no `subentity`/chamber, no `factory_class` here** -- those only exist in
  the per-tranche cases CSVs and must be joined back in by `pair_key`.
- Five per-tranche manifests, one row per case, columns
  `pair_key, wafer_key, inspection_time, [lot,] defect_id, layer, subentity,
  factory_class, bright_image_path, dark_image_path`:
  - `outputs/beep_evidence/tranche_0001_cases.csv`
  - `outputs/beep_evidence/tranche_0002_cases.csv`
  - `outputs/beep_evidence/tranche_0003_cases.csv`
  - `outputs/beep_evidence/tranche_0004_cases.csv`
  - `outputs/beep_evidence/tranche_0005_cases.csv`
  - **Known gap:** only `tranche_0005_cases.csv` currently has a `lot` column
    (added 2026-09-01, and the tranche builder/report generator were updated so
    every *future* tranche gets it automatically). Tranches 0001-0004 do **not**
    have `lot` yet. If the report should show LOT for all 5 tranches, backfill
    0001-0004 the same way 0005 was done: join `wafer_key`+`defect_id` against
    `outputs/defects/DEFECT_COORDINATES_EXTENDED.csv`'s `WAFER_KEY`/`DEFECT_ID`/
    `LOT` columns (normalize both sides to the same integer-like string form
    before joining -- watch for `"123.0"` vs `"123"` mismatches). This is
    optional scope, not required to build the report.
  - `bright_image_path`/`dark_image_path` point directly at the **burned
    library images already on disk** (`images/defects/<chamber>/...jpg`) --
    unlike the separate generic-description pilot work elsewhere in this
    project, **no raw-image download / SecureFTP / GAJT machinery is needed
    here**. These paths are already viewable as-is.

## What to build

1. Load `beep_evidence_ground_truth.csv`, filter to
   `tranche_id in {tranche_0001..tranche_0005}` (currently all rows qualify,
   but be explicit rather than assuming the file will never grow past tranche 5)
   and `label == 'BEEP'` -> ~143 rows.
2. Load and concatenate the 5 `tranche_000N_cases.csv` files, join onto the
   filtered ground-truth rows by `pair_key` to pull `bright_image_path`,
   `dark_image_path`, `subentity`, `layer` (already in both, redundant but
   harmless), `factory_class` (will always read `SMALL_PARTICLE` -- that's the
   point), and `lot` where available (0005 only, per the gap above).
3. Render one summary block per case: bright + dark images side by side,
   metadata (`pair_key`, `wafer_key`, `inspection_time`, `lot` if present,
   `defect_id`, `layer`, `subentity`, `tranche_id`, `reviewer`,
   `submitted_at_utc`). **No radio buttons, no feedback form, no
   fetch()/backend calls** -- this is a plain static page.
4. A simple summary count at the top (total misclassified count, maybe a
   breakdown by `subentity`/chamber or by `tranche_id` -- Trey didn't ask for a
   specific breakdown, use judgment or ask).

## HTML tooling to reuse (do not reimplement from scratch)

- `reporting/build_beep_labeling_report.py` -- `_img_tag()`, `_dom_safe_id()`,
  and `_write_html_with_rev_fallback()` are the relevant reusable helpers
  (image relative-path resolution against the report's own output directory,
  DOM-safe id generation, and locked-file write fallback with `_revN` naming).
  **Do not reuse** `_case_row_html()`'s radio-button markup or the
  `_SCRIPT_TEMPLATE`'s labeling/submit JS -- none of that applies to a
  feedback-free static report.
- `reporting/build_generic_description_html_report.py` is a second, more
  recent example in this project of a **feedback-optional** static report
  (built with `--with-feedback-portal` as an opt-in flag, defaulting to off) --
  useful as a structural reference for "images + metadata table, no
  interactivity" even though its data shape (VLM `model_call` JSON) doesn't
  apply here.
- Suggested new file: `reporting/build_beep_misclassified_report.py`, output to
  something like `outputs/beep_evidence/beep_misclassified_tranches_1-5.html`.

## Open questions for whoever picks this up

- Should the report be sorted by `subentity`/chamber, by `inspection_time`, or
  by `tranche_id`? Not specified.
- Should `tranche_0001-0004`'s missing `lot` column be backfilled as part of
  this task, or left out of the report for those tranches (blank/omitted)?
- Confirm with Trey whether "misclassified" should ever include the reverse
  direction (factory said something other than `SMALL_PARTICLE` -- not
  possible today since the tranche population is 100% `SMALL_PARTICLE` by
  construction, but flagging in case the tranche source population definition
  changes later).
