# Handoff: probe/run scoring + HTML reporting tooling

**Date built:** 2026-08-28
**Fills the gap described in:** [PROBE_OUTPUT_SCORING_AND_HTML_REPORT_GAP.md](PROBE_OUTPUT_SCORING_AND_HTML_REPORT_GAP.md)
(read that doc first for *why* this exists and the two raw output shapes it unifies --
this doc is the "what got built and how to run it" companion.)

## What this is for

Before this, scoring a VLM run/probe against ground truth and viewing the result as
images-plus-verdicts required manually locating the output JSONL, `ConvertFrom-Json`-ing
it, and eyeballing rows one at a time -- there was no scorer or HTML report for the
throwaway `tools/probe_*.py` scripts at all, and the production runner's scorer and HTML
builder didn't talk to each other. **Any future run or probe that needs "did the model
get it right, let me look at the images" reporting should go through the three files
below instead of building another one-off script.**

## The three files

| File | Role |
|---|---|
| `tools/normalize_probe_output.py` | Maps either raw output shape into one generic per-case contract |
| `tools/score_probe_run.py` | Joins GT, computes metrics, writes scored CSV + scored JSONL + summary |
| `reporting/build_probe_html_report.py` | Renders the scored JSONL as an HTML review page |

### 1. `tools/normalize_probe_output.py`

Auto-detects and normalizes:
- **Lineage A** -- production `stage_ab_results.jsonl` (one row per image, grouped here
  by `pair_key` into brightfield+darkfield pairs).
- **Lineage B** -- throwaway `tools/probe_*.py` output (one flat JSON object per case
  per line, e.g. `outputs/probes/describe_then_classify_v14_*.jsonl`).

Both get mapped into the same shape:

```jsonc
{
  "case_id": "BMK_0029",            // "" for Lineage A until score_probe_run.py resolves it
  "vlm_pair_key": "...",             // Lineage A join key only
  "run_id": "...", "config_version": "...", "lineage": "a" | "b",
  "images": [{"role": "brightfield", "path": "..."}, {"role": "darkfield", "path": "..."}],
  "model_calls": [                   // ORDERED, never dropped -- a gated/skipped call still
    {"call_label": "...", "prompt_version": "...", "raw_text": "...",
     "parsed_json": {...} | null, "skipped": false, "skip_reason": null, "usage": {...}}
    // appears here with "skipped": true and a "skip_reason"
  ],
  "final_verdict": {                 // normalized from the LAST non-skipped call's parsed_json
    "coarse_class": "...", "blocked_etch_evidence": "...", "confidence": 0.9,
    "review_required": false, "evidence_checks": {...}, "rationale": "..."
  }
}
```

Importable entry point: `normalize_jsonl(path: Path) -> list[dict]`.

### 2. `tools/score_probe_run.py`

```bash
python tools/score_probe_run.py \
  --input-jsonl outputs/probes/describe_then_classify_v14_20260828T052533Z.jsonl [<more files>...] \
  --output-folder outputs/probes/<some_output_dir> \
  [--lookup-csv <run_dir>/benchmark_id_lookup.csv]   # required for Lineage A input only
  [--gt-csv artifacts/benchmark_candidates_14day.csv]  # this is already the default
```

- Accepts 1+ JSONL files, each auto-detected as Lineage A or B independently -- you can
  score a Lineage B probe run without touching any Lineage A machinery.
- GT join key is `case_id` (`benchmark_id`) against `artifacts/benchmark_candidates_14day.csv`
  (uses `adjudicated_coarse_class` / `adjudicated_blocked_etch_evidence` /
  `review_required_expected` -- **never** `factory_class_label`, see that CSV's own gotcha
  noted in repo memory `alloy_class_vlm_architecture_investigation.md` section 10).
  - Lineage B records already carry `case_id` directly.
  - Lineage A records only carry `vlm_pair_key`; pass `--lookup-csv` pointing at that run's
    `benchmark_id_lookup.csv` to resolve `vlm_pair_key -> benchmark_id`. Without it, Lineage A
    cases score as `confusion_label: "no_gt"`.
- Positive class for `confusion_label` (`TP`/`TN`/`FP`/`FN`/`indeterminate`/`no_gt`) is
  `possible_beep`, matching `tools/score_benchmark_run.py`'s existing `fn_beep_rate`/
  `fp_beep_rate` convention -- do not invent a different convention for new callers.

**Outputs** (in `--output-folder`):
- `probe_scored_rows.csv` -- flat, one row per case, for quick filtering/Excel.
- `probe_scored_cases.jsonl` -- full nested record (images + model_calls + gt/match fields)
  -- **this is what `build_probe_html_report.py` reads.**
- `probe_score_summary.json` -- `confusion_counts`, `coarse_class_agreement_rate`,
  `fn_beep_rate`, `fp_beep_rate`, `evidence_agreement_rate`, `review_required_calibration_rate`.

### 3. `reporting/build_probe_html_report.py`

```bash
python reporting/build_probe_html_report.py \
  --input-jsonl outputs/probes/<some_output_dir>/probe_scored_cases.jsonl \
  --output-html outputs/probes/<some_output_dir>/probe_review.html
```

Layout (iterated per review feedback on 2026-08-28, after the initial build):

- **Summary row** per case: `Case | Category | Coarse | Evidence | Verdict Detail` -- `Coarse`
  and `Evidence` are green/red/gray GT-vs-VLM cells (gray = no GT available); `Verdict Detail`
  has confidence/review_required/confusion_label.
- **Detail row** per case, split into two side-by-side panels (`display:flex`) so a zoomed
  image can never bleed into the model-call text next to it:
  - **Left (`.images-panel`, width-capped at 300px, `overflow:hidden`)**: brightfield +
    darkfield images, then the evidence-check comparison directly below them (no
    "Checks" header -- just the three checks). Each check renders as
    **`<b>evidence_type:</b>`** on its own line, then `gt=... / vlm=...` on the next line,
    then a blank line before the next check. GT comes from the adjudication CSV
    (`offset_surface_lines_present` / `comparator_boundary_line_present` /
    `sunken_residual_continuity_present`, normalized to the same 3 key names the VLM
    uses); VLM values come from `final_verdict.evidence_checks` (omit/show `<none>` if a
    given probe's model doesn't emit that field).
  - **Right (`.calls-panel`, flexible width, `overflow-x:auto`, left border divider)**: a
    `<details open>` block **per `model_calls` entry** (loops over the list, so it renders
    correctly whether a case has 1 call, 2 calls, or N calls) -- **defaults to expanded**,
    shows a `[SKIPPED: ...]` badge for gated calls.
- Top summary block (above the table) has case count, review-required rate, VLM class
  counts, and confusion counts.
- **Output write is lock-safe**: if `--output-html`'s target path is locked (e.g. a
  previous version of the same report is still open in a browser tab on this UNC share),
  the write falls back to an auto-incrementing `<name>_rev2.html`, `_rev3.html`, ... instead
  of failing the run. The script prints which path it actually wrote to -- check that note
  if the file you're viewing doesn't reflect a change you just made.

## Verified working end-to-end

Initial smoke test scored `describe_then_classify_v14_20260828T051448Z.jsonl` (a
standalone 1-case rerun of BMK_0029) alongside `...T051609Z.jsonl` and `...T052533Z.jsonl`,
which double-counted BMK_0029 (30 cases, one duplicate) -- that test output was deleted
afterward. See "2026-08-28 real run" below for the corrected, deduplicated scoring.

## 2026-08-28 real run: describe_then_classify_v14 (29 cases)

`outputs/probes/` accumulated four v14 files from the same session; three of them are
supersets/reruns of each other:

| File | Cases | Status |
|---|---|---|
| `describe_then_classify_v14_20260828T045546Z.jsonl` | 10 (5 FN + 4 particle_control + 1 edge_case) | superseded by `...T051609Z` (same 10 case_ids, later timestamp) |
| `describe_then_classify_v14_20260828T051448Z.jsonl` | 1 (BMK_0029 only) | superseded by `...T051609Z` (same case_id, later timestamp) |
| `describe_then_classify_v14_20260828T051609Z.jsonl` | 10 (same set as 045546Z) | **used** -- latest version of this batch |
| `describe_then_classify_v14_20260828T052533Z.jsonl` | 19 (fp21_case set, 21 configured/2 image-missing skips) | **used** -- no overlap with the other batch |

Scored the two non-superseded files (`...T051609Z.jsonl` + `...T052533Z.jsonl`, 29 unique
`case_id`s, no duplicates) into
`outputs/probes/scored/describe_then_classify_v14_20260828/`:

```bash
python tools/score_probe_run.py \
  --input-jsonl outputs/probes/describe_then_classify_v14_20260828T051609Z.jsonl \
                outputs/probes/describe_then_classify_v14_20260828T052533Z.jsonl \
  --output-folder outputs/probes/scored/describe_then_classify_v14_20260828

python reporting/build_probe_html_report.py \
  --input-jsonl outputs/probes/scored/describe_then_classify_v14_20260828/probe_scored_cases.jsonl \
  --output-html outputs/probes/scored/describe_then_classify_v14_20260828/probe_review.html
```

Result (0 unmatched GT):

```
scored_cases=29 unmatched=0
{
  "total_cases": 29, "cases_with_gt": 29,
  "confusion_counts": {"TP": 5, "TN": 6, "FP": 18, "FN": 0, "indeterminate": 0, "no_gt": 0},
  "coarse_class_agreement_rate": 0.3793, "fn_beep_rate": 0.0, "fp_beep_rate": 0.75,
  "evidence_agreement_rate": 0.2414, "review_required_calibration_rate": 0.2759
}
```

HTML report confirmed rendering correctly: images resolved via relative path, GT/VLM
match cells colored, images/checks/model-calls panels laid out side by side per case, and
`model_calls` `<details>` blocks expanded by default. Outputs live at
`outputs/probes/scored/describe_then_classify_v14_20260828/` (`probe_scored_rows.csv`,
`probe_scored_cases.jsonl`, `probe_score_summary.json`, `probe_review.html`).

## For an agent picking this up on a new run/probe

1. Locate the run's raw JSONL (probe script output, or `stage_ab_results.jsonl`).
2. Run `score_probe_run.py` against it (add `--lookup-csv` if it's Lineage A).
3. Run `build_probe_html_report.py` against the resulting `probe_scored_cases.jsonl`.
4. Open the HTML in a browser -- no more manual `ConvertFrom-Json` inspection.

If a probe script's output doesn't match either detected shape (new field names, a
restructured call sequence, etc.), extend `normalize_probe_output.py`'s two mapping
functions (`normalize_lineage_a_pair` / `normalize_lineage_b_row`) rather than writing a
new parallel scorer/HTML builder -- that's the whole point of the generic contract.

## Open decisions still unresolved (inherited from the gap doc, not settled here)

- **Output location convention**: `score_probe_run.py` still takes an explicit
  `--output-folder` with no enforced default. The 2026-08-28 real run above used
  `outputs/probes/scored/<probe_run_name>/` -- follow that pattern for consistency unless
  a stronger convention gets established.
- **Per-run HTML vs. running index**: today each run gets its own standalone HTML file.
  A single appending index (closer to what `docs/PROMPT_ITERATION_REGISTRY.md` does at
  the CSV level) would be more useful for comparing prompt versions side by side, but
  isn't built.
- **Lineage A's Stage A/B raw excerpts are truncated to 1000 chars** (`stage_a_raw_excerpt`
  / `stage_b_raw_excerpt` in the source JSONL) -- the normalizer passes these through
  as-is; full raw text isn't available for Lineage A the way it is for Lineage B.
- `call2_prompt_chars` (Lineage B) still only records a length, not the actual prompt
  text sent -- unchanged from the gap doc's original note; not persisted anywhere yet.

## Repo memory pointer

Repo memory `probe_scoring_html_tooling.md` has a condensed version of this same
information for the agent's own recall across sessions.
