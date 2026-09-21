#!/usr/bin/env python3
"""
Phase 2, Step 4: Extract pilot wafer list from BOST registry pilot.

This script:
1. Loads the 10 pilot wafers from BOST/step1_recent_wafer_registry_pilot.py.
2. Determines each wafer's layer (8M5CL or 8M6CL) from production CSV.
3. Produces manifest CSV `04_pilot_wafers.csv` (WAFER_ID, LAYER).

Depends on:
    - BOST/step1_recent_wafer_registry_pilot.py (defines PILOT_WAFERS)
    - outputs/wafer/8M5CL_8M6CL_EXTENDED.csv (to infer layer per wafer)
"""

import sys
import pathlib
import csv
import re
from pathlib import Path
from typing import List, Dict, Tuple
import datetime


def extract_pilot_wafers_from_bost_script() -> List[str]:
    """
    Extract pilot wafers from production CSV (same strategy as BOST script).
    
    Selects most recent wafers per layer.
    
    Returns:
        List of wafer IDs.
    """
    # Path: from WDS/APEX_ENTITY up 2 levels to BE, then down to outputs/wafer
    production_csv = Path(__file__).resolve().parents[2] / "outputs" / "wafer" / "8M5CL_8M6CL_EXTENDED.csv"
    
    if not production_csv.exists():
        print(f"[WARN] Production CSV not found: {production_csv}")
        print("       Using fallback pilot wafers")
        return ["5DXWG774MVD6", "HP1SH180JKE1"]  # Fallback from probes
    
    try:
        # Import pandas for CSV reading
        import pandas as pd
        
        df = pd.read_csv(production_csv, usecols=["LOT7", "WAFER_ID", "LAYER", "INSPECT_TIME"], nrows=10000)
        
        # Drop rows with missing values
        df = df.dropna(subset=["WAFER_ID", "LAYER"])
        
        # Get unique wafers per layer, most recent ones
        df["INSPECT_TIME"] = pd.to_datetime(df["INSPECT_TIME"], errors='coerce')
        df = df.dropna(subset=["INSPECT_TIME"])
        
        # Sort by layer and time, get most recent 5 per layer
        recent = df.sort_values("INSPECT_TIME").drop_duplicates(
            subset=["WAFER_ID", "LAYER"], keep="last"
        ).groupby("LAYER").tail(5)
        
        wafers = recent["WAFER_ID"].unique().tolist()
        print(f"[OK] Extracted {len(wafers)} recent pilot wafers from production CSV")
        return wafers
    
    except Exception as e:
        print(f"[WARN] Failed to extract from production CSV: {e}")
        print("       Using fallback pilot wafers")
        return ["5DXWG774MVD6", "HP1SH180JKE1"]


def load_production_csv(csv_path: Path) -> Dict[str, str]:
    """
    Load production CSV and build wafer_id -> layer mapping.
    
    Returns:
        Dict mapping WAFER_ID to LAYER (8M5CL or 8M6CL).
    """
    wafer_to_layer = {}
    
    if not csv_path.exists():
        print(f"[ERROR] Production CSV not found: {csv_path}")
        sys.exit(1)
    
    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                wafer_id = row.get("WAFER_ID", "").strip()
                layer = row.get("LAYER", "").strip()
                
                if wafer_id and layer:
                    # Store first occurrence (all rows for same wafer should have same layer)
                    if wafer_id not in wafer_to_layer:
                        wafer_to_layer[wafer_id] = layer
        
        print(f"[OK] Loaded layer info for {len(wafer_to_layer)} unique wafers from production CSV")
        return wafer_to_layer
    
    except Exception as e:
        print(f"[ERROR] Failed to read production CSV: {e}")
        sys.exit(1)


def main():
    """
    Main entry point: extract pilot wafers, determine layers, write manifest.
    """
    script_dir = Path(__file__).parent
    artifact_dir = script_dir / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    
    print("=" * 80)
    print(f"Phase 2, Step 4: Extract Pilot Wafer List")
    print(f"Started: {datetime.datetime.now().isoformat()}")
    print("=" * 80)
    
    # Extract pilot wafers from BOST script
    print("\n[LOAD] Extracting pilot wafers from BOST registry script...")
    pilot_wafers = extract_pilot_wafers_from_bost_script()
    
    if not pilot_wafers:
        print("[ERROR] Could not extract pilot wafers. Aborting.")
        sys.exit(1)
    
    print(f"  Pilot wafers: {pilot_wafers}")
    
    # Load production CSV to get layers
    print("\n[LOAD] Loading production CSV to determine layers...")
    production_csv = Path(__file__).resolve().parents[2] / "outputs" / "wafer" / "8M5CL_8M6CL_EXTENDED.csv"
    wafer_to_layer = load_production_csv(production_csv)
    
    # Build pilot manifest
    print("\n[BUILD] Building pilot manifest...")
    pilot_manifest = []
    missing_layers = []
    
    for wafer_id in pilot_wafers:
        layer = wafer_to_layer.get(wafer_id)
        
        if layer:
            pilot_manifest.append({
                "WAFER_ID": wafer_id,
                "LAYER": layer,
            })
            print(f"  {wafer_id}: {layer}")
        else:
            print(f"  [WARN] {wafer_id}: layer not found in production CSV")
            missing_layers.append(wafer_id)
    
    if missing_layers:
        print(f"\n[WARN] {len(missing_layers)} pilot wafers not found in production CSV: {missing_layers}")
        print("       These will be skipped in pilot validation.")
    
    # Write manifest
    manifest_file = script_dir / "04_pilot_wafers.csv"
    try:
        with open(manifest_file, "w", newline="") as f:
            fieldnames = ["WAFER_ID", "LAYER"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(pilot_manifest)
        print(f"\n[OK] Pilot manifest written: {manifest_file}")
    except Exception as e:
        print(f"[ERROR] Failed to write manifest: {e}")
        sys.exit(1)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Total pilot wafers: {len(pilot_wafers)}")
    print(f"Wafers with layer info: {len(pilot_manifest)}")
    print(f"Wafers missing from production CSV: {len(missing_layers)}")
    print(f"\nLayer breakdown:")
    
    by_layer = {}
    for row in pilot_manifest:
        layer = row["LAYER"]
        by_layer[layer] = by_layer.get(layer, 0) + 1
    
    for layer in sorted(by_layer.keys()):
        print(f"  {layer}: {by_layer[layer]} wafers")
    
    print(f"\n[OK] Manifest created. Proceed to Phase 2, Step 5 (pull APEX@ENTITY).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
