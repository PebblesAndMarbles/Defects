# Tooling & methods inventory: VLM defect image labeling/disposition

**Date:** 2026-08-30
**Scope:** this is an inventory of what already exists and how to use it -- **not** a plan
for the fine-bin-tagging / disposition initiative discussed 2026-08-30. Written so a plan
can be built on top of it later, separately.

## 1. How to call the Alloy VLM

All image-calling code lives behind `reporting/run_stage_ab_prompt_tests.py`'s `_call_image()`
(imported by every probe script in `tools/probe_*.py`). Two paths depending on image count:

- **Single image**: `alloy.core.llm.image(path, prompt=..., model=..., max_completion_tokens=..., include_usage=True)`.
- **Multiple images** (e.g. brightfield + darkfield together, which is what every probe
  script in this project actually uses): base64-encodes each image, then POSTs a payload
  (`{"images": [...], "prompt": ..., "model": ..., "type": "azure", "max_completion_tokens": ...}`)
  to `alloy.core.config.config.vision_url` via `alloy.core.llm.core._make_request(..., max_retries=3, context="vision")`.

`_call_image()` returns `(parsed_json_dict, raw_output_text, usage_dict)`. It internally
calls `_extract_json_payload()` (same file) to pull a JSON object out of whatever shape the
model/runtime returns (native dict payload, a `content`/`description`/`json`/`result`
sub-field, or a bare JSON string), and `_extract_usage()`/`_estimate_tokens()` to fill in
token usage even when the runtime doesn't report it natively (`usage["source"]` will say
`"estimated"` in that case).

**Model identifier used throughout this project's probes**: `"claude-sonnet-4-6"` (a string
passed straight through to Alloy -- Alloy is the internal routing/gateway layer, not a
model itself).

**Environment/API key setup**: `_load_env_from_supported_locations()` (same file) checks
`ALLOY_ENV_FILE` env var first, then walks upward from the current working directory
looking for env files to parse. Every probe script calls this once at the top of `main()`
before making any calls -- copy that pattern for any new script.

**Token budget**: `DEFAULT_MAX_TOKENS = 1800` is the standing default across probe scripts,
inherited from an earlier finding (`docs/v12_post_mortem.md`) that 400 tokens caused a 25%
empty-response rate vs. 0% at 1800. Even at 1800, this session hit occasional truncated or
fully empty responses (a handful per ~30-case run) -- retrying the specific failed
case_id(s) at a higher budget (2400 worked in practice) is the established workaround, not
a documented root-cause fix.

**Cost/latency scales with prompt length.** Concrete numbers from this session: the
V11-derived two-call prompt grew from 11,252 to 19,047 characters through incremental
patching before it was abandoned; the from-scratch lexicon-based prompt (`LEXICON_PROMPT_V1`)
runs 6,557-7,531 characters as a single call. This matters directly for any plan that
scales to thousands of defects.

## 2. JSON output approaches -- two schemas exist today, plus one normalized layer

**Lineage A** (production, multi-stage): `reporting/run_stage_ab_prompt_tests.py` +
`tools/run_benchmark_vlm.py` orchestrate Stage A (substrate context) and Stage B
(classification) calls per image, writing `stage_ab_results.jsonl` with nested `stage_a`/
`stage_b` dicts, one row per image (brightfield + darkfield separately), grouped by
`pair_key`. This is the older, config-driven pipeline (see section 4).

**Lineage B** (throwaway probes, this session's work): `tools/probe_describe_then_classify*.py`
and `tools/probe_beep_lexicon_v*.py` write one flat JSON object per case per line, with the
model's parsed JSON under a `call2_parsed` key (and, for two-call architectures, a
`call1_observation` free-text field). GT (`gt_class`) is hardcoded per-case in the script,
not joined from a CSV -- fine at ~30 cases, would need to change for thousands (see
section 5).

**Normalized contract**: `tools/normalize_probe_output.py` maps either lineage into one
generic per-case shape (`images`, an ordered `model_calls` list, and a `final_verdict` with
`coarse_class`/`blocked_etch_evidence`/`confidence`/`review_required`/`evidence_checks`/
`rationale`) so `tools/score_probe_run.py` and `reporting/build_probe_html_report.py` work
regardless of how many calls an architecture uses. Full schema documented in
`docs/PROBE_OUTPUT_SCORING_AND_HTML_REPORT_GAP.md`.

**Output-contract-in-prompt pattern**: every prompt used this session ends with an explicit
"OUTPUT CONTRACT" block: strict JSON only, exact key order, allowed enum values spelled
out, `confidence` required to be a decimal float (models will otherwise write words like
"high"/"medium" unless told not to). This is a consistent, load-bearing convention across
every prompt version tried.

## 3. Prompt config patterns -- two generations

**Generation 1 (config-file-driven)**: `config/stage_ab_prompt_tests_substrate_tier1_vN.json`
(v1 through v14 exist) holds the actual prompt text in a `stage_a.prompt` /
`stage_b.prompt` JSON field, loaded at runtime by `run_stage_ab_prompt_tests.py`. This
still works for single-call, Stage A -> Stage B architectures.

**Generation 2 (prompt-embedded-in-code)**: starting at v13/v14, the two-call
describe-then-classify architecture's actual prompt text moved into Python constants
inside `tools/probe_*.py` scripts (e.g. `CALL1_PROMPT_V14`, and `_build_call2_prompt_v14()`
which loads V11's config JSON as a base and patches it at runtime with string
replacements). The `config/stage_ab_prompt_tests_substrate_tier1_v14.json` file for that
version is documentation-only -- it explicitly says "N/A, see code" rather than holding
real prompt text. The from-scratch lexicon prompts (`tools/probe_beep_lexicon_v1.py`,
`probe_beep_lexicon_v2.py`) continue this pattern: one Python constant
(`LEXICON_PROMPT_V1`/`V2`) holds the entire prompt, single call, no config JSON at all.

**Source lexicon document**: the actual definitions/evidence-rules content currently being
translated into prompt text lives in `images/Alloy_Class/BEEP_Evidence copy 2.txt`
(most recent iteration as of 2026-08-30) -- a plain-language, terse lexicon (image/substrate/
comparator/material-defect definitions, comparator concavity, inset surface lines,
occluding/non-occluding boundary conformance, sunken residual material, a 3-scenario
case-split by defect-to-comparator spatial relationship) that `probe_beep_lexicon_v2.py`'s
`LEXICON_PROMPT_V2` is a fairly direct translation of. This lexicon is scoped entirely to
the pre-etch/post-etch (particle vs. BEEP) disposition question -- it has no fine-bin
tagging (morphology/occlusion/sphere/defect-count) content in it as written.

## 4. Test-case / sampling patterns

Every probe script this session (`tools/probe_describe_then_classify_v14.py`,
`tools/probe_beep_lexicon_v1.py`, `v2.py`) uses **hardcoded Python dict lists**
(`FN_CASES`, `PARTICLE_CONTROLS`, `EDGE_CASE_CONTROLS`, `FP21_CASES`) -- 31 hand-picked
cases total, each with an explicit `folder`/`stem` pointing at a specific image pair on
disk and a hardcoded `gt_class`. This does not scale to thousands of defects as-is; a
larger run would need cases sourced from a CSV/query result (e.g. `artifacts/
benchmark_candidates_14day.csv`, or a fresh query analogous to
`BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py`'s `CLASS_FILTER = ['SMALL_PARTICLE', 'BEEP']`)
rather than typed into the script by hand.

**Production-scale pathway that already exists**: `tools/run_benchmark_vlm.py` takes a
`--pair-list-csv` (e.g. `artifacts/benchmark_pairs_full145.csv`) and stages/runs an
arbitrary number of pairs through Lineage A's Stage A/B pipeline -- this is the path built
for larger batches, not the throwaway probe scripts.

## 5. Ground truth sources

- **`artifacts/benchmark_candidates_14day.csv`** -- keyed by `benchmark_id`
  (e.g. `BMK_0029`), carries `adjudicated_coarse_class` as the canonical GT label
  (**never** `factory_class_label`, which is a pre-adjudication sampling-pool label), plus
  `bright_image_path`/`dark_image_path`, `chamber`, `tool_name`, and several evidence-flag
  columns (`comparator_visible`, `occlusion_present`, `offset_surface_lines_present`,
  `sunken_residual_continuity_present`, `comparator_boundary_line_present`, etc.) already
  used as GT for the evidence-check comparison in the HTML report.
- **`artifacts/benchmark_v1_frozen.csv` + per-run `benchmark_id_lookup.csv`** -- the
  legacy join path Lineage A's scorer (`tools/score_benchmark_run.py`) uses, keyed by
  `pair_key` instead of `benchmark_id`.
- Neither of these currently covers the full 6,487-defect `SMALL_PARTICLE` population --
  they're benchmark/candidate slices built for prompt iteration, not the full dataset.

## 6. Scoring

`tools/score_probe_run.py`: takes one or more raw JSONL files (auto-detects lineage per
file), joins GT by `case_id`/`benchmark_id` against `artifacts/benchmark_candidates_14day.csv`
by default (or a `--lookup-csv` for Lineage A), and writes `probe_scored_rows.csv` (flat),
`probe_scored_cases.jsonl` (full nested, what the HTML report reads), and
`probe_score_summary.json` (`confusion_counts` TP/TN/FP/FN/indeterminate/no_gt,
`coarse_class_agreement_rate`, `fn_beep_rate`, `fp_beep_rate`, `evidence_agreement_rate`,
`review_required_calibration_rate`). Positive class for confusion labeling is
`possible_beep` throughout.

Convention (from `docs/PROMPT_ITERATION_REGISTRY.md`): scored-row CSVs are treated as
immutable once written -- a rescore produces a new output folder, not an overwrite.

## 7. HTML reporting + feedback portal

`reporting/build_probe_html_report.py` renders `probe_scored_cases.jsonl` as one
summary+detail row pair per case (images, GT-vs-VLM color-coded cells, evidence-check
comparison, and every `model_calls` entry in an expandable `<details>` block -- generic
over however many calls an architecture uses).

`--with-feedback-portal` (opt-in flag) embeds a per-case feedback form (agree/disagree,
corrected-class select, comment) plus JS that posts to a local Flask backend
(`reporting/feedback_portal/backend/main.py`, started via `run_portal.cmd`/`run_portal.ps1
-DataFile <path>`), which appends submissions to a `probe_review_feedback.csv` next to
that run's scored output (schema: `case_id, reviewer, submitted_at_utc, agrees_with_vlm,
corrected_class, comment, run_id`). The backend only serves `/submit_feedback` and
`/feedback`; the HTML report itself is opened directly via `file://`, not served by Flask.
Full setup/run instructions in `docs/HANDOFF_HTML_FEEDBACK_PORTAL_INTEGRATION.md`.

This is the mechanism used this session for manual review of VLM verdicts against images
-- the same pattern would apply to a manual disposition pass over post-etch particles.

## 8. Relevant documentation index

| Doc | What it covers |
|---|---|
| `images/Alloy_Class/BEEP_Evidence copy 2.txt` | Current lexicon (pre/post-etch disposition rules only) |
| `docs/PROBE_OUTPUT_SCORING_AND_HTML_REPORT_GAP.md` | Full schema reference for both output lineages + the generic normalized contract |
| `docs/HANDOFF_PROBE_SCORING_AND_HTML_REPORTING.md` | How to run the scorer + HTML builder end to end |
| `docs/HANDOFF_HTML_FEEDBACK_PORTAL_INTEGRATION.md` | Feedback portal setup, CSV target, round-trip workflow |
| `docs/PROMPT_ITERATION_REGISTRY.md` + `artifacts/prompt_iteration_registry.csv` | Manual run-history tracker (run_id, prompt version, metrics) -- lightweight, CSV-based |
| `docs/v12_post_mortem.md` | Token-budget findings, Stage A/B vs. two-call architecture history |
| `docs/iGPT_v13_FN_plan_passdown.md` | The FN/FP diagnosis session that led to the v13/v14 architecture and, eventually, this lexicon pivot |
| `artifacts/benchmark_candidates_14day.csv` schema | GT source, adjudication columns, chamber/tool metadata |
| `BE_QUERY_FILES/DEFECT_COORDINATES_QUERY.py` | How the `SMALL_PARTICLE`/`BEEP` factory-class population gets queried today (`CLASS_FILTER`) |
| `BE_QUERY_FILES/surf_scan_coordinates.py`, `surf_scan_elwc_pm_pilot.py` | Chamber (`PROCESS_EQUIP_ID`/`SUBENTITY`) and PM-counter/mechanical-cycle history already queryable per chamber over time |

## 9. Known constraints worth knowing before planning

- Model responses are not perfectly repeatable -- the same image, prompt, and model
  produced different verdicts across duplicate test entries in this session's runs
  (observed on borderline/edge cases specifically, not clean-cut ones).
- Every attempt to tighten evidence criteria to reduce false positives this session also
  measurably increased false negatives, and vice versa -- no configuration tried achieved
  low error on both simultaneously across the same 31-case set.
- UNC paths containing `ORAnalysis$` break PowerShell double-quoted strings/here-strings
  (the `$` triggers variable-expansion parsing) -- always single-quote these paths in
  terminal commands.
