#!/usr/bin/env python
"""
EDI Backfill Script - Phase 1 Revisited

Re-applies the complete EDI history from standalone EDI CSV files
into the production wafer output CSV.

Join Strategy:
  - Key: WAFER_ID + LAYER (wafer-level, not inspection-time dependent)
  - This captures complete EDI metrics history for each wafer
  
Expected Result:
  - 8M5CL: ~4,455 EDI records backfilled
  - 8M6CL: ~5,524 EDI records backfilled
  - Total: ~9,979 rows with EDI data restored
"""

import pandas as pd
from pathlib import Path
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('EDI_Backfill')

def load_and_prepare_edi_csv(edi_csv_path, layer_name):
    """Load EDI CSV and extract/rename metric columns"""
    logger.info(f"Loading {layer_name} EDI backfill: {edi_csv_path}")
    
    df = pd.read_csv(edi_csv_path, low_memory=False)
    logger.info(f"  Loaded: {len(df)} rows, {len(df.columns)} cols")
    
    # Keep only essential columns for backfill
    keep_cols = ['WAFER_ID', 'LAYER']
    
    # Find and rename EDI metric columns
    edi_metric_cols = [col for col in df.columns if 'CLASS_EDI' in col]
    logger.info(f"  Found {len(edi_metric_cols)} EDI metric columns")
    
    # Extract rename mapping
    rename_map = {}
    for col in edi_metric_cols:
        if 'CLASS_EDI@BEEP' in col:
            rename_map[col] = 'BEEP_EDI'
        elif 'CLASS_EDI@SMALL_PARTICLE' in col:
            rename_map[col] = 'SMP_EDI'
    
    logger.info(f"  Rename mapping: {rename_map}")
    
    # Select columns for backfill
    select_cols = keep_cols + list(rename_map.keys())
    available = [col for col in select_cols if col in df.columns]
    
    result = df[available].copy()
    result = result.rename(columns=rename_map)
    
    logger.info(f"  Prepared: {len(result)} rows with columns {list(result.columns)}")
    return result


def backfill_edi_metrics(prod_csv_path, m5_edi_csv, m6_edi_csv, output_csv_path):
    """Backfill EDI metrics from historical CSVs into production CSV"""
    
    logger.info("=" * 80)
    logger.info("EDI BACKFILL PROCESS")
    logger.info("=" * 80)
    
    # Load production CSV
    logger.info(f"\nLoading production CSV: {prod_csv_path}")
    prod_df = pd.read_csv(prod_csv_path, low_memory=False)
    logger.info(f"  Loaded: {len(prod_df)} rows")
    
    before_edi_nulls = prod_df['BEEP_EDI'].isna().sum()
    logger.info(f"  BEEP_EDI nulls before backfill: {before_edi_nulls}/{len(prod_df)}")
    
    # Load and prepare EDI backfills
    m5_edi = load_and_prepare_edi_csv(m5_edi_csv, "8M5CL")
    m6_edi = load_and_prepare_edi_csv(m6_edi_csv, "8M6CL")
    
    # Combine EDI backfills
    combined_edi = pd.concat([m5_edi, m6_edi], ignore_index=True)
    logger.info(f"\nCombined EDI backfill: {len(combined_edi)} rows")
    logger.info(f"  Layers: {combined_edi['LAYER'].unique()}")
    
    # Join production CSV with EDI backfill by WAFER_ID + LAYER
    logger.info(f"\nJoining by WAFER_ID + LAYER...")
    join_key = ['WAFER_ID', 'LAYER']
    
    # Use left merge to preserve all production rows
    backfilled = pd.merge(
        prod_df,
        combined_edi,
        on=join_key,
        how='left',
        suffixes=('', '_edi_backfill')
    )
    
    # Consolidate: use backfill data to fill nulls
    logger.info(f"Consolidating EDI columns...")
    
    # BEEP_EDI: fill nulls from backfill
    if 'BEEP_EDI_edi_backfill' in backfilled.columns:
        backfilled['BEEP_EDI'] = backfilled['BEEP_EDI'].fillna(
            backfilled['BEEP_EDI_edi_backfill']
        )
        backfilled = backfilled.drop(columns=['BEEP_EDI_edi_backfill'])
    
    # SMP_EDI: fill nulls from backfill
    if 'SMP_EDI_edi_backfill' in backfilled.columns:
        backfilled['SMP_EDI'] = backfilled['SMP_EDI'].fillna(
            backfilled['SMP_EDI_edi_backfill']
        )
        backfilled = backfilled.drop(columns=['SMP_EDI_edi_backfill'])
    
    # Recalculate SUM_EDI if BEEP_EDI and SMP_EDI available
    logger.info(f"Recalculating SUM_EDI...")
    beep_filled = pd.to_numeric(backfilled['BEEP_EDI'], errors='coerce').fillna(0)
    smp_filled = pd.to_numeric(backfilled['SMP_EDI'], errors='coerce').fillna(0)
    backfilled['SUM_EDI'] = beep_filled + smp_filled
    
    # Verify results
    after_edi_nulls = backfilled['BEEP_EDI'].isna().sum()
    beep_filled_count = before_edi_nulls - after_edi_nulls
    
    logger.info(f"\n" + "=" * 80)
    logger.info(f"BACKFILL RESULTS")
    logger.info(f"=" * 80)
    logger.info(f"BEEP_EDI:")
    logger.info(f"  Before: {before_edi_nulls} nulls")
    logger.info(f"  After:  {after_edi_nulls} nulls")
    logger.info(f"  Filled: {beep_filled_count} records")
    logger.info(f"  Coverage: {(1 - after_edi_nulls/len(backfilled))*100:.1f}%")
    
    # Save output
    output_path = Path(output_csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    backfilled.to_csv(output_path, index=False)
    logger.info(f"\n✓ Backfilled CSV saved: {output_path}")
    logger.info(f"  Total rows: {len(backfilled)}")
    logger.info(f"  Total cols: {len(backfilled.columns)}")
    
    return backfilled


def main():
    workspace_root = Path(r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE')
    
    prod_csv = workspace_root / 'outputs' / 'wafer' / '8M5CL_8M6CL_EXTENDED.csv'
    m5_edi = workspace_root / 'BE_QUERY_FILES' / '8M5CL_EDI.csv'
    m6_edi = workspace_root / 'BE_QUERY_FILES' / '8M6CL_EDI.csv'
    output_csv = workspace_root / 'outputs' / 'wafer' / '8M5CL_8M6CL_EXTENDED.csv'
    
    # Run backfill
    result_df = backfill_edi_metrics(
        str(prod_csv),
        str(m5_edi),
        str(m6_edi),
        str(output_csv)
    )
    
    logger.info(f"\n" + "=" * 80)
    logger.info(f"BACKFILL COMPLETE")
    logger.info(f"=" * 80)
    

if __name__ == '__main__':
    main()
