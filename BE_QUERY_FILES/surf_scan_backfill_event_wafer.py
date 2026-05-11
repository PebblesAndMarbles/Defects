from __future__ import annotations

import argparse
import json
from datetime import datetime

import pandas as pd

from pipeline_config import PIPELINE_PATHS
from surf_scan_coordinates import _add_event_wafer_column
from surf_scan_event_wafer_sample import _build_samples


def _rewrite_event_wafer(path) -> dict[str, int | str]:
    df = pd.read_csv(path, low_memory=False)
    rows = len(df)
    before_non_null = int(df["EVENT_WAFER"].notna().sum()) if "EVENT_WAFER" in df.columns else 0

    updated = _add_event_wafer_column(df)
    updated.to_csv(path, index=False)

    after_non_null = int(updated["EVENT_WAFER"].notna().sum()) if "EVENT_WAFER" in updated.columns else 0
    return {
        "path": str(path),
        "rows": int(rows),
        "event_wafer_non_null_before": before_non_null,
        "event_wafer_non_null_after": after_non_null,
    }


def run(refresh_sample: bool, sample_lookback_days: int) -> dict[str, object]:
    metrics_summary = _rewrite_event_wafer(PIPELINE_PATHS.surf_metrics_csv)
    coords_summary = _rewrite_event_wafer(PIPELINE_PATHS.surf_coordinates_csv)

    payload: dict[str, object] = {
        "generated_at": datetime.now().isoformat(),
        "metrics": metrics_summary,
        "coordinates": coords_summary,
    }

    if refresh_sample:
        payload["sample"] = _build_samples(sample_lookback_days)

    summary_path = PIPELINE_PATHS.artifacts_dir / "surf_scan_event_wafer_backfill_summary.json"
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recompute EVENT_WAFER across existing SURF outputs.")
    parser.add_argument(
        "--skip-sample-refresh",
        action="store_true",
        help="Do not rebuild the 90-day sample outputs after rewriting production CSVs.",
    )
    parser.add_argument(
        "--sample-lookback-days",
        type=int,
        default=90,
        help="Lookback window used when refreshing the sample outputs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run(
        refresh_sample=not args.skip_sample_refresh,
        sample_lookback_days=args.sample_lookback_days,
    )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())