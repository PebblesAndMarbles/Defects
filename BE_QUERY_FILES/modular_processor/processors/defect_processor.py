# -*- coding: utf-8 -*-
"""
Main defect data processor that orchestrates all processing steps
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from core.base_processors import ProcessorBase
from core.utils import DataUtils, DataValidator
from core.column_manager import ColumnManager
from core.config import Config

from processors.elwc_processor import OptimizedELWCProcessor
from processors.leak_processors import RefactoredLeakRateProcessor, LeakByProcessor
from processors.pump_processor import RefactoredDryPumpProcessor
from processors.spc_processor import SPCMonitorProcessor
from processors.defect_trends_processor import DefectTrendsProcessor
from processors.elwc2_processor import ELWC2Processor


class DefectDataProcessor(ProcessorBase):
    """Main defect data processor that orchestrates all processing steps"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        # Initialize processors based on config flags
        self.elwc_processor = OptimizedELWCProcessor(config) if config.ENABLE_ELWC else None
        self.elwc2_processor = ELWC2Processor(config) if config.ENABLE_ELWC2 else None
        self.dp_processor = RefactoredDryPumpProcessor(config) if config.ENABLE_DRY_PUMP else None
        self.leak_processor = RefactoredLeakRateProcessor(config) if config.ENABLE_LEAK_RATE else None
        self.leak_by_processor = LeakByProcessor(config) if config.ENABLE_LEAK_BY else None
        self.spc_monitor_processor = SPCMonitorProcessor(config) if config.ENABLE_SPC_MONITOR else None
        self.trends_processor = DefectTrendsProcessor(config) if config.ENABLE_DEFECT_TRENDS else None
        
        # Log which processors are enabled
        self._log_processor_status()
    
    def _log_processor_status(self):
        """Log which processors are enabled/disabled"""
        self.logger.info("=== PROCESSOR STATUS ===")
        processors = [
            ("ELWC Lookbacks", self.config.ENABLE_ELWC),
            ("ELWC2 Production Utilization", self.config.ENABLE_ELWC2),
            ("Dry Pump Failures", self.config.ENABLE_DRY_PUMP),
            ("Leak Rates", self.config.ENABLE_LEAK_RATE),
            ("Leak By (Gas-specific)", self.config.ENABLE_LEAK_BY),
            ("SPC Monitors", self.config.ENABLE_SPC_MONITOR),
            ("Defect Trends", self.config.ENABLE_DEFECT_TRENDS),
            ("Recoat Status", self.config.ENABLE_RECOAT)
        ]
        
        for name, enabled in processors:
            status = "ENABLED" if enabled else "DISABLED"
            self.logger.info(f"{name}: {status}")
        self.logger.info("========================\n")
        
    
    
    def load_base_data(self) -> pd.DataFrame:
        """Load and combine base defect data"""
        self.logger.info("Loading and concatenating data files...")
        
        df1 = self.safe_load_csv(self.config.FILE1_PATH)
        df2 = self.safe_load_csv(self.config.FILE2_PATH)
        
        if df1 is None or df2 is None:
            raise ValueError("Failed to load base data files")
        
        dt = pd.concat([df1, df2], ignore_index=True)
        self.logger.info(f"Combined dataframe shape: {dt.shape}")
        
        # NEW: Apply date filtering if enabled
        if self.config.ENABLE_DATE_FILTER:
            dt = self._apply_date_filter(dt)
        
        return dt
    
    def _apply_date_filter(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Apply date range filtering to reduce dataset size"""
        self.logger.info("Applying date range filter...")
        
        # Use only INSPECTION_TIME@DEFECT for filtering
        time_col = 'INSPECTION_TIME@DEFECT'
        
        if time_col not in dt.columns:
            self.logger.warning(f"Time column '{time_col}' not found for date filtering")
            self.logger.info(f"Available columns: {sorted(dt.columns)}")
            return dt
        
        self.logger.info(f"Using {time_col} for date filtering")
        
        # Convert to datetime
        dt = DataUtils.safe_datetime_convert(dt, time_col)
        original_size = len(dt)
        
        # Apply filters
        if self.config.start_datetime:
            dt = dt[dt[time_col] >= self.config.start_datetime]
            self.logger.info(f"After start date filter ({self.config.START_DATE}): {len(dt)} rows")
        
        if self.config.end_datetime:
            dt = dt[dt[time_col] <= self.config.end_datetime]
            self.logger.info(f"After end date filter ({self.config.END_DATE}): {len(dt)} rows")
        
        filtered_size = len(dt)
        if original_size > 0:
            reduction_pct = (1 - filtered_size/original_size) * 100
            self.logger.info(f"Date filtering reduced dataset by {reduction_pct:.1f}% ({original_size} -> {filtered_size} rows)")
        
        return dt
    
    def clean_and_rename_columns(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Clean and rename columns - UPDATED to handle new stepper and SIF columns"""
        self.logger.info("Cleaning and renaming columns...")
        
        # Delete columns containing 'SORTER'
        cols_to_delete = [col for col in dt.columns if 'SORTER' in col]
        if cols_to_delete:
            dt = dt.drop(columns=cols_to_delete)
        
        # Columns to keep
        cols2keep = ["WAFER", "WAFER_ID", "LAYER"]
        
        # Create rename mapping for exact matches
        rename_map = {
            "DEFECT@WAFER@CLASS_NCDD@BEEP": "BEEP_NCDD",
            "DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE": "SMP_NCDD",
            "ACTUAL_LOT@DEFECT": "LOT",
            "INSPECTION_TIME@DEFECT": "INSPECT_TIME",
            "INSPECTION_TOOL@DEFECT": "INSPECT_TOOL",
            "PRODUCT@STARTS": "PRODUCT",
            "ROUTE@STARTS": "ROUTE_STARTS",
            "DEVICE@DEFECT": "DEVICE"
        }
        
        # Flexible patterns that might differ between 8M5 and 8M6
        flexible_patterns = {
            "LOT": "LOT7",
            "SLOT": "SLOT",
            "SUBENTITY": "SUBENTITY",
            "OPERATION_NUMBER": "OPERATION",
            "RECIPE@NTSC": "RECIPE",
            "END_TIME@CHAMBER": "SUBENTITY_END_TIME",
            "PROCESS_ORDER": "P_ORDER",
            "FullPMCounter": "FULLPM",
            "FullPMRFCounter": "FULLPM_RF",
            "MiniPMCounter": "MINIPM",
            "MiniPMRFCounter": "MINIPM_RF",
            "SSCounter": "CNTR_SS",
            "PRIOR_LOT_RECIPE": "PL_RECIPE",
            "PRIOR_TIME_BETWEEN": "PT_BTWN",
            "TIME@PRIOR_LOT": "PL_TIME",
            "PROCESS_TIME@BATCH_SUBENTITY_UTILIZATION@12HOURS": "UPT_12HRS",
            "N_WAFERS@BATCH_SUBENTITY_UTILIZATION@12HOURS": "UNW_12HRS",
            "PERCENT_UTILIZATION@BATCH_SUBENTITY_UTILIZATION@12HOURS": "UP_12HRS",
            # IMPORTANT: Put specific patterns BEFORE generic ones
            "ENTITY@NTSC@STEPPER@L_8M": "STEPPER",  # <-- MOVED UP
            "RETICLE@NTSC@STEPPER@L_8M": "RETICLE",
            "ENTITY": "ENTITY",  # <-- MOVED DOWN (after specific ENTITY patterns)
        }
        
        # NEW: SIF patterns that need binary conversion (1 if data exists, 0 otherwise)
        sif_binary_patterns = {
            "SIF_FLAG@SIFDATA@L_8M": "SIF_SED",
            "SIF_FLAG@SIFDATA@E_8M": "SIF_ETCH",
            "SIF_FLAG@SIFDATA@173457": "SIF_DEFECT",  # M5 specific
            "SIF_FLAG@SIFDATA@174824": "SIF_DEFECT"   # M6 specific
        }
        
        # Process flexible patterns FIRST (existing logic)
        for pattern, new_name in flexible_patterns.items():
            matching_cols = [col for col in dt.columns if col.startswith(pattern)]
            
            if matching_cols:
                dt[new_name] = None
                
                # Copy data from all matching columns, prioritizing non-null values
                for col in matching_cols:
                    mask = dt[new_name].isna() & dt[col].notna()
                    dt.loc[mask, new_name] = dt.loc[mask, col]
                
                # Drop the original columns
                dt = dt.drop(columns=matching_cols)
                cols2keep.append(new_name)
        
        # NEW: Process SIF binary patterns
        for pattern, new_name in sif_binary_patterns.items():
            matching_cols = [col for col in dt.columns if col.startswith(pattern)]
            
            if matching_cols:
                # Initialize column to 0
                if new_name not in dt.columns:
                    dt[new_name] = 0
                    cols2keep.append(new_name)
                
                # Set to 1 if any matching column has non-null data
                for col in matching_cols:
                    mask = dt[col].notna() & (dt[col] != '') & (dt[col] != 0)
                    dt.loc[mask, new_name] = 1
                
                # Drop the original columns
                dt = dt.drop(columns=matching_cols)
        
        # THEN process exact matches (existing logic)
        for key, new_name in rename_map.items():
            if key in dt.columns:
                dt = dt.rename(columns={key: new_name})
                cols2keep.append(new_name)
        
        # Create ROUTE column from ROUTE_STARTS (existing logic)
        if 'ROUTE_STARTS' in dt.columns:
            self.logger.info("Creating ROUTE column from ROUTE_STARTS (first 2 characters)...")
            dt['ROUTE'] = dt['ROUTE_STARTS'].astype(str).str[:2]
            cols2keep.append('ROUTE')
            
            # Show sample of ROUTE extraction
            sample_routes = dt[['ROUTE_STARTS', 'ROUTE']].dropna().head(10)
            if not sample_routes.empty:
                self.logger.info("Sample ROUTE extraction:")
                for idx, row in sample_routes.iterrows():
                    self.logger.info(f"  {row['ROUTE_STARTS']} -> {row['ROUTE']}")
        
        # Delete columns not in cols2keep
        final_cols_to_delete = [col for col in dt.columns if col not in cols2keep]
        if final_cols_to_delete:
            dt = dt.drop(columns=final_cols_to_delete)
        
        self.logger.info("Column renaming and cleanup complete!")
        self.logger.info(f"New columns added: STEPPER, RETICLE, SIF_SED, SIF_ETCH, SIF_DEFECT")
        
        # Show summary of new columns
        self._show_new_column_summary(dt)
        
        return dt
    
    def _show_new_column_summary(self, dt: pd.DataFrame):
        """Show summary of newly added stepper and SIF columns"""
        self.logger.info("\n=== NEW COLUMN SUMMARY ===")
        
        # Define total_rows at the beginning
        total_rows = len(dt)
        
        # STEPPER column
        if 'STEPPER' in dt.columns:
            stepper_non_null = dt['STEPPER'].notna().sum()
            self.logger.info(f"STEPPER: {stepper_non_null}/{total_rows} ({stepper_non_null/total_rows*100:.1f}%) non-null values")
            if stepper_non_null > 0:
                unique_steppers = dt['STEPPER'].nunique()
                self.logger.info(f"  Unique steppers: {unique_steppers}")
                top_steppers = dt['STEPPER'].value_counts().head(5)
                self.logger.info(f"  Top steppers: {top_steppers.to_dict()}")
        
        # RETICLE column
        if 'RETICLE' in dt.columns:
            reticle_non_null = dt['RETICLE'].notna().sum()
            self.logger.info(f"RETICLE: {reticle_non_null}/{total_rows} ({reticle_non_null/total_rows*100:.1f}%) non-null values")
            if reticle_non_null > 0:
                unique_reticles = dt['RETICLE'].nunique()
                self.logger.info(f"  Unique reticles: {unique_reticles}")
        
        # SIF columns (binary flags)
        sif_cols = ['SIF_SED', 'SIF_ETCH', 'SIF_DEFECT']
        for col in sif_cols:
            if col in dt.columns:
                ones_count = (dt[col] == 1).sum()
                zeros_count = (dt[col] == 0).sum()
                self.logger.info(f"{col}: {ones_count} ones ({ones_count/total_rows*100:.1f}%), {zeros_count} zeros ({zeros_count/total_rows*100:.1f}%)")
        
        self.logger.info("===========================\n")
    
    def add_pilot_status(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add pilot status columns"""
        self.logger.info("Adding pilot status columns...")
        
        # Load pilot turn-on dates
        pilot_on_time_df = self.safe_load_csv(self.config.PILOT_DATES_PATH)
        if pilot_on_time_df is None:
            self.logger.error("Failed to load pilot dates")
            return dt
        
        # Convert time columns to datetime
        time_column_name = "SUBENTITY_END_TIME"
        subentity_column_name = "SUBENTITY"
        
        if time_column_name in dt.columns:
            dt = DataUtils.safe_datetime_convert(dt, time_column_name)
        
        for col in self.config.PILOT_COLUMNS:
            if col in pilot_on_time_df.columns:
                pilot_on_time_df = DataUtils.safe_datetime_convert(pilot_on_time_df, col)
        
        # Create pilot status columns
        self.logger.info("Creating pilot status columns...")
        for col_to_create in self.config.PILOT_COLUMNS:
            dt[col_to_create] = "OFF"  # Initialize all as OFF
            
            for i in dt.index:
                current_subentity = dt.loc[i, subentity_column_name]
                current_data_time = dt.loc[i, time_column_name]
                
                # Skip if subentity or time is null
                if pd.isna(current_subentity) or pd.isna(current_data_time):
                    continue
                
                # Find matching subentity in pilot data
                matching_rows = pilot_on_time_df[pilot_on_time_df['SUBENTITY'] == current_subentity]
                
                if not matching_rows.empty and col_to_create in pilot_on_time_df.columns:
                    apc_time = matching_rows.iloc[0][col_to_create]
                    
                    if pd.isna(apc_time):
                        dt.loc[i, col_to_create] = "OFF"
                    elif apc_time >= current_data_time:
                        dt.loc[i, col_to_create] = "OFF"
                    else:
                        dt.loc[i, col_to_create] = "ON"
        
        # Create PILOT_STATUS column
        dt['PILOT_STATUS'] = dt.apply(self._create_pilot_status, axis=1)
        
        return dt
    
    def _create_pilot_status(self, row) -> str:
        """Create pilot status based on individual pilot columns"""
        # Check SRCIP first - if ON, return only "SRCIP"
        if row['SRCIP'] == "ON":
            return "SRCIP"
        
        # Otherwise, use the original logic
        if row['CCMR2'] == "OFF" and row['ICCR2'] == "OFF":
            base_status = "POR"
        elif row['CCMR2'] == "ON" and row['ICCR2'] == "OFF":
            base_status = "CCMR2"
        elif row['CCMR2'] == "OFF" and row['ICCR2'] == "ON":
            base_status = "ICCR2"
        elif row['CCMR2'] == "ON" and row['ICCR2'] == "ON":
            base_status = "CCMR2+ICCR2"
        else:
            base_status = "ERROR"
        
        # Add CV and/or GF suffixes
        cv_suffix = "+CV" if row['CV'] == "ON" else ""
        gf_suffix = "+GF" if row['GF'] == "ON" else ""
        
        return base_status + cv_suffix + gf_suffix

    def add_basic_columns(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add basic calculated columns - UPDATED to test new ColumnManager"""
        self.logger.info("Creating basic calculated columns...")
        
        # Create SUM_NCDD column
        dt['SUM_NCDD'] = pd.to_numeric(dt['BEEP_NCDD'], errors='coerce').fillna(0) + \
                        pd.to_numeric(dt['SMP_NCDD'], errors='coerce').fillna(0)
        dt['YYMM'] = pd.to_datetime(dt['INSPECT_TIME'], errors='coerce').dt.strftime('%y%m')
                        
        # NEW: Test ColumnManager for NCDD derived columns
        self.logger.info("Testing new ColumnManager for NCDD derived columns...")
        dt = ColumnManager.create_ncdd_derived_columns(dt, 'SUM_NCDD', 0.02)
        dt = ColumnManager.create_ncdd_derived_columns(dt, 'BEEP_NCDD', 0.0094, 'BEEP')
        dt = ColumnManager.create_ncdd_derived_columns(dt, 'SMP_NCDD', 0.013, 'SMP')
        
        # EXISTING: Create N_SCAN column (number of wafers scanned per LAYER+LOT combination)
        self.logger.info("Creating N_SCAN column (wafers scanned per LAYER+LOT)...")
        dt['N_SCAN'] = dt.groupby(['LAYER', 'LOT']).transform('size')
        
        # NEW: Create S_SCAN column (number of wafers scanned per LAYER+LOT+SUBENTITY combination)
        self.logger.info("Creating S_SCAN column (wafers scanned per LAYER+LOT+SUBENTITY)...")
        dt['S_SCAN'] = dt.groupby(['LAYER', 'LOT', 'SUBENTITY']).transform('size')
        
        # NEW: Create S_ORDER column (average P_ORDER per LAYER+LOT+SUBENTITY combination)
        self.logger.info("Creating S_ORDER column (average P_ORDER per LAYER+LOT+SUBENTITY)...")
        dt['S_ORDER'] = dt.groupby(['LAYER', 'LOT', 'SUBENTITY'])['P_ORDER'].transform('mean')
        
        # Show memory usage
        memory_mb = DataUtils.memory_usage_mb(dt)
        self.logger.info(f"Current dataframe memory usage: {memory_mb:.1f}MB")
        
        # Show N_SCAN and S_SCAN statistics
        self.logger.info(f"N_SCAN statistics:")
        self.logger.info(f"  Range: {dt['N_SCAN'].min()} to {dt['N_SCAN'].max()} wafers per LAYER+LOT")
        self.logger.info(f"  Mean: {dt['N_SCAN'].mean():.1f} wafers per LAYER+LOT")
        self.logger.info(f"  Unique N_SCAN values: {sorted(dt['N_SCAN'].unique())}")
        
        self.logger.info(f"S_SCAN statistics:")
        self.logger.info(f"  Range: {dt['S_SCAN'].min()} to {dt['S_SCAN'].max()} wafers per LAYER+LOT+SUBENTITY")
        self.logger.info(f"  Mean: {dt['S_SCAN'].mean():.1f} wafers per LAYER+LOT+SUBENTITY")
        self.logger.info(f"  Unique S_SCAN values: {sorted(dt['S_SCAN'].unique())}")
        
        self.logger.info(f"S_ORDER statistics:")
        self.logger.info(f"  Range: {dt['S_ORDER'].min():.1f} to {dt['S_ORDER'].max():.1f}")
        self.logger.info(f"  Mean: {dt['S_ORDER'].mean():.1f}")
        
        # Create STATUS column as categorical (existing logic)
        dt['STATUS'] = pd.Categorical(
            dt['SUM_NCDD'].apply(lambda x: 'BSL' if x < 0.02 else 'HIGHFLIER'),
            categories=['BSL', 'HIGHFLIER']
        )
        
        # Create CLASS column with three categories (existing)
        dt['CLASS'] = pd.Categorical(
            dt['SUM_NCDD'].apply(DataUtils.classify_sum_ncdd),
            categories=['ZERO', 'BSL', 'HIGHFLIER', 'UNKNOWN']
        )
        
        # Create NCDD_ZERO column (existing)
        dt['ZERO_NCDD'] = dt['SUM_NCDD'].apply(lambda x: True if x == 0 else False)
        
        # NEW: Create BEEP_NCDD derived columns (threshold = 0.0094)
        self.logger.info("Creating BEEP_NCDD derived columns (threshold = 0.0094)...")
        
        # Convert BEEP_NCDD to numeric for processing
        beep_numeric = pd.to_numeric(dt['BEEP_NCDD'], errors='coerce')
        
        # STATUS_BEEP
        dt['STATUS_BEEP'] = pd.Categorical(
            beep_numeric.apply(lambda x: 'BSL' if pd.notna(x) and x < 0.0094 else 'HIGHFLIER'),
            categories=['BSL', 'HIGHFLIER']
        )
        
        # CLASS_BEEP
        def classify_beep_ncdd(value: float) -> str:
            """Classify BEEP_NCDD values into categories"""
            if pd.isna(value):
                return 'UNKNOWN'
            elif value == 0:
                return 'ZERO'
            elif 0 < value < 0.0094:
                return 'BSL'
            else:  # value >= 0.0094
                return 'HIGHFLIER'
        
        dt['CLASS_BEEP'] = pd.Categorical(
            beep_numeric.apply(classify_beep_ncdd),
            categories=['ZERO', 'BSL', 'HIGHFLIER', 'UNKNOWN']
        )
        
        # ZERO_BEEP
        dt['ZERO_BEEP'] = beep_numeric.apply(lambda x: True if x == 0 else False)
        
        # NEW: Create SMP_NCDD derived columns (threshold = 0.013)
        self.logger.info("Creating SMP_NCDD derived columns (threshold = 0.013)...")
        
        # Convert SMP_NCDD to numeric for processing
        smp_numeric = pd.to_numeric(dt['SMP_NCDD'], errors='coerce')
        
        # STATUS_SMP
        dt['STATUS_SMP'] = pd.Categorical(
            smp_numeric.apply(lambda x: 'BSL' if pd.notna(x) and x < 0.013 else 'HIGHFLIER'),
            categories=['BSL', 'HIGHFLIER']
        )
        
        # CLASS_SMP
        def classify_smp_ncdd(value: float) -> str:
            """Classify SMP_NCDD values into categories"""
            if pd.isna(value):
                return 'UNKNOWN'
            elif value == 0:
                return 'ZERO'
            elif 0 < value < 0.013:
                return 'BSL'
            else:  # value >= 0.013
                return 'HIGHFLIER'
        
        dt['CLASS_SMP'] = pd.Categorical(
            smp_numeric.apply(classify_smp_ncdd),
            categories=['ZERO', 'BSL', 'HIGHFLIER', 'UNKNOWN']
        )
        
        # ZERO_SMP
        dt['ZERO_SMP'] = smp_numeric.apply(lambda x: True if x == 0 else False)
        
        # NEW: Create defect rate columns by LOT+LAYER+SUBENTITY
        self.logger.info("Creating defect rate columns (BP_RATE, SP_RATE, NC_RATE) by LOT+LAYER+SUBENTITY...")
        
        # BP_RATE: Proportion of False values in ZERO_BEEP (i.e., defective wafers)
        dt['BP_RATE'] = dt.groupby(['LOT', 'LAYER', 'SUBENTITY'])['ZERO_BEEP'].transform(
            lambda x: (~x).mean()  # ~x converts True->False, False->True, then mean gives proportion of originally False
        )
        
        # SP_RATE: Proportion of False values in ZERO_SMP
        dt['SP_RATE'] = dt.groupby(['LOT', 'LAYER', 'SUBENTITY'])['ZERO_SMP'].transform(
            lambda x: (~x).mean()
        )
        
        # NC_RATE: Proportion of False values in ZERO_NCDD
        dt['NC_RATE'] = dt.groupby(['LOT', 'LAYER', 'SUBENTITY'])['ZERO_NCDD'].transform(
            lambda x: (~x).mean()
        )
        
        # Show defect rate statistics
        self.logger.info(f"BP_RATE statistics (BEEP defect rate by LOT+LAYER+SUBENTITY):")
        self.logger.info(f"  Range: {dt['BP_RATE'].min():.3f} to {dt['BP_RATE'].max():.3f}")
        self.logger.info(f"  Mean: {dt['BP_RATE'].mean():.3f}")
        
        self.logger.info(f"SP_RATE statistics (SMP defect rate by LOT+LAYER+SUBENTITY):")
        self.logger.info(f"  Range: {dt['SP_RATE'].min():.3f} to {dt['SP_RATE'].max():.3f}")
        self.logger.info(f"  Mean: {dt['SP_RATE'].mean():.3f}")
        
        self.logger.info(f"NC_RATE statistics (NCDD defect rate by LOT+LAYER+SUBENTITY):")
        self.logger.info(f"  Range: {dt['NC_RATE'].min():.3f} to {dt['NC_RATE'].max():.3f}")
        self.logger.info(f"  Mean: {dt['NC_RATE'].mean():.3f}")

        # NEW: Create lot-level ZERO columns based on rate columns
        self.logger.info("Creating lot-level ZERO columns (ZERO_BEEP_LOT, ZERO_SMP_LOT, ZERO_NCDD_LOT)...")

        # ZERO_BEEP_LOT: True if BP_RATE = 0 (no BEEP defects in this LOT+LAYER+SUBENTITY group)
        dt['ZERO_BEEP_LOT'] = dt['BP_RATE'].apply(lambda x: True if x == 0 else False)

        # ZERO_SMP_LOT: True if SP_RATE = 0 (no SMP defects in this LOT+LAYER+SUBENTITY group)
        dt['ZERO_SMP_LOT'] = dt['SP_RATE'].apply(lambda x: True if x == 0 else False)

        # ZERO_NCDD_LOT: True if NC_RATE = 0 (no NCDD defects in this LOT+LAYER+SUBENTITY group)
        dt['ZERO_NCDD_LOT'] = dt['NC_RATE'].apply(lambda x: True if x == 0 else False)

        # Show lot-level ZERO statistics
        self.logger.info(f"ZERO_BEEP_LOT statistics (BP_RATE = 0):")
        beep_lot_true = dt['ZERO_BEEP_LOT'].sum()
        beep_lot_total = len(dt)
        self.logger.info(f"  True: {beep_lot_true}/{beep_lot_total} ({beep_lot_true/beep_lot_total*100:.1f}%) - no BEEP defects in LOT+LAYER+SUBENTITY")

        self.logger.info(f"ZERO_SMP_LOT statistics (SP_RATE = 0):")
        smp_lot_true = dt['ZERO_SMP_LOT'].sum()
        self.logger.info(f"  True: {smp_lot_true}/{beep_lot_total} ({smp_lot_true/beep_lot_total*100:.1f}%) - no SMP defects in LOT+LAYER+SUBENTITY")

        self.logger.info(f"ZERO_NCDD_LOT statistics (NC_RATE = 0):")
        ncdd_lot_true = dt['ZERO_NCDD_LOT'].sum()
        self.logger.info(f"  True: {ncdd_lot_true}/{beep_lot_total} ({ncdd_lot_true/beep_lot_total*100:.1f}%) - no NCDD defects in LOT+LAYER+SUBENTITY")
        
        return dt
    
    def add_recoat_status(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add recoat status columns"""
        if not self.config.ENABLE_RECOAT:
            self.logger.info("RECOAT processing is DISABLED - skipping")
            return dt
        
        self.logger.info("Loading parts info and adding RECOAT status columns...")
        
        parts_df = self.safe_load_csv(self.config.PARTS_PATH)
        if parts_df is None:
            self.logger.error("Failed to load parts data")
            return dt
        
        self.logger.info(f"Parts DataFrame shape: {parts_df.shape}")
        
        # Convert date columns to datetime
        parts_df = DataUtils.safe_datetime_convert(parts_df, 'PART_INSTALL_DATE')
        parts_df = DataUtils.safe_datetime_convert(parts_df, 'PART_REMOVE_DATE')
        
        # Initialize RECOAT status columns
        for part_type in self.config.PART_TYPES:
            dt[part_type] = 'NOTFOUND'
        
        # Process each row to determine RECOAT status
        self._process_recoat_status(dt, parts_df)
        
        # Create final RECOAT column
        dt['RECOAT'] = dt.apply(self._determine_final_recoat, axis=1)
        
        # Show summary
        self._show_recoat_summary(dt)
        
        return dt
    
    def _get_recoat_status_by_part(self, subentity: str, subentity_end_time, part_type: str, 
                                   parts_df: pd.DataFrame, debug: bool = False) -> str:
        """Get RECOAT status for a specific PART type"""
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                self.logger.debug(f"Missing subentity or time: {subentity}, {subentity_end_time}")
            return 'NOTFOUND'
        
        # Filter parts data for this subentity and PART type
        entity_parts = parts_df[
            (parts_df['ENTITY'] == subentity) & 
            (parts_df['PART'] == part_type)
        ].copy()
        
        if debug:
            self.logger.debug(f"Entity parts found for {part_type}: {len(entity_parts)}")
        
        if entity_parts.empty:
            return 'NOTFOUND'
        
        matching_parts = []
        
        # Check currently installed parts first
        currently_installed = entity_parts[
            (entity_parts['CURRENTLY_INSTALLED'] == True) | 
            (entity_parts['CURRENTLY_INSTALLED'] == 'TRUE') |
            (entity_parts['CURRENTLY_INSTALLED'] == 'True')
        ]
        
        for _, part in currently_installed.iterrows():
            if pd.notna(part['PART_INSTALL_DATE']) and subentity_end_time > part['PART_INSTALL_DATE']:
                matching_parts.append(part)
        
        # Check previously installed parts
        previously_installed = entity_parts[
            (entity_parts['CURRENTLY_INSTALLED'] == False) | 
            (entity_parts['CURRENTLY_INSTALLED'] == 'FALSE') |
            (entity_parts['CURRENTLY_INSTALLED'] == 'False')
        ]
        
        for _, part in previously_installed.iterrows():
            if (pd.notna(part['PART_INSTALL_DATE']) and 
                pd.notna(part['PART_REMOVE_DATE']) and
                part['PART_INSTALL_DATE'] < subentity_end_time < part['PART_REMOVE_DATE']):
                matching_parts.append(part)
        
        if len(matching_parts) == 0:
            return 'NOTFOUND'
        elif len(matching_parts) == 1:
            # Special handling for LID - return INSTALL_COUNT instead of RECOAT
            if part_type == 'LID':
                install_count = matching_parts[0]['INSTALL_COUNT']
                return install_count if pd.notna(install_count) else 'MISSING'
            
            # Original logic for all other part types
            recoat_val = str(matching_parts[0]['RECOAT'])
            if recoat_val.upper() == 'TRUE':
                return 'True'
            elif recoat_val.upper() == 'FALSE':
                return 'False'
            else:
                return recoat_val
        else:
            # Special handling for LID - return most recent INSTALL_COUNT
            if part_type == 'LID':
                most_recent_part = max(matching_parts, key=lambda x: x['PART_INSTALL_DATE'] if pd.notna(x['PART_INSTALL_DATE']) else pd.Timestamp.min)
                install_count = most_recent_part['INSTALL_COUNT']
                return install_count if pd.notna(install_count) else 'MISSING'
            
            # Original logic for all other part types
            recoat_values = [part['RECOAT'] for part in matching_parts]
            
            if any(str(val).upper() == 'TRUE' for val in recoat_values):
                return 'True'
            elif any(str(val).upper() == 'MISSING' for val in recoat_values):
                return 'MISSING'
            elif all(str(val).upper() == 'FALSE' for val in recoat_values):
                return 'False'
            else:
                return 'MULTIPLE'
    
    def _process_recoat_status(self, dt: pd.DataFrame, parts_df: pd.DataFrame):
        """Process RECOAT status for each defect scan"""
        self.logger.info("Processing RECOAT status for each defect scan...")
        
        for idx in dt.index:
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            for part_type in self.config.PART_TYPES:
                recoat_status = self._get_recoat_status_by_part(
                    subentity, subentity_end_time, part_type, parts_df, debug=False
                )
                dt.at[idx, part_type] = recoat_status
    
    def _determine_final_recoat(self, row) -> bool:
        """Determine final RECOAT status"""
        recoat_values = [row[part_type] for part_type in self.config.PART_TYPES]
        return any(str(val).upper() == 'TRUE' for val in recoat_values)
    
    def _show_recoat_summary(self, dt: pd.DataFrame):
        """Show RECOAT processing summary"""
        self.logger.info(f"\nRECOAT Summary:")
        self.logger.info(f"Final RECOAT column: {dt['RECOAT'].value_counts()}")
        for part_type in self.config.PART_TYPES:
            self.logger.info(f"{part_type}: {dt[part_type].value_counts().to_dict()}")
    
    def _finalize_dataframe(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Finalize dataframe with proper column ordering and sorting"""
        # Sort by SUBENTITY_END_TIME with most recent first
        dt = dt.sort_values('SUBENTITY_END_TIME', ascending=False)
        
        # Define desired column order
        elwc_lookback_cols = []
        if self.config.ENABLE_ELWC:
            elwc_lookback_cols = [f'{group}_{window}HRS' 
                                 for group in self.config.RECIPE_GROUPS
                                 for window in self.config.TIME_WINDOWS]
        
        # ELWC2 columns
        elwc2_cols = []
        if self.config.ENABLE_ELWC2:
            for days in self.config.ELWC2_LOOKBACKS:
                days_str = f"{days:02d}"
                elwc2_cols.extend([
                    f'CH_{days_str}_NWAF', f'FL_{days_str}_NWAF',
                    f'CH_{days_str}_AWAF', f'FL_{days_str}_AWAF'
                ])
        
        leak_by_cols = []
        if self.config.ENABLE_LEAK_BY:
            leak_by_cols = [f'LB_{gas}' for gas in self.config.LEAK_BY_GASES]
        
        # SPC Monitor columns (raw, MA3, MA6, MA9)
        spc_monitor_cols = []
        if self.config.ENABLE_SPC_MONITOR:
            for monitor_type in self.config.SPC_MONITOR_TYPES:
                spc_monitor_cols.extend([monitor_type, f'{monitor_type}_MA3', f'{monitor_type}_MA6', f'{monitor_type}_MA9'])
        
        # Defect trends columns
        defect_trends_cols = []
        if self.config.ENABLE_DEFECT_TRENDS:
            # Chamber trends
            for days in self.config.TREND_LOOKBACK_DAYS:
                days_str = f"{days:02d}"
                defect_trends_cols.extend([
                    f'CH_BP_{days_str}_RATE', f'CH_SP_{days_str}_RATE', f'CH_{days_str}_RATE',
                    f'CH_BP_{days_str}', f'CH_SP_{days_str}', f'CH_{days_str}', f'CH_{days_str}_MWAF'
                ])
            # Fleet trends
            for days in self.config.TREND_LOOKBACK_DAYS:
                days_str = f"{days:02d}"
                defect_trends_cols.extend([
                    f'FL_BP_{days_str}_RATE', f'FL_SP_{days_str}_RATE', f'FL_{days_str}_RATE',
                    f'FL_BP_{days_str}', f'FL_SP_{days_str}', f'FL_{days_str}', f'FL_{days_str}_MWAF'
                ])
            # Chamber-to-Fleet ratios
            for days in self.config.TREND_LOOKBACK_DAYS:
                days_str = f"{days:02d}"
                defect_trends_cols.extend([
                    f'CF_BP_{days_str}_RRAT', f'CF_SP_{days_str}_RRAT', f'CF_{days_str}_RRAT',
                    f'CF_BP_{days_str}_DRAT', f'CF_SP_{days_str}_DRAT', f'CF_{days_str}_DRAT'
                ])
        
        # Base columns - UPDATED to include N_SCAN and new stepper and SIF columns
        desired_order = [
            'YYMM',
            'LOT', 'WAFER_ID', 'PRODUCT', 'ROUTE', 'LAYER', 'DEVICE', 'SUBENTITY', 'OPERATION','RECIPE', 
            'SUBENTITY_END_TIME','PILOT_STATUS', 
            'N_SCAN', 'S_SCAN', 'S_ORDER',  # NEW: Added S_SCAN and S_ORDER
            'SUM_NCDD', 'STATUS', 'CLASS',  'ZERO_NCDD', 'ZERO_NCDD_LOT', 'NC_RATE',  # NEW: Added NC_RATE
            'INSPECT_TIME', 'INSPECT_TOOL', 
            'BEEP_NCDD', 'STATUS_BEEP', 'CLASS_BEEP', 'ZERO_BEEP', 'ZERO_BEEP_LOT', 'BP_RATE',  # NEW: Added BP_RATE
            'SMP_NCDD', 'STATUS_SMP', 'CLASS_SMP', 'ZERO_SMP', 'ZERO_SMP_LOT', 'SP_RATE',      # NEW: Added SP_RATE
            'STEPPER', 'RETICLE', 'SIF_SED', 'SIF_ETCH', 'SIF_DEFECT',
            'ENTITY', 'LOT7', 'WAFER', 'SLOT', 'P_ORDER',
            'CCMR2', 'ICCR2', 'GF', 'CV', 'SRCIP', 'TS', 'FULLPM', 'FULLPM_RF', 'MINIPM', 'MINIPM_RF', 
            'CNTR_SS', 'PL_RECIPE', 'PT_BTWN', 'PL_TIME', 'UPT_12HRS', 'UNW_12HRS', 'UP_12HRS'
        ]
        
        # Add optional columns based on enabled processors
        if self.config.ENABLE_RECOAT:
            desired_order.extend(self.config.PART_TYPES + ['RECOAT'])
        
        if self.config.ENABLE_LEAK_RATE:
            desired_order.extend(['RAW_LEAK_RATE', 'SMOOTH_LEAK_RATE'])
        
        if self.config.ENABLE_DRY_PUMP:
            desired_order.append('DP_FAIL_HRS')
        
        # Add processor-specific columns in logical order
        desired_order.extend(leak_by_cols + spc_monitor_cols + defect_trends_cols + elwc2_cols + elwc_lookback_cols)
        
        # Reorder columns
        existing_priority_cols = [col for col in desired_order if col in dt.columns]
        remaining_cols = [col for col in dt.columns if col not in desired_order]
        dt = dt[existing_priority_cols + remaining_cols]
        
        return dt
    
    def create_lot_level_output(self, df):
        """
        Create lot-level CSV grouped by LAYER, LOT, SUBENTITY.
        Selects row with most recent SUBENTITY_END_TIME per group.
        """
        print("Creating lot-level output...")
        
        try:
            # Ensure SUBENTITY_END_TIME is datetime
            if 'SUBENTITY_END_TIME' not in df.columns:
                print("Warning: SUBENTITY_END_TIME column not found. Using index for selection.")
                # Fallback: use the last row per group
                lot_df = df.groupby(['LAYER', 'LOT', 'SUBENTITY']).tail(1).reset_index(drop=True)
            else:
                # Convert to datetime if not already
                df['SUBENTITY_END_TIME'] = pd.to_datetime(df['SUBENTITY_END_TIME'])
                
                # Sort by grouping columns and timestamp (most recent first)
                df_sorted = df.sort_values(['LAYER', 'LOT', 'SUBENTITY', 'SUBENTITY_END_TIME'], 
                                        ascending=[True, True, True, False])
                
                # Take first row (most recent) per group
                lot_df = df_sorted.groupby(['LAYER', 'LOT', 'SUBENTITY']).first().reset_index()
            
            print(f"Lot-level data: {len(lot_df):,} rows from {len(df):,} wafer-level rows")
            print(f"Grouping summary:")
            print(f"  - Unique layers: {lot_df['LAYER'].nunique()}")
            print(f"  - Unique lots: {lot_df['LOT'].nunique()}")
            print(f"  - Unique subentities: {lot_df['SUBENTITY'].nunique()}")
            
            # Export to CSV
            lot_df.to_csv(self.config.LOT_LEVEL_OUTPUT_PATH, index=False)
            print(f"Lot-level CSV saved to: {self.config.LOT_LEVEL_OUTPUT_PATH}")
            
            return lot_df
            
        except Exception as e:
            print(f"Error creating lot-level output: {e}")
            return None


    def process(self) -> pd.DataFrame:
        """Main processing pipeline with selective processor execution"""
        try:
            # Load and process base data (always required)
            dt = self.load_base_data()
            dt = self.clean_and_rename_columns(dt)
            dt = self.add_pilot_status(dt)
            dt = self.add_basic_columns(dt)
            dt = self.add_recoat_status(dt)
            
            # Add external data sources (conditionally based on config)
            if self.config.ENABLE_DEFECT_TRENDS and self.trends_processor:
                dt = self.trends_processor.process(dt)

            if self.config.ENABLE_LEAK_RATE and self.leak_processor:
                dt = self.leak_processor.add_leak_rate_data(dt)
            else:
                self.logger.info("Leak rate processing SKIPPED")
            
            if self.config.ENABLE_DRY_PUMP and self.dp_processor:
                dt = self.dp_processor.add_dp_fail_data(dt)
            else:
                self.logger.info("Dry pump processing SKIPPED")
            
            if self.config.ENABLE_LEAK_BY and self.leak_by_processor:
                dt = self.leak_by_processor.add_leak_by_data(dt)
            else:
                self.logger.info("Leak by processing SKIPPED")
            
            if self.config.ENABLE_SPC_MONITOR and self.spc_monitor_processor:
                dt = self.spc_monitor_processor.add_spc_monitor_data(dt)
            else:
                self.logger.info("SPC monitor processing SKIPPED")
            
            if self.config.ENABLE_ELWC2 and self.elwc2_processor:
                dt = self.elwc2_processor.add_elwc2_lookbacks(dt)
            else:
                self.logger.info("ELWC2 production utilization processing SKIPPED")
            
            if self.config.ENABLE_ELWC and self.elwc_processor:
                dt = self.elwc_processor.add_elwc_lookbacks_optimized(dt)
            else:
                self.logger.info("ELWC lookback processing SKIPPED")
            
            # Finalize
            dt = self._finalize_dataframe(dt)
            
            self.logger.info("Processing complete!")
            self.logger.info(f"Final dataframe shape: {dt.shape}")

             # NEW: Create lot-level output if enabled
            if self.config.ENABLE_LOT_LEVEL_OUTPUT:
                lot_level_df = self.create_lot_level_output(dt)
            
            return dt
            
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise


def main():
    """Main execution function with proper error handling"""
    try:
        # Install tqdm if not already available
        try:
            from tqdm import tqdm
        except ImportError:
            print("Installing tqdm for progress bars...")
            import subprocess
            subprocess.check_call(["pip", "install", "tqdm"])
        
        # Initialize configuration with selective processor control
        config = Config(
            # Override date filtering settings
            ENABLE_DATE_FILTER=True,
            START_DATE="2025-11-01",
            END_DATE="2025-12-01",
            
            # Enable/disable processors as needed for faster iteration
            ENABLE_ELWC=True,           # Set to False to skip ELWC processing during development
            ENABLE_ELWC2=True,          # NEW: Enable ELWC2 production utilization
            ENABLE_LEAK_RATE=True,
            ENABLE_DRY_PUMP=True,
            ENABLE_LEAK_BY=True,
            ENABLE_SPC_MONITOR=True,
            ENABLE_DEFECT_TRENDS=True,
            ENABLE_RECOAT=True,
            
            # Optional: Override output path (NEW!)
            OUTPUT_PATH=r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_2025.csv"

        )
        
        # Process data
        processor = DefectDataProcessor(config)
        result_df = processor.process()
        
        # Save results
        result_df.to_csv(config.OUTPUT_PATH, index=False)
        logging.info(f"Processed data saved to: {config.OUTPUT_PATH}")
        
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

        # Show lot-level ZERO column summaries
        lot_zero_cols = ['ZERO_BEEP_LOT', 'ZERO_SMP_LOT', 'ZERO_NCDD_LOT']
        existing_lot_zero_cols = [col for col in lot_zero_cols if col in result_df.columns]
        if existing_lot_zero_cols:
            logging.info(f"\nLot-level ZERO columns summary:")
            for col in existing_lot_zero_cols:
                true_count = result_df[col].sum()
                total_count = len(result_df)
                logging.info(f"{col}: {true_count}/{total_count} ({true_count/total_count*100:.1f}%) have zero defect rate in LOT+LAYER+SUBENTITY")
                
        # Show defect rate column summaries
        rate_cols = ['BP_RATE', 'SP_RATE', 'NC_RATE']
        existing_rate_cols = [col for col in rate_cols if col in result_df.columns]
        if existing_rate_cols:
            logging.info(f"\nDefect rate column summaries:")
            for col in existing_rate_cols:
                rate_stats = result_df[col].describe()
                logging.info(f"{col} statistics: {rate_stats}")
                
                # Show some examples of high defect rates
                high_rates = result_df[result_df[col] > 0.5][['LOT', 'LAYER', 'SUBENTITY', col, 'S_SCAN']].drop_duplicates()
                if not high_rates.empty:
                    logging.info(f"{col} > 0.5 examples:")
                    logging.info(f"{high_rates.head()}")

        # Show ROUTE column summary
        if 'ROUTE' in result_df.columns:
            logging.info(f"\nROUTE column distribution:")
            route_counts = result_df['ROUTE'].value_counts().head(10)
            logging.info(f"{route_counts}")

        # Show S_SCAN and S_ORDER column summaries
        if 'S_SCAN' in result_df.columns:
            logging.info(f"\nS_SCAN column summary:")
            s_scan_stats = result_df['S_SCAN'].describe()
            logging.info(f"S_SCAN statistics: {s_scan_stats}")
            s_scan_counts = result_df['S_SCAN'].value_counts().sort_index()
            logging.info(f"S_SCAN distribution: {s_scan_counts.to_dict()}")

        if 'S_ORDER' in result_df.columns:
            logging.info(f"\nS_ORDER column summary:")
            s_order_stats = result_df['S_ORDER'].describe()
            logging.info(f"S_ORDER statistics: {s_order_stats}")
        
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
                
        # Add this after the existing summaries in main():
        # Show N_SCAN column summary
        if 'N_SCAN' in result_df.columns:
            logging.info(f"\nN_SCAN column summary:")
            n_scan_stats = result_df['N_SCAN'].describe()
            logging.info(f"N_SCAN statistics: {n_scan_stats}")
            n_scan_counts = result_df['N_SCAN'].value_counts().sort_index()
            logging.info(f"N_SCAN distribution: {n_scan_counts.to_dict()}")
        
        # NEW: Show ELWC2 column summaries
        if config.ENABLE_ELWC2:
            elwc2_cols = [col for col in result_df.columns if any(pattern in col for pattern in ['_NWAF', '_AWAF'])]
            if elwc2_cols:
                logging.info(f"\nELWC2 column summaries (first few columns):")
                sample_elwc2_cols = elwc2_cols[:8]  # Show first 8 ELWC2 columns
                for col in sample_elwc2_cols:
                    non_null_count = result_df[col].notna().sum()
                    total_count = len(result_df)
                    if non_null_count > 0:
                        mean_val = result_df[col].mean()
                        logging.info(f"{col}: {non_null_count}/{total_count} ({non_null_count/total_count*100:.1f}%) non-null, mean={mean_val:.1f}")
                    else:
                        logging.info(f"{col}: {non_null_count}/{total_count} ({non_null_count/total_count*100:.1f}%) non-null")
        
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