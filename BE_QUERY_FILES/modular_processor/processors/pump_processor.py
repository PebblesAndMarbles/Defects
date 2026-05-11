# -*- coding: utf-8 -*-
"""
Dry pump failure processor
"""

import pandas as pd
import numpy as np
import logging
from typing import List

from core.base_processors import TimeBasedLookupProcessor
from core.column_manager import ColumnManager
from core.config import Config

class RefactoredDryPumpProcessor(TimeBasedLookupProcessor):
    """Refactored dry pump processor using TimeBasedLookupProcessor base class"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.time_col = 'DP_FAIL_TIME'  # Override default time column
        self.lookback_days = [15, 30, 60]
    
    def get_required_columns(self) -> List[str]:
        """Return required columns for dry pump data"""
        return ['SUBENTITY', 'DP_FAIL_TIME']
    
    def get_file_path(self) -> str:
        """Return file path for dry pump data"""
        return self.config.DP_FAIL_PATH
    
    def get_time_column(self) -> str:
        """Override to use 'DP_FAIL_TIME'"""
        return 'DP_FAIL_TIME'
    
    def add_dp_fail_data(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add dry pump failure data using new base class functionality"""
        if not self.load_and_prepare_data():
            self.logger.error("Failed to load dry pump data")
            return dt
        
        # Initialize columns using ColumnManager
        column_specs = {'DP_FAIL_HRS': np.nan}
        for days in self.lookback_days:
            column_specs[f'DP_FAIL_{days}'] = 0
        
        dt = ColumnManager.add_columns_batch(dt, column_specs)
        
        # Test with sample data
        self._test_dp_failure_lookup(dt)
        
        # Process all rows using optimized base class method
        self._process_all_dp_failures_optimized(dt)
        
        # Show summary
        self._show_dp_failure_summary(dt)
        
        return dt
    
    def _process_all_dp_failures_optimized(self, dt: pd.DataFrame):
        """Process DP failures using optimized base class lookup"""
        self.logger.info("Processing DP failures (using optimized base class)...")
        
        hours_results = []
        
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
                time_diff = subentity_end_time - most_recent[self.time_col]
                hours_since_fail = time_diff.total_seconds() / 3600.0
            else:
                hours_since_fail = np.nan
            
            hours_results.append(hours_since_fail)
        
        # Assign hours column
        dt['DP_FAIL_HRS'] = hours_results
        
        # Create binary flags using ColumnManager helper
        dt = ColumnManager.create_binary_flags(
            dt, 'DP_FAIL_HRS', self.lookback_days, 'DP_FAIL'
        )
        
        self.logger.info("DP failure processing complete!")
    
    def _test_dp_failure_lookup(self, dt: pd.DataFrame):
        """Test DP failure lookup with sample data"""
        self.logger.info("\n=== TESTING DP FAILURE LOOKUP (REFACTORED) ===")
        
        # Try to find rows with subentities that have DP failures
        if hasattr(self, 'chamber_data') and self.chamber_data:
            test_subentities = list(self.chamber_data.keys())[:3]
            test_rows = dt[dt['SUBENTITY'].isin(test_subentities)].head(3)
        else:
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
                time_diff = subentity_end_time - most_recent[self.time_col]
                hours_since_fail = time_diff.total_seconds() / 3600.0
                days_since_fail = hours_since_fail / 24
                
                self.logger.info(f"Result - Hours since DP fail: {hours_since_fail:.2f}")
                self.logger.info(f"Days since failure: {days_since_fail:.1f}")
                
                # Show what the binary flags would be
                flags = {}
                for days in self.lookback_days:
                    hours_threshold = days * 24
                    flags[f'DP_FAIL_{days}'] = 0 if pd.isna(hours_since_fail) or hours_since_fail > hours_threshold else 1
                
                flag_str = ", ".join([f"{k}={v}" for k, v in flags.items()])
                self.logger.info(f"Lookback flags: {flag_str}")
            else:
                self.logger.info(f"Result - No DP failure found")
                self.logger.info(f"Lookback flags: DP_FAIL_15=0, DP_FAIL_30=0, DP_FAIL_60=0")
        
        self.logger.info("=== END TEST ===\n")
    
    def _show_dp_failure_summary(self, dt: pd.DataFrame):
        """Show DP failure processing summary using ColumnManager"""
        self.logger.info(f"\nDP Failure Summary (Refactored):")
        
        # Show hours column summary
        ColumnManager.show_column_summary(
            dt, 
            ['DP_FAIL_HRS'], 
            self.logger
        )
        
        # Show lookback flag summaries
        self.logger.info(f"\nLookback Flag Summary:")
        for days in self.lookback_days:
            col_name = f'DP_FAIL_{days}'
            flag_counts = dt[col_name].value_counts()
            ones_count = flag_counts.get(1, 0)
            zeros_count = flag_counts.get(0, 0)
            total_count = len(dt)
            
            self.logger.info(f"{col_name}: {ones_count} failures within {days} days ({ones_count/total_count*100:.1f}%), "
                           f"{zeros_count} no recent failures ({zeros_count/total_count*100:.1f}%)")
        
        # Show processing stats from base class
        stats = self.get_processing_stats()
        if stats:
            self.logger.info(f"Processing stats: {stats}")

