"""
Review Phase 1 classification quality with confidence and BF/DF pair consistency metrics.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text:
            rows.append(json.loads(text))
    return rows


def _pair_key_from_name(image_name: str) -> str:
    if image_name.endswith("_2.jpg") or image_name.endswith("_3.jpg"):
        return image_name[:-6]
    return image_name.rsplit(".", 1)[0]


def _primary_class(row: dict) -> str:
    for key in ("primary_class", "defect_class", "defect_type"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return "<missing>"


def _confidence(row: dict) -> float | None:
    value = row.get("confidence")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _review_required(row: dict) -> bool:
    value = row.get("review_required")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _confidence_bucket(value: float) -> str:
    if value < 0.6:
        return "lt_0_60"
    if value < 0.75:
        return "0_60_to_0_75"
    if value < 0.9:
        return "0_75_to_0_90"
    return "gte_0_90"


def _summarize(rows: list[dict]) -> dict:
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    total_ok = len(ok_rows)

    confidences = [c for c in (_confidence(row) for row in ok_rows) if c is not None]
    confidence_hist = Counter(_confidence_bucket(c) for c in confidences)

    classes = Counter(_primary_class(row) for row in ok_rows)
    review_true = sum(1 for row in ok_rows if _review_required(row))

    pairs: dict[str, dict[str, dict]] = {}
    for row in ok_rows:
        image_name = str(row.get("image_name", ""))
        pair_key = str(row.get("pair_key") or _pair_key_from_name(image_name))
        role = row.get("pair_role")
        if role not in {"brightfield", "darkfield"}:
            if image_name.endswith("_2.jpg"):
                role = "brightfield"
            elif image_name.endswith("_3.jpg"):
                role = "darkfield"
            else:
                role = "unknown"
        pairs.setdefault(pair_key, {})[str(role)] = row

    paired_keys = [key for key, val in pairs.items() if "brightfield" in val and "darkfield" in val]
    disagreement_count = 0
    contradiction_pairs: list[dict] = []
    max_examples = 10

    for key in sorted(paired_keys):
        bf = pairs[key]["brightfield"]
        df = pairs[key]["darkfield"]
        bf_class = _primary_class(bf)
        df_class = _primary_class(df)
        if bf_class != df_class:
            disagreement_count += 1
            if len(contradiction_pairs) < max_examples:
                contradiction_pairs.append(
                    {
                        "pair_key": key,
                        "bf_image": bf.get("image_name", ""),
                        "df_image": df.get("image_name", ""),
                        "bf_class": bf_class,
                        "df_class": df_class,
                        "bf_confidence": _confidence(bf),
                        "df_confidence": _confidence(df),
                        "bf_review_required": _review_required(bf),
                        "df_review_required": _review_required(df),
                    }
                )

    pair_count = len(paired_keys)
    disagreement_rate = (disagreement_count / pair_count) if pair_count else None
    review_rate = (review_true / total_ok) if total_ok else None
    avg_conf = (sum(confidences) / len(confidences)) if confidences else None

    return {
        "row_counts": {
            "rows": len(rows),
            "ok_rows": total_ok,
            "paired_rows": pair_count * 2,
            "paired_pairs": pair_count,
        },
        "confidence": {
            "avg": avg_conf,
            "min": min(confidences) if confidences else None,
            "max": max(confidences) if confidences else None,
            "buckets": dict(confidence_hist),
        },
        "review_required": {
            "true_count": review_true,
            "rate": review_rate,
        },
        "class_distribution": dict(classes),
        "bf_df_consistency": {
            "pair_disagreement_count": disagreement_count,
            "pair_disagreement_rate": disagreement_rate,
            "disagreement_examples": contradiction_pairs,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review Phase 1 confidence and BF/DF consistency")
    parser.add_argument("jsonl_path", help="Path to phase1_results.jsonl")
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to write summary JSON.",
    )
    args = parser.parse_args()

    summary = _summarize(_load_jsonl(Path(args.jsonl_path)))
    text = json.dumps(summary, indent=2)
    print(text)
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
