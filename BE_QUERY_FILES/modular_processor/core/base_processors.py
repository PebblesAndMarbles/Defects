# -*- coding: utf-8 -*-
"""
Base processor classes providing common functionality
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Union, List, Tuple

from core.config import Config
from core.utils import DataUtils

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
        
        
