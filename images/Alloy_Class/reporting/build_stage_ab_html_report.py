"""
Build an HTML review report for Stage A -> Stage B test runs.
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


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_label(value: Any) -> str:
    return str(value or "").strip()


def _fmt_json(value: Any) -> str:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return html.escape(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            return html.escape(value)
    return html.escape(json.dumps(value, indent=2))


def _img_tag(image_path: Path, report_dir: Path) -> str:
    try:
        rel = os.path.relpath(str(image_path), str(report_dir)).replace("\\", "/")
        src = html.escape(rel)
    except ValueError:
        # Cross-mount (e.g. C:\ vs UNC): fall back to absolute file URI
        src = html.escape(image_path.as_uri())
    return f'<img src="{src}" alt="{html.escape(image_path.name)}" style="max-width:260px;border:1px solid #bbb;">'


def _stage_a_conf(stage_a: dict[str, Any]) -> float | None:
    conf = _as_float(stage_a.get("confidence"))
    if conf is not None:
        return conf
    return _as_float(stage_a.get("context_confidence"))


def build_report(
    input_jsonl: Path,
    run_id: str,
    input_folder: Path,
    output_html: Path,
) -> dict[str, Any]:
    rows = [r for r in _load_jsonl(input_jsonl) if str(r.get("run_id", "")) == run_id]
    report_dir = output_html.resolve().parent

    by_pair: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get("pair_key", ""))
        role = str(row.get("pair_role", "unknown"))
        by_pair.setdefault(key, {})[role] = row

    class_counts: Counter[str] = Counter()
    blocked_counts: Counter[str] = Counter()
    stage_b_review_true = 0
    stage_a_review_true = 0

    body_rows: list[str] = []
    for pair_key in sorted(by_pair.keys()):
        for role in ("brightfield", "darkfield"):
            row = by_pair[pair_key].get(role)
            if not row:
                continue

            stage_a = row.get("stage_a") or {}
            stage_b = row.get("stage_b") or {}
            if not isinstance(stage_a, dict):
                stage_a = {}
            if not isinstance(stage_b, dict):
                stage_b = {}

            image_name = str(row.get("image_name", ""))
            image_path = input_folder / image_name

            a_review = _as_bool(stage_a.get("review_required"))
            b_review = _as_bool(stage_b.get("review_required"))
            a_conf = _stage_a_conf(stage_a)
            b_conf = _as_float(stage_b.get("confidence"))

            stage_b_class = _as_label(stage_b.get("defect_coarse_class"))
            blocked = _as_label(stage_b.get("blocked_etch_evidence"))
            class_counts[stage_b_class or "<missing>"] += 1
            blocked_counts[blocked or "<missing>"] += 1

            if a_review:
                stage_a_review_true += 1
            if b_review:
                stage_b_review_true += 1

            transition = []
            if a_review and not b_review:
                transition.append("A-review->B-no-review")
            if (not a_review) and b_review:
                transition.append("A-no-review->B-review")
            if stage_b_class.lower() == "possible_beep":
                transition.append("possible_beep")
            transition_text = ", ".join(transition) if transition else "none"

            body_rows.append(
                "<tr>"
                f"<td>{html.escape(pair_key)}</td>"
                f"<td>{html.escape(role)}</td>"
                f"<td>{_img_tag(image_path.resolve(), report_dir) if image_path.exists() else html.escape(image_name)}</td>"
                f"<td><div><b>regime:</b> {html.escape(_as_label(stage_a.get('coarse_substrate_regime')))}</div>"
                f"<div><b>conf:</b> {a_conf if a_conf is not None else ''}</div>"
                f"<div><b>review:</b> {str(a_review).lower()}</div></td>"
                f"<td><div><b>class:</b> {html.escape(stage_b_class)}</div>"
                f"<div><b>blocked_etch:</b> {html.escape(blocked)}</div>"
                f"<div><b>conf:</b> {b_conf if b_conf is not None else ''}</div>"
                f"<div><b>review:</b> {str(b_review).lower()}</div></td>"
                f"<td>{html.escape(transition_text)}</td>"
                f"<td><details><summary>Stage A JSON</summary><pre>{_fmt_json(stage_a)}</pre></details>"
                f"<details><summary>Stage B JSON</summary><pre>{_fmt_json(stage_b)}</pre></details></td>"
                "</tr>"
            )

    total_rows = len(rows)
    total_pairs = len(by_pair)
    summary = {
        "run_id": run_id,
        "rows": total_rows,
        "pairs": total_pairs,
        "stage_a_review_rate": (stage_a_review_true / total_rows) if total_rows else 0.0,
        "stage_b_review_rate": (stage_b_review_true / total_rows) if total_rows else 0.0,
        "stage_b_class_counts": dict(class_counts),
        "blocked_etch_counts": dict(blocked_counts),
    }

    html_doc = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Stage A-B Review Report</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 22px; background: #f8f9fb; color: #1f2937; }}
    h1 {{ margin-bottom: 6px; }}
    .meta {{ color: #4b5563; margin-bottom: 10px; }}
    .box {{ background: white; border: 1px solid #d1d5db; padding: 10px; margin-bottom: 14px; }}
    table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; vertical-align: top; background: white; }}
    th {{ background: #e5eefb; }}
    pre {{ white-space: pre-wrap; word-break: break-word; font-size: 12px; }}
    details summary {{ cursor: pointer; color: #1d4ed8; }}
  </style>
</head>
<body>
  <h1>Stage A -> Stage B Review Report</h1>
  <div class=\"meta\">run_id={html.escape(run_id)}</div>
  <div class=\"box\"><pre>{html.escape(json.dumps(summary, indent=2))}</pre></div>
  <table>
    <thead>
      <tr>
        <th>Pair Key</th>
        <th>Role</th>
        <th>Image</th>
        <th>Stage A</th>
        <th>Stage B</th>
        <th>Transition Flags</th>
        <th>Detail JSON</th>
      </tr>
    </thead>
    <tbody>
      {''.join(body_rows)}
    </tbody>
  </table>
</body>
</html>
"""

    output_html.write_text(html_doc, encoding="utf-8")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage A/B review HTML report")
    parser.add_argument("--input-jsonl", default="outputs/stage_ab_tests/stage_ab_results.jsonl")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--input-folder", default="inputs")
    parser.add_argument("--output-html", default="outputs/stage_ab_tests/stage_ab_review.html")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = build_report(
        input_jsonl=Path(args.input_jsonl),
        run_id=args.run_id,
        input_folder=Path(args.input_folder),
        output_html=Path(args.output_html),
    )
    print(json.dumps(summary, indent=2))
    print(str(Path(args.output_html).resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
