#!/usr/bin/env python3
"""
Phase 1, Step 2: Probe APEX@ENTITY columns for all 10 FULL_FLOW_ALIASES.

This script:
1. Identifies the 10 FULL_FLOW_ALIASES (5 M5 + 5 M6).
2. For each alias, queries WDS to discover available columns.
3. Saves raw column lists to `02a_raw_columns_<ALIAS>.txt`.
4. Summarizes schema to `02b_apex_entity_column_schema.csv`.

Key constraint: ONE ALIAS PER CALL (critical for perf, see wds_client_setup.md).

Usage:
    python 02_probe_all_aliases.py [--env {rf3stg,rf3prod}] [--pilot-wafers PATH]

Depends on:
    - WDS client installed
    - CA bundle at WDS/wds_ca_bundle.pem
    - Phase 1, Step 1 completed (version verified)
"""

import sys
import pathlib
import datetime
import csv
from pathlib import Path
from typing import List, Tuple, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "dev" / "wds-clients" / "clients" / "python"))

try:
    from wds_client import WDSClient
except ImportError as e:
    print(f"ERROR: Could not import wds_client. {e}")
    sys.exit(1)


# 10 FULL_FLOW_ALIASES per BOST/adhoc_bost_gate_rollout.py
FULL_FLOW_ALIASES = [
    # M5 layer (5 aliases)
    "L_8M5_SIARC_DEP",
    "L_8M5_CHM_DEP",
    "L_8M5_SED",
    "E_8M5_HM_ETCH",
    "W_8M5_HM_CLN",
    # M6 layer (5 aliases)
    "L_8M6_SIARC_DEP",
    "L_8M6_CHM_DEP",
    "L_8M6_SED",
    "E_8M6_HM_ETCH",
    "W_8M6_HM_CLN",
]


def get_wds_client(env: str = "rf3stg", verify_cert: bool = True) -> WDSClient:
    """Initialize WDS client with SSL cert verification."""
    wds_dir = Path(__file__).parent.parent
    ca_bundle = wds_dir / "wds_ca_bundle.pem"
    
    if verify_cert and ca_bundle.exists():
        print(f"[INFO] Using CA bundle: {ca_bundle}")
        return WDSClient(environment=env, verify=str(ca_bundle))
    else:
        if verify_cert and not ca_bundle.exists():
            print(f"[WARN] CA bundle not found. Proceeding without cert verification.")
        return WDSClient(environment=env, verify=not verify_cert)


def load_pilot_wafers(pilot_csv_path: Path) -> Dict[str, List[str]]:
    """
    Load pilot wafer list from CSV (WAFER_ID, LAYER columns).
    
    Returns:
        Dict mapping layer (8M5CL / 8M6CL) to list of wafer IDs.
    """
    wafers_by_layer = {"8M5CL": [], "8M6CL": []}
    
    if not pilot_csv_path.exists():
        print(f"[WARN] Pilot CSV not found at {pilot_csv_path}. Using fallback wafers.")
        # Fallback: use placeholder wafers for probing
        return {
            "8M5CL": ["5DXWG774MVD6"],  # From wds_client_setup.md probe
            "8M6CL": ["HP1SH180JKE1"],   # From wds_client_setup.md probe
        }
    
    try:
        with open(pilot_csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                wafer_id = row.get("WAFER_ID", "").strip()
                layer = row.get("LAYER", "").strip()
                if wafer_id and layer in wafers_by_layer:
                    wafers_by_layer[layer].append(wafer_id)
        print(f"[OK] Loaded pilot wafers from {pilot_csv_path}: {wafers_by_layer}")
        return wafers_by_layer
    except Exception as e:
        print(f"[ERROR] Failed to load pilot CSV: {e}")
        sys.exit(1)


def probe_alias_columns(
    client: WDSClient, 
    alias: str, 
    wafer_id: str, 
    version: str = "V6"
) -> List[str]:
    """
    Query WDS for APEX@ENTITY columns for a single alias.
    
    ONE ALIAS PER CALL (critical constraint from perf testing).
    
    Args:
        client: WDSClient instance
        alias: Alias name (e.g., E_8M5_HM_ETCH)
        wafer_id: Real wafer ID for the probe (must be in WDS)
        version: APEX@ENTITY version (e.g., V6)
        
    Returns:
        List of column names matching the pattern.
    """
    pattern = f"^APEX@ENTITY@{alias}@{version}@"
    
    print(f"  [PROBE] Alias: {alias}, Wafer: {wafer_id}, Pattern: {pattern}")
    
    try:
        columns = client.row.columns(
            data_context="WAFER",
            row_id=wafer_id,
            include_patterns=[pattern],
            page_size=100000  # Note: may truncate silently if >= page_size
        )
        print(f"    [OK] Found {len(columns)} columns")
        return columns
    except Exception as e:
        print(f"    [ERROR] Failed to probe: {e}")
        return []


def parse_column_metadata(column_name: str) -> Dict[str, str]:
    """
    Parse a column name to extract segment structure.
    
    Example: APEX@ENTITY@E_8M5_HM_ETCH@V6@SUBENTITY_0@BATCH_IDLE
    Segments: ['APEX', 'ENTITY', 'E_8M5_HM_ETCH', 'V6', 'SUBENTITY_0', 'BATCH_IDLE']
    
    Returns:
        Dict with keys: project, dataset, alias, version, field_path.
    """
    parts = column_name.split("@")
    
    if len(parts) < 5:
        return {"raw": column_name, "invalid": True}
    
    field_path = "@".join(parts[4:])  # Everything after version
    
    return {
        "project": parts[0],
        "dataset": parts[1],
        "alias": parts[2],
        "version": parts[3],
        "field_path": field_path,
        "is_top_level": "@" not in field_path,  # No @ in field => top-level
        "is_subentity": "SUBENTITY_" in field_path,
    }


def categorize_columns(columns: List[str]) -> Dict[str, list]:
    """
    Categorize columns by type (top-level vs. subentity slots + subfields).
    
    Returns:
        Dict with keys: top_level, subentity_fields, all_fields.
    """
    categories = {
        "top_level": [],
        "subentity_fields": [],
        "unparseable": [],
    }
    
    for col in columns:
        meta = parse_column_metadata(col)
        if meta.get("invalid"):
            categories["unparseable"].append(col)
        elif meta.get("is_top_level"):
            categories["top_level"].append(col)
        elif meta.get("is_subentity"):
            categories["subentity_fields"].append(col)
        else:
            categories["unparseable"].append(col)
    
    return categories


def main():
    """
    Main entry point: probe all 10 aliases, save raw + summary.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Probe APEX@ENTITY columns for all FULL_FLOW_ALIASES."
    )
    parser.add_argument("--env", choices=["rf3stg", "rf3prod"], default="rf3stg")
    parser.add_argument(
        "--pilot-wafers",
        type=Path,
        default=None,
        help="Path to pilot wafers CSV (default: auto-detect from BOST registry pilot)"
    )
    parser.add_argument("--no-cert-verify", action="store_true")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print(f"Phase 1, Step 2: Probe APEX@ENTITY Columns")
    print(f"Started: {datetime.datetime.now().isoformat()}")
    print("=" * 80)
    
    # Load pilot wafers
    pilot_wafers_path = args.pilot_wafers or (Path(__file__).parent / "04_pilot_wafers.csv")
    wafers_by_layer = load_pilot_wafers(pilot_wafers_path)
    
    # Initialize WDS client
    try:
        client = get_wds_client(env=args.env, verify_cert=not args.no_cert_verify)
        print(f"[OK] WDS client initialized\n")
    except Exception as e:
        print(f"[ERROR] Failed to initialize WDS client: {e}")
        sys.exit(1)
    
    # Probe each alias
    artifact_dir = Path(__file__).parent / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    
    all_results = []  # For summary CSV
    
    for alias in FULL_FLOW_ALIASES:
        print(f"[PROBE] {alias}")
        
        # Pick wafer based on layer
        layer = "8M5CL" if alias.startswith("L_8M5") or alias.startswith("E_8M5") or alias.startswith("W_8M5") else "8M6CL"
        wafers = wafers_by_layer.get(layer, [])
        
        if not wafers:
            print(f"  [WARN] No wafers for layer {layer}. Skipping.")
            continue
        
        wafer_id = wafers[0]  # Use first wafer
        
        # Probe
        columns = probe_alias_columns(client, alias, wafer_id)
        
        if not columns:
            print(f"  [WARN] No columns found for {alias}")
            continue
        
        # Save raw column list
        raw_file = artifact_dir / f"02a_raw_columns_{alias}.txt"
        try:
            raw_file.write_text("\n".join(columns))
            print(f"  [OK] Saved raw columns to {raw_file.name}")
        except Exception as e:
            print(f"  [ERROR] Failed to save raw columns: {e}")
        
        # Categorize
        categories = categorize_columns(columns)
        
        # Summarize to results
        all_results.append({
            "alias": alias,
            "layer": layer,
            "wafer_probed": wafer_id,
            "total_columns": len(columns),
            "top_level_fields": len(categories["top_level"]),
            "subentity_columns": len(categories["subentity_fields"]),
            "unparseable": len(categories["unparseable"]),
            "top_level_list": "; ".join(categories["top_level"]),
        })
        
        print()
    
    # Write summary CSV
    summary_file = artifact_dir / "02b_apex_entity_column_schema.csv"
    try:
        with open(summary_file, "w", newline="") as f:
            fieldnames = [
                "alias",
                "layer",
                "wafer_probed",
                "total_columns",
                "top_level_fields",
                "subentity_columns",
                "unparseable",
                "top_level_list",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)
        print(f"[OK] Summary CSV written: {summary_file}")
    except Exception as e:
        print(f"[ERROR] Failed to write summary CSV: {e}")
        sys.exit(1)
    
    # Final summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    for result in all_results:
        print(f"{result['alias']:20s}: {result['total_columns']:4d} cols "
              f"({result['top_level_fields']} top-level, {result['subentity_columns']} subentity)")
    
    print(f"\n[OK] Probing complete. Proceed to Phase 1, Step 3 (parse & categorize).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
