#!/usr/bin/env python3
"""
EDI Backfill Scoping Audit
Validates join keys and data quality before backfilling production CSVs with EDI metrics.

Usage:
    python audit_edi_backfill.py

Audit outputs:
    - Join key uniqueness checks (LOT + WAFER_ID + LAYER)
    - Match/mismatch row counts between EDI and production tables
    - Sample validation of matched rows
    - Consolidated audit report
"""

import sys
import os
from pathlib import Path
import pandas as pd
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Workspace and file paths
WORKSPACE_ROOT = Path("\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Defects\\BE")
BE_QUERY_FILES = WORKSPACE_ROOT / "BE_QUERY_FILES"
OUTPUTS_WAFER = WORKSPACE_ROOT / "outputs" / "wafer"

# Source EDI CSVs (full historical)
EDI_8M5CL_PATH = BE_QUERY_FILES / "8M5CL_EDI.csv"
EDI_8M6CL_PATH = BE_QUERY_FILES / "8M6CL_EDI.csv"

# Production target CSVs
PROD_EXTENDED_60DAY_PATH = OUTPUTS_WAFER / "8M5CL_8M6CL_EXTENDED_60DAY.csv"
PROD_EXTENDED_PATH = OUTPUTS_WAFER / "8M5CL_8M6CL_EXTENDED.csv"

# Audit output
AUDIT_REPORT_PATH = BE_QUERY_FILES / "audit_edi_backfill_report.txt"

# Join key columns (must align with pipeline dedup logic in main.py)
# Note: SUBENTITY not available in raw EDI defect pulls; using INSPECT_TIME instead
JOIN_KEYS = ["LOT", "WAFER_ID", "LAYER", "INSPECT_TIME"]
INSPECT_TIME_EDI_COL = "INSPECTION_TIME@DEFECT"  # Column name in EDI CSVs


def check_file_exists(path, name):
    """Verify file exists; log and return True/False"""
    if path.exists():
        logger.info(f"✓ {name}: {path}")
        return True
    else:
        logger.error(f"✗ {name} NOT FOUND: {path}")
        return False


def load_csv(path, name):
    """Load CSV with basic error handling"""
    try:
        df = pd.read_csv(path, low_memory=False)
        logger.info(f"Loaded {name}: {len(df)} rows, {len(df.columns)} columns")
        return df
    except Exception as e:
        logger.error(f"Failed to load {name}: {e}")
        return None


def check_join_key_cols(df, name):
    """Verify all join key columns exist (handle INSPECT_TIME variant)"""
    base_keys = ["LOT", "WAFER_ID", "LAYER"]
    time_col = None
    
    # Check base keys
    missing = [col for col in base_keys if col not in df.columns]
    if missing:
        logger.warning(f"{name}: Missing base join key columns: {missing}")
        return False
    
    # Check for INSPECT_TIME or INSPECTION_TIME@DEFECT
    if "INSPECT_TIME" in df.columns:
        time_col = "INSPECT_TIME"
    elif INSPECT_TIME_EDI_COL in df.columns:
        time_col = INSPECT_TIME_EDI_COL
    else:
        logger.warning(f"{name}: Missing inspection time column (need INSPECT_TIME or {INSPECT_TIME_EDI_COL})")
        return False
    
    logger.info(f"{name}: All join keys present: {base_keys} + {time_col}")
    return True


def normalize_time_column(df, dataset_name):
    """Normalize INSPECT_TIME to standard format; handle both EDI and prod column names"""
    df = df.copy()
    
    # Detect which time column is present
    if "INSPECT_TIME" in df.columns:
        time_col = "INSPECT_TIME"
    elif INSPECT_TIME_EDI_COL in df.columns:
        time_col = INSPECT_TIME_EDI_COL
    else:
        logger.error(f"{dataset_name}: No inspection time column found")
        return None
    
    # Normalize to string format for join
    df["INSPECT_TIME"] = pd.to_datetime(df[time_col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
    
    return df


def check_uniqueness(df, name):
    """Check if join keys are unique"""
    # Normalize INSPECT_TIME first
    df_norm = normalize_time_column(df, name)
    if df_norm is None:
        return False
    
    dedup = df_norm.drop_duplicates(subset=JOIN_KEYS, keep=False)
    duplicates = df_norm[df_norm.duplicated(subset=JOIN_KEYS, keep=False)]
    n_dups = len(duplicates)
    
    if n_dups > 0:
        logger.warning(f"{name}: Found {n_dups} duplicate rows on join key {JOIN_KEYS}")
        logger.info(f"  Sample duplicates:\n{duplicates[JOIN_KEYS].head()}")
        return False
    else:
        logger.info(f"{name}: ✓ All rows unique on join key {JOIN_KEYS}")
        return True


def audit_join(edi_df, prod_df, edi_name, prod_name):
    """Simulate full outer join and report match/mismatch statistics"""
    logger.info(f"\n{'='*70}")
    logger.info(f"AUDIT JOIN: {edi_name} ← → {prod_name}")
    logger.info(f"{'='*70}")
    
    # Normalize INSPECT_TIME in both datasets
    edi_norm = normalize_time_column(edi_df, edi_name)
    prod_norm = normalize_time_column(prod_df, prod_name)
    
    if edi_norm is None or prod_norm is None:
        logger.error("Failed to normalize time columns")
        return None
    
    # Create join indicator columns
    edi_keyed = edi_norm[JOIN_KEYS].copy()
    edi_keyed["_in_edi"] = True
    
    prod_keyed = prod_norm[JOIN_KEYS].copy()
    prod_keyed["_in_prod"] = True
    
    # Full outer join
    merged = edi_keyed.merge(prod_keyed, on=JOIN_KEYS, how="outer")
    merged["_in_edi"] = merged["_in_edi"].fillna(False)
    merged["_in_prod"] = merged["_in_prod"].fillna(False)
    
    # Categorize rows
    both = merged[(merged["_in_edi"]) & (merged["_in_prod"])]
    edi_only = merged[(merged["_in_edi"]) & (~merged["_in_prod"])]
    prod_only = merged[(~merged["_in_edi"]) & (merged["_in_prod"])]
    
    logger.info(f"Total rows in {edi_name}: {len(edi_df)}")
    logger.info(f"Total rows in {prod_name}: {len(prod_df)}")
    logger.info(f"\n  Matched (in both): {len(both)}")
    logger.info(f"  {edi_name} only: {len(edi_only)} ({100*len(edi_only)/len(edi_df):.1f}% of EDI)")
    logger.info(f"  {prod_name} only: {len(prod_only)} ({100*len(prod_only)/len(prod_df):.1f}% of PROD)")
    
    # Flag threshold
    edi_unmatched_pct = 100*len(edi_only)/len(edi_df) if len(edi_df) > 0 else 0
    if edi_unmatched_pct > 5:
        logger.warning(f"\n⚠ WARNING: >5% of EDI rows unmatched in production ({edi_unmatched_pct:.1f}%)")
        logger.info(f"  Sample EDI-only rows:\n{edi_only.head(10)}")
    else:
        logger.info(f"\n✓ EDI unmatched rate acceptable ({edi_unmatched_pct:.1f}%)")
    
    return {
        "matched": len(both),
        "edi_only": len(edi_only),
        "prod_only": len(prod_only),
        "edi_pct_unmatched": edi_unmatched_pct,
        "prod_pct_unmatched": 100 * len(prod_only) / len(prod_df) if len(prod_df) > 0 else 0,
    }


def sample_validation(edi_df, prod_df):
    """Spot-check matched rows for data alignment"""
    logger.info(f"\n{'='*70}")
    logger.info("SAMPLE VALIDATION (Matched Rows)")
    logger.info(f"{'='*70}")
    
    # Normalize INSPECT_TIME in both
    edi_norm = normalize_time_column(edi_df, "EDI")
    prod_norm = normalize_time_column(prod_df, "PROD")
    
    if edi_norm is None or prod_norm is None:
        logger.warning("Failed to normalize time columns for sample validation")
        return
    
    # Merge on join keys to get matched subset
    merged = edi_norm.merge(prod_norm, on=JOIN_KEYS, how="inner", suffixes=("_edi", "_prod"))
    
    if len(merged) == 0:
        logger.warning("No matched rows to validate!")
        return
    
    # Sample up to 5 rows per layer
    for layer in merged["LAYER"].unique():
        layer_sample = merged[merged["LAYER"] == layer].head(3)
        logger.info(f"\nLayer {layer}: {len(layer_sample)} sample(s)")
        
        for idx, row in layer_sample.iterrows():
            logger.info(f"  LOT={row['LOT']}, WAFER_ID={row['WAFER_ID']}")
            
            # Check for EDI columns
            edi_cols = [col for col in row.index if "EDI" in str(col) and not col.endswith("_prod")]
            if edi_cols:
                for col in edi_cols[:3]:  # Show first 3 EDI columns
                    val = row[col]
                    if pd.notna(val):
                        logger.info(f"    {col}: {val}")
            
            # Check INSPECT_TIME alignment
            logger.info(f"    INSPECT_TIME: {row['INSPECT_TIME']}")


def main():
    """Run full audit"""
    logger.info("="*70)
    logger.info("EDI BACKFILL SCOPING AUDIT")
    logger.info("="*70)
    
    # Verify all files exist
    logger.info("\n--- FILE AVAILABILITY CHECK ---")
    files_ok = all([
        check_file_exists(EDI_8M5CL_PATH, "8M5CL_EDI.csv"),
        check_file_exists(EDI_8M6CL_PATH, "8M6CL_EDI.csv"),
        check_file_exists(PROD_EXTENDED_60DAY_PATH, "8M5CL_8M6CL_EXTENDED_60DAY.csv"),
        check_file_exists(PROD_EXTENDED_PATH, "8M5CL_8M6CL_EXTENDED.csv"),
    ])
    
    if not files_ok:
        logger.error("Missing critical files; aborting audit")
        return False
    
    # Load CSVs
    logger.info("\n--- LOADING DATA ---")
    edi_5cl = load_csv(EDI_8M5CL_PATH, "8M5CL_EDI.csv")
    edi_6cl = load_csv(EDI_8M6CL_PATH, "8M6CL_EDI.csv")
    prod_60d = load_csv(PROD_EXTENDED_60DAY_PATH, "8M5CL_8M6CL_EXTENDED_60DAY.csv")
    prod_full = load_csv(PROD_EXTENDED_PATH, "8M5CL_8M6CL_EXTENDED.csv")
    
    if not all([edi_5cl is not None, edi_6cl is not None, prod_60d is not None, prod_full is not None]):
        logger.error("Failed to load one or more CSVs; aborting")
        return False
    
    # Combine EDI data
    edi_combined = pd.concat([edi_5cl, edi_6cl], ignore_index=True)
    logger.info(f"Combined EDI data: {len(edi_combined)} rows")
    
    # Verify join key columns exist
    logger.info("\n--- JOIN KEY VALIDATION ---")
    check_join_key_cols(edi_combined, "EDI combined")
    check_join_key_cols(prod_60d, "EXTENDED_60DAY")
    check_join_key_cols(prod_full, "EXTENDED full")
    
    # Check uniqueness
    logger.info("\n--- JOIN KEY UNIQUENESS CHECK ---")
    check_uniqueness(edi_combined, "EDI combined")
    check_uniqueness(prod_60d, "EXTENDED_60DAY")
    check_uniqueness(prod_full, "EXTENDED full")
    
    # Run join audits
    logger.info("\n--- JOIN AUDITS (Full Outer) ---")
    
    audit_60d = audit_join(edi_combined, prod_60d, "EDI combined", "EXTENDED_60DAY")
    audit_full = audit_join(edi_combined, prod_full, "EDI combined", "EXTENDED full")
    
    # Sample validation
    sample_validation(edi_combined, prod_full)
    
    # Summary and decision
    logger.info(f"\n{'='*70}")
    logger.info("AUDIT SUMMARY & RECOMMENDATION")
    logger.info(f"{'='*70}")
    
    logger.info(f"\n60-DAY BACKFILL:")
    logger.info(f"  Matched: {audit_60d['matched']} rows")
    logger.info(f"  EDI unmatched: {audit_60d['edi_only']} ({audit_60d['edi_pct_unmatched']:.1f}%)")
    logger.info(f"  PROD unmatched: {audit_60d['prod_only']} ({audit_60d['prod_pct_unmatched']:.1f}%)")
    
    logger.info(f"\nFULL BACKFILL:")
    logger.info(f"  Matched: {audit_full['matched']} rows")
    logger.info(f"  EDI unmatched: {audit_full['edi_only']} ({audit_full['edi_pct_unmatched']:.1f}%)")
    logger.info(f"  PROD unmatched: {audit_full['prod_only']} ({audit_full['prod_pct_unmatched']:.1f}%)")
    
    # Decision logic
    edi_threshold = 0.05  # 5%
    if audit_full['edi_pct_unmatched'] > edi_threshold * 100:
        logger.error(f"\n❌ STOP: EDI unmatched rate ({audit_full['edi_pct_unmatched']:.1f}%) exceeds {edi_threshold*100}% threshold")
        logger.error("  Investigate data quality before proceeding with backfill")
        return False
    else:
        logger.info(f"\n✓ PROCEED: EDI unmatched rate ({audit_full['edi_pct_unmatched']:.1f}%) is acceptable")
        logger.info("  Backfill can proceed safely")
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
