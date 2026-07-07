from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import PyUber

# Standalone config section: edit these values for local machine usage.
STANDALONE_CONFIG = {
    "database": "D1D_PROD_YAS_1278",
    "default_output_dir": "\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Defects\\BE\\outputs\\surf_scan\\ad_hoc\\",
    "default_lookback_days": 28,
    "default_step_layer_id": "6OX450GTO_M025_PST",
    "default_recipe": "6OX450GTO_SAAA_M025_PST",
    "default_process_equip": "GTO111_PC1",
    "default_inspect_equip": None,
    "default_lot_id": None,
    "default_class_name": None,
}

DATABASE = str(STANDALONE_CONFIG["database"])
DEFAULT_OUTPUT_DIR = Path(str(STANDALONE_CONFIG["default_output_dir"]))
DEFAULT_LOOKBACK_DAYS = int(STANDALONE_CONFIG["default_lookback_days"])
DEFAULT_STEP_LAYER_ID = str(STANDALONE_CONFIG["default_step_layer_id"])
DEFAULT_RECIPE = STANDALONE_CONFIG["default_recipe"]
DEFAULT_PROCESS_EQUIP = STANDALONE_CONFIG["default_process_equip"]
DEFAULT_INSPECT_EQUIP = STANDALONE_CONFIG["default_inspect_equip"]
DEFAULT_LOT_ID = STANDALONE_CONFIG["default_lot_id"]
DEFAULT_CLASS_NAME = STANDALONE_CONFIG["default_class_name"]
RECIPE_COLUMN_CANDIDATES = [
    "RECIPE_KEY",
    "RECIPE",
    "SEQ_RECIPE",
    "PROCESS_RECIPE",
    "LOT_RECIPE",
    "WAFER_RECIPE",
]


def _sql_quote(value: str) -> str:
    return value.replace("'", "''")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_")


def _ensure_output_dir(path: Path) -> Path:
    resolved = path.expanduser()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _discover_recipe_column(conn) -> str | None:
    cols_in = ", ".join(f"'{c}'" for c in RECIPE_COLUMN_CANDIDATES)
    sql = f"""
SELECT column_name
FROM all_tab_columns
WHERE owner = 'UDB'
  AND table_name = 'INSP_WAFER_SUMMARY'
  AND column_name IN ({cols_in})
ORDER BY CASE column_name
    WHEN 'RECIPE_KEY' THEN 1
    WHEN 'RECIPE' THEN 1
    WHEN 'SEQ_RECIPE' THEN 2
    WHEN 'PROCESS_RECIPE' THEN 3
    WHEN 'LOT_RECIPE' THEN 4
    WHEN 'WAFER_RECIPE' THEN 5
    ELSE 99 END
"""
    found = pd.read_sql(sql, conn)
    if found.empty:
        return None
    return str(found.iloc[0]["COLUMN_NAME"])


def _fetch_wafer_summary(
    conn,
    lookback_days: int,
    step_layer_id: str,
    recipe: str | None,
    process_equip: str | None,
    inspect_equip: str | None,
    lot_id: str | None,
) -> tuple[pd.DataFrame, str | None]:
    recipe_col = _discover_recipe_column(conn)

    if recipe and not recipe_col:
        raise RuntimeError(
            "No recipe-like column found on UDB.INSP_WAFER_SUMMARY, "
            "so recipe filtering cannot be applied safely."
        )

    recipe_join = ""
    recipe_filter_clause = ""
    if recipe_col == "RECIPE_KEY":
        recipe_join = "LEFT JOIN UDB.INSP_RECIPE r ON r.RECIPE_KEY = s.RECIPE_KEY"
        recipe_select = "r.RECIPE_ID AS RECIPE"
        if recipe:
            recipe_filter_clause = f"UPPER(r.RECIPE_ID) = UPPER('{_sql_quote(recipe)}')"
    else:
        recipe_select = f"s.{recipe_col} AS RECIPE" if recipe_col else "CAST(NULL AS VARCHAR2(128)) AS RECIPE"
        if recipe and recipe_col:
            recipe_filter_clause = f"UPPER(s.{recipe_col}) = UPPER('{_sql_quote(recipe)}')"

    where_clauses = [
        f"s.INSPECTION_TIME >= SYSDATE - {int(lookback_days)}",
        f"s.LAYER_ID = '{_sql_quote(step_layer_id)}'",
    ]

    if process_equip:
        where_clauses.append(f"s.PROCESS_EQUIP_ID = '{_sql_quote(process_equip)}'")
    if inspect_equip:
        where_clauses.append(f"s.INSPECT_EQUIP_ID = '{_sql_quote(inspect_equip)}'")
    if lot_id:
        where_clauses.append(f"s.LOT_ID = '{_sql_quote(lot_id)}'")
    if recipe_filter_clause:
        where_clauses.append(recipe_filter_clause)

    where_sql = "\n  AND ".join(where_clauses)
    sql = f"""
SELECT
    s.WAFER_KEY,
    s.INSPECTION_TIME,
    s.SCRIBE_ID AS WAFER_ID,
    s.LOT_ID AS LOT_ID,
    SUBSTR(s.LOT_ID, 1, 7) AS LOT7,
    s.LAYER_ID AS STEP_LAYER_ID,
    s.PROCESS_EQUIP_ID AS PROCESS_EQUIP,
    s.INSPECT_EQUIP_ID AS INSPECT_EQP,
    s.SLOT_ID,
    s.DEFECTS AS N_DEFECTS,
    s.ADDER_DEFECTS,
    {recipe_select}
FROM UDB.INSP_WAFER_SUMMARY s
{recipe_join}
WHERE {where_sql}
"""
    summary = pd.read_sql(sql, conn)
    if not summary.empty:
        summary["INSPECTION_TIME"] = pd.to_datetime(summary["INSPECTION_TIME"], errors="coerce")
    return summary, recipe_col


def _fetch_defects(
    conn,
    pairs: list[tuple[pd.Timestamp, int]],
    class_name: str | None,
) -> pd.DataFrame:
    if not pairs:
        return pd.DataFrame()

    rows = []
    for ts, wafer_key in pairs:
        ts_str = pd.Timestamp(ts).strftime("%Y%m%d%H%M%S")
        rows.append(f"(TO_DATE('{ts_str}','YYYYMMDDHH24MISS'), {int(wafer_key)})")

    class_filter = ""
    if class_name:
        class_filter = f"\n  AND UPPER(c.NAME) = UPPER('{_sql_quote(class_name)}')"

    sql = f"""
SELECT
    s.WAFER_KEY,
    s.INSPECTION_TIME,
    s.SCRIBE_ID AS WAFER_ID,
    s.LOT_ID AS LOT_ID,
    s.LAYER_ID AS STEP_LAYER_ID,
    s.PROCESS_EQUIP_ID AS PROCESS_EQUIP,
    s.INSPECT_EQUIP_ID AS INSPECT_EQP,
    TO_CHAR(d.DEFECT_ID) AS DEFECT_ID,
    c.NAME AS CLASSNAME,
    f.NAME AS FINEBIN,
    TO_CHAR((d.WAFER_X - s.CENTER_X) / 1000000.0) AS WAFER_X_MM,
    TO_CHAR((d.WAFER_Y - s.CENTER_Y) / 1000000.0) AS WAFER_Y_MM,
    TO_CHAR(d.SIZE_D / 1000.0) AS SIZE_D_UM,
    TO_CHAR(d.IMAGES) AS IMAGE_COUNT
FROM UDB.INSP_WAFER_SUMMARY s
INNER JOIN UDB.INSP_DEFECT d
    ON d.WAFER_KEY = s.WAFER_KEY
   AND d.INSPECTION_TIME = s.INSPECTION_TIME
   AND d.ADDER = 1
LEFT JOIN UDB.CLASS c
    ON c.CLASS_ID = d.CLASS_NUMBER
LEFT JOIN UDB.FINEBIN f
    ON f.FINEBIN_ID = d.AUTOMATED_OPTICAL_CLASS
WHERE (s.INSPECTION_TIME, s.WAFER_KEY) IN (
    {', '.join(rows)}
){class_filter}
"""

    defects = pd.read_sql(sql, conn)
    if defects.empty:
        return defects

    defects["INSPECTION_TIME"] = pd.to_datetime(defects["INSPECTION_TIME"], errors="coerce")
    for col in ["WAFER_X_MM", "WAFER_Y_MM", "SIZE_D_UM", "IMAGE_COUNT"]:
        defects[col] = pd.to_numeric(defects[col], errors="coerce")
    return defects


def _build_metrics(summary_df: pd.DataFrame, defects_df: pd.DataFrame) -> pd.DataFrame:
    metrics = summary_df.copy()
    if metrics.empty:
        return metrics

    agg = pd.DataFrame(columns=["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ROW_COUNT", "IMAGE_DEFECT_COUNT"])
    if not defects_df.empty:
        agg = (
            defects_df.groupby(["WAFER_KEY", "INSPECTION_TIME"], as_index=False)
            .agg(
                DEFECT_ROW_COUNT=("DEFECT_ID", "size"),
                IMAGE_DEFECT_COUNT=("IMAGE_COUNT", lambda s: int((pd.to_numeric(s, errors="coerce").fillna(0) > 0).sum())),
            )
        )

    metrics = metrics.merge(agg, on=["WAFER_KEY", "INSPECTION_TIME"], how="left")
    metrics["DEFECT_ROW_COUNT"] = metrics["DEFECT_ROW_COUNT"].fillna(0).astype(int)
    metrics["IMAGE_DEFECT_COUNT"] = metrics["IMAGE_DEFECT_COUNT"].fillna(0).astype(int)
    metrics["HAS_DEFECT_ROWS"] = (metrics["DEFECT_ROW_COUNT"] > 0).astype(int)
    metrics["HAS_IMAGES"] = (metrics["IMAGE_DEFECT_COUNT"] > 0).astype(int)
    metrics["STATUS"] = metrics["ADDER_DEFECTS"].apply(
        lambda x: "BASELINE" if pd.notna(x) and x < 10 else "HIGHFLIER"
    )
    metrics["YYMM"] = pd.to_datetime(metrics["INSPECTION_TIME"], errors="coerce").dt.strftime("%y%m")

    lead = [
        "YYMM",
        "INSPECTION_TIME",
        "PROCESS_EQUIP",
        "INSPECT_EQP",
        "LOT_ID",
        "LOT7",
        "WAFER_ID",
        "WAFER_KEY",
        "SLOT_ID",
        "STEP_LAYER_ID",
        "RECIPE",
        "N_DEFECTS",
        "ADDER_DEFECTS",
        "STATUS",
        "DEFECT_ROW_COUNT",
        "IMAGE_DEFECT_COUNT",
        "HAS_DEFECT_ROWS",
        "HAS_IMAGES",
    ]
    ordered = [c for c in lead if c in metrics.columns] + [c for c in metrics.columns if c not in lead]
    return metrics[ordered].sort_values("INSPECTION_TIME", ascending=False, kind="mergesort")


def _build_coordinates(defects_df: pd.DataFrame, summary_df: pd.DataFrame) -> pd.DataFrame:
    if defects_df.empty:
        return defects_df

    join_cols = [
        "WAFER_KEY",
        "INSPECTION_TIME",
        "LOT7",
        "STEP_LAYER_ID",
        "PROCESS_EQUIP",
        "INSPECT_EQP",
        "RECIPE",
        "SLOT_ID",
        "N_DEFECTS",
        "ADDER_DEFECTS",
    ]
    summary_lookup = summary_df[join_cols].drop_duplicates(["WAFER_KEY", "INSPECTION_TIME"])

    coords = defects_df.merge(summary_lookup, on=["WAFER_KEY", "INSPECTION_TIME"], how="left")
    coords["STATUS"] = coords["ADDER_DEFECTS"].apply(
        lambda x: "BASELINE" if pd.notna(x) and x < 10 else "HIGHFLIER"
    )
    coords["YYMM"] = pd.to_datetime(coords["INSPECTION_TIME"], errors="coerce").dt.strftime("%y%m")

    lead = [
        "YYMM",
        "INSPECTION_TIME",
        "PROCESS_EQUIP",
        "INSPECT_EQP",
        "LOT_ID",
        "LOT7",
        "WAFER_ID",
        "WAFER_KEY",
        "SLOT_ID",
        "STEP_LAYER_ID",
        "RECIPE",
        "DEFECT_ID",
        "CLASSNAME",
        "FINEBIN",
        "WAFER_X_MM",
        "WAFER_Y_MM",
        "SIZE_D_UM",
        "IMAGE_COUNT",
        "N_DEFECTS",
        "ADDER_DEFECTS",
        "STATUS",
    ]
    ordered = [c for c in lead if c in coords.columns] + [c for c in coords.columns if c not in lead]
    return coords[ordered].sort_values("INSPECTION_TIME", ascending=False, kind="mergesort")


def run_lightweight_query(
    lookback_days: int,
    step_layer_id: str,
    recipe: str | None,
    process_equip: str | None,
    inspect_equip: str | None,
    lot_id: str | None,
    class_name: str | None,
    output_dir: Path,
) -> dict[str, object]:
    output_dir = _ensure_output_dir(output_dir)

    conn = PyUber.connect(DATABASE)
    try:
        summary_df, recipe_col = _fetch_wafer_summary(
            conn=conn,
            lookback_days=lookback_days,
            step_layer_id=step_layer_id,
            recipe=recipe,
            process_equip=process_equip,
            inspect_equip=inspect_equip,
            lot_id=lot_id,
        )

        pairs = [
            (row["INSPECTION_TIME"], int(row["WAFER_KEY"]))
            for _, row in summary_df.iterrows()
            if pd.notna(row.get("INSPECTION_TIME")) and pd.notna(row.get("WAFER_KEY"))
        ]
        pairs = list(dict.fromkeys(pairs))

        defects_df = _fetch_defects(conn=conn, pairs=pairs, class_name=class_name)
    finally:
        conn.close()

    metrics_df = _build_metrics(summary_df, defects_df)
    coords_df = _build_coordinates(defects_df, summary_df)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    layer_slug = _slug(step_layer_id)
    recipe_slug = _slug(recipe or "all_recipes")
    base = f"SS_LIGHT_{lookback_days}d_{layer_slug}_{recipe_slug}_{stamp}"

    metrics_path = output_dir / f"{base}_METRICS.csv"
    coords_path = output_dir / f"{base}_COORDINATES.csv"
    summary_path = output_dir / f"{base}_SUMMARY.json"

    metrics_df.to_csv(metrics_path, index=False)
    coords_df.to_csv(coords_path, index=False)

    summary_payload = {
        "database": DATABASE,
        "lookback_days": int(lookback_days),
        "filters": {
            "step_layer_id": step_layer_id,
            "recipe": recipe,
            "recipe_column_used": recipe_col,
            "process_equip": process_equip,
            "inspect_equip": inspect_equip,
            "lot_id": lot_id,
            "class_name": class_name,
        },
        "rows": {
            "wafer_summary": int(len(summary_df)),
            "metrics": int(len(metrics_df)),
            "coordinates": int(len(coords_df)),
            "unique_wafers": int(summary_df["WAFER_KEY"].nunique()) if not summary_df.empty else 0,
        },
        "outputs": {
            "metrics_csv": str(metrics_path),
            "coordinates_csv": str(coords_path),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    print("Lightweight SURF query complete")
    print(f"  wafer_summary_rows: {len(summary_df)}")
    print(f"  metrics_rows:       {len(metrics_df)}")
    print(f"  coordinate_rows:    {len(coords_df)}")
    print(f"  recipe_column:      {recipe_col}")
    print(f"  metrics_csv:        {metrics_path}")
    print(f"  coordinates_csv:    {coords_path}")
    print(f"  summary_json:       {summary_path}")

    return summary_payload


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a lightweight SURF metrics + coordinates query for a specific step layer/recipe window."
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"Lookback window in days (default from STANDALONE_CONFIG: {DEFAULT_LOOKBACK_DAYS})",
    )
    parser.add_argument(
        "--step-layer-id",
        default=DEFAULT_STEP_LAYER_ID,
        help="Exact INSP_WAFER_SUMMARY.LAYER_ID to query (default from STANDALONE_CONFIG)",
    )
    parser.add_argument(
        "--recipe",
        default=DEFAULT_RECIPE,
        help="Exact recipe filter (default from STANDALONE_CONFIG)",
    )
    parser.add_argument(
        "--process-equip",
        default=DEFAULT_PROCESS_EQUIP,
        help="Exact PROCESS_EQUIP_ID filter (default from STANDALONE_CONFIG)",
    )
    parser.add_argument(
        "--inspect-equip",
        default=DEFAULT_INSPECT_EQUIP,
        help="Exact INSPECT_EQUIP_ID filter (default from STANDALONE_CONFIG)",
    )
    parser.add_argument(
        "--lot-id",
        default=DEFAULT_LOT_ID,
        help="Exact LOT_ID filter (default from STANDALONE_CONFIG)",
    )
    parser.add_argument(
        "--class-name",
        default=DEFAULT_CLASS_NAME,
        help="Optional CLASS filter in INSP_DEFECT (default from STANDALONE_CONFIG)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Folder for output CSV/JSON artifacts",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    run_lightweight_query(
        lookback_days=args.lookback_days,
        step_layer_id=args.step_layer_id,
        recipe=args.recipe,
        process_equip=args.process_equip,
        inspect_equip=args.inspect_equip,
        lot_id=args.lot_id,
        class_name=args.class_name,
        output_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
