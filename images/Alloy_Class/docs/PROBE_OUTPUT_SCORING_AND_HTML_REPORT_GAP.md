# Gap: probe/run outputs are not auto-scored or viewable as HTML

**STATUS (2026-08-28): the tooling described in section 6 has been built.** See
[HANDOFF_PROBE_SCORING_AND_HTML_REPORTING.md](HANDOFF_PROBE_SCORING_AND_HTML_REPORTING.md)
for what was built, exact usage, and which of this doc's "Open decisions" (section 8) are
still unresolved. This doc is kept as-is below for the original gap description and data
shape reference.

**Audience:** an agent picking this up to build the missing tooling. This is a description of
the current gap and the data shapes involved, not an implementation. Written 2026-08-28 after a
v13/v14 describe-then-classify diagnosis session where every result had to be manually located,
`ConvertFrom-Json`'d in PowerShell, and eyeballed row-by-row -- see
[iGPT_v13_FN_plan_passdown.md](iGPT_v13_FN_plan_passdown.md) and repo memory
`alloy_class_v13_v14_fp_diagnosis.md` for the session that motivated this doc.

## The gap, stated plainly

There are currently **two independent output lineages** in this project, and neither one gives you
a single command that goes from "a run just finished" to "scored CSV + an HTML page with images."

- **Lineage A (production Stage A/B runner)** has a scorer (`tools/score_benchmark_run.py`) and an
  HTML builder (`reporting/build_stage_ab_html_report.py`) -- but they don't talk to each other. The
  HTML builder renders the *raw* JSONL (no GT, no match/mismatch column). The scorer produces a CSV
  with GT joined and match/mismatch flags, but nothing renders that CSV with images. You have to run
  both and cross-reference by hand.
- **Lineage B (throwaway probe scripts)** -- `tools/probe_describe_then_classify.py`,
  `tools/probe_describe_then_classify_v14.py`, and any future `probe_*.py` -- has **neither**. GT is
  hardcoded inline in each script's test-case list rather than joined from a CSV, there is no scorer,
  and there is no HTML report. This is the format that produced every `outputs/probes/describe_then_classify*_*.jsonl`
  file from the v13/v14 session, and the only way to inspect them this session was ad hoc
  PowerShell `ConvertFrom-Json` dumps to a temp file, read back one case at a time.

Compounding both: the underlying architecture keeps changing shape (single Stage B call in v9-v12,
two-call describe-then-classify in v13, a hard-gate that skips the second call entirely in v14).
Anything hardcoded around "stage_a and stage_b" or "call1 and call2" breaks the next time the
approach changes. That's the "please keep this generic" ask driving section 4 below.

## 1. Lineage A: production Stage A/B runner

Pipeline: `tools/run_benchmark_vlm.py` (orchestrator) invokes `reporting/run_stage_ab_prompt_tests.py`
(per-image-pair Stage A/Stage B calls) against a `config/stage_ab_prompt_tests_substrate_tier1_vN.json`,
writing `stage_ab_results.jsonl` (one row per image, i.e. 2 rows per pair: brightfield + darkfield).

### 1a. Raw JSONL record shape (`stage_ab_results.jsonl`)

| Field | Notes |
|---|---|
| `run_id`, `timestamp_utc` | run identity |
| `pair_key` | join key -- filename stem with the `_2`/`_3` role suffix stripped |
| `image_name`, `pair_role` (`brightfield`/`darkfield`) | one row per image |
| `stage_a_prompt_version`, `stage_b_prompt_version` | e.g. `stageA_substrate_tier1_v1`, `stageB_describe_then_classify_v13` |
| `stage_a` | dict: `coarse_substrate_regime`, `dominant_orientation`, ..., `context_confidence`, `review_required`, `rationale` |
| `stage_b` | dict: `evidence_check_inset_surface_lines`, `evidence_check_boundary_conformance`, `evidence_check_sunken_residual`, `defect_coarse_class`, `blocked_etch_evidence`, `confidence`, `review_required`, `particle_location`, `trench_interaction`, `morphology_summary`, `rationale`, `metadata_alignment` |
| `stage_a_raw_excerpt`, `stage_b_raw_excerpt` | first 1000 chars of raw model text (fallback for parse failures) |
| `stage_a_usage`, `stage_b_usage` | token usage dicts |
| `burned_image_path`, `inference_image_path_stage_a`, `inference_image_path_stage_b` | absolute paths |
| *(v13+ only)* `stage_b_describe_then_classify: true`, `stage_b_call1_observation`, `stage_b_call1_usage` | Call 1's free-text observation and its token usage, when the two-call architecture is used |

`benchmark_id_lookup.csv` is written alongside by `run_benchmark_vlm.py`, columns:
`benchmark_id, pair_key_benchmark, bright_stem, source_pool, adjudicated_coarse_class`.

### 1b. Scorer: `tools/score_benchmark_run.py`

Joins `stage_ab_results.jsonl` rows to `benchmark_v1_frozen.csv` (canonical adjudicated labels) via
`benchmark_id_lookup.csv` (bright_stem minus `_2`/`_3` -> `pair_key`). Outputs a scored CSV with
columns like `vlm_coarse_class`, `gt_coarse_class`, `coarse_class_match`, `evidence_match`, plus a
summary JSON (`_compute_metrics`): `coarse_class_agreement_rate`, `fn_beep_rate`, `fp_beep_rate`,
`evidence_agreement_rate`, `review_required_calibration_rate`. This is the metrics logic worth
reusing -- see `_compute_metrics()` and `_stage_b_contract_summary()`.

### 1c. HTML builder: `reporting/build_stage_ab_html_report.py`

Reads the raw JSONL directly (not the scored CSV), groups by `pair_key`, renders one row per
image with an `<img>` tag (relative path from the report's own folder) plus collapsible
`<details>` blocks holding the raw `stage_a`/`stage_b` JSON. **Does not join GT and does not show
match/mismatch** -- it's a pre-scoring sanity-check view, not the "did the model get it right" view.

## 2. Lineage B: throwaway probe scripts

`tools/probe_describe_then_classify.py` (v13) and `tools/probe_describe_then_classify_v14.py` (v14)
are standalone scripts (not using `run_benchmark_vlm.py`/`run_stage_ab_prompt_tests.py` at all). Each
has a hardcoded Python list of test cases (`FN_CASES`, `PARTICLE_CONTROLS`, `EDGE_CASE_CONTROLS`,
`FP21_CASES` in the v14 script) with GT baked in as a literal (`gt_class`), and writes one flat JSON
object per line to `outputs/probes/describe_then_classify_v14_<UTC timestamp>.jsonl`.

### 2a. Probe JSONL record shape

| Field | Notes |
|---|---|
| `case_id` | e.g. `BMK_0029` -- matches `benchmark_id` in the CSVs below, but is NOT looked up from them; it's copied from the script's own hardcoded list |
| `category` | script-defined grouping, e.g. `fn_case`, `particle_control`, `edge_case_control`, `fp21_case` -- not a stable taxonomy, changes per script |
| `gt_class` | hardcoded in the script, e.g. `"particle"` or `"possible_beep"` -- **only as reliable as whoever typed it in**, not joined from an adjudicated source |
| `notes` | free-text, script author's context for why the case was picked |
| `bf_image`, `df_image` | absolute paths |
| `call1_observation` | Call 1's raw free-text |
| `call1_verdict` *(v14 only)* | parsed from Call 1's `VERDICT:` line -- one of `no_evidence`, `possible`, `ambiguous`, `missing` |
| `gated` *(v14 only)* | bool -- true means Call 2 was skipped entirely and `call2_parsed` is a synthetic hard-gate template, not a real model call |
| `call2_prompt_chars` | length only, NOT the actual prompt text sent (the constructed Call 2 prompt itself is not persisted anywhere -- see Open Decisions) |
| `call2_parsed` | dict, same evidence-check/verdict shape as Lineage A's `stage_b` dict (`evidence_check_inset_surface_lines`, `defect_coarse_class`, `blocked_etch_evidence`, `confidence`, `review_required`, `rationale`, ...) |
| `call2_raw_text` | raw model text fallback |
| `call1_usage`, `call2_usage` | token usage (`call2_usage` is `null` when `gated: true`) |

No scorer, no HTML builder exists for this shape today.

## 3. `reporting/benchmark_review_14day.html`

Separate from both of the above -- this is `tools/build_benchmark_candidates.py`'s output, a
source_pool x chamber card gallery over the *candidate pool* (for adjudication), not a scored-model-output
report. It's the correct place to resolve a `benchmark_id` (BMK_XXXX) to its burned-in image identity
for narrative/manual reference, but it has nothing to do with scoring a VLM run.

## 4. GT sources (pick one, be consistent)

- **`artifacts/benchmark_candidates_14day.csv`** -- keyed by `benchmark_id`, has `adjudicated_coarse_class`
  (canonical GT per project convention -- **never** `factory_class_label`, which is pre-adjudication),
  plus `bright_image_path`/`dark_image_path` and `pair_key` in the same row. This is the simplest
  single-file join for anything keyed by `benchmark_id` (i.e. all of Lineage B, and any future probe).
- **`benchmark_v1_frozen.csv` + `benchmark_id_lookup.csv`** -- the join path `score_benchmark_run.py`
  already uses for Lineage A, keyed by `pair_key` (stem-with-suffix-stripped). Keep this working for
  existing production runs; don't force Lineage A onto the `benchmark_candidates_14day.csv` join
  unless you're also willing to re-verify nothing regresses in `score_benchmark_run.py`'s existing
  metrics.

## 5. Proposed generic contract (what a scorer/HTML builder should actually consume)

Rather than hardcoding "stage_a/stage_b" or "call1/call2", define one normalized shape that both
lineages (and any future N-call architecture) get mapped into, either by adapting the runner/probe
scripts to emit it directly going forward, or via a small `normalize_lineage_a_row()` /
`normalize_lineage_b_row()` adapter function for scoring/rendering already-collected historical
JSONL without re-running anything:

```jsonc
{
  "case_id": "BMK_0029",                 // canonical join key -- benchmark_id
  "run_id": "...", "config_version": "...", // whatever identifies "which approach produced this"
  "gt_source": "artifacts/benchmark_candidates_14day.csv",
  "gt_coarse_class": "possible_beep",
  "gt_blocked_etch_evidence": "weak",
  "images": [
    {"role": "brightfield", "path": "...\\..._2.jpg"},
    {"role": "darkfield",   "path": "...\\..._3.jpg"}
  ],
  "model_calls": [                       // ORDERED LIST -- 1 call, 2 calls, N calls, all fit
    {"call_label": "call1_observation", "prompt_version": "CALL1_PROMPT_V14", "raw_text": "...", "parsed_json": null, "skipped": false, "usage": {...}},
    {"call_label": "call2_classify",    "prompt_version": "stageB_describe_then_classify_v14", "raw_text": "...", "parsed_json": {...}, "skipped": false, "usage": {...}}
    // a gated/hard-gated call still appears here with "skipped": true and a "skip_reason" -- never silently dropped
  ],
  "final_verdict": {                     // always normalized from the LAST non-skipped model_calls entry's parsed_json
    "coarse_class": "particle", "blocked_etch_evidence": "none", "confidence": 0.9,
    "review_required": false,
    "evidence_checks": {"inset_surface_lines": "no", "boundary_conformance": "no", "sunken_residual": "no"},
    "rationale": "..."
  }
}
```

Fields a scorer computes and appends (not present in the raw normalized record above):
`coarse_class_match` (bool), `evidence_match` (bool), `review_required_match` (bool), and a
`confusion_label` of `TP`/`TN`/`FP`/`FN`/`indeterminate` (define TP/FP relative to
`possible_beep` as the positive class, matching `score_benchmark_run.py`'s existing
`fn_beep_rate`/`fp_beep_rate` convention -- don't invent a new convention).

## 6. Two tools to build

1. **A generic scorer** (extend `tools/score_benchmark_run.py` or add `tools/score_probe_run.py`):
   takes one or more JSONL files (raw Lineage A or Lineage B shape, run through the matching
   normalizer above), joins GT from `artifacts/benchmark_candidates_14day.csv` by `case_id`/`benchmark_id`,
   reuses the `_compute_metrics()` logic pattern, and writes a scored CSV + summary JSON per run.
2. **A generic HTML report** (extend `reporting/build_stage_ab_html_report.py` or add
   `reporting/build_probe_html_report.py`): reads the scored CSV/JSONL, renders **one row per case**
   -- images side by side, a GT-vs-predicted cell with a match/mismatch color, then a `<details>`
   block **per `model_calls` entry** (loop over the list -- do not hardcode call count or names) showing
   raw text + parsed JSON, and a top summary block in the same style as the existing report
   (`class_counts`, review rate, etc., plus the new FN/FP rate now that GT is joined).

## 7. Worked example (this session's actual data)

`outputs/probes/describe_then_classify_v14_20260828T051448Z.jsonl`, BMK_0029 record, mapped into
the generic contract:

- `call1_observation` (raw string) -> `model_calls[0]` (`call_label: "call1_observation"`, `parsed_json: null`)
- `call1_verdict: "possible"` -> not part of `model_calls[0]` in the raw record today; a normalizer
  should re-parse it from `call1_observation`'s trailing `VERDICT:` line, or the probe script should
  be changed to store it as `model_calls[0].parsed_json = {"verdict": "possible"}` going forward
- `call2_parsed` -> `model_calls[1].parsed_json`, and also copied into `final_verdict` (rename
  `defect_coarse_class` -> `coarse_class` per the normalized shape, or just keep the field name and
  document that `final_verdict` is "whatever the last call's parsed JSON contract is" without forcing
  a rename -- see Open Decisions)
- `gated: false` -> `model_calls[1].skipped = false`. For a case where `gated: true` (e.g. BMK_0024
  in the same run), `model_calls[1]` should still be present with `skipped: true`,
  `skip_reason: "call1_verdict=no_evidence"`, `parsed_json` = the synthetic particle template from
  `_particle_gate_result()`.

## 8. Open decisions for the implementing agent

These are genuinely undecided -- pick something reasonable and note the choice in the tool's own
docstring rather than treating any of this as settled:

- Where scored outputs land: alongside the source JSONL, or a shared `outputs/probes/scored/` folder?
- One HTML file per run, or a single running index that appends new runs over time (the latter is
  more useful for comparing prompt versions side by side, closer to what
  `docs/PROMPT_ITERATION_REGISTRY.md` is trying to do at the CSV level)?
- Should the normalizer live as small per-lineage functions inside the generic scorer script, or as
  a separate `tools/normalize_probe_output.py` importable by both the scorer and the HTML builder?
  (Recommend the latter -- avoids the scorer and HTML builder silently drifting out of sync on what
  "normalized" means.)
- `call2_prompt_chars` only records a length today, not the actual constructed prompt text (see
  section 2a) -- if per-case prompt provenance matters for future debugging, the probe scripts
  should be changed to persist the actual prompt string, not just its length.

## 9. File inventory (exact paths, for quick reference)

| Purpose | Path |
|---|---|
| Production runner | `reporting/run_stage_ab_prompt_tests.py` |
| Production orchestrator | `tools/run_benchmark_vlm.py` |
| Production scorer (existing) | `tools/score_benchmark_run.py` |
| Production HTML (existing, pre-scoring only) | `reporting/build_stage_ab_html_report.py` |
| Probe scripts (no scorer/HTML today) | `tools/probe_describe_then_classify.py`, `tools/probe_describe_then_classify_v14.py` |
| Probe outputs | `outputs/probes/describe_then_classify_v14_*.jsonl` (and sibling v13 files) |
| GT (preferred, keyed by `benchmark_id`) | `artifacts/benchmark_candidates_14day.csv` |
| GT (legacy join, keyed by `pair_key`) | `artifacts/benchmark_v1_frozen.csv` + per-run `benchmark_id_lookup.csv` |
| Candidate-pool review gallery (not a scoring report) | `reporting/benchmark_review_14day.html` (built by `tools/build_benchmark_candidates.py`) |
| Prompt/run version tracking (manual, CSV) | `docs/PROMPT_ITERATION_REGISTRY.md` + `artifacts/prompt_iteration_registry.csv` |
