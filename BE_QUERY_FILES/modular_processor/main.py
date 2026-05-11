# -*- coding: utf-8 -*-
"""
Main execution script for the modular defect data processor

Usage:
    python main.py

This script processes semiconductor defect data by:
1. Loading and combining base defect data files
2. Adding ELWC lookback calculations  
3. Adding leak rate and pump failure data
4. Adding SPC monitor data
5. Generating final processed dataset
"""

import sys
import os
from pathlib import Path
import pandas as pd

# Add the current directory to Python path so we can import our modules
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

import logging
from core.config import Config
from EXTEND_BENCHMARK import refresh_merged_raw_sources
from processors.defect_processor import DefectDataProcessor
from pipeline_config import PIPELINE_PATHS, ensure_pipeline_dirs, validate_pipeline_paths, write_artifact_manifest

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def _wafer_dedup_keys(df):
    preferred = ["LOT", "WAFER_ID", "LAYER", "INSPECT_TIME", "SUBENTITY"]
    keys = [col for col in preferred if col in df.columns]
    if not keys:
        raise ValueError("Unable to determine wafer accumulation keys")
    return keys


def _normalize_wafer_keys(df, dedup_keys):
    normalized = df.copy()
    temp_cols = []
    for key in dedup_keys:
        temp_col = f"__norm_{key}"
        if key == "INSPECT_TIME":
            normalized[temp_col] = pd.to_datetime(normalized[key], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
        else:
            normalized[temp_col] = normalized[key].fillna("").astype(str).str.strip()
        temp_cols.append(temp_col)
    return normalized, temp_cols


def _normalize_wafer_schema(df):
    normalized = df.copy()
    if "INSPECT_TIME" in normalized.columns:
        normalized["YYMM"] = pd.to_datetime(normalized["INSPECT_TIME"], errors="coerce").dt.strftime("%y%m")

    if "YYMM" in normalized.columns:
        ordered = ["YYMM"] + [col for col in normalized.columns if col != "YYMM"]
        normalized = normalized[ordered]

    return normalized


def _accumulate_wafer_output(result_df, output_path):
    output_path = Path(output_path)
    seed_paths = []
    legacy_seed = PIPELINE_PATHS.workspace_root / output_path.name
    for candidate in [legacy_seed, output_path]:
        if candidate.exists() and candidate not in seed_paths:
            seed_paths.append(candidate)

    if not seed_paths:
        logging.info("No existing wafer output seeds found; writing %s new rows", len(result_df))
        return result_df

    frames = []
    for seed_path in seed_paths:
        seed_df = pd.read_csv(seed_path, low_memory=False)
        seed_df = _normalize_wafer_schema(seed_df)
        seed_df["_seed_path"] = str(seed_path)
        frames.append(seed_df)

    result_with_source = _normalize_wafer_schema(result_df)
    result_with_source["_seed_path"] = "current_run"
    frames.append(result_with_source)

    combined = pd.concat(frames, ignore_index=True, sort=False)
    dedup_keys = _wafer_dedup_keys(combined)
    combined, normalized_keys = _normalize_wafer_keys(combined, dedup_keys)
    combined = (
        combined
        .drop_duplicates(subset=normalized_keys, keep="last")
        .drop(columns=["_seed_path", *normalized_keys], errors="ignore")
        .reset_index(drop=True)
    )

    logging.info(
        "Accumulated wafer output using seeds %s -> %s rows",
        [str(path) for path in seed_paths],
        len(combined),
    )
    return _normalize_wafer_schema(combined)

def main():
    """Main execution function with proper error handling"""
    try:
        ensure_pipeline_dirs()

        # Keep wafer processing aligned with latest current JSL raws.
        refresh_merged_raw_sources()

        # Install tqdm if not already available
        try:
            from tqdm import tqdm
        except ImportError:
            print("Installing tqdm for progress bars...")
            import subprocess
            subprocess.check_call(["pip", "install", "tqdm"])
        
        for line in validate_pipeline_paths(
            {
                "merged_m5_csv": PIPELINE_PATHS.merged_m5_csv,
                "merged_m6_csv": PIPELINE_PATHS.merged_m6_csv,
            }
        ):
            logging.info(line)

        # Initialize configuration with selective processor control
        config = Config(
            # Override date filtering settings
            ENABLE_DATE_FILTER=True,
            START_DATE="2025-01-01",
            END_DATE=None,
            
            # Enable/disable processors as needed for faster iteration
            ENABLE_ELWC=False,           # Set to False to skip ELWC processing during development
            ENABLE_LEAK_RATE=False,
            ENABLE_DRY_PUMP=False,
            ENABLE_LEAK_BY=False,
            ENABLE_SPC_MONITOR=False,
            ENABLE_RECOAT=False,
            ENABLE_DEFECT_TRENDS=False,  # Enable/disable trends
            ENABLE_ELWC2= False,  # Enable/disable ELWC2 processor
            ENABLE_LOT_LEVEL_OUTPUT = False,  # Flag to enable/disable lot-level output
            # Optional: Override output path (NEW!)
            OUTPUT_PATH=str(PIPELINE_PATHS.extended_output_csv)

        )
        
        # Process data
        processor = DefectDataProcessor(config)
        result_df = processor.process()
        result_df = _accumulate_wafer_output(result_df, config.OUTPUT_PATH)
        
        # Save results
        result_df.to_csv(config.OUTPUT_PATH, index=False)
        logging.info(f"Processed data saved to: {config.OUTPUT_PATH}")
        manifest_path = write_artifact_manifest(
            PIPELINE_PATHS.main_artifact_manifest,
            extra_outputs={"main_output_csv": Path(config.OUTPUT_PATH)},
        )
        logging.info(f"Artifact manifest saved to: {manifest_path}")
        
        # Show final summary
        logging.info(f"\nFinal enhanced dataframe shape: {result_df.shape}")
        
        # Show CLASS column distributions (original and new)
        logging.info(f"\nCLASS column distribution (SUM_NCDD, threshold=0.02):")
        logging.info(f"{result_df['CLASS'].value_counts()}")
        
        if 'CLASS_BEEP' in result_df.columns:
            logging.info(f"\nCLASS_BEEP column distribution (BEEP_NCDD, threshold=0.0094):")
            logging.info(f"{result_df['CLASS_BEEP'].value_counts()}")
        
        if 'CLASS_SMP' in result_df.columns:
            logging.info(f"\nCLASS_SMP column distribution (SMP_NCDD, threshold=0.013):")
            logging.info(f"{result_df['CLASS_SMP'].value_counts()}")
        
        # Show STATUS column distributions
        logging.info(f"\nSTATUS column distribution (SUM_NCDD, threshold=0.02):")
        logging.info(f"{result_df['STATUS'].value_counts()}")
        
        if 'STATUS_BEEP' in result_df.columns:
            logging.info(f"\nSTATUS_BEEP column distribution (BEEP_NCDD, threshold=0.0094):")
            logging.info(f"{result_df['STATUS_BEEP'].value_counts()}")
        
        if 'STATUS_SMP' in result_df.columns:
            logging.info(f"\nSTATUS_SMP column distribution (SMP_NCDD, threshold=0.013):")
            logging.info(f"{result_df['STATUS_SMP'].value_counts()}")
        
        # Show ZERO column summaries
        zero_cols = ['ZERO_NCDD', 'ZERO_BEEP', 'ZERO_SMP']
        existing_zero_cols = [col for col in zero_cols if col in result_df.columns]
        if existing_zero_cols:
            logging.info(f"\nZERO columns summary:")
            for col in existing_zero_cols:
                true_count = result_df[col].sum()
                total_count = len(result_df)
                logging.info(f"{col}: {true_count}/{total_count} ({true_count/total_count*100:.1f}%) are zero")
        
        # Show ROUTE column summary
        if 'ROUTE' in result_df.columns:
            logging.info(f"\nROUTE column distribution:")
            route_counts = result_df['ROUTE'].value_counts().head(10)
            logging.info(f"{route_counts}")
        
        # Show DEVICE column summary
        if 'DEVICE' in result_df.columns:
            logging.info(f"\nDEVICE column distribution:")
            device_counts = result_df['DEVICE'].value_counts().head(10)
            logging.info(f"{device_counts}")
        
        # NEW: Show summary of stepper and SIF columns
        if 'STEPPER' in result_df.columns:
            logging.info(f"\nSTEPPER column summary:")
            stepper_counts = result_df['STEPPER'].value_counts().head(10)
            logging.info(f"{stepper_counts}")
        
        if 'RETICLE' in result_df.columns:
            logging.info(f"\nRETICLE column summary:")
            reticle_non_null = result_df['RETICLE'].notna().sum()
            total_count = len(result_df)
            logging.info(f"Non-null reticles: {reticle_non_null}/{total_count} ({reticle_non_null/total_count*100:.1f}%)")
            if reticle_non_null > 0:
                unique_reticles = result_df['RETICLE'].nunique()
                logging.info(f"Unique reticles: {unique_reticles}")
        
        # Show SIF flag summaries
        sif_cols = ['SIF_SED', 'SIF_ETCH', 'SIF_DEFECT']
        existing_sif_cols = [col for col in sif_cols if col in result_df.columns]
        if existing_sif_cols:
            logging.info(f"\nSIF flag summaries:")
            for col in existing_sif_cols:
                ones_count = (result_df[col] == 1).sum()
                total_count = len(result_df)
                logging.info(f"{col}: {ones_count}/{total_count} ({ones_count/total_count*100:.1f}%) have SIF data")

        # Show N_SCAN column summary
        if 'N_SCAN' in result_df.columns:
            logging.info(f"\nN_SCAN column summary:")
            n_scan_stats = result_df['N_SCAN'].describe()
            logging.info(f"N_SCAN statistics: {n_scan_stats}")
            n_scan_counts = result_df['N_SCAN'].value_counts().sort_index()
            logging.info(f"N_SCAN distribution: {n_scan_counts.to_dict()}")
                
        # Show defect trends column summaries (if enabled)
        if config.ENABLE_DEFECT_TRENDS:
            # Get all trend columns
            trend_cols = [col for col in result_df.columns if any(
                col.startswith(f"{days}DAY_") for days in config.TREND_LOOKBACK_DAYS
            )]
            
            if trend_cols:
                logging.info(f"\nDefect trends column summaries:")
                
                # Group by lookback days for organized display
                for days in config.TREND_LOOKBACK_DAYS:
                    day_cols = [col for col in trend_cols if col.startswith(f"{days}DAY_")]
                    if day_cols:
                        logging.info(f"\n{days}-day lookback trends:")
                        for col in day_cols:
                            non_null_count = result_df[col].notna().sum()
                            total_count = len(result_df)
                            coverage = non_null_count / total_count * 100
                            
                            if non_null_count > 0:
                                mean_rate = result_df[col].mean()
                                max_rate = result_df[col].max()
                                logging.info(f"  {col}: {non_null_count}/{total_count} ({coverage:.1f}%) non-null, "
                                           f"mean={mean_rate:.4f}, max={max_rate:.4f}")
                            else:
                                logging.info(f"  {col}: {non_null_count}/{total_count} ({coverage:.1f}%) non-null")
                
                # Show sample of trend data
                logging.info(f"\nSample of defect trends columns:")
                sample_cols = ['WAFER_ID', 'LOT', 'LAYER'] + trend_cols[:6]  # Show first 6 trend columns
                available_cols = [col for col in sample_cols if col in result_df.columns]
                logging.info(f"{result_df[available_cols].head()}")

        # Show sample of leak by columns (if enabled)
        if config.ENABLE_LEAK_BY:
            leak_by_cols = [col for col in result_df.columns if col.startswith('LB_')]
            if leak_by_cols:
                logging.info(f"\nSample of leak by columns:")
                logging.info(f"{result_df[['WAFER_ID', 'SUBENTITY'] + leak_by_cols[:6]].head()}")
        
        # Show sample of ELWC lookback columns (if enabled)
        if config.ENABLE_ELWC:
            elwc_cols = [col for col in result_df.columns if any(group in col for group in ['MONTW', '8GAB', '0GAB'])]
            if elwc_cols:
                logging.info(f"\nSample of ELWC lookback columns:")
                logging.info(f"{result_df[['WAFER_ID', 'OPERATION', 'SUBENTITY'] + elwc_cols[:6]].head()}")
        
        return result_df
        
    except Exception as e:
        logging.error(f"Main processing failed: {e}")
        raise


if __name__ == "__main__":
    main()

