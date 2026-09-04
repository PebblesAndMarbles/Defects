"""
Build a static HTML report of BEEP-misclassified cases from the first five
rapid-labeling tranches.

This report is read-only: it shows only cases where the ground-truth reviewer
label is BEEP, joined with the tranche manifests for image paths and factory
metadata. The intended review set is tranche_0001 through tranche_0005.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import sys

REPORTING_DIR = Path(__file__).resolve().parent
ALLY_CLASS_DIR = REPORTING_DIR.parent
BE_ROOT = ALLY_CLASS_DIR.parent.parent
if str(REPORTING_DIR) not in sys.path:
    sys.path.insert(0, str(REPORTING_DIR))

from build_beep_labeling_report import (  # type: ignore  # noqa: E402
    _dom_safe_id,
    _img_tag,
    _write_html_with_rev_fallback,
)
from build_probe_html_report import (  # type: ignore  # noqa: E402
  _FEEDBACK_PORTAL_CSS,
  _feedback_portal_assets,
)

BE_SUFFIX = "beep_evidence"
ALLOWED_TRANCHES = {f"tranche_{idx:04d}" for idx in range(1, 6)}
DEFAULT_DISK_IMAGE_MANIFEST = BE_ROOT / "outputs" / "defects" / "DEFECT_COORDINATES_EXTENDED_IMAGES.csv"


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_ground_truth(path: Path) -> list[dict[str, str]]:
    rows = [row for row in _load_csv(path) if row.get("tranche_id") in ALLOWED_TRANCHES]
    rows.sort(key=lambda row: (str(row.get("pair_key") or ""), str(row.get("submitted_at_utc") or "")))

    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        pair_key = str(row.get("pair_key") or "")
        if not pair_key:
            continue
        existing = deduped.get(pair_key)
        if existing is None or str(row.get("submitted_at_utc") or "") >= str(existing.get("submitted_at_utc") or ""):
            deduped[pair_key] = row

    return [row for row in deduped.values() if row.get("label") == "BEEP"]


def _load_case_manifests(beep_evidence_dir: Path) -> dict[str, dict[str, str]]:
    combined: dict[str, dict[str, str]] = {}
    for tranche_idx in range(1, 6):
        path = beep_evidence_dir / f"tranche_{tranche_idx:04d}_cases.csv"
        for row in _load_csv(path):
            pair_key = str(row.get("pair_key") or "")
            if pair_key:
                combined[pair_key] = row
    return combined


def _normalize_join_value(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _pair_key_from_values(wafer_key: Any, inspection_time: Any, defect_id: Any) -> str:
    raw = str(inspection_time or "").strip()
    try:
        insp = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            insp = datetime.fromisoformat(raw)
        except ValueError:
            return ""
    insp_str = insp.strftime("%Y%m%d_%H%M%S")
    return f"{_normalize_join_value(wafer_key)}_{insp_str}_{_normalize_join_value(defect_id)}"


def _load_disk_image_manifest(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}

    disk_by_pair_key: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            pair_key = _pair_key_from_values(row.get("WAFER_KEY"), row.get("INSPECTION_TIME"), row.get("DEFECT_ID"))
            if not pair_key:
                continue

            entry = disk_by_pair_key.setdefault(pair_key, {})
            image_id = _normalize_join_value(row.get("IMAGE_ID"))
            image_path = str(row.get("LOCAL_IMAGE_FILE") or row.get("local_path") or "").strip()
            if image_id == "2" and image_path:
                entry["disk_bright_image_path"] = image_path
            elif image_id == "3" and image_path:
                entry["disk_dark_image_path"] = image_path

            for source_key, target_key in (
                ("QUERY_SITE", "disk_query_site"),
                ("LOT", "disk_lot"),
                ("LAYER", "disk_layer"),
                ("SUBENTITY", "disk_subentity"),
            ):
                value = str(row.get(source_key) or "").strip()
                if value and not entry.get(target_key):
                    entry[target_key] = value

    return disk_by_pair_key


def _group_count_html(title: str, counts: Counter[str]) -> str:
    if not counts:
        return f'<div class="summary-block"><h2>{html.escape(title)}</h2><div class="empty-note">No data</div></div>'

    rows = "".join(
        f"<tr><td>{html.escape(str(key))}</td><td>{count}</td></tr>"
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))
    )
    return (
        f'<div class="summary-block"><h2>{html.escape(title)}</h2>'
        f"<table class=\"summary-table\"><thead><tr><th>Group</th><th>Count</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )


def _disk_image_block_html(case: dict[str, Any], report_dir: Path) -> str:
    bright_path = str(case.get("disk_bright_image_path") or "")
    dark_path = str(case.get("disk_dark_image_path") or "")
    if not bright_path and not dark_path:
        return ""

    bright = _img_tag(bright_path, report_dir, "disk bright") if bright_path else '<div class="missing-img">no disk bright image</div>'
    dark = _img_tag(dark_path, report_dir, "disk dark") if dark_path else '<div class="missing-img">no disk dark image</div>'
    meta_rows = "".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>"
        for label, value in [
            ("disk_query_site", case.get("disk_query_site", "")),
            ("disk_lot", case.get("disk_lot", "")),
            ("disk_layer", case.get("disk_layer", "")),
            ("disk_subentity", case.get("disk_subentity", "")),
            ("disk_bright_image_path", bright_path),
            ("disk_dark_image_path", dark_path),
        ]
        if str(value) != ""
    )

    return f"""
      <details class="disk-image-details">
        <summary>Disk image references</summary>
        <div class="case-images" style="margin-top:10px;">
          <div class="image-block">
            {bright}
            <div class="image-caption">disk bright</div>
          </div>
          <div class="image-block">
            {dark}
            <div class="image-caption">disk dark</div>
          </div>
        </div>
        <table class="meta-table" style="margin-top:10px;">
          <tbody>
            {meta_rows}
          </tbody>
        </table>
      </details>
    """


def _case_card_html(case: dict[str, Any], report_dir: Path) -> str:
    pair_key = str(case.get("pair_key") or "")
    dom_id = _dom_safe_id(pair_key)
    bright = _img_tag(str(case.get("bright_image_path") or ""), report_dir, "bright")
    dark = _img_tag(str(case.get("dark_image_path") or ""), report_dir, "dark")
    disk_block = _disk_image_block_html(case, report_dir)

    fields = [
        ("pair_key", pair_key),
        ("wafer_key", case.get("wafer_key", "")),
        ("inspection_time", case.get("inspection_time", "")),
        ("lot", case.get("lot", "")),
        ("defect_id", case.get("defect_id", "")),
        ("layer", case.get("layer", "")),
        ("subentity", case.get("subentity", "")),
        ("tranche_id", case.get("tranche_id", "")),
        ("reviewer", case.get("reviewer", "")),
        ("submitted_at_utc", case.get("submitted_at_utc", "")),
        ("label", case.get("label", "")),
        ("factory_class", case.get("factory_class", "")),
    ]
    meta_rows = "".join(
        f"<tr><th>{html.escape(name)}</th><td>{html.escape(str(value))}</td></tr>"
        for name, value in fields
        if str(value) != ""
    )

    case_id_js = html.escape(json.dumps(pair_key))

    return f"""
  <section class="case-card" id="case-{dom_id}">
    <div class="case-header">
      <div class="case-title">{html.escape(pair_key)}</div>
      <div class="case-badge">reviewer labeled BEEP, factory class SMALL_PARTICLE</div>
    </div>
    <div class="case-body">
      <div class="case-images">
        <div class="image-block">
          {bright}
          <div class="image-caption">bright</div>
        </div>
        <div class="image-block">
          {dark}
          <div class="image-caption">dark</div>
        </div>
      </div>
      <table class="meta-table">
        <tbody>
          {meta_rows}
        </tbody>
      </table>
      {disk_block}
      <div class="disposition-panel">
        <div class="disposition-title">Disposition</div>
        <label>Agrees with this BEEP disposition?
          <select id="agrees_{dom_id}">
            <option value="">-- select --</option>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </label>
        <label>Corrected class (if disagreeing)
          <select id="corrected_{dom_id}">
            <option value="">-- n/a --</option>
            <option value="beep">beep</option>
            <option value="small_particle">small_particle</option>
            <option value="indeterminate">indeterminate</option>
          </select>
        </label>
        <label>Comment:<br>
          <textarea id="comment_{dom_id}" rows="2"></textarea>
        </label>
        <button onclick="submitFeedback({case_id_js}, '{dom_id}')">Submit Disposition</button>
        <span id="feedback-status-{dom_id}" class="feedback-status"></span>
      </div>
    </div>
  </section>
"""


def build_report(
    ground_truth_csv: Path,
    output_html: Path,
    beep_evidence_dir: Path,
    disk_image_manifest_csv: Path | None = None,
    with_feedback_portal: bool = True,
    feedback_api_base: str = "http://127.0.0.1:8000",
) -> tuple[dict[str, Any], Path]:
    gt_rows = _load_ground_truth(ground_truth_csv)
    manifest_by_pair_key = _load_case_manifests(beep_evidence_dir)
    disk_manifest_by_pair_key = _load_disk_image_manifest(disk_image_manifest_csv)

    joined_rows: list[dict[str, Any]] = []
    for row in gt_rows:
        pair_key = str(row.get("pair_key") or "")
        manifest_row = manifest_by_pair_key.get(pair_key, {})
        merged = dict(manifest_row)
        merged.update(row)
        merged.update(disk_manifest_by_pair_key.get(pair_key, {}))
        joined_rows.append(merged)

    joined_rows.sort(
        key=lambda row: (
            str(row.get("tranche_id") or ""),
            str(row.get("inspection_time") or ""),
            str(row.get("wafer_key") or ""),
            str(row.get("defect_id") or ""),
        )
    )

    total_cases = len(joined_rows)
    tranche_counts = Counter(str(row.get("tranche_id") or "") for row in joined_rows)
    subentity_counts = Counter(str(row.get("subentity") or "") for row in joined_rows)
    cases_with_disk_images = sum(1 for row in joined_rows if row.get("disk_bright_image_path") or row.get("disk_dark_image_path"))

    summary_json = {
        "total_misclassified_cases": total_cases,
        "tranche_counts": dict(sorted(tranche_counts.items())),
        "subentity_counts": dict(sorted(subentity_counts.items(), key=lambda item: (-item[1], item[0]))),
        "cases_with_disk_images": cases_with_disk_images,
        "disk_image_manifest_csv": str(disk_image_manifest_csv) if disk_image_manifest_csv else "",
        "source_ground_truth_csv": str(ground_truth_csv),
        "source_manifest_dir": str(beep_evidence_dir),
    }

    report_dir = output_html.resolve().parent
    card_html = "\n".join(_case_card_html(row, report_dir) for row in joined_rows)
    summary_blocks = "\n".join(
        [
            f'<div class="summary-total"><div class="summary-number">{total_cases}</div><div class="summary-label">misclassified cases</div></div>',
            _group_count_html("By tranche", tranche_counts),
            _group_count_html("By subentity", subentity_counts),
        ]
    )

    html_doc = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>BEEP Misclassified Cases - tranches 1-5</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 22px; background: #f6f7fb; color: #1f2937; }}
    h1 {{ margin: 0 0 6px 0; font-size: 30px; }}
    .subtitle {{ margin: 0 0 16px 0; color: #4b5563; }}
    .summary-grid {{ display: grid; grid-template-columns: minmax(160px, 220px) 1fr 1fr; gap: 12px; margin-bottom: 18px; }}
    .summary-total, .summary-block {{ background: white; border: 1px solid #d1d5db; border-radius: 10px; padding: 14px; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03); }}
    .summary-number {{ font-size: 44px; font-weight: 700; line-height: 1; color: #111827; }}
    .summary-label {{ margin-top: 6px; color: #6b7280; font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; }}
    .summary-block h2 {{ margin: 0 0 8px 0; font-size: 16px; }}
    .summary-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .summary-table th, .summary-table td {{ border-top: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }}
    .summary-table th {{ background: #f9fafb; }}
    .empty-note {{ color: #9ca3af; font-size: 13px; }}
    .report-note {{ background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412; padding: 10px 12px; border-radius: 8px; margin-bottom: 16px; }}
    .case-card {{ background: white; border: 1px solid #d1d5db; border-radius: 12px; margin-bottom: 14px; overflow: hidden; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03); }}
    .case-header {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; padding: 12px 14px; background: linear-gradient(90deg, #eef2ff, #ffffff); border-bottom: 1px solid #e5e7eb; }}
    .case-title {{ font-weight: 700; font-size: 14px; word-break: break-word; }}
    .case-badge {{ font-size: 12px; color: #92400e; background: #fffbeb; border: 1px solid #fcd34d; border-radius: 999px; padding: 4px 10px; white-space: nowrap; }}
    .case-body {{ display: grid; grid-template-columns: minmax(320px, 2fr) minmax(320px, 1fr); gap: 16px; padding: 14px; align-items: flex-start; }}
    .case-images {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .image-block {{ width: 240px; max-width: 100%; }}
    .image-block img {{ max-width: 100%; display: block; border: 1px solid #cbd5e1; border-radius: 8px; background: #fff; }}
    .image-caption {{ text-align: center; font-size: 12px; color: #6b7280; margin-top: 4px; }}
    .meta-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .meta-table th, .meta-table td {{ border-top: 1px solid #e5e7eb; padding: 7px 8px; vertical-align: top; text-align: left; }}
    .meta-table th {{ width: 34%; color: #374151; background: #f9fafb; font-weight: 600; }}
    .disk-image-details {{ margin-top: 12px; }}
    .disk-image-details summary {{ cursor: pointer; color: #1d4ed8; font-size: 13px; font-weight: 600; }}
    .disposition-panel {{ grid-column: 1 / -1; background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; margin-top: 4px; }}
    .disposition-title {{ font-size: 13px; font-weight: 700; margin-bottom: 8px; color: #111827; }}
    .disposition-panel label {{ display: block; margin-top: 8px; font-size: 13px; }}
    .disposition-panel select, .disposition-panel textarea {{ width: 100%; max-width: 440px; }}
    .disposition-panel button {{ margin-top: 10px; }}
    .feedback-status {{ margin-left: 8px; color: #16a34a; font-size: 13px; }}
    @media (max-width: 980px) {{
      .summary-grid {{ grid-template-columns: 1fr; }}
      .case-body {{ grid-template-columns: 1fr; }}
      .image-block {{ width: 100%; }}
    }}
    {_FEEDBACK_PORTAL_CSS if with_feedback_portal else ''}
  </style>
</head>
<body>
  <h1>BEEP Misclassified Cases</h1>
  <p class="subtitle">Reviewer-labeled BEEP cases from tranches 0001-0005, joined to their manifest images, factory metadata, and disk-image references.</p>
  <div class="report-note">Static report only. No labeling controls, no backend callbacks.</div>
  { _feedback_portal_assets(run_id=report_dir.name, api_base=feedback_api_base)[0] if with_feedback_portal else '' }
  <div class="summary-grid">
    {summary_blocks}
  </div>
  <div class="summary-block" style="margin-bottom: 16px;">
    <h2>Summary JSON</h2>
    <pre style="white-space: pre-wrap; word-break: break-word; margin: 0; font-size: 12px;">{html.escape(json.dumps(summary_json, indent=2))}</pre>
  </div>
  <div id="cases">
    {card_html}
  </div>
  { _feedback_portal_assets(run_id=report_dir.name, api_base=feedback_api_base)[1] if with_feedback_portal else '' }
</body>
</html>
"""

    written_path = _write_html_with_rev_fallback(html_doc, output_html)
    return summary_json, written_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a static BEEP misclassified HTML report")
    parser.add_argument(
        "--ground-truth-csv",
        default=str(ALLY_CLASS_DIR / "outputs" / BE_SUFFIX / "beep_evidence_ground_truth.csv"),
        help="beep_evidence_ground_truth.csv path",
    )
    parser.add_argument(
        "--output-html",
        default=str(ALLY_CLASS_DIR / "outputs" / BE_SUFFIX / "beep_misclassified_tranches_1-5.html"),
        help="Output HTML path",
    )
    parser.add_argument(
        "--beep-evidence-dir",
        default=str(ALLY_CLASS_DIR / "outputs" / BE_SUFFIX),
        help="Directory containing tranche_000N_cases.csv files",
    )
    parser.add_argument(
        "--disk-image-manifest-csv",
        default=str(DEFAULT_DISK_IMAGE_MANIFEST),
        help="Optional production image manifest for disk-image references",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary, written_path = build_report(
        ground_truth_csv=Path(args.ground_truth_csv),
        output_html=Path(args.output_html),
        beep_evidence_dir=Path(args.beep_evidence_dir),
      disk_image_manifest_csv=Path(args.disk_image_manifest_csv),
      with_feedback_portal=True,
    )
    print(json.dumps(summary, indent=2))
    print(str(written_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())