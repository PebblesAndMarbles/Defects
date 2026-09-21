#!/usr/bin/env python3
"""
Incrementally build an accumulating APEX@ENTITY history CSV.

This script reuses the proven WDS pull and flattening logic from
09_enrich_production_csv.py, but only queries WDS for wafer/layer keys that are
not already present in the durable history CSV.

Default behavior:
- Source rows from outputs/wafer/8M5CL_8M6CL_EXTENDED.csv
- Preserve WAFER_ID and LAYER as the history identity
- Carry LOT and INSPECT_TIME as convenience fields immediately after the identity columns
- Append new rows to the history CSV in place
- Write a per-run delta CSV for staging/review

Upsert mode is available for reruns where an existing key should be refreshed.
"""

import sys
import datetime
import re
from pathlib import Path
from typing import Dict, Optional, Any
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "dev" / "wds-clients" / "clients" / "python"))

try:
    from wds_client import WDSClient
except ImportError as e:
    print(f"ERROR: Could not import wds_client. {e}")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not installed. Install via: pip install pandas")
    sys.exit(1)


FULL_FLOW_ALIASES = [
    "L_8M5_SIARC_DEP", "L_8M5_CHM_DEP", "L_8M5_SED", "E_8M5_HM_ETCH", "W_8M5_HM_CLN",
    "L_8M6_SIARC_DEP", "L_8M6_CHM_DEP", "L_8M6_SED", "E_8M6_HM_ETCH", "W_8M6_HM_CLN",
]

ALIAS_FAMILIES = {
    alias: re.sub(r"_(8M5|8M6)_", "_", alias)
    for alias in FULL_FLOW_ALIASES
}

ALIASES_BY_LAYER = {
    "8M5CL": [a for a in FULL_FLOW_ALIASES if "8M5" in a],
    "8M6CL": [a for a in FULL_FLOW_ALIASES if "8M6" in a],
}

COLUMN_ORDER_FILE = Path(__file__).with_name("COLUMN_ORDER.txt")
COLUMN_ORDER_INDEX: dict[str, int] = {}


def _load_column_order_index() -> dict[str, int]:
    """Load the maintained WDS column ordering file."""
    if not COLUMN_ORDER_FILE.exists():
        raise FileNotFoundError(f"Required column order file not found: {COLUMN_ORDER_FILE}")

    tokens = COLUMN_ORDER_FILE.read_text(encoding="utf-8").split()
    if not tokens:
        raise ValueError(f"Column order file is empty: {COLUMN_ORDER_FILE}")
    return {column_name: position for position, column_name in enumerate(tokens)}


COLUMN_ORDER_INDEX = _load_column_order_index()


def get_wds_client(env: str = "rf3stg", verify_cert: bool = True) -> WDSClient:
    """Initialize the WDS client."""
    wds_dir = Path(__file__).parent.parent
    ca_bundle = wds_dir / "wds_ca_bundle.pem"

    if verify_cert and ca_bundle.exists():
        return WDSClient(environment=env, verify=str(ca_bundle))
    return WDSClient(environment=env, verify=not verify_cert)


def load_csv(csv_path: Path, limit: Optional[int] = None) -> pd.DataFrame:
    """Load a CSV and optionally truncate it."""
    print(f"[LOAD] {csv_path}")

    if not csv_path.exists():
        print(f"[ERROR] File not found: {csv_path}")
        sys.exit(1)

    try:
        df = pd.read_csv(csv_path)
        if limit:
            df = df.head(limit)
            print(f"  [LIMIT] Restricted to first {limit} rows")
        print(f"  [OK] Loaded {len(df)} rows, {len(df.columns)} columns")
        return df
    except Exception as e:
        print(f"[ERROR] Failed to load CSV: {e}")
        sys.exit(1)


def load_history_csv(history_path: Path) -> pd.DataFrame:
    """Load the durable history CSV if it exists."""
    if not history_path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(history_path)
    except ValueError:
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERROR] Failed to load history from {history_path}: {e}")
        sys.exit(1)


def pull_apex_entity_for_alias(
    client: WDSClient,
    wafer_id: str,
    alias: str,
    version: str = "V6"
) -> Optional[Dict]:
    """Pull raw APEX@ENTITY data for a single wafer/alias pair."""
    pattern = f"^APEX@ENTITY@{alias}@{version}@"

    try:
        result = client.query.download_dataframe(
            data_context="WAFER",
            ids=[wafer_id],
            include_patterns=[pattern]
        )

        if result is None or result.empty:
            return None

        return result.iloc[0].to_dict()
    except Exception:
        return None


def extract_entity_and_chambers(
    wds_data: Dict,
    alias: str,
    version: str = "V6"
) -> Dict[str, Any]:
    """Extract the stable WDS fields for one alias."""
    result: Dict[str, Any] = {}

    for field_name in ["ENTITY", "OPERATION", "WAFER_ENTITY_END_TIME"]:
        col_name = f"APEX@ENTITY@{alias}@{version}@{field_name}"
        if col_name in wds_data:
            result[field_name] = wds_data[col_name]

    chamber_fields = {}
    for col_name, col_value in wds_data.items():
        if "CHAMBER@NTSC@" in col_name:
            parts = col_name.split("@")
            if len(parts) >= 9:
                chamber_type = parts[6]
                chamber_fields[f"CHAMBER_{chamber_type}"] = col_value

    result.update(chamber_fields)

    for slot_idx in range(15):
        col_name = f"APEX@ENTITY@{alias}@{version}@SUBENTITY_{slot_idx}"
        if col_name in wds_data and wds_data[col_name]:
            result[f"SUBENTITY_{slot_idx}"] = wds_data[col_name]
            for subfield in ["BATCH_IDLE", "PRIOR_ALIAS", "PROCESS_ORDER", "SEQUENCE", "UTILIZATION"]:
                subfield_col = f"APEX@ENTITY@{alias}@{version}@SUBENTITY_{slot_idx}@{subfield}"
                if subfield_col in wds_data:
                    result[f"SUBENTITY_{slot_idx}_{subfield}"] = wds_data[subfield_col]

    return result


def _normalize_layer_agnostic_alias(alias: str) -> str:
    return re.sub(r"_(8M5|8M6)_", "_", str(alias))


def _split_wds_column_name(column_name: str) -> tuple[str | None, str | None]:
    for alias in sorted(FULL_FLOW_ALIASES, key=len, reverse=True):
        prefix = f"WDS_{alias}_"
        if column_name.startswith(prefix):
            return alias, column_name[len(prefix):]
    return None, None


def _collapse_layer_agnostic_columns(raw_df: pd.DataFrame) -> pd.DataFrame:
    base_cols = ["WAFER_ID", "LAYER"]
    grouped_sources: dict[str, list[str]] = defaultdict(list)
    passthrough_columns: list[str] = []

    for column_name in raw_df.columns:
        if column_name in base_cols:
            continue
        alias, field_suffix = _split_wds_column_name(column_name)
        if alias is None or field_suffix is None:
            passthrough_columns.append(column_name)
            continue
        family_alias = _normalize_layer_agnostic_alias(alias)
        target_column = f"WDS_{family_alias}_{field_suffix}"
        grouped_sources[target_column].append(column_name)

    collapsed_parts = [raw_df[base_cols].copy()]

    if passthrough_columns:
        collapsed_parts.append(raw_df[passthrough_columns].copy())

    collapsed_family_data = {}
    for target_column, source_columns in grouped_sources.items():
        combined = raw_df[source_columns[0]].copy()
        for source_column in source_columns[1:]:
            combined = combined.combine_first(raw_df[source_column])
        collapsed_family_data[target_column] = combined

    if collapsed_family_data:
        collapsed_parts.append(pd.DataFrame(collapsed_family_data, index=raw_df.index))

    collapsed = pd.concat(collapsed_parts, axis=1)
    collapsed = collapsed.loc[:, ~collapsed.columns.duplicated()]
    return collapsed


def _wds_column_sort_key(column_name: str) -> tuple[int, str, str]:
    order_rank = COLUMN_ORDER_INDEX.get(column_name)
    if order_rank is not None:
        return (0, f"{order_rank:06d}", column_name)

    alias, field_suffix = _split_wds_column_name(column_name)
    if alias is None or field_suffix is None:
        return (2, column_name, "")

    family_alias = _normalize_layer_agnostic_alias(alias)
    return (1, family_alias, field_suffix)


def _order_wds_columns(df: pd.DataFrame) -> pd.DataFrame:
    base_cols = [c for c in ["WAFER_ID", "LAYER"] if c in df.columns]
    wds_cols = sorted([c for c in df.columns if c.startswith("WDS_")], key=_wds_column_sort_key)
    identity_cols = [c for c in ["LOT", "INSPECT_TIME"] if c in df.columns]
    other_cols = [c for c in df.columns if c not in base_cols and c not in identity_cols and c not in wds_cols]
    return df[base_cols + identity_cols + wds_cols + other_cols]


def enrich_wafer(
    client: WDSClient,
    wafer_row: pd.Series,
    wds_data_cache: Dict[tuple[str, str], Optional[Dict]],
    stats: Dict[str, int]
) -> Dict[str, Any]:
    """Pull all WDS alias data for one wafer/layer key."""
    wafer_id = wafer_row.get("WAFER_ID")
    layer = wafer_row.get("LAYER")
    lot = wafer_row.get("LOT")
    inspect_time = wafer_row.get("INSPECT_TIME")

    result: Dict[str, Any] = {"WAFER_ID": wafer_id, "LAYER": layer, "LOT": lot, "INSPECT_TIME": inspect_time}

    if not layer:
        return result

    aliases = ALIASES_BY_LAYER.get(layer, [])

    for alias in aliases:
        cache_key = (wafer_id, alias)
        if cache_key in wds_data_cache:
            wds_data = wds_data_cache[cache_key]
        else:
            wds_data = pull_apex_entity_for_alias(client, wafer_id, alias)
            wds_data_cache[cache_key] = wds_data

        if wds_data is None:
            stats["no_data"] += 1
            continue

        stats["data_available"] += 1
        extracted = extract_entity_and_chambers(wds_data, alias)

        for field_name, field_value in extracted.items():
            result[f"WDS_{alias}_{field_name}"] = field_value

    return result


def build_history_dataframe(
    source_df: pd.DataFrame,
    history_df: pd.DataFrame,
    client: WDSClient,
    append_only: bool,
    batch_size: Optional[int],
) -> tuple[pd.DataFrame, pd.DataFrame, Dict[str, int]]:
    """Create a staged delta dataframe and the updated history dataframe."""
    source_rows = source_df.copy()
    source_rows = source_rows.dropna(subset=["WAFER_ID", "LAYER"]).copy()
    source_rows["_INSPECT_TIME_SORT"] = pd.to_datetime(source_rows.get("INSPECT_TIME"), errors="coerce")
    source_rows = source_rows.sort_values(
        by=["_INSPECT_TIME_SORT", "WAFER_ID", "LAYER"],
        ascending=[False, True, True],
        kind="mergesort"
    )

    source_keys = source_rows[["WAFER_ID", "LAYER", "LOT", "INSPECT_TIME", "_INSPECT_TIME_SORT"]].drop_duplicates(
        subset=["WAFER_ID", "LAYER"],
        keep="first"
    )

    if history_df.empty:
        missing_keys = source_keys.copy()
    else:
        source_key_index = source_keys.astype(str).agg("|".join, axis=1)
        history_key_index = history_df[["WAFER_ID", "LAYER"]].dropna().drop_duplicates().astype(str).agg("|".join, axis=1)
        missing_mask = ~source_key_index.isin(set(history_key_index))
        missing_keys = source_keys.loc[missing_mask].copy()

    if batch_size is not None:
        missing_keys = missing_keys.head(batch_size)

    stats = {"data_available": 0, "no_data": 0}
    wds_data_cache: Dict[tuple[str, str], Optional[Dict]] = {}
    delta_rows: list[Dict[str, Any]] = []

    print(f"[PLAN] Source keys: {len(source_keys)}")
    print(f"[PLAN] Existing history keys: {len(history_df)}")
    print(f"[PLAN] Missing keys selected for this run: {len(missing_keys)}")

    for idx, (_, row) in enumerate(missing_keys.iterrows(), 1):
        if (idx - 1) % 10 == 0:
            print(f"  [{idx}/{len(missing_keys)}] Querying missing wafers...")
        delta_rows.append(enrich_wafer(client, row, wds_data_cache, stats))

    delta_df = pd.DataFrame(delta_rows)
    if not delta_df.empty:
        delta_df = _collapse_layer_agnostic_columns(delta_df)
        delta_df = _order_wds_columns(delta_df)

    if history_df.empty:
        updated_history = delta_df.copy()
    elif append_only:
        updated_history = pd.concat([history_df, delta_df], ignore_index=True, sort=False)
    else:
        combined = pd.concat([history_df, delta_df], ignore_index=True, sort=False)
        updated_history = combined.drop_duplicates(subset=["WAFER_ID", "LAYER"], keep="last")

    if not updated_history.empty:
        history_key_cols = [c for c in ["WAFER_ID", "LAYER"] if c in updated_history.columns]
        if history_key_cols:
            source_identity = source_rows[["WAFER_ID", "LAYER", "LOT", "INSPECT_TIME"]].drop_duplicates(subset=["WAFER_ID", "LAYER"], keep="first")
            updated_history = updated_history.drop(columns=["LOT", "INSPECT_TIME"], errors="ignore")
            updated_history = updated_history.merge(source_identity, on=["WAFER_ID", "LAYER"], how="left")

    if not updated_history.empty:
        identity_cols = [c for c in ["WAFER_ID", "LAYER", "LOT", "INSPECT_TIME"] if c in updated_history.columns]
        remaining_cols = [c for c in updated_history.columns if c not in identity_cols]
        updated_history = updated_history[identity_cols + remaining_cols]
        updated_history = updated_history.loc[:, ~updated_history.columns.duplicated()]

    return delta_df, updated_history, stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Build an accumulating APEX@ENTITY CSV from missing wafer/layer keys."
    )
    parser.add_argument("--source", type=Path, default=None, help="Source production CSV")
    parser.add_argument("--history", type=Path, default=None, help="Durable accumulating CSV")
    parser.add_argument("--delta-out", type=Path, default=None, help="Per-run staged delta CSV")
    parser.add_argument("--limit", type=int, default=None, help="Limit source rows for testing")
    parser.add_argument("--tranche-rows", type=int, default=100, help="Limit number of missing rows processed in this run")
    parser.add_argument("--env", choices=["rf3stg", "rf3prod"], default="rf3prod")
    parser.add_argument("--no-cert-verify", action="store_true")
    parser.add_argument("--upsert", action="store_true", help="Refresh existing keys instead of append-only")

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    artifact_dir = script_dir / "artifacts"
    artifact_dir.mkdir(exist_ok=True)

    source_csv = args.source or (Path(__file__).resolve().parents[2] / "outputs" / "wafer" / "8M5CL_8M6CL_EXTENDED.csv")
    history_csv = args.history or (script_dir / "apex_entity_history.csv")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    delta_out = args.delta_out or (artifact_dir / f"apex_entity_delta_{timestamp}.csv")

    print("=" * 80)
    print("APEX@ENTITY Incremental History Builder")
    print(f"Started: {datetime.datetime.now().isoformat()}")
    print("=" * 80)

    source_df = load_csv(source_csv, args.limit)

    if "WAFER_ID" not in source_df.columns or "LAYER" not in source_df.columns:
        print("[ERROR] Source CSV must contain WAFER_ID and LAYER")
        sys.exit(1)

    if "INSPECT_TIME" not in source_df.columns:
        print("[ERROR] Source CSV must contain INSPECT_TIME for tranche prioritization")
        sys.exit(1)

    history_df = load_history_csv(history_csv)

    print("\n[INIT] Initializing WDS client...")
    try:
        client = get_wds_client(env=args.env, verify_cert=not args.no_cert_verify)
    except Exception as e:
        print(f"[ERROR] Failed to initialize WDS client: {e}")
        sys.exit(1)

    print("\n[BUILD] Selecting missing keys and querying WDS...")
    delta_df, updated_history, stats = build_history_dataframe(
        source_df=source_df,
        history_df=history_df,
        client=client,
        append_only=not args.upsert,
        batch_size=args.tranche_rows,
    )

    if delta_df.empty:
        print("[WRITE] No new rows found; history unchanged")
    else:
        print(f"[WRITE] Writing staged delta to {delta_out}")
        delta_df.to_csv(delta_out, index=False)

        print(f"[WRITE] Writing updated history to {history_csv}")
        history_csv.parent.mkdir(parents=True, exist_ok=True)
        updated_history.to_csv(history_csv, index=False)

    total_pairs = stats["data_available"] + stats["no_data"]
    data_availability = (stats["data_available"] / total_pairs * 100) if total_pairs > 0 else 0

    report_file = artifact_dir / f"apex_entity_history_report_{timestamp}.txt"
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("APEX@ENTITY Incremental History Report\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Generated: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Source CSV: {source_csv}\n")
            f.write(f"History CSV: {history_csv}\n")
            f.write(f"Delta CSV: {delta_out}\n")
            f.write(f"Mode: {'upsert' if args.upsert else 'append-only'}\n")
            f.write(f"Source rows: {len(source_df)}\n")
            f.write(f"Existing history keys: {len(history_df)}\n")
            f.write(f"New staged rows: {len(delta_df)}\n")
            f.write(f"WDS data available: {stats['data_available']}\n")
            f.write(f"WDS no data: {stats['no_data']}\n")
            f.write(f"Data availability rate: {data_availability:.1f}%\n")
    except Exception as e:
        print(f"[WARN] Failed to write report: {e}")

    print("\n" + "=" * 80)
    print("COMPLETION SUMMARY")
    print("=" * 80)
    print(f"History CSV: {history_csv}")
    print(f"Delta CSV: {delta_out}")
    print(f"Mode: {'upsert' if args.upsert else 'append-only'}")
    print(f"New rows staged: {len(delta_df)}")
    print(f"Data availability: {data_availability:.1f}%")
    print(f"Report: {report_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())