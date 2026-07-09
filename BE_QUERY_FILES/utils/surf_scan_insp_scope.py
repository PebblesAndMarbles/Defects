from __future__ import annotations

import argparse
import gc
import json
import warnings
from pathlib import Path

import PyUber
import pandas as pd

from pipeline_config import PIPELINE_PATHS, ensure_pipeline_dirs
from surf_scan_config import DEFAULT_SEED_LOOKBACK_DAYS
import surf_scan_coordinates as surf_coords


warnings.filterwarnings(
    "ignore",
    message=".*SQLAlchemy.*",
    category=UserWarning,
)


TABLES_TO_PROFILE = (
    "INSP_WAFER_SUMMARY",
    "INSP_DEFECT",
    "INSP_ELEMENT",
    "INSP_WAFER_IMAGE",
)

EVENT_MAP = {1: "SS0", 3: "SS1", 10: "SS7"}


def _resolve_primary_equip_filter() -> list[str] | None:
    primary_equip = surf_coords.PRIMARY_EQUIP_FILTER or (
        surf_coords.SUBENTITY_FILTER if isinstance(surf_coords.SUBENTITY_FILTER, list) else
        [surf_coords.SUBENTITY_FILTER] if surf_coords.SUBENTITY_FILTER else None
    )
    return primary_equip


def _query_table_columns(conn, table_names: tuple[str, ...]) -> pd.DataFrame:
    table_in = ", ".join(f"'{name.upper()}'" for name in table_names)
    sql = f"""
SELECT
    owner,
    table_name,
    column_name,
    data_type,
    data_length,
    data_precision,
    data_scale,
    nullable,
    column_id
FROM all_tab_columns
WHERE owner = 'UDB'
  AND table_name IN ({table_in})
ORDER BY table_name, column_id
"""
    return pd.read_sql(sql, conn)


def _filter_candidate_columns(columns_df: pd.DataFrame) -> pd.DataFrame:
    candidate_pattern = (
        r"TIME|DATE|SLOT|ORDER|SEQ|RECIPE|RUN|STEP|WAFER|LOT|EQUIP|ENTITY|LAYER"
    )
    mask = columns_df["COLUMN_NAME"].astype(str).str.contains(candidate_pattern, case=False, regex=True)
    return columns_df[mask].reset_index(drop=True)


def _fetch_summary_samples(conn, lookback_days: int, include_seg: bool) -> pd.DataFrame:
    primary_equip = _resolve_primary_equip_filter()

    ss_df = surf_coords._fetch_wafer_summary_ss(
        conn,
        lookback_days=lookback_days,
        layer_filter=surf_coords.SS_LAYER_FILTER,
        chamber_filter=primary_equip,
    ).copy()
    ss_df["SCAN_FAMILY"] = "SS"

    parts = [ss_df]
    if include_seg:
        seg_df = surf_coords._fetch_wafer_summary_ss(
            conn,
            lookback_days=lookback_days,
            layer_filter=surf_coords.SEG_LAYER_FILTER,
            chamber_filter=primary_equip,
        ).copy()
        if not seg_df.empty:
            seg_df["SCAN_FAMILY"] = "SEG"
            parts.append(seg_df)

    summary_df = pd.concat(parts, ignore_index=True)
    if summary_df.empty:
        return summary_df

    summary_df["INSPECTION_TIME"] = pd.to_datetime(summary_df["INSPECTION_TIME"], errors="coerce")
    summary_df["WAFER_NUM"] = pd.to_numeric(summary_df.get("WAFER_NUM"), errors="coerce")
    return summary_df


def _assign_candidate_runs(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return summary_df.copy()

    run_df = summary_df.copy()
    run_df = run_df.sort_values(
        ["SCAN_FAMILY", "ACTUAL_LOT", "PRIMARY_EQUIP", "INSPECTION_TIME", "WAFER_NUM", "WAFER_KEY"],
        kind="mergesort",
    ).reset_index(drop=True)

    gap = pd.Timedelta(hours=surf_coords.SS_RUN_GAP_HOURS)
    run_df["RUN_GROUP_INDEX"] = 0

    for keys, group in run_df.groupby(["SCAN_FAMILY", "ACTUAL_LOT", "PRIMARY_EQUIP"], sort=False):
        ordered = group.sort_values(["INSPECTION_TIME", "WAFER_NUM", "WAFER_KEY"], kind="mergesort")
        is_new = ordered["INSPECTION_TIME"].diff() > gap
        run_df.loc[ordered.index, "RUN_GROUP_INDEX"] = is_new.cumsum().astype(int)

    run_keys = ["SCAN_FAMILY", "ACTUAL_LOT", "PRIMARY_EQUIP", "RUN_GROUP_INDEX"]
    run_df = run_df.sort_values(run_keys + ["INSPECTION_TIME", "WAFER_NUM", "WAFER_KEY"], kind="mergesort")
    run_df["ROW_ORDER_IN_RUN"] = run_df.groupby(run_keys).cumcount() + 1
    run_df["RUN_MIN_SLOT"] = run_df.groupby(run_keys)["WAFER_NUM"].transform("min")
    run_df["SLOT_NORMALIZED_RUN_NUMBER"] = run_df["WAFER_NUM"] - run_df["RUN_MIN_SLOT"] + 1
    run_df["WAFER_RUN_NUMBER_CANDIDATE"] = run_df["SLOT_NORMALIZED_RUN_NUMBER"]
    run_df.loc[
        run_df["WAFER_RUN_NUMBER_CANDIDATE"].isna(),
        "WAFER_RUN_NUMBER_CANDIDATE",
    ] = run_df.loc[run_df["WAFER_RUN_NUMBER_CANDIDATE"].isna(), "ROW_ORDER_IN_RUN"]
    run_df["WAFER_RUN_NUMBER_CANDIDATE"] = pd.to_numeric(
        run_df["WAFER_RUN_NUMBER_CANDIDATE"], errors="coerce"
    ).astype("Int64")

    run_df["N_WAFERS_IN_RUN_CANDIDATE"] = (
        run_df.groupby(run_keys)["WAFER_ID"].transform("nunique")
    )
    run_df["SS_EVENT_CANDIDATE"] = run_df["N_WAFERS_IN_RUN_CANDIDATE"].map(EVENT_MAP)
    run_df["EVENT_CANDIDATE"] = run_df["SS_EVENT_CANDIDATE"]
    run_df["SEG_EVENT_INDEX"] = pd.NA

    seg_mask = run_df["SCAN_FAMILY"].eq("SEG")
    if seg_mask.any():
        seg_indices: list[int] = []
        seg_event_indices: list[int] = []
        seg_event_names: list[str] = []
        seg_within_event: list[int] = []

        seg_df = run_df[seg_mask].copy()
        for _, group in seg_df.groupby(run_keys, sort=False):
            ordered = group.sort_values(["WAFER_NUM", "INSPECTION_TIME", "WAFER_KEY"], kind="mergesort")
            slot_rank = pd.Series(range(1, len(ordered) + 1), index=ordered.index, dtype="int64")
            event_index = ((slot_rank - 1) // surf_coords.SEG_WAFERS_PER_RECIPE) + 1
            within_event = ((slot_rank - 1) % surf_coords.SEG_WAFERS_PER_RECIPE) + 1

            for idx in ordered.index:
                event_idx = int(event_index.loc[idx])
                seg_indices.append(idx)
                seg_event_indices.append(event_idx)
                seg_within_event.append(int(within_event.loc[idx]))
                if 1 <= event_idx <= len(surf_coords.SEG_RECIPE_SEQUENCE):
                    seg_event_names.append(str(surf_coords.SEG_RECIPE_SEQUENCE[event_idx - 1]))
                else:
                    seg_event_names.append("PARTIAL_RUN")

        run_df.loc[seg_indices, "SEG_EVENT_INDEX"] = seg_event_indices
        run_df.loc[seg_indices, "EVENT_CANDIDATE"] = seg_event_names
        run_df.loc[seg_indices, "WAFER_RUN_NUMBER_CANDIDATE"] = seg_within_event

    run_df["RUN_START_TIME"] = run_df.groupby(run_keys)["INSPECTION_TIME"].transform("min")
    run_df["RUN_END_TIME"] = run_df.groupby(run_keys)["INSPECTION_TIME"].transform("max")
    run_df["RUN_SPAN_MINUTES"] = (
        (run_df["RUN_END_TIME"] - run_df["RUN_START_TIME"]).dt.total_seconds() / 60.0
    )
    run_df["INSP_RUN_TIME_CANDIDATE"] = run_df["INSPECTION_TIME"]
    return run_df.reset_index(drop=True)


def _find_same_day_duplicates(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame()

    dup_df = summary_df.copy()
    dup_df["INSPECTION_DAY"] = dup_df["INSPECTION_TIME"].dt.floor("D")
    grouped = (
        dup_df.groupby(["SCAN_FAMILY", "PRIMARY_EQUIP", "WAFER_ID", "INSPECTION_DAY"], dropna=False)
        .agg(
            ROW_COUNT=("WAFER_KEY", "size"),
            UNIQUE_WAFER_KEYS=("WAFER_KEY", "nunique"),
            UNIQUE_LOTS=("ACTUAL_LOT", "nunique"),
            FIRST_INSPECTION_TIME=("INSPECTION_TIME", "min"),
            LAST_INSPECTION_TIME=("INSPECTION_TIME", "max"),
            MIN_WAFER_NUM=("WAFER_NUM", "min"),
            MAX_WAFER_NUM=("WAFER_NUM", "max"),
        )
        .reset_index()
    )
    grouped["DAY_SPAN_MINUTES"] = (
        (grouped["LAST_INSPECTION_TIME"] - grouped["FIRST_INSPECTION_TIME"]).dt.total_seconds() / 60.0
    )
    return grouped[grouped["ROW_COUNT"] > 1].sort_values(
        ["ROW_COUNT", "DAY_SPAN_MINUTES"], ascending=[False, False], kind="mergesort"
    ).reset_index(drop=True)


def _summarize_runs(run_df: pd.DataFrame) -> pd.DataFrame:
    if run_df.empty:
        return pd.DataFrame()

    run_keys = ["SCAN_FAMILY", "ACTUAL_LOT", "PRIMARY_EQUIP", "RUN_GROUP_INDEX"]
    summary = (
        run_df.groupby(run_keys, dropna=False)
        .agg(
            RUN_START_TIME=("RUN_START_TIME", "min"),
            RUN_END_TIME=("RUN_END_TIME", "max"),
            RUN_SPAN_MINUTES=("RUN_SPAN_MINUTES", "max"),
            ROW_COUNT=("WAFER_KEY", "size"),
            DISTINCT_WAFERS=("WAFER_ID", "nunique"),
            MIN_WAFER_NUM=("WAFER_NUM", "min"),
            MAX_WAFER_NUM=("WAFER_NUM", "max"),
            MAX_WAFER_RUN_NUMBER=("WAFER_RUN_NUMBER_CANDIDATE", "max"),
            SS_EVENT_CANDIDATE=("SS_EVENT_CANDIDATE", "first"),
            EVENT_CANDIDATE=("EVENT_CANDIDATE", "first"),
        )
        .reset_index()
        .sort_values(run_keys, kind="mergesort")
    )
    summary["HAS_DUPLICATE_WAFERS_IN_RUN"] = summary["ROW_COUNT"] > summary["DISTINCT_WAFERS"]
    return summary


def _write_outputs(
    output_dir: Path,
    columns_df: pd.DataFrame,
    candidate_columns_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    run_df: pd.DataFrame,
    duplicate_df: pd.DataFrame,
    run_summary_df: pd.DataFrame,
    lookback_days: int,
    include_seg: bool,
) -> dict[str, str | int | float | None]:
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "columns_csv": output_dir / "INSP_SCOPE_COLUMNS.csv",
        "candidate_columns_csv": output_dir / "INSP_SCOPE_CANDIDATE_COLUMNS.csv",
        "sample_csv": output_dir / "INSP_SCOPE_SAMPLE.csv",
        "run_candidates_csv": output_dir / "INSP_SCOPE_RUN_CANDIDATES.csv",
        "duplicates_csv": output_dir / "INSP_SCOPE_DUPLICATES.csv",
        "run_summary_csv": output_dir / "INSP_SCOPE_RUN_SUMMARY.csv",
        "summary_json": output_dir / "INSP_SCOPE_SUMMARY.json",
    }

    columns_df.to_csv(paths["columns_csv"], index=False)
    candidate_columns_df.to_csv(paths["candidate_columns_csv"], index=False)
    summary_df.to_csv(paths["sample_csv"], index=False)
    run_df.to_csv(paths["run_candidates_csv"], index=False)
    duplicate_df.to_csv(paths["duplicates_csv"], index=False)
    run_summary_df.to_csv(paths["run_summary_csv"], index=False)

    summary_payload: dict[str, str | int | float | None] = {
        "lookback_days": int(lookback_days),
        "include_seg": bool(include_seg),
        "rows_sampled": int(len(summary_df)),
        "rows_run_candidates": int(len(run_df)),
        "duplicate_same_day_groups": int(len(duplicate_df)),
        "run_groups": int(len(run_summary_df)),
        "column_count_profiled": int(len(columns_df)),
        "candidate_column_count": int(len(candidate_columns_df)),
        "max_duplicate_day_span_minutes": (
            float(duplicate_df["DAY_SPAN_MINUTES"].max()) if not duplicate_df.empty else None
        ),
        "max_run_span_minutes": (
            float(run_summary_df["RUN_SPAN_MINUTES"].max()) if not run_summary_df.empty else None
        ),
        "paths": {key: str(value) for key, value in paths.items()},
    }
    paths["summary_json"].write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    return summary_payload


def run_scope(lookback_days: int, include_seg: bool) -> dict[str, str | int | float | None]:
    ensure_pipeline_dirs()
    output_dir = PIPELINE_PATHS.surf_outputs_dir / "INSP_SCOPE"

    conn = PyUber.connect(surf_coords.DATABASE)
    try:
        columns_df = _query_table_columns(conn, TABLES_TO_PROFILE)
        candidate_columns_df = _filter_candidate_columns(columns_df)
        summary_df = _fetch_summary_samples(conn, lookback_days=lookback_days, include_seg=include_seg)
    finally:
        conn.close()
        del conn
        gc.collect()

    run_df = _assign_candidate_runs(summary_df)
    duplicate_df = _find_same_day_duplicates(summary_df)
    run_summary_df = _summarize_runs(run_df)
    return _write_outputs(
        output_dir=output_dir,
        columns_df=columns_df,
        candidate_columns_df=candidate_columns_df,
        summary_df=summary_df,
        run_df=run_df,
        duplicate_df=duplicate_df,
        run_summary_df=run_summary_df,
        lookback_days=lookback_days,
        include_seg=include_seg,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="INSP-only scoping utility for SURF run-time/order feasibility.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=14,
        help=(
            "Recent lookback window for scoping pulls. "
            f"Use {DEFAULT_SEED_LOOKBACK_DAYS} only for broad backfill diagnostics."
        ),
    )
    parser.add_argument(
        "--skip-seg",
        action="store_true",
        help="Profile SS only and skip SEG sampling.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_scope(lookback_days=args.lookback_days, include_seg=not args.skip_seg)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())