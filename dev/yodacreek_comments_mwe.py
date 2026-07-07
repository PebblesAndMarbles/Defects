#!/usr/bin/env python3
"""Minimal Yodacreek DefMet comments fetch example.

This probe connects to D1D_PROD_YODACREEKV3_1278 and queries
UDB.USR_DefMet_Comments for either a specific lot or a batch of lots
derived from the production defect coordinates CSV.
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path
from typing import Iterable

import pandas as pd
import PyUber

# Match existing workspace patterns where pandas warns that DBAPI objects are
# not SQLAlchemy connectables. PyUber intentionally provides a DBAPI connection.
warnings.filterwarnings(
    "ignore",
    message=".*SQLAlchemy.*",
    category=UserWarning,
)

DATABASE = "D1D_PROD_YODACREEKV3_1278"
TABLE = "UDB.USR_DefMet_Comments"
DEFAULT_LOT = "D6026420"
DEFAULT_CHUNK_SIZE = 200
DEFAULT_INPUT_CSV = Path(
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED.csv"
)
DEFAULT_BATCH_OUT = Path(
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\dev\yodacreek_comments_M5CL_M6CL_all_lots.csv"
)

TARGET_LAYERS = {"M5CL", "M6CL"}
LAYER_NORMALIZATION = {
    "8M5CL": "M5CL",
    "8M6CL": "M6CL",
    "M5CL": "M5CL",
    "M6CL": "M6CL",
}
RAW_COMMENT_LAYER_FILTER = ("M5CL", "M6CL", "8M5CL", "8M6CL")


def _connect():
    return PyUber.connect(DATABASE)


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _normalize_layer(value: str) -> str:
    layer = str(value).strip().upper()
    return LAYER_NORMALIZATION.get(layer, "")


def _clean_lot(value: str) -> str:
    if value is None:
        return ""
    lot = str(value).strip()
    if lot.lower() in {"", "nan", "none"}:
        return ""
    return lot


def _chunks(values: list[str], chunk_size: int) -> Iterable[list[str]]:
    for i in range(0, len(values), chunk_size):
        yield values[i : i + chunk_size]


def _find_lot_column(df: pd.DataFrame) -> str | None:
    lot_col = _find_column_case_insensitive(df, ["LOT"])
    if lot_col is not None:
        return lot_col
    for candidate in ("Lot", "lot"):
        if candidate in df.columns:
            return candidate
    return None


def _find_column_case_insensitive(
    df: pd.DataFrame, candidates: list[str]
) -> str | None:
    lookup = {str(col).upper(): col for col in df.columns}
    for candidate in candidates:
        key = candidate.upper()
        if key in lookup:
            return lookup[key]
    return None


def extract_lots_from_production_csv(input_csv: Path) -> tuple[list[str], dict]:
    usecols = ["ACTUAL_LOT", "LOT", "LAYER"]
    try:
        src = pd.read_csv(input_csv, usecols=usecols, dtype=str, low_memory=False)
    except ValueError as exc:
        missing_msg = (
            "Input CSV is missing one or more required columns: "
            "ACTUAL_LOT, LOT, LAYER"
        )
        raise RuntimeError(missing_msg) from exc

    src["ACTUAL_LOT"] = src["ACTUAL_LOT"].map(_clean_lot)
    src["LOT"] = src["LOT"].map(_clean_lot)
    src["SRC_LAYER_NORM"] = src["LAYER"].map(_normalize_layer)

    src["LOT_QUERY"] = src["ACTUAL_LOT"]
    missing_actual = src["LOT_QUERY"] == ""
    src.loc[missing_actual, "LOT_QUERY"] = src.loc[missing_actual, "LOT"]

    filtered = src[
        (src["SRC_LAYER_NORM"].isin(TARGET_LAYERS)) & (src["LOT_QUERY"] != "")
    ].copy()

    unique_lots = list(dict.fromkeys(filtered["LOT_QUERY"].tolist()))
    summary = {
        "input_rows": len(src),
        "filtered_rows": len(filtered),
        "unique_lots": len(unique_lots),
    }
    return unique_lots, summary


def fetch_comments_for_lot(lot: str, limit: int | None = None) -> pd.DataFrame:
    lot_sql = _escape_sql_literal(lot)
    layer_sql = ", ".join(f"'{value}'" for value in RAW_COMMENT_LAYER_FILTER)
    where_clause = (
        f"WHERE dm0.LOT = '{lot_sql}' "
        f"AND dm0.LAYER IN ({layer_sql})"
    )

    if limit is not None and limit > 0:
        # SQL Server style TOP keeps this portable for the current target.
        top_prefix = f"TOP {int(limit)} "
    else:
        top_prefix = ""

    query = f"""
SELECT {top_prefix}dm0.*
FROM {TABLE} dm0
{where_clause}
"""

    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    layer_col = _find_column_case_insensitive(df, ["LAYER"])
    if layer_col is not None:
        df["COMMENT_LAYER_NORM"] = df[layer_col].map(_normalize_layer)
        df = df[df["COMMENT_LAYER_NORM"].isin(TARGET_LAYERS)].copy()
    return df


def fetch_comments_for_lots(
    lots: list[str], chunk_size: int = DEFAULT_CHUNK_SIZE, limit: int | None = None
) -> pd.DataFrame:
    if not lots:
        return pd.DataFrame()

    if chunk_size <= 0:
        chunk_size = DEFAULT_CHUNK_SIZE

    layer_sql = ", ".join(f"'{value}'" for value in RAW_COMMENT_LAYER_FILTER)
    total_chunks = (len(lots) + chunk_size - 1) // chunk_size
    frames: list[pd.DataFrame] = []

    conn = _connect()
    try:
        for chunk_index, lot_chunk in enumerate(_chunks(lots, chunk_size), start=1):
            in_clause = ", ".join(
                f"'{_escape_sql_literal(lot)}'" for lot in lot_chunk
            )
            query = f"""
SELECT dm0.*
FROM {TABLE} dm0
WHERE dm0.LOT IN ({in_clause})
  AND dm0.LAYER IN ({layer_sql})
"""

            chunk_df = pd.read_sql(query, conn)
            frames.append(chunk_df)
            print(
                f"Chunk {chunk_index}/{total_chunks}: "
                f"{len(lot_chunk)} lots -> {len(chunk_df)} rows"
            )
    finally:
        conn.close()

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    layer_col = _find_column_case_insensitive(out, ["LAYER"])
    if layer_col is not None:
        out["COMMENT_LAYER_NORM"] = out[layer_col].map(_normalize_layer)
        out = out[out["COMMENT_LAYER_NORM"].isin(TARGET_LAYERS)].copy()

    if limit is not None and limit > 0:
        out = out.head(limit).copy()

    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Yodacreek DefMet comments from Yodacreek 1278."
    )
    parser.add_argument(
        "--mode",
        choices=["single", "batch"],
        default="batch",
        help="Query mode: single lot or batch from production CSV (default: batch).",
    )
    parser.add_argument(
        "--lot",
        default=DEFAULT_LOT,
        help=f"Lot to query in single mode (default: {DEFAULT_LOT})",
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DEFAULT_INPUT_CSV,
        help="Production defect CSV used to derive lot list in batch mode.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Lots per SQL IN-clause chunk in batch mode (default: {DEFAULT_CHUNK_SIZE}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max rows in final output.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_BATCH_OUT,
        help="Output CSV path. Defaults to batch export path in dev.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print(f"Database: {DATABASE}")
    print(f"Table:    {TABLE}")
    print(f"Mode:     {args.mode}")

    try:
        if args.mode == "single":
            print(f"Lot:      {args.lot}")
            df = fetch_comments_for_lot(args.lot, args.limit)
        else:
            print(f"Input:    {args.input_csv}")
            lots, summary = extract_lots_from_production_csv(args.input_csv)
            print(f"Input rows scanned:            {summary['input_rows']}")
            print(f"Rows after M5CL/M6CL filter:  {summary['filtered_rows']}")
            print(f"Unique lots to query:          {summary['unique_lots']}")
            if not lots:
                print("No lots available after filtering. Nothing to query.")
                return 1

            df = fetch_comments_for_lots(lots, args.chunk_size, args.limit)

            lot_col = _find_lot_column(df)
            if lot_col is not None:
                returned_lots = set(df[lot_col].map(_clean_lot).tolist())
                requested_lots = set(lots)
                unmatched_count = len(requested_lots - returned_lots)
                print(f"Requested lots with no comments returned: {unmatched_count}")
    except Exception as exc:
        print("Query failed.")
        print(f"Error: {exc}")
        return 1

    print(f"Rows returned: {len(df)}")
    if df.empty:
        print("No rows returned for this lot.")
    else:
        print("Columns:")
        print(", ".join(df.columns.astype(str)))
        print("Sample rows:")
        print(df.head(10).to_string(index=False))

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.out, index=False)
        print(f"Wrote CSV: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
