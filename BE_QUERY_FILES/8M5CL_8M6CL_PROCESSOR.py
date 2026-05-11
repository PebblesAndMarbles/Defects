# -*- coding: utf-8 -*-
"""
Created on Sat Dec 27 08:54:25 2025

@author: tbatson
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class Config:
    """Configuration class for all file paths and processing parameters"""
    # File paths
    ELWC_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\2025-12-30 375 days ALL_CHAMBERS ELWC.csv"
    DP_FAIL_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\BE_AME_PUMPDOWN_FAILS.csv"
    LEAK_RATE_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\BE_AME_CHLEAK.csv"
    LEAK_BY_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\LEAKBY\processed_mfc_leak_data.csv"
    SPC_MONITOR_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\SPC_MONS\SPC_SS.csv"
    FILE1_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M5CL_NCDD.csv"
    FILE2_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M6CL_NCDD.csv"
    PARTS_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\PLT\PLT_CURRENTLY_INSTALLED.csv"
    PILOT_DATES_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\BE_AME_PILOT_TURN_ON_DATES.csv"
    OUTPUT_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_NCDD_PST.csv"
    
    # NEW: Date range filtering for faster iteration
    ENABLE_DATE_FILTER: bool = False
    START_DATE: Optional[str] = None  # Format: "2024-12-01"
    END_DATE: Optional[str] = None    # Format: "2024-12-31"
    
    # Processor control flags - NEW!
    ENABLE_ELWC: bool = True
    ENABLE_LEAK_RATE: bool = True
    ENABLE_DRY_PUMP: bool = True
    ENABLE_LEAK_BY: bool = True
    ENABLE_SPC_MONITOR: bool = True
    ENABLE_RECOAT: bool = True
    
    # Processing parameters
    RECIPE_GROUPS: List[str] = None
    TIME_WINDOWS: List[int] = None
    PART_TYPES: List[str] = None 
    PILOT_COLUMNS: List[str] = None
    LEAK_BY_GASES: List[str] = None
    SPC_MONITOR_TYPES: List[str] = None
    TOLERANCE: float = 1e-10
    
    def __post_init__(self):
        # Convert date strings to datetime objects if provided
        if self.START_DATE:
            self.start_datetime = pd.to_datetime(self.START_DATE)
        else:
            self.start_datetime = None
            
        if self.END_DATE:
            self.end_datetime = pd.to_datetime(self.END_DATE)
        else:
            self.end_datetime = None
        
        if self.RECIPE_GROUPS is None:
            # Add 8MT5 to the recipe groups list
            self.RECIPE_GROUPS = ['MONTW', '8GAB', '8THA', '8GOB', '8PIL', '8SIF', '8MT5',  # NEW!
                                 '0GAB', '0THA', '0GOB', '0PIL', '0SIF']
        if self.TIME_WINDOWS is None:
            self.TIME_WINDOWS = self.TIME_WINDOWS = [4, 12, 24, 48, 72, 96]  # Add 24, 48, 72 hours
        if self.PART_TYPES is None:
            self.PART_TYPES = ['PLSCR', 'SLD', 'LNRCAT', 'LNRTSG', 'SLVCAT', 'HUB', 'LID', 'SNZZL']
        if self.PILOT_COLUMNS is None:
            self.PILOT_COLUMNS = ["CCMR2", "ICCR2", "GF", "CV", "SRCIP"]
        if self.LEAK_BY_GASES is None:
            # Exclude BCL3, AR_LO, and SiCL4 as requested
            self.LEAK_BY_GASES = ['AR', 'C4F8_IGI', 'CF4', 'CH3F', 'CH4', 'CHF3', 'CL2', 'CL2_HI', 
                                 'COS', 'H2', 'HBr', 'HBR', 'HE', 'N2_HI', 'N2_LO', 'NF3', 'O2', 'O2_IGI']
        if self.SPC_MONITOR_TYPES is None:
            self.SPC_MONITOR_TYPES = ['ADDED_CLUSTERS', 'ADDED_CLUSTER_AREA', 'LARGE_ADDERS', 'TOTAL_ADDERS']

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Union, List, Tuple

class DataUtils:
    """Utility functions for common data processing tasks"""
    
    @staticmethod
    def safe_datetime_convert(df: pd.DataFrame, column: str) -> pd.DataFrame:
        """Safely convert column to datetime with error handling"""
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors='coerce')
        return df
    
    @staticmethod
    def filter_by_entity_and_time(df: pd.DataFrame, entity: str, end_time, 
                                  entity_col: str = 'SUBENTITY', 
                                  time_col: str = 'START_DATETIME') -> pd.DataFrame:
        """Common pattern for filtering by entity and time"""
        return df[(df[entity_col] == entity) & (df[time_col] <= end_time)]
    
    @staticmethod
    def progress_apply(df: pd.DataFrame, func, desc: str = "Processing", **kwargs):
        """Apply function with progress bar"""
        try:
            from tqdm import tqdm
            tqdm.pandas(desc=desc)
            return df.progress_apply(func, **kwargs)
        except ImportError:
            logging.warning("tqdm not available, using regular apply")
            return df.apply(func, **kwargs)
    
    @staticmethod
    def classify_sum_ncdd(value: float) -> str:
        """Classify SUM_NCDD values into categories"""
        if pd.isna(value):
            return 'UNKNOWN'
        elif value == 0:
            return 'ZERO'
        elif 0 < value < 0.02:
            return 'BSL'
        else:  # value >= 0.02
            return 'HIGHFLIER'


    @staticmethod
    def batch_process(df: pd.DataFrame, process_func: Callable, 
                     batch_size: int = 1000, desc: str = "Processing") -> pd.DataFrame:
        """Process dataframe in batches for better memory management"""
        total_rows = len(df)
        
        try:
            from tqdm import tqdm
            batch_iterator = tqdm(range(0, total_rows, batch_size), desc=desc)
        except ImportError:
            batch_iterator = range(0, total_rows, batch_size)
        
        for start_idx in batch_iterator:
            end_idx = min(start_idx + batch_size, total_rows)
            batch = df.iloc[start_idx:end_idx]
            
            # Process batch
            process_func(batch, start_idx, end_idx)
        
        return df
    
    @staticmethod
    def memory_usage_mb(df: pd.DataFrame) -> float:
        """Calculate dataframe memory usage in MB"""
        return df.memory_usage(deep=True).sum() / 1024 / 1024
    
    @staticmethod
    def optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
        """Optimize dataframe dtypes to reduce memory usage"""
        original_memory = DataUtils.memory_usage_mb(df)
        
        # Optimize numeric columns
        for col in df.select_dtypes(include=['int64']).columns:
            df[col] = pd.to_numeric(df[col], downcast='integer')
        
        for col in df.select_dtypes(include=['float64']).columns:
            df[col] = pd.to_numeric(df[col], downcast='float')
        
        # Convert object columns to category if they have few unique values
        for col in df.select_dtypes(include=['object']).columns:
            if df[col].nunique() / len(df) < 0.5:  # Less than 50% unique values
                df[col] = df[col].astype('category')
        
        new_memory = DataUtils.memory_usage_mb(df)
        logging.info(f"Memory optimization: {original_memory:.1f}MB -> {new_memory:.1f}MB "
                    f"({(1-new_memory/original_memory)*100:.1f}% reduction)")
        
        return df

class ProcessorBase:
    """Enhanced base class for all data processors"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._processing_stats = {}
    
    def safe_load_csv(self, file_path: str) -> Optional[pd.DataFrame]:
        """Safely load CSV with error handling and basic optimization"""
        try:
            start_time = datetime.now()
            
            # Try to load with optimal dtypes
            df = pd.read_csv(file_path, low_memory=False)
            
            load_time = (datetime.now() - start_time).total_seconds()
            memory_mb = DataUtils.memory_usage_mb(df)
            
            self.logger.info(f"Successfully loaded {file_path}")
            self.logger.info(f"  Shape: {df.shape}")
            self.logger.info(f"  Memory: {memory_mb:.1f}MB")
            self.logger.info(f"  Load time: {load_time:.1f}s")
            
            # Store stats
            self._processing_stats['load_time'] = load_time
            self._processing_stats['memory_mb'] = memory_mb
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to load {file_path}: {e}")
            return None
    
    def validate_required_columns(self, df: pd.DataFrame, required_cols: List[str]) -> bool:
        """Validate that required columns exist"""
        if df is None:
            return False
        
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            self.logger.error(f"Missing required columns: {missing}")
            self.logger.info(f"Available columns: {sorted(df.columns)}")
            return False
        
        self.logger.info(f"All required columns present: {required_cols}")
        return True
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics for this processor"""
        return self._processing_stats.copy()
    
    def log_processing_summary(self, df: pd.DataFrame, operation: str):
        """Log summary of processing operation"""
        self.logger.info(f"\n{operation} Summary:")
        self.logger.info(f"  Final shape: {df.shape}")
        self.logger.info(f"  Memory usage: {DataUtils.memory_usage_mb(df):.1f}MB")
        
        if 'load_time' in self._processing_stats:
            self.logger.info(f"  Load time: {self._processing_stats['load_time']:.1f}s")
    
    


class TimeBasedLookupProcessor(ProcessorBase, ABC):
    """Base class for processors that perform time-based lookups against chamber data"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.data_df = None
        self.chamber_data = {}
        self.entity_col = 'SUBENTITY'
        self.time_col = 'TIME'
        self._lookup_cache = {}  # Add caching for performance
    
    @abstractmethod
    def get_required_columns(self) -> List[str]:
        """Return list of required columns for this processor"""
        pass
    
    @abstractmethod
    def get_file_path(self) -> str:
        """Return the file path for this processor's data"""
        pass
    
    def get_time_column(self) -> str:
        """Override this if your time column has a different name"""
        return self.time_col
    
    def load_and_prepare_data(self) -> bool:
        """Load data and prepare for lookups"""
        self.logger.info(f"Loading {self.__class__.__name__} data...")
        
        # Load data
        self.data_df = self.safe_load_csv(self.get_file_path())
        if self.data_df is None:
            return False
        
        # Validate required columns
        if not self.validate_required_columns(self.data_df, self.get_required_columns()):
            return False
        
        self.logger.info(f"{self.__class__.__name__} DataFrame shape: {self.data_df.shape}")
        
        # Convert time column to datetime
        time_col = self.get_time_column()
        self.data_df = DataUtils.safe_datetime_convert(self.data_df, time_col)
        
        # Custom preprocessing hook
        self._custom_preprocessing()
        
        # Prepare chamber-based lookup
        self._prepare_chamber_lookup()
        
        return True
    
    def _custom_preprocessing(self):
        """Override this for processor-specific preprocessing"""
        pass
    
    def _prepare_chamber_lookup(self):
        """Prepare chamber-grouped data for efficient lookups"""
        self.logger.info(f"Preparing {self.__class__.__name__} chamber lookup data...")
        
        time_col = self.get_time_column()
        
        # Sort for efficient lookup
        self.data_df = self.data_df.sort_values([self.entity_col, time_col])
        
        # Group by chamber for efficient lookup
        for chamber in self.data_df[self.entity_col].unique():
            chamber_data = self.data_df[self.data_df[self.entity_col] == chamber].copy()
            self.chamber_data[chamber] = chamber_data
        
        self.logger.info(f"Prepared lookup data for {len(self.chamber_data)} chambers")
    
    def get_most_recent_before_time(self, subentity: str, reference_time, 
                                   filter_func: Optional[Callable] = None, 
                                   debug: bool = False) -> Optional[pd.Series]:
        """Get most recent data before reference time with optional filtering"""
        if pd.isna(reference_time) or pd.isna(subentity):
            if debug:
                self.logger.debug(f"Missing subentity or time: {subentity}, {reference_time}")
            return None
        
        # Check cache first
        cache_key = (subentity, reference_time, str(filter_func) if filter_func else None)
        if cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]
        
        # Check if chamber has data
        if subentity not in self.chamber_data:
            if debug:
                self.logger.debug(f"No data found for chamber {subentity}")
            self._lookup_cache[cache_key] = None
            return None
        
        chamber_data = self.chamber_data[subentity]
        time_col = self.get_time_column()
        
        # Apply custom filter if provided
        if filter_func:
            chamber_data = chamber_data[filter_func(chamber_data)]
        
        # Filter for data before reference time
        valid_data = chamber_data[chamber_data[time_col] <= reference_time]
        
        if debug:
            self.logger.debug(f"Valid measurements (before {reference_time}): {len(valid_data)}")
        
        if valid_data.empty:
            if debug:
                self.logger.debug(f"No measurements before {reference_time}")
            self._lookup_cache[cache_key] = None
            return None
        
        # Return most recent
        most_recent = valid_data.loc[valid_data[time_col].idxmax()]
        
        if debug:
            self.logger.debug(f"Most recent measurement time: {most_recent[time_col]}")
        
        # Cache result
        self._lookup_cache[cache_key] = most_recent
        return most_recent
    
    def clear_cache(self):
        """Clear lookup cache to free memory"""
        self._lookup_cache.clear()
        
        
class ColumnManager:
    """Helper class for managing dataframe columns and categorical operations"""
    
    @staticmethod
    def add_columns_batch(df: pd.DataFrame, column_specs: Dict[str, Any]) -> pd.DataFrame:
        """Add multiple columns at once with specified default values"""
        for col_name, default_val in column_specs.items():
            df[col_name] = default_val
        return df
    
    @staticmethod
    def create_ncdd_derived_columns(df: pd.DataFrame, source_col: str, 
                                   threshold: float, suffix: str = '') -> pd.DataFrame:
        """Create STATUS, CLASS, and ZERO columns from an NCDD source column"""
        
        # Determine column names
        status_col = f'STATUS_{suffix}' if suffix else 'STATUS'
        class_col = f'CLASS_{suffix}' if suffix else 'CLASS'
        zero_col = f'ZERO_{suffix}' if suffix else 'ZERO_NCDD'
        
        # Convert to numeric
        numeric_values = pd.to_numeric(df[source_col], errors='coerce')
        
        # Create STATUS column
        df[status_col] = pd.Categorical(
            numeric_values.apply(lambda x: 'BSL' if pd.notna(x) and x < threshold else 'HIGHFLIER'),
            categories=['BSL', 'HIGHFLIER']
        )
        
        # Create CLASS column
        df[class_col] = pd.Categorical(
            numeric_values.apply(lambda x: ColumnManager._classify_ncdd_value(x, threshold)),
            categories=['ZERO', 'BSL', 'HIGHFLIER', 'UNKNOWN']
        )
        
        # Create ZERO column
        df[zero_col] = numeric_values.apply(lambda x: x == 0)
        
        return df
    
    @staticmethod
    def _classify_ncdd_value(value: float, threshold: float) -> str:
        """Generic NCDD classification logic"""
        if pd.isna(value):
            return 'UNKNOWN'
        elif value == 0:
            return 'ZERO'
        elif 0 < value < threshold:
            return 'BSL'
        else:
            return 'HIGHFLIER'
    
    @staticmethod
    def create_binary_flags(df: pd.DataFrame, source_col: str, 
                           lookback_periods: List[int], 
                           col_prefix: str) -> pd.DataFrame:
        """Create binary flag columns for different lookback periods"""
        for period in lookback_periods:
            col_name = f'{col_prefix}_{period}'
            hours_threshold = period * 24
            
            # Create binary flag: 1 if within threshold, 0 otherwise
            df[col_name] = df[source_col].apply(
                lambda x: 0 if pd.isna(x) or x > hours_threshold else 1
            )
        
        return df
    
    @staticmethod
    def reorder_columns(df: pd.DataFrame, priority_columns: List[str]) -> pd.DataFrame:
        """Reorder dataframe columns with priority columns first"""
        existing_priority_cols = [col for col in priority_columns if col in df.columns]
        remaining_cols = [col for col in df.columns if col not in priority_columns]
        return df[existing_priority_cols + remaining_cols]
    
    @staticmethod
    def show_column_summary(df: pd.DataFrame, columns: List[str], logger):
        """Show summary statistics for specified columns"""
        logger.info(f"\nColumn Summary:")
        total_rows = len(df)
        
        for col in columns:
            if col in df.columns:
                non_null_count = df[col].notna().sum()
                null_count = df[col].isna().sum()
                
                logger.info(f"{col}:")
                logger.info(f"  Non-null: {non_null_count}/{total_rows} ({non_null_count/total_rows*100:.1f}%)")
                logger.info(f"  Null: {null_count}/{total_rows} ({null_count/total_rows*100:.1f}%)")
                
                if non_null_count > 0:
                    if df[col].dtype in ['int64', 'float64']:
                        logger.info(f"  Range: {df[col].min():.4f} to {df[col].max():.4f}")
                        logger.info(f"  Mean: {df[col].mean():.4f}")
                    elif df[col].dtype == 'object' or pd.api.types.is_categorical_dtype(df[col]):
                        value_counts = df[col].value_counts().head(5)
                        logger.info(f"  Top values: {value_counts.to_dict()}")
                        
                        
                        
        


class DataValidator:
    """Data validation utilities"""
    
    @staticmethod
    def validate_dataframe(df: pd.DataFrame, name: str) -> bool:
        """Basic dataframe validation"""
        if df is None or df.empty:
            logging.error(f"{name} is empty or None")
            return False
        logging.info(f"{name} validation passed: {df.shape}")
        return True
    
    @staticmethod
    def validate_time_columns(df: pd.DataFrame, time_cols: List[str]) -> bool:
        """Validate time columns are properly formatted"""
        for col in time_cols:
            if col in df.columns:
                if not pd.api.types.is_datetime64_any_dtype(df[col]):
                    logging.warning(f"Column {col} is not datetime type")
                    return False
        return True


class SPCMonitorProcessor(ProcessorBase):
    """SPC surf scan particle monitor data processor"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.spc_df = None
        self.chamber_monitor_data = {}
        
        # Define control limits for classification
        self.control_limits = {
            'TOTAL_ADDERS': {'centerline': 0.7, 'upper_limit': 4.01, 'levels': 4},
            'LARGE_ADDERS': {'centerline': 0.39, 'upper_limit': 2.01, 'levels': 4},
            'ADDED_CLUSTERS': {'centerline': 0, 'upper_limit': 1.1, 'levels': 3},
            'ADDED_CLUSTER_AREA': {'centerline': 0, 'upper_limit': 1.0, 'levels': 3}
        }
    
    def load_data(self) -> bool:
        """Load SPC monitor data"""
        self.logger.info("Loading SPC surf scan particle monitor data...")
        self.spc_df = self.safe_load_csv(self.config.SPC_MONITOR_PATH)
        
        if self.spc_df is None:
            return False
        
        # Updated required columns to include MA6 and MA9
        if not self.validate_required_columns(self.spc_df, ['SUBENTITY', 'DATE', 'SIZE', 'VALUE', 'MA3', 'MA6', 'MA9']):
            return False
        
        self.logger.info(f"SPC Monitor DataFrame shape: {self.spc_df.shape}")
        
        # Convert date column to datetime
        self.spc_df = DataUtils.safe_datetime_convert(self.spc_df, 'DATE')
        
        # Show monitor type distribution
        self._show_monitor_distribution()
        
        # Prepare lookup data
        self._prepare_lookup_data()
        
        return True
    
    def _show_monitor_distribution(self):
        """Show monitor type distribution in the data"""
        self.logger.info(f"\nSPC Monitor type distribution:")
        size_counts = self.spc_df['SIZE'].value_counts()
        for monitor_type in self.config.SPC_MONITOR_TYPES:
            count = size_counts.get(monitor_type, 0)
            self.logger.info(f"  {monitor_type}: {count} measurements")
        
        # Show chamber coverage
        unique_chambers = self.spc_df['SUBENTITY'].nunique()
        self.logger.info(f"\nUnique chambers with SPC monitor data: {unique_chambers}")
    
    def _prepare_lookup_data(self):
        """Prepare data for efficient lookups by chamber and monitor type"""
        self.logger.info("Preparing SPC monitor lookup data...")
        
        # Sort by SUBENTITY, SIZE, and DATE for efficient lookup
        self.spc_df = self.spc_df.sort_values(['SUBENTITY', 'SIZE', 'DATE'])
        
        # Create chamber-monitor type grouped data for efficient lookup
        for chamber in self.spc_df['SUBENTITY'].unique():
            chamber_data = self.spc_df[self.spc_df['SUBENTITY'] == chamber]
            self.chamber_monitor_data[chamber] = {}
            
            for monitor_type in self.config.SPC_MONITOR_TYPES:
                monitor_data = chamber_data[chamber_data['SIZE'] == monitor_type].copy()
                if not monitor_data.empty:
                    self.chamber_monitor_data[chamber][monitor_type] = monitor_data
    
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
    
    def get_most_recent_monitor_values(self, subentity: str, subentity_end_time, monitor_type: str, debug: bool = False) -> Tuple[float, float, float, float]:
        """Get the most recent monitor values (raw VALUE, MA3, MA6, MA9) for a specific monitor type"""
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                self.logger.debug(f"Missing subentity or time: {subentity}, {subentity_end_time}")
            return np.nan, np.nan, np.nan, np.nan
        
        # Check if chamber has data for this monitor type
        if subentity not in self.chamber_monitor_data:
            if debug:
                self.logger.debug(f"No SPC monitor data found for chamber {subentity}")
            return np.nan, np.nan, np.nan, np.nan
        
        if monitor_type not in self.chamber_monitor_data[subentity]:
            if debug:
                self.logger.debug(f"No {monitor_type} data found for chamber {subentity}")
            return np.nan, np.nan, np.nan, np.nan
        
        monitor_data = self.chamber_monitor_data[subentity][monitor_type]
        
        if debug:
            self.logger.debug(f"SPC monitor measurements found for {subentity} {monitor_type}: {len(monitor_data)}")
        
        # Filter for measurements before or at the subentity end time
        valid_measurements = monitor_data[monitor_data['DATE'] <= subentity_end_time]
        
        if debug:
            self.logger.debug(f"Valid measurements (before {subentity_end_time}): {len(valid_measurements)}")
            if len(valid_measurements) > 0:
                self.logger.debug(f"Latest valid measurement time: {valid_measurements['DATE'].max()}")
        
        if valid_measurements.empty:
            if debug:
                self.logger.debug(f"No {monitor_type} measurements before {subentity_end_time}")
            return np.nan, np.nan, np.nan, np.nan
        
        # Get the most recent measurement
        most_recent = valid_measurements.loc[valid_measurements['DATE'].idxmax()]
        raw_value = most_recent['VALUE']
        ma3_value = most_recent['MA3']
        ma6_value = most_recent['MA6']
        ma9_value = most_recent['MA9']
        
        if debug:
            self.logger.debug(f"Most recent {monitor_type} measurement time: {most_recent['DATE']}")
            self.logger.debug(f"{monitor_type} raw value: {raw_value}")
            self.logger.debug(f"{monitor_type} MA3 value: {ma3_value}")
            self.logger.debug(f"{monitor_type} MA6 value: {ma6_value}")
            self.logger.debug(f"{monitor_type} MA9 value: {ma9_value}")
        
        return raw_value, ma3_value, ma6_value, ma9_value
    
    def _create_control_classifications(self, dt: pd.DataFrame):
        """Create control limit based classifications for all SPC monitor columns"""
        self.logger.info("Creating control limit classifications...")
        
        # Get all monitor columns (raw + moving averages)
        all_monitor_cols = []
        for base_monitor in self.control_limits.keys():
            # Raw values
            if base_monitor in dt.columns:
                all_monitor_cols.append(base_monitor)
            # Moving averages
            for ma_suffix in ['_MA3', '_MA6', '_MA9']:
                ma_col = base_monitor + ma_suffix
                if ma_col in dt.columns:
                    all_monitor_cols.append(ma_col)
        
        # Apply classifications
        for col in all_monitor_cols:
            # Determine base monitor type
            base_monitor = col.split('_MA')[0]  # Remove MA suffix if present
            
            if base_monitor in self.control_limits:
                limits = self.control_limits[base_monitor]
                
                if limits['levels'] == 4:
                    # 4-level classification
                    dt[f'{col}_CLASS'] = dt[col].apply(
                        lambda x: self._classify_4_level(x, limits['centerline'], limits['upper_limit'])
                    )
                else:
                    # 3-level classification  
                    dt[f'{col}_CLASS'] = dt[col].apply(
                        lambda x: self._classify_3_level(x, limits['upper_limit'])
                    )
        
        # Show classification summary
        self._show_classification_summary(dt, all_monitor_cols)
    
    def _show_classification_summary(self, dt: pd.DataFrame, monitor_cols: List[str]):
        """Show summary of control limit classifications"""
        self.logger.info("\nControl Limit Classification Summary:")
        
        for col in monitor_cols:
            class_col = f'{col}_CLASS'
            if class_col in dt.columns:
                class_counts = dt[class_col].value_counts().sort_index()
                total_valid = dt[class_col].notna().sum()
                
                self.logger.info(f"\n{col} Classifications:")
                for level, count in class_counts.items():
                    pct = (count / total_valid * 100) if total_valid > 0 else 0
                    level_name = self._get_level_name(col, int(level))
                    self.logger.info(f"  Level {int(level)} ({level_name}): {count} ({pct:.1f}%)")
    
    def _get_level_name(self, col: str, level: int) -> str:
        """Get descriptive name for classification level"""
        base_monitor = col.split('_MA')[0]
        
        if base_monitor in ['TOTAL_ADDERS', 'LARGE_ADDERS']:
            level_names = {0: 'Zero', 1: 'Low', 2: 'Medium', 3: 'High/OOC'}
        else:  # ADDED_CLUSTERS, ADDED_CLUSTER_AREA
            level_names = {0: 'Zero', 1: 'Normal', 2: 'High/OOC'}
        
        return level_names.get(level, 'Unknown')
    
    def add_spc_monitor_data(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add SPC monitor data to the main dataframe"""
        if not self.load_data():
            self.logger.error("Failed to load SPC monitor data")
            return dt
        
        # Initialize new columns for each monitor type (raw, MA3, MA6, MA9)
        for monitor_type in self.config.SPC_MONITOR_TYPES:
            dt[monitor_type] = np.nan
            dt[f'{monitor_type}_MA3'] = np.nan
            dt[f'{monitor_type}_MA6'] = np.nan
            dt[f'{monitor_type}_MA9'] = np.nan
        
        # Test with sample data
        self._test_spc_monitor_lookup(dt)
        
        # Process all rows
        self._process_all_spc_monitors(dt)
        
        # Create control limit classifications
        self._create_control_classifications(dt)
        
        # Show summary
        self._show_spc_monitor_summary(dt)
        
        return dt
    
    def _test_spc_monitor_lookup(self, dt: pd.DataFrame):
        """Test SPC monitor lookup with sample data"""
        self.logger.info("\n=== TESTING SPC MONITOR LOOKUP ===")
        
        # Try to find rows with subentities that have SPC monitor data
        test_subentities = list(self.chamber_monitor_data.keys())[:3]
        test_rows = dt[dt['SUBENTITY'].isin(test_subentities)].head(3)
        
        if test_rows.empty:
            test_rows = dt.head(3)
        
        for idx in test_rows.index:
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            self.logger.info(f"\nRow {idx}: {subentity} at {subentity_end_time}")
            
            # Test a few monitor types
            test_monitors = ['ADDED_CLUSTERS', 'TOTAL_ADDERS']
            for monitor_type in test_monitors:
                raw_value, ma3_value, ma6_value, ma9_value = self.get_most_recent_monitor_values(subentity, subentity_end_time, monitor_type, debug=True)
                if pd.isna(raw_value):
                    self.logger.info(f"  {monitor_type}: NaN (no measurement found)")
                else:
                    self.logger.info(f"  {monitor_type}: {raw_value} (MA3: {ma3_value}, MA6: {ma6_value}, MA9: {ma9_value})")
        
        self.logger.info("=== END TEST ===\n")
    
    def _process_all_spc_monitors(self, dt: pd.DataFrame):
        """Process SPC monitor measurements for all rows"""
        self.logger.info("Processing SPC monitor measurements for all defect scans...")
        
        for idx in dt.index:
            if idx % 100 == 0:
                self.logger.info(f"Processing row {idx}/{len(dt)}")
            
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            # Get monitor values for each type
            for monitor_type in self.config.SPC_MONITOR_TYPES:
                raw_value, ma3_value, ma6_value, ma9_value = self.get_most_recent_monitor_values(subentity, subentity_end_time, monitor_type, debug=False)
                dt.at[idx, monitor_type] = raw_value
                dt.at[idx, f'{monitor_type}_MA3'] = ma3_value
                dt.at[idx, f'{monitor_type}_MA6'] = ma6_value
                dt.at[idx, f'{monitor_type}_MA9'] = ma9_value
        
        self.logger.info("SPC monitor processing complete!")
    
    def _show_spc_monitor_summary(self, dt: pd.DataFrame):
        """Show SPC monitor processing summary"""
        self.logger.info(f"\nSPC Monitor Summary:")
        
        for monitor_type in self.config.SPC_MONITOR_TYPES:
            raw_col = monitor_type
            ma3_col = f'{monitor_type}_MA3'
            ma6_col = f'{monitor_type}_MA6'
            ma9_col = f'{monitor_type}_MA9'
            
            raw_non_null = dt[raw_col].notna().sum()
            ma3_non_null = dt[ma3_col].notna().sum()
            ma6_non_null = dt[ma6_col].notna().sum()
            ma9_non_null = dt[ma9_col].notna().sum()
            total_count = len(dt)
            
            self.logger.info(f"{raw_col} - Non-null values: {raw_non_null}/{total_count} ({raw_non_null/total_count*100:.1f}%)")
            self.logger.info(f"{ma3_col} - Non-null values: {ma3_non_null}/{total_count} ({ma3_non_null/total_count*100:.1f}%)")
            self.logger.info(f"{ma6_col} - Non-null values: {ma6_non_null}/{total_count} ({ma6_non_null/total_count*100:.1f}%)")
            self.logger.info(f"{ma9_col} - Non-null values: {ma9_non_null}/{total_count} ({ma9_non_null/total_count*100:.1f}%)")
            
            if raw_non_null > 0:
                valid_raw = dt[dt[raw_col].notna()][raw_col]
                self.logger.info(f"  {raw_col} Range: {valid_raw.min():.4f} to {valid_raw.max():.4f}")
                self.logger.info(f"  {raw_col} Mean: {valid_raw.mean():.4f}")
                
                # Show non-zero count
                non_zero_count = (valid_raw > 0).sum()
                if non_zero_count > 0:
                    self.logger.info(f"  {raw_col} Non-zero values: {non_zero_count} ({non_zero_count/raw_non_null*100:.1f}%)")

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


class DefectDataProcessor(ProcessorBase):
    """Main defect data processor that orchestrates all processing steps"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        # Initialize processors based on config flags
        self.elwc_processor = OptimizedELWCProcessor(config) if config.ENABLE_ELWC else None
        self.dp_processor = RefactoredDryPumpProcessor(config) if config.ENABLE_DRY_PUMP else None
        self.leak_processor = RefactoredLeakRateProcessor(config) if config.ENABLE_LEAK_RATE else None
        self.leak_by_processor = LeakByProcessor(config) if config.ENABLE_LEAK_BY else None
        self.spc_monitor_processor = SPCMonitorProcessor(config) if config.ENABLE_SPC_MONITOR else None
        
        # Log which processors are enabled
        self._log_processor_status()
    
    def _log_processor_status(self):
        """Log which processors are enabled/disabled"""
        self.logger.info("=== PROCESSOR STATUS ===")
        processors = [
            ("ELWC Lookbacks", self.config.ENABLE_ELWC),
            ("Dry Pump Failures", self.config.ENABLE_DRY_PUMP),
            ("Leak Rates", self.config.ENABLE_LEAK_RATE),
            ("Leak By (Gas-specific)", self.config.ENABLE_LEAK_BY),
            ("SPC Monitors", self.config.ENABLE_SPC_MONITOR),
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
                         
        # NEW: Test ColumnManager for NCDD derived columns
        self.logger.info("Testing new ColumnManager for NCDD derived columns...")
        dt = ColumnManager.create_ncdd_derived_columns(dt, 'SUM_NCDD', 0.02)
        dt = ColumnManager.create_ncdd_derived_columns(dt, 'BEEP_NCDD', 0.0094, 'BEEP')
        dt = ColumnManager.create_ncdd_derived_columns(dt, 'SMP_NCDD', 0.013, 'SMP')
        
        # NEW: Create N_SCAN column (number of wafers scanned per LAYER+LOT combination)
        self.logger.info("Creating N_SCAN column (wafers scanned per LAYER+LOT)...")
        dt['N_SCAN'] = dt.groupby(['LAYER', 'LOT']).transform('size')
        
        # Show memory usage
        memory_mb = DataUtils.memory_usage_mb(dt)
        self.logger.info(f"Current dataframe memory usage: {memory_mb:.1f}MB")
        
        # Show N_SCAN statistics
        self.logger.info(f"N_SCAN statistics:")
        self.logger.info(f"  Range: {dt['N_SCAN'].min()} to {dt['N_SCAN'].max()} wafers per LAYER+LOT")
        self.logger.info(f"  Mean: {dt['N_SCAN'].mean():.1f} wafers per LAYER+LOT")
        self.logger.info(f"  Unique N_SCAN values: {sorted(dt['N_SCAN'].unique())}")
        
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
        
        leak_by_cols = []
        if self.config.ENABLE_LEAK_BY:
            leak_by_cols = [f'LB_{gas}' for gas in self.config.LEAK_BY_GASES]
        
        # SPC Monitor columns (raw, MA3, MA6, MA9)
        spc_monitor_cols = []
        if self.config.ENABLE_SPC_MONITOR:
            for monitor_type in self.config.SPC_MONITOR_TYPES:
                spc_monitor_cols.extend([monitor_type, f'{monitor_type}_MA3', f'{monitor_type}_MA6', f'{monitor_type}_MA9'])
        
        # Base columns - UPDATED to include N_SCAN and new stepper and SIF columns
        desired_order = [
            'LOT', 'WAFER_ID', 'PRODUCT', 'ROUTE', 'LAYER', 'DEVICE', 'SUBENTITY', 'OPERATION','RECIPE', 
            'SUBENTITY_END_TIME','PILOT_STATUS', 'N_SCAN', 'SUM_NCDD', 'STATUS', 'CLASS',  'ZERO_NCDD', 'INSPECT_TIME', 
            'INSPECT_TOOL', 
            'BEEP_NCDD', 'STATUS_BEEP', 'CLASS_BEEP', 'ZERO_BEEP',  # BEEP columns grouped together
            'SMP_NCDD', 'STATUS_SMP', 'CLASS_SMP', 'ZERO_SMP',      # SMP columns grouped together
            'STEPPER', 'RETICLE', 'SIF_SED', 'SIF_ETCH', 'SIF_DEFECT',  # NEW stepper and SIF columns
            'ENTITY', 'LOT7', 'WAFER', 'SLOT', 'P_ORDER',
            'CCMR2', 'ICCR2', 'GF', 'CV', 'SRCIP', 'FULLPM', 'FULLPM_RF', 'MINIPM', 'MINIPM_RF', 
            'CNTR_SS', 'PL_RECIPE', 'PT_BTWN', 'PL_TIME', 'UPT_12HRS', 'UNW_12HRS', 'UP_12HRS'
        ]
        
        # Add optional columns based on enabled processors
        if self.config.ENABLE_RECOAT:
            desired_order.extend(self.config.PART_TYPES + ['RECOAT'])
        
        if self.config.ENABLE_LEAK_RATE:
            desired_order.extend(['RAW_LEAK_RATE', 'SMOOTH_LEAK_RATE'])
        
        if self.config.ENABLE_DRY_PUMP:
            desired_order.append('DP_FAIL_HRS')
        
        desired_order.extend(leak_by_cols + spc_monitor_cols + elwc_lookback_cols)
        
        # Reorder columns
        existing_priority_cols = [col for col in desired_order if col in dt.columns]
        remaining_cols = [col for col in dt.columns if col not in desired_order]
        dt = dt[existing_priority_cols + remaining_cols]
        
        return dt
    
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
            
            if self.config.ENABLE_ELWC and self.elwc_processor:
                dt = self.elwc_processor.add_elwc_lookbacks_optimized(dt)
            else:
                self.logger.info("ELWC lookback processing SKIPPED")
            
            # Finalize
            dt = self._finalize_dataframe(dt)
            
            self.logger.info("Processing complete!")
            self.logger.info(f"Final dataframe shape: {dt.shape}")
            
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
            ENABLE_LEAK_RATE=True,
            ENABLE_DRY_PUMP=True,
            ENABLE_LEAK_BY=True,
            ENABLE_SPC_MONITOR=True,
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
                
        # Add this after the existing summaries in main():
        # Show N_SCAN column summary
        if 'N_SCAN' in result_df.columns:
            logging.info(f"\nN_SCAN column summary:")
            n_scan_stats = result_df['N_SCAN'].describe()
            logging.info(f"N_SCAN statistics: {n_scan_stats}")
            n_scan_counts = result_df['N_SCAN'].value_counts().sort_index()
            logging.info(f"N_SCAN distribution: {n_scan_counts.to_dict()}")
                
        
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