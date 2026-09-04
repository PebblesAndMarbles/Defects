from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))

from DEFECT_COORDINATES_QUERY import _connect, _fetch_defect_coords, _fetch_wafer_summary
from pipeline_config import PIPELINE_PATHS, ensure_pipeline_dirs, write_artifact_manifest


DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_DB = "D1D_PROD_YAS_1278"
DEFAULT_OUTPUT_DIR = PIPELINE_PATHS.defect_outputs_dir / "mismatch_audit"


def _safe_dt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _normalize_class_filter(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None


def _load_production_csv(path: Path, lookback_days: int) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    required = {"LOT", "WAFER_ID", "LAYER", "INSPECT_TIME"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Production CSV missing required columns: {sorted(missing)}")

    work = df.copy()
    work["INSPECT_TIME_DT"] = _safe_dt(work["INSPECT_TIME"])
    max_time = work["INSPECT_TIME_DT"].max()
    if pd.isna(max_time):
        return work.iloc[0:0].copy()

    cutoff = max_time - pd.Timedelta(days=lookback_days)
    return work[work["INSPECT_TIME_DT"] >= cutoff].copy()


def _count_map(series: pd.Series) -> dict[str, int]:
    return series.fillna("<NA>").astype(str).value_counts().sort_index().to_dict()


def _json_safe(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _prod_summary(df: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["LOT", "WAFER_ID", "LAYER"]
    grouped = df.groupby(group_cols, dropna=False)
    summary = grouped.agg(defect_count=("DEFECT_ID", "count")).reset_index()
    summary["CLASS_counts"] = grouped["CLASS"].apply(_count_map).reset_index(drop=True)
    if "MANUAL_OPTICAL_CLASS" in df.columns:
        summary["MANUAL_OPTICAL_CLASS_counts"] = grouped["MANUAL_OPTICAL_CLASS"].apply(_count_map).reset_index(drop=True)
    else:
        summary["MANUAL_OPTICAL_CLASS_counts"] = None
    summary["class_kind"] = grouped["CLASS"].apply(
        lambda s: "mixed" if len([v for v in sorted(set(s.fillna("<NA>").astype(str))) if v != "<NA>"]) > 1 else "single"
    ).reset_index(drop=True)
    return summary


def _db_pull(prod: pd.DataFrame, class_filter: list[str] | None, database: str) -> pd.DataFrame:
    lot_list = sorted(prod["LOT"].dropna().astype(str).unique().tolist())
    layers = sorted(prod["LAYER"].dropna().astype(str).unique().tolist())
    if not lot_list or not layers:
        return prod.iloc[0:0].copy()

    conn = _connect(database)
    try:
        summary_df = _fetch_wafer_summary(conn, lot_list, layers)
        if summary_df.empty:
            return summary_df

        summary_df = summary_df.copy()
        summary_df["INSPECTION_TIME"] = _safe_dt(summary_df["INSPECTION_TIME"])
        summary_df["INSPECT_KEY"] = summary_df["INSPECTION_TIME"].dt.strftime("%Y-%m-%d %H:%M:%S")

        prod_lookup = prod[["LOT", "WAFER_ID", "LAYER", "INSPECT_TIME_DT"]].drop_duplicates().copy()
        prod_lookup["INSPECT_KEY"] = prod_lookup["INSPECT_TIME_DT"].dt.strftime("%Y-%m-%d %H:%M:%S")

        merged = prod_lookup.merge(
            summary_df,
            left_on=["LOT", "WAFER_ID", "LAYER", "INSPECT_KEY"],
            right_on=["ACTUAL_LOT", "WAFER_ID", "LAYER", "INSPECT_KEY"],
            how="inner",
        )
        if merged.empty:
            merged = prod_lookup.merge(
                summary_df,
                left_on=["LOT", "WAFER_ID", "LAYER"],
                right_on=["ACTUAL_LOT", "WAFER_ID", "LAYER"],
                how="inner",
            )

        if merged.empty:
            return merged

        pairs = [(row["INSPECTION_TIME"], int(row["WAFER_KEY"])) for _, row in merged.iterrows()]
        pairs = list(dict.fromkeys(pairs))
        if not pairs:
            return merged.iloc[0:0].copy()

        defects_df = _fetch_defect_coords(conn, pairs, class_filter=class_filter)
    finally:
        conn.close()

    if defects_df.empty:
        return defects_df

    defects_df = defects_df.copy()
    defects_df["INSPECTION_TIME"] = _safe_dt(defects_df["INSPECTION_TIME"])
    defects_df["INSPECT_KEY"] = defects_df["INSPECTION_TIME"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return defects_df


def _classify_mismatch(prod: pd.DataFrame, db: pd.DataFrame) -> pd.DataFrame:
    prod = prod.copy()
    db = db.copy()

    prod["INSPECT_KEY"] = prod["INSPECT_TIME_DT"].dt.strftime("%Y-%m-%d %H:%M:%S")
    if "ACTUAL_LOT" not in db.columns:
        db["ACTUAL_LOT"] = db.get("LOT", pd.Series(dtype=str))

    prod["_KEY"] = (
        prod["LOT"].astype(str)
        + "|" + prod["WAFER_ID"].astype(str)
        + "|" + prod["LAYER"].astype(str)
        + "|" + prod["INSPECT_KEY"].astype(str)
        + "|" + prod["DEFECT_ID"].astype(str)
    )
    db["_KEY"] = (
        db["ACTUAL_LOT"].astype(str)
        + "|" + db["WAFER_ID"].astype(str)
        + "|" + db["LAYER"].astype(str)
        + "|" + db["INSPECT_KEY"].astype(str)
        + "|" + db["DEFECT_ID"].astype(str)
    )

    compare = prod.merge(db, on="_KEY", how="outer", indicator=True, suffixes=("_prod", "_db"))

    def _row_status(row: pd.Series) -> str:
        if row["_merge"] == "both":
            prod_class = str(row.get("CLASS_prod", "<NA>"))
            db_class = str(row.get("CLASS_db", "<NA>"))
            prod_mo = str(row.get("MANUAL_OPTICAL_CLASS_prod", "<NA>"))
            db_mo = str(row.get("MANUAL_OPTICAL_CLASS_db", "<NA>"))
            if prod_class == db_class and prod_mo == db_mo:
                return "match"
            if prod_class != db_class:
                return "class_changed"
            if prod_mo != db_mo:
                return "manual_optical_disagrees"
            return "other_difference"
        if row["_merge"] == "left_only":
            return "missing_in_db"
        return "missing_in_production"

    compare["mismatch_type"] = compare.apply(_row_status, axis=1)
    compare["LOT_GROUP"] = compare["LOT"] if "LOT" in compare.columns else compare.get("ACTUAL_LOT", compare.get("ACTUAL_LOT_db"))
    compare["WAFER_GROUP"] = compare["WAFER_ID"] if "WAFER_ID" in compare.columns else compare.get("WAFER_ID_db")
    compare["LAYER_GROUP"] = compare["LAYER"] if "LAYER" in compare.columns else compare.get("LAYER_db")
    return compare


def build_report(production_csv: Path, lookback_days: int, class_filter: list[str] | None, database: str) -> dict:
    ensure_pipeline_dirs()
    prod = _load_production_csv(production_csv, lookback_days)
    prod_summary = _prod_summary(prod)
    db = _db_pull(prod, class_filter, database)

    compare = _classify_mismatch(prod, db) if not db.empty else prod.iloc[0:0].copy()
    mismatch_counts = compare["mismatch_type"].value_counts(dropna=False).to_dict() if not compare.empty else {}

    if not compare.empty:
        group_summary = (
            compare.groupby(["LOT_GROUP", "WAFER_GROUP", "LAYER_GROUP"], dropna=False)["mismatch_type"]
            .apply(lambda s: s.value_counts().to_dict())
            .reset_index(name="mismatch_counts")
            .sort_values(["LOT_GROUP", "WAFER_GROUP", "LAYER_GROUP"])
        )
    else:
        group_summary = pd.DataFrame(columns=["LOT_GROUP", "WAFER_GROUP", "LAYER_GROUP", "mismatch_counts"])

    changed = compare[compare["mismatch_type"] == "class_changed"].copy() if not compare.empty else compare
    if not changed.empty:
        changed["transition"] = changed["CLASS_prod"].astype(str) + " -> " + changed["CLASS_db"].astype(str)
        transition_counts = changed["transition"].value_counts().head(25).to_dict()
    else:
        transition_counts = {}

    report = {
        "files": {
            "production_csv": str(production_csv),
            "database": database,
        },
        "parameters": {
            "lookback_days": lookback_days,
            "class_filter": class_filter,
        },
        "production": {
            "rows": int(len(prod)),
            "groups": int(len(prod_summary)),
        },
        "comparison": {
            "rows": int(len(compare)),
            "mismatch_counts": mismatch_counts,
            "group_summary_rows": int(len(group_summary)),
            "class_transition_counts": transition_counts,
        },
        "samples": {
            "production_summary": _json_safe(prod_summary.head(50).to_dict(orient="records")),
            "mismatch_summary": _json_safe(group_summary.head(50).to_dict(orient="records")),
            "mismatch_rows": _json_safe(compare.head(100).to_dict(orient="records")),
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare production defect coordinates to a 14-day DB pull.")
    parser.add_argument("--production-csv", type=Path, default=PIPELINE_PATHS.defect_coordinates_csv)
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--class-filter", default=None, help="Comma-separated class filter for DB pull; default is unfiltered")
    parser.add_argument("--database", default=DEFAULT_DB)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUTPUT_DIR / "mismatch_report.json")
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUTPUT_DIR / "mismatch_rows.csv")
    args = parser.parse_args()

    report = build_report(
        production_csv=args.production_csv,
        lookback_days=args.lookback_days,
        class_filter=_normalize_class_filter(args.class_filter),
        database=args.database,
    )

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    mismatch_rows = pd.DataFrame(report["samples"]["mismatch_rows"])
    mismatch_rows.to_csv(args.out_csv, index=False)

    manifest_path = write_artifact_manifest(
        PIPELINE_PATHS.defect_artifact_manifest,
        extra_outputs={
            "mismatch_report_json": args.out_json,
            "mismatch_rows_csv": args.out_csv,
        },
    )
    print(json.dumps({"artifact_manifest": str(manifest_path), "out_json": str(args.out_json), "out_csv": str(args.out_csv)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def _safe_dt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _normalize_class_filter(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None


def _load_production_csv(path: Path, lookback_days: int) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    required = {"LOT", "WAFER_ID", "LAYER", "INSPECT_TIME"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Production CSV missing required columns: {sorted(missing)}")

    work = df.copy()
    work["INSPECT_TIME_DT"] = _safe_dt(work["INSPECT_TIME"])
    max_time = work["INSPECT_TIME_DT"].max()
    if pd.isna(max_time):
        return work.iloc[0:0].copy()
    cutoff = max_time - pd.Timedelta(days=lookback_days)
    return work[work["INSPECT_TIME_DT"] >= cutoff].copy()


def _prod_summary(df: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["LOT", "WAFER_ID", "LAYER"]
    count_cols = [c for c in ["CLASS", "MANUAL_OPTICAL_CLASS"] if c in df.columns]
    agg_map = {"DEFECT_ID": "count"}
    for col in count_cols:
        agg_map[col] = lambda s, col=col: s.fillna("<NA>").astype(str).value_counts().to_dict()

    summary = (
        df.groupby(group_cols, dropna=False)
        .agg(defect_count=("DEFECT_ID", "count"))
        .reset_index()
    )

    for col in count_cols:
        counts = (
            df.groupby(group_cols, dropna=False)[col]
            .apply(lambda s: s.fillna("<NA>").astype(str).value_counts().to_dict())
            .reset_index(name=f"{col}_counts")
        )
        summary = summary.merge(counts, on=group_cols, how="left")

    return summary


def _db_pull(df: pd.DataFrame, lookback_days: int, class_filter: list[str] | None, database: str) -> pd.DataFrame:
    lot7_list = sorted(df["LOT"].astype(str).dropna().unique().tolist())
    layers = sorted(df["LAYER"].astype(str).dropna().unique().tolist())
    if not lot7_list or not layers:
        return df.iloc[0:0].copy()

    conn = _connect(database)
    try:
        summary_df = _fetch_wafer_summary(conn, lot7_list, layers)
        if summary_df.empty:
            return summary_df
        summary_df["INSPECTION_TIME"] = _safe_dt(summary_df["INSPECTION_TIME"])

        prod_lookup = df[["LOT", "WAFER_ID", "LAYER", "INSPECT_TIME_DT"]].drop_duplicates()
        prod_lookup = prod_lookup.rename(columns={"LOT": "LOT7"})
        merged = prod_lookup.merge(summary_df, on=["LOT7", "WAFER_ID", "LAYER"], how="inner")
        merged["time_delta"] = (merged["INSPECTION_TIME"] - merged["INSPECT_TIME_DT"]).abs().dt.total_seconds()
        matched = merged[merged["time_delta"] <= 1].copy()
        if matched.empty:
            matched = merged.copy()

        pairs = [(row["INSPECTION_TIME"], int(row["WAFER_KEY"])) for _, row in matched.iterrows()]
        pairs = list(dict.fromkeys(pairs))
        if not pairs:
            return summary_df.iloc[0:0].copy()

        defects_df = _fetch_defect_coords(conn, pairs, class_filter=class_filter)
    finally:
        conn.close()

    if defects_df.empty:
        return defects_df

    defects_df = defects_df.copy()
    defects_df["INSPECTION_TIME"] = _safe_dt(defects_df["INSPECTION_TIME"])
    return defects_df


def _classify_mismatch(prod: pd.DataFrame, db: pd.DataFrame) -> pd.DataFrame:
    prod = prod.copy()
    db = db.copy()
    prod["_KEY"] = (
        prod["LOT"].astype(str) + "|" + prod["WAFER_ID"].astype(str) + "|" + prod["LAYER"].astype(str) + "|" + prod["DEFECT_ID"].astype(str)
    )
    db["_KEY"] = (
        db["ACTUAL_LOT"].astype(str) + "|" + db["WAFER_ID"].astype(str) + "|" + db["LAYER"].astype(str) + "|" + db["DEFECT_ID"].astype(str)
    )

    compare = prod.merge(
        db,
        on="_KEY",
        how="outer",
        indicator=True,
        suffixes=("_prod", "_db"),
    )

    def _row_status(row: pd.Series) -> str:
        if row["_merge"] == "both":
            prod_class = str(row.get("CLASS_prod", ""))
            db_class = str(row.get("CLASS_db", ""))
            prod_mo = str(row.get("MANUAL_OPTICAL_CLASS_prod", ""))
            db_mo = str(row.get("MANUAL_OPTICAL_CLASS_db", ""))
            if prod_class == db_class and prod_mo == db_mo:
                return "match"
            if prod_class != db_class:
                return "class_changed"
            if prod_mo != db_mo:
                return "manual_optical_disagrees"
            return "other_difference"
        if row["_merge"] == "left_only":
            return "missing_in_db"
        return "missing_in_production"

    compare["mismatch_type"] = compare.apply(_row_status, axis=1)
    return compare


def build_report(production_csv: Path, lookback_days: int, class_filter: list[str] | None, database: str) -> dict:
    ensure_pipeline_dirs()
    prod = _load_production_csv(production_csv, lookback_days)
    prod_summary = _prod_summary(prod)
    db = _db_pull(prod, lookback_days, class_filter, database)
    compare = _classify_mismatch(prod, db) if not db.empty else prod.iloc[0:0].copy()

    mismatch_counts = compare["mismatch_type"].value_counts(dropna=False).to_dict() if not compare.empty else {}

    if not compare.empty:
        compare["LOT_group"] = compare[["LOT_prod", "LOT_db"]].bfill(axis=1).iloc[:, 0]
        compare["WAFER_GROUP"] = compare[["WAFER_ID_prod", "WAFER_ID_db"]].bfill(axis=1).iloc[:, 0]
        compare["LAYER_GROUP"] = compare[["LAYER_prod", "LAYER_db"]].bfill(axis=1).iloc[:, 0]
        group_summary = (
            compare.groupby(["LOT_group", "WAFER_GROUP", "LAYER_GROUP"], dropna=False)["mismatch_type"]
            .apply(lambda s: s.value_counts().to_dict())
            .reset_index(name="mismatch_counts")
        )
    else:
        group_summary = pd.DataFrame(columns=["LOT_group", "WAFER_GROUP", "LAYER_GROUP", "mismatch_counts"])

    report = {
        "files": {
            "production_csv": str(production_csv),
            "database": database,
        },
        "parameters": {
            "lookback_days": lookback_days,
            "class_filter": class_filter,
        },
        "production": {
            "rows": int(len(prod)),
            "group_summary_rows": int(len(prod_summary)),
        },
        "comparison": {
            "rows": int(len(compare)),
            "mismatch_counts": mismatch_counts,
            "group_summary_rows": int(len(group_summary)),
        },
        "samples": {
            "production_summary": prod_summary.head(50).to_dict(orient="records"),
            "mismatch_summary": group_summary.head(50).to_dict(orient="records"),
            "mismatch_rows": compare.head(100).to_dict(orient="records"),
        },
    }

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare production defect coordinates to a 14-day DB pull.")
    parser.add_argument("--production-csv", type=Path, default=PIPELINE_PATHS.defect_coordinates_csv)
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--class-filter", default=",".join(DEFAULT_CLASS_FILTER), help="Comma-separated class filter for DB pull")
    parser.add_argument("--database", default=DEFAULT_DB)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUTPUT_DIR / "mismatch_report.json")
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUTPUT_DIR / "mismatch_rows.csv")
    args = parser.parse_args()

    report = build_report(
        production_csv=args.production_csv,
        lookback_days=args.lookback_days,
        class_filter=_normalize_class_filter(args.class_filter),
        database=args.database,
    )

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    mismatch_rows = pd.DataFrame(report["samples"]["mismatch_rows"])
    mismatch_rows.to_csv(args.out_csv, index=False)

    manifest_path = write_artifact_manifest(
        PIPELINE_PATHS.defect_artifact_manifest,
        extra_outputs={
            "mismatch_report_json": args.out_json,
            "mismatch_rows_csv": args.out_csv,
        },
    )
    print(json.dumps({"artifact_manifest": str(manifest_path), "out_json": str(args.out_json), "out_csv": str(args.out_csv)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())