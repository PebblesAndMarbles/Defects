#!/usr/bin/env python3
"""
Phase 2, Steps 5-6: Pull APEX@ENTITY for pilot wafers and match SUBENTITY_N.

This script:
1. Loads pilot wafer manifest from 04_pilot_wafers.csv.
2. For each wafer + applicable alias, pulls APEX@ENTITY from WDS (one alias per call).
3. Matches SUBENTITY_N to production CSV's SUBENTITY column.
4. Extracts matched slot's 5 subfields as enrichment payload.
5. Produces:
   - 05a_pilot_raw_apex_entity_<TIMESTAMP>.csv (wide, all columns)
   - 05b_pilot_matched_wafers.csv (flattened, with match status)

Depends on:
    - Phase 1 completed (APEX@ENTITY schema known)
    - Phase 2, Step 4 completed (04_pilot_wafers.csv)
    - outputs/wafer/8M5CL_8M6CL_EXTENDED.csv (for matching)
"""

import sys
import pathlib
import csv
import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "dev" / "wds-clients" / "clients" / "python"))

try:
    from wds_client import WDSClient
except ImportError as e:
    print(f"ERROR: Could not import wds_client. {e}")
    sys.exit(1)


# FULL_FLOW_ALIASES
FULL_FLOW_ALIASES = [
    "L_8M5_SIARC_DEP", "L_8M5_CHM_DEP", "L_8M5_SED", "E_8M5_HM_ETCH", "W_8M5_HM_CLN",
    "L_8M6_SIARC_DEP", "L_8M6_CHM_DEP", "L_8M6_SED", "E_8M6_HM_ETCH", "W_8M6_HM_CLN",
]

ALIASES_BY_LAYER = {
    "8M5CL": [a for a in FULL_FLOW_ALIASES if "8M5" in a],
    "8M6CL": [a for a in FULL_FLOW_ALIASES if "8M6" in a],
}


def get_wds_client(env: str = "rf3stg", verify_cert: bool = True) -> WDSClient:
    """Initialize WDS client."""
    wds_dir = Path(__file__).parent.parent
    ca_bundle = wds_dir / "wds_ca_bundle.pem"
    
    if verify_cert and ca_bundle.exists():
        return WDSClient(environment=env, verify=str(ca_bundle))
    else:
        return WDSClient(environment=env, verify=not verify_cert)


def load_pilot_wafers(manifest_path: Path) -> List[Tuple[str, str]]:
    """Load (WAFER_ID, LAYER) tuples from pilot manifest."""
    wafers = []
    
    if not manifest_path.exists():
        print(f"[ERROR] Pilot manifest not found: {manifest_path}")
        sys.exit(1)
    
    try:
        with open(manifest_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                wafer_id = row.get("WAFER_ID", "").strip()
                layer = row.get("LAYER", "").strip()
                if wafer_id and layer:
                    wafers.append((wafer_id, layer))
        print(f"[OK] Loaded {len(wafers)} pilot wafers")
        return wafers
    except Exception as e:
        print(f"[ERROR] Failed to load manifest: {e}")
        sys.exit(1)


def load_production_csv_subentity(csv_path: Path) -> Dict[str, str]:
    """
    Load production CSV and build (WAFER_ID, LOT7) -> SUBENTITY mapping.
    
    Note: Each wafer appears once per operation/alias, so we may have multiple rows
    per wafer (at different operations). For this step, we just care about SUBENTITY
    being consistent per wafer (it should be, since it's the chamber that processed it).
    """
    wafer_subentity = {}
    
    if not csv_path.exists():
        print(f"[ERROR] Production CSV not found: {csv_path}")
        sys.exit(1)
    
    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                wafer_id = row.get("WAFER_ID", "").strip()
                lot7 = row.get("LOT7", "").strip()
                subentity = row.get("SUBENTITY", "").strip()
                
                # Store first occurrence per wafer
                if wafer_id and lot7 and subentity:
                    key = (wafer_id, lot7)
                    if key not in wafer_subentity:
                        wafer_subentity[key] = subentity
        
        print(f"[OK] Loaded SUBENTITY info for {len(wafer_subentity)} wafer-lot pairs")
        return wafer_subentity
    except Exception as e:
        print(f"[ERROR] Failed to load production CSV: {e}")
        sys.exit(1)


def pull_apex_entity_for_alias(
    client: WDSClient,
    wafer_id: str,
    alias: str,
    version: str = "V6"
) -> Optional[Dict]:
    """
    Pull APEX@ENTITY data for a single (wafer, alias) pair.
    
    Returns:
        Dict with raw WDS data (wide format), or None if failed.
    """
    pattern = f"^APEX@ENTITY@{alias}@{version}@"
    
    try:
        # Download as dataframe (easier to work with than raw columns)
        # Note: WDSClient.query.download_dataframe() is the method for ad-hoc queries
        # For row-scoped data, use client.wafer.scope(...) or client.query.download_dataframe()
        # depending on the pattern.
        
        # Attempt: use download_dataframe with include_patterns
        result = client.query.download_dataframe(
            data_context="WAFER",
            ids=[wafer_id],
            include_patterns=[pattern]
        )
        
        # result should be a DataFrame; convert to dict
        if result is None or result.empty:
            return None
        
        # Flatten to single row (should only have 1 wafer, but ensure it)
        if len(result) == 0:
            return None
        
        row_data = result.iloc[0].to_dict()
        return row_data
    
    except Exception as e:
        print(f"    [WARN] Failed to pull {alias} for {wafer_id}: {e}")
        return None


def match_subentity_slot(
    wds_data: Dict,
    production_subentity: str,
    alias: str,
    version: str = "V6"
) -> Optional[int]:
    """
    Match production CSV's SUBENTITY to WDS SUBENTITY_N slot.
    
    Naming convention mapping (supplier PM slot → WDS chamber designation):
      PM1 ↔ A1,  PM2 ↔ A2,  PM3 ↔ B1,  PM4 ↔ B2,  PM5 ↔ C1,  PM6 ↔ C2
    
    Returns:
        Slot index N if match found, None otherwise.
    """
    if not production_subentity:
        return None
    
    # Mapping: PM suffix → WDS chamber suffix
    pm_to_chamber = {
        "PM1": "A1", "PM2": "A2", "PM3": "B1",
        "PM4": "B2", "PM5": "C1", "PM6": "C2",
    }
    
    # Extract tool and PM slot from production_subentity (e.g., "AME425_PM1")
    parts = production_subentity.split("_")
    if len(parts) < 2:
        return None
    
    prod_tool = parts[0]
    prod_pm = parts[1] if len(parts) > 1 else None
    
    # Translate PM to chamber designation
    wds_chamber = pm_to_chamber.get(prod_pm)
    if not wds_chamber:
        return None
    
    expected_wds_value = f"{prod_tool}_{wds_chamber}"
    
    # Search for SUBENTITY_N columns
    for slot_idx in range(15):
        col_name = f"APEX@ENTITY@{alias}@{version}@SUBENTITY_{slot_idx}"
        
        if col_name in wds_data:
            wds_value = wds_data[col_name]
            
            # Handle NaN/None
            if isinstance(wds_value, float):
                if __import__('math').isnan(wds_value):
                    wds_value = None
            
            if wds_value and str(wds_value).strip() == expected_wds_value:
                return slot_idx
    
    return None


def extract_matched_slot_fields(
    wds_data: Dict,
    slot_idx: int,
    alias: str,
    version: str = "V6"
) -> Dict[str, any]:
    """
    Extract the 5 subfields for a matched slot.
    
    Returns:
        Dict with keys: BATCH_IDLE, PRIOR_ALIAS, PROCESS_ORDER, SEQUENCE, UTILIZATION.
    """
    result = {}
    subfields = ["BATCH_IDLE", "PRIOR_ALIAS", "PROCESS_ORDER", "SEQUENCE", "UTILIZATION"]
    
    for subfield in subfields:
        col_name = f"APEX@ENTITY@{alias}@{version}@SUBENTITY_{slot_idx}@{subfield}"
        result[subfield] = wds_data.get(col_name, None)
    
    return result


def main():
    """
    Main entry point: pull APEX@ENTITY for pilot wafers, match slots, produce outputs.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Pull APEX@ENTITY for pilot wafers and match subentity slots."
    )
    parser.add_argument("--env", choices=["rf3stg", "rf3prod"], default="rf3stg")
    parser.add_argument("--no-cert-verify", action="store_true")
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    artifact_dir = script_dir / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    
    print("=" * 80)
    print(f"Phase 2, Steps 5-6: Pull APEX@ENTITY and Match Subentity Slots")
    print(f"Started: {datetime.datetime.now().isoformat()}")
    print("=" * 80)
    
    # Load pilot wafers
    print("\n[LOAD] Loading pilot wafers...")
    manifest_path = script_dir / "04_pilot_wafers.csv"
    pilot_wafers = load_pilot_wafers(manifest_path)
    
    # Load production CSV SUBENTITY mapping
    print("[LOAD] Loading production CSV...")
    production_csv = (Path(__file__).resolve().parents[2] / 
                     "outputs" / "wafer" / "8M5CL_8M6CL_EXTENDED.csv")
    wafer_subentity_map = load_production_csv_subentity(production_csv)
    
    # Initialize WDS client
    print("[INIT] Initializing WDS client...")
    try:
        client = get_wds_client(env=args.env, verify_cert=not args.no_cert_verify)
    except Exception as e:
        print(f"[ERROR] Failed to initialize WDS client: {e}")
        sys.exit(1)
    
    # Pull and match
    print("\n[PULL] Pulling APEX@ENTITY and matching slots...")
    raw_data = []  # For 05a output
    matched_data = []  # For 05b output
    match_stats = {"ok": 0, "mismatch": 0, "no_data": 0}
    
    for wafer_id, layer in pilot_wafers:
        print(f"\n  {wafer_id} ({layer}):")
        
        aliases = ALIASES_BY_LAYER.get(layer, [])
        
        for alias in aliases:
            print(f"    {alias}...", end=" ", flush=True)
            
            # Pull from WDS (one alias per call)
            wds_data = pull_apex_entity_for_alias(client, wafer_id, alias)
            
            if wds_data is None:
                print("[no data]")
                match_stats["no_data"] += 1
                continue
            
            # Save raw data
            raw_row = {"WAFER_ID": wafer_id, "ALIAS": alias}
            raw_row.update(wds_data)
            raw_data.append(raw_row)
            
            # Try to match SUBENTITY
            # Note: wafer appears multiple times in production CSV, at different operations
            # Get production SUBENTITY (should be consistent per wafer, or we need to track per operation)
            production_subentity = None
            for (w, l), sub in wafer_subentity_map.items():
                if w == wafer_id:
                    production_subentity = sub
                    break
            
            slot_idx = match_subentity_slot(wds_data, production_subentity, alias) if production_subentity else None
            
            if slot_idx is not None:
                print(f"[match slot {slot_idx}]")
                match_stats["ok"] += 1
                
                # Extract matched slot fields
                matched_fields = extract_matched_slot_fields(wds_data, slot_idx, alias)
                
                # Extract top-level fields
                top_level = {
                    "ENTITY": wds_data.get(f"APEX@ENTITY@{alias}@V6@ENTITY"),
                    "OPERATION": wds_data.get(f"APEX@ENTITY@{alias}@V6@OPERATION"),
                    "WAFER_ENTITY_END_TIME": wds_data.get(f"APEX@ENTITY@{alias}@V6@WAFER_ENTITY_END_TIME"),
                }
                
                matched_row = {
                    "WAFER_ID": wafer_id,
                    "ALIAS": alias,
                    "MATCHED_SLOT": slot_idx,
                    "MATCH_STATUS": "OK",
                    "WDS_SUBENTITY": f"SUBENTITY_{slot_idx}",
                    "PRODUCTION_SUBENTITY": production_subentity,
                }
                matched_row.update(matched_fields)
                matched_row.update(top_level)
                matched_data.append(matched_row)
            else:
                print(f"[MISMATCH] No matching slot for {production_subentity}")
                match_stats["mismatch"] += 1
                
                matched_row = {
                    "WAFER_ID": wafer_id,
                    "ALIAS": alias,
                    "MATCH_STATUS": "MISMATCH",
                    "PRODUCTION_SUBENTITY": production_subentity,
                }
                matched_data.append(matched_row)
    
    # Write raw output (05a)
    if raw_data:
        raw_output = artifact_dir / f"05a_pilot_raw_apex_entity_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            fieldnames = set()
            for row in raw_data:
                fieldnames.update(row.keys())
            fieldnames = ["WAFER_ID", "ALIAS"] + sorted([k for k in fieldnames if k not in ["WAFER_ID", "ALIAS"]])
            
            with open(raw_output, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
                writer.writeheader()
                writer.writerows(raw_data)
            print(f"\n[OK] Raw output written: {raw_output.name} ({len(raw_data)} rows)")
        except Exception as e:
            print(f"[ERROR] Failed to write raw output: {e}")
    
    # Write matched output (05b)
    if matched_data:
        matched_output = artifact_dir / "05b_pilot_matched_wafers.csv"
        try:
            fieldnames = set()
            for row in matched_data:
                fieldnames.update(row.keys())
            fieldnames = ["WAFER_ID", "ALIAS", "MATCH_STATUS", "MATCHED_SLOT"] + sorted([k for k in fieldnames if k not in ["WAFER_ID", "ALIAS", "MATCH_STATUS", "MATCHED_SLOT"]])
            
            with open(matched_output, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
                writer.writeheader()
                writer.writerows(matched_data)
            print(f"[OK] Matched output written: {matched_output.name} ({len(matched_data)} rows)")
        except Exception as e:
            print(f"[ERROR] Failed to write matched output: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Total (wafer, alias) pairs: {len(raw_data)}")
    print(f"Successful matches (slot found): {match_stats['ok']}")
    print(f"Mismatches (no slot match): {match_stats['mismatch']}")
    print(f"No data (WDS query failed): {match_stats['no_data']}")
    
    match_rate = (match_stats["ok"] / len(raw_data) * 100) if raw_data else 0
    print(f"Match rate: {match_rate:.1f}%")
    
    print(f"\n[OK] Pull and match complete. Proceed to Phase 2, Step 7 (validate).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
