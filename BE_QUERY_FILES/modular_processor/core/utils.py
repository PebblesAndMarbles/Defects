# -*- coding: utf-8 -*-
"""
Utility functions and classes for data processing
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime
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


