#!/usr/bin/env python3
"""
EDI vs Production Data Structure Diagnostic
Investigates why join keys don't match and identifies correct linking strategy.
"""

import pandas as pd
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path("\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Defects\\BE")
BE_QUERY_FILES = WORKSPACE_ROOT / "BE_QUERY_FILES"
OUTPUTS_WAFER = WORKSPACE_ROOT / "outputs" / "wafer"

edi_5cl = pd.read_csv(BE_QUERY_FILES / "8M5CL_EDI.csv", low_memory=False)
prod_full = pd.read_csv(OUTPUTS_WAFER / "8M5CL_8M6CL_EXTENDED.csv", low_memory=False)

logger.info("="*80)
logger.info("EDI DATA STRUCTURE (8M5CL_EDI.csv first 5 rows)")
logger.info("="*80)
logger.info(f"Shape: {edi_5cl.shape}")
logger.info(f"Columns: {list(edi_5cl.columns[:15])}")  # First 15 columns
logger.info("\nFirst 3 rows (key columns):")
for col in ["LOT", "WAFER", "WAFER_ID", "LAYER", "INSPECTION_TIME@DEFECT", "WAFER_KEY@DEFECT"]:
    if col in edi_5cl.columns:
        logger.info(f"\n{col}:")
        logger.info(f"  Sample values: {edi_5cl[col].head(3).tolist()}")
        logger.info(f"  Data type: {edi_5cl[col].dtype}")

logger.info("\n" + "="*80)
logger.info("PRODUCTION DATA STRUCTURE (8M5CL_8M6CL_EXTENDED.csv first 5 rows)")
logger.info("="*80)
logger.info(f"Shape: {prod_full.shape}")
logger.info(f"Columns: {list(prod_full.columns[:15])}")  # First 15 columns
logger.info("\nFirst 3 rows (key columns):")
for col in ["LOT", "WAFER", "WAFER_ID", "LAYER", "INSPECT_TIME", "WAFER_KEY"]:
    if col in prod_full.columns:
        logger.info(f"\n{col}:")
        logger.info(f"  Sample values: {prod_full[col].head(3).tolist()}")
        logger.info(f"  Data type: {prod_full[col].dtype}")

logger.info("\n" + "="*80)
logger.info("POTENTIAL JOIN COLUMNS")
logger.info("="*80)

# Check for any overlapping LOT values
edi_lots = set(edi_5cl["LOT"].unique())
prod_lots = set(prod_full["LOT"].unique())
overlap_lots = edi_lots & prod_lots
logger.info(f"\nEDI unique LOTs: {len(edi_lots)}")
logger.info(f"PROD unique LOTs: {len(prod_lots)}")
logger.info(f"Overlapping LOTs: {len(overlap_lots)}")
if overlap_lots:
    logger.info(f"  Sample overlaps: {list(overlap_lots)[:5]}")
    
    # Try join on overlapping LOT
    edi_sample = edi_5cl[edi_5cl["LOT"].isin(overlap_lots)].head(3)
    prod_sample = prod_full[prod_full["LOT"].isin(overlap_lots)].head(3)
    logger.info(f"\n  EDI sample (LOT in overlap):")
    logger.info(f"    {edi_sample[['LOT', 'WAFER_ID', 'LAYER']].to_string()}")
    logger.info(f"\n  PROD sample (LOT in overlap):")
    logger.info(f"    {prod_sample[['LOT', 'WAFER_ID', 'LAYER']].to_string()}")
else:
    logger.info("  ⚠ No overlapping LOTs found!")

# Check WAFER_KEY
logger.info("\n" + "-"*80)
logger.info("WAFER_KEY as alternative join:")
if "WAFER_KEY@DEFECT" in edi_5cl.columns and "WAFER_KEY" in prod_full.columns:
    edi_wk = set(edi_5cl["WAFER_KEY@DEFECT"].dropna().unique())
    prod_wk = set(prod_full["WAFER_KEY"].dropna().unique())
    overlap_wk = edi_wk & prod_wk
    logger.info(f"  EDI unique WAFER_KEYs: {len(edi_wk)}")
    logger.info(f"  PROD unique WAFER_KEYs: {len(prod_wk)}")
    logger.info(f"  Overlapping WAFER_KEYs: {len(overlap_wk)}")
    if overlap_wk:
        logger.info(f"    Sample overlaps: {list(overlap_wk)[:5]}")

# Check INSPECT_TIME alignment
logger.info("\n" + "-"*80)
logger.info("INSPECT_TIME alignment:")
if "INSPECTION_TIME@DEFECT" in edi_5cl.columns and "INSPECT_TIME" in prod_full.columns:
    edi_times = set(edi_5cl["INSPECTION_TIME@DEFECT"].dropna().unique())
    prod_times = set(prod_full["INSPECT_TIME"].dropna().unique())
    logger.info(f"  EDI unique INSPECTION_TIMEs: {len(edi_times)}")
    logger.info(f"  PROD unique INSPECT_TIMEs: {len(prod_times)}")
    logger.info(f"  Sample EDI times: {list(edi_times)[:3]}")
    logger.info(f"  Sample PROD times: {list(prod_times)[:3]}")
