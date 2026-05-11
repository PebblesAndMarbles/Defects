# -*- coding: utf-8 -*-
"""
Column management utilities for dataframe operations
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List

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
                        
                        
                        
        


