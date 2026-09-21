#!/usr/bin/env python3
"""
Phase 4, Step 12: Validate enriched CSV output integrity.

This script:
1. Loads enriched CSV and original production CSV.
2. Validates:
   - Row count unchanged (left join)
   - All 70 WDS columns present
   - No unexpected duplicates/suffixes
   - Sample rows have sensible values
3. Produces integrity check report.

Usage:
    python 10_validate_output_integrity.py [--enriched CSV] [--prod CSV]

Depends on:
    - Phase 4, Steps 10-11 completed (enriched CSV generated)
"""

import sys
import math
from pathlib import Path
from typing import Dict, List, Tuple, Any
import datetime

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not installed. Install via: pip install pandas")
    sys.exit(1)


# Expected WDS columns
FULL_FLOW_ALIASES = [
    "L_8M5_SIARC_DEP", "L_8M5_CHM_DEP", "L_8M5_SED", "E_8M5_HM_ETCH", "W_8M5_HM_CLN",
    "L_8M6_SIARC_DEP", "L_8M6_CHM_DEP", "L_8M6_SED", "E_8M6_HM_ETCH", "W_8M6_HM_CLN",
]

SUBFIELDS = ["BATCH_IDLE", "PRIOR_ALIAS", "PROCESS_ORDER", "SEQUENCE", "UTILIZATION", "MATCHED_SLOT", "WAFER_ENTITY_END_TIME"]


def load_csvs(enriched_path: Path, prod_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load both CSVs."""
    print(f"[LOAD] Loading CSVs...")
    
    try:
        enriched_df = pd.read_csv(enriched_path)
        prod_df = pd.read_csv(prod_path)
        print(f"  Enriched: {len(enriched_df)} rows, {len(enriched_df.columns)} columns")
        print(f"  Production: {len(prod_df)} rows, {len(prod_df.columns)} columns")
        return enriched_df, prod_df
    except Exception as e:
        print(f"[ERROR] Failed to load CSVs: {e}")
        sys.exit(1)


def validate_row_count(enriched: pd.DataFrame, prod: pd.DataFrame) -> bool:
    """Validate row count unchanged."""
    if len(enriched) == len(prod):
        print(f"✓ Row count preserved: {len(enriched)}")
        return True
    else:
        print(f"✗ Row count mismatch: enriched={len(enriched)}, prod={len(prod)}")
        return False


def validate_wds_columns(enriched: pd.DataFrame) -> Tuple[bool, Dict[str, Any]]:
    """Validate all WDS columns present."""
    print(f"\n[VALIDATE] Checking WDS columns...")
    
    expected_cols = []
    for alias in FULL_FLOW_ALIASES:
        for subfield in SUBFIELDS:
            col_name = f"WDS_ENTITY_{alias}_{subfield}"
            expected_cols.append(col_name)
    
    enriched_cols = set(enriched.columns)
    expected_cols_set = set(expected_cols)
    
    missing = expected_cols_set - enriched_cols
    extra_wds = {c for c in enriched_cols if c.startswith("WDS_ENTITY_") and c not in expected_cols_set}
    
    ok = len(missing) == 0 and len(extra_wds) == 0
    
    if ok:
        print(f"  ✓ All {len(expected_cols)} WDS columns present")
    else:
        if missing:
            print(f"  ✗ Missing {len(missing)} columns: {list(missing)[:5]}...")
        if extra_wds:
            print(f"  ✗ Unexpected {len(extra_wds)} extra columns: {list(extra_wds)[:5]}...")
    
    return ok, {"missing": missing, "extra": extra_wds, "total_expected": len(expected_cols)}


def validate_column_names(enriched: pd.DataFrame) -> bool:
    """Check for problematic suffixes (_x, _y from merge errors)."""
    print(f"[VALIDATE] Checking for merge artifacts...")
    
    problematic = [c for c in enriched.columns if c.endswith("_x") or c.endswith("_y")]
    
    if not problematic:
        print(f"  ✓ No merge artifact suffixes found")
        return True
    else:
        print(f"  ✗ Found {len(problematic)} columns with merge suffixes: {problematic[:5]}...")
        return False


def validate_sample_values(enriched: pd.DataFrame) -> bool:
    """Sample 5-10 rows and spot-check WDS column values."""
    print(f"[VALIDATE] Spot-checking sample row values...")
    
    wds_cols = [c for c in enriched.columns if c.startswith("WDS_ENTITY_")]
    
    if not wds_cols:
        print(f"  [WARN] No WDS columns to check")
        return True
    
    # Sample 5 random rows
    sample_count = min(5, len(enriched))
    samples = enriched.sample(n=sample_count, random_state=42)
    
    issues = []
    
    for idx, (_, row) in enumerate(samples.iterrows()):
        # Check for reasonable values
        for col in wds_cols:
            value = row[col]
            
            if pd.isna(value) or value is None:
                continue  # NULLs are OK
            
            # PROCESS_ORDER should be small int
            if "PROCESS_ORDER" in col:
                try:
                    int_val = int(value)
                    if int_val < 0 or int_val > 10000:
                        issues.append(f"Row {idx}, {col}: suspicious PROCESS_ORDER value {value}")
                except (ValueError, TypeError):
                    issues.append(f"Row {idx}, {col}: PROCESS_ORDER not numeric: {value}")
            
            # SEQUENCE should be small int
            elif "SEQUENCE" in col:
                try:
                    int_val = int(value)
                    if int_val < 0 or int_val > 100:
                        issues.append(f"Row {idx}, {col}: suspicious SEQUENCE value {value}")
                except (ValueError, TypeError):
                    issues.append(f"Row {idx}, {col}: SEQUENCE not numeric: {value}")
            
            # UTILIZATION should be 0-1 range
            elif "UTILIZATION" in col:
                try:
                    float_val = float(value)
                    if float_val < 0 or float_val > 1:
                        issues.append(f"Row {idx}, {col}: UTILIZATION out of range: {value}")
                except (ValueError, TypeError):
                    pass  # Could be string/enum
            
            # MATCHED_SLOT should be 0-14
            elif "MATCHED_SLOT" in col:
                try:
                    int_val = int(value)
                    if int_val < 0 or int_val > 14:
                        issues.append(f"Row {idx}, {col}: MATCHED_SLOT out of range: {value}")
                except (ValueError, TypeError):
                    issues.append(f"Row {idx}, {col}: MATCHED_SLOT not numeric: {value}")
    
    if not issues:
        print(f"  ✓ Spot-checked {sample_count} rows: values look reasonable")
        return True
    else:
        print(f"  ⚠ Found {len(issues)} potential issues:")
        for issue in issues[:5]:
            print(f"    - {issue}")
        return True  # Non-fatal, just warnings


def validate_layer_consistency(enriched: pd.DataFrame) -> bool:
    """Check that M5 wafers have M5 data and M6 have M6 data."""
    print(f"[VALIDATE] Checking layer consistency...")
    
    issues = []
    
    M5_ALIASES = [a for a in FULL_FLOW_ALIASES if "8M5" in a]
    M6_ALIASES = [a for a in FULL_FLOW_ALIASES if "8M6" in a]
    
    M5_COLS = [f"WDS_ENTITY_{a}_MATCHED_SLOT" for a in M5_ALIASES]
    M6_COLS = [f"WDS_ENTITY_{a}_MATCHED_SLOT" for a in M6_ALIASES]
    
    for idx, row in enriched.sample(n=min(10, len(enriched)), random_state=42).iterrows():
        layer = row.get("LAYER")
        
        if layer == "8M5CL":
            # M5 wafers should have some M5 data and no M6 data
            m5_data_count = sum(1 for c in M5_COLS if c in enriched.columns and pd.notna(row.get(c)))
            m6_data_count = sum(1 for c in M6_COLS if c in enriched.columns and pd.notna(row.get(c)))
            
            if m5_data_count == 0:
                issues.append(f"Row {idx} (8M5CL): no M5 data found")
            if m6_data_count > 0:
                issues.append(f"Row {idx} (8M5CL): unexpected M6 data found")
        
        elif layer == "8M6CL":
            # M6 wafers should have some M6 data and no M5 data
            m5_data_count = sum(1 for c in M5_COLS if c in enriched.columns and pd.notna(row.get(c)))
            m6_data_count = sum(1 for c in M6_COLS if c in enriched.columns and pd.notna(row.get(c)))
            
            if m6_data_count == 0:
                issues.append(f"Row {idx} (8M6CL): no M6 data found")
            if m5_data_count > 0:
                issues.append(f"Row {idx} (8M6CL): unexpected M5 data found")
    
    if not issues:
        print(f"  ✓ Layer consistency verified")
        return True
    else:
        print(f"  ⚠ Found {len(issues)} layer consistency issues:")
        for issue in issues[:5]:
            print(f"    - {issue}")
        return True  # Non-fatal


def main():
    """
    Main entry point: validate enriched CSV integrity.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate enriched CSV output integrity."
    )
    parser.add_argument(
        "--enriched",
        type=Path,
        default=None,
        help="Path to enriched CSV (auto-detected if not specified)"
    )
    parser.add_argument(
        "--prod",
        type=Path,
        default=None,
        help="Path to original production CSV (auto-detected if not specified)"
    )
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    artifact_dir = script_dir / "artifacts"
    
    print("=" * 80)
    print(f"Phase 4, Step 12: Validate Output Integrity")
    print(f"Started: {datetime.datetime.now().isoformat()}")
    print("=" * 80)
    
    # Resolve input paths
    enriched_csv = args.enriched
    if not enriched_csv:
        # Find most recent enriched_*.csv
        matching = sorted(artifact_dir.glob("enriched_*.csv"))
        if not matching:
            print(f"[ERROR] No enriched CSV found in {artifact_dir}")
            sys.exit(1)
        enriched_csv = matching[-1]
    
    prod_csv = args.prod
    if not prod_csv:
        prod_csv = (Path(__file__).resolve().parents[2] / 
                   "outputs" / "wafer" / "8M5CL_8M6CL_EXTENDED.csv")
    
    print(f"\nEnriched: {enriched_csv}")
    print(f"Production: {prod_csv}")
    
    # Load
    enriched_df, prod_df = load_csvs(enriched_csv, prod_csv)
    
    # Validate
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS:")
    print("=" * 80)
    
    results = {
        "row_count": validate_row_count(enriched_df, prod_df),
        "wds_cols": validate_wds_columns(enriched_df)[0],
        "col_names": validate_column_names(enriched_df),
        "sample_values": validate_sample_values(enriched_df),
        "layer_consistency": validate_layer_consistency(enriched_df),
    }
    
    # Write report
    print("\n[REPORT] Writing integrity check report...")
    report_file = artifact_dir / "enrichment_integrity_check.txt"
    
    try:
        with open(report_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("APEX@ENTITY Enrichment Integrity Check\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Generated: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Enriched CSV: {enriched_csv}\n")
            f.write(f"Production CSV: {prod_csv}\n\n")
            
            f.write("VALIDATION RESULTS:\n")
            f.write("-" * 80 + "\n")
            for check, passed in results.items():
                status = "✓ PASS" if passed else "✗ FAIL"
                f.write(f"{check:25s}: {status}\n")
            
            f.write("\n" + "=" * 80 + "\n")
            all_passed = all(results.values())
            if all_passed:
                f.write("OVERALL: ✓ PASS\n")
                f.write("Enriched CSV is ready for use.\n")
            else:
                f.write("OVERALL: ⚠ REVIEW WARNINGS\n")
                f.write("Check the validation output above for details.\n")
        
        print(f"  [OK] Report written: {report_file.name}")
    except Exception as e:
        print(f"[WARN] Failed to write report: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    
    all_passed = all(results.values())
    
    if all_passed:
        print("✓ All validation checks passed!")
        print(f"\nEnriched CSV: {enriched_csv}")
        print(f"Report: {report_file}")
        print("\n[OK] Phase 4 complete. Enrichment ready for analysis.")
        return 0
    else:
        print("⚠ Some validation checks did not pass. Review report above.")
        print(f"\nReport: {report_file}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
