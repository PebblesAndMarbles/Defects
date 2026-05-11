from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import PyUber

from pipeline_config import PIPELINE_PATHS
from surf_scan_coordinates import (
    COUNTER_DATABASE,
    PM_COUNTER_OUTPUT_COLS,
    _fetch_pm_counter_history,
)
from surf_scan_elwc_pm_pilot import (
    EVENT_RECIPE_MAP,
    _attach_elwc_stage_to_surf,
    _norm_recipe,
    _recipe_prefixes_from_map,
)

TARGET_RF_COLUMNS = ["FULLPM_RF", "MINIPM_RF"]
STAGE_BLOCKED_CANONICAL_COUNTERS = [*TARGET_RF_COLUMNS]
LEGACY_COUNTER_COLUMNS_TO_REMOVE = ["FULLPM", "MINIPM", "CNTR_SS"]
LOGGER = logging.getLogger("surf_scan_elwc_pm_stage_backfill")


def _configure_logging() -> None:
    if LOGGER.handlers:
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s %(message)s")


def _to_sql_date(ts: pd.Timestamp) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _load_surf_scope(metrics_csv: Path, lookback_days: int | None) -> pd.DataFrame:
    df = pd.read_csv(metrics_csv, low_memory=False)
    df["INSPECTION_TIME"] = pd.to_datetime(df["INSPECTION_TIME"], errors="coerce")
    df = df[df["EVENT"].isin(EVENT_RECIPE_MAP.keys())].copy()

    if lookback_days is not None:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=int(lookback_days))
        df = df[df["INSPECTION_TIME"] >= cutoff].copy()

    if df.empty:
        return df

    df["EXPECTED_RECIPE"] = df["EVENT"].map(EVENT_RECIPE_MAP)
    df["WAFER_NUM"] = pd.to_numeric(df.get("SLOT_ID"), errors="coerce")
    df = df.dropna(subset=["INSPECTION_TIME", "PRIMARY_EQUIP", "ACTUAL_LOT", "WAFER_NUM"]).copy()
    return df


def _build_event_chunks(surf_df: pd.DataFrame, chunk_events: int) -> pd.DataFrame:
    keys = (
        surf_df[["INSPECTION_TIME", "PRIMARY_EQUIP", "ACTUAL_LOT"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["INSPECTION_TIME", "PRIMARY_EQUIP", "ACTUAL_LOT"])
        .reset_index(drop=True)
    )
    keys["CHUNK_ID"] = (np.arange(len(keys)) // int(chunk_events)).astype(int)
    return keys


def _fetch_elwc_events_window(
    chambers: list[str],
    recipe_prefixes: list[str],
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
) -> pd.DataFrame:
    if not chambers:
        return pd.DataFrame()

    chamber_in = ", ".join(f"'{c}'" for c in sorted(set(chambers)))
    recipe_or = " OR ".join(f"UPPER(lwr.recipe) LIKE '{r}%'" for r in sorted(set(recipe_prefixes)))

    start_s = _to_sql_date(start_time - pd.Timedelta(days=2))
    end_s = _to_sql_date(end_time + pd.Timedelta(days=1))

    sql = f"""
SELECT
      wch.slot AS WAFER_NUM
    , wch.wafer AS ELWC_WAFER
    , e.entity AS ENTITY
    , wch.subentity AS PRIMARY_EQUIP
    , wch.lot AS ACTUAL_LOT
    , wch.slot AS ELWC_SLOT
    , wch.operation AS OPERATION
    , wch.start_time AS SUBENTITY_START_TIME
    , wch.end_time AS SUBENTITY_END_TIME
    , lwr.recipe AS SEQ_RECIPE
    , lwr.recipe AS WAFER_RECIPE
    , lrc.oper_short_desc AS OPER_SHORT_DESC
FROM F_LotEntityHist leh
INNER JOIN F_WaferChamberHist wch
  ON leh.runkey = wch.runkey
INNER JOIN F_Entity e
  ON e.facility NOT IN ('Test','Intel')
 AND e.entity = wch.entity
 AND e.entity = leh.entity
INNER JOIN F_Lot_Wafer_Recipe lwr
  ON lwr.recipe_id = wch.wafer_chamber_recipe_id
INNER JOIN F_Lot_Run_card lrc
  ON lrc.lotoperkey = wch.lotoperkey
WHERE wch.start_time >= TO_DATE('{start_s}', 'YYYY-MM-DD HH24:MI:SS')
  AND wch.start_time <= TO_DATE('{end_s}', 'YYYY-MM-DD HH24:MI:SS')
  AND leh.entity LIKE 'AME%'
  AND wch.subentity IN ({chamber_in})
  AND wch.state = 'Completed'
  AND ({recipe_or})
"""

    conn = PyUber.connect(COUNTER_DATABASE)
    try:
        df = pd.read_sql(sql, conn)
    finally:
        conn.close()

    if df.empty:
        return df

    df["SUBENTITY_START_TIME"] = pd.to_datetime(df["SUBENTITY_START_TIME"], errors="coerce")
    df["SUBENTITY_END_TIME"] = pd.to_datetime(df["SUBENTITY_END_TIME"], errors="coerce")
    df["SUBENTITY_EVENT_TIME"] = df["SUBENTITY_END_TIME"].fillna(df["SUBENTITY_START_TIME"])
    df["WAFER_NUM"] = pd.to_numeric(df["WAFER_NUM"], errors="coerce")

    for col in ["SEQ_RECIPE", "WAFER_RECIPE", "OPER_SHORT_DESC"]:
        if col not in df.columns:
            df[col] = ""
        df[f"{col}_NORM"] = df[col].map(_norm_recipe)

    df["RECIPE_MATCH_KEY"] = (
        df["SEQ_RECIPE_NORM"]
        .where(df["SEQ_RECIPE_NORM"] != "", df["WAFER_RECIPE_NORM"])
        .where(lambda s: s != "", df["OPER_SHORT_DESC_NORM"])
    )

    return df.dropna(subset=["PRIMARY_EQUIP", "ACTUAL_LOT", "WAFER_NUM", "SUBENTITY_EVENT_TIME"])


def _attach_pm_to_stage_window(elwc_events: pd.DataFrame, start_time: pd.Timestamp, end_time: pd.Timestamp) -> pd.DataFrame:
    if elwc_events.empty:
        return elwc_events

    chambers = sorted(elwc_events["PRIMARY_EQUIP"].dropna().unique().tolist())
    lookback_days = max(30, int((pd.Timestamp.now() - start_time).days) + 14)
    counters = _fetch_pm_counter_history(
        chamber_filter=chambers,
        lookback_days=lookback_days,
        start_time=start_time - pd.Timedelta(days=2),
        end_time=end_time + pd.Timedelta(days=2),
    )

    if counters.empty:
        out = elwc_events.copy()
        for c in PM_COUNTER_OUTPUT_COLS:
            out[c] = np.nan
        return out

    counters = counters.sort_values(["PRIMARY_EQUIP", "COUNTER_TIME"])
    counters[PM_COUNTER_OUTPUT_COLS] = (
        counters.groupby("PRIMARY_EQUIP", dropna=False)[PM_COUNTER_OUTPUT_COLS].ffill()
    )

    parts: list[pd.DataFrame] = []
    for equip, grp in elwc_events.groupby("PRIMARY_EQUIP", dropna=False, sort=False):
        left = grp.sort_values("SUBENTITY_EVENT_TIME")
        right = counters[counters["PRIMARY_EQUIP"] == equip].sort_values("COUNTER_TIME")
        if right.empty:
            z = left.copy()
            for c in PM_COUNTER_OUTPUT_COLS:
                z[c] = np.nan
            parts.append(z)
            continue

        joined = pd.merge_asof(
            left,
            right,
            left_on="SUBENTITY_EVENT_TIME",
            right_on="COUNTER_TIME",
            direction="backward",
        )
        joined = joined.drop(columns=["PRIMARY_EQUIP_y", "COUNTER_TIME"], errors="ignore")
        joined = joined.rename(columns={"PRIMARY_EQUIP_x": "PRIMARY_EQUIP"})
        parts.append(joined)

    out = pd.concat(parts, ignore_index=True)
    for c in PM_COUNTER_OUTPUT_COLS:
        out[c] = pd.to_numeric(out.get(c), errors="coerce")
    return out


def _process_chunk(
    chunk_id: int,
    surf_chunk: pd.DataFrame,
    recipe_prefixes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    start_time = surf_chunk["INSPECTION_TIME"].min()
    end_time = surf_chunk["INSPECTION_TIME"].max()
    chambers = sorted(surf_chunk["PRIMARY_EQUIP"].dropna().unique().tolist())

    elwc = _fetch_elwc_events_window(
        chambers=chambers,
        recipe_prefixes=recipe_prefixes,
        start_time=start_time,
        end_time=end_time,
    )
    stage = _attach_pm_to_stage_window(elwc, start_time=start_time, end_time=end_time)

    lookback_days = max(30, int((pd.Timestamp.now() - start_time).days) + 14)
    attached = _attach_elwc_stage_to_surf(
        surf_chunk,
        stage,
        counter_lookback_days=lookback_days,
    )

    attached["ELWC_STAGE_CHUNK_ID"] = int(chunk_id)
    if not stage.empty:
        stage = stage.copy()
        stage["ELWC_STAGE_CHUNK_ID"] = int(chunk_id)

    summary = {
        "chunk_id": int(chunk_id),
        "surf_rows": int(len(surf_chunk)),
        "chambers": int(len(chambers)),
        "start_time": str(start_time),
        "end_time": str(end_time),
        "elwc_rows": int(len(elwc)),
        "stage_rows": int(len(stage)),
        "match_rows": int(attached["ELWC_MATCH_TIME"].notna().sum()) if "ELWC_MATCH_TIME" in attached.columns else 0,
        "counter_fallback_rows": int(attached.get("ELWC_COUNTER_FALLBACK", pd.Series(dtype=float)).fillna(0).sum()),
    }
    return attached, stage, summary


def build_stage(
    lookback_days: int | None,
    chunk_events: int,
) -> dict[str, object]:
    _configure_logging()
    metrics_path = PIPELINE_PATHS.surf_metrics_csv
    surf = _load_surf_scope(metrics_path, lookback_days=lookback_days)
    if surf.empty:
        payload = {
            "generated_at": datetime.now().isoformat(),
            "message": "No SURF rows in selected scope.",
            "input_metrics": str(metrics_path),
        }
        out_artifact = PIPELINE_PATHS.artifacts_dir / "surf_scan_elwc_pm_stage_full_summary.json"
        out_artifact.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    keys = _build_event_chunks(surf, chunk_events=chunk_events)
    recipe_prefixes = _recipe_prefixes_from_map()
    total_chunks = int(keys["CHUNK_ID"].nunique())
    LOGGER.info(
        "[stage] start rows=%s unique_events=%s chunks=%s lookback_days=%s chunk_events=%s",
        len(surf),
        len(keys),
        total_chunks,
        lookback_days,
        chunk_events,
    )

    attached_parts: list[pd.DataFrame] = []
    stage_parts: list[pd.DataFrame] = []
    chunk_summaries: list[dict[str, object]] = []

    event_key_cols = ["INSPECTION_TIME", "PRIMARY_EQUIP", "ACTUAL_LOT"]
    for chunk_id, chunk_keys in keys.groupby("CHUNK_ID", sort=True):
        LOGGER.info(
            "[stage] chunk %s/%s begin events=%s",
            int(chunk_id) + 1,
            total_chunks,
            len(chunk_keys),
        )
        surf_chunk = surf.merge(chunk_keys[event_key_cols], on=event_key_cols, how="inner")
        attached, stage, summary = _process_chunk(int(chunk_id), surf_chunk, recipe_prefixes)
        attached_parts.append(attached)
        if not stage.empty:
            stage_parts.append(stage)
        chunk_summaries.append(summary)
        LOGGER.info(
            "[stage] chunk %s/%s done surf_rows=%s elwc_rows=%s match_rows=%s fallback_rows=%s",
            int(chunk_id) + 1,
            total_chunks,
            summary.get("surf_rows", 0),
            summary.get("elwc_rows", 0),
            summary.get("match_rows", 0),
            summary.get("counter_fallback_rows", 0),
        )

    attached_all = pd.concat(attached_parts, ignore_index=True)
    stage_all = pd.concat(stage_parts, ignore_index=True) if stage_parts else pd.DataFrame()

    # Stage output should only carry ELWC-derived columns for apply; drop
    # canonical counters to avoid legacy confusion in stage artifacts.
    stage_legacy_cols = [
        c
        for c in STAGE_BLOCKED_CANONICAL_COUNTERS
        if c in attached_all.columns
    ]
    if stage_legacy_cols:
        attached_all = attached_all.drop(columns=stage_legacy_cols, errors="ignore")

    stage_metrics_path = PIPELINE_PATHS.surf_outputs_dir / "SS_METRICS_ELWC_PM_STAGE_FULL.csv"
    stage_events_path = PIPELINE_PATHS.surf_outputs_dir / "SS_ELWC_STAGE_PM_FULL.csv"
    artifact_path = PIPELINE_PATHS.artifacts_dir / "surf_scan_elwc_pm_stage_full_summary.json"

    attached_all.to_csv(stage_metrics_path, index=False)
    stage_all.to_csv(stage_events_path, index=False)

    payload: dict[str, object] = {
        "generated_at": datetime.now().isoformat(),
        "input_metrics": str(metrics_path),
        "stage_metrics_output": str(stage_metrics_path),
        "stage_events_output": str(stage_events_path),
        "lookback_days": None if lookback_days is None else int(lookback_days),
        "chunk_events": int(chunk_events),
        "total_surf_rows": int(len(surf)),
        "total_unique_events": int(len(keys)),
        "total_chunks": int(keys["CHUNK_ID"].nunique()),
        "elwc_match_rows": int(attached_all["ELWC_MATCH_TIME"].notna().sum()) if "ELWC_MATCH_TIME" in attached_all.columns else 0,
        "elwc_counter_fallback_rows": int(attached_all.get("ELWC_COUNTER_FALLBACK", pd.Series(dtype=float)).fillna(0).sum()),
        "elwc_pm_non_null": {
            c: int(attached_all.get(f"ELWC_{c}", pd.Series(dtype=float)).notna().sum())
            for c in PM_COUNTER_OUTPUT_COLS
        },
        "chunk_summaries": chunk_summaries,
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOGGER.info(
        "[stage] complete rows=%s match_rows=%s fallback_rows=%s stage_metrics=%s",
        payload.get("total_surf_rows", 0),
        payload.get("elwc_match_rows", 0),
        payload.get("elwc_counter_fallback_rows", 0),
        stage_metrics_path,
    )
    return payload


def _replace_pm_columns_from_stage(
    prod_csv: Path,
    stage_metrics_csv: Path,
    keep_diagnostics: bool,
    target_pm_cols: list[str],
) -> dict[str, object]:
    stage = pd.read_csv(stage_metrics_csv, low_memory=False)
    if stage.empty:
        return {"path": str(prod_csv), "rows": 0, "message": "Stage metrics is empty."}

    key_cols = ["WAFER_KEY", "INSPECTION_TIME"]
    use_cols = [
        *key_cols,
        *[f"ELWC_{c}" for c in target_pm_cols],
        "ELWC_MATCH_TIME",
        "ELWC_RECIPE_FALLBACK",
        "ELWC_COUNTER_FALLBACK",
        "ELWC_TIME_SOURCE",
    ]
    use_cols = [c for c in use_cols if c in stage.columns]
    stage = stage[use_cols].copy()
    stage_rename = {
        **{f"ELWC_{c}": f"STAGE_ELWC_{c}" for c in target_pm_cols if f"ELWC_{c}" in stage.columns},
        "ELWC_MATCH_TIME": "STAGE_ELWC_MATCH_TIME",
        "ELWC_RECIPE_FALLBACK": "STAGE_ELWC_RECIPE_FALLBACK",
        "ELWC_COUNTER_FALLBACK": "STAGE_ELWC_COUNTER_FALLBACK",
        "ELWC_TIME_SOURCE": "STAGE_ELWC_TIME_SOURCE",
    }
    stage = stage.rename(columns={k: v for k, v in stage_rename.items() if k in stage.columns})
    stage["INSPECTION_TIME"] = pd.to_datetime(stage["INSPECTION_TIME"], errors="coerce")
    stage = stage.dropna(subset=key_cols).drop_duplicates(subset=key_cols, keep="last")

    prod = pd.read_csv(prod_csv, low_memory=False)
    prod = prod.drop(columns=[c for c in LEGACY_COUNTER_COLUMNS_TO_REMOVE if c in prod.columns], errors="ignore")
    existing_elwc_cols = [c for c in prod.columns if c.startswith("ELWC_")]
    if existing_elwc_cols:
        LOGGER.info("[apply] dropping existing ELWC columns from %s: %s", prod_csv.name, existing_elwc_cols)
        prod = prod.drop(columns=existing_elwc_cols, errors="ignore")

    prod["INSPECTION_TIME"] = pd.to_datetime(prod["INSPECTION_TIME"], errors="coerce")
    before = {c: int(prod[c].notna().sum()) if c in prod.columns else 0 for c in target_pm_cols}

    merged = prod.merge(stage, on=key_cols, how="left")
    for c in target_pm_cols:
        source_col = f"STAGE_ELWC_{c}"
        if source_col in merged.columns:
            incoming = pd.to_numeric(merged[source_col], errors="coerce")
            existing = pd.to_numeric(merged[c], errors="coerce") if c in merged.columns else pd.Series(np.nan, index=merged.index)
            # Preserve previously populated RF values outside current stage scope.
            merged[c] = incoming.combine_first(existing)

    if keep_diagnostics:
        LOGGER.info("[apply] keep_diagnostics is ignored for production outputs; ELWC columns are always removed")

    # Production outputs should only contain canonical target columns.
    drop_cols = [c for c in merged.columns if c.startswith("ELWC_") or c.startswith("STAGE_ELWC_")]
    if drop_cols:
        merged = merged.drop(columns=drop_cols, errors="ignore")
    merged = merged.drop(columns=[c for c in LEGACY_COUNTER_COLUMNS_TO_REMOVE if c in merged.columns], errors="ignore")

    after = {c: int(merged[c].notna().sum()) if c in merged.columns else 0 for c in target_pm_cols}

    tmp = prod_csv.with_suffix(prod_csv.suffix + ".elwc_tmp")
    merged.to_csv(tmp, index=False)
    tmp.replace(prod_csv)

    return {
        "path": str(prod_csv),
        "rows": int(len(merged)),
        "pm_non_null_before": before,
        "pm_non_null_after": after,
    }


def apply_stage_to_production(stage_metrics_csv: Path, keep_diagnostics: bool) -> dict[str, object]:
    _configure_logging()
    LOGGER.info("[apply] start stage_metrics=%s", stage_metrics_csv)
    metrics_summary = _replace_pm_columns_from_stage(
        PIPELINE_PATHS.surf_metrics_csv,
        stage_metrics_csv,
        keep_diagnostics=keep_diagnostics,
        target_pm_cols=TARGET_RF_COLUMNS,
    )
    coords_summary = _replace_pm_columns_from_stage(
        PIPELINE_PATHS.surf_coordinates_csv,
        stage_metrics_csv,
        keep_diagnostics=keep_diagnostics,
        target_pm_cols=TARGET_RF_COLUMNS,
    )

    payload: dict[str, object] = {
        "generated_at": datetime.now().isoformat(),
        "stage_metrics_input": str(stage_metrics_csv),
        "target_pm_columns": TARGET_RF_COLUMNS,
        "metrics": metrics_summary,
        "coordinates": coords_summary,
    }
    artifact_path = PIPELINE_PATHS.artifacts_dir / "surf_scan_elwc_pm_stage_apply_summary.json"
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOGGER.info("[apply] complete metrics_rows=%s coordinates_rows=%s", metrics_summary.get("rows", 0), coords_summary.get("rows", 0))
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build chunked ELWC+PM stage output and optionally apply to production SURF CSVs."
    )
    parser.add_argument("--lookback-days", type=int, default=None, help="Optional SURF metrics lookback filter.")
    parser.add_argument("--chunk-events", type=int, default=100, help="Unique inspection events per chunk.")
    parser.add_argument(
        "--apply-production",
        action="store_true",
        help="After stage build, replace production PM columns using staged ELWC values.",
    )
    parser.add_argument(
        "--keep-diagnostics",
        action="store_true",
        help="Keep ELWC diagnostics columns in production outputs when applying.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    stage_payload = build_stage(
        lookback_days=args.lookback_days,
        chunk_events=args.chunk_events,
    )
    payload: dict[str, object] = {"stage": stage_payload}

    if args.apply_production and "stage_metrics_output" in stage_payload:
        apply_payload = apply_stage_to_production(
            Path(str(stage_payload["stage_metrics_output"])),
            keep_diagnostics=bool(args.keep_diagnostics),
        )
        payload["apply"] = apply_payload

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
