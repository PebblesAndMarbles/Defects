import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def add_elwc_lookbacks(dt):
    """
    Add ELWC lookback metrics to the defect dataframe
    """
    from tqdm import tqdm
    
    print("=== ELWC LOOKBACK PROCESSING (Updated for Test Wafer Logic) ===")
    start_time = datetime.now()
    
    # File path for ELWC data (updated to 185 days)
    elwc_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\2025-12-22 185 days ALL_CHAMBERS ELWC.csv"
    
    # Load ELWC dataset
    print("Loading ELWC historical data...")
    elwc_df = pd.read_csv(elwc_path)
    print(f"ELWC data loaded: {len(elwc_df)} records")
    
    # Preprocess ELWC data
    print("Preprocessing ELWC data...")
    
    # Convert START_DATE to datetime
    elwc_df['START_DATETIME'] = pd.to_datetime(elwc_df['START_DATE'])
    
    # Identify test wafers (LOT contains 'T')
    elwc_df['IS_TEST_WAFER'] = elwc_df['LOT'].astype(str).str.contains('T', na=False)
    
    # Determine technology from 4th character of OPER_SHORT_DESC
    def get_technology(oper_short_desc):
        if pd.isna(oper_short_desc) or len(str(oper_short_desc)) < 4:
            return 'UNKNOWN'
        fourth_char = str(oper_short_desc)[3]
        if fourth_char == '8':
            return '1278'
        elif fourth_char == '0':
            return '1280'
        else:
            return 'UNKNOWN'
    
    tqdm.pandas(desc="Determining technology")
    elwc_df['TECHNOLOGY'] = elwc_df['OPER_SHORT_DESC'].progress_apply(get_technology)
    
    # Define recipe groups
    def classify_recipe_group(seq_recipe, technology, is_test_wafer):
        if pd.isna(seq_recipe):
            return 'OTHER'
        
        recipe_str = str(seq_recipe).upper()
        
        # MONTW: Monitors and test wafers (includes all test wafers)
        if (recipe_str.startswith('M_') or 
            recipe_str.startswith('C_') or 
            'TEACH' in recipe_str or
            is_test_wafer):  # All test wafers go to MONTW
            return 'MONTW'
        
        # Product wafers by technology (only non-test wafers)
        if not is_test_wafer:  # Only classify product groups for non-test wafers
            if technology == '1278':
                if 'GABON' in recipe_str or 'CHALBI' in recipe_str:
                    return '8GAB'
                elif 'THAR' in recipe_str:
                    return '8THA'
                elif 'GOBI' in recipe_str:
                    return '8GOB'
                elif 'PIL' in recipe_str:
                    return '8PIL'
                elif recipe_str.startswith('S_'):
                    return '8SIF'
            elif technology == '1280':
                if 'GABON' in recipe_str or 'CHALBI' in recipe_str:
                    return '0GAB'
                elif 'THAR' in recipe_str:
                    return '0THA'
                elif 'GOBI' in recipe_str:
                    return '0GOB'
                elif 'PIL' in recipe_str:
                    return '0PIL'
                elif recipe_str.startswith('S_'):
                    return '0SIF'
        
        return 'OTHER'
    
    tqdm.pandas(desc="Classifying recipe groups")
    elwc_df['RECIPE_GROUP'] = elwc_df.progress_apply(
        lambda row: classify_recipe_group(row['SEQ_RECIPE'], row['TECHNOLOGY'], row['IS_TEST_WAFER']), 
        axis=1
    )
    
    # Show recipe group distribution
    print("\nRecipe group distribution in ELWC data:")
    print(elwc_df['RECIPE_GROUP'].value_counts())
    
    # Show test wafer statistics
    print(f"\nTest wafer statistics:")
    print(f"Total test wafers (LOT contains 'T'): {elwc_df['IS_TEST_WAFER'].sum()}")
    print(f"Total product wafers: {(~elwc_df['IS_TEST_WAFER']).sum()}")
    
    # Sort ELWC data by SUBENTITY and START_DATETIME for efficient lookups
    print("Sorting ELWC data...")
    elwc_df = elwc_df.sort_values(['SUBENTITY', 'START_DATETIME']).reset_index(drop=True)
    
    # Create chamber-grouped data for efficient lookup
    print("Creating chamber-grouped lookup tables...")
    chamber_data = {}
    for chamber in tqdm(elwc_df['SUBENTITY'].unique(), desc="Grouping by chamber"):
        chamber_data[chamber] = elwc_df[elwc_df['SUBENTITY'] == chamber].copy()
    
    # Define all recipe groups and time windows
    recipe_groups = ['MONTW', '8GAB', '8THA', '8GOB', '8PIL', '8SIF', 
                     '0GAB', '0THA', '0GOB', '0PIL', '0SIF']
    time_windows = [4, 12, 36]  # hours
    
    # Initialize new columns in defect data
    print("Initializing lookback columns...")
    for group in recipe_groups:
        for window in time_windows:
            dt[f'{group}_{window}HRS'] = np.nan
    
    def find_elwc_match(wafer_id, operation, debug=False):
        """Find matching ELWC row for wafer_id and operation"""
        # Filter ELWC data for matching WAFER and OPER
        matches = elwc_df[(elwc_df['WAFER'] == wafer_id) & (elwc_df['OPER'] == operation)]
        
        if matches.empty:
            if debug:
                print(f"  No ELWC match found for {wafer_id}, {operation}")
            return None, None
        
        # If multiple matches, take the most recent one
        if len(matches) > 1:
            if debug:
                print(f"  Multiple ELWC matches found ({len(matches)}), taking most recent")
            match = matches.loc[matches['START_DATETIME'].idxmax()]
        else:
            match = matches.iloc[0]
        
        if debug:
            print(f"  ELWC match: {match['SUBENTITY']} at {match['START_DATETIME']}")
        
        return match['SUBENTITY'], match['START_DATETIME']
    
    def calculate_lookbacks(wafer_id, operation, debug=False):
        """Calculate lookback metrics for a specific wafer/operation"""
        
        # Find matching row in ELWC data
        subentity, reference_time = find_elwc_match(wafer_id, operation, debug)
        
        if subentity is None:
            return {f'{group}_{window}HRS': np.nan 
                   for group in recipe_groups for window in time_windows}
        
        # Get chamber-specific historical data
        if subentity not in chamber_data:
            if debug:
                print(f"  No chamber data for {subentity}")
            return {f'{group}_{window}HRS': np.nan 
                   for group in recipe_groups for window in time_windows}
        
        chamber_history = chamber_data[subentity]
        
        # Calculate lookbacks for each group and time window
        results = {}
        
        for window_hours in time_windows:
            lookback_time = reference_time - timedelta(hours=window_hours)
            
            # Filter chamber history for this time window
            time_mask = ((chamber_history['START_DATETIME'] >= lookback_time) & 
                        (chamber_history['START_DATETIME'] < reference_time))
            window_data = chamber_history[time_mask]
            
            if debug and window_hours == 4:  # Only debug first window
                print(f"    {window_hours}hr window: {len(window_data)} total wafers")
                print(f"      Test wafers in window: {window_data['IS_TEST_WAFER'].sum()}")
                print(f"      Product wafers in window: {(~window_data['IS_TEST_WAFER']).sum()}")
            
            # Count wafers by recipe group
            for group in recipe_groups:
                count = len(window_data[window_data['RECIPE_GROUP'] == group])
                results[f'{group}_{window_hours}HRS'] = count
                
                if debug and window_hours == 4 and count > 0:  # Only show non-zero counts
                    print(f"      {group}: {count} wafers")
        
        return results
    
    # Process each defect row
    print("Calculating lookbacks for defect data...")
    
    # Test with first few rows
    print("\n=== TESTING LOOKBACK CALCULATIONS ===")
    test_rows = dt.head(3)
    for idx in test_rows.index:
        row = dt.loc[idx]
        wafer_id = row['WAFER_ID']
        operation = row['OPERATION']
        
        print(f"\nTesting row {idx}: {wafer_id}, {operation}")
        results = calculate_lookbacks(wafer_id, operation, debug=True)
        
        # Show sample results
        sample_cols = [f'{group}_4HRS' for group in recipe_groups[:4]]
        for col in sample_cols:
            print(f"  {col}: {results[col]}")
    print("=== END TEST ===\n")
    
    # Process all rows with progress bar
    successful_matches = 0
    failed_matches = 0
    
    for idx in tqdm(dt.index, desc="Processing defect rows"):
        row = dt.loc[idx]
        wafer_id = row['WAFER_ID']
        operation = row['OPERATION']
        
        results = calculate_lookbacks(wafer_id, operation, debug=False)
        
        # Update defect dataframe with results
        for col, value in results.items():
            dt.at[idx, col] = value
        
        # Track success/failure
        if pd.isna(list(results.values())[0]):  # Check first result
            failed_matches += 1
        else:
            successful_matches += 1
    
    print(f"\nLookback processing complete!")
    print(f"Successful ELWC matches: {successful_matches}")
    print(f"Failed matches (set to NaN): {failed_matches}")
    
    # Show summary statistics
    print(f"\nLookback column statistics:")
    sample_cols = [f'{group}_{window}HRS' 
                  for group in recipe_groups[:4] 
                  for window in time_windows[:2]]
    
    for col in sample_cols:
        non_null_count = dt[col].notna().sum()
        if non_null_count > 0:
            mean_val = dt[col].mean()
            max_val = dt[col].max()
            print(f"{col}: {non_null_count} non-null, mean={mean_val:.1f}, max={max_val}")
        else:
            print(f"{col}: All NaN")
    
    total_time = (datetime.now() - start_time).total_seconds()
    print(f"ELWC lookback processing completed in {total_time/60:.1f} minutes")
    
    return dt

def add_dp_fail_data(dt):
    """
    Add dry pump failure data to the main dataframe based on SUBENTITY and SUBENTITY_END_TIME
    """
    # Load dry pump failure data
    dp_fail_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\BE_AME_PUMPDOWN_FAILS.csv"
    
    print("Loading dry pump failure data...")
    dp_fail_df = pd.read_csv(dp_fail_path)
    
    print(f"DP Fail DataFrame shape: {dp_fail_df.shape}")
    print(f"DP Fail DataFrame columns: {list(dp_fail_df.columns)}")
    print(f"Sample SUBENTITY values: {dp_fail_df['SUBENTITY'].head(10).tolist()}")
    print(f"Unique subentities with DP failures: {dp_fail_df['SUBENTITY'].nunique()}")
    
    # Convert time column to datetime
    dp_fail_df['DP_FAIL_TIME'] = pd.to_datetime(dp_fail_df['DP_FAIL_TIME'], errors='coerce')
    
    # Sort by SUBENTITY and DP_FAIL_TIME for efficient lookup
    dp_fail_df = dp_fail_df.sort_values(['SUBENTITY', 'DP_FAIL_TIME'])
    
    # Initialize new column with NaN (changed from 1440.0)
    dt['DP_FAIL_HRS'] = np.nan
    
    def get_hours_since_dp_fail(subentity, subentity_end_time, debug=False):
        """
        Get hours since most recent dry pump failure for a given subentity and time
        Returns NaN if no failure found or invalid inputs
        """
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                print(f"  Missing subentity or time: {subentity}, {subentity_end_time}")
            return np.nan  # Changed from 1440.0
        
        # Filter DP fail data for this subentity
        entity_dp_data = dp_fail_df[dp_fail_df['SUBENTITY'] == subentity].copy()
        
        if debug:
            print(f"  DP failures found for {subentity}: {len(entity_dp_data)}")
        
        if entity_dp_data.empty:
            if debug:
                print(f"  No DP failure data found for {subentity}")
            return np.nan  # Changed from 1440.0
        
        # Filter for failures before or at the subentity end time
        valid_failures = entity_dp_data[
            entity_dp_data['DP_FAIL_TIME'] <= subentity_end_time
        ]
        
        if debug:
            print(f"  Valid failures (before {subentity_end_time}): {len(valid_failures)}")
            if len(valid_failures) > 0:
                print(f"  Latest valid failure time: {valid_failures['DP_FAIL_TIME'].max()}")
        
        if valid_failures.empty:
            if debug:
                print(f"  No failures before {subentity_end_time}")
            return np.nan  # Changed from 1440.0
        
        # Get the most recent failure
        most_recent_fail_time = valid_failures['DP_FAIL_TIME'].max()
        
        # Calculate hours difference
        time_diff = subentity_end_time - most_recent_fail_time
        hours_since_fail = time_diff.total_seconds() / 3600.0
        
        if debug:
            print(f"  Most recent failure time: {most_recent_fail_time}")
            print(f"  Hours since failure: {hours_since_fail:.2f}")
        
        return hours_since_fail
    
    # Test with a few rows first
    print("\n=== TESTING DP FAILURE LOOKUP ===")
    # Try to find rows with subentities that have DP failures
    test_subentities = dp_fail_df['SUBENTITY'].unique()[:3]
    test_rows = dt[dt['SUBENTITY'].isin(test_subentities)].head(3)
    
    if test_rows.empty:
        # If no matches, just test first 3 rows
        test_rows = dt.head(3)
    
    for idx in test_rows.index:
        row = dt.loc[idx]
        subentity = row['SUBENTITY']
        subentity_end_time = row['SUBENTITY_END_TIME']
        
        print(f"\nRow {idx}: {subentity} at {subentity_end_time}")
        hours_since_fail = get_hours_since_dp_fail(subentity, subentity_end_time, debug=True)
        if pd.isna(hours_since_fail):
            print(f"  Result - Hours since DP fail: NaN (no failure found)")
        else:
            print(f"  Result - Hours since DP fail: {hours_since_fail:.2f}")
    print("=== END TEST ===\n")
    
    # Process all rows
    print("Processing DP failure times for all defect scans...")
    for idx in dt.index:
        if idx % 100 == 0:  # Progress indicator
            print(f"  Processing row {idx}/{len(dt)}")
        
        row = dt.loc[idx]
        subentity = row['SUBENTITY']
        subentity_end_time = row['SUBENTITY_END_TIME']
        
        hours_since_fail = get_hours_since_dp_fail(subentity, subentity_end_time, debug=False)
        dt.at[idx, 'DP_FAIL_HRS'] = hours_since_fail
    
    print("DP failure processing complete!")
    
    # Show summary (updated for NaN handling)
    print(f"\nDP Failure Summary:")
    print(f"DP_FAIL_HRS - Non-null values: {dt['DP_FAIL_HRS'].notna().sum()}/{len(dt)}")
    print(f"DP_FAIL_HRS - Null values (no failure found): {dt['DP_FAIL_HRS'].isna().sum()}/{len(dt)}")
    if dt['DP_FAIL_HRS'].notna().sum() > 0:
        valid_values = dt[dt['DP_FAIL_HRS'].notna()]['DP_FAIL_HRS']
        print(f"DP_FAIL_HRS - Range (valid values): {valid_values.min():.2f} to {valid_values.max():.2f} hours")
        print(f"DP_FAIL_HRS - Mean (valid values): {valid_values.mean():.2f} hours")
        print(f"DP_FAIL_HRS - Median (valid values): {valid_values.median():.2f} hours")
    
    return dt

def add_leak_rate_data(dt):
    """
    Add leak rate data to the main dataframe based on SUBENTITY and SUBENTITY_END_TIME
    """
    # Load leak rate data
    leak_rate_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\BE_AME_CHLEAK.csv"
    
    print("Loading leak rate data...")
    leak_df = pd.read_csv(leak_rate_path)
    
    print(f"Leak rate DataFrame shape: {leak_df.shape}")
    print(f"Leak rate DataFrame columns: {list(leak_df.columns)}")
    print(f"Sample SUBENTITY values: {leak_df['SUBENTITY'].head(10).tolist()}")
    
    # Convert time column to datetime (note: using 'Time' not 'MEASUREMENT_TIME')
    leak_df['Time'] = pd.to_datetime(leak_df['Time'], errors='coerce')
    
    # Sort by SUBENTITY and Time for efficient lookup
    leak_df = leak_df.sort_values(['SUBENTITY', 'Time'])
    
    # Initialize new columns
    dt['RAW_LEAK_RATE'] = np.nan
    dt['SMOOTH_LEAK_RATE'] = np.nan
    
    def get_most_recent_leak_rates(subentity, subentity_end_time, debug=False):
        """
        Get the most recent leak rate measurements for a given subentity and time
        """
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                print(f"  Missing subentity or time: {subentity}, {subentity_end_time}")
            return np.nan, np.nan
        
        # Filter leak data for this subentity
        entity_leak_data = leak_df[leak_df['SUBENTITY'] == subentity].copy()
        
        if debug:
            print(f"  Leak measurements found for {subentity}: {len(entity_leak_data)}")
        
        if entity_leak_data.empty:
            if debug:
                print(f"  No leak data found for {subentity}")
            return np.nan, np.nan
        
        # Filter for measurements before or at the subentity end time
        valid_measurements = entity_leak_data[
            entity_leak_data['Time'] <= subentity_end_time
        ]
        
        if debug:
            print(f"  Valid measurements (before {subentity_end_time}): {len(valid_measurements)}")
            if len(valid_measurements) > 0:
                print(f"  Latest valid measurement time: {valid_measurements['Time'].max()}")
        
        if valid_measurements.empty:
            if debug:
                print(f"  No measurements before {subentity_end_time}")
            return np.nan, np.nan
        
        # Get the most recent measurement
        most_recent = valid_measurements.loc[valid_measurements['Time'].idxmax()]
        
        # Use 'Leak rate' column for raw leak rate
        raw_leak_rate = most_recent['Leak rate'] if 'Leak rate' in most_recent else np.nan
        smooth_leak_rate = most_recent['LRSMOOTH'] if 'LRSMOOTH' in most_recent else np.nan
        
        # Handle blank/empty values in LRSMOOTH
        if pd.isna(smooth_leak_rate) or str(smooth_leak_rate).strip() == '':
            smooth_leak_rate = np.nan
        
        if debug:
            print(f"  Most recent measurement time: {most_recent['Time']}")
            print(f"  Raw leak rate: {raw_leak_rate}")
            print(f"  Smooth leak rate: {smooth_leak_rate}")
        
        return raw_leak_rate, smooth_leak_rate
    
    # Test with a few rows first
    print("\n=== TESTING LEAK RATE LOOKUP ===")
    test_rows = dt.head(3)
    for idx in test_rows.index:
        row = dt.loc[idx]
        subentity = row['SUBENTITY']
        subentity_end_time = row['SUBENTITY_END_TIME']
        
        print(f"\nRow {idx}: {subentity} at {subentity_end_time}")
        raw_rate, smooth_rate = get_most_recent_leak_rates(subentity, subentity_end_time, debug=True)
        print(f"  Result - Raw: {raw_rate}, Smooth: {smooth_rate}")
    print("=== END TEST ===\n")
    
    # Process all rows
    print("Processing leak rates for all defect scans...")
    for idx in dt.index:
        if idx % 100 == 0:  # Progress indicator
            print(f"  Processing row {idx}/{len(dt)}")
        
        row = dt.loc[idx]
        subentity = row['SUBENTITY']
        subentity_end_time = row['SUBENTITY_END_TIME']
        
        raw_rate, smooth_rate = get_most_recent_leak_rates(subentity, subentity_end_time, debug=False)
        
        dt.at[idx, 'RAW_LEAK_RATE'] = raw_rate
        dt.at[idx, 'SMOOTH_LEAK_RATE'] = smooth_rate
    
    print("Leak rate processing complete!")
    
    # Show summary
    print(f"\nLeak Rate Summary:")
    print(f"RAW_LEAK_RATE - Non-null values: {dt['RAW_LEAK_RATE'].notna().sum()}/{len(dt)}")
    if dt['RAW_LEAK_RATE'].notna().sum() > 0:
        print(f"RAW_LEAK_RATE - Range: {dt['RAW_LEAK_RATE'].min():.4f} to {dt['RAW_LEAK_RATE'].max():.4f}")
    print(f"SMOOTH_LEAK_RATE - Non-null values: {dt['SMOOTH_LEAK_RATE'].notna().sum()}/{len(dt)}")
    if dt['SMOOTH_LEAK_RATE'].notna().sum() > 0:
        print(f"SMOOTH_LEAK_RATE - Range: {dt['SMOOTH_LEAK_RATE'].min():.4f} to {dt['SMOOTH_LEAK_RATE'].max():.4f}")
    
    return dt

def process_defect_data():
    # File paths
    file1_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M5CL_NCDD.csv"
    file2_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M6CL_NCDD.csv"
    file3_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\PLT\PLT_CURRENTLY_INSTALLED.csv"
    
    pilot_dates_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\BE_AME_PILOT_TURN_ON_DATES.csv"
    
    # Import and concatenate the two tables
    print("Loading and concatenating data files...")
    df1 = pd.read_csv(file1_path)
    df2 = pd.read_csv(file2_path)
    dt = pd.concat([df1, df2], ignore_index=True)
    
    # Delete columns containing 'SORTER'
    cols_to_delete = [col for col in dt.columns if 'SORTER' in col]
    if cols_to_delete:
        dt = dt.drop(columns=cols_to_delete)
    
    # Columns to keep (will be expanded during renaming)
    cols2keep = ["WAFER", "WAFER_ID", "LAYER"]
    
    # Create rename mapping for exact matches
    rename_map = {
        "DEFECT@WAFER@CLASS_NCDD@BEEP": "BEEP_NCDD",
        "DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE": "SMP_NCDD",
        "ACTUAL_LOT@DEFECT": "LOT",
        "INSPECTION_TIME@DEFECT": "INSPECT_TIME",
        "INSPECTION_TOOL@DEFECT": "INSPECT_TOOL",
        "PRODUCT@STARTS": "PRODUCT"
    }
    
    # Flexible patterns that might differ between 8M5 and 8M6
    flexible_patterns = {
        "LOT" : "LOT7",
        "ENTITY": "ENTITY",
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
        "PERCENT_UTILIZATION@BATCH_SUBENTITY_UTILIZATION@12HOURS": "UP_12HRS"
    }
    
    # Process flexible patterns FIRST (before exact matches)
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
    
    # THEN process exact matches
    for key, new_name in rename_map.items():
        if key in dt.columns:
            dt = dt.rename(columns={key: new_name})
            cols2keep.append(new_name)
    
    # Delete columns not in cols2keep
    final_cols_to_delete = [col for col in dt.columns if col not in cols2keep]
    if final_cols_to_delete:
        dt = dt.drop(columns=final_cols_to_delete)
    
    print("Column renaming and cleanup complete!")
    
    # User input: time and subentity column names
    time_column_name = "SUBENTITY_END_TIME"
    subentity_column_name = "SUBENTITY"
    
    # Columns to create with ON/OFF status
    cols_to_create = ["CCMR2", "ICCR2", "GF", "CV", "SRCIP"]
    
    # Load pilot turn-on dates
    print("Loading pilot turn-on dates...")
    pilot_on_time_df = pd.read_csv(pilot_dates_path)
    
    # Convert time columns to datetime
    if time_column_name in dt.columns:
        dt[time_column_name] = pd.to_datetime(dt[time_column_name], errors='coerce')
    
    for col in cols_to_create:
        if col in pilot_on_time_df.columns:
            pilot_on_time_df[col] = pd.to_datetime(pilot_on_time_df[col], errors='coerce')
    
    # Create pilot status columns
    print("Creating pilot status columns...")
    for col_to_create in cols_to_create:
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
    def create_pilot_status(row):
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
        
        # Combine base status with suffixes
        final_status = base_status + cv_suffix + gf_suffix
        return final_status
    
    dt['PILOT_STATUS'] = dt.apply(create_pilot_status, axis=1)
    
    # Create SUM_NCDD column
    print("Creating SUM_NCDD column...")
    dt['SUM_NCDD'] = pd.to_numeric(dt['BEEP_NCDD'], errors='coerce').fillna(0) + \
                     pd.to_numeric(dt['SMP_NCDD'], errors='coerce').fillna(0)
    
    # Create STATUS column as categorical
    print("Creating STATUS column...")
    dt['STATUS'] = pd.Categorical(
        dt['SUM_NCDD'].apply(lambda x: 'BSL' if x < 0.02 else 'HIGHFLIER'),
        categories=['BSL', 'HIGHFLIER']
    )
    
    # Load parts info and add RECOAT status columns
    print("Loading parts info and adding RECOAT status columns...")
    parts_df = pd.read_csv(file3_path)
    
    print(f"Parts DataFrame shape: {parts_df.shape}")
    print(f"Parts DataFrame columns: {list(parts_df.columns)}")
    print(f"Sample ENTITY values: {parts_df['ENTITY'].head(10).tolist()}")
    print(f"AME411_PM2 in parts data: {'AME411_PM2' in parts_df['ENTITY'].values}")
    print(f"Unique entities containing 'AME411': {[e for e in parts_df['ENTITY'].unique() if 'AME411' in str(e)]}")
    
    # Print column info for verification
    print(f"Parts info columns: {list(parts_df.columns)}")
    
    # Convert date columns to datetime
    parts_df['PART_INSTALL_DATE'] = pd.to_datetime(parts_df['PART_INSTALL_DATE'], errors='coerce')
    parts_df['PART_REMOVE_DATE'] = pd.to_datetime(parts_df['PART_REMOVE_DATE'], errors='coerce')
    
    # UPDATED: Use PART column directly instead of IPN mapping
    # Define the part types we want to track
    part_types = ['PLSCR', 'SLD', 'LNRCAT', 'LNRTSG', 'SLVCAT', 'HUB', 'LID', 'SNZZL']
    
    # Initialize RECOAT status columns
    for part_type in part_types:
        dt[part_type] = 'NOTFOUND'
    
    def get_recoat_status_by_part(subentity, subentity_end_time, part_type, debug=False):
        """Get RECOAT status for a specific PART type at a given time for a subentity"""
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                print(f"  Missing subentity or time: {subentity}, {subentity_end_time}")
            return 'NOTFOUND'
        
        # Filter parts data for this subentity and PART type
        entity_parts = parts_df[
            (parts_df['ENTITY'] == subentity) & 
            (parts_df['PART'] == part_type)
        ].copy()
        
        if debug:
            print(f"  Entity parts found for {part_type}: {len(entity_parts)}")
            if len(entity_parts) > 0:
                print(f"  Sample part dates and status:")
                for idx, row in entity_parts.head(3).iterrows():
                    print(f"    Install: {row['PART_INSTALL_DATE']} | Remove: {row['PART_REMOVE_DATE']} | Currently: {row['CURRENTLY_INSTALLED']} | Recoat: {row['RECOAT']}")
                print(f"  Subentity end time: {subentity_end_time}")
                print(f"  CURRENTLY_INSTALLED column type: {type(entity_parts.iloc[0]['CURRENTLY_INSTALLED'])}")
                print(f"  CURRENTLY_INSTALLED unique values: {entity_parts['CURRENTLY_INSTALLED'].unique()}")
        
        if entity_parts.empty:
            return 'NOTFOUND'
        
        matching_parts = []
        
        # Check currently installed parts first
        currently_installed = entity_parts[
            (entity_parts['CURRENTLY_INSTALLED'] == True) | 
            (entity_parts['CURRENTLY_INSTALLED'] == 'TRUE') |
            (entity_parts['CURRENTLY_INSTALLED'] == 'True')
        ]
        if debug:
            print(f"  Currently installed parts: {len(currently_installed)}")
        
        for _, part in currently_installed.iterrows():
            if debug:
                print(f"    Checking currently installed part: Install={part['PART_INSTALL_DATE']}, End_time={subentity_end_time}")
            if pd.notna(part['PART_INSTALL_DATE']) and subentity_end_time > part['PART_INSTALL_DATE']:
                matching_parts.append(part)
                if debug:
                    print(f"    ✓ Match found (currently installed): {part['RECOAT']}")
            elif debug:
                print(f"    ✗ No match: Install date check failed")
        
        # Check previously installed parts
        previously_installed = entity_parts[
            (entity_parts['CURRENTLY_INSTALLED'] == False) | 
            (entity_parts['CURRENTLY_INSTALLED'] == 'FALSE') |
            (entity_parts['CURRENTLY_INSTALLED'] == 'False')
        ]
        if debug:
            print(f"  Previously installed parts: {len(previously_installed)}")
        
        for _, part in previously_installed.iterrows():
            if debug:
                print(f"    Checking previously installed: Install={part['PART_INSTALL_DATE']}, Remove={part['PART_REMOVE_DATE']}, End_time={subentity_end_time}")
            if (pd.notna(part['PART_INSTALL_DATE']) and 
                pd.notna(part['PART_REMOVE_DATE']) and
                part['PART_INSTALL_DATE'] < subentity_end_time < part['PART_REMOVE_DATE']):
                matching_parts.append(part)
                if debug:
                    print(f"    ✓ Match found (previously installed): {part['RECOAT']}")
            elif debug:
                print(f"    ✗ No match: Date range check failed")
        
        if debug:
            print(f"  Total matching parts: {len(matching_parts)}")
        
        if len(matching_parts) == 0:
            return 'NOTFOUND'
        elif len(matching_parts) == 1:
            # Special handling for LID - return INSTALL_COUNT instead of RECOAT
            if part_type == 'LID':
                install_count = matching_parts[0]['INSTALL_COUNT']
                if debug:
                    print(f"  Single match, LID INSTALL_COUNT: '{install_count}'")
                return install_count if pd.notna(install_count) else 'MISSING'
            
            # Original logic for all other part types
            recoat_val = str(matching_parts[0]['RECOAT'])
            if debug:
                print(f"  Single match, RECOAT value: '{recoat_val}'")
            if recoat_val.upper() == 'TRUE':
                return 'True'
            elif recoat_val.upper() == 'FALSE':
                return 'False'
            else:
                return recoat_val
        else:
            # Special handling for LID - return most recent INSTALL_COUNT
            if part_type == 'LID':
                # Get the most recent part (by install date) and return its counter value
                most_recent_part = max(matching_parts, key=lambda x: x['PART_INSTALL_DATE'] if pd.notna(x['PART_INSTALL_DATE']) else pd.Timestamp.min)
                install_count = most_recent_part['INSTALL_COUNT']
                if debug:
                    print(f"  Multiple matches, most recent LID INSTALL_COUNT: '{install_count}'")
                return install_count if pd.notna(install_count) else 'MISSING'
            
            # Original logic for all other part types
            recoat_values = [part['RECOAT'] for part in matching_parts]
            if debug:
                print(f"  Multiple matches, RECOAT values: {recoat_values}")
            
            if any(str(val).upper() == 'TRUE' for val in recoat_values):
                return 'True'
            elif any(str(val).upper() == 'MISSING' for val in recoat_values):
                return 'MISSING'
            elif all(str(val).upper() == 'FALSE' for val in recoat_values):
                return 'False'
            else:
                return 'MULTIPLE'
    
    # Process each row to determine RECOAT status for each part type
    print("Processing RECOAT status for each defect scan...")
    
    # Test with AME411_PM2 for debugging
    test_rows = dt[dt['SUBENTITY'] == 'AME411_PM2'].head(1)
    if not test_rows.empty:
        print("\n=== TESTING AME411_PM2 ===")
        for idx in test_rows.index:
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            print(f"\nRow {idx}: {subentity} at {subentity_end_time}")
            
            # Test just one part type first
            for part_type in ['PLSCR']:  # Test just one part type first
                recoat_status = get_recoat_status_by_part(subentity, subentity_end_time, part_type, debug=True)
                dt.at[idx, part_type] = recoat_status
                print(f"  {part_type}: {recoat_status}")
        print("=== END TEST ===\n")
    
    # Process all rows
    for idx in dt.index:
        row = dt.loc[idx]
        subentity = row['SUBENTITY']
        subentity_end_time = row['SUBENTITY_END_TIME']
        
        for part_type in part_types:
            recoat_status = get_recoat_status_by_part(subentity, subentity_end_time, part_type, debug=False)
            dt.at[idx, part_type] = recoat_status
    
    # Create final RECOAT column
    print("Creating final RECOAT column...")
    def determine_final_recoat(row):
        recoat_values = [row[part_type] for part_type in part_types]
        
        # Check if any column has TRUE (as string)
        if any(str(val).upper() == 'TRUE' for val in recoat_values):
            return True
        else:
            return False
    
    dt['RECOAT'] = dt.apply(determine_final_recoat, axis=1)
    
    # Add leak rate data
    dt = add_leak_rate_data(dt)
    
    # Add dry pump failure data
    dt = add_dp_fail_data(dt)
    
    # Add ELWC lookback data (NEW!)
    dt = add_elwc_lookbacks(dt)
    
    # Sort by SUBENTITY_END_TIME with most recent first
    dt = dt.sort_values('SUBENTITY_END_TIME', ascending=False)
    
    print("Processing complete!")
    print(f"Final dataframe shape: {dt.shape}")
    
    # Show summary of RECOAT results
    print(f"\nRECOAT Summary:")
    print(f"Final RECOAT column: {dt['RECOAT'].value_counts()}")
    for part_type in part_types:
        print(f"{part_type}: {dt[part_type].value_counts().to_dict()}")
    
    # Define desired column order (including new ELWC lookback columns)
    elwc_lookback_cols = [f'{group}_{window}HRS' 
                         for group in ['MONTW', '8GAB', '8THA', '8GOB', '8PIL', '8SIF', 
                                      '0GAB', '0THA', '0GOB', '0PIL', '0SIF']
                         for window in [4, 12, 36]]
    
    desired_order = [
        'LOT', 'WAFER_ID', 'PRODUCT', 'LAYER', 'SUBENTITY', 'OPERATION','RECIPE', 
        'SUBENTITY_END_TIME','PILOT_STATUS',  'SUM_NCDD', 'STATUS',  'INSPECT_TIME', 
        'INSPECT_TOOL', 'BEEP_NCDD', 'SMP_NCDD', 'ENTITY', 'LOT7', 'WAFER', 'SLOT', 'P_ORDER',
        'CCMR2', 'ICCR2', 'GF', 'CV', 'SRCIP', 'FULLPM', 'FULLPM_RF', 'MINIPM', 'MINIPM_RF', 
        'CNTR_SS', 'PL_RECIPE', 'PT_BTWN', 'PL_TIME', 'UPT_12HRS', 'UNW_12HRS', 'UP_12HRS',
        'PLSCR', 'SLD', 'LNRCAT', 'LNRTSG', 'SLVCAT', 'HUB', 'LID', 'SNZZL', 'RECOAT',
        'RAW_LEAK_RATE', 'SMOOTH_LEAK_RATE', 'DP_FAIL_HRS'
    ] + elwc_lookback_cols  # Add all ELWC lookback columns at the end
    
    # Reorder columns (existing columns in desired order + any remaining columns)
    existing_priority_cols = [col for col in desired_order if col in dt.columns]
    remaining_cols = [col for col in dt.columns if col not in desired_order]
    dt = dt[existing_priority_cols + remaining_cols]
    
    return dt

# Run the processing and save
if __name__ == "__main__":
    # Install tqdm if not already available
    try:
        from tqdm import tqdm
    except ImportError:
        print("Installing tqdm for progress bars...")
        import subprocess
        subprocess.check_call(["pip", "install", "tqdm"])
        from tqdm import tqdm
    
    processed_df = process_defect_data()
    
    # Save the result with ELWC lookbacks included
    save_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_NCDD_PST_WITH_ELWC_LOOKBACKS.csv"
    processed_df.to_csv(save_path, index=False)
    print(f"Processed data with ELWC lookbacks saved to: {save_path}")
    
    # Show final summary
    print(f"\nFinal enhanced dataframe shape: {processed_df.shape}")
    
    # Show sample of ELWC lookback columns
    elwc_cols = [col for col in processed_df.columns if any(group in col for group in ['MONTW', '8GAB', '0GAB'])]
    if elwc_cols:
        print(f"\nSample of ELWC lookback columns:")
        print(processed_df[['WAFER_ID', 'OPERATION', 'SUBENTITY'] + elwc_cols[:6]].head())