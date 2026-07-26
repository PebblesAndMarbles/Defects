"""
Build a paired HTML report for Phase 1 Alloy image experiments.

Output layout per row:
1. brightfield image
2. darkfield image
3. brightfield caption
4. darkfield caption
5. brightfield structured output
6. darkfield structured output
"""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text:
            rows.append(json.loads(text))
    return rows


def _pair_key(image_name: str) -> str:
    if image_name.endswith("_2.jpg"):
        return image_name[:-6]
    if image_name.endswith("_3.jpg"):
        return image_name[:-6]
    return image_name.rsplit(".", 1)[0]


def _fmt_structured(record: dict) -> str:
    filtered = {k: v for k, v in record.items() if k not in {"run_id", "timestamp_utc", "image_key", "image_path", "image_name", "model_name", "prompt_version", "status", "raw_response_excerpt"}}
    return html.escape(json.dumps(filtered, indent=2))


def _img_tag(path: Path, report_dir: Path) -> str:
    src = os.path.relpath(str(path), str(report_dir)).replace("\\", "/")
    return f'<img src="{html.escape(src)}" alt="{html.escape(path.name)}" style="max-width: 260px; border: 1px solid #bbb;">'


def build_report(inputs_dir: Path, caption_jsonl: Path, structured_jsonl: Path, output_html: Path) -> None:
    report_dir = output_html.resolve().parent
    inputs_dir = inputs_dir.resolve()

    captions = {row["image_name"]: row for row in _load_jsonl(caption_jsonl)}
    structured = {row["image_name"]: row for row in _load_jsonl(structured_jsonl)}

    pairs: dict[str, dict[str, Path]] = {}
    for image_path in sorted(inputs_dir.iterdir()):
        if not image_path.is_file():
            continue
        suffix_key = image_path.stem.split("_")[-1]
        base = _pair_key(image_path.name)
        pairs.setdefault(base, {})[suffix_key] = image_path

    rows_html: list[str] = []
    for base, pair in pairs.items():
        bright = pair.get("2")
        dark = pair.get("3")
        if not bright or not dark:
            continue

        bright_caption = captions.get(bright.name, {})
        dark_caption = captions.get(dark.name, {})
        bright_struct = structured.get(bright.name, {})
        dark_struct = structured.get(dark.name, {})

        rows_html.append(
            "<tr>"
            f"<td>{_img_tag(bright.resolve(), report_dir)}<div class='label'>{html.escape(bright.name)}</div></td>"
            f"<td>{_img_tag(dark.resolve(), report_dir)}<div class='label'>{html.escape(dark.name)}</div></td>"
            f"<td><pre>{html.escape(bright_caption.get('caption', ''))}</pre></td>"
            f"<td><pre>{html.escape(dark_caption.get('caption', ''))}</pre></td>"
            f"<td><pre>{_fmt_structured(bright_struct) if bright_struct else ''}</pre></td>"
            f"<td><pre>{_fmt_structured(dark_struct) if dark_struct else ''}</pre></td>"
            "</tr>"
        )

    html_doc = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Phase 1 Alloy Image Classification Report</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; background: #fafafa; color: #222; }}
    h1 {{ margin-bottom: 8px; }}
    p {{ margin-top: 0; color: #555; }}
    table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
    th, td {{ border: 1px solid #ccc; vertical-align: top; padding: 10px; background: white; }}
    th {{ background: #e9eef5; }}
    pre {{ white-space: pre-wrap; word-break: break-word; font-size: 12px; margin: 0; }}
    .label {{ font-size: 12px; color: #555; margin-top: 6px; }}
  </style>
</head>
<body>
  <h1>Phase 1 Alloy Image Classification Report</h1>
  <p>Paired brightfield/darkfield review with Rob-style captions and structured phase outputs.</p>
  <table>
    <thead>
      <tr>
        <th>Brightfield</th>
        <th>Darkfield</th>
        <th>Brightfield Caption</th>
        <th>Darkfield Caption</th>
        <th>Brightfield Structured</th>
        <th>Darkfield Structured</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
</body>
</html>
"""

    output_html.write_text(html_doc, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Phase 1 HTML report")
    parser.add_argument("--inputs-dir", default="inputs")
    parser.add_argument("--caption-jsonl", default="outputs/captions/caption_results.jsonl")
    parser.add_argument("--structured-jsonl", default="outputs/phase1/phase1_results.jsonl")
    parser.add_argument("--output-html", default="outputs/phase1_combined_report.html")
    args = parser.parse_args()

    build_report(
        inputs_dir=Path(args.inputs_dir),
        caption_jsonl=Path(args.caption_jsonl),
        structured_jsonl=Path(args.structured_jsonl),
        output_html=Path(args.output_html),
    )
    print(str(Path(args.output_html).resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
