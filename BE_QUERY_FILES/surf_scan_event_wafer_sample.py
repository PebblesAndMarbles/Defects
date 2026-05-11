from __future__ import annotations

import argparse
import gc
import json
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import PyUber

from pipeline_config import PIPELINE_PATHS, ensure_pipeline_dirs
import surf_scan_coordinates as surf_coords


INSP_EXTRA_METRIC_COLS = [
    "ADDER_CLUSTERS",
    "CLUSTERS",
    "CLUSTER_AREA",
    "CLUSTER_METHOD",
    "CLUSTER_MIN_DEFECTS",
    "CLUSTER_THRESHOLD",
    "ADDER_RANDOM_DEFECTS",
    "ADDER_REPEATERS",
]


warnings.filterwarnings(
    "ignore",
    message=".*SQLAlchemy.*",
    category=UserWarning,
)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing input CSV: {path}")
    return pd.read_csv(path, low_memory=False)


def _parse_time(df: pd.DataFrame, col: str = "INSPECTION_TIME") -> pd.DataFrame:
    out = df.copy()
    out[col] = pd.to_datetime(out[col], errors="coerce")
    return out


def _recent_window_from_csv(path: Path, lookback_days: int, chunksize: int = 5000) -> pd.DataFrame:
    cutoff = pd.Timestamp.now().floor("s") - pd.Timedelta(days=lookback_days)
    chunks: list[pd.DataFrame] = []

    for chunk in pd.read_csv(path, chunksize=chunksize, engine="python"):
        chunk["INSPECTION_TIME"] = pd.to_datetime(chunk["INSPECTION_TIME"], errors="coerce")
        recent = chunk[chunk["INSPECTION_TIME"] >= cutoff].copy()
        if not recent.empty:
            chunks.append(recent)

    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)


def _recent_window(df: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
    cutoff = pd.Timestamp.now().floor("s") - pd.Timedelta(days=lookback_days)
    use = _parse_time(df)
    use = use[use["INSPECTION_TIME"] >= cutoff].copy()
    return use


def _fetch_slot_lookup(lookback_days: int) -> pd.DataFrame:
    primary_equip = surf_coords.PRIMARY_EQUIP_FILTER or (
        surf_coords.SUBENTITY_FILTER if isinstance(surf_coords.SUBENTITY_FILTER, list) else
        [surf_coords.SUBENTITY_FILTER] if surf_coords.SUBENTITY_FILTER else None
    )

    conn = PyUber.connect(surf_coords.DATABASE)
    try:
        ss = surf_coords._fetch_wafer_summary_ss(
            conn,
            lookback_days=lookback_days,
            layer_filter=surf_coords.SS_LAYER_FILTER,
            chamber_filter=primary_equip,
        )
        seg = surf_coords._fetch_wafer_summary_ss(
            conn,
            lookback_days=lookback_days,
            layer_filter=surf_coords.SEG_LAYER_FILTER,
            chamber_filter=primary_equip,
        )
    finally:
        conn.close()
        del conn
        gc.collect()

    slot_df = pd.concat([ss, seg], ignore_index=True)
    if slot_df.empty:
        return slot_df

    slot_df = _parse_time(slot_df)
    slot_df["SLOT_ID"] = pd.to_numeric(slot_df.get("WAFER_NUM"), errors="coerce")

    keep_cols = [
        "WAFER_KEY",
        "INSPECTION_TIME",
        "ACTUAL_LOT",
        "PRIMARY_EQUIP",
        "WAFER_ID",
        "SLOT_ID",
    ]

    slot_df = slot_df[keep_cols].drop_duplicates()

    extras_df = _fetch_insp_extras(lookback_days=lookback_days, primary_equip=primary_equip)
    if not extras_df.empty:
        slot_df = slot_df.merge(
            extras_df,
            on=["WAFER_KEY", "INSPECTION_TIME", "ACTUAL_LOT", "PRIMARY_EQUIP", "WAFER_ID", "SLOT_ID"],
            how="left",
        )

    return slot_df


def _fetch_insp_extras(lookback_days: int, primary_equip: list[str] | None) -> pd.DataFrame:
    layer_values = list(dict.fromkeys((surf_coords.SS_LAYER_FILTER or []) + (surf_coords.SEG_LAYER_FILTER or [])))
    if not layer_values:
        layer_clause = "s.LAYER_ID LIKE '%\\_PST' ESCAPE '\\'"
    else:
        layer_in = ", ".join(f"'{v}'" for v in layer_values)
        layer_clause = f"s.LAYER_ID IN ({layer_in})"

    if primary_equip:
        chamber_in = ", ".join(f"'{v}'" for v in primary_equip)
        chamber_clause = f"AND s.PROCESS_EQUIP_ID IN ({chamber_in})"
    else:
        chamber_clause = ""

    sql = f"""
SELECT
    s.WAFER_KEY,
    s.INSPECTION_TIME,
    s.LOT_ID AS ACTUAL_LOT,
    s.PROCESS_EQUIP_ID AS PRIMARY_EQUIP,
    s.SCRIBE_ID AS WAFER_ID,
    s.SLOT_ID AS SLOT_ID,
    s.ADDER_CLUSTERS,
    s.CLUSTERS,
    s.CLUSTER_AREA,
    s.CLUSTER_METHOD,
    s.CLUSTER_MIN_DEFECTS,
    s.CLUSTER_THRESHOLD,
    s.ADDER_RANDOM_DEFECTS,
    s.ADDER_REPEATERS
FROM UDB.INSP_WAFER_SUMMARY s
WHERE s.INSPECTION_TIME >= SYSDATE - {int(lookback_days)}
  AND {layer_clause}
  {chamber_clause}
"""

    conn = PyUber.connect(surf_coords.DATABASE)
    try:
        extras_df = pd.read_sql(sql, conn)
    finally:
        conn.close()
        del conn
        gc.collect()

    if extras_df.empty:
        return extras_df

    extras_df = _parse_time(extras_df)
    extras_df["SLOT_ID"] = pd.to_numeric(extras_df.get("SLOT_ID"), errors="coerce")
    for col in INSP_EXTRA_METRIC_COLS:
        if col in extras_df.columns and col != "CLUSTER_METHOD":
            extras_df[col] = pd.to_numeric(extras_df[col], errors="coerce")
    return extras_df.drop_duplicates()


def _compute_event_wafer(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["SLOT_ID"] = pd.to_numeric(out.get("SLOT_ID"), errors="coerce")
    group_keys = ["INSPECTION_TIME", "PRIMARY_EQUIP", "ACTUAL_LOT", "EVENT"]

    out = out.sort_values(group_keys + ["SLOT_ID", "WAFER_ID", "WAFER_KEY"], kind="mergesort")
    out["_ROW_IN_EVENT"] = out.groupby(group_keys, dropna=False).cumcount() + 1

    out["EVENT_WAFER"] = out.groupby(group_keys, dropna=False)["SLOT_ID"].rank(method="dense")
    out.loc[out["EVENT_WAFER"].isna(), "EVENT_WAFER"] = out.loc[
        out["EVENT_WAFER"].isna(), "_ROW_IN_EVENT"
    ]
    out["EVENT_WAFER"] = pd.to_numeric(out["EVENT_WAFER"], errors="coerce").astype("Int64")
    out = out.drop(columns=["_ROW_IN_EVENT"])
    return out


def _insert_after_event(df: pd.DataFrame) -> pd.DataFrame:
    cols = list(df.columns)
    if "EVENT" not in cols:
        return df

    movable = [c for c in ["EVENT_WAFER", "SLOT_ID"] if c in cols]
    for c in movable:
        cols.remove(c)

    i = cols.index("EVENT") + 1
    cols[i:i] = movable

    if "ADDER_DEFECTS" in cols:
        adders_cluster_cols = [c for c in ["ADDER_CLUSTERS"] + INSP_EXTRA_METRIC_COLS[1:] if c in cols]
        for c in adders_cluster_cols:
            cols.remove(c)
        j = cols.index("ADDER_DEFECTS") + 1
        cols[j:j] = adders_cluster_cols

    return df[cols]


def _drop_conflicting_sample_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    drop_cols = [c for c in columns if c in df.columns]
    if not drop_cols:
        return df
    return df.drop(columns=drop_cols)


def _build_samples(lookback_days: int) -> dict[str, str | int]:
    ensure_pipeline_dirs()

    metrics_path = PIPELINE_PATHS.surf_metrics_csv
    coords_path = PIPELINE_PATHS.surf_coordinates_csv

    metrics = _recent_window_from_csv(metrics_path, lookback_days)
    coords = _recent_window_from_csv(coords_path, lookback_days)

    slot_lookup = _fetch_slot_lookup(lookback_days)
    sample_value_cols = ["SLOT_ID", "EVENT_WAFER"] + INSP_EXTRA_METRIC_COLS

    merge_keys = ["WAFER_KEY", "INSPECTION_TIME", "ACTUAL_LOT", "PRIMARY_EQUIP", "WAFER_ID"]
    metrics = _drop_conflicting_sample_columns(metrics, sample_value_cols)
    metrics = metrics.merge(slot_lookup, on=merge_keys, how="left")
    metrics = _compute_event_wafer(metrics)
    metrics = _insert_after_event(metrics)

    wafer_map_cols = [
        "WAFER_KEY",
        "INSPECTION_TIME",
        "ACTUAL_LOT",
        "PRIMARY_EQUIP",
        "WAFER_ID",
        "EVENT",
        "SLOT_ID",
        "EVENT_WAFER",
    ] + [c for c in INSP_EXTRA_METRIC_COLS if c in metrics.columns]
    wafer_map = metrics[wafer_map_cols].drop_duplicates()

    coords = _drop_conflicting_sample_columns(coords, [c for c in wafer_map.columns if c not in merge_keys + ["EVENT"]])
    coords = coords.merge(
        wafer_map,
        on=["WAFER_KEY", "INSPECTION_TIME", "ACTUAL_LOT", "PRIMARY_EQUIP", "WAFER_ID", "EVENT"],
        how="left",
    )
    coords = _insert_after_event(coords)

    out_dir = PIPELINE_PATHS.surf_outputs_dir / "SAMPLES_90D"
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics_out = out_dir / "SS_METRICS_EVENT_WAFER_SAMPLE_90D.csv"
    coords_out = out_dir / "SS_COORDINATES_EVENT_WAFER_SAMPLE_90D.csv"
    summary_out = out_dir / "SS_EVENT_WAFER_SAMPLE_90D_SUMMARY.json"

    metrics.to_csv(metrics_out, index=False)
    coords.to_csv(coords_out, index=False)

    payload = {
        "lookback_days": int(lookback_days),
        "generated_at": datetime.now().isoformat(),
        "rows_metrics_sample": int(len(metrics)),
        "rows_coords_sample": int(len(coords)),
        "missing_slot_metrics": int(metrics["SLOT_ID"].isna().sum()) if "SLOT_ID" in metrics.columns else 0,
        "missing_event_wafer_metrics": int(metrics["EVENT_WAFER"].isna().sum()) if "EVENT_WAFER" in metrics.columns else 0,
        "missing_slot_coords": int(coords["SLOT_ID"].isna().sum()) if "SLOT_ID" in coords.columns else 0,
        "missing_event_wafer_coords": int(coords["EVENT_WAFER"].isna().sum()) if "EVENT_WAFER" in coords.columns else 0,
        "metrics_output": str(metrics_out),
        "coords_output": str(coords_out),
    }
    summary_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["summary_output"] = str(summary_out)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build 90-day SURF sample CSVs with SLOT_ID and EVENT_WAFER columns.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=90,
        help="Lookback window for sample extraction from current production SURF CSVs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = _build_samples(lookback_days=args.lookback_days)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())