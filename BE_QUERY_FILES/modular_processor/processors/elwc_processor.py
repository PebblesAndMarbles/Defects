# -*- coding: utf-8 -*-
"""
ELWC (Equipment Level Wafer Count) processor for lookback calculations
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable

from core.base_processors import ProcessorBase
from core.utils import DataUtils
from core.column_manager import ColumnManager
from core.config import Config

class OptimizedELWCProcessor(ProcessorBase):
    """Dramatically optimized ELWC processor with vectorization and smart caching"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.elwc_df = None
        self.wafer_lookup = {}  # Cache for wafer->ELWC mapping
        self.chamber_recipe_cache = {}  # Pre-calculated recipe counts
        self.recipe_group_masks = {}  # Pre-calculated boolean masks for each recipe group
    
    # ===== INTEGRATED RECIPE CLASSIFICATION (same as before) =====
    def _get_technology(self, oper_short_desc: str) -> str:
        """Determine technology from operation description"""
        if pd.isna(oper_short_desc) or len(str(oper_short_desc)) < 4:
            return 'UNKNOWN'
        fourth_char = str(oper_short_desc)[3]
        return {'8': '1278', '0': '1280'}.get(fourth_char, 'UNKNOWN')
    
    def _classify_recipe_group(self, seq_recipe: str, technology: str, is_test_wafer: bool, oper_short_desc: str = None) -> str:
        """Classify recipe into groups - includes 8MT5"""
        if pd.isna(seq_recipe):
            return 'OTHER'
        
        recipe_str = str(seq_recipe).upper()
        
        # MONTW: Monitors and test wafers
        if (recipe_str.startswith(('M_', 'C_')) or 
            'TEACH' in recipe_str or is_test_wafer):
            return 'MONTW'
        
        # 8MT5 classification - must be checked BEFORE product wafer classification
        if (not is_test_wafer and 
            technology == '1278' and 
            pd.notna(oper_short_desc) and 
            '5' in str(oper_short_desc)):
            return '8MT5'
        
        # Product wafers by technology
        if not is_test_wafer:
            return self._classify_product_recipe(recipe_str, technology)
        
        return 'OTHER'
    
    def _classify_product_recipe(self, recipe_str: str, technology: str) -> str:
        """Classify product recipes by technology"""
        recipe_mapping = {
            '1278': {
                ('GABON', 'CHALBI'): '8GAB',
                ('THAR',): '8THA',
                ('GOBI',): '8GOB',
                ('PIL',): '8PIL'
            },
            '1280': {
                ('GABON', 'CHALBI'): '0GAB',
                ('THAR',): '0THA',
                ('GOBI',): '0GOB',
                ('PIL',): '0PIL'
            }
        }
        
        if recipe_str.startswith('S_'):
            return f"{technology[-1]}SIF"
        
        for keywords, group in recipe_mapping.get(technology, {}).items():
            if any(keyword in recipe_str for keyword in keywords):
                return group
        
        return 'OTHER'
    
    # ===== OPTIMIZED ELWC PROCESSING =====
    def load_and_preprocess_optimized(self) -> bool:
        """Load and preprocess ELWC data with optimizations"""
        self.logger.info("=== OPTIMIZED ELWC LOOKBACK PROCESSING ===")
        
        # Load ELWC dataset
        self.elwc_df = self.safe_load_csv(self.config.ELWC_PATH)
        if self.elwc_df is None:
            return False
        
        if not self.validate_required_columns(self.elwc_df, ['START_DATE', 'LOT', 'OPER_SHORT_DESC', 'SEQ_RECIPE']):
            return False
        
        # Preprocess ELWC data
        self.logger.info("Preprocessing ELWC data (optimized)...")
        
        # Convert START_DATE to datetime
        self.elwc_df = DataUtils.safe_datetime_convert(self.elwc_df, 'START_DATE')
        self.elwc_df['START_DATETIME'] = self.elwc_df['START_DATE']
        
        # Vectorized operations for better performance
        self.logger.info("Creating test wafer flags (vectorized)...")
        self.elwc_df['IS_TEST_WAFER'] = self.elwc_df['LOT'].astype(str).str.contains('T', na=False)
        
        self.logger.info("Determining technology (vectorized)...")
        self.elwc_df['TECHNOLOGY'] = self.elwc_df['OPER_SHORT_DESC'].apply(self._get_technology)
        
        self.logger.info("Classifying recipe groups (vectorized)...")
        self.elwc_df['RECIPE_GROUP'] = self.elwc_df.apply(
            lambda row: self._classify_recipe_group(
                row['SEQ_RECIPE'], 
                row['TECHNOLOGY'], 
                row['IS_TEST_WAFER'],
                row['OPER_SHORT_DESC']
            ), axis=1
        )
        
        # Show statistics
        self._show_preprocessing_stats()
        
        # Create optimized lookup structures
        self._create_optimized_lookups()
        
        return True
    
    def _show_preprocessing_stats(self):
        """Show preprocessing statistics"""
        self.logger.info(f"\nRecipe group distribution in ELWC data:")
        recipe_counts = self.elwc_df['RECIPE_GROUP'].value_counts()
        self.logger.info(f"{recipe_counts}")
        
        # Special logging for 8MT5
        if '8MT5' in recipe_counts.index:
            mt5_count = recipe_counts['8MT5']
            gab_count = recipe_counts.get('8GAB', 0)
            self.logger.info(f"\n*** 8MT5 GROUP IMPACT ***")
            self.logger.info(f"8MT5 wafers identified: {mt5_count}")
            self.logger.info(f"Remaining 8GAB wafers: {gab_count}")
            if (mt5_count + gab_count) > 0:
                self.logger.info(f"8MT5 represents {mt5_count/(mt5_count + gab_count)*100:.1f}% of former 8GAB+8MT5 combined")
    
    def _create_optimized_lookups(self):
        """Create highly optimized lookup structures"""
        self.logger.info("Creating optimized ELWC lookup structures...")
        
        # 1. Create wafer->ELWC mapping for O(1) lookups
        self.logger.info("Building wafer lookup dictionary...")
        self.wafer_lookup = {}
        for idx, row in self.elwc_df.iterrows():
            key = (row['WAFER'], row['OPER'])
            self.wafer_lookup[key] = {
                'subentity': row['SUBENTITY'],
                'start_time': row['START_DATETIME'],
                'recipe_group': row['RECIPE_GROUP']
            }
        
        self.logger.info(f"Created wafer lookup for {len(self.wafer_lookup)} wafer-operation combinations")
        
        # 2. Pre-calculate recipe group masks for vectorized operations
        self.logger.info("Pre-calculating recipe group masks...")
        for group in self.config.RECIPE_GROUPS:
            self.recipe_group_masks[group] = self.elwc_df['RECIPE_GROUP'] == group
        
        # 3. Sort and group by chamber for efficient time-window filtering
        self.logger.info("Grouping by chamber for time-window calculations...")
        self.elwc_df = self.elwc_df.sort_values(['SUBENTITY', 'START_DATETIME'])
        
        # Group by chamber
        chamber_groups = self.elwc_df.groupby('SUBENTITY')
        for chamber, chamber_data in chamber_groups:
            # Store sorted chamber data for efficient time-window queries
            self.chamber_recipe_cache[chamber] = chamber_data.reset_index(drop=True)
        
        self.logger.info(f"Prepared chamber data for {len(self.chamber_recipe_cache)} chambers")
    
    def calculate_lookbacks_optimized(self, wafer_id: str, operation: str, debug: bool = False) -> Dict[str, float]:
        """Highly optimized lookback calculation"""
        # O(1) lookup for wafer match
        wafer_key = (wafer_id, operation)
        if wafer_key not in self.wafer_lookup:
            if debug:
                self.logger.debug(f"No ELWC match found for {wafer_id}, {operation}")
            return {f'{group}_{window}HRS': np.nan 
                   for group in self.config.RECIPE_GROUPS 
                   for window in self.config.TIME_WINDOWS}
        
        elwc_info = self.wafer_lookup[wafer_key]
        subentity = elwc_info['subentity']
        reference_time = elwc_info['start_time']
        
        if debug:
            self.logger.debug(f"ELWC match: {subentity} at {reference_time}")
        
        # Get chamber data
        if subentity not in self.chamber_recipe_cache:
            if debug:
                self.logger.debug(f"No chamber data for {subentity}")
            return {f'{group}_{window}HRS': np.nan 
                   for group in self.config.RECIPE_GROUPS 
                   for window in self.config.TIME_WINDOWS}
        
        chamber_data = self.chamber_recipe_cache[subentity]
        results = {}
        
        # Vectorized time window calculations
        for window_hours in self.config.TIME_WINDOWS:
            lookback_time = reference_time - timedelta(hours=window_hours)
            
            # Vectorized time filtering
            time_mask = ((chamber_data['START_DATETIME'] >= lookback_time) & 
                        (chamber_data['START_DATETIME'] < reference_time))
            window_data = chamber_data[time_mask]
            
            if debug and window_hours == 4:
                self.logger.debug(f"{window_hours}hr window: {len(window_data)} total wafers")
            
            # Vectorized recipe group counting
            for group in self.config.RECIPE_GROUPS:
                group_mask = window_data['RECIPE_GROUP'] == group
                count = group_mask.sum()
                results[f'{group}_{window_hours}HRS'] = count
                
                if debug and window_hours == 4 and count > 0:
                    self.logger.debug(f"{group}: {count} wafers")
        
        return results
    
    def add_elwc_lookbacks_optimized(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add ELWC lookback metrics with dramatic optimizations"""
        start_time = datetime.now()
        
        if not self.load_and_preprocess_optimized():
            self.logger.error("Failed to load ELWC data")
            return dt
        
        # Initialize columns using ColumnManager
        lookback_cols = {
            f'{group}_{window}HRS': np.nan 
            for group in self.config.RECIPE_GROUPS 
            for window in self.config.TIME_WINDOWS
        }
        dt = ColumnManager.add_columns_batch(dt, lookback_cols)
        
        # Test with first few rows
        self._test_lookback_calculations_optimized(dt)
        
        # Process all rows with optimized batch processing
        self._process_all_lookbacks_optimized(dt)
        
        # Show summary
        self._show_lookback_summary_optimized(dt, start_time)
        
        return dt
    
    def _test_lookback_calculations_optimized(self, dt: pd.DataFrame):
        """Test optimized lookback calculations"""
        self.logger.info("\n=== TESTING OPTIMIZED LOOKBACK CALCULATIONS ===")
        test_rows = dt.head(3)
        for idx in test_rows.index:
            row = dt.loc[idx]
            wafer_id = row['WAFER_ID']
            operation = row['OPERATION']
            
            self.logger.info(f"\nTesting row {idx}: {wafer_id}, {operation}")
            results = self.calculate_lookbacks_optimized(wafer_id, operation, debug=True)
            
            # Show sample results including 8MT5
            sample_cols = [f'{group}_4HRS' for group in ['MONTW', '8GAB', '8MT5', '8THA']]
            for col in sample_cols:
                if col in results:
                    self.logger.info(f"  {col}: {results[col]}")
        self.logger.info("=== END TEST ===\n")
    
    def _process_all_lookbacks_optimized(self, dt: pd.DataFrame):
        """Process lookbacks with optimized batch processing"""
        self.logger.info("Calculating lookbacks (OPTIMIZED)...")
        
        successful_matches = 0
        failed_matches = 0
        
        # Use batch processing for better performance
        def process_batch(batch_df, start_idx, end_idx):
            nonlocal successful_matches, failed_matches
            
            for idx in batch_df.index:
                row = dt.loc[idx]
                wafer_id = row['WAFER_ID']
                operation = row['OPERATION']
                
                results = self.calculate_lookbacks_optimized(wafer_id, operation, debug=False)
                
                # Update dataframe with results
                for col, value in results.items():
                    dt.at[idx, col] = value
                
                # Track success/failure
                if pd.isna(list(results.values())[0]):
                    failed_matches += 1
                else:
                    successful_matches += 1
        
        # Process in batches
        DataUtils.batch_process(dt, process_batch, batch_size=100, desc="Processing ELWC lookbacks")
        
        self.logger.info(f"\nOptimized lookback processing complete!")
        self.logger.info(f"Successful ELWC matches: {successful_matches}")
        self.logger.info(f"Failed matches (set to NaN): {failed_matches}")
    
    def _show_lookback_summary_optimized(self, dt: pd.DataFrame, start_time: datetime):
        """Show optimized summary statistics"""
        self.logger.info(f"\nOptimized Lookback Summary:")
        
        # Use ColumnManager for consistent display
        sample_cols = [f'{group}_{window}HRS' 
                      for group in ['MONTW', '8GAB', '8MT5', '8THA', '8GOB']
                      for window in self.config.TIME_WINDOWS[:2]]
        
        ColumnManager.show_column_summary(dt, sample_cols[:10], self.logger)  # Show first 10 columns
        
        # Show processing stats
        stats = self.get_processing_stats()
        total_time = (datetime.now() - start_time).total_seconds()
        
        self.logger.info(f"\n*** PERFORMANCE SUMMARY ***")
        self.logger.info(f"Total processing time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        if stats:
            self.logger.info(f"ELWC data load time: {stats.get('load_time', 0):.1f}s")
            self.logger.info(f"ELWC data memory: {stats.get('memory_mb', 0):.1f}MB")
        
        # Show 8MT5 impact
        if '8MT5_4HRS' in dt.columns:
            mt5_4hr_data = dt['8MT5_4HRS'].dropna()
            if len(mt5_4hr_data) > 0:
                self.logger.info(f"\n*** 8MT5 IMPACT ***")
                self.logger.info(f"Defect scans with 8MT5 activity (4hr): {len(mt5_4hr_data)}")
                self.logger.info(f"Average 8MT5 wafers per 4hr window: {mt5_4hr_data.mean():.1f}")
        

