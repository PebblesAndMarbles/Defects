# Handoff: add a feedback portal to the probe review HTML report

**Date:** 2026-08-29
**For:** the feedback-portal agent (HTML report + local Flask callback + CSV pattern)
**Related docs (read these first for context on the pipeline this report comes from):**
[PROBE_OUTPUT_SCORING_AND_HTML_REPORT_GAP.md](PROBE_OUTPUT_SCORING_AND_HTML_REPORT_GAP.md),
[HANDOFF_PROBE_SCORING_AND_HTML_REPORTING.md](HANDOFF_PROBE_SCORING_AND_HTML_REPORTING.md)

## STATUS: implemented 2026-08-29 -- built and smoke-tested end to end

Everything described in the original handoff below (kept as-is beneath this section for
context) has been built. Summary for whoever picks this up next:

- **Generator flag:** `reporting/build_probe_html_report.py` now takes
  `--with-feedback-portal` (opt-in, default off) and `--feedback-api-base` (default
  `http://127.0.0.1:8000`). Each case's summary/detail row pair now carries
  `id="case-{dom_id}"` / `id="calls-{dom_id}"` / `data-case-id="{case_id}"`
  (`dom_id` = case_id sanitized to `[A-Za-z0-9_-]`), and when the flag is set a third
  `<tr class="feedback-row" id="feedback-{dom_id}">` is emitted per case with the
  reviewer form (agree/disagree select, corrected-class select, comment textarea,
  submit button), plus a page-level "Recent Feedback" panel and inline `<script>` at
  the bottom of the document.
- **Backend:** `reporting/feedback_portal/` (backend/main.py, run_portal.ps1/.cmd,
  requirements.txt, README.txt) -- a local Flask server exposing only
  `POST /submit_feedback` and `GET /feedback` (it does **not** serve the HTML report
  itself; the report is opened directly via `file://`). CSV columns:
  `case_id, reviewer, submitted_at_utc, agrees_with_vlm, corrected_class, comment,
  run_id` -- matches the schema suggested below plus `run_id` for traceability across
  regenerated runs. Appends one row per submission (never rewrites), one shared CSV
  (not per-user). Bound to `127.0.0.1` only (no auth on this server, so no LAN
  exposure). Default `DATA_FILE` points at
  `outputs/probes/scored/beep_lexicon_v1_20260828_full31/probe_review_feedback.csv`;
  override per-run via `-DataFile <path>` on `run_portal.ps1` or the `FEEDBACK_DATA_FILE`
  env var -- **do not edit the constant in main.py per run.**
- **How to run it:**
  ```powershell
  # 1. Regenerate the report with the widget embedded (produces a NEW html file,
  #    does not touch the existing static probe_review.html snapshot):
  python reporting/build_probe_html_report.py `
    --input-jsonl outputs/probes/scored/beep_lexicon_v1_20260828_full31/probe_scored_cases.jsonl `
    --output-html outputs/probes/scored/beep_lexicon_v1_20260828_full31/probe_review_feedback_portal.html `
    --with-feedback-portal

  # 2. Start the backend (leave running in the background while reviewing):
  reporting/feedback_portal/run_portal.cmd
  # or: reporting/feedback_portal/run_portal.ps1 -DataFile <path to a different run's feedback.csv>

  # 3. Open probe_review_feedback_portal.html directly in a browser (file://) and use
  #    the per-case forms. Each submission appends a row to probe_review_feedback.csv
  #    next to that run's probe_scored_cases.jsonl.
  ```
  The interpreter used for local smoke-testing (has Flask 3.0.0 installed):
  `%USERPROFILE%\My Programs\SQLPathFinder3\Python3\python.exe` -- `python`/`py` are not
  on PATH directly in this environment (only the Microsoft Store app-execution alias
  stub, which errors if invoked with no Python installed via the Store).
- **Verified 2026-08-29:** regenerated `probe_review_feedback_portal.html` from the
  full31 run's `probe_scored_cases.jsonl` (31 cases, summary counts unchanged from the
  original run). Started `backend/main.py`, confirmed `GET /` status endpoint,
  `POST /submit_feedback` (wrote a row), and `GET /feedback` (read it back) all work
  against the UNC path; smoke-test row was then deleted from the CSV (the file no
  longer exists on disk until a real reviewer submits -- it's created on first write).
- **Not done / open for next agent:** no join script yet for
  `probe_review_feedback.csv` <-> `probe_scored_cases.jsonl` by `case_id` (see "Round-trip
  back to the coding agent" below) -- deferred given the low row count (31 cases);
  reading both files directly may be enough.

---

## What this is for


The user wants to review VLM classification results (images + prompt reasoning + evidence
checks, already rendered in an existing HTML report) and leave feedback directly in that
same page, without a separate review tool. Feedback needs to land in a CSV the user (and
the main coding agent) can read afterward to see what was flagged, and it needs to work on
this workspace's shared UNC path.

## Where the most recent HTML report is

Most recent / most complete instance (31 cases: 5 known FN + 4 particle controls + 1 edge
case + all 21 known v13 false-positive cases, scored against adjudicated ground truth):

```
\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\outputs\probes\scored\beep_lexicon_v1_20260828_full31\probe_review.html
```

Its underlying data, in the same folder:
- `probe_scored_cases.jsonl` -- full nested record per case (images, model call(s), GT, VLM verdict, match flags) -- **this is what `probe_review.html` is rendered from.**
- `probe_scored_rows.csv` -- flat, one row per case, same data as above but denormalized for spreadsheet use.
- `probe_score_summary.json` -- aggregate metrics (confusion counts, FN/FP rates, etc.).

**This file will be regenerated as new prompt iterations get tested** -- it is a
point-in-time snapshot from one run, not a permanently maintained page. The report is
produced by a reusable generator script (see below), and that's almost certainly where
the feedback UI should actually be added, not by hand-editing this one static HTML file.

## Canonical report generator (where to add the feedback UI)

```
images/Alloy_Class/reporting/build_probe_html_report.py
```

Run as:
```bash
python reporting/build_probe_html_report.py --input-jsonl <probe_scored_cases.jsonl> --output-html <probe_review.html>
```

`build_report()` (the function that emits the HTML) currently renders one **two-row pair**
per case: a summary row (`<tr>`) with case_id / category / GT-vs-VLM cells, followed by a
detail row (`<tr class="model-calls-row">`) with the images, evidence-check comparison, and
the full model call(s) text. **Case rows do not currently carry a stable DOM identifier**
(no `id=` or `data-case-id` attribute) -- the case_id is only present as plain text in the
first `<td>`. Adding something like `id="case-{case_id}"` or `data-case-id="{case_id}"` to
both rows of each pair would be the natural hook point for attaching a feedback
widget/form per case and for the JS to know which case a submission belongs to.

**Recommendation:** integrate the feedback widget into `build_probe_html_report.py` itself
(new HTML/JS emitted alongside each case's existing rows, using `case_id` as the row key),
not as a one-off patch to the current static `probe_review.html`. That way every future
report this script generates automatically has the feedback portal, instead of it being
lost the next time someone reruns the generator.

## Target CSV for feedback

**Do not write feedback into `probe_scored_rows.csv`.** That file is the scorer's own
output and this project's convention (see `docs/PROMPT_ITERATION_REGISTRY.md`) is to treat
scored-row CSVs as immutable once a run is finalized -- a rescore should produce a new
file, not mutate an old one in place. Feedback should go into a **separate CSV**, joined
back to the scored data by `case_id`:

```
outputs/probes/scored/beep_lexicon_v1_20260828_full31/probe_review_feedback.csv
```

Suggested minimal schema (adjust as needed for whatever the feedback form actually
collects):

| column | notes |
|---|---|
| `case_id` | join key back to `probe_scored_cases.jsonl` / `probe_scored_rows.csv` |
| `reviewer` | free text or username, whatever's available locally |
| `submitted_at_utc` | ISO timestamp |
| `agrees_with_vlm` | bool/yes-no -- does the reviewer agree with `defect_coarse_class` |
| `corrected_class` | optional override (particle / possible_beep / indeterminate) if the reviewer disagrees |
| `comment` | free text |

The Flask backend should be safe to call repeatedly for the same `case_id` (e.g. append a
new row each submission rather than requiring in-place update, so nothing is lost if the
reviewer changes their mind later -- the consuming side can just take the latest row per
`case_id`).

## Round-trip back to the coding agent

Once `probe_review_feedback.csv` has entries, the plan is: the user tells the coding agent
review is ready, the agent reads `probe_review_feedback.csv`, joins it to
`probe_scored_cases.jsonl` by `case_id`, and reviews disagreements/comments the same way
prompt-iteration feedback has been handled all session (image inspection + rationale
review, per the pattern in `alloy_class_v13_v14_fp_diagnosis.md` repo memory). No specific
tooling for this join exists yet -- whoever picks this up next can decide whether a small
script is worth writing or whether reading both files directly is enough given the low
row counts here (31 cases).

## Open questions for the feedback-portal agent to decide

- Exact feedback form fields/UI (table above is a minimum, not a spec).
- Where the local Flask server itself runs from / how it's started (follow this agent's
  own established pattern for that, nothing project-specific here).
- Whether `build_probe_html_report.py` needs a new CLI flag to opt in/out of embedding the
  feedback widget (e.g. `--with-feedback-portal`), since not every report render is meant
  for interactive review (some are just quick sanity-check dumps during iteration).
