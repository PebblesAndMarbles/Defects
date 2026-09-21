#!/usr/bin/env python3
"""Incrementally build an accumulating BOST history CSV.

This script reuses the proven treatment-rules BOST query and wide-column
construction from adhoc_bost_gate_rollout.py, but only queries wafer/layer
keys that are not already present in the durable history CSV.

Behavior:
- Source rows from outputs/wafer/8M5CL_8M6CL_EXTENDED.csv by default
- Preserve WAFER_ID and LAYER as the identity key
- Carry LOT7 and INSPECT_TIME through the history for verification and triage
- Append new rows to the history CSV in place
- Write a per-run tranche snapshot for staging/review
- Select the next tranche by most recent missing INSPECT_TIME first
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import PyUber

sys.path.insert(0, str(Path(__file__).resolve().parent))

from adhoc_bost_gate_rollout import (  # type: ignore
    FAB,
    FULL_FLOW_ALIASES,
    PROCESS,
    _build_bost_wide,
    _run_bost_query_treatment_rules,
)


DSN = "D1D_PROD_XEUS_GAJT"
DEFAULT_INPUT_CSV = Path(__file__).resolve().parents[1] / "outputs" / "wafer" / "8M5CL_8M6CL_EXTENDED.csv"
DEFAULT_HISTORY_CSV = Path(__file__).resolve().parent / "adhoc_bost_accumulating_history.csv"
DEFAULT_TRANCHE_DIR = Path(__file__).resolve().parent / "artifacts"

BASE_KEY_COLS = ["WAFER_ID", "LAYER"]
AUDIT_COLS = ["LOT7", "INSPECT_TIME"]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_CSV, help="Production CSV to source keys from")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY_CSV, help="Canonical accumulating CSV")
    parser.add_argument("--tranche-rows", type=int, default=100, help="Number of missing keys to query per run")
    parser.add_argument("--env", default="rf3prod", help="PyUber environment / DSN routing hint")
    parser.add_argument("--preview", action="store_true", help="Plan the next tranche without querying or writing")
    parser.add_argument("--limit", type=int, default=None, help="Optional source row limit for testing")
    return parser.parse_args()


def _load_csv(path: Path, limit: int | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    df = pd.read_csv(path)
    if limit is not None:
        df = df.head(limit).copy()
    return df


def _validate_source(df: pd.DataFrame) -> None:
    required = {"LOT", "LOT7", "WAFER_ID", "LAYER", "INSPECT_TIME"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required source columns: {missing}")


def _build_source_keys(df: pd.DataFrame) -> pd.DataFrame:
    work = df[["LOT", "LOT7", "WAFER_ID", "LAYER", "INSPECT_TIME"]].copy()
    work = work.dropna(subset=["WAFER_ID", "LAYER"]).copy()
    work["LOT"] = work["LOT"].astype(str).str.strip()
    work["LOT7"] = work["LOT7"].astype(str).str.strip()
    work["WAFER_ID"] = work["WAFER_ID"].astype(str).str.strip()
    work["LAYER"] = work["LAYER"].astype(str).str.strip()
    work["INSPECT_TIME_DT"] = pd.to_datetime(work["INSPECT_TIME"], errors="coerce")
    work = work.sort_values(
        by=["INSPECT_TIME_DT", "WAFER_ID", "LAYER", "LOT"],
        ascending=[False, True, True, True],
        kind="mergesort",
    )
    return work.drop_duplicates(subset=BASE_KEY_COLS, keep="first").reset_index(drop=True)


def _load_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=BASE_KEY_COLS + AUDIT_COLS)
    history = pd.read_csv(path)
    for column in BASE_KEY_COLS + AUDIT_COLS:
        if column not in history.columns:
            history[column] = pd.NA
    return history


def _history_key_index(history: pd.DataFrame) -> set[str]:
    if history.empty:
        return set()
    work = history[BASE_KEY_COLS].dropna().drop_duplicates().astype(str)
    return set(work.agg("|".join, axis=1).tolist())


def _select_next_tranche(source_keys: pd.DataFrame, history: pd.DataFrame, tranche_rows: int) -> pd.DataFrame:
    history_index = _history_key_index(history)
    key_index = source_keys[BASE_KEY_COLS].astype(str).agg("|".join, axis=1)
    missing = source_keys.loc[~key_index.isin(history_index)].copy()
    if tranche_rows > 0:
        missing = missing.head(tranche_rows).copy()
    return missing.reset_index(drop=True)


def _source_identity_frame(selected_keys: pd.DataFrame) -> pd.DataFrame:
    return selected_keys[BASE_KEY_COLS + AUDIT_COLS].drop_duplicates(subset=BASE_KEY_COLS, keep="first").copy()


def _query_bost_history(conn: PyUber.Connection, selected_keys: pd.DataFrame) -> pd.DataFrame:
    if selected_keys.empty:
        return pd.DataFrame(columns=["LOT", "WAFER_ID", "LAYER"])

    query_keys = selected_keys[["LOT", "WAFER_ID", "LAYER"]].copy()
    bost_raw = _run_bost_query_treatment_rules(conn, query_keys)
    if bost_raw.empty:
        bost_wide = pd.DataFrame(columns=["LOT", "WAFER_ID", "LAYER"])
    else:
        bost_wide, _, _ = _build_bost_wide(bost_raw)

    if bost_wide.empty:
        merged = selected_keys.copy()
    else:
        merged = selected_keys.merge(
            bost_wide,
            how="left",
            on=BASE_KEY_COLS,
            suffixes=("", "_BOST"),
        )

    merged = merged.drop(columns=["LOT_BOST"], errors="ignore")
    for column in AUDIT_COLS:
        if column not in merged.columns:
            merged[column] = pd.NA

    merged = merged.drop(columns=["INSPECT_TIME_DT"], errors="ignore")
    merged = merged.drop_duplicates(subset=BASE_KEY_COLS, keep="last")
    return merged


def _order_columns(df: pd.DataFrame) -> pd.DataFrame:
    preferred = [col for col in ["WAFER_ID", "LAYER", "LOT7", "INSPECT_TIME"] if col in df.columns]
    remaining = [col for col in df.columns if col not in preferred]
    return df[preferred + remaining]


def _normalize_history_schema(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    if "LOT_BOST" in normalized.columns:
        normalized = normalized.drop(columns=["LOT_BOST"])
    if "LOT" in normalized.columns and "LOT7" not in normalized.columns:
        normalized = normalized.rename(columns={"LOT": "LOT7"})
    normalized = normalized.drop(columns=["LOT"], errors="ignore")
    if "LOT7" not in normalized.columns:
        normalized["LOT7"] = pd.NA
    return _order_columns(normalized)


def _align_with_history_schema(existing: pd.DataFrame, new_rows: pd.DataFrame) -> pd.DataFrame:
    existing = _normalize_history_schema(existing)
    new_rows = _normalize_history_schema(new_rows)

    all_columns = list(existing.columns)
    for column in new_rows.columns:
        if column not in all_columns:
            all_columns.append(column)

    existing_aligned = existing.copy()
    new_aligned = new_rows.copy()
    for column in all_columns:
        if column not in existing_aligned.columns:
            existing_aligned[column] = pd.NA
        if column not in new_aligned.columns:
            new_aligned[column] = pd.NA

    combined = pd.concat([existing_aligned[all_columns], new_aligned[all_columns]], ignore_index=True, sort=False)
    combined = combined.drop_duplicates(subset=BASE_KEY_COLS, keep="last")
    return _order_columns(combined)


def _merge_source_identity_and_bost(source_identity: pd.DataFrame, bost_rows: pd.DataFrame) -> pd.DataFrame:
    if bost_rows.empty:
        return _order_columns(source_identity.copy())

    merged = source_identity.merge(
        bost_rows.drop(columns=["LOT_BOST"], errors="ignore").drop(columns=AUDIT_COLS, errors="ignore"),
        how="left",
        on=BASE_KEY_COLS,
        suffixes=("", "_BOST"),
    )
    return _order_columns(merged)


def _write_csv_atomic(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(temp_path, index=False)
    temp_path.replace(path)


def _write_tranche_snapshot(df: pd.DataFrame, tranche_dir: Path, tranche_rows: int) -> Path:
    tranche_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tranche_path = tranche_dir / f"adhoc_bost_accumulating_tranche_{stamp}_{tranche_rows}.csv"
    df.to_csv(tranche_path, index=False)
    return tranche_path


def _print_plan(source_keys: pd.DataFrame, history: pd.DataFrame, tranche: pd.DataFrame, history_path: Path, tranche_rows: int) -> None:
    print("=" * 80)
    print("BOST ACCUMULATING CSV PLAN")
    print("=" * 80)
    print(f"Source keys: {len(source_keys)}")
    print(f"History rows: {len(history)}")
    print(f"Next tranche size requested: {tranche_rows}")
    print(f"Next tranche selected: {len(tranche)}")
    print(f"Canonical history: {history_path}")
    if not tranche.empty:
        preview = tranche[["LOT", "WAFER_ID", "LAYER", "INSPECT_TIME"]].head(20).copy()
        print("\nTop tranche candidates by INSPECT_TIME:")
        print(preview.to_string(index=False))
    else:
        print("\nNo missing rows remain to query.")


def main() -> None:
    args = _parse_args()
    t0 = time.time()

    if args.tranche_rows < 0:
        raise ValueError("--tranche-rows must be non-negative")

    source = _load_csv(args.input, limit=args.limit)
    _validate_source(source)
    source_keys = _build_source_keys(source)
    history = _load_history(args.history)
    tranche = _select_next_tranche(source_keys, history, args.tranche_rows)

    _print_plan(source_keys, history, tranche, args.history, args.tranche_rows)
    if args.preview:
        return

    if tranche.empty:
        print("[INFO] Nothing new to query; history is already up to date.")
        return

    print(f"[INFO] Connecting to {DSN} ({args.env})")
    conn = PyUber.connect(DSN)
    try:
        new_rows = _query_bost_history(conn, tranche)
    finally:
        conn.close()

    if new_rows.empty:
        print("[INFO] Query returned no rows; writing the selected source keys only.")
        new_rows = _order_columns(tranche.copy())
    else:
        source_identity = _source_identity_frame(tranche)
        new_rows = _merge_source_identity_and_bost(source_identity, new_rows)

    new_rows = _normalize_history_schema(new_rows)

    for column in AUDIT_COLS:
        if column not in new_rows.columns:
            new_rows[column] = pd.NA

    new_rows = new_rows.drop_duplicates(subset=BASE_KEY_COLS, keep="last")

    updated_history = _align_with_history_schema(history, new_rows)

    _write_csv_atomic(updated_history, args.history)
    tranche_snapshot = _write_tranche_snapshot(new_rows, DEFAULT_TRANCHE_DIR, args.tranche_rows)

    print(f"[OK] Appended {len(new_rows)} rows to {args.history}")
    print(f"[OK] Wrote tranche snapshot: {tranche_snapshot}")
    print(f"[OK] Runtime seconds: {round(time.time() - t0, 3)}")


if __name__ == "__main__":
    main()