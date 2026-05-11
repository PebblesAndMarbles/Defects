# -*- coding: utf-8 -*-
"""
ELWC2 (Enhanced Equipment Level Wafer Count) processor for production wafer utilization
Provides layer-specific and all-product wafer counts with chamber and fleet metrics
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from core.base_processors import ProcessorBase
from core.utils import DataUtils
from core.column_manager import ColumnManager
from core.config import Config

class ELWC2Processor(ProcessorBase):
    """
    ELWC2 processor for production wafer utilization lookbacks
    Generates layer-specific (NWAF) and all-product (AWAF) wafer counts
    """
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.elwc_df = None
        self.wafer_lookup = {}  # Cache for wafer->ELWC mapping
        self.chamber_data_cache = {}  # Pre-sorted chamber data
        self.fleet_data_cache = None  # Fleet-wide data cache
        self.layer_patterns = {
            '8M5CL': {'technology': '1278', 'layer_digit': '5'},
            '8M6CL': {'technology': '1278', 'layer_digit': '6'}
        }
    
    def _get_technology(self, oper_short_desc: str) -> str:
        """Determine technology from operation description"""
        if pd.isna(oper_short_desc) or len(str(oper_short_desc)) < 4:
            return 'UNKNOWN'
        fourth_char = str(oper_short_desc)[3]
        return {'8': '1278', '0': '1280'}.get(fourth_char, 'UNKNOWN')
        
    def _is_layer_specific_wafer(self, row: pd.Series, layer: str) -> bool:
        """
        Check if wafer matches layer-specific pattern
        Uses same logic as ELWC processor's 8MT5 classification but more specific
        """
        if layer not in self.layer_patterns:
            return False
        
        pattern = self.layer_patterns[layer]
        
        # Must be production wafer (not MONTW)
        if row.get('IS_TEST_WAFER', False):
            return False
        
        # Check technology match
        if row.get('TECHNOLOGY') != pattern['technology']:
            return False
        
        # Check for specific layer patterns in operation description
        oper_desc = str(row.get('OPER_SHORT_DESC', ''))
        
        if layer == '8M5CL':
            # For 8M5CL: Look for 'M5' or 'MT5' patterns (matches ELWC logic)
            return 'M5' in oper_desc or 'MT5' in oper_desc
        
        elif layer == '8M6CL':
            # For 8M6CL: Look specifically for 'M6' or 'MT6' patterns
            return 'M6' in oper_desc or 'MT6' in oper_desc
        
        else:
            # For future layers: use M{digit} or MT{digit} pattern
            layer_digit = pattern['layer_digit']
            return f'M{layer_digit}' in oper_desc or f'MT{layer_digit}' in oper_desc
    
    def _is_product_wafer(self, row: pd.Series) -> bool:
        """
        Check if wafer is a product wafer (not MONTW)
        """
        # Not a test wafer and not MONTW recipe group
        return not row.get('IS_TEST_WAFER', False) and row.get('RECIPE_GROUP') != 'MONTW'
    
    def _classify_recipe_group(self, seq_recipe: str, technology: str, is_test_wafer: bool, oper_short_desc: str = None) -> str:
        """Classify recipe into groups - reuse ELWC logic"""
        if pd.isna(seq_recipe):
            return 'OTHER'
        
        recipe_str = str(seq_recipe).upper()
        
        # MONTW: Monitors and test wafers
        if (recipe_str.startswith(('M_', 'C_')) or 
            'TEACH' in recipe_str or is_test_wafer):
            return 'MONTW'
        
        # Product wafers
        if not is_test_wafer:
            return 'PRODUCT'
        
        return 'OTHER'
    
    def load_and_preprocess(self) -> bool:
        """Load and preprocess ELWC data for ELWC2 calculations"""
        self.logger.info("=== ELWC2 PRODUCTION UTILIZATION PROCESSING ===")
        
        # Load ELWC dataset (same source as ELWC processor)
        self.elwc_df = self.safe_load_csv(self.config.ELWC_PATH)
        if self.elwc_df is None:
            return False
        
        if not self.validate_required_columns(self.elwc_df, ['START_DATE', 'LOT', 'OPER_SHORT_DESC', 'SEQ_RECIPE', 'SUBENTITY']):
            return False
        
        # Preprocess ELWC data
        self.logger.info("Preprocessing ELWC data for ELWC2...")
        
        # Convert START_DATE to datetime
        self.elwc_df = DataUtils.safe_datetime_convert(self.elwc_df, 'START_DATE')
        self.elwc_df['START_DATETIME'] = self.elwc_df['START_DATE']
        
        # Create flags
        self.elwc_df['IS_TEST_WAFER'] = self.elwc_df['LOT'].astype(str).str.contains('T', na=False)
        self.elwc_df['TECHNOLOGY'] = self.elwc_df['OPER_SHORT_DESC'].apply(self._get_technology)
        self.elwc_df['RECIPE_GROUP'] = self.elwc_df.apply(
            lambda row: self._classify_recipe_group(
                row['SEQ_RECIPE'], 
                row['TECHNOLOGY'], 
                row['IS_TEST_WAFER'],
                row['OPER_SHORT_DESC']
            ), axis=1
        )
        
        # Add layer-specific flags for each supported layer
        for layer in self.layer_patterns.keys():
            self.elwc_df[f'IS_{layer}'] = self.elwc_df.apply(
                lambda row: self._is_layer_specific_wafer(row, layer), axis=1
            )
        
        # Add product wafer flag
        self.elwc_df['IS_PRODUCT'] = self.elwc_df.apply(self._is_product_wafer, axis=1)
        
        # Show statistics
        self._show_preprocessing_stats()
        
        # Create optimized lookup structures
        self._create_optimized_lookups()
        
        return True
    
    def _show_preprocessing_stats(self):
        """Show preprocessing statistics"""
        total_wafers = len(self.elwc_df)
        product_wafers = self.elwc_df['IS_PRODUCT'].sum()
        montw_wafers = (self.elwc_df['RECIPE_GROUP'] == 'MONTW').sum()
        
        self.logger.info(f"\nELWC2 Data Statistics:")
        self.logger.info(f"Total wafers in ELWC data: {total_wafers}")
        self.logger.info(f"Product wafers (AWAF eligible): {product_wafers}")
        self.logger.info(f"MONTW wafers (excluded): {montw_wafers}")
        
        # Layer-specific statistics
        for layer in self.layer_patterns.keys():
            layer_count = self.elwc_df[f'IS_{layer}'].sum()
            self.logger.info(f"{layer} wafers (NWAF eligible): {layer_count}")
    
    def _create_optimized_lookups(self):
        """Create optimized lookup structures for ELWC2"""
        self.logger.info("Creating optimized ELWC2 lookup structures...")
        
        # 1. Create wafer->ELWC mapping for O(1) lookups
        self.wafer_lookup = {}
        for idx, row in self.elwc_df.iterrows():
            key = (row['WAFER'], row['OPER'])
            self.wafer_lookup[key] = {
                'subentity': row['SUBENTITY'],
                'start_time': row['START_DATETIME'],
                'layer_flags': {layer: row[f'IS_{layer}'] for layer in self.layer_patterns.keys()},
                'is_product': row['IS_PRODUCT']
            }
        
        self.logger.info(f"Created wafer lookup for {len(self.wafer_lookup)} wafer-operation combinations")
        
        # 2. Sort and group by chamber for efficient time-window filtering
        self.elwc_df = self.elwc_df.sort_values(['SUBENTITY', 'START_DATETIME'])
        
        # Group by chamber
        chamber_groups = self.elwc_df.groupby('SUBENTITY')
        for chamber, chamber_data in chamber_groups:
            self.chamber_data_cache[chamber] = chamber_data.reset_index(drop=True)
        
        # 3. Create fleet-wide data cache (all chambers combined, sorted by time)
        self.fleet_data_cache = self.elwc_df.sort_values('START_DATETIME').reset_index(drop=True)
        
        self.logger.info(f"Prepared chamber data for {len(self.chamber_data_cache)} chambers")
        self.logger.info(f"Prepared fleet data with {len(self.fleet_data_cache)} total wafers")
    
    def _format_lookback_days(self, days: int) -> str:
        """Format lookback days as 2-digit string"""
        return f"{days:02d}"
    
    def _calculate_utilization_counts(self, reference_time: datetime, lookback_days: int, 
                                    chamber_data: pd.DataFrame, fleet_data: pd.DataFrame, 
                                    layer: str = None) -> Dict[str, int]:
        """
        Calculate utilization counts for given time window
        
        Args:
            reference_time: Reference timestamp
            lookback_days: Lookback period in days
            chamber_data: Chamber-specific data
            fleet_data: Fleet-wide data
            layer: Layer to filter for (None for all product wafers)
        
        Returns:
            Dict with CH_count and FL_count
        """
        lookback_time = reference_time - timedelta(days=lookback_days)
        
        results = {}
        
        # Chamber counts
        chamber_mask = ((chamber_data['START_DATETIME'] >= lookback_time) & 
                       (chamber_data['START_DATETIME'] < reference_time))
        chamber_window = chamber_data[chamber_mask]
        
        if layer:
            # Layer-specific count (NWAF)
            chamber_count = chamber_window[f'IS_{layer}'].sum()
        else:
            # All product wafers count (AWAF)
            chamber_count = chamber_window['IS_PRODUCT'].sum()
        
        results['CH_count'] = chamber_count
        
        # Fleet counts
        fleet_mask = ((fleet_data['START_DATETIME'] >= lookback_time) & 
                     (fleet_data['START_DATETIME'] < reference_time))
        fleet_window = fleet_data[fleet_mask]
        
        if layer:
            # Layer-specific count (NWAF)
            fleet_count = fleet_window[f'IS_{layer}'].sum()
        else:
            # All product wafers count (AWAF)
            fleet_count = fleet_window['IS_PRODUCT'].sum()
        
        results['FL_count'] = fleet_count
        
        return results
    
    def calculate_elwc2_lookbacks(self, wafer_id: str, operation: str, layer: str, debug: bool = False) -> Dict[str, float]:
        """Calculate ELWC2 lookback metrics for a specific wafer"""
        # O(1) lookup for wafer match
        wafer_key = (wafer_id, operation)
        if wafer_key not in self.wafer_lookup:
            if debug:
                self.logger.debug(f"No ELWC2 match found for {wafer_id}, {operation}")
            return self._get_empty_results()
        
        elwc_info = self.wafer_lookup[wafer_key]
        subentity = elwc_info['subentity']
        reference_time = elwc_info['start_time']
        
        if debug:
            self.logger.debug(f"ELWC2 match: {subentity} at {reference_time}, layer: {layer}")
        
        # Get chamber and fleet data
        if subentity not in self.chamber_data_cache:
            if debug:
                self.logger.debug(f"No chamber data for {subentity}")
            return self._get_empty_results()
        
        chamber_data = self.chamber_data_cache[subentity]
        fleet_data = self.fleet_data_cache
        
        results = {}
        
        # Calculate for each lookback period
        for days in self.config.ELWC2_LOOKBACKS:
            days_str = self._format_lookback_days(days)
            
            # Layer-specific counts (NWAF)
            if layer in self.layer_patterns:
                layer_counts = self._calculate_utilization_counts(
                    reference_time, days, chamber_data, fleet_data, layer
                )
                results[f'CH_{days_str}_NWAF'] = layer_counts['CH_count']
                results[f'FL_{days_str}_NWAF'] = layer_counts['FL_count']
            else:
                # If layer not supported, set to NaN
                results[f'CH_{days_str}_NWAF'] = np.nan
                results[f'FL_{days_str}_NWAF'] = np.nan
            
            # All product wafer counts (AWAF)
            product_counts = self._calculate_utilization_counts(
                reference_time, days, chamber_data, fleet_data, layer=None
            )
            results[f'CH_{days_str}_AWAF'] = product_counts['CH_count']
            results[f'FL_{days_str}_AWAF'] = product_counts['FL_count']
            
            if debug and days == self.config.ELWC2_LOOKBACKS[0]:
                self.logger.debug(f"{days}d window - Layer {layer}: CH={results.get(f'CH_{days_str}_NWAF', 'N/A')}, FL={results.get(f'FL_{days_str}_NWAF', 'N/A')}")
                self.logger.debug(f"{days}d window - All Product: CH={results[f'CH_{days_str}_AWAF']}, FL={results[f'FL_{days_str}_AWAF']}")
        
        return results
    
    def _get_empty_results(self) -> Dict[str, float]:
        """Get empty results dictionary with NaN values"""
        results = {}
        for days in self.config.ELWC2_LOOKBACKS:
            days_str = self._format_lookback_days(days)
            results[f'CH_{days_str}_NWAF'] = np.nan
            results[f'FL_{days_str}_NWAF'] = np.nan
            results[f'CH_{days_str}_AWAF'] = np.nan
            results[f'FL_{days_str}_AWAF'] = np.nan
        return results
    
    def add_elwc2_lookbacks(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add ELWC2 lookback metrics to dataframe"""
        start_time = datetime.now()
        
        if not self.load_and_preprocess():
            self.logger.error("Failed to load ELWC2 data")
            return dt
        
        # Validate LAYER column exists
        if 'LAYER' not in dt.columns:
            self.logger.error("LAYER column not found in dataframe - required for ELWC2")
            return dt
        
        # Initialize columns using ColumnManager
        lookback_cols = {}
        for days in self.config.ELWC2_LOOKBACKS:
            days_str = self._format_lookback_days(days)
            lookback_cols[f'CH_{days_str}_NWAF'] = np.nan
            lookback_cols[f'FL_{days_str}_NWAF'] = np.nan
            lookback_cols[f'CH_{days_str}_AWAF'] = np.nan
            lookback_cols[f'FL_{days_str}_AWAF'] = np.nan
        
        dt = ColumnManager.add_columns_batch(dt, lookback_cols)
        
        # Test with first few rows
        self._test_elwc2_calculations(dt)
        
        # Process all rows
        self._process_all_elwc2_lookbacks(dt)
        
        # Show summary
        self._show_elwc2_summary(dt, start_time)
        
        return dt
    
    def _test_elwc2_calculations(self, dt: pd.DataFrame):
        """Test ELWC2 calculations on sample rows"""
        self.logger.info("\n=== TESTING ELWC2 CALCULATIONS ===")
        test_rows = dt.head(3)
        for idx in test_rows.index:
            row = dt.loc[idx]
            wafer_id = row['WAFER_ID']
            operation = row['OPERATION']
            layer = row['LAYER']
            
            self.logger.info(f"\nTesting row {idx}: {wafer_id}, {operation}, layer: {layer}")
            results = self.calculate_elwc2_lookbacks(wafer_id, operation, layer, debug=True)
            
            # Show sample results
            first_days = self.config.ELWC2_LOOKBACKS[0]
            days_str = self._format_lookback_days(first_days)
            sample_cols = [f'CH_{days_str}_NWAF', f'FL_{days_str}_NWAF', 
                          f'CH_{days_str}_AWAF', f'FL_{days_str}_AWAF']
            for col in sample_cols:
                if col in results:
                    self.logger.info(f"  {col}: {results[col]}")
        self.logger.info("=== END ELWC2 TEST ===\n")
    
    def _process_all_elwc2_lookbacks(self, dt: pd.DataFrame):
        """Process ELWC2 lookbacks for all rows"""
        self.logger.info("Calculating ELWC2 lookbacks...")
        
        successful_matches = 0
        failed_matches = 0
        
        def process_batch(batch_df, start_idx, end_idx):
            nonlocal successful_matches, failed_matches
            
            for idx in batch_df.index:
                row = dt.loc[idx]
                wafer_id = row['WAFER_ID']
                operation = row['OPERATION']
                layer = row['LAYER']
                
                results = self.calculate_elwc2_lookbacks(wafer_id, operation, layer, debug=False)
                
                # Update dataframe with results
                for col, value in results.items():
                    dt.at[idx, col] = value
                
                # Track success/failure
                if pd.isna(list(results.values())[0]):
                    failed_matches += 1
                else:
                    successful_matches += 1
        
        # Process in batches
        DataUtils.batch_process(dt, process_batch, batch_size=100, desc="Processing ELWC2 lookbacks")
        
        self.logger.info(f"\nELWC2 lookback processing complete!")
        self.logger.info(f"Successful ELWC2 matches: {successful_matches}")
        self.logger.info(f"Failed matches (set to NaN): {failed_matches}")
    
    def _show_elwc2_summary(self, dt: pd.DataFrame, start_time: datetime):
        """Show ELWC2 summary statistics"""
        self.logger.info(f"\nELWC2 Lookback Summary:")
        
        # Show sample columns
        first_days = self.config.ELWC2_LOOKBACKS[0] if self.config.ELWC2_LOOKBACKS else 1
        days_str = self._format_lookback_days(first_days)
        sample_cols = [f'CH_{days_str}_NWAF', f'FL_{days_str}_NWAF', 
                      f'CH_{days_str}_AWAF', f'FL_{days_str}_AWAF']
        
        ColumnManager.show_column_summary(dt, sample_cols, self.logger)
        
        # Show processing stats
        total_time = (datetime.now() - start_time).total_seconds()
        self.logger.info(f"\n*** ELWC2 PERFORMANCE SUMMARY ***")
        self.logger.info(f"Total processing time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        
        # Show layer distribution
        if 'LAYER' in dt.columns:
            layer_dist = dt['LAYER'].value_counts()
            self.logger.info(f"\nLayer distribution in processed data:")
            for layer, count in layer_dist.head(10).items():
                self.logger.info(f"  {layer}: {count} wafers")