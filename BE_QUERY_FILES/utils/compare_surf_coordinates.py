from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def _safe_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _key_frame(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing key columns: {missing}")
    out = df[cols].copy()
    out["WAFER_KEY"] = out["WAFER_KEY"].astype(str)
    out["INSPECTION_TIME"] = out["INSPECTION_TIME"].astype(str)
    out["DEFECT_ID"] = out["DEFECT_ID"].astype(str)
    return out.drop_duplicates()


def build_report(original_path: Path, new_path: Path) -> dict:
    if not original_path.exists():
        raise FileNotFoundError(f"Original file missing: {original_path}")
    if not new_path.exists():
        raise FileNotFoundError(f"New file missing: {new_path}")

    original = pd.read_csv(original_path, low_memory=False)
    new = pd.read_csv(new_path, low_memory=False)

    for df in (original, new):
        if "INSPECTION_TIME" in df.columns:
            df["INSPECTION_TIME"] = _safe_datetime(df["INSPECTION_TIME"])

    orig_keys = _key_frame(original)
    new_keys = _key_frame(new)
    key_cols = ["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"]

    both = orig_keys.merge(new_keys, on=key_cols, how="inner")
    only_orig = orig_keys.merge(new_keys, on=key_cols, how="left", indicator=True)
    only_orig = only_orig[only_orig["_merge"] == "left_only"].drop(columns=["_merge"])
    only_new = new_keys.merge(orig_keys, on=key_cols, how="left", indicator=True)
    only_new = only_new[only_new["_merge"] == "left_only"].drop(columns=["_merge"])

    original_monthly = (
        original.dropna(subset=["INSPECTION_TIME"]).assign(
            MONTH=lambda d: d["INSPECTION_TIME"].dt.strftime("%Y-%m")
        )["MONTH"].value_counts().sort_index()
    )
    new_monthly = (
        new.dropna(subset=["INSPECTION_TIME"]).assign(
            MONTH=lambda d: d["INSPECTION_TIME"].dt.strftime("%Y-%m")
        )["MONTH"].value_counts().sort_index()
    )

    report = {
        "files": {
            "original": str(original_path),
            "new": str(new_path),
            "original_size_bytes": int(original_path.stat().st_size),
            "new_size_bytes": int(new_path.stat().st_size),
        },
        "rows": {
            "original": int(len(original)),
            "new": int(len(new)),
        },
        "inspection_time": {
            "original_min": str(original["INSPECTION_TIME"].min()) if "INSPECTION_TIME" in original.columns else None,
            "original_max": str(original["INSPECTION_TIME"].max()) if "INSPECTION_TIME" in original.columns else None,
            "new_min": str(new["INSPECTION_TIME"].min()) if "INSPECTION_TIME" in new.columns else None,
            "new_max": str(new["INSPECTION_TIME"].max()) if "INSPECTION_TIME" in new.columns else None,
        },
        "keys": {
            "original_unique": int(len(orig_keys)),
            "new_unique": int(len(new_keys)),
            "both": int(len(both)),
            "only_original": int(len(only_orig)),
            "only_new": int(len(only_new)),
        },
        "columns": {
            "only_original": sorted(list(set(original.columns) - set(new.columns))),
            "only_new": sorted(list(set(new.columns) - set(original.columns))),
        },
        "monthly_counts": {
            "original": {k: int(v) for k, v in original_monthly.items()},
            "new": {k: int(v) for k, v in new_monthly.items()},
        },
    }

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare original and consolidated SURF SS_COORDINATES files.")
    parser.add_argument("--original", type=Path, required=True, help="Path to original baseline SS_COORDINATES.csv")
    parser.add_argument("--new", type=Path, required=True, help="Path to new SS_COORDINATES.csv")
    parser.add_argument("--out-json", type=Path, default=None, help="Optional output JSON report path")
    args = parser.parse_args()

    report = build_report(args.original, args.new)
    report_text = json.dumps(report, indent=2)
    print(report_text)

    if args.out_json is not None:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(report_text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
