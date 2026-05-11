# -*- coding: utf-8 -*-
"""
SPC (Statistical Process Control) monitor processor with time-based lookbacks
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

class SPCMonitorProcessor(ProcessorBase):
    """SPC surf scan particle monitor data processor with time-based lookbacks"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.spc_df = None
        self.chamber_data_cache = {}  # Pre-sorted chamber data
        self.fleet_data_cache = None  # Fleet-wide data cache
        
        # Define control limits for classification (chamber-specific only)
        self.control_limits = {
            'TOTAL_ADDERS': {'centerline': 0.7, 'upper_limit': 4.01, 'levels': 4},
            'LARGE_ADDERS': {'centerline': 0.39, 'upper_limit': 2.01, 'levels': 4},
            'ADDED_CLUSTERS': {'centerline': 0, 'upper_limit': 1.1, 'levels': 3},
            'ADDED_CLUSTER_AREA': {'centerline': 0, 'upper_limit': 1.0, 'levels': 3}
        }
        
        # Size mapping for column naming
        self.size_mapping = {
            'TOTAL_ADDERS': 'TA',
            'LARGE_ADDERS': 'LA', 
            'ADDED_CLUSTERS': 'AC',
            'ADDED_CLUSTER_AREA': 'CA'
        }
    
    def load_and_preprocess(self) -> bool:
        """Load and preprocess SPC monitor data"""
        self.logger.info("=== SPC MONITOR TIME-BASED LOOKBACK PROCESSING ===")
        
        # Load SPC dataset
        self.spc_df = self.safe_load_csv(self.config.SPC_MONITOR_PATH)
        if self.spc_df is None:
            return False
        
        # Validate required columns (note: using DATE instead of SUBENTITY_END_TIME)
        if not self.validate_required_columns(self.spc_df, ['SUBENTITY', 'DATE', 'SIZE', 'VALUE']):
            return False
        
        # Preprocess SPC data
        self.logger.info("Preprocessing SPC data for time-based lookbacks...")
        
        # Convert DATE to datetime
        self.spc_df = DataUtils.safe_datetime_convert(self.spc_df, 'DATE')
        self.spc_df['MEASUREMENT_TIME'] = self.spc_df['DATE']
        
        # Filter for expected particle sizes
        expected_sizes = list(self.size_mapping.keys())
        self.spc_df = self.spc_df[self.spc_df['SIZE'].isin(expected_sizes)].copy()
        
        # Show statistics
        self._show_preprocessing_stats()
        
        # Create optimized lookup structures
        self._create_optimized_lookups()
        
        return True
    
    def _show_preprocessing_stats(self):
        """Show preprocessing statistics"""
        total_measurements = len(self.spc_df)
        
        self.logger.info(f"\nSPC Data Statistics:")
        self.logger.info(f"Total SS measurements: {total_measurements}")
        
        # Size distribution
        size_counts = self.spc_df['SIZE'].value_counts()
        for size in self.size_mapping.keys():
            count = size_counts.get(size, 0)
            self.logger.info(f"{size}: {count} measurements")
        
        # Chamber coverage
        unique_chambers = self.spc_df['SUBENTITY'].nunique()
        self.logger.info(f"Unique chambers with SPC data: {unique_chambers}")
        
        # Date range
        if not self.spc_df.empty:
            date_range = f"{self.spc_df['DATE'].min()} to {self.spc_df['DATE'].max()}"
            self.logger.info(f"Date range: {date_range}")
    
    def _create_optimized_lookups(self):
        """Create optimized lookup structures for SPC"""
        self.logger.info("Creating optimized SPC lookup structures...")
        
        # Sort and group by chamber for efficient time-window filtering
        self.spc_df = self.spc_df.sort_values(['SUBENTITY', 'SIZE', 'MEASUREMENT_TIME'])
        
        # Group by chamber
        chamber_groups = self.spc_df.groupby('SUBENTITY')
        for chamber, chamber_data in chamber_groups:
            self.chamber_data_cache[chamber] = chamber_data.reset_index(drop=True)
        
        # Create fleet-wide data cache (all chambers combined, sorted by time)
        self.fleet_data_cache = self.spc_df.sort_values('MEASUREMENT_TIME').reset_index(drop=True)
        
        self.logger.info(f"Prepared chamber data for {len(self.chamber_data_cache)} chambers")
        self.logger.info(f"Prepared fleet data with {len(self.fleet_data_cache)} total measurements")
    
    def _format_lookback_days(self, days: int) -> str:
        """Format lookback days as string"""
        return str(days)
    
    def _calculate_days_since_last_measurement(self, reference_time: datetime, 
                                            chamber_data: pd.DataFrame) -> float:
        """Calculate days since last SS measurement (any size, since they're simultaneous)"""
        if chamber_data.empty:
            return np.nan
        
        # Find measurements before reference time (any size since they're simultaneous)
        valid_measurements = chamber_data[chamber_data['MEASUREMENT_TIME'] < reference_time]
        
        if valid_measurements.empty:
            return np.nan
        
        # Get most recent measurement
        last_measurement_time = valid_measurements['MEASUREMENT_TIME'].max()
        days_since = (reference_time - last_measurement_time).total_seconds() / (24 * 3600)
        
        return days_since

    def _calculate_spc_metrics(self, reference_time: datetime, lookback_days: int,
                            chamber_data: pd.DataFrame, fleet_data: pd.DataFrame,
                            size: str) -> Dict[str, float]:
        """
        Calculate SPC metrics for given time window (NO expanding window logic)
        
        Args:
            reference_time: Reference timestamp
            lookback_days: Lookback period in days
            chamber_data: Chamber-specific data
            fleet_data: Fleet-wide data
            size: Particle size to filter for
        
        Returns:
            Dict with chamber and fleet metrics
        """
        lookback_time = reference_time - timedelta(days=lookback_days)
        
        results = {}
        
        # Chamber metrics - strict time window only
        chamber_size_data = chamber_data[chamber_data['SIZE'] == size]
        chamber_mask = ((chamber_size_data['MEASUREMENT_TIME'] >= lookback_time) & 
                    (chamber_size_data['MEASUREMENT_TIME'] < reference_time))
        chamber_window = chamber_size_data[chamber_mask]
        
        if len(chamber_window) > 0:
            results['CH_avg'] = chamber_window['VALUE'].mean()
            results['CH_count'] = chamber_window['MEASUREMENT_TIME'].nunique()
        else:
            results['CH_avg'] = np.nan
            results['CH_count'] = 0
        
        # Fleet metrics - strict time window only
        fleet_size_data = fleet_data[fleet_data['SIZE'] == size]
        fleet_mask = ((fleet_size_data['MEASUREMENT_TIME'] >= lookback_time) & 
                    (fleet_size_data['MEASUREMENT_TIME'] < reference_time))
        fleet_window = fleet_size_data[fleet_mask]
        
        if len(fleet_window) > 0:
            results['FL_avg'] = fleet_window['VALUE'].mean()
            results['FL_count'] = fleet_window['MEASUREMENT_TIME'].nunique()
        else:
            results['FL_avg'] = np.nan
            results['FL_count'] = 0
        
        return results

    def _classify_4_level(self, value, centerline, upper_limit):
        """
        4-level classification for TOTAL_ADDERS and LARGE_ADDERS
        0 = Zero (no particles detected)
        1 = Low (0 < value ≤ centerline) 
        2 = Medium (centerline < value ≤ upper_limit)
        3 = High (value > upper_limit) - OUT OF CONTROL
        """
        if pd.isna(value):
            return np.nan
        if value == 0:
            return 0
        elif 0 < value <= centerline:
            return 1
        elif centerline < value <= upper_limit:
            return 2
        else:  # value > upper_limit
            return 3
    
    def _classify_3_level(self, value, upper_limit):
        """
        3-level classification for ADDED_CLUSTERS and ADDED_CLUSTER_AREA
        0 = Zero (no clusters/area detected)
        1 = Normal (0 < value ≤ upper_limit)
        2 = High (value > upper_limit) - OUT OF CONTROL
        """
        if pd.isna(value):
            return np.nan
        if value == 0:
            return 0
        elif 0 < value <= upper_limit:
            return 1
        else:  # value > upper_limit
            return 2
 
    def calculate_spc_lookbacks(self, subentity: str, subentity_end_time: datetime, 
                            debug: bool = False) -> Dict[str, float]:
        """Calculate SPC lookback metrics for a specific chamber and time (NO expanding window)"""
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                self.logger.debug(f"Missing subentity or time: {subentity}, {subentity_end_time}")
            return self._get_empty_results()
        
        # Get chamber and fleet data
        if subentity not in self.chamber_data_cache:
            if debug:
                self.logger.debug(f"No SPC data for chamber {subentity}")
            return self._get_empty_results()
        
        chamber_data = self.chamber_data_cache[subentity]
        fleet_data = self.fleet_data_cache
        
        results = {}
        
        # Calculate for each lookback period and size
        for days in self.config.SPC_LOOKBACKS:
            days_str = self._format_lookback_days(days)
            
            for size, short_name in self.size_mapping.items():
                # Calculate metrics (no expanding window)
                metrics = self._calculate_spc_metrics(
                    subentity_end_time, days, chamber_data, fleet_data, size
                )
                
                # Chamber-specific columns (with classification)
                ch_avg = metrics['CH_avg']
                results[f'CH_SS_{days_str}_{short_name}'] = ch_avg
                results[f'CH_SS_{days_str}_N'] = metrics['CH_count']
                
                # Apply classification to chamber averages
                if not pd.isna(ch_avg) and size in self.control_limits:
                    limits = self.control_limits[size]
                    if limits['levels'] == 4:
                        classification = self._classify_4_level(ch_avg, limits['centerline'], limits['upper_limit'])
                    else:
                        classification = self._classify_3_level(ch_avg, limits['upper_limit'])
                    results[f'CH_SS_{days_str}_{short_name}_CLASS'] = classification
                else:
                    results[f'CH_SS_{days_str}_{short_name}_CLASS'] = np.nan
                
                # Fleet-specific columns (no classification, just averages)
                results[f'FL_SS_{days_str}_{short_name}'] = metrics['FL_avg']
                results[f'FL_SS_{days_str}_N'] = metrics['FL_count']
        
        # Calculate days since last measurement (single column since all sizes are simultaneous)
        days_since = self._calculate_days_since_last_measurement(subentity_end_time, chamber_data)
        results['CH_SS_DAYS'] = days_since
        
        if debug:
            sample_size = list(self.size_mapping.keys())[0]
            sample_short = self.size_mapping[sample_size]
            first_days_str = self._format_lookback_days(self.config.SPC_LOOKBACKS[0])
            self.logger.debug(f"SPC match: {subentity} at {subentity_end_time}")
            self.logger.debug(f"Sample {sample_size}: CH={results.get(f'CH_SS_{first_days_str}_{sample_short}', 'N/A')}, FL={results.get(f'FL_SS_{first_days_str}_{sample_short}', 'N/A')}")
            self.logger.debug(f"Days since last SS: {results['CH_SS_DAYS']}")
        
        return results

    def _get_empty_results(self) -> Dict[str, float]:
        """Get empty results dictionary with NaN values"""
        results = {}
        
        for days in self.config.SPC_LOOKBACKS:
            days_str = self._format_lookback_days(days)
            
            for size, short_name in self.size_mapping.items():
                # Chamber columns
                results[f'CH_SS_{days_str}_{short_name}'] = np.nan
                results[f'CH_SS_{days_str}_{short_name}_CLASS'] = np.nan
                results[f'CH_SS_{days_str}_N'] = 0
                
                # Fleet columns
                results[f'FL_SS_{days_str}_{short_name}'] = np.nan
                results[f'FL_SS_{days_str}_N'] = 0
        
        # Single days since last measurement column
        results['CH_SS_DAYS'] = np.nan
        
        return results

    def add_spc_monitor_data(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add SPC monitor data to the main dataframe"""
        start_time = datetime.now()
        
        if not self.load_and_preprocess():
            self.logger.error("Failed to load SPC monitor data")
            return dt
        
        # Initialize columns using ColumnManager
        spc_cols = {}
        
        for days in self.config.SPC_LOOKBACKS:
            days_str = self._format_lookback_days(days)
            
            for size, short_name in self.size_mapping.items():
                # Chamber columns
                spc_cols[f'CH_SS_{days_str}_{short_name}'] = np.nan
                spc_cols[f'CH_SS_{days_str}_{short_name}_CLASS'] = np.nan
                spc_cols[f'CH_SS_{days_str}_N'] = 0
                
                # Fleet columns
                spc_cols[f'FL_SS_{days_str}_{short_name}'] = np.nan
                spc_cols[f'FL_SS_{days_str}_N'] = 0
        
        # Single days since last measurement column
        spc_cols['CH_SS_DAYS'] = np.nan
        
        dt = ColumnManager.add_columns_batch(dt, spc_cols)
        
        # Test with first few rows
        self._test_spc_calculations(dt)
        
        # Process all rows
        self._process_all_spc_lookbacks(dt)
        
        # Show summary
        self._show_spc_summary(dt, start_time)
        
        return dt

    def _test_spc_calculations(self, dt: pd.DataFrame):
        """Test SPC calculations on sample rows"""
        self.logger.info("\n=== TESTING SPC CALCULATIONS ===")
        
        # Try to find rows with subentities that have SPC data
        test_subentities = list(self.chamber_data_cache.keys())[:3]
        test_rows = dt[dt['SUBENTITY'].isin(test_subentities)].head(3)
        
        if test_rows.empty:
            test_rows = dt.head(3)
        
        for idx in test_rows.index:
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            self.logger.info(f"\nTesting row {idx}: {subentity} at {subentity_end_time}")
            results = self.calculate_spc_lookbacks(subentity, subentity_end_time, debug=True)
            
            # Show sample results
            if self.config.SPC_LOOKBACKS:
                first_days = self.config.SPC_LOOKBACKS[0]
                days_str = self._format_lookback_days(first_days)
                sample_cols = [f'CH_SS_{days_str}_TA', f'FL_SS_{days_str}_TA', 
                            f'CH_SS_{days_str}_N', 'CH_SS_DAYS']
                for col in sample_cols:
                    if col in results:
                        self.logger.info(f"  {col}: {results[col]}")
        
        self.logger.info("=== END SPC TEST ===\n")
    
    def _process_all_spc_lookbacks(self, dt: pd.DataFrame):
        """Process SPC lookbacks for all rows"""
        self.logger.info("Calculating SPC lookbacks...")
        
        successful_matches = 0
        failed_matches = 0
        
        def process_batch(batch_df, start_idx, end_idx):
            nonlocal successful_matches, failed_matches
            
            for idx in batch_df.index:
                row = dt.loc[idx]
                subentity = row['SUBENTITY']
                subentity_end_time = row['SUBENTITY_END_TIME']
                
                results = self.calculate_spc_lookbacks(subentity, subentity_end_time, debug=False)
                
                # Update dataframe with results
                for col, value in results.items():
                    dt.at[idx, col] = value
                
                # Track success/failure (check if any chamber values are not NaN)
                chamber_values = [v for k, v in results.items() if k.startswith('CH_SS_') and not k.endswith('_N') and not k.endswith('_CLASS') and not k.startswith('CH_SS_DAYS')]
                if any(not pd.isna(v) for v in chamber_values):
                    successful_matches += 1
                else:
                    failed_matches += 1
        
        # Process in batches
        DataUtils.batch_process(dt, process_batch, batch_size=100, desc="Processing SPC lookbacks")
        
        self.logger.info(f"\nSPC lookback processing complete!")
        self.logger.info(f"Successful SPC matches: {successful_matches}")
        self.logger.info(f"Failed matches (set to NaN): {failed_matches}")
    
    def _show_spc_summary(self, dt: pd.DataFrame, start_time: datetime):
        """Show SPC summary statistics"""
        self.logger.info(f"\nSPC Lookback Summary:")
        
        # Show sample columns
        if self.config.SPC_LOOKBACKS:
            first_days = self.config.SPC_LOOKBACKS[0]
            days_str = self._format_lookback_days(first_days)
            sample_cols = [f'CH_SS_{days_str}_TA', f'FL_SS_{days_str}_TA', 
                          f'CH_SS_{days_str}_N', f'CH_SS_DAYS_TA']
            
            ColumnManager.show_column_summary(dt, sample_cols, self.logger)
        
        # Show classification summary
        self._show_classification_summary(dt)
        
        # Show processing stats
        total_time = (datetime.now() - start_time).total_seconds()
        self.logger.info(f"\n*** SPC PERFORMANCE SUMMARY ***")
        self.logger.info(f"Total processing time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    
    def _show_classification_summary(self, dt: pd.DataFrame):
        """Show summary of control limit classifications"""
        self.logger.info("\nSPC Control Limit Classification Summary:")
        
        # Find classification columns
        class_cols = [col for col in dt.columns if col.startswith('CH_SS_') and col.endswith('_CLASS')]
        
        for col in class_cols[:4]:  # Show first few for brevity
            if col in dt.columns:
                class_counts = dt[col].value_counts().sort_index()
                total_valid = dt[col].notna().sum()
                
                if total_valid > 0:
                    self.logger.info(f"\n{col} Classifications:")
                    for level, count in class_counts.items():
                        pct = (count / total_valid * 100) if total_valid > 0 else 0
                        level_name = self._get_level_name(col, int(level))
                        self.logger.info(f"  Level {int(level)} ({level_name}): {count} ({pct:.1f}%)")
    
    def _get_level_name(self, col: str, level: int) -> str:
        """Get descriptive name for classification level"""
        if '_TA_' in col or '_LA_' in col:  # TOTAL_ADDERS or LARGE_ADDERS
            level_names = {0: 'Zero', 1: 'Low', 2: 'Medium', 3: 'High/OOC'}
        else:  # ADDED_CLUSTERS, ADDED_CLUSTER_AREA
            level_names = {0: 'Zero', 1: 'Normal', 2: 'High/OOC'}
        
        return level_names.get(level, 'Unknown')