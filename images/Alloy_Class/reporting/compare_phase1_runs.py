"""
Summarize Phase 1 structured classification outputs for quick comparison.
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


def _summarize(rows: list[dict]) -> dict:
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    primary_counts = Counter(row.get("primary_class", "<missing>") for row in ok_rows)
    review_true = sum(1 for row in ok_rows if row.get("review_required") is True)
    confidence_values = [row.get("confidence") for row in ok_rows if isinstance(row.get("confidence"), (int, float))]
    avg_conf = sum(confidence_values) / len(confidence_values) if confidence_values else None
    return {
        "rows": len(rows),
        "ok_rows": len(ok_rows),
        "review_required_true": review_true,
        "avg_confidence": avg_conf,
        "primary_class_counts": dict(primary_counts),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Phase 1 structured run outputs")
    parser.add_argument("jsonl_path", help="Path to phase1_results.jsonl")
    args = parser.parse_args()
    rows = _load_jsonl(Path(args.jsonl_path))
    print(json.dumps(_summarize(rows), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
