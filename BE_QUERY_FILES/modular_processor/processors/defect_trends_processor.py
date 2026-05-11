# -*- coding: utf-8 -*-
"""
Defect Trends Processor
Adds historical defect rate trend columns based on lookback windows
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import List, Tuple

from core.base_processors import ProcessorBase

logger = logging.getLogger(__name__)

class DefectTrendsProcessor(ProcessorBase):
    """
    Processor for adding defect trend columns based on historical lookback windows
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.lookback_days = config.TREND_LOOKBACK_DAYS
        self.defect_cols = config.TREND_DEFECT_COLS
        self.time_col = config.TREND_TIME_COL
        self.layer_col = config.TREND_LAYER_COL
        self.lot_col = config.TREND_LOT_COL
        self.device_col = 'DEVICE'
        
        # SIMPLE 3-CONFIG CONTROL FOR ALL DEFECT TYPES
        self.defect_type_controls = {
            'ZERO_BEEP': getattr(config, 'TREND_ENABLE_BEEP', True),
            'ZERO_SMP': getattr(config, 'TREND_ENABLE_SMP', True), 
            'ZERO_NCDD': getattr(config, 'TREND_ENABLE_NCDD', True)
        }
        
        # Generate column mappings and all trend columns
        self.column_mapping = self._get_column_mappings()
        self.all_trend_columns = self._generate_all_trend_columns()
        
        logger.info(f"DefectTrendsProcessor initialized:")
        logger.info(f"  Lookback days: {self.lookback_days}")
        logger.info(f"  Defect columns: {self.defect_cols}")
        logger.info(f"  Device column: {self.device_col}")
        logger.info(f"  Defect type controls: {self.defect_type_controls}")
        logger.info(f"  Column mapping: {self.column_mapping}")
        logger.info(f"  Total trend columns to create: {len(self.all_trend_columns)}")

    def _get_column_mappings(self):
        """
        Create mapping from config defect columns to short names for column generation
        """
        default_mapping = {
            'ZERO_NCDD': 'NC',    # Combined defects
            'ZERO_BEEP': 'BP',    # Beep defects  
            'ZERO_SMP': 'SP'      # Small particle defects
        }
        
        column_mapping = {}
        for col in self.defect_cols:
            if col in default_mapping:
                column_mapping[col] = default_mapping[col]
            else:
                # For new defect types, derive from column name
                suffix = col.replace('ZERO_', '')
                short_name = ''.join([word[0] for word in suffix.split('_')])[:2].upper()
                column_mapping[col] = short_name
                
        return column_mapping

    def _generate_all_trend_columns(self):
        """
        Generate all trend column names based on simple defect type controls
        """
        all_columns = []
        
        for days in self.lookback_days:
            for defect_col in self.defect_cols:
                # Skip this defect type if disabled
                if not self.defect_type_controls.get(defect_col, True):
                    continue
                    
                short_name = self.column_mapping[defect_col]
                
                # Fleet columns (layer-level)
                all_columns.extend([
                    f"FL_{short_name}_{days:02d}_RATE",
                    f"FL_{short_name}_{days:02d}",
                ])
                
                # Device columns (layer + device level)
                all_columns.extend([
                    f"FL_{short_name}_{days:02d}_RATE_DEV",
                    f"FL_{short_name}_{days:02d}_DEV",
                ])
                
                # Chamber columns
                all_columns.extend([
                    f"CH_{short_name}_{days:02d}_RATE",
                    f"CH_{short_name}_{days:02d}",
                ])
            
            # MWAF columns (always included if any defect types are enabled)
            if any(self.defect_type_controls.values()):
                all_columns.extend([
                    f"FL_{days:02d}_MWAF",
                    f"FL_{days:02d}_MWAF_DEV",
                    f"CH_{days:02d}_MWAF"
                ])
        
        return all_columns
        
    def _initialize_trend_columns(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Initialize all trend columns with NaN values"""
        for col_name in self.all_trend_columns:
            df[col_name] = np.nan
        
        logger.info(f"Initialized {len(self.all_trend_columns)} trend columns")
        return df, self.all_trend_columns
        
    def _calculate_fleet_trends(self, df: pd.DataFrame, layer: str, current_lot: str, 
                            current_time: datetime, days: int) -> dict:
        """Calculate fleet-wide trends for a specific lot and lookback period"""
        layer_df = df[df[self.layer_col] == layer]
        
        # Standard lookback window
        lookback_start = current_time - timedelta(days=days)
        lookback_mask = (
            (layer_df[self.time_col] >= lookback_start) & 
            (layer_df[self.time_col] < current_time)
        )
        lookback_data = layer_df[lookback_mask]
        
        results = {}
        
        if len(lookback_data) > 0:
            total_wafers = len(lookback_data)
            results[f"FL_{days:02d}_MWAF"] = total_wafers
            
            # Calculate for each enabled defect type
            for defect_col in self.defect_cols:
                if (defect_col in lookback_data.columns and 
                    self.defect_type_controls.get(defect_col, True)):
                    
                    short_name = self.column_mapping[defect_col]
                    defective_count = (~lookback_data[defect_col]).sum()
                    defect_rate = defective_count / total_wafers
                    
                    results[f"FL_{short_name}_{days:02d}_RATE"] = defect_rate
                    results[f"FL_{short_name}_{days:02d}"] = defective_count
        else:
            # No data available
            results[f"FL_{days:02d}_MWAF"] = 0
            for defect_col in self.defect_cols:
                if self.defect_type_controls.get(defect_col, True):
                    short_name = self.column_mapping[defect_col]
                    results[f"FL_{short_name}_{days:02d}_RATE"] = np.nan
                    results[f"FL_{short_name}_{days:02d}"] = 0
        
        return results

    def _calculate_device_trends(self, df: pd.DataFrame, layer: str, device: str,
                               current_lot: str, current_time: datetime, days: int) -> dict:
        """Calculate device-specific trends for a specific lot and lookback period"""
        device_df = df[(df[self.layer_col] == layer) & (df[self.device_col] == device)]
        
        # Standard lookback window
        lookback_start = current_time - timedelta(days=days)
        lookback_mask = (
            (device_df[self.time_col] >= lookback_start) & 
            (device_df[self.time_col] < current_time)
        )
        lookback_data = device_df[lookback_mask]
        
        results = {}
        
        if len(lookback_data) > 0:
            total_wafers = len(lookback_data)
            results[f"FL_{days:02d}_MWAF_DEV"] = total_wafers
            
            # Calculate for each enabled defect type
            for defect_col in self.defect_cols:
                if (defect_col in lookback_data.columns and 
                    self.defect_type_controls.get(defect_col, True)):
                    
                    short_name = self.column_mapping[defect_col]
                    defective_count = (~lookback_data[defect_col]).sum()
                    defect_rate = defective_count / total_wafers
                    
                    results[f"FL_{short_name}_{days:02d}_RATE_DEV"] = defect_rate
                    results[f"FL_{short_name}_{days:02d}_DEV"] = defective_count
        else:
            # No data available
            results[f"FL_{days:02d}_MWAF_DEV"] = 0
            for defect_col in self.defect_cols:
                if self.defect_type_controls.get(defect_col, True):
                    short_name = self.column_mapping[defect_col]
                    results[f"FL_{short_name}_{days:02d}_RATE_DEV"] = np.nan
                    results[f"FL_{short_name}_{days:02d}_DEV"] = 0
        
        return results

    def _calculate_chamber_trends(self, df: pd.DataFrame, layer: str, chamber: str,
                                current_lot: str, current_time: datetime, days: int) -> dict:
        """Calculate chamber-specific trends for a specific lot and lookback period"""
        chamber_df = df[(df[self.layer_col] == layer) & (df['SUBENTITY'] == chamber)]
        
        # Standard lookback window
        lookback_start = current_time - timedelta(days=days)
        lookback_mask = (
            (chamber_df[self.time_col] >= lookback_start) & 
            (chamber_df[self.time_col] < current_time)
        )
        lookback_data = chamber_df[lookback_mask]
        
        results = {}
        
        if len(lookback_data) > 0:
            total_wafers = len(lookback_data)
            results[f"CH_{days:02d}_MWAF"] = total_wafers
            
            # Calculate for each enabled defect type
            for defect_col in self.defect_cols:
                if (defect_col in lookback_data.columns and 
                    self.defect_type_controls.get(defect_col, True)):
                    
                    short_name = self.column_mapping[defect_col]
                    defective_count = (~lookback_data[defect_col]).sum()
                    defect_rate = defective_count / total_wafers
                    
                    results[f"CH_{short_name}_{days:02d}_RATE"] = defect_rate
                    results[f"CH_{short_name}_{days:02d}"] = defective_count
        else:
            # No data available
            results[f"CH_{days:02d}_MWAF"] = 0
            for defect_col in self.defect_cols:
                if self.defect_type_controls.get(defect_col, True):
                    short_name = self.column_mapping[defect_col]
                    results[f"CH_{short_name}_{days:02d}_RATE"] = np.nan
                    results[f"CH_{short_name}_{days:02d}"] = 0
        
        return results
    
    def _process_layer_trends(self, df: pd.DataFrame, layer: str) -> pd.DataFrame:
        """Process trends for a specific layer"""
        logger.info(f"Processing trends for layer: {layer}")
        
        layer_mask = df[self.layer_col] == layer
        layer_df = df[layer_mask].copy()
        
        # Get unique lot-chamber combinations with their inspect times and devices
        lot_chamber_info = layer_df.groupby([self.lot_col, 'SUBENTITY']).agg({
            self.time_col: 'first',
            self.device_col: 'first'
        }).sort_values(self.time_col)
        
        # Process each lot-chamber combination
        for lot_chamber_idx, ((current_lot, current_chamber), lot_data) in enumerate(lot_chamber_info.iterrows()):
            if lot_chamber_idx % 10 == 0:
                logger.debug(f"  Processing lot-chamber {lot_chamber_idx+1}/{len(lot_chamber_info)}: {current_lot}-{current_chamber}")
            
            current_time = lot_data[self.time_col]
            current_device = lot_data[self.device_col]
            
            # Create mask for current lot AND chamber combination
            current_lot_chamber_mask = (
                (df[self.layer_col] == layer) & 
                (df[self.lot_col] == current_lot) & 
                (df['SUBENTITY'] == current_chamber)
            )
            
            # For each lookback window
            for days in self.lookback_days:
                # Calculate fleet trends (layer-level)
                fleet_results = self._calculate_fleet_trends(
                    df, layer, current_lot, current_time, days
                )
                
                # Calculate device trends (layer + device level)
                device_results = self._calculate_device_trends(
                    df, layer, current_device, current_lot, current_time, days
                )
                
                # Calculate chamber trends
                chamber_results = self._calculate_chamber_trends(
                    df, layer, current_chamber, current_lot, current_time, days
                )
                
                # Assign results to wafers in current lot-chamber combination
                all_results = {**fleet_results, **device_results, **chamber_results}
                for col_name, value in all_results.items():
                    df.loc[current_lot_chamber_mask, col_name] = value
        
        return df
        
    def _validate_trend_results(self, df: pd.DataFrame, trend_columns: List[str]) -> bool:
        """Validate the trend calculations"""
        logger.info("Validating trend calculations...")
        
        # Check for expected columns
        missing_trend_cols = [col for col in trend_columns if col not in df.columns]
        if missing_trend_cols:
            logger.error(f"❌ Missing trend columns: {missing_trend_cols}")
            return False
        else:
            logger.info("✅ All expected trend columns present")
        
        # Separate columns by type for different validation
        rate_cols = [col for col in trend_columns if col.endswith('_RATE') or col.endswith('_RATE_DEV')]
        count_cols = [col for col in trend_columns if not col.endswith('_RATE') and not col.endswith('_RATE_DEV') and not col.endswith('_MWAF') and not col.endswith('_MWAF_DEV')]
        mwaf_cols = [col for col in trend_columns if col.endswith('_MWAF') or col.endswith('_MWAF_DEV')]
        
        # Check data coverage
        logger.info("Data Coverage:")
        for col_type, cols in [("Rate", rate_cols), ("Count", count_cols), ("MWAF", mwaf_cols)]:
            if cols:
                avg_coverage = np.mean([df[col].notna().sum() / len(df) * 100 for col in cols])
                logger.info(f"  {col_type} columns: {avg_coverage:.1f}% average coverage")
        
        # Check value ranges for sample columns
        logger.info("Value Range Check:")
        
        # Rate columns should be between 0 and 1
        for col in rate_cols[:5]:
            values = df[col].dropna()
            if len(values) > 0:
                min_val, max_val = values.min(), values.max()
                logger.info(f"  {col}: min={min_val:.4f}, max={max_val:.4f}")
                if min_val < 0 or max_val > 1:
                    logger.warning(f"    ⚠️  Warning: Rate values outside expected range [0,1]")
        
        # Count columns should be non-negative integers
        for col in count_cols[:5]:
            values = df[col].dropna()
            if len(values) > 0:
                min_val, max_val = values.min(), values.max()
                logger.info(f"  {col}: min={min_val}, max={max_val}")
                if min_val < 0:
                    logger.warning(f"    ⚠️  Warning: Count values should be non-negative")
        
        # MWAF columns should be positive integers
        for col in mwaf_cols[:3]:
            values = df[col].dropna()
            if len(values) > 0:
                min_val, max_val = values.min(), values.max()
                logger.info(f"  {col}: min={min_val}, max={max_val}")

        return True

    def _add_chamber_fleet_ratios(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add chamber-to-fleet ratio columns for rates and counts
        """
        logger.info("Adding chamber-to-fleet ratio columns...")
        
        ratio_columns = []
        
        for days in self.lookback_days:
            for defect_col in self.defect_cols:
                # Skip if this defect type is disabled
                if not self.defect_type_controls.get(defect_col, True):
                    continue
                    
                short_name = self.column_mapping[defect_col]
                
                ch_rate_col = f"CH_{short_name}_{days:02d}_RATE"
                fl_rate_col = f"FL_{short_name}_{days:02d}_RATE"
                ch_count_col = f"CH_{short_name}_{days:02d}"
                fl_count_col = f"FL_{short_name}_{days:02d}"
                
                rate_ratio_col = f"CF_{short_name}_{days:02d}_RRAT"
                count_ratio_col = f"CF_{short_name}_{days:02d}_DRAT"
                
                # Calculate rate ratios (CH_RATE / FL_RATE)
                if ch_rate_col in df.columns and fl_rate_col in df.columns:
                    df[rate_ratio_col] = np.where(
                        df[fl_rate_col] == 0,
                        0,
                        df[ch_rate_col] / df[fl_rate_col]
                    )
                    ratio_columns.append(rate_ratio_col)
                
                # Calculate count ratios (CH_COUNT / FL_COUNT)  
                if ch_count_col in df.columns and fl_count_col in df.columns:
                    df[count_ratio_col] = np.where(
                        df[fl_count_col] == 0,
                        0,
                        df[ch_count_col] / df[fl_count_col]
                    )
                    ratio_columns.append(count_ratio_col)
        
        logger.info(f"Added {len(ratio_columns)} chamber-to-fleet ratio columns")
        
        # Log sample values for validation
        logger.info("Sample ratio values:")
        for col in ratio_columns[:6]:
            non_null_data = df[col].dropna()
            if len(non_null_data) > 0:
                sample_stats = {
                    'min': non_null_data.min(),
                    'max': non_null_data.max(), 
                    'mean': non_null_data.mean()
                }
                logger.info(f"  {col}: min={sample_stats['min']:.3f}, max={sample_stats['max']:.3f}, mean={sample_stats['mean']:.3f}")
        
        return df, ratio_columns
    
    def _get_ordered_trend_columns_with_ratios(self, all_columns):
        """
        Generate trend columns in desired order including ratios:
        CH → FL → FL_DEV → CF, Period-grouped, RATE → Count → MWAF → Ratios
        """
        ordered_columns = []
        
        scope_order = ['CH', 'FL', 'FL_DEV', 'CF']
        # Only include enabled defect types in ordering
        enabled_defect_types = [self.column_mapping[dt] for dt in self.defect_cols 
                               if self.defect_type_controls.get(dt, True)]
        defect_order = sorted(enabled_defect_types)
        
        for scope in scope_order:
            for days in self.lookback_days:
                if scope == 'CH':
                    # Chamber columns
                    # RATE columns
                    for defect_type in defect_order:
                        col_name = f"CH_{defect_type}_{days:02d}_RATE"
                        if col_name in all_columns:
                            ordered_columns.append(col_name)
                    
                    # Count columns
                    for defect_type in defect_order:
                        col_name = f"CH_{defect_type}_{days:02d}"
                        if col_name in all_columns:
                            ordered_columns.append(col_name)
                    
                    # MWAF columns
                    mwaf_col = f"CH_{days:02d}_MWAF"
                    if mwaf_col in all_columns:
                        ordered_columns.append(mwaf_col)
                
                elif scope == 'FL':
                    # Fleet columns
                    # RATE columns
                    for defect_type in defect_order:
                        col_name = f"FL_{defect_type}_{days:02d}_RATE"
                        if col_name in all_columns:
                            ordered_columns.append(col_name)
                    
                    # Count columns
                    for defect_type in defect_order:
                        col_name = f"FL_{defect_type}_{days:02d}"
                        if col_name in all_columns:
                            ordered_columns.append(col_name)
                    
                    # MWAF columns
                    mwaf_col = f"FL_{days:02d}_MWAF"
                    if mwaf_col in all_columns:
                        ordered_columns.append(mwaf_col)
                
                elif scope == 'FL_DEV':
                    # Device columns
                    # RATE columns
                    for defect_type in defect_order:
                        col_name = f"FL_{defect_type}_{days:02d}_RATE_DEV"
                        if col_name in all_columns:
                            ordered_columns.append(col_name)
                    
                    # Count columns
                    for defect_type in defect_order:
                        col_name = f"FL_{defect_type}_{days:02d}_DEV"
                        if col_name in all_columns:
                            ordered_columns.append(col_name)
                    
                    # MWAF columns
                    mwaf_col = f"FL_{days:02d}_MWAF_DEV"
                    if mwaf_col in all_columns:
                        ordered_columns.append(mwaf_col)
                
                elif scope == 'CF':
                    # Ratio columns
                    # Rate ratios first
                    for defect_type in defect_order:
                        col_name = f"CF_{defect_type}_{days:02d}_RRAT"
                        if col_name in all_columns:
                            ordered_columns.append(col_name)
                    
                    # Count ratios
                    for defect_type in defect_order:
                        col_name = f"CF_{defect_type}_{days:02d}_DRAT"
                        if col_name in all_columns:
                            ordered_columns.append(col_name)
        
        return ordered_columns

    def _validate_column_ordering(self, ordered_columns, all_columns_including_ratios):
        """Validate that all expected columns are present in ordered list"""
        logger.info("🔍 Validating column ordering...")
        
        missing_from_ordered = set(all_columns_including_ratios) - set(ordered_columns)
        extra_in_ordered = set(ordered_columns) - set(all_columns_including_ratios)
        
        if missing_from_ordered:
            logger.warning(f"⚠️  Columns missing from ordered list: {missing_from_ordered}")
            return False
        
        if extra_in_ordered:
            logger.warning(f"⚠️  Extra columns in ordered list: {extra_in_ordered}")
            return False
        
        if len(ordered_columns) != len(all_columns_including_ratios):
            logger.warning(f"⚠️  Column count mismatch: ordered={len(ordered_columns)}, expected={len(all_columns_including_ratios)}")
            return False
        
        logger.info(f"✅ Column ordering validated: {len(ordered_columns)} columns in correct order")
        return True
    
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main processing method to add defect trend columns
        """
        if not self.config.ENABLE_DEFECT_TRENDS:
            logger.info("Defect trends processing disabled in config")
            return df
            
        logger.info("="*50)
        logger.info("ADDING DEFECT TREND COLUMNS WITH SIMPLE CONTROLS")
        logger.info("="*50)
        
        # Validate required columns exist
        required_cols = [self.time_col, self.layer_col, self.lot_col, 'SUBENTITY', self.device_col] + self.defect_cols
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            logger.error(f"Missing required columns for trends: {missing_cols}")
            return df
        
        # Make a copy and prepare data
        df_work = df.copy()
        
        # Ensure timestamp column is datetime
        df_work[self.time_col] = pd.to_datetime(df_work[self.time_col])
        
        # Sort by layer, then by time, then by lot, then by chamber
        df_work = df_work.sort_values([self.layer_col, self.time_col, self.lot_col, 'SUBENTITY'])
        
        # Initialize trend columns
        df_work, trend_columns = self._initialize_trend_columns(df_work)
        
        # Show data summary
        logger.info(f"Input dataset shape: {df_work.shape}")
        unique_layers = df_work[self.layer_col].unique()
        unique_chambers = df_work['SUBENTITY'].unique()
        unique_devices = df_work[self.device_col].unique()
        logger.info(f"Processing {len(unique_layers)} layers: {unique_layers}")
        logger.info(f"Processing {len(unique_chambers)} chambers: {unique_chambers}")
        logger.info(f"Processing {len(unique_devices)} devices: {unique_devices}")
        
        # Show simple config controls
        enabled_defects = [k for k, v in self.defect_type_controls.items() if v]
        disabled_defects = [k for k, v in self.defect_type_controls.items() if not v]
        logger.info(f"📋 Simple Config Controls:")
        logger.info(f"   Enabled defect types: {enabled_defects}")
        if disabled_defects:
            logger.info(f"   Disabled defect types: {disabled_defects}")
        
        # Check time range
        time_range = f"{df_work[self.time_col].min()} to {df_work[self.time_col].max()}"
        logger.info(f"Time range: {time_range}")
        
        # Process each layer separately
        for layer in unique_layers:
            df_work = self._process_layer_trends(df_work, layer)
        
        # Validate results
        self._validate_trend_results(df_work, trend_columns)
        
        # Calculate chamber-to-fleet ratios
        df_work, ratio_columns = self._add_chamber_fleet_ratios(df_work)
        
        # Update trend columns list to include ratios for ordering
        all_columns_with_ratios = trend_columns + ratio_columns
        
        # Get ordered column list
        ordered_trend_columns = self._get_ordered_trend_columns_with_ratios(all_columns_with_ratios)
        
        # Validate ordering with the complete column list
        if not self._validate_column_ordering(ordered_trend_columns, all_columns_with_ratios):
            logger.error("Column ordering validation failed!")
            return df_work
        
        # Reorder columns in dataframe
        other_columns = [col for col in df_work.columns if col not in ordered_trend_columns]
        df_work = df_work[other_columns + ordered_trend_columns]
        
        # Show results summary
        logger.info(f"📊 SIMPLE TREND PROCESSING COMPLETE")
        logger.info(f"   Total new columns added: {len(ordered_trend_columns)}")
        logger.info(f"   Column order: CH→FL→FL_DEV→CF, Period-grouped")
        logger.info(f"   Enabled defect types: {enabled_defects}")
        if ordered_trend_columns:
            logger.info(f"   First 10 ordered columns: {ordered_trend_columns[:10]}")
        logger.info("="*50)
        
        return df_work