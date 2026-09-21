#!/usr/bin/env python3
"""
Phase 4, Steps 10-11: Build and run end-to-end APEX@ENTITY enrichment (REVISED).

REVISED STRATEGY (from pilot analysis):
- Do NOT match against production CSV SUBENTITY (not portable across operations)
- Instead, extract ALL available entity/chamber metadata from WDS for each operation
- Each operation has different chamber naming (etch=PM slots, clean=Process, coater=Process+Track, stepper=16 fields)
- Include whatever is available without requiring field-level matching

This script:
1. Loads production CSV.
2. For each wafer/layer, pulls APEX@ENTITY from WDS (one alias per call).
3. Extracts all available ENTITY and CHAMBER-related columns (no matching required).
4. Flattens to output columns (one per ENTITY/CHAMBER field per operation).
5. Merges back into production CSV (per Step 9 merge strategy).
6. Produces enriched CSV + summary report.

Usage:
    python 09_enrich_production_csv.py [--input PROD_CSV] [--output OUT_CSV] 
                                       [--limit N] [--env {rf3stg,rf3prod}]

Options:
    --input PROD_CSV      Path to production CSV (default: outputs/wafer/8M5CL_8M6CL_EXTENDED.csv)
    --output OUT_CSV      Path to output enriched CSV (auto-generated if not specified)
    --limit N             Limit to first N wafers (for testing)
    --env ENV             WDS environment (default: rf3prod)
    --no-cert-verify      Disable SSL cert verification (not recommended)

Revised approach: Success = data available (no match threshold).
"""

import sys
import csv
import datetime
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
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


# FULL_FLOW_ALIASES
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
    """Load the user-maintained WDS column order file into a lookup table."""
    if not COLUMN_ORDER_FILE.exists():
        raise FileNotFoundError(f"Required column order file not found: {COLUMN_ORDER_FILE}")

    tokens = COLUMN_ORDER_FILE.read_text(encoding="utf-8").split()
    if not tokens:
        raise ValueError(f"Column order file is empty: {COLUMN_ORDER_FILE}")
    return {column_name: position for position, column_name in enumerate(tokens)}


COLUMN_ORDER_INDEX = _load_column_order_index()


def get_wds_client(env: str = "rf3stg", verify_cert: bool = True) -> WDSClient:
    """Initialize WDS client."""
    wds_dir = Path(__file__).parent.parent
    ca_bundle = wds_dir / "wds_ca_bundle.pem"
    
    if verify_cert and ca_bundle.exists():
        return WDSClient(environment=env, verify=str(ca_bundle))
    else:
        return WDSClient(environment=env, verify=not verify_cert)


def load_production_csv(csv_path: Path, limit: Optional[int] = None) -> pd.DataFrame:
    """Load production CSV, optionally limit to first N rows."""
    print(f"[LOAD] Loading production CSV: {csv_path}")
    
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


def apply_inspect_time_lookback(df: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
    """Keep only rows within the requested lookback window based on INSPECT_TIME."""
    if "INSPECT_TIME" not in df.columns:
        print("[ERROR] lookback requested but INSPECT_TIME column is missing")
        sys.exit(1)

    inspect_times = pd.to_datetime(df["INSPECT_TIME"], errors="coerce")
    valid_times = inspect_times.dropna()
    if valid_times.empty:
        print("[ERROR] lookback requested but no valid INSPECT_TIME values were found")
        sys.exit(1)

    max_inspect_time = valid_times.max()
    cutoff = max_inspect_time - pd.Timedelta(days=lookback_days)
    filtered = df.loc[inspect_times >= cutoff].copy()

    print(f"  [LOOKBACK] INSPECT_TIME max: {max_inspect_time}")
    print(f"  [LOOKBACK] Cutoff ({lookback_days} days): {cutoff}")
    print(f"  [LOOKBACK] Rows kept: {len(filtered)} of {len(df)}")
    return filtered


def pull_apex_entity_for_alias(
    client: WDSClient,
    wafer_id: str,
    alias: str,
    version: str = "V6"
) -> Optional[Dict]:
    """
    Pull APEX@ENTITY data for a single (wafer, alias) pair.
    
    Extracts ENTITY (top-level) and CHAMBER/entity metadata (no matching).
    
    Returns:
        Dict with raw WDS data (wide format), or None if failed/no data.
    """
    pattern = f"^APEX@ENTITY@{alias}@{version}@"
    
    try:
        result = client.query.download_dataframe(
            data_context="WAFER",
            ids=[wafer_id],
            include_patterns=[pattern]
        )
        
        if result is None or result.empty:
            return None
        
        # Flatten to single row dict
        row_data = result.iloc[0].to_dict()
        return row_data
    
    except Exception:
        return None


def extract_entity_and_chambers(
    wds_data: Dict,
    alias: str,
    version: str = "V6"
) -> Dict[str, Any]:
    """
    Extract all ENTITY-level and CHAMBER/entity fields from WDS data.
    
    Looks for patterns:
    - ENTITY (top-level entity identifier)
    - CHAMBER@NTSC@* (operation-specific chamber fields)
    - SUBENTITY_N for legacy purposes
    
    Returns dict with flattened field values.
    """
    result = {}
    
    # Extract top-level ENTITY fields
    for field_name in ["ENTITY", "OPERATION", "WAFER_ENTITY_END_TIME"]:
        col_name = f"APEX@ENTITY@{alias}@{version}@{field_name}"
        if col_name in wds_data:
            result[field_name] = wds_data[col_name]
    
    # Extract all CHAMBER/entity fields (operation-specific structure)
    # Pattern: CHAMBER@NTSC@{chamber_type}@{operation}
    chamber_fields = {}
    for col_name, col_value in wds_data.items():
        if "CHAMBER@NTSC@" in col_name:
            # Parse: APEX@ENTITY@{alias}@V6@CHAMBER@NTSC@{chamber_type}@{operation}
            parts = col_name.split("@")
            if len(parts) >= 9:
                chamber_type = parts[6]  # e.g., "Process-1", "Adhesion-1"
                # Store with simplified name
                chamber_key = f"CHAMBER_{chamber_type}"
                chamber_fields[chamber_key] = col_value
    
    result.update(chamber_fields)
    
    # Also extract SUBENTITY slots (if present) - some operations use these
    for slot_idx in range(15):
        col_name = f"APEX@ENTITY@{alias}@{version}@SUBENTITY_{slot_idx}"
        if col_name in wds_data and wds_data[col_name]:
            result[f"SUBENTITY_{slot_idx}"] = wds_data[col_name]
            
            # Extract subfields for this slot
            for subfield in ["BATCH_IDLE", "PRIOR_ALIAS", "PROCESS_ORDER", "SEQUENCE", "UTILIZATION"]:
                subfield_col = f"APEX@ENTITY@{alias}@{version}@SUBENTITY_{slot_idx}@{subfield}"
                if subfield_col in wds_data:
                    result[f"SUBENTITY_{slot_idx}_{subfield}"] = wds_data[subfield_col]
    
    return result


def _normalize_layer_agnostic_alias(alias: str) -> str:
    """Strip the layer token from an alias while keeping the operation family intact."""
    return re.sub(r"_(8M5|8M6)_", "_", str(alias))


def _split_wds_column_name(column_name: str) -> tuple[str | None, str | None]:
    """
    Split a raw WDS column name into (alias, field_suffix).

    The helper matches the known alias list first so aliases that contain multiple
    underscores are parsed deterministically.
    """
    for alias in sorted(FULL_FLOW_ALIASES, key=len, reverse=True):
        prefix = f"WDS_{alias}_"
        if column_name.startswith(prefix):
            return alias, column_name[len(prefix):]
    return None, None


def _collapse_layer_agnostic_columns(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse layer-qualified APEX columns into layer-agnostic families.

    Raw columns remain available in the debug artifact. The returned dataframe keeps
    only one column per semantic family, coalescing M5/M6 variants where both exist.
    """
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
    """Sort WDS columns by the explicit order file, then alphabetically for leftovers."""
    order_rank = COLUMN_ORDER_INDEX.get(column_name)
    if order_rank is not None:
        return (0, f"{order_rank:06d}", column_name)

    alias, field_suffix = _split_wds_column_name(column_name)
    if alias is None or field_suffix is None:
        return (2, column_name, "")

    family_alias = _normalize_layer_agnostic_alias(alias)
    return (1, family_alias, field_suffix)


def _order_wds_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Place WAFER_ID/LAYER first, then WDS columns in flow order, then everything else."""
    base_cols = [c for c in ["WAFER_ID", "LAYER"] if c in df.columns]
    wds_cols = sorted([c for c in df.columns if c.startswith("WDS_")], key=_wds_column_sort_key)
    other_cols = [c for c in df.columns if c not in base_cols and c not in wds_cols]
    return df[base_cols + wds_cols + other_cols]


def enrich_wafer(
    client: WDSClient,
    wafer_row: pd.Series,
    wds_data_cache: Dict[Tuple[str, str], Optional[Dict]],
    stats: Dict
) -> Dict:
    """
    Enrich a single wafer row with APEX@ENTITY data.
    
    For each alias, extracts all available ENTITY and CHAMBER fields.
    No matching required - just includes whatever WDS has.
    
    Returns:
        Dict with all WDS columns for this wafer.
    """
    wafer_id = wafer_row.get("WAFER_ID")
    layer = wafer_row.get("LAYER")
    
    result = {"WAFER_ID": wafer_id, "LAYER": layer}
    
    if not layer:
        return result
    
    aliases = ALIASES_BY_LAYER.get(layer, [])
    
    for alias in aliases:
        # Check cache first
        cache_key = (wafer_id, alias)
        if cache_key in wds_data_cache:
            wds_data = wds_data_cache[cache_key]
        else:
            # Pull from WDS
            wds_data = pull_apex_entity_for_alias(client, wafer_id, alias)
            wds_data_cache[cache_key] = wds_data
        
        if wds_data is None:
            stats["no_data"] += 1
            continue
        
        stats["data_available"] += 1
        
        # Extract all entity and chamber fields
        extracted = extract_entity_and_chambers(wds_data, alias)
        
        # Add to result with alias prefix
        for field_name, field_value in extracted.items():
            col_name = f"WDS_{alias}_{field_name}"
            result[col_name] = field_value
    
    return result


def main():
    """
    Main entry point: load production CSV, enrich with APEX@ENTITY, produce output.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Build and run end-to-end APEX@ENTITY enrichment (revised strategy)."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to production CSV (auto-detected if not specified)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to output enriched CSV (auto-generated if not specified)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit to first N wafers (for testing)"
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Restrict the input CSV to rows within N days of the max INSPECT_TIME"
    )
    parser.add_argument(
        "--env",
        choices=["rf3stg", "rf3prod"],
        default="rf3prod"
    )
    parser.add_argument(
        "--no-cert-verify",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    artifact_dir = script_dir / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    
    print("=" * 80)
    print(f"Phase 4, Steps 10-11: Build and Run End-to-End Enrichment (REVISED)")
    print(f"Started: {datetime.datetime.now().isoformat()}")
    print("=" * 80)
    
    # Resolve input CSV
    input_csv = args.input
    if not input_csv:
        input_csv = (Path(__file__).resolve().parents[2] / 
                    "outputs" / "wafer" / "8M5CL_8M6CL_EXTENDED.csv")
    
    # Load production CSV
    prod_df = load_production_csv(input_csv, args.limit)

    if args.lookback_days is not None:
        prod_df = apply_inspect_time_lookback(prod_df, args.lookback_days)
    
    # Resolve output CSV
    output_csv = args.output
    if not output_csv:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_csv = artifact_dir / f"enriched_revised_{timestamp}.csv"
    
    # Initialize WDS client
    print("\n[INIT] Initializing WDS client...")
    try:
        client = get_wds_client(env=args.env, verify_cert=not args.no_cert_verify)
    except Exception as e:
        print(f"[ERROR] Failed to initialize WDS client: {e}")
        sys.exit(1)
    
    # Enrich each wafer
    print(f"\n[ENRICH] Processing {len(prod_df)} wafers...")
    
    stats = {"data_available": 0, "no_data": 0}
    wds_data_cache = {}
    enrichment_rows = []
    
    unique_wafers = prod_df.drop_duplicates(subset=["WAFER_ID", "LAYER"])
    
    for idx, (_, row) in enumerate(unique_wafers.iterrows(), 1):
        if (idx - 1) % 10 == 0:
            print(f"  [{idx}/{len(unique_wafers)}] Processing wafers...")
        
        enrich = enrich_wafer(client, row, wds_data_cache, stats)
        enrichment_rows.append(enrich)
    
    # Create enrichment dataframe
    print("\n[BUILD] Building enrichment dataframe...")
    enrich_df = pd.DataFrame(enrichment_rows)

    raw_output_csv = None
    if args.limit:
        raw_output_csv = artifact_dir / f"enriched_revised_raw_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        enrich_df.to_csv(raw_output_csv, index=False)
        print(f"[WRITE] Raw split artifact written to {raw_output_csv}")

    collapsed_enrich_df = _collapse_layer_agnostic_columns(enrich_df)
    collapsed_enrich_df = _order_wds_columns(collapsed_enrich_df)
    
    # Merge with production CSV on (WAFER_ID, LAYER)
    print("[MERGE] Merging enrichment with production CSV...")
    
    # For merge, we need to match on WAFER_ID and LAYER (LOT7 may vary)
    # Group production CSV by unique wafer-layer, merge once
    enriched = pd.merge(
        prod_df,
        collapsed_enrich_df,
        on=["WAFER_ID", "LAYER"],
        how="left"
    )
    
    # Write output
    print(f"[WRITE] Writing enriched CSV to {output_csv}...")
    try:
        enriched.to_csv(output_csv, index=False)
        print(f"  [OK] {len(enriched)} rows, {len(enriched.columns)} columns")
    except Exception as e:
        print(f"[ERROR] Failed to write output: {e}")
        sys.exit(1)
    
    # Compute data availability rate
    total_pairs = stats["data_available"] + stats["no_data"]
    data_availability = (stats["data_available"] / total_pairs * 100) if total_pairs > 0 else 0
    
    # Write summary report
    print("\n[REPORT] Writing summary report...")
    report_file = artifact_dir / f"enrichment_report_revised_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    try:
        with open(report_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("APEX@ENTITY Enrichment Report (REVISED STRATEGY)\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Generated: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Input CSV: {input_csv}\n")
            f.write(f"Output CSV: {output_csv}\n")
            f.write(f"WDS Environment: {args.env}\n\n")
            
            f.write("STRATEGY NOTE:\n")
            f.write("-" * 80 + "\n")
            f.write("Revised approach: Extract all ENTITY and CHAMBER metadata from WDS without\n")
            f.write("requiring field-level matching (incompatible across operations).\n")
            f.write("Success metric: % of (wafer, alias) pairs with WDS data available.\n\n")
            
            f.write("SUMMARY:\n")
            f.write("-" * 80 + "\n")
            f.write(f"Production CSV rows:                 {len(prod_df)}\n")
            f.write(f"Unique wafers:                       {len(enrichment_rows)}\n")
            f.write(f"Enriched CSV rows:                   {len(enriched)}\n")
            f.write(f"Enriched CSV columns:                {len(enriched.columns)}\n")
            f.write(f"Collapsed APEX columns:              {len([c for c in collapsed_enrich_df.columns if c.startswith('WDS_')])}\n")
            f.write(f"\nWDS Data Availability:\n")
            f.write(f"  Total (wafer, alias) pairs:        {total_pairs}\n")
            f.write(f"  Data available (extracted):        {stats['data_available']}\n")
            f.write(f"  No data (WDS errors/empty):        {stats['no_data']}\n")
            f.write(f"  Data availability rate:            {data_availability:.1f}%\n")
            f.write(f"\n  Aliases per wafer: {len(FULL_FLOW_ALIASES) // 2} per layer (5 per wafer/8M5 or 8M6)\n")
            if raw_output_csv is not None:
                f.write(f"\nRaw split artifact:                 {raw_output_csv}\n")
        
        print(f"  [OK] Report written: {report_file.name}")
    except Exception as e:
        print(f"[WARN] Failed to write report: {e}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("COMPLETION SUMMARY:")
    print("=" * 80)
    print(f"Output CSV: {output_csv}")
    print(f"Report: {report_file}")
    print(f"Data availability: {data_availability:.1f}%")
    print(f"\n[OK] Enrichment complete. Proceed to Phase 4, Step 12 (validate output).")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
