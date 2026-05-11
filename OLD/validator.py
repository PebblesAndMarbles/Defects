# -*- coding: utf-8 -*-
"""
DataFrame Validation Script
Comprehensive comparison of PRE and POST refactor outputs
"""
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any
import os

class DataFrameValidator:
    """Comprehensive DataFrame validation and comparison"""
    
    def __init__(self, pre_path: str, post_path: str):
        self.pre_path = pre_path
        self.post_path = post_path
        self.pre_df = None
        self.post_df = None
        self.validation_results = {}
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def load_dataframes(self) -> bool:
        """Load both PRE and POST dataframes"""
        self.logger.info("=== DATAFRAME VALIDATION SCRIPT ===")
        self.logger.info(f"PRE-refactor file: {self.pre_path}")
        self.logger.info(f"POST-refactor file: {self.post_path}")
        
        # Load PRE dataframe
        try:
            if os.path.exists(self.pre_path):
                start_time = datetime.now()
                self.pre_df = pd.read_csv(self.pre_path)
                load_time = (datetime.now() - start_time).total_seconds()
                self.logger.info(f"✅ PRE dataframe loaded: {self.pre_df.shape} in {load_time:.1f}s")
            else:
                self.logger.error(f"❌ PRE file not found: {self.pre_path}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Error loading PRE file: {str(e)}")
            return False
        
        # Load POST dataframe
        try:
            if os.path.exists(self.post_path):
                start_time = datetime.now()
                self.post_df = pd.read_csv(self.post_path)
                load_time = (datetime.now() - start_time).total_seconds()
                self.logger.info(f"✅ POST dataframe loaded: {self.post_df.shape} in {load_time:.1f}s")
            else:
                self.logger.error(f"❌ POST file not found: {self.post_path}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Error loading POST file: {str(e)}")
            return False
        
        return True
    
    def validate_basic_structure(self) -> Dict[str, Any]:
        """Validate basic DataFrame structure"""
        self.logger.info("\n=== BASIC STRUCTURE VALIDATION ===")
        
        results = {
            'shape_match': False,
            'row_count_match': False,
            'column_count_match': False,
            'pre_shape': self.pre_df.shape,
            'post_shape': self.post_df.shape
        }
        
        # Shape comparison
        if self.pre_df.shape == self.post_df.shape:
            results['shape_match'] = True
            results['row_count_match'] = True
            results['column_count_match'] = True
            self.logger.info(f"✅ Shape match: {self.pre_df.shape}")
        else:
            self.logger.error(f"❌ Shape mismatch:")
            self.logger.error(f"   PRE:  {self.pre_df.shape}")
            self.logger.error(f"   POST: {self.post_df.shape}")
            
            if self.pre_df.shape[0] == self.post_df.shape[0]:
                results['row_count_match'] = True
                self.logger.info(f"✅ Row count match: {self.pre_df.shape[0]}")
            else:
                self.logger.error(f"❌ Row count mismatch: {self.pre_df.shape[0]} vs {self.post_df.shape[0]}")
            
            if self.pre_df.shape[1] == self.post_df.shape[1]:
                results['column_count_match'] = True
                self.logger.info(f"✅ Column count match: {self.pre_df.shape[1]}")
            else:
                self.logger.error(f"❌ Column count mismatch: {self.pre_df.shape[1]} vs {self.post_df.shape[1]}")
        
        return results
    
    def validate_columns(self) -> Dict[str, Any]:
        """Validate column names and order"""
        self.logger.info("\n=== COLUMN VALIDATION ===")
        
        pre_cols = list(self.pre_df.columns)
        post_cols = list(self.post_df.columns)
        
        results = {
            'column_names_match': False,
            'column_order_match': False,
            'missing_in_post': [],
            'extra_in_post': [],
            'pre_columns': pre_cols,
            'post_columns': post_cols
        }
        
        # Column names comparison
        pre_set = set(pre_cols)
        post_set = set(post_cols)
        
        if pre_set == post_set:
            results['column_names_match'] = True
            self.logger.info(f"✅ Column names match: {len(pre_cols)} columns")
        else:
            results['missing_in_post'] = list(pre_set - post_set)
            results['extra_in_post'] = list(post_set - pre_set)
            
            if results['missing_in_post']:
                self.logger.error(f"❌ Missing in POST: {results['missing_in_post']}")
            if results['extra_in_post']:
                self.logger.error(f"❌ Extra in POST: {results['extra_in_post']}")
        
        # Column order comparison
        if pre_cols == post_cols:
            results['column_order_match'] = True
            self.logger.info("✅ Column order matches")
        else:
            self.logger.warning("⚠️ Column order differs")
            # Show first few differences
            for i, (pre_col, post_col) in enumerate(zip(pre_cols[:10], post_cols[:10])):
                if pre_col != post_col:
                    self.logger.warning(f"   Position {i}: '{pre_col}' vs '{post_col}'")
        
        return results
    
    def validate_data_content(self) -> Dict[str, Any]:
        """Validate actual data content"""
        self.logger.info("\n=== DATA CONTENT VALIDATION ===")
        
        results = {
            'identical_dataframes': False,
            'column_comparisons': {},
            'total_differences': 0,
            'columns_with_differences': []
        }
        
        # Get common columns
        common_cols = list(set(self.pre_df.columns) & set(self.post_df.columns))
        self.logger.info(f"Comparing {len(common_cols)} common columns...")
        
        total_diffs = 0
        cols_with_diffs = []
        
        for col in common_cols:
            col_result = self._compare_column(col)
            results['column_comparisons'][col] = col_result
            
            if not col_result['identical']:
                total_diffs += col_result['differences']
                cols_with_diffs.append(col)
        
        results['total_differences'] = total_diffs
        results['columns_with_differences'] = cols_with_diffs
        
        if total_diffs == 0:
            results['identical_dataframes'] = True
            self.logger.info("✅ All data content identical!")
        else:
            self.logger.error(f"❌ Found {total_diffs} differences across {len(cols_with_diffs)} columns")
        
        return results
    
    def _compare_column(self, col: str) -> Dict[str, Any]:
        """Compare a single column between dataframes"""
        pre_col = self.pre_df[col]
        post_col = self.post_df[col]
        
        result = {
            'identical': False,
            'differences': 0,
            'null_count_match': False,
            'dtype_match': False,
            'pre_dtype': str(pre_col.dtype),
            'post_dtype': str(post_col.dtype),
            'pre_nulls': pre_col.isnull().sum(),
            'post_nulls': post_col.isnull().sum()
        }
        
        # Check dtypes
        if pre_col.dtype == post_col.dtype:
            result['dtype_match'] = True
        
        # Check null counts
        if result['pre_nulls'] == result['post_nulls']:
            result['null_count_match'] = True
        
        # Compare values
        try:
            if pre_col.dtype in ['float64', 'float32']:
                # For float columns, use approximate comparison
                differences = ~np.isclose(pre_col, post_col, equal_nan=True, rtol=1e-10, atol=1e-10)
            else:
                # For other types, use exact comparison
                differences = (pre_col != post_col) & ~(pre_col.isnull() & post_col.isnull())
            
            diff_count = differences.sum()
            result['differences'] = diff_count
            
            if diff_count == 0:
                result['identical'] = True
            
        except Exception as e:
            self.logger.warning(f"⚠️ Could not compare column {col}: {str(e)}")
            result['differences'] = -1  # Indicates comparison error
        
        return result
    
    def validate_spc_columns(self) -> Dict[str, Any]:
        """Specifically validate SPC columns"""
        self.logger.info("\n=== SPC COLUMNS VALIDATION ===")
        
        # Expected SPC column patterns
        spc_patterns = [
            'CH_SS_', 'FL_SS_', 'CH_SS_DAYS'
        ]
        
        pre_spc_cols = [col for col in self.pre_df.columns if any(pattern in col for pattern in spc_patterns)]
        post_spc_cols = [col for col in self.post_df.columns if any(pattern in col for pattern in spc_patterns)]
        
        results = {
            'pre_spc_columns': pre_spc_cols,
            'post_spc_columns': post_spc_cols,
            'spc_columns_match': False,
            'spc_data_identical': False
        }
        
        self.logger.info(f"PRE SPC columns found: {len(pre_spc_cols)}")
        self.logger.info(f"POST SPC columns found: {len(post_spc_cols)}")
        
        if set(pre_spc_cols) == set(post_spc_cols):
            results['spc_columns_match'] = True
            self.logger.info("✅ SPC columns match")
            
            # Compare SPC data
            spc_diffs = 0
            for col in pre_spc_cols:
                if col in self.post_df.columns:
                    col_result = self._compare_column(col)
                    if not col_result['identical']:
                        spc_diffs += col_result['differences']
                        self.logger.warning(f"⚠️ SPC column {col}: {col_result['differences']} differences")
            
            if spc_diffs == 0:
                results['spc_data_identical'] = True
                self.logger.info("✅ All SPC data identical")
            else:
                self.logger.error(f"❌ SPC data differences: {spc_diffs}")
        else:
            self.logger.error("❌ SPC columns don't match")
            missing = set(pre_spc_cols) - set(post_spc_cols)
            extra = set(post_spc_cols) - set(pre_spc_cols)
            if missing:
                self.logger.error(f"   Missing in POST: {list(missing)}")
            if extra:
                self.logger.error(f"   Extra in POST: {list(extra)}")
        
        return results
    
    def generate_detailed_report(self) -> None:
        """Generate detailed validation report"""
        self.logger.info("\n=== DETAILED VALIDATION REPORT ===")
        
        # Summary
        structure_ok = self.validation_results['structure']['shape_match']
        columns_ok = self.validation_results['columns']['column_names_match']
        data_ok = self.validation_results['data']['identical_dataframes']
        spc_ok = self.validation_results['spc']['spc_data_identical']
        
        overall_status = structure_ok and columns_ok and data_ok and spc_ok
        
        self.logger.info(f"📊 OVERALL STATUS: {'✅ PASS' if overall_status else '❌ FAIL'}")
        self.logger.info(f"   Structure: {'✅' if structure_ok else '❌'}")
        self.logger.info(f"   Columns:   {'✅' if columns_ok else '❌'}")
        self.logger.info(f"   Data:      {'✅' if data_ok else '❌'}")
        self.logger.info(f"   SPC:       {'✅' if spc_ok else '❌'}")
        
        # Detailed breakdown
        if not overall_status:
            self.logger.info("\n📋 DETAILED ISSUES:")
            
            if not structure_ok:
                self.logger.info(f"   Structure: {self.validation_results['structure']['pre_shape']} vs {self.validation_results['structure']['post_shape']}")
            
            if not columns_ok:
                missing = self.validation_results['columns']['missing_in_post']
                extra = self.validation_results['columns']['extra_in_post']
                if missing:
                    self.logger.info(f"   Missing columns: {missing}")
                if extra:
                    self.logger.info(f"   Extra columns: {extra}")
            
            if not data_ok:
                total_diffs = self.validation_results['data']['total_differences']
                diff_cols = self.validation_results['data']['columns_with_differences']
                self.logger.info(f"   Data differences: {total_diffs} across {len(diff_cols)} columns")
                
                # Show top 10 columns with most differences
                col_diffs = [(col, self.validation_results['data']['column_comparisons'][col]['differences']) 
                           for col in diff_cols]
                col_diffs.sort(key=lambda x: x[1], reverse=True)
                
                self.logger.info("   Top columns with differences:")
                for col, diffs in col_diffs[:10]:
                    self.logger.info(f"     {col}: {diffs} differences")
        
        # Performance stats
        pre_memory = self.pre_df.memory_usage(deep=True).sum() / 1024**2
        post_memory = self.post_df.memory_usage(deep=True).sum() / 1024**2
        
        self.logger.info(f"\n📈 PERFORMANCE COMPARISON:")
        self.logger.info(f"   PRE memory:  {pre_memory:.1f} MB")
        self.logger.info(f"   POST memory: {post_memory:.1f} MB")
        self.logger.info(f"   Memory diff: {post_memory - pre_memory:+.1f} MB")
    
    def run_validation(self) -> bool:
        """Run complete validation suite"""
        start_time = datetime.now()
        
        # Load dataframes
        if not self.load_dataframes():
            return False
        
        # Run all validations
        self.validation_results['structure'] = self.validate_basic_structure()
        self.validation_results['columns'] = self.validate_columns()
        self.validation_results['data'] = self.validate_data_content()
        self.validation_results['spc'] = self.validate_spc_columns()
        
        # Generate report
        self.generate_detailed_report()
        
        # Final summary
        total_time = (datetime.now() - start_time).total_seconds()
        self.logger.info(f"\n⏱️ Validation completed in {total_time:.1f} seconds")
        
        # Return overall success
        return (self.validation_results['structure']['shape_match'] and 
                self.validation_results['columns']['column_names_match'] and 
                self.validation_results['data']['identical_dataframes'] and
                self.validation_results['spc']['spc_data_identical'])

def main():
    """Main validation function"""
    # File paths
    pre_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_2025 - Copy.csv"
    post_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_2025_REFACTORED.csv"  # Update this path
    
    # Run validation
    validator = DataFrameValidator(pre_path, post_path)
    success = validator.run_validation()
    
    if success:
        print("\n🎉 VALIDATION PASSED - Refactor is safe to deploy!")
        return 0
    else:
        print("\n⚠️ VALIDATION FAILED - Review issues before deploying refactor!")
        return 1

if __name__ == "__main__":
    exit(main())