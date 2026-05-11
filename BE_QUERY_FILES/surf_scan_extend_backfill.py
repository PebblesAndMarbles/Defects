from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pipeline_config import PIPELINE_PATHS, ensure_pipeline_dirs
import surf_scan_coordinates as surf_coords
from surf_scan_update import _build_stacked_edx, _build_zero_timebin_summary


@dataclass
class ExtendSummary:
    full_lookback_days: int
    preserve_recent_days: int
    old_rows_metrics: int
    old_rows_coordinates: int
    merged_rows_metrics: int
    merged_rows_coordinates: int
    rows_stacked: int
    rows_stacked_y: int
    metrics_output: str
    coordinates_output: str


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def _merge_dedupe(df_newer: pd.DataFrame, df_older: pd.DataFrame, dedup_keys: list[str]) -> pd.DataFrame:
    if df_newer.empty and df_older.empty:
        return pd.DataFrame()

    merged = pd.concat([df_newer, df_older], ignore_index=True, sort=False)
    if "INSPECTION_TIME" in merged.columns:
        merged["INSPECTION_TIME"] = pd.to_datetime(merged["INSPECTION_TIME"], errors="coerce")
        merged = merged.sort_values("INSPECTION_TIME", ascending=False, kind="mergesort")

    keys = [k for k in dedup_keys if k in merged.columns]
    if keys:
        merged = merged.drop_duplicates(subset=keys, keep="first")

    return merged.reset_index(drop=True)


def run(full_lookback_days: int, preserve_recent_days: int) -> ExtendSummary:
    ensure_pipeline_dirs()

    prod_metrics = PIPELINE_PATHS.surf_metrics_csv
    prod_coords = PIPELINE_PATHS.surf_coordinates_csv

    current_metrics = _read_csv(prod_metrics)
    current_coords = _read_csv(prod_coords)

    tmp_dir = PIPELINE_PATHS.surf_outputs_dir / "BACKFILL_EXTEND_TMP"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    old_metrics_path = tmp_dir / "SS_METRICS_OLDER_WINDOW.csv"
    old_coords_path = tmp_dir / "SS_COORDINATES_OLDER_WINDOW.csv"
    old_edx_path = tmp_dir / "SS_EDX_OLDER_WINDOW.csv"

    original = {
        "OUTPUT_CSV": surf_coords.OUTPUT_CSV,
        "METRICS_OUTPUT_CSV": surf_coords.METRICS_OUTPUT_CSV,
        "EDX_OUTPUT_CSV": surf_coords.EDX_OUTPUT_CSV,
        "LOOKBACK_DAYS": surf_coords.LOOKBACK_DAYS,
        "UPPER_BOUND_DAYS": getattr(surf_coords, "UPPER_BOUND_DAYS", None),
        "INCREMENTAL_UPDATE": surf_coords.INCREMENTAL_UPDATE,
    }

    try:
        surf_coords.OUTPUT_CSV = str(old_coords_path)
        surf_coords.METRICS_OUTPUT_CSV = str(old_metrics_path)
        surf_coords.EDX_OUTPUT_CSV = str(old_edx_path)
        surf_coords.LOOKBACK_DAYS = int(full_lookback_days)
        surf_coords.UPPER_BOUND_DAYS = int(preserve_recent_days)
        surf_coords.INCREMENTAL_UPDATE = False
        surf_coords.query_ss_coordinates()
    finally:
        surf_coords.OUTPUT_CSV = original["OUTPUT_CSV"]
        surf_coords.METRICS_OUTPUT_CSV = original["METRICS_OUTPUT_CSV"]
        surf_coords.EDX_OUTPUT_CSV = original["EDX_OUTPUT_CSV"]
        surf_coords.LOOKBACK_DAYS = original["LOOKBACK_DAYS"]
        surf_coords.UPPER_BOUND_DAYS = original["UPPER_BOUND_DAYS"]
        surf_coords.INCREMENTAL_UPDATE = original["INCREMENTAL_UPDATE"]

    old_metrics = _read_csv(old_metrics_path)
    old_coords = _read_csv(old_coords_path)

    merged_metrics = _merge_dedupe(
        current_metrics,
        old_metrics,
        dedup_keys=["WAFER_KEY", "INSPECTION_TIME"],
    )
    merged_coords = _merge_dedupe(
        current_coords,
        old_coords,
        dedup_keys=["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"],
    )

    merged_metrics.to_csv(prod_metrics, index=False)
    merged_coords.to_csv(prod_coords, index=False)

    rows_stacked, rows_stacked_y = _build_stacked_edx(
        prod_coords,
        PIPELINE_PATHS.surf_edx_stacked_csv,
        PIPELINE_PATHS.surf_edx_stacked_y_csv,
    )
    _build_zero_timebin_summary(
        prod_metrics,
        PIPELINE_PATHS.surf_zero_summary_csv,
        PIPELINE_PATHS.surf_zero_wide_summary_csv,
    )

    summary = ExtendSummary(
        full_lookback_days=int(full_lookback_days),
        preserve_recent_days=int(preserve_recent_days),
        old_rows_metrics=int(len(old_metrics)),
        old_rows_coordinates=int(len(old_coords)),
        merged_rows_metrics=int(len(merged_metrics)),
        merged_rows_coordinates=int(len(merged_coords)),
        rows_stacked=int(rows_stacked),
        rows_stacked_y=int(rows_stacked_y),
        metrics_output=str(prod_metrics),
        coordinates_output=str(prod_coords),
    )

    summary_path = PIPELINE_PATHS.artifacts_dir / "surf_scan_extend_backfill_summary.json"
    summary_path.write_text(json.dumps(summary.__dict__, indent=2), encoding="utf-8")
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extend SURF production outputs with older-window backfill without re-querying recent data.",
    )
    parser.add_argument(
        "--full-lookback-days",
        type=int,
        default=760,
        help="Lower bound lookback (days from now) for older-window fetch.",
    )
    parser.add_argument(
        "--preserve-recent-days",
        type=int,
        default=90,
        help="Upper bound cutoff for recent data to preserve as-is (not re-queried).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(
        full_lookback_days=args.full_lookback_days,
        preserve_recent_days=args.preserve_recent_days,
    )
    print(json.dumps(summary.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
