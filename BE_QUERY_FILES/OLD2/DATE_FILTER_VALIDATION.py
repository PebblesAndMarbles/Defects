import pandas as pd
import numpy as np
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def validate_date_filtering():
    """Validate that date filtering was applied correctly"""
    
    # File paths
    pre_filter_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_2025_PRE.csv"
    post_filter_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_2025.csv"
    
    # CORRECTED date range to match your config
    start_date = "2025-12-01"  # Fixed year!
    end_date = "2025-12-21"    # Fixed year!
    start_datetime = pd.to_datetime(start_date)
    end_datetime = pd.to_datetime(end_date)
    
    logging.info("=== DATE FILTERING VALIDATION (CORRECTED) ===")
    logging.info(f"Expected date range: {start_date} to {end_date}")
    
    try:
        # Load datasets
        logging.info("Loading pre-filter dataset...")
        df_pre = pd.read_csv(pre_filter_path)
        logging.info(f"Pre-filter dataset shape: {df_pre.shape}")
        
        logging.info("Loading post-filter dataset...")
        df_post = pd.read_csv(post_filter_path)
        logging.info(f"Post-filter dataset shape: {df_post.shape}")
        
        # Find the inspection time column
        pre_time_col = 'INSPECT_TIME'  # Should be renamed in both files
        post_time_col = 'INSPECT_TIME'
        
        if pre_time_col not in df_pre.columns:
            # Try original column name
            pre_time_col = 'INSPECTION_TIME@DEFECT'
        
        if pre_time_col not in df_pre.columns:
            logging.error(f"Time column not found in pre-filter data. Available columns: {list(df_pre.columns)[:10]}...")
            return False
        
        if post_time_col not in df_post.columns:
            logging.error(f"Time column not found in post-filter data. Available columns: {list(df_post.columns)[:10]}...")
            return False
        
        # Convert time columns to datetime
        df_pre[pre_time_col] = pd.to_datetime(df_pre[pre_time_col], errors='coerce')
        df_post[post_time_col] = pd.to_datetime(df_post[post_time_col], errors='coerce')
        
        # Analyze pre-filter date range
        logging.info(f"\n=== PRE-FILTER DATE ANALYSIS ===")
        pre_min_date = df_pre[pre_time_col].min()
        pre_max_date = df_pre[pre_time_col].max()
        
        logging.info(f"Pre-filter date range: {pre_min_date} to {pre_max_date}")
        
        # Count records in expected date range (pre-filter)
        pre_in_range = df_pre[
            (df_pre[pre_time_col] >= start_datetime) & 
            (df_pre[pre_time_col] <= end_datetime)
        ]
        pre_before_range = df_pre[df_pre[pre_time_col] < start_datetime]
        pre_after_range = df_pre[df_pre[pre_time_col] > end_datetime]
        
        logging.info(f"Pre-filter records in target range ({start_date} to {end_date}): {len(pre_in_range)}")
        logging.info(f"Pre-filter records before {start_date}: {len(pre_before_range)}")
        logging.info(f"Pre-filter records after {end_date}: {len(pre_after_range)}")
        
        # Analyze post-filter date range
        logging.info(f"\n=== POST-FILTER DATE ANALYSIS ===")
        post_min_date = df_post[post_time_col].min()
        post_max_date = df_post[post_time_col].max()
        
        logging.info(f"Post-filter date range: {post_min_date} to {post_max_date}")
        
        # Count records outside expected range (post-filter)
        post_before_range = df_post[df_post[post_time_col] < start_datetime]
        post_after_range = df_post[df_post[post_time_col] > end_datetime]
        post_in_range = df_post[
            (df_post[post_time_col] >= start_datetime) & 
            (df_post[post_time_col] <= end_datetime)
        ]
        
        logging.info(f"Post-filter records in target range: {len(post_in_range)}")
        logging.info(f"Post-filter records before {start_date}: {len(post_before_range)}")
        logging.info(f"Post-filter records after {end_date}: {len(post_after_range)}")
        
        # Validation checks
        logging.info(f"\n=== VALIDATION RESULTS ===")
        validation_passed = True
        
        # Check 1: Post-filter should have no records outside date range
        if len(post_before_range) > 0:
            logging.error(f"❌ FAIL: Found {len(post_before_range)} records before {start_date}")
            validation_passed = False
        else:
            logging.info(f"✅ PASS: No records before {start_date}")
        
        if len(post_after_range) > 0:
            logging.error(f"❌ FAIL: Found {len(post_after_range)} records after {end_date}")
            validation_passed = False
            sample_after = post_after_range[post_time_col].head()
            logging.error(f"Sample dates after range: {sample_after.tolist()}")
        else:
            logging.info(f"✅ PASS: No records after {end_date}")
        
        # Check 2: Post-filter count should match pre-filter in-range count
        expected_count = len(pre_in_range)
        actual_count = len(df_post)
        
        if actual_count == expected_count:
            logging.info(f"✅ PASS: Record count matches expected ({actual_count} == {expected_count})")
        else:
            logging.warning(f"⚠️  INFO: Record count difference (actual: {actual_count}, expected: {expected_count})")
            logging.warning(f"Difference: {actual_count - expected_count}")
            # This could be due to null handling or other filtering
        
        # Summary statistics
        size_reduction = len(df_pre) - len(df_post)
        size_reduction_pct = (size_reduction / len(df_pre)) * 100 if len(df_pre) > 0 else 0
        
        logging.info(f"\n=== SUMMARY ===")
        logging.info(f"Original dataset: {len(df_pre):,} records")
        logging.info(f"Filtered dataset: {len(df_post):,} records")
        logging.info(f"Records removed: {size_reduction:,} ({size_reduction_pct:.1f}%)")
        logging.info(f"Expected records in range: {expected_count:,}")
        logging.info(f"Filter efficiency: Kept {len(df_post)} out of {expected_count} expected records")
        
        if validation_passed:
            logging.info(f"🎉 VALIDATION PASSED: Date filtering is working correctly!")
        else:
            logging.error(f"💥 VALIDATION FAILED: Issues found with date filtering!")
        
        return validation_passed
        
    except Exception as e:
        logging.error(f"Validation failed with error: {e}")
        return False

if __name__ == "__main__":
    validate_date_filtering()