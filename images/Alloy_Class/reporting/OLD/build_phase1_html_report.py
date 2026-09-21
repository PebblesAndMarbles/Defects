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
from typing import Literal


STRUCTURED_EXCLUDE_FIELDS = {
    "run_id",
    "timestamp_utc",
    "image_key",
    "image_path",
    "image_name",
    "model_name",
    "prompt_version",
    "status",
    "raw_response_excerpt",
}


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _extract_confidence(record: dict) -> float | None:
    value = record.get("confidence")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _extract_primary_class(record: dict) -> str:
    for key in ("primary_class", "defect_class", "defect_type"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
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


def _role_from_name(image_name: str) -> str | None:
    if image_name.endswith("_2.jpg"):
        return "2"
    if image_name.endswith("_3.jpg"):
        return "3"
    return None


def _fmt_structured(record: dict) -> str:
    filtered = {k: v for k, v in record.items() if k not in STRUCTURED_EXCLUDE_FIELDS}
    return html.escape(json.dumps(filtered, indent=2))


def _fmt_pair_metadata(base: str, bright_name: str, dark_name: str, bright_struct: dict, dark_struct: dict) -> str:
    row = bright_struct or dark_struct
    pair_meta = {
        "pair_key": row.get("pair_key", base),
        "run_id": row.get("run_id", ""),
        "model_name": row.get("model_name", ""),
        "prompt_version": row.get("prompt_version", ""),
        "brightfield_image_name": bright_name,
        "darkfield_image_name": dark_name,
        "brightfield_class": _extract_primary_class(bright_struct),
        "darkfield_class": _extract_primary_class(dark_struct),
        "brightfield_confidence": _extract_confidence(bright_struct),
        "darkfield_confidence": _extract_confidence(dark_struct),
    }
    return html.escape(json.dumps(pair_meta, indent=2))


def _fmt_review_flags(bright_struct: dict, dark_struct: dict) -> str:
    bf_review = _as_bool(bright_struct.get("review_required"))
    df_review = _as_bool(dark_struct.get("review_required"))
    bf_conf = _extract_confidence(bright_struct)
    df_conf = _extract_confidence(dark_struct)

    pair_any_review = bf_review or df_review
    confidence_delta = None
    if bf_conf is not None and df_conf is not None:
        confidence_delta = round(abs(bf_conf - df_conf), 3)

    bf_name = str(bright_struct.get("image_name", "")).upper()
    df_name = str(dark_struct.get("image_name", "")).upper()
    bf_is_smp = "_SMP_" in bf_name
    df_is_smp = "_SMP_" in df_name

    bf_class = _extract_primary_class(bright_struct).lower()
    df_class = _extract_primary_class(dark_struct).lower()
    beep_tokens = ("beep", "bridge", "line_bridge", "stringer")
    bf_beep_like = any(tok in bf_class for tok in beep_tokens)
    df_beep_like = any(tok in df_class for tok in beep_tokens)

    flags = {
        "bf_review_required": bf_review,
        "df_review_required": df_review,
        "pair_review_required": pair_any_review,
        "bf_df_class_disagreement": _extract_primary_class(bright_struct) != _extract_primary_class(dark_struct),
        "smp_to_beep_suspect": (bf_is_smp and bf_beep_like) or (df_is_smp and df_beep_like),
        "bf_confidence": bf_conf,
        "df_confidence": df_conf,
        "confidence_abs_delta": confidence_delta,
    }
    return html.escape(json.dumps(flags, indent=2))


def _img_tag(path: Path, report_dir: Path) -> str:
    try:
        src = os.path.relpath(str(path), str(report_dir)).replace("\\", "/")
    except ValueError:
        # Windows relpath fails across mounts (for example UNC report dir vs C: images).
        src = path.as_uri()
    return f'<img src="{html.escape(src)}" alt="{html.escape(path.name)}" style="max-width: 260px; border: 1px solid #bbb;">'


def _choose_structured_image_path(record: dict) -> Path | None:
    for key in ("burned_image_path", "image_path", "inference_image_path", "local_path"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            candidate = Path(value.strip())
            if candidate.exists() and candidate.is_file():
                return candidate
    return None


def _build_pairs_from_names(image_names: set[str]) -> dict[str, dict[str, str]]:
    pairs: dict[str, dict[str, str]] = {}
    for name in sorted(image_names):
        role = _role_from_name(name)
        if role is None:
            continue
        base = _pair_key(name)
        pairs.setdefault(base, {})[role] = name
    return pairs


def _resolve_image_path(
    image_name: str,
    image_path_source: Literal["inputs", "structured", "auto"],
    inputs_dir: Path,
    struct_row: dict,
) -> Path | None:
    input_candidate = (inputs_dir / image_name).resolve()
    struct_candidate = _choose_structured_image_path(struct_row)

    if image_path_source == "inputs":
        if input_candidate.exists() and input_candidate.is_file():
            return input_candidate
        return struct_candidate

    if image_path_source == "structured":
        if struct_candidate:
            return struct_candidate
        if input_candidate.exists() and input_candidate.is_file():
            return input_candidate
        return None

    # auto
    if struct_candidate:
        return struct_candidate
    if input_candidate.exists() and input_candidate.is_file():
        return input_candidate
    return None


def _img_cell(path: Path | None, name: str, report_dir: Path) -> str:
    if path:
        return f"{_img_tag(path.resolve(), report_dir)}<div class='label'>{html.escape(name)}</div>"
    return (
        "<div style='width:260px;height:180px;border:1px dashed #bbb;display:flex;align-items:center;"
        "justify-content:center;color:#777;font-size:12px;'>image not found</div>"
        f"<div class='label'>{html.escape(name)}</div>"
    )


def build_report(
    inputs_dir: Path,
    caption_jsonl: Path,
    structured_jsonl: Path,
    output_html: Path,
    image_path_source: Literal["inputs", "structured", "auto"] = "auto",
) -> None:
    report_dir = output_html.resolve().parent
    inputs_dir = inputs_dir.resolve()

    captions = {row["image_name"]: row for row in _load_jsonl(caption_jsonl) if row.get("image_name")}
    structured = {row["image_name"]: row for row in _load_jsonl(structured_jsonl)}

    image_names = set(captions.keys()) | set(structured.keys())
    if inputs_dir.exists() and inputs_dir.is_dir():
        image_names |= {p.name for p in inputs_dir.iterdir() if p.is_file()}

    pairs = _build_pairs_from_names(image_names)

    rows_html: list[str] = []
    for base, pair in pairs.items():
        bright_name = pair.get("2")
        dark_name = pair.get("3")
        if not bright_name or not dark_name:
            continue

        bright_caption = captions.get(bright_name, {})
        dark_caption = captions.get(dark_name, {})
        bright_struct = structured.get(bright_name, {})
        dark_struct = structured.get(dark_name, {})
        bright_path = _resolve_image_path(bright_name, image_path_source, inputs_dir, bright_struct)
        dark_path = _resolve_image_path(dark_name, image_path_source, inputs_dir, dark_struct)

        rows_html.append(
            "<tr>"
            f"<td>{_img_cell(bright_path, bright_name, report_dir)}</td>"
            f"<td>{_img_cell(dark_path, dark_name, report_dir)}</td>"
            f"<td><pre>{html.escape(bright_caption.get('caption', ''))}</pre></td>"
            f"<td><pre>{html.escape(dark_caption.get('caption', ''))}</pre></td>"
            f"<td><pre>{_fmt_pair_metadata(base, bright_name, dark_name, bright_struct, dark_struct)}</pre></td>"
            f"<td><pre>{_fmt_review_flags(bright_struct, dark_struct)}</pre></td>"
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
                <th>Pair Metadata</th>
                <th>Reviewer Flags</th>
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
    parser.add_argument(
        "--image-path-source",
        choices=["inputs", "structured", "auto"],
        default="auto",
        help="Image path source: inputs folder, structured record paths, or auto fallback.",
    )
    args = parser.parse_args()

    build_report(
        inputs_dir=Path(args.inputs_dir),
        caption_jsonl=Path(args.caption_jsonl),
        structured_jsonl=Path(args.structured_jsonl),
        output_html=Path(args.output_html),
        image_path_source=args.image_path_source,
    )
    print(str(Path(args.output_html).resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
