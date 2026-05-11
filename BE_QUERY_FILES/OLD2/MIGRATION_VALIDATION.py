# -*- coding: utf-8 -*-
"""
SAFE Migration Validation Script - Spyder Compatible
Enhanced with explicit column validation
"""

import pandas as pd
import numpy as np
import logging
import gc
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import warnings
warnings.filterwarnings('ignore')

class SafeMigrationValidator:
    """Memory-efficient, Spyder-safe validation of pre/post migration CSV files"""
    
    def __init__(self, pre_file_path: str, post_file_path: str):
        self.pre_file_path = pre_file_path
        self.post_file_path = post_file_path
        self.pre_df = None
        self.post_df = None
        self.logger = self._setup_safe_logging()
        
        # Safe parameters
        self.chunk_size = 1000  # Process in small chunks
        self.max_sample_diffs = 5  # Limit sample differences
        self.float_tolerance = 1e-10
        
        # EXPLICIT COLUMNS TO VALIDATE - These are critical!
        self.explicit_columns = [
            'SUM_NCDD',
            'RECOAT', 
            'SMOOTH_LEAK_RATE',
            'LB_COS',
            'ADDED_CLUSTERS_MA3',
            'LARGE_ADDERS_MA3', 
            'TOTAL_ADDERS_MA6',
            'MONTW_48HRS',
            '8GAB_72HRS',
            'DP_FAIL_60'
        ]
        
    def _setup_safe_logging(self):
        """Setup logging that won't crash Spyder"""
        logger = logging.getLogger('SafeValidator')
        logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Add only console handler (avoid file handler issues)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def safe_load_files(self) -> bool:
        """Safely load CSV files with memory management"""
        self.logger.info("=== LOADING FILES SAFELY ===")
        
        try:
            # Check file existence first
            if not Path(self.pre_file_path).exists():
                self.logger.error(f"PRE file not found: {self.pre_file_path}")
                return False
                
            if not Path(self.post_file_path).exists():
                self.logger.error(f"POST file not found: {self.post_file_path}")
                return False
            
            # Load PRE file
            self.logger.info("Loading PRE-migration file...")
            self.pre_df = pd.read_csv(self.pre_file_path, low_memory=False)
            self.logger.info(f"PRE shape: {self.pre_df.shape}")
            
            # Force garbage collection
            gc.collect()
            
            # Load POST file
            self.logger.info("Loading POST-migration file...")
            self.post_df = pd.read_csv(self.post_file_path, low_memory=False)
            self.logger.info(f"POST shape: {self.post_df.shape}")
            
            # Force garbage collection again
            gc.collect()
            
            return True
            
        except MemoryError:
            self.logger.error("MEMORY ERROR: Files too large for available memory")
            return False
        except Exception as e:
            self.logger.error(f"Error loading files: {str(e)[:200]}")  # Limit error message length
            return False
    
    def quick_structure_check(self) -> bool:
        """Quick structure validation without deep comparison"""
        self.logger.info("\n=== QUICK STRUCTURE CHECK ===")
        
        try:
            # Shape check
            if self.pre_df.shape != self.post_df.shape:
                self.logger.error(f"SHAPE MISMATCH: PRE {self.pre_df.shape} vs POST {self.post_df.shape}")
                return False
            else:
                self.logger.info(f"✓ Shapes match: {self.pre_df.shape}")
            
            # Column check
            pre_cols = set(self.pre_df.columns)
            post_cols = set(self.post_df.columns)
            
            missing = pre_cols - post_cols
            extra = post_cols - pre_cols
            
            if missing:
                self.logger.error(f"MISSING COLUMNS: {list(missing)[:10]}")  # Limit output
                return False
            
            if extra:
                self.logger.info(f"EXTRA COLUMNS: {list(extra)[:10]}")  # Just info, not error
            
            self.logger.info(f"✓ Column count: {len(pre_cols)} columns")
            return True
            
        except Exception as e:
            self.logger.error(f"Structure check failed: {str(e)[:100]}")
            return False
    
    def explicit_columns_check(self) -> bool:
        """Check the explicitly specified critical columns"""
        self.logger.info(f"\n=== EXPLICIT COLUMNS CHECK ===")
        self.logger.info(f"Validating {len(self.explicit_columns)} critical columns...")
        
        try:
            # Check which explicit columns are available
            available_explicit = []
            missing_explicit = []
            
            for col in self.explicit_columns:
                if col in self.pre_df.columns and col in self.post_df.columns:
                    available_explicit.append(col)
                else:
                    missing_explicit.append(col)
            
            if missing_explicit:
                self.logger.warning(f"⚠ Missing explicit columns: {missing_explicit}")
            
            self.logger.info(f"Found {len(available_explicit)}/{len(self.explicit_columns)} explicit columns")
            
            # Validate each available explicit column
            explicit_results = {}
            all_explicit_pass = True
            
            for col in available_explicit:
                self.logger.info(f"\n--- Checking {col} ---")
                
                # Get full columns (not just sample)
                pre_col = self.pre_df[col]
                post_col = self.post_df[col]
                
                # Detailed comparison for explicit columns
                col_result = self._detailed_column_compare(pre_col, post_col, col)
                explicit_results[col] = col_result
                
                if col_result['match']:
                    self.logger.info(f"✓ {col}: PERFECT MATCH")
                else:
                    self.logger.error(f"✗ {col}: DIFFERENCES FOUND")
                    all_explicit_pass = False
                    
                    # Show detailed differences for explicit columns
                    if col_result.get('sample_diffs'):
                        self.logger.error(f"  Sample differences in {col}:")
                        for i, diff in enumerate(col_result['sample_diffs'][:3]):  # Show first 3
                            self.logger.error(f"    Row {diff['row']}: '{diff['pre_value']}' → '{diff['post_value']}'")
            
            # Summary for explicit columns
            passed_explicit = sum(1 for r in explicit_results.values() if r['match'])
            self.logger.info(f"\nExplicit columns summary: {passed_explicit}/{len(available_explicit)} passed")
            
            if all_explicit_pass:
                self.logger.info("🎯 ✓ ALL EXPLICIT COLUMNS MATCH PERFECTLY!")
            else:
                self.logger.error("🎯 ✗ SOME EXPLICIT COLUMNS HAVE DIFFERENCES!")
            
            return all_explicit_pass
            
        except Exception as e:
            self.logger.error(f"Explicit columns check failed: {str(e)[:100]}")
            return False
    
    def _detailed_column_compare(self, pre_col: pd.Series, post_col: pd.Series, 
                               col_name: str) -> Dict[str, Any]:
        """Detailed comparison for critical columns"""
        result = {
            'match': False,
            'null_match': False,
            'value_match': False,
            'differences': 0,
            'sample_diffs': []
        }
        
        try:
            # Check null patterns
            pre_nulls = pre_col.isna()
            post_nulls = post_col.isna()
            result['null_match'] = pre_nulls.equals(post_nulls)
            
            if not result['null_match']:
                null_diff = (pre_nulls != post_nulls).sum()
                self.logger.warning(f"  Null pattern differs in {null_diff} rows")
            
            # Check values based on data type
            if pd.api.types.is_numeric_dtype(pre_col) or pd.api.types.is_numeric_dtype(post_col):
                result['value_match'] = self._compare_numeric_detailed(pre_col, post_col, col_name, result)
            else:
                result['value_match'] = self._compare_text_detailed(pre_col, post_col, col_name, result)
            
            # Overall match
            result['match'] = result['null_match'] and result['value_match']
            
            return result
            
        except Exception as e:
            self.logger.error(f"  Detailed comparison failed for {col_name}: {str(e)[:100]}")
            return result
    
    def _compare_numeric_detailed(self, pre_col: pd.Series, post_col: pd.Series, 
                                col_name: str, result: Dict[str, Any]) -> bool:
        """Detailed numeric comparison"""
        try:
            # Convert to numeric
            pre_numeric = pd.to_numeric(pre_col, errors='coerce')
            post_numeric = pd.to_numeric(post_col, errors='coerce')
            
            # Find differences
            diff_mask = ~np.isclose(pre_numeric, post_numeric, 
                                   rtol=self.float_tolerance, 
                                   atol=self.float_tolerance, 
                                   equal_nan=True)
            
            differences = diff_mask.sum()
            result['differences'] = differences
            
            if differences > 0:
                self.logger.warning(f"  {differences} numeric differences found")
                
                # Get sample differences
                diff_indices = diff_mask[diff_mask].index[:self.max_sample_diffs]
                sample_diffs = []
                
                for idx in diff_indices:
                    pre_val = pre_numeric.iloc[idx] if idx < len(pre_numeric) else np.nan
                    post_val = post_numeric.iloc[idx] if idx < len(post_numeric) else np.nan
                    
                    sample_diffs.append({
                        'row': idx,
                        'pre_value': pre_val,
                        'post_value': post_val,
                        'abs_diff': abs(pre_val - post_val) if pd.notna(pre_val) and pd.notna(post_val) else 'NaN diff'
                    })
                
                result['sample_diffs'] = sample_diffs
                
                # Show statistics
                if len(pre_numeric.dropna()) > 0 and len(post_numeric.dropna()) > 0:
                    pre_mean = pre_numeric.mean()
                    post_mean = post_numeric.mean()
                    self.logger.warning(f"  Mean: {pre_mean:.6f} → {post_mean:.6f}")
                
                return False
            
            self.logger.info(f"  All {len(pre_numeric)} numeric values match")
            return True
            
        except Exception as e:
            self.logger.error(f"  Numeric comparison failed: {str(e)[:100]}")
            return False
    
    def _compare_text_detailed(self, pre_col: pd.Series, post_col: pd.Series, 
                             col_name: str, result: Dict[str, Any]) -> bool:
        """Detailed text comparison"""
        try:
            # Convert to string for comparison
            pre_str = pre_col.astype(str)
            post_str = post_col.astype(str)
            
            # Find differences
            diff_mask = (pre_str != post_str) & ~(pre_col.isna() & post_col.isna())
            differences = diff_mask.sum()
            result['differences'] = differences
            
            if differences > 0:
                self.logger.warning(f"  {differences} text differences found")
                
                # Get sample differences
                diff_indices = diff_mask[diff_mask].index[:self.max_sample_diffs]
                sample_diffs = []
                
                for idx in diff_indices:
                    pre_val = pre_col.iloc[idx] if idx < len(pre_col) else None
                    post_val = post_col.iloc[idx] if idx < len(post_col) else None
                    
                    sample_diffs.append({
                        'row': idx,
                        'pre_value': pre_val,
                        'post_value': post_val
                    })
                
                result['sample_diffs'] = sample_diffs
                
                # Show value counts for categorical data
                if differences < 20:  # Only for small number of differences
                    unique_pre = pre_col.value_counts().head(5)
                    unique_post = post_col.value_counts().head(5)
                    self.logger.info(f"  PRE top values: {unique_pre.to_dict()}")
                    self.logger.info(f"  POST top values: {unique_post.to_dict()}")
                
                return False
            
            self.logger.info(f"  All {len(pre_col)} text values match")
            return True
            
        except Exception as e:
            self.logger.error(f"  Text comparison failed: {str(e)[:100]}")
            return False
    
    def sample_data_check(self, sample_size: int = 100) -> bool:
        """Check a small sample of data instead of full validation"""
        self.logger.info(f"\n=== SAMPLE DATA CHECK (n={sample_size}) ===")
        
        try:
            # Get common columns
            common_cols = list(set(self.pre_df.columns) & set(self.post_df.columns))
            
            # Take a random sample
            sample_indices = np.random.choice(
                min(len(self.pre_df), len(self.post_df)), 
                size=min(sample_size, len(self.pre_df)), 
                replace=False
            )
            
            pre_sample = self.pre_df.iloc[sample_indices][common_cols].reset_index(drop=True)
            post_sample = self.post_df.iloc[sample_indices][common_cols].reset_index(drop=True)
            
            # Check key columns first
            key_cols = ['WAFER_ID', 'STATUS', 'CLASS']
            available_key_cols = [col for col in key_cols if col in common_cols]
            
            self.logger.info(f"Checking {len(available_key_cols)} key columns in sample...")
            
            key_cols_pass = True
            for col in available_key_cols:
                if not self._safe_column_compare(pre_sample[col], post_sample[col], col):
                    key_cols_pass = False
            
            if key_cols_pass:
                self.logger.info("✓ Key columns match in sample")
            else:
                self.logger.error("✗ Key columns differ in sample")
                return False
            
            # Check a few more random columns (excluding explicit ones since they're checked separately)
            other_cols = [col for col in common_cols 
                         if col not in available_key_cols and col not in self.explicit_columns]
            sample_other_cols = other_cols[:10]  # Just check 10 more columns
            
            self.logger.info(f"Spot-checking {len(sample_other_cols)} additional columns...")
            
            other_cols_issues = 0
            for col in sample_other_cols:
                if not self._safe_column_compare(pre_sample[col], post_sample[col], col, verbose=False):
                    other_cols_issues += 1
            
            if other_cols_issues == 0:
                self.logger.info("✓ Additional columns match in sample")
            else:
                self.logger.warning(f"⚠ {other_cols_issues}/{len(sample_other_cols)} additional columns have differences")
            
            return key_cols_pass
            
        except Exception as e:
            self.logger.error(f"Sample check failed: {str(e)[:100]}")
            return False
    
    def _safe_column_compare(self, pre_col: pd.Series, post_col: pd.Series, 
                           col_name: str, verbose: bool = True) -> bool:
        """Safely compare two columns without memory issues"""
        try:
            # Quick null check
            if pre_col.isna().sum() != post_col.isna().sum():
                if verbose:
                    self.logger.warning(f"⚠ {col_name}: Different null counts")
                return False
            
            # For numeric columns
            if pd.api.types.is_numeric_dtype(pre_col) and pd.api.types.is_numeric_dtype(post_col):
                # Use numpy for efficient comparison
                pre_vals = pre_col.values
                post_vals = post_col.values
                
                # Handle NaN values
                both_valid = ~(np.isnan(pre_vals) | np.isnan(post_vals))
                
                if both_valid.sum() > 0:
                    diff_count = (~np.isclose(
                        pre_vals[both_valid], 
                        post_vals[both_valid], 
                        rtol=self.float_tolerance, 
                        atol=self.float_tolerance
                    )).sum()
                    
                    if diff_count > 0:
                        if verbose:
                            self.logger.warning(f"⚠ {col_name}: {diff_count} numeric differences")
                        return False
            
            # For non-numeric columns
            else:
                # Convert to string for comparison
                pre_str = pre_col.astype(str)
                post_str = post_col.astype(str)
                
                diff_count = (pre_str != post_str).sum()
                if diff_count > 0:
                    if verbose:
                        self.logger.warning(f"⚠ {col_name}: {diff_count} text differences")
                    return False
            
            if verbose:
                self.logger.info(f"✓ {col_name}: Match")
            return True
            
        except Exception as e:
            if verbose:
                self.logger.error(f"✗ {col_name}: Comparison failed - {str(e)[:50]}")
            return False
    
    def statistical_summary_check(self) -> bool:
        """Compare basic statistics instead of full data"""
        self.logger.info("\n=== STATISTICAL SUMMARY CHECK ===")
        
        try:
            # Get numeric columns
            pre_numeric = self.pre_df.select_dtypes(include=[np.number])
            post_numeric = self.post_df.select_dtypes(include=[np.number])
            
            common_numeric = list(set(pre_numeric.columns) & set(post_numeric.columns))
            
            self.logger.info(f"Comparing statistics for {len(common_numeric)} numeric columns...")
            
            stats_issues = 0
            
            for col in common_numeric[:20]:  # Limit to first 20 numeric columns
                try:
                    pre_stats = pre_numeric[col].describe()
                    post_stats = post_numeric[col].describe()
                    
                    # Compare key stats
                    for stat in ['count', 'mean', 'std', 'min', 'max']:
                        if stat in pre_stats.index and stat in post_stats.index:
                            pre_val = pre_stats[stat]
                            post_val = post_stats[stat]
                            
                            if not np.isclose(pre_val, post_val, rtol=1e-6, atol=1e-6, equal_nan=True):
                                self.logger.warning(f"⚠ {col}.{stat}: {pre_val:.6f} → {post_val:.6f}")
                                stats_issues += 1
                                break  # Don't check other stats for this column
                
                except Exception:
                    continue  # Skip problematic columns
            
            if stats_issues == 0:
                self.logger.info("✓ Statistical summaries match")
                return True
            else:
                self.logger.warning(f"⚠ {stats_issues} statistical differences found")
                return False
                
        except Exception as e:
            self.logger.error(f"Statistical check failed: {str(e)[:100]}")
            return False
    
    def run_safe_validation(self) -> bool:
        """Run a safe, memory-efficient validation"""
        self.logger.info("🚀 STARTING SAFE MIGRATION VALIDATION")
        self.logger.info("=" * 50)
        
        try:
            # Step 1: Load files safely
            if not self.safe_load_files():
                self.logger.error("❌ Failed to load files")
                return False
            
            # Step 2: Quick structure check
            if not self.quick_structure_check():
                self.logger.error("❌ Structure validation failed")
                return False
            
            # Step 3: EXPLICIT COLUMNS CHECK (MOST IMPORTANT!)
            explicit_ok = self.explicit_columns_check()
            
            # Step 4: Sample data check
            sample_ok = self.sample_data_check(sample_size=200)
            
            # Step 5: Statistical summary check
            stats_ok = self.statistical_summary_check()
            
            # Final result
            self.logger.info("\n" + "=" * 50)
            
            if explicit_ok and sample_ok and stats_ok:
                self.logger.info("🎉 VALIDATION PASSED!")
                self.logger.info("✓ All critical columns match perfectly")
                self.logger.info("✓ Sample data matches")
                self.logger.info("✓ Statistical summaries match")
            elif explicit_ok and sample_ok:
                self.logger.warning("⚠ VALIDATION MOSTLY PASSED")
                self.logger.info("✓ All critical columns match perfectly")
                self.logger.info("✓ Sample data matches")
                self.logger.warning("⚠ Some statistical differences (may be acceptable)")
            elif explicit_ok:
                self.logger.warning("⚠ CRITICAL COLUMNS OK, BUT OTHER ISSUES")
                self.logger.info("✓ All critical columns match perfectly")
                self.logger.error("✗ Sample data or statistics have issues")
            else:
                self.logger.error("❌ VALIDATION FAILED!")
                self.logger.error("✗ Critical columns have differences!")
            
            self.logger.info("=" * 50)
            
            return explicit_ok  # Return True only if explicit columns pass
            
        except Exception as e:
            self.logger.error(f"❌ VALIDATION FAILED: {str(e)[:100]}")
            return False
        
        finally:
            # Clean up memory
            self.pre_df = None
            self.post_df = None
            gc.collect()


def safe_main():
    """Safe main function that won't crash Spyder"""
    
    print("🔍 Starting Safe Migration Validation with Explicit Column Checks...")
    
    # File paths
    pre_file = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_2025_PRE.csv"
    post_file = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_2025.csv"
    
    try:
        # Create validator
        validator = SafeMigrationValidator(pre_file, post_file)
        
        # Show which explicit columns will be checked
        print(f"\n🎯 Will explicitly validate these critical columns:")
        for i, col in enumerate(validator.explicit_columns, 1):
            print(f"  {i:2d}. {col}")
        
        # Run validation
        success = validator.run_safe_validation()
        
        if success:
            print("\n✅ Validation completed successfully!")
            print("🎯 All critical columns match perfectly!")
        else:
            print("\n❌ Validation failed!")
            print("🎯 Check the explicit column results above!")
        
        return success
        
    except Exception as e:
        print(f"\n💥 Validation crashed: {str(e)[:200]}")
        return False
    
    finally:
        # Force cleanup
        gc.collect()


# For Spyder: Run this instead of the full validation
if __name__ == "__main__":
    safe_main()