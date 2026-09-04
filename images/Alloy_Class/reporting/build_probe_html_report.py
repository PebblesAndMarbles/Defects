"""
Build an HTML review report from a scored, normalized probe/run output file
(`probe_scored_cases.jsonl`, written by tools/score_probe_run.py).

Renders one summary row per case (Case/Category/Coarse/Evidence/Checks/Verdict Detail)
followed by a detail row split into two side-by-side panels -- images on the left
(width-capped so they can't bleed into the right panel), a <details> block per
`model_calls` entry on the right (looped over -- never hardcodes call count or names, so
this works unchanged whether a case has 1 call, 2 calls, or N calls, and whether a call
was skipped/gated). The "Checks" column shows GT (adjudication CSV) alongside the VLM's
own evidence_check_* verdicts, when the VLM emits them. A summary block at the top
mirrors reporting/build_stage_ab_html_report.py's style plus the FN/FP rates now that GT
is joined.
"""

from __future__ import annotations

import argparse
import html
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text:
            rows.append(json.loads(text))
    return rows


def _fmt_json(value: Any) -> str:
    return html.escape(json.dumps(value, indent=2)) if value is not None else "null"


def _dom_safe_id(raw: str) -> str:
    """Sanitize a case_id for use as an HTML id/JS string suffix (case_ids may contain chars unsafe for DOM ids)."""
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in raw) or "case"


def _img_tag(image_path_str: str, report_dir: Path) -> str:
    if not image_path_str:
        return ""
    image_path = Path(image_path_str)
    if not image_path.exists():
        return html.escape(image_path.name or image_path_str)
    try:
        rel = os.path.relpath(str(image_path.resolve()), str(report_dir)).replace("\\", "/")
        src = html.escape(rel)
    except ValueError:
        # Cross-mount (e.g. C:\ vs UNC): fall back to absolute file URI
        src = html.escape(image_path.resolve().as_uri())
    # width is capped relative to the images panel (not a fixed px) so it can never bleed into the calls panel
    return f'<img src="{src}" alt="{html.escape(image_path.name)}" style="max-width:100%;display:block;margin-bottom:6px;border:1px solid #bbb;">'


def _match_cell(gt: str, vlm: str, match: bool | None) -> str:
    gt_disp = html.escape(gt or "<none>")
    vlm_disp = html.escape(vlm or "<none>")
    if match is None:
        color = "#9ca3af"  # gray: no GT to compare
        label = "no_gt"
    elif match:
        color = "#16a34a"  # green
        label = "match"
    else:
        color = "#dc2626"  # red
        label = "mismatch"
    return (
        f'<div style="color:{color};font-weight:600;">{label}</div>'
        f"<div><b>gt:</b> {gt_disp}</div>"
        f"<div><b>vlm:</b> {vlm_disp}</div>"
    )


def _evidence_checks_cell(gt_evidence_checks: dict[str, Any], vlm_evidence_checks: dict[str, Any]) -> str:
    """GT (from adjudication CSV) side-by-side with the VLM's own evidence_check_* verdicts (from the last call's parsed_json), when the VLM emits them."""
    rows = []
    for key in ("inset_surface_lines", "boundary_conformance", "sunken_residual"):
        gt_val = html.escape(str(gt_evidence_checks.get(key, "") or "<none>"))
        vlm_val = html.escape(str(vlm_evidence_checks.get(key) or "<none>"))
        rows.append(f"<b>{key}:</b><br>gt={gt_val} / vlm={vlm_val}<br><br>")
    return "".join(rows)


def _model_calls_detail(model_calls: list[dict[str, Any]]) -> str:
    blocks = []
    for call in model_calls:
        label = html.escape(str(call.get("call_label", "")))
        skipped = bool(call.get("skipped"))
        skip_badge = f' <span style="color:#b45309;">[SKIPPED: {html.escape(str(call.get("skip_reason") or ""))}]</span>' if skipped else ""
        raw_text = html.escape(str(call.get("raw_text") or ""))
        parsed = call.get("parsed_json")
        blocks.append(
            f"<details open><summary>{label}{skip_badge}</summary>"
            f"<div><b>prompt_version:</b> {html.escape(str(call.get('prompt_version') or ''))}</div>"
            f"<div><b>parsed_json:</b><pre>{_fmt_json(parsed)}</pre></div>"
            f"<div><b>raw_text:</b><pre>{raw_text}</pre></div>"
            "</details>"
        )
    return "".join(blocks)


def _feedback_row(case_id: str, dom_id: str) -> str:
    """Per-case reviewer feedback form row. POSTs to the feedback_portal backend (see reporting/feedback_portal/)."""
    # html.escape the JSON literal too: it's embedded inside a double-quoted HTML
    # attribute, and JSON strings themselves contain literal double quotes that
    # would otherwise break out of the attribute if case_id ever had odd chars.
    case_id_js = html.escape(json.dumps(case_id))
    return (
        f'<tr class="feedback-row" id="feedback-{dom_id}"><td colspan="5">'
        '<div class="feedback-block"><b>Reviewer Feedback</b>'
        f'<label>Agrees with VLM verdict?<select id="agrees_{dom_id}">'
        '<option value="">-- select --</option><option value="yes">Yes</option><option value="no">No</option>'
        "</select></label>"
        f'<label>Corrected class (if disagreeing):<select id="corrected_{dom_id}">'
        '<option value="">-- n/a --</option><option value="particle">particle</option>'
        '<option value="possible_beep">possible_beep</option><option value="indeterminate">indeterminate</option>'
        "</select></label>"
        f'<label>Comment:<br><textarea id="comment_{dom_id}" rows="2" style="width:100%;"></textarea></label>'
        f'<button onclick="submitFeedback({case_id_js}, \'{dom_id}\')">Submit Feedback</button>'
        f' <span id="feedback-status-{dom_id}" style="color:#16a34a;"></span>'
        "</div></td></tr>"
    )


_FEEDBACK_PORTAL_CSS = """
    .feedback-row td { background: #fefce8; }
    .feedback-block label { display: block; margin-top: 6px; font-size: 13px; }
    .feedback-block select, .feedback-block textarea { width: 100%; max-width: 420px; }
    .feedback-block button { margin-top: 8px; }
    .offline-warning { background: #fff3cd; border: 1px solid #ffe08a; padding: 10px; border-radius: 6px; margin-bottom: 14px; }
    .feedback-summary-entry { background: #e8f0fb; margin-bottom: 6px; padding: 6px; border-radius: 4px; font-size: 13px; }
"""


def _feedback_portal_assets(run_id: str, api_base: str) -> tuple[str, str]:
    """Returns (banner_html, script_html) for the feedback portal widget. Backend contract: POST /submit_feedback, GET /feedback (reporting/feedback_portal/backend/main.py)."""
    banner = (
        '<div class="box offline-warning">Reviewer feedback requires the local feedback-portal '
        "server to be running in the background (see reporting/feedback_portal/README.txt) -- "
        "start it via run_portal.cmd / run_portal.ps1, then use the per-case forms below. "
        "This report itself can still be viewed normally without it.</div>"
        '<div class="box"><b>Recent Feedback</b><div id="feedback-display">Loading...</div></div>'
    )
    script = f"""
  <script>
    const REPORT_RUN_ID = {json.dumps(run_id)};
    // apiBase is a fixed absolute URL: this report is opened via file://, so
    // fetch() must target the backend directly rather than same-origin.
    // (Do not remove -- this is the fix for the file:// vs http:// fetch
    // failure documented in the feedback-portal template's BUG-001.)
    const apiBase = {json.dumps(api_base)};

    function getReviewerName() {{
      let name = localStorage.getItem('probe_review_reviewer') || '';
      if (!name) {{
        name = prompt('Enter your name (used for all feedback submissions on this report):') || '';
        if (name) localStorage.setItem('probe_review_reviewer', name);
      }}
      return name;
    }}

    async function submitFeedback(caseId, domId) {{
      const reviewer = getReviewerName();
      if (!reviewer) {{ alert('Reviewer name is required.'); return; }}
      const agrees = document.getElementById(`agrees_${{domId}}`)?.value || '';
      const corrected = document.getElementById(`corrected_${{domId}}`)?.value || '';
      const comment = document.getElementById(`comment_${{domId}}`).value;
      const statusEl = document.getElementById(`feedback-status-${{domId}}`);
      const payload = {{
        case_id: caseId,
        reviewer: reviewer,
        agrees_with_vlm: agrees,
        corrected_class: corrected,
        comment: comment,
        run_id: REPORT_RUN_ID
      }};
      try {{
        const resp = await fetch(`${{apiBase}}/submit_feedback`, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(payload)
        }});
        if (!resp.ok) throw new Error('bad response');
        statusEl.textContent = 'Submitted \u2713';
        loadFeedback();
      }} catch (e) {{
        statusEl.textContent = '';
        alert('Submission failed. Is the feedback-portal server running? See banner at top of page.');
      }}
    }}

    async function loadFeedback() {{
      const list = document.getElementById('feedback-display');
      if (!list) return;
      try {{
        const resp = await fetch(`${{apiBase}}/feedback`);
        const data = await resp.json();
        if (!data.length) {{
          list.innerHTML = '<em>No feedback yet.</em>';
          return;
        }}
        list.innerHTML = '';
        data.slice(-15).reverse().forEach(row => {{
          const div = document.createElement('div');
          div.className = 'feedback-summary-entry';
          div.innerHTML = `<b>${{row.case_id}}</b> [agrees=${{row.agrees_with_vlm || 'n/a'}}]`
            + (row.corrected_class ? ` -> corrected: ${{row.corrected_class}}` : '')
            + `<br><i>${{row.comment || ''}}</i><br><small>By: ${{row.reviewer}} | ${{row.submitted_at_utc}}</small>`;
          list.appendChild(div);
        }});
      }} catch (e) {{
        list.innerHTML = '<em>Feedback server not reachable -- start it via reporting/feedback_portal/run_portal.cmd.</em>';
      }}
    }}

    loadFeedback();
  </script>"""
    return banner, script


def _write_html_with_rev_fallback(html_doc: str, output_html: Path) -> Path:
    """
    Write to output_html; if that path is locked (PermissionError -- e.g. a
    previous version of this same report is still open in a browser tab, which
    on this UNC share can hold a write lock), fall back to an auto-incrementing
    "_revN" filename instead of failing the whole run.
    """
    try:
        output_html.write_text(html_doc, encoding="utf-8")
        return output_html
    except PermissionError:
        rev = 2
        while True:
            candidate = output_html.with_name(f"{output_html.stem}_rev{rev}{output_html.suffix}")
            try:
                candidate.write_text(html_doc, encoding="utf-8")
                return candidate
            except PermissionError:
                rev += 1


def build_report(
    input_jsonl: Path,
    output_html: Path,
    with_feedback_portal: bool = False,
    feedback_api_base: str = "http://127.0.0.1:8000",
) -> tuple[dict[str, Any], Path]:
    cases = _load_jsonl(input_jsonl)
    report_dir = output_html.resolve().parent

    class_counts: Counter[str] = Counter()
    confusion_counts: Counter[str] = Counter()
    review_true = 0

    body_rows: list[str] = []
    for case in sorted(cases, key=lambda c: str(c.get("case_id") or c.get("vlm_pair_key") or "")):
        final_verdict = case.get("final_verdict") or {}
        vlm_coarse_class = str(final_verdict.get("coarse_class", ""))
        vlm_evidence = str(final_verdict.get("blocked_etch_evidence", ""))
        review_required = final_verdict.get("review_required")

        class_counts[vlm_coarse_class or "<missing>"] += 1
        confusion_counts[case.get("confusion_label", "no_gt")] += 1
        if str(review_required).strip().lower() in {"true", "1", "yes"}:
            review_true += 1

        images_html = "".join(_img_tag(img.get("path", ""), report_dir) for img in case.get("images") or [])
        vlm_evidence_checks = final_verdict.get("evidence_checks") or {}

        case_id = str(case.get("case_id") or case.get("vlm_pair_key") or "")
        dom_id = _dom_safe_id(case_id)

        body_rows.append(
            f'<tr id="case-{dom_id}" data-case-id="{html.escape(case_id)}">'
            f"<td>{html.escape(case_id)}</td>"
            f"<td>{html.escape(str(case.get('category', '')))}</td>"
            f"<td>{_match_cell(case.get('gt_coarse_class', ''), vlm_coarse_class, case.get('coarse_class_match'))}</td>"
            f"<td>{_match_cell(case.get('gt_blocked_etch_evidence', ''), vlm_evidence, case.get('evidence_match'))}</td>"
            f"<td><div><b>confidence:</b> {html.escape(str(final_verdict.get('confidence', '')))}</div>"
            f"<div><b>review_required:</b> {html.escape(str(review_required))}</div>"
            f"<div><b>confusion:</b> {html.escape(str(case.get('confusion_label', '')))}</div></td>"
            "</tr>"
            f'<tr class="model-calls-row" id="calls-{dom_id}">'
            '<td colspan="5"><div class="case-detail-split">'
            f'<div class="images-panel">{images_html}'
            f'<div class="checks-block">{_evidence_checks_cell(case.get("gt_evidence_checks") or {}, vlm_evidence_checks)}</div>'
            "</div>"
            f'<div class="calls-panel"><b>Model Calls</b>{_model_calls_detail(case.get("model_calls") or [])}</div>'
            "</div></td>"
            "</tr>"
        )
        if with_feedback_portal:
            body_rows.append(_feedback_row(case_id, dom_id))

    total = len(cases)
    summary = {
        "total_cases": total,
        "review_required_rate": (review_true / total) if total else 0.0,
        "vlm_coarse_class_counts": dict(class_counts),
        "confusion_counts": dict(confusion_counts),
    }

    feedback_banner = ""
    feedback_script = ""
    feedback_css = ""
    if with_feedback_portal:
        feedback_css = _FEEDBACK_PORTAL_CSS
        feedback_banner, feedback_script = _feedback_portal_assets(run_id=report_dir.name, api_base=feedback_api_base)

    html_doc = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Probe Run Review Report</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 22px; background: #f8f9fb; color: #1f2937; }}
    h1 {{ margin-bottom: 6px; }}
    .box {{ background: white; border: 1px solid #d1d5db; padding: 10px; margin-bottom: 14px; }}
    table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; vertical-align: top; background: white; }}
    th {{ background: #e5eefb; }}
    pre {{ white-space: pre-wrap; word-break: break-word; font-size: 12px; }}
    details summary {{ cursor: pointer; color: #1d4ed8; }}
    .model-calls-row td {{ background: #f3f4f6; }}
    .model-calls-row details {{ margin-top: 6px; }}
    .case-detail-split {{ display: flex; align-items: flex-start; gap: 12px; }}
    .images-panel {{ flex: 0 0 300px; max-width: 300px; overflow: hidden; }}
    .checks-block {{ margin-top: 8px; }}
    .calls-panel {{ flex: 1 1 auto; min-width: 0; overflow-x: auto; border-left: 1px solid #d1d5db; padding-left: 12px; }}
{feedback_css}
  </style>
</head>
<body>
  <h1>Probe Run Review Report</h1>
  <div class=\"box\"><pre>{html.escape(json.dumps(summary, indent=2))}</pre></div>
  {feedback_banner}
  <table>
    <thead>
      <tr>
        <th>Case</th>
        <th>Category</th>
        <th>Coarse</th>
        <th>Evidence</th>
        <th>Verdict Detail</th>
      </tr>
    </thead>
    <tbody>
      {''.join(body_rows)}
    </tbody>
  </table>
  {feedback_script}
</body>
</html>
"""

    written_path = _write_html_with_rev_fallback(html_doc, output_html)
    return summary, written_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build HTML review report from probe_scored_cases.jsonl")
    parser.add_argument("--input-jsonl", required=True, help="probe_scored_cases.jsonl from tools/score_probe_run.py")
    parser.add_argument("--output-html", required=True)
    parser.add_argument(
        "--with-feedback-portal",
        action="store_true",
        help="Embed the reviewer feedback widget (per-case forms + recent-feedback panel). "
        "Requires reporting/feedback_portal/ backend running locally for submissions to work; "
        "not needed for quick sanity-check report dumps during iteration.",
    )
    parser.add_argument(
        "--feedback-api-base",
        default="http://127.0.0.1:8000",
        help="Base URL the feedback widget POSTs/GETs to (default: local feedback_portal backend).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary, written_path = build_report(
        input_jsonl=Path(args.input_jsonl),
        output_html=Path(args.output_html),
        with_feedback_portal=args.with_feedback_portal,
        feedback_api_base=args.feedback_api_base,
    )
    print(json.dumps(summary, indent=2))
    if written_path != Path(args.output_html):
        print(f"NOTE: requested output path was locked; wrote to {written_path.resolve()} instead")
    else:
        print(str(written_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
