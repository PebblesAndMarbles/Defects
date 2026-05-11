# -*- coding: utf-8 -*-
"""
Leak rate and leak by processors
"""

import pandas as pd
import numpy as np
import logging
from typing import List, Tuple

from core.base_processors import ProcessorBase, TimeBasedLookupProcessor
from core.utils import DataUtils
from core.column_manager import ColumnManager
from core.config import Config

class RefactoredLeakRateProcessor(TimeBasedLookupProcessor):
    """Refactored leak rate processor using TimeBasedLookupProcessor base class"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.time_col = 'Time'  # Override default time column name
    
    def get_required_columns(self) -> List[str]:
        """Return required columns for leak rate data"""
        return ['SUBENTITY', 'Time', 'Leak rate', 'LRSMOOTH']
    
    def get_file_path(self) -> str:
        """Return file path for leak rate data"""
        return self.config.LEAK_RATE_PATH
    
    def get_time_column(self) -> str:
        """Override to use 'Time' instead of default 'TIME'"""
        return 'Time'
    
    def add_leak_rate_data(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add leak rate data using new base class functionality"""
        if not self.load_and_prepare_data():
            self.logger.error("Failed to load leak rate data")
            return dt
        
        # Initialize columns using ColumnManager
        dt = ColumnManager.add_columns_batch(dt, {
            'RAW_LEAK_RATE': np.nan,
            'SMOOTH_LEAK_RATE': np.nan
        })
        
        # Test with sample data (existing functionality)
        self._test_leak_rate_lookup(dt)
        
        # Process all rows using new base class method
        self._process_all_leak_rates_optimized(dt)
        
        # Show summary
        self._show_leak_rate_summary(dt)
        
        return dt
    
    def _process_all_leak_rates_optimized(self, dt: pd.DataFrame):
        """Process leak rates using optimized base class lookup"""
        self.logger.info("Processing leak rates (using optimized base class)...")
        
        for idx in dt.index:
            if idx % 100 == 0:
                self.logger.info(f"Processing row {idx}/{len(dt)}")
            
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            # Use base class method for lookup
            most_recent = self.get_most_recent_before_time(
                subentity, 
                subentity_end_time, 
                debug=False
            )
            
            if most_recent is not None:
                raw_rate = most_recent.get('Leak rate', np.nan)
                smooth_rate = most_recent.get('LRSMOOTH', np.nan)
                
                # Handle blank/empty values in LRSMOOTH
                if pd.isna(smooth_rate) or str(smooth_rate).strip() == '':
                    smooth_rate = np.nan
            else:
                raw_rate = smooth_rate = np.nan
            
            dt.at[idx, 'RAW_LEAK_RATE'] = raw_rate
            dt.at[idx, 'SMOOTH_LEAK_RATE'] = smooth_rate
        
        self.logger.info("Leak rate processing complete!")
    
    def _test_leak_rate_lookup(self, dt: pd.DataFrame):
        """Test leak rate lookup with sample data"""
        self.logger.info("\n=== TESTING LEAK RATE LOOKUP (REFACTORED) ===")
        test_rows = dt.head(3)
        for idx in test_rows.index:
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            self.logger.info(f"\nRow {idx}: {subentity} at {subentity_end_time}")
            
            # Use base class method with debug
            most_recent = self.get_most_recent_before_time(
                subentity, 
                subentity_end_time, 
                debug=True
            )
            
            if most_recent is not None:
                raw_rate = most_recent.get('Leak rate', np.nan)
                smooth_rate = most_recent.get('LRSMOOTH', np.nan)
                self.logger.info(f"Result - Raw: {raw_rate}, Smooth: {smooth_rate}")
            else:
                self.logger.info(f"Result - No data found")
        
        self.logger.info("=== END TEST ===\n")
    
    def _show_leak_rate_summary(self, dt: pd.DataFrame):
        """Show leak rate processing summary using ColumnManager"""
        self.logger.info(f"\nLeak Rate Summary (Refactored):")
        
        # Use ColumnManager for consistent summary display
        ColumnManager.show_column_summary(
            dt, 
            ['RAW_LEAK_RATE', 'SMOOTH_LEAK_RATE'], 
            self.logger
        )
        
        # Show processing stats from base class
        stats = self.get_processing_stats()
        if stats:
            self.logger.info(f"Processing stats: {stats}")




class LeakByProcessor(ProcessorBase):
    """Gas-specific leak by measurement processor"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.leak_by_df = None
        self.chamber_gas_data = {}
    
    def load_data(self) -> bool:
        """Load leak by data"""
        self.logger.info("Loading gas-specific leak by data...")
        self.leak_by_df = self.safe_load_csv(self.config.LEAK_BY_PATH)
        
        if self.leak_by_df is None:
            return False
        
        if not self.validate_required_columns(self.leak_by_df, ['SUBENTITY', 'TIME', 'GAS', 'LEAK_BY']):
            return False
        
        self.logger.info(f"Leak by DataFrame shape: {self.leak_by_df.shape}")
        
        # Convert time column to datetime
        self.leak_by_df = DataUtils.safe_datetime_convert(self.leak_by_df, 'TIME')
        
        # Show gas distribution
        self._show_gas_distribution()
        
        # Prepare lookup data
        self._prepare_lookup_data()
        
        return True
    
    def _show_gas_distribution(self):
        """Show gas distribution in the data"""
        self.logger.info(f"\nGas distribution in leak by data:")
        gas_counts = self.leak_by_df['GAS'].value_counts()
        for gas in self.config.LEAK_BY_GASES:
            count = gas_counts.get(gas, 0)
            self.logger.info(f"  {gas}: {count} measurements")
        
        # Show chamber coverage
        unique_chambers = self.leak_by_df['SUBENTITY'].nunique()
        self.logger.info(f"\nUnique chambers with leak by data: {unique_chambers}")
    
    def _prepare_lookup_data(self):
        """Prepare data for efficient lookups by chamber and gas"""
        self.logger.info("Preparing leak by lookup data...")
        
        # Sort by SUBENTITY, GAS, and TIME for efficient lookup
        self.leak_by_df = self.leak_by_df.sort_values(['SUBENTITY', 'GAS', 'TIME'])
        
        # Create chamber-gas grouped data for efficient lookup
        for chamber in self.leak_by_df['SUBENTITY'].unique():
            chamber_data = self.leak_by_df[self.leak_by_df['SUBENTITY'] == chamber]
            self.chamber_gas_data[chamber] = {}
            
            for gas in self.config.LEAK_BY_GASES:
                gas_data = chamber_data[chamber_data['GAS'] == gas].copy()
                if not gas_data.empty:
                    self.chamber_gas_data[chamber][gas] = gas_data
    
    def get_most_recent_leak_by(self, subentity: str, subentity_end_time, gas: str, debug: bool = False) -> float:
        """Get the most recent leak by measurement for a specific gas"""
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                self.logger.debug(f"Missing subentity or time: {subentity}, {subentity_end_time}")
            return np.nan
        
        # Check if chamber has data for this gas
        if subentity not in self.chamber_gas_data:
            if debug:
                self.logger.debug(f"No leak by data found for chamber {subentity}")
            return np.nan
        
        if gas not in self.chamber_gas_data[subentity]:
            if debug:
                self.logger.debug(f"No {gas} data found for chamber {subentity}")
            return np.nan
        
        gas_data = self.chamber_gas_data[subentity][gas]
        
        if debug:
            self.logger.debug(f"Leak by measurements found for {subentity} {gas}: {len(gas_data)}")
        
        # Filter for measurements before or at the subentity end time
        valid_measurements = gas_data[gas_data['TIME'] <= subentity_end_time]
        
        if debug:
            self.logger.debug(f"Valid measurements (before {subentity_end_time}): {len(valid_measurements)}")
            if len(valid_measurements) > 0:
                self.logger.debug(f"Latest valid measurement time: {valid_measurements['TIME'].max()}")
        
        if valid_measurements.empty:
            if debug:
                self.logger.debug(f"No {gas} measurements before {subentity_end_time}")
            return np.nan
        
        # Get the most recent measurement
        most_recent = valid_measurements.loc[valid_measurements['TIME'].idxmax()]
        leak_by_value = most_recent['LEAK_BY']
        
        if debug:
            self.logger.debug(f"Most recent {gas} measurement time: {most_recent['TIME']}")
            self.logger.debug(f"{gas} leak by value: {leak_by_value}")
        
        return leak_by_value
    
    def add_leak_by_data(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add gas-specific leak by data to the main dataframe"""
        if not self.load_data():
            self.logger.error("Failed to load leak by data")
            return dt
        
        # Initialize new columns for each gas
        for gas in self.config.LEAK_BY_GASES:
            dt[f'LB_{gas}'] = np.nan
        
        # Test with sample data
        self._test_leak_by_lookup(dt)
        
        # Process all rows
        self._process_all_leak_by(dt)
        
        # Show summary
        self._show_leak_by_summary(dt)
        
        return dt
    
    def _test_leak_by_lookup(self, dt: pd.DataFrame):
        """Test leak by lookup with sample data"""
        self.logger.info("\n=== TESTING LEAK BY LOOKUP ===")
        
        # Try to find rows with subentities that have leak by data
        test_subentities = list(self.chamber_gas_data.keys())[:3]
        test_rows = dt[dt['SUBENTITY'].isin(test_subentities)].head(3)
        
        if test_rows.empty:
            test_rows = dt.head(3)
        
        for idx in test_rows.index:
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            self.logger.info(f"\nRow {idx}: {subentity} at {subentity_end_time}")
            
            # Test a few gases
            test_gases = ['AR', 'CF4', 'CL2']
            for gas in test_gases:
                leak_by_value = self.get_most_recent_leak_by(subentity, subentity_end_time, gas, debug=True)
                if pd.isna(leak_by_value):
                    self.logger.info(f"  LB_{gas}: NaN (no measurement found)")
                else:
                    self.logger.info(f"  LB_{gas}: {leak_by_value}")
        
        self.logger.info("=== END TEST ===\n")
    
    def _process_all_leak_by(self, dt: pd.DataFrame):
        """Process leak by measurements for all rows"""
        self.logger.info("Processing leak by measurements for all defect scans...")
        
        for idx in dt.index:
            if idx % 100 == 0:
                self.logger.info(f"Processing row {idx}/{len(dt)}")
            
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            # Get leak by values for each gas
            for gas in self.config.LEAK_BY_GASES:
                leak_by_value = self.get_most_recent_leak_by(subentity, subentity_end_time, gas, debug=False)
                dt.at[idx, f'LB_{gas}'] = leak_by_value
        
        self.logger.info("Leak by processing complete!")
    
    def _show_leak_by_summary(self, dt: pd.DataFrame):
        """Show leak by processing summary"""
        self.logger.info(f"\nLeak By Summary:")
        
        for gas in self.config.LEAK_BY_GASES:
            col_name = f'LB_{gas}'
            non_null_count = dt[col_name].notna().sum()
            total_count = len(dt)
            
            self.logger.info(f"{col_name} - Non-null values: {non_null_count}/{total_count} ({non_null_count/total_count*100:.1f}%)")
            
            if non_null_count > 0:
                valid_values = dt[dt[col_name].notna()][col_name]
                self.logger.info(f"  Range: {valid_values.min():.4f} to {valid_values.max():.4f}")
                self.logger.info(f"  Mean: {valid_values.mean():.4f}")
                
                # Show non-zero count
                non_zero_count = (valid_values > 0).sum()
                if non_zero_count > 0:
                    self.logger.info(f"  Non-zero values: {non_zero_count} ({non_zero_count/non_null_count*100:.1f}%)")



