import pandas as pd
import numpy as np
from pathlib import Path
import logging
from typing import Dict, List, Tuple, Any
import warnings
import json
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataFrameValidator:
    """Comprehensive validator for comparing two DataFrames to detect regressions."""
    
    def __init__(self, tolerance: float = 1e-10):
        self.tolerance = tolerance
        self.results = {}
        
    def validate_files(self, pre_file: str, post_file: str) -> Dict[str, Any]:
        """Main validation function comparing PRE and POST files."""
        
        logger.info("Starting validation process...")
        
        # Load files
        try:
            df_pre = pd.read_csv(pre_file)
            df_post = pd.read_csv(post_file)
            logger.info(f"Loaded PRE file: {df_pre.shape}")
            logger.info(f"Loaded POST file: {df_post.shape}")
        except Exception as e:
            logger.error(f"Error loading files: {e}")
            return {"error": str(e)}
        
        # Run all validation checks
        self.results = {
            "basic_structure": self._check_basic_structure(df_pre, df_post),
            "column_comparison": self._check_columns(df_pre, df_post),
            "data_types": self._check_data_types(df_pre, df_post),
            "numerical_values": self._check_numerical_values(df_pre, df_post),
            "categorical_values": self._check_categorical_values(df_pre, df_post),
            "missing_values": self._check_missing_values(df_pre, df_post),
            "statistical_summary": self._check_statistical_summary(df_pre, df_post),
            "row_by_row": self._check_row_differences(df_pre, df_post),
            "duplicates": self._check_duplicates(df_pre, df_post)
        }
        
        # Generate summary
        self.results["summary"] = self._generate_summary()
        
        return self.results
    
    def _check_basic_structure(self, df_pre: pd.DataFrame, df_post: pd.DataFrame) -> Dict:
        """Check basic structure: shape, index, etc."""
        return {
            "shape_match": df_pre.shape == df_post.shape,
            "pre_shape": df_pre.shape,
            "post_shape": df_post.shape,
            "row_diff": df_post.shape[0] - df_pre.shape[0],
            "col_diff": df_post.shape[1] - df_pre.shape[1],
            "index_match": df_pre.index.equals(df_post.index)
        }
    
    def _check_columns(self, df_pre: pd.DataFrame, df_post: pd.DataFrame) -> Dict:
        """Check column names and order."""
        pre_cols = set(df_pre.columns)
        post_cols = set(df_post.columns)
        
        return {
            "columns_match": list(df_pre.columns) == list(df_post.columns),
            "column_order_match": df_pre.columns.equals(df_post.columns),
            "missing_in_post": list(pre_cols - post_cols),
            "added_in_post": list(post_cols - pre_cols),
            "common_columns": list(pre_cols & post_cols)
        }
    
    def _check_data_types(self, df_pre: pd.DataFrame, df_post: pd.DataFrame) -> Dict:
        """Check data types for each column."""
        common_cols = list(set(df_pre.columns) & set(df_post.columns))
        type_differences = {}
        
        for col in common_cols:
            pre_type = str(df_pre[col].dtype)
            post_type = str(df_post[col].dtype)
            if pre_type != post_type:
                type_differences[col] = {"pre": pre_type, "post": post_type}
        
        return {
            "all_types_match": len(type_differences) == 0,
            "type_differences": type_differences
        }
    
    def _check_numerical_values(self, df_pre: pd.DataFrame, df_post: pd.DataFrame) -> Dict:
        """Check numerical columns for differences."""
        common_cols = list(set(df_pre.columns) & set(df_post.columns))
        numerical_cols = [col for col in common_cols 
                         if df_pre[col].dtype in ['int64', 'float64', 'int32', 'float32']]
        
        differences = {}
        
        for col in numerical_cols:
            if df_pre.shape[0] == df_post.shape[0]:
                # Element-wise comparison
                diff_mask = ~np.isclose(df_pre[col].fillna(0), df_post[col].fillna(0), 
                                      rtol=self.tolerance, atol=self.tolerance, equal_nan=True)
                
                if diff_mask.any():
                    diff_indices = df_pre.index[diff_mask].tolist()
                    max_diff = abs(df_pre[col] - df_post[col]).max()
                    mean_diff = abs(df_pre[col] - df_post[col]).mean()
                    
                    differences[col] = {
                        "different_values": len(diff_indices),
                        "sample_indices": diff_indices[:10],  # First 10 differences
                        "max_absolute_diff": float(max_diff) if not pd.isna(max_diff) else None,
                        "mean_absolute_diff": float(mean_diff) if not pd.isna(mean_diff) else None
                    }
        
        return {
            "numerical_columns": numerical_cols,
            "all_numerical_match": len(differences) == 0,
            "differences": differences
        }
    
    def _check_categorical_values(self, df_pre: pd.DataFrame, df_post: pd.DataFrame) -> Dict:
        """Check categorical/string columns for differences."""
        common_cols = list(set(df_pre.columns) & set(df_post.columns))
        categorical_cols = [col for col in common_cols 
                          if df_pre[col].dtype in ['object', 'category', 'string']]
        
        differences = {}
        
        for col in categorical_cols:
            if df_pre.shape[0] == df_post.shape[0]:
                # Direct comparison
                diff_mask = df_pre[col].fillna('') != df_post[col].fillna('')
                
                if diff_mask.any():
                    diff_indices = df_pre.index[diff_mask].tolist()
                    differences[col] = {
                        "different_values": len(diff_indices),
                        "sample_indices": diff_indices[:10],
                        "unique_values_pre": int(df_pre[col].nunique()),
                        "unique_values_post": int(df_post[col].nunique())
                    }
        
        return {
            "categorical_columns": categorical_cols,
            "all_categorical_match": len(differences) == 0,
            "differences": differences
        }
    
    def _check_missing_values(self, df_pre: pd.DataFrame, df_post: pd.DataFrame) -> Dict:
        """Check for differences in missing values pattern."""
        common_cols = list(set(df_pre.columns) & set(df_post.columns))
        
        missing_differences = {}
        
        for col in common_cols:
            pre_missing = int(df_pre[col].isna().sum())
            post_missing = int(df_post[col].isna().sum())
            
            if pre_missing != post_missing:
                missing_differences[col] = {
                    "pre_missing": pre_missing,
                    "post_missing": post_missing,
                    "difference": post_missing - pre_missing
                }
        
        return {
            "missing_pattern_match": len(missing_differences) == 0,
            "differences": missing_differences
        }
    
    def _check_statistical_summary(self, df_pre: pd.DataFrame, df_post: pd.DataFrame) -> Dict:
        """Compare statistical summaries."""
        common_cols = list(set(df_pre.columns) & set(df_post.columns))
        numerical_cols = [col for col in common_cols 
                         if df_pre[col].dtype in ['int64', 'float64', 'int32', 'float32']]
        
        stat_differences = {}
        
        for col in numerical_cols:
            pre_stats = df_pre[col].describe()
            post_stats = df_post[col].describe()
            
            col_diffs = {}
            for stat in ['mean', 'std', 'min', 'max']:
                if stat in pre_stats and stat in post_stats:
                    pre_val = pre_stats[stat]
                    post_val = post_stats[stat]
                    
                    if not (pd.isna(pre_val) and pd.isna(post_val)):
                        if not np.isclose(pre_val, post_val, 
                                        rtol=self.tolerance, atol=self.tolerance, equal_nan=True):
                            col_diffs[stat] = {
                                "pre": float(pre_val) if not pd.isna(pre_val) else None,
                                "post": float(post_val) if not pd.isna(post_val) else None,
                                "diff": float(post_val - pre_val) if not (pd.isna(pre_val) or pd.isna(post_val)) else None
                            }
            
            if col_diffs:
                stat_differences[col] = col_diffs
        
        return {
            "statistics_match": len(stat_differences) == 0,
            "differences": stat_differences
        }
    
    def _check_row_differences(self, df_pre: pd.DataFrame, df_post: pd.DataFrame) -> Dict:
        """Check for row-level differences."""
        if df_pre.shape != df_post.shape:
            return {"message": "Cannot compare rows - different shapes"}
        
        common_cols = list(set(df_pre.columns) & set(df_post.columns))
        
        # Find rows that are completely different
        different_rows = []
        
        for idx in range(min(len(df_pre), len(df_post))):
            row_pre = df_pre.iloc[idx][common_cols]
            row_post = df_post.iloc[idx][common_cols]
            
            # Check if any value in the row is different
            differences_in_row = []
            for col in common_cols:
                val_pre = row_pre[col]
                val_post = row_post[col]
                
                # Handle different data types
                if pd.isna(val_pre) and pd.isna(val_post):
                    continue
                elif pd.isna(val_pre) or pd.isna(val_post):
                    differences_in_row.append(col)
                elif isinstance(val_pre, (int, float)) and isinstance(val_post, (int, float)):
                    if not np.isclose(val_pre, val_post, rtol=self.tolerance, atol=self.tolerance):
                        differences_in_row.append(col)
                else:
                    if str(val_pre) != str(val_post):
                        differences_in_row.append(col)
            
            if differences_in_row:
                different_rows.append({
                    "row_index": int(idx),
                    "different_columns": differences_in_row[:5]  # Limit to first 5
                })
            
            # Limit to first 100 different rows for performance
            if len(different_rows) >= 100:
                break
        
        return {
            "total_different_rows": len(different_rows),
            "sample_different_rows": different_rows[:10],
            "all_rows_match": len(different_rows) == 0
        }
    
    def _check_duplicates(self, df_pre: pd.DataFrame, df_post: pd.DataFrame) -> Dict:
        """Check for differences in duplicate rows."""
        return {
            "pre_duplicates": int(df_pre.duplicated().sum()),
            "post_duplicates": int(df_post.duplicated().sum()),
            "duplicate_count_match": df_pre.duplicated().sum() == df_post.duplicated().sum()
        }
    
    def _generate_summary(self) -> Dict:
        """Generate overall summary of validation."""
        checks = [
            self.results["basic_structure"]["shape_match"],
            self.results["column_comparison"]["columns_match"],
            self.results["data_types"]["all_types_match"],
            self.results["numerical_values"]["all_numerical_match"],
            self.results["categorical_values"]["all_categorical_match"],
            self.results["missing_values"]["missing_pattern_match"],
            self.results["statistical_summary"]["statistics_match"],
            self.results["row_by_row"]["all_rows_match"],
            self.results["duplicates"]["duplicate_count_match"]
        ]
        
        return {
            "all_checks_passed": all(checks),
            "passed_checks": sum(checks),
            "total_checks": len(checks),
            "regression_detected": not all(checks)
        }
    
    def print_report(self):
        """Print a formatted validation report."""
        print("="*80)
        print("DATA VALIDATION REPORT")
        print("="*80)
        
        summary = self.results["summary"]
        print(f"\nOVERALL RESULT: {'✅ PASS' if summary['all_checks_passed'] else '❌ FAIL'}")
        print(f"Checks passed: {summary['passed_checks']}/{summary['total_checks']}")
        
        if summary["regression_detected"]:
            print("\n⚠️  REGRESSION DETECTED - DIFFERENCES FOUND:")
            
            # Print specific issues
            if not self.results["basic_structure"]["shape_match"]:
                print(f"  - Shape mismatch: {self.results['basic_structure']['pre_shape']} → {self.results['basic_structure']['post_shape']}")
            
            if not self.results["column_comparison"]["columns_match"]:
                print(f"  - Column differences detected")
                if self.results["column_comparison"]["missing_in_post"]:
                    print(f"    Missing columns: {self.results['column_comparison']['missing_in_post']}")
                if self.results["column_comparison"]["added_in_post"]:
                    print(f"    Added columns: {self.results['column_comparison']['added_in_post']}")
            
            if not self.results["numerical_values"]["all_numerical_match"]:
                print(f"  - Numerical value differences in {len(self.results['numerical_values']['differences'])} columns")
            
            if not self.results["categorical_values"]["all_categorical_match"]:
                print(f"  - Categorical value differences in {len(self.results['categorical_values']['differences'])} columns")
            
            if not self.results["row_by_row"]["all_rows_match"]:
                print(f"  - {self.results['row_by_row']['total_different_rows']} rows have differences")
        
        else:
            print("\n✅ NO REGRESSION DETECTED - All validations passed!")
        
        print("="*80)

    def _serialize_for_json(self, obj):
        """Convert objects to JSON-serializable format."""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        elif isinstance(obj, pd.Index):
            return obj.tolist()
        elif hasattr(obj, 'item'):  # numpy scalars
            return obj.item()
        elif isinstance(obj, dict):
            return {k: self._serialize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_for_json(item) for item in obj]
        else:
            return obj


def main():
    """Main execution function."""
    
    # File paths
    pre_file = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_NCDD_PST_WITH_ELWC_LOOKBACKS_PRE.csv"
    post_file = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_NCDD_PST_WITH_ELWC_LOOKBACKS.csv"
    
    # Create validator with appropriate tolerance for floating point comparisons
    validator = DataFrameValidator(tolerance=1e-10)
    
    # Run validation
    results = validator.validate_files(pre_file, post_file)
    
    # Print report
    validator.print_report()
    
    # Save detailed results to JSON with proper serialization
    try:
        serialized_results = validator._serialize_for_json(results)
        json_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\validation_results.json"
        with open(json_path, "w") as f:
            json.dump(serialized_results, f, indent=2)
        print(f"\nDetailed results saved to: validation_results.json")
    except Exception as e:
        print(f"\nWarning: Could not save JSON results: {e}")
        # Save a simplified summary instead
        summary_only = {
            "validation_summary": results["summary"],
            "basic_info": {
                "pre_shape": results["basic_structure"]["pre_shape"],
                "post_shape": results["basic_structure"]["post_shape"],
                "shape_match": results["basic_structure"]["shape_match"]
            }
        }
        with open("validation_summary.json", "w") as f:
            json.dump(summary_only, f, indent=2)
        print("Saved validation summary to: validation_summary.json")
    
    # Return exit code based on validation result
    return 0 if results["summary"]["all_checks_passed"] else 1


if __name__ == "__main__":
    exit_code = main()
    # Don't call exit() in Spyder/Jupyter environments
    print(f"\nValidation completed with exit code: {exit_code}")