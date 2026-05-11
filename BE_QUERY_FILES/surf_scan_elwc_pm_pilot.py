from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd
import PyUber

from pipeline_config import PIPELINE_PATHS
from surf_scan_coordinates import (
    COUNTER_DATABASE,
    PM_COUNTER_OUTPUT_COLS,
    _fetch_pm_counter_history,
)

EVENT_RECIPE_MAP = {
    "M_GO_ALL_SEG": "M_GO_ALL_SEG",
    "M_GO_C_SEG": "M_GO_C_SEG",
    "M_GO_E_SEG": "M_GO_E_SEG",
    "M_GO_M_SEG": "M_GO_M_SEG",
    "M_LIFT10X_SEG": "M_LIFT10X_SEG",
    "M_MECH_CYCLE_SEG": "M_MECH_CYCLE_SEG",
    "M_SFV10X_SEG": "M_SFV10X_SEG",
    "SS0": "M_SS_L100",
    "SS1": "M_SS_L100",
    "SS7": "M_SS_L100",
}
LOGGER = logging.getLogger("surf_scan_elwc_pm_pilot")


def _load_surf_metrics_60d(metrics_csv: str, lookback_days: int) -> pd.DataFrame:
    df = pd.read_csv(metrics_csv, low_memory=False)
    df["INSPECTION_TIME"] = pd.to_datetime(df["INSPECTION_TIME"], errors="coerce")
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
    df = df[df["INSPECTION_TIME"] >= cutoff].copy()
    df = df[df["EVENT"].isin(EVENT_RECIPE_MAP.keys())].copy()
    if df.empty:
        return df

    df["EXPECTED_RECIPE"] = df["EVENT"].map(EVENT_RECIPE_MAP)
    df["WAFER_NUM"] = pd.to_numeric(df.get("SLOT_ID"), errors="coerce")
    return df


def _norm_recipe(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value).strip().upper()


def _recipe_prefixes_from_map() -> list[str]:
    # Keep the ELWC pull bounded by expected recipe families from event mapping.
    return sorted({_norm_recipe(v) for v in EVENT_RECIPE_MAP.values() if _norm_recipe(v)})


def _fetch_elwc_events(chambers: list[str], recipe_prefixes: list[str], lookback_days: int) -> pd.DataFrame:
    if not chambers:
        return pd.DataFrame()

    chamber_in = ", ".join(f"'{c}'" for c in sorted(set(chambers)))
    recipe_like_clause = ""
    if recipe_prefixes:
        recipe_or = " OR ".join(f"UPPER(lwr.recipe) LIKE '{r}%'" for r in sorted(set(recipe_prefixes)))
        recipe_like_clause = f"\n  AND ({recipe_or})"

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
WHERE wch.start_time >= SYSDATE - {int(lookback_days)}
  AND leh.entity LIKE 'AME%'
  AND wch.subentity IN ({chamber_in})
    AND wch.state = 'Completed'{recipe_like_clause}
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


def _attach_pm_to_elwc_events(elwc_events: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
    if elwc_events.empty:
        return elwc_events

    chambers = sorted(elwc_events["PRIMARY_EQUIP"].dropna().unique().tolist())
    counters = _fetch_pm_counter_history(chamber_filter=chambers, lookback_days=lookback_days)
    if counters.empty:
        out = elwc_events.copy()
        for c in PM_COUNTER_OUTPUT_COLS:
            out[c] = np.nan
        return out

    counters = counters.sort_values(["PRIMARY_EQUIP", "COUNTER_TIME"])
    # Counter attributes are often logged at different timestamps; carry forward
    # last-known values per chamber to build a coherent snapshot at event time.
    counters[PM_COUNTER_OUTPUT_COLS] = (
        counters.groupby("PRIMARY_EQUIP", dropna=False)[PM_COUNTER_OUTPUT_COLS].ffill()
    )

    parts = []
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


def _build_counter_snapshots(chambers: list[str], start_time: pd.Timestamp, end_time: pd.Timestamp, lookback_days: int) -> pd.DataFrame:
    counters = _fetch_pm_counter_history(
        chamber_filter=chambers,
        lookback_days=lookback_days,
        start_time=start_time - pd.Timedelta(days=2) if pd.notna(start_time) else None,
        end_time=end_time + pd.Timedelta(days=7) if pd.notna(end_time) else None,
    )
    if counters.empty:
        return counters

    counters = counters.sort_values(["PRIMARY_EQUIP", "COUNTER_TIME"])
    counters[PM_COUNTER_OUTPUT_COLS] = (
        counters.groupby("PRIMARY_EQUIP", dropna=False)[PM_COUNTER_OUTPUT_COLS].ffill()
    )
    return counters


def _apply_inspection_counter_fallback(out_df: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
    out_df = out_df.copy()
    out_df["_ROW_ID"] = np.arange(len(out_df))
    elwc_cols = [f"ELWC_{c}" for c in PM_COUNTER_OUTPUT_COLS]
    for c in elwc_cols:
        if c not in out_df.columns:
            out_df[c] = np.nan

    missing_match_mask = (
        out_df["ELWC_MATCH_TIME"].isna()
        if "ELWC_MATCH_TIME" in out_df.columns
        else pd.Series(False, index=out_df.index)
    )
    partial_counter_mask = (
        out_df["ELWC_MATCH_TIME"].notna()
        & out_df[elwc_cols].isna().any(axis=1)
    )
    fallback_target_mask = missing_match_mask | partial_counter_mask

    if not fallback_target_mask.any():
        if "ELWC_COUNTER_FALLBACK" not in out_df.columns:
            out_df["ELWC_COUNTER_FALLBACK"] = 0
        if "ELWC_TIME_SOURCE" not in out_df.columns:
            out_df["ELWC_TIME_SOURCE"] = np.where(out_df["ELWC_MATCH_TIME"].notna(), "ELWC_EVENT", "UNMATCHED")
        return out_df.drop(columns=["_ROW_ID"], errors="ignore")

    missing = out_df.loc[fallback_target_mask].copy()
    chambers = sorted(missing["PRIMARY_EQUIP"].dropna().unique().tolist())
    if not chambers:
        out_df["ELWC_COUNTER_FALLBACK"] = 0
        out_df["ELWC_TIME_SOURCE"] = np.where(out_df["ELWC_MATCH_TIME"].notna(), "ELWC_EVENT", "UNMATCHED")
        return out_df.drop(columns=["_ROW_ID"], errors="ignore")

    counters = _build_counter_snapshots(
        chambers=chambers,
        start_time=missing["INSPECTION_TIME"].min(),
        end_time=missing["INSPECTION_TIME"].max(),
        lookback_days=lookback_days,
    )
    if counters.empty:
        out_df["ELWC_COUNTER_FALLBACK"] = 0
        out_df["ELWC_TIME_SOURCE"] = np.where(out_df["ELWC_MATCH_TIME"].notna(), "ELWC_EVENT", "UNMATCHED")
        return out_df.drop(columns=["_ROW_ID"], errors="ignore")

    parts = []
    for equip, grp in missing.groupby("PRIMARY_EQUIP", dropna=False, sort=False):
        left = grp.sort_values("INSPECTION_TIME")
        right = counters[counters["PRIMARY_EQUIP"] == equip].sort_values("COUNTER_TIME")
        if right.empty:
            left["FALLBACK_COUNTER_TIME"] = pd.NaT
            for c in PM_COUNTER_OUTPUT_COLS:
                left[f"FALLBACK_{c}"] = np.nan
                left[f"NEAR_{c}"] = np.nan
            parts.append(left)
            continue

        stage_slice = right[["COUNTER_TIME", *PM_COUNTER_OUTPUT_COLS]].copy()
        stage_slice = stage_slice.rename(columns={c: f"FALLBACK_{c}" for c in PM_COUNTER_OUTPUT_COLS})
        joined = pd.merge_asof(
            left,
            stage_slice,
            left_on="INSPECTION_TIME",
            right_on="COUNTER_TIME",
            direction="backward",
        )

        # Secondary nearest snapshot helps fill sparse attributes that did not
        # exist yet at the immediate backward timestamp.
        near_slice = right[["COUNTER_TIME", *PM_COUNTER_OUTPUT_COLS]].copy()
        near_slice = near_slice.rename(columns={c: f"NEAR_{c}" for c in PM_COUNTER_OUTPUT_COLS})
        near_joined = pd.merge_asof(
            left,
            near_slice,
            left_on="INSPECTION_TIME",
            right_on="COUNTER_TIME",
            direction="nearest",
        )
        for c in PM_COUNTER_OUTPUT_COLS:
            joined[f"NEAR_{c}"] = near_joined[f"NEAR_{c}"]
        joined = joined.rename(columns={"COUNTER_TIME": "FALLBACK_COUNTER_TIME"})
        parts.append(joined)

    fallback = pd.concat(parts, ignore_index=True)
    out_df["ELWC_COUNTER_FALLBACK"] = 0
    out_df["ELWC_TIME_SOURCE"] = np.where(out_df["ELWC_MATCH_TIME"].notna(), "ELWC_EVENT", "UNMATCHED")

    # For fallback-target rows, use only INSPECTION_PM semantics.
    target_ids = missing["_ROW_ID"].to_numpy()
    target_mask = out_df["_ROW_ID"].isin(target_ids)
    out_df.loc[target_mask, "ELWC_TIME_SOURCE"] = "INSPECTION_PM"
    out_df.loc[target_mask, "ELWC_MATCH_TIME"] = pd.NaT
    for c in PM_COUNTER_OUTPUT_COLS:
        out_df.loc[target_mask, f"ELWC_{c}"] = np.nan

    fallback_rows = fallback["FALLBACK_COUNTER_TIME"].notna()
    if fallback_rows.any():
        fallback_ids = fallback.loc[fallback_rows, "_ROW_ID"].to_numpy()
        out_mask = out_df["_ROW_ID"].isin(fallback_ids)
        # Guard against duplicate row ids from chunk/group joins so map() always
        # resolves to a scalar per id and assignments stay 1D.
        fill_map = (
            fallback.loc[fallback_rows]
            .sort_values(["_ROW_ID", "FALLBACK_COUNTER_TIME"])
            .drop_duplicates(subset=["_ROW_ID"], keep="last")
            .set_index("_ROW_ID")
        )
        out_df.loc[out_mask, "ELWC_MATCH_TIME"] = out_df.loc[out_mask, "_ROW_ID"].map(fill_map["FALLBACK_COUNTER_TIME"])
        out_df.loc[out_mask, "ELWC_COUNTER_FALLBACK"] = 1
        for c in PM_COUNTER_OUTPUT_COLS:
            primary = out_df.loc[out_mask, "_ROW_ID"].map(fill_map[f"FALLBACK_{c}"])
            near_col = f"NEAR_{c}"
            if near_col in fill_map.columns:
                secondary = out_df.loc[out_mask, "_ROW_ID"].map(fill_map[near_col])
                out_df.loc[out_mask, f"ELWC_{c}"] = primary.fillna(secondary)
            else:
                out_df.loc[out_mask, f"ELWC_{c}"] = primary

        # For remaining sparse attributes, fill from nearest non-null value per
        # chamber and attribute within a bounded window around inspection time.
        # This handles asynchronous attribute logging where one attribute updates
        # much less frequently than others.
        nearest_fill_max_hours = 24
        out_subset = out_df.loc[out_mask].copy()
        unresolved_attr_mask = out_subset[[f"ELWC_{c}" for c in PM_COUNTER_OUTPUT_COLS]].isna()
        if unresolved_attr_mask.any().any():
            nearest_fill_count = 0
            for idx, row in out_subset.iterrows():
                equip = row.get("PRIMARY_EQUIP")
                if pd.isna(equip):
                    continue

                right = counters[counters["PRIMARY_EQUIP"] == equip].copy()
                if right.empty:
                    continue

                inspect_ts = pd.to_datetime(row.get("INSPECTION_TIME"), errors="coerce")
                if pd.isna(inspect_ts):
                    continue

                for c in PM_COUNTER_OUTPUT_COLS:
                    target_col = f"ELWC_{c}"
                    if pd.notna(out_df.at[idx, target_col]):
                        continue

                    candidates = right[["COUNTER_TIME", c]].dropna(subset=[c]).copy()
                    if candidates.empty:
                        continue

                    candidates["ABS_DELTA_HOURS"] = (
                        (candidates["COUNTER_TIME"] - inspect_ts).abs().dt.total_seconds() / 3600.0
                    )
                    best = candidates.sort_values("ABS_DELTA_HOURS").iloc[0]
                    if float(best["ABS_DELTA_HOURS"]) <= float(nearest_fill_max_hours):
                        out_df.at[idx, target_col] = best[c]
                        nearest_fill_count += 1

            if nearest_fill_count:
                LOGGER.info(
                    "[fallback] nearest non-null attribute fills applied=%s max_hours=%s",
                    nearest_fill_count,
                    nearest_fill_max_hours,
                )

    # Emit compact diagnostics for rows that still have sparse counters after fallback.
    unresolved_mask = out_df[[f"ELWC_{c}" for c in PM_COUNTER_OUTPUT_COLS]].isna().any(axis=1)
    unresolved = out_df.loc[unresolved_mask, [
        "INSPECTION_TIME",
        "PRIMARY_EQUIP",
        "ACTUAL_LOT",
        "WAFER_ID",
        "ELWC_TIME_SOURCE",
        "ELWC_COUNTER_FALLBACK",
        *[f"ELWC_{c}" for c in PM_COUNTER_OUTPUT_COLS],
    ]].copy()
    if not unresolved.empty:
        LOGGER.info("[fallback] unresolved_rows=%s (showing up to 5)", len(unresolved))
        LOGGER.info("[fallback] sample=%s", unresolved.head(5).to_dict("records"))

    return out_df.drop(columns=["_ROW_ID"], errors="ignore")


def _attach_elwc_stage_to_surf(surf_df: pd.DataFrame, staged: pd.DataFrame, counter_lookback_days: int) -> pd.DataFrame:
    if surf_df.empty:
        return surf_df

    out = surf_df.copy()
    stale_elwc_cols = [
        *(f"ELWC_{c}" for c in PM_COUNTER_OUTPUT_COLS),
        "ELWC_MATCH_TIME",
        "ELWC_RECIPE_FALLBACK",
        "ELWC_TIME_SOURCE",
        "ELWC_COUNTER_FALLBACK",
    ]
    out = out.drop(columns=[c for c in stale_elwc_cols if c in out.columns], errors="ignore")
    if staged.empty:
        for c in PM_COUNTER_OUTPUT_COLS:
            out[f"ELWC_{c}"] = np.nan
        out["ELWC_MATCH_TIME"] = pd.NaT
        out["ELWC_RECIPE_FALLBACK"] = 0
        return _apply_inspection_counter_fallback(out, lookback_days=counter_lookback_days)

    staged = staged.copy()
    for col in ["SEQ_RECIPE", "WAFER_RECIPE", "OPER_SHORT_DESC", "RECIPE_MATCH_KEY"]:
        if col not in staged.columns:
            staged[col] = ""
    for col in ["SEQ_RECIPE", "WAFER_RECIPE", "OPER_SHORT_DESC", "RECIPE_MATCH_KEY"]:
        staged[f"{col}_NORM"] = staged[col].map(_norm_recipe)
    out["EXPECTED_RECIPE_NORM"] = out["EXPECTED_RECIPE"].map(_norm_recipe)

    key_cols = ["PRIMARY_EQUIP", "ACTUAL_LOT", "WAFER_NUM", "EXPECTED_RECIPE"]
    parts = []
    for key, g in out.groupby(key_cols, dropna=False, sort=False):
        equip, lot, wafer_num, expected_recipe = key
        expected_norm = _norm_recipe(expected_recipe)
        candidates_base = staged[
            (staged["PRIMARY_EQUIP"] == equip)
            & (staged["ACTUAL_LOT"] == lot)
            & (staged["WAFER_NUM"] == wafer_num)
        ].copy()
        candidates = candidates_base[
            (candidates_base["SEQ_RECIPE_NORM"] == expected_norm)
            | (candidates_base["WAFER_RECIPE_NORM"] == expected_norm)
            | (candidates_base["OPER_SHORT_DESC_NORM"] == expected_norm)
            | (candidates_base["RECIPE_MATCH_KEY_NORM"] == expected_norm)
        ].copy()
        used_fallback = 0
        if candidates.empty:
            candidates = candidates_base
            used_fallback = 1

        left = g.sort_values("INSPECTION_TIME")
        if candidates.empty:
            z = left.copy()
            for c in PM_COUNTER_OUTPUT_COLS:
                z[f"ELWC_{c}"] = np.nan
            z["ELWC_MATCH_TIME"] = pd.NaT
            z["ELWC_RECIPE_FALLBACK"] = 0
            parts.append(z)
            continue

        candidates = candidates.sort_values("SUBENTITY_EVENT_TIME")
        stage_cols = ["SUBENTITY_EVENT_TIME", *PM_COUNTER_OUTPUT_COLS]
        stage_slice = candidates[stage_cols].copy()
        rename_map = {c: f"STAGE_{c}" for c in PM_COUNTER_OUTPUT_COLS}
        stage_slice = stage_slice.rename(columns=rename_map)
        joined = pd.merge_asof(
            left,
            stage_slice,
            left_on="INSPECTION_TIME",
            right_on="SUBENTITY_EVENT_TIME",
            direction="backward",
        )

        joined = joined.rename(columns={"SUBENTITY_EVENT_TIME": "ELWC_MATCH_TIME"})
        for c in PM_COUNTER_OUTPUT_COLS:
            joined = joined.rename(columns={f"STAGE_{c}": f"ELWC_{c}"})
        joined["ELWC_RECIPE_FALLBACK"] = used_fallback
        joined["ELWC_TIME_SOURCE"] = "ELWC_EVENT"
        parts.append(joined)

    out_df = pd.concat(parts, ignore_index=True)
    out_df = out_df.drop(columns=["EXPECTED_RECIPE_NORM"], errors="ignore")
    return _apply_inspection_counter_fallback(out_df, lookback_days=counter_lookback_days)


def run_pilot(lookback_days: int = 60) -> dict[str, object]:
    metrics_path = PIPELINE_PATHS.surf_metrics_csv
    out_csv = PIPELINE_PATHS.surf_outputs_dir / f"SS_METRICS_ELWC_PM_PILOT_{lookback_days}D.csv"
    stage_csv = PIPELINE_PATHS.surf_outputs_dir / f"SS_ELWC_STAGE_PM_{lookback_days}D.csv"
    artifact_path = PIPELINE_PATHS.artifacts_dir / f"surf_scan_elwc_pm_pilot_{lookback_days}d_summary.json"

    surf = _load_surf_metrics_60d(str(metrics_path), lookback_days=lookback_days)
    if surf.empty:
        payload = {
            "generated_at": datetime.now().isoformat(),
            "lookback_days": int(lookback_days),
            "message": "No SURF rows in pilot window.",
            "input_metrics": str(metrics_path),
        }
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    chambers = sorted(surf["PRIMARY_EQUIP"].dropna().unique().tolist())
    recipe_prefixes = _recipe_prefixes_from_map()
    elwc_events = _fetch_elwc_events(
        chambers=chambers,
        recipe_prefixes=recipe_prefixes,
        lookback_days=lookback_days + 7,
    )
    staged = _attach_pm_to_elwc_events(elwc_events, lookback_days=lookback_days + 14)

    staged.to_csv(stage_csv, index=False)

    attached = _attach_elwc_stage_to_surf(surf, staged, counter_lookback_days=lookback_days + 14)
    attached.to_csv(out_csv, index=False)

    pm_non_null = {
        c: int(attached[f"ELWC_{c}"].notna().sum()) if f"ELWC_{c}" in attached.columns else 0
        for c in PM_COUNTER_OUTPUT_COLS
    }
    payload = {
        "generated_at": datetime.now().isoformat(),
        "lookback_days": int(lookback_days),
        "input_metrics": str(metrics_path),
        "output_metrics_pilot": str(out_csv),
        "output_stage": str(stage_csv),
        "surf_rows": int(len(surf)),
        "elwc_event_rows": int(len(elwc_events)),
        "staged_rows": int(len(staged)),
        "elwc_match_rows": int(attached["ELWC_MATCH_TIME"].notna().sum()) if "ELWC_MATCH_TIME" in attached.columns else 0,
        "elwc_recipe_fallback_rows": int(attached["ELWC_RECIPE_FALLBACK"].sum()) if "ELWC_RECIPE_FALLBACK" in attached.columns else 0,
        "elwc_counter_fallback_rows": int(attached["ELWC_COUNTER_FALLBACK"].sum()) if "ELWC_COUNTER_FALLBACK" in attached.columns else 0,
        "elwc_recipe_filter_prefixes": recipe_prefixes,
        "elwc_pm_non_null": pm_non_null,
        "elwc_recipe_samples": {
            "SEQ_RECIPE": sorted([str(x) for x in elwc_events.get("SEQ_RECIPE", pd.Series(dtype=object)).dropna().unique()[:20]]),
            "WAFER_RECIPE": sorted([str(x) for x in elwc_events.get("WAFER_RECIPE", pd.Series(dtype=object)).dropna().unique()[:20]]),
            "OPER_SHORT_DESC": sorted([str(x) for x in elwc_events.get("OPER_SHORT_DESC", pd.Series(dtype=object)).dropna().unique()[:20]]),
        },
        "notes": [
            "Pilot-only script: does not modify production SS_METRICS.csv/SS_COORDINATES.csv.",
            "ELWC templates were used as query references only; no ELWC file edits.",
            "Attachment rule: latest SUBENTITY_EVENT_TIME <= INSPECTION_TIME.",
        ],
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 60-day SURF ELWC+PM pilot staging and attachment.")
    parser.add_argument("--lookback-days", type=int, default=60)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_pilot(lookback_days=args.lookback_days)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
