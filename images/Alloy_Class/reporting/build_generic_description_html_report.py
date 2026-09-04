"""
Build an HTML review report for the SMALL_PARTICLE generic-description pilot
(tools/probe_generic_description_v1.py output), joined against the pilot sample
manifest (tools/select_generic_description_sample.py output) for image paths.

Unlike reporting/build_probe_html_report.py, there is no ground truth here (this
is an unsupervised, exploratory pass) -- so this renders the model's free-text
description + structured attributes directly instead of a GT-vs-VLM match cell.
Image rendering, the feedback-portal widget (CSS/JS/banner), and the locked-file
write fallback are reused directly from build_probe_html_report.py rather than
reimplemented, since they don't depend on the GT-classification schema.

Note: the model saw raw (non-burned) images that were deleted after each call
(see probe_generic_description_v1.py) -- this report shows the burned library
copies instead, as a visual reference only.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any

import sys

_REPORTING_DIR = Path(__file__).resolve().parent
if str(_REPORTING_DIR) not in sys.path:
    sys.path.insert(0, str(_REPORTING_DIR))

from build_probe_html_report import (  # type: ignore  # noqa: E402
    _img_tag,
    _dom_safe_id,
    _fmt_json,
    _FEEDBACK_PORTAL_CSS,
    _feedback_portal_assets,
    _write_html_with_rev_fallback,
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text:
            rows.append(json.loads(text))
    return rows


def _load_manifest_by_case_id(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {row["case_id"]: row for row in csv.DictReader(f)}


def _manifest_local_image_columns(row: dict[str, str]) -> tuple[str, str]:
    return (
        (row.get("bright_local_image_file") or row.get("bright_image_file") or row.get("bright_path") or "").strip(),
        (row.get("dark_local_image_file") or row.get("dark_image_file") or row.get("dark_path") or "").strip(),
    )


def _img_tag_for_local_cache(image_path_str: str, report_dir: Path) -> str:
    if not image_path_str:
        return ""
    candidate = Path(image_path_str)
    if candidate.is_absolute():
        uri = candidate.as_uri()
        return f'<img src="{html.escape(uri)}" alt="{html.escape(candidate.name)}" style="max-width:100%;display:block;margin-bottom:6px;border:1px solid #bbb;">'
    if candidate.exists():
        return _img_tag(image_path_str, report_dir)
    return _img_tag(image_path_str, report_dir)


def _attributes_table(parsed: dict[str, Any]) -> str:
    """Renders every parsed field except description (shown separately) in its own
    output-contract order -- schema-agnostic so this works unchanged across prompt
    versions (v1's open descriptors, v2's closed-vocab coarse/fine fields, etc.)."""
    rows = "".join(
        f"<tr><td><b>{html.escape(str(k))}</b></td><td>{html.escape(str(v))}</td></tr>"
        for k, v in parsed.items()
        if k != "description"
    )
    return f'<table style="width:100%;">{rows}</table>'


def _feedback_row(case_id: str, dom_id: str) -> str:
    """Per-case reviewer feedback form: comment only (no agree/disagree or
    corrected-class fields -- there's no classification here to agree/disagree
    with). Posts to the same feedback_portal backend contract as
    build_probe_html_report.py's _feedback_row."""
    case_id_js = html.escape(json.dumps(case_id))
    return (
        f'<tr class="feedback-row" id="feedback-{dom_id}"><td colspan="3">'
        '<div class="feedback-block"><b>Reviewer Feedback</b>'
        f'<label>Comment:<br><textarea id="comment_{dom_id}" rows="2" style="width:100%;"></textarea></label>'
        f'<button onclick="submitFeedback({case_id_js}, \'{dom_id}\')">Submit Feedback</button>'
        f' <span id="feedback-status-{dom_id}" style="color:#16a34a;"></span>'
        "</div></td></tr>"
    )


def _master_submit_assets(case_dom_pairs: list[tuple[str, str]]) -> tuple[str, str]:
    """Returns (banner_html, script_html) for a single top-of-page button that submits
    every case's non-empty comment box in one click, reusing the per-case submitFeedback()
    JS function already emitted by _feedback_portal_assets -- resubmitting a case appends a
    new row, and the backend/consumers already treat the latest row per case_id as current."""
    banner = (
        '<div class="box"><button onclick="submitAllFeedback()">Submit All Feedback</button> '
        '<span id="submit-all-status"></span>'
        "<div style='font-size:11px;color:#6b7280;margin-top:4px;'>Submits every case's comment box "
        "that currently has text -- no need to click each case's own button.</div></div>"
    )
    script = f"""
  <script>
    const ALL_CASE_DOM_IDS = {json.dumps(case_dom_pairs)};

    async function submitAllFeedback() {{
      const statusEl = document.getElementById('submit-all-status');
      let submitted = 0;
      for (const [caseId, domId] of ALL_CASE_DOM_IDS) {{
        const box = document.getElementById(`comment_${{domId}}`);
        if (box && box.value.trim()) {{
          await submitFeedback(caseId, domId);
          submitted++;
        }}
      }}
      statusEl.textContent = `Submitted ${{submitted}} case(s) \u2713`;
    }}
  </script>"""
    return banner, script


def build_report(
    input_jsonl: Path,
    pilot_manifest_csv: Path,
    output_html: Path,
    with_feedback_portal: bool = False,
    feedback_api_base: str = "http://127.0.0.1:8000",
) -> tuple[dict[str, Any], Path]:
    cases = _load_jsonl(input_jsonl)
    manifest_by_case_id = _load_manifest_by_case_id(pilot_manifest_csv)
    report_dir = output_html.resolve().parent

    review_true = 0
    raw_download_ok = 0
    parsed_ok = 0
    case_dom_pairs: list[tuple[str, str]] = []

    body_rows: list[str] = []
    for case in sorted(cases, key=lambda c: str(c.get("case_id") or "")):
        case_id = str(case.get("case_id") or "")
        dom_id = _dom_safe_id(case_id)
        case_dom_pairs.append((case_id, dom_id))
        manifest_row = manifest_by_case_id.get(case_id, {})

        bright_image, dark_image = _manifest_local_image_columns(manifest_row)
        images_html = "".join(_img_tag_for_local_cache(path, report_dir) for path in (bright_image, dark_image) if path)

        parsed = ((case.get("model_call") or {}).get("parsed")) or {}
        description = html.escape(str(parsed.get("description", "")))
        if str(parsed.get("review_required")).strip().lower() in {"true", "1", "yes"}:
            review_true += 1
        if case.get("status") == "ok":
            raw_download_ok += 1
        if parsed:
            parsed_ok += 1

        body_rows.append(
            f'<tr id="case-{dom_id}" data-case-id="{html.escape(case_id)}">'
            f"<td>{html.escape(case_id)}</td>"
            f"<td><div><b>chamber:</b> {html.escape(str(case.get('subentity', '')))}</div>"
            f"<div><b>finebin:</b> {html.escape(str(case.get('finebin', '')))}</div>"
            f"<div><b>size_d:</b> {html.escape(str(case.get('size_d', '')))}</div>"
            f"<div><b>area:</b> {html.escape(str(case.get('area', '')))}</div></td>"
            f"<td>{description or '<i>no description (status=' + html.escape(str(case.get('status', ''))) + ')</i>'}</td>"
            "</tr>"
            f'<tr class="model-calls-row" id="calls-{dom_id}">'
            '<td colspan="3"><div class="case-detail-split">'
            f'<div class="images-panel">{images_html}'
            '<div style="margin-top:6px;color:#6b7280;font-size:11px;">'
            "Burned reference copy shown -- the model was sent the raw (non-burned) source image.</div></div>"
            f'<div class="calls-panel"><b>Structured Attributes</b>{_attributes_table(parsed)}'
            f"<details><summary>raw model_call JSON</summary><pre>{_fmt_json(case.get('model_call'))}</pre></details>"
            "</div>"
            "</div></td>"
            "</tr>"
        )
        if with_feedback_portal:
            body_rows.append(_feedback_row(case_id, dom_id))

    total = len(cases)
    summary = {
        "total_cases": total,
        "status_ok_rate": (raw_download_ok / total) if total else 0.0,
        "parsed_rate": (parsed_ok / total) if total else 0.0,
        "review_required_rate": (review_true / total) if total else 0.0,
    }

    feedback_banner = ""
    feedback_script = ""
    feedback_css = ""
    master_submit_banner = ""
    master_submit_script = ""
    if with_feedback_portal:
        feedback_css = _FEEDBACK_PORTAL_CSS
        feedback_banner, feedback_script = _feedback_portal_assets(run_id=report_dir.name, api_base=feedback_api_base)
        master_submit_banner, master_submit_script = _master_submit_assets(case_dom_pairs)

    html_doc = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Generic Description Pilot Review (SMALL_PARTICLE)</title>
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
    .case-detail-split {{ display: flex; align-items: flex-start; gap: 12px; }}
    .images-panel {{ flex: 0 0 300px; max-width: 300px; overflow: hidden; }}
    .calls-panel {{ flex: 1 1 auto; min-width: 0; overflow-x: auto; border-left: 1px solid #d1d5db; padding-left: 12px; }}
{feedback_css}
  </style>
</head>
<body>
  <h1>Generic Description Pilot Review (SMALL_PARTICLE)</h1>
  <div class=\"box\"><pre>{html.escape(json.dumps(summary, indent=2))}</pre></div>
  {master_submit_banner}
  {feedback_banner}
  <table>
    <thead>
      <tr>
        <th>Case</th>
        <th>Metadata</th>
        <th>Description</th>
      </tr>
    </thead>
    <tbody>
      {''.join(body_rows)}
    </tbody>
  </table>
  {feedback_script}
  {master_submit_script}
</body>
</html>
"""

    written_path = _write_html_with_rev_fallback(html_doc, output_html)
    return summary, written_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build HTML review report for the generic-description pilot")
    parser.add_argument("--input-jsonl", required=True, help="generic_description_v1_<timestamp>.jsonl")
    parser.add_argument("--pilot-manifest-csv", required=True, help="generic_description_pilot_manifest.csv")
    parser.add_argument("--output-html", required=True)
    parser.add_argument("--with-feedback-portal", action="store_true")
    parser.add_argument("--feedback-api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--input-manifest-csv", default="", help="Optional pair-level manifest CSV keyed by case_id. If omitted, the pilot manifest is used.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary, written_path = build_report(
        input_jsonl=Path(args.input_jsonl),
        pilot_manifest_csv=Path(args.input_manifest_csv) if args.input_manifest_csv else Path(args.pilot_manifest_csv),
        output_html=Path(args.output_html),
        with_feedback_portal=args.with_feedback_portal,
        feedback_api_base=args.feedback_api_base,
    )
    print(json.dumps(summary, indent=2))
    print(str(written_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
