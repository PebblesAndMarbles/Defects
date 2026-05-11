# -*- coding: utf-8 -*-
"""
Add ELWC Lookback Metrics to Defect Data (Updated for Test Wafer Logic)
"""

def add_elwc_lookbacks():
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta
    from tqdm import tqdm
    
    print("=== ELWC LOOKBACK PROCESSING (Updated for Test Wafer Logic) ===")
    start_time = datetime.now()
    
    # File paths
    elwc_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\2025-12-22 185 days ALL_CHAMBERS ELWC.csv"
    defect_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_NCDD_PST.csv"
    
    # Load datasets
    print("Loading ELWC historical data...")
    elwc_df = pd.read_csv(elwc_path)
    print(f"ELWC data loaded: {len(elwc_df)} records")
    
    print("Loading defect data...")
    defect_df = pd.read_csv(defect_path)
    print(f"Defect data loaded: {len(defect_df)} records")
    
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
            defect_df[f'{group}_{window}HRS'] = np.nan
    
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
    test_rows = defect_df.head(3)
    for idx in test_rows.index:
        row = defect_df.loc[idx]
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
    
    for idx in tqdm(defect_df.index, desc="Processing defect rows"):
        row = defect_df.loc[idx]
        wafer_id = row['WAFER_ID']
        operation = row['OPERATION']
        
        results = calculate_lookbacks(wafer_id, operation, debug=False)
        
        # Update defect dataframe with results
        for col, value in results.items():
            defect_df.at[idx, col] = value
        
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
        non_null_count = defect_df[col].notna().sum()
        if non_null_count > 0:
            mean_val = defect_df[col].mean()
            max_val = defect_df[col].max()
            print(f"{col}: {non_null_count} non-null, mean={mean_val:.1f}, max={max_val}")
        else:
            print(f"{col}: All NaN")
    
    # Save enhanced defect data
    print("\nSaving enhanced defect data...")
    output_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_NCDD_PST_WITH_ELWC_LOOKBACKS.csv"
    defect_df.to_csv(output_path, index=False)
    
    total_time = (datetime.now() - start_time).total_seconds()
    print(f"\nProcessing completed in {total_time/60:.1f} minutes")
    print(f"Enhanced defect data saved to:")
    print(f"{output_path}")
    
    return defect_df

# Execute the function
if __name__ == "__main__":
    # Install tqdm if not already available
    try:
        from tqdm import tqdm
    except ImportError:
        print("Installing tqdm for progress bars...")
        import subprocess
        subprocess.check_call(["pip", "install", "tqdm"])
        from tqdm import tqdm
    
    enhanced_defect_df = add_elwc_lookbacks()
    print(f"\nFinal enhanced dataframe shape: {enhanced_defect_df.shape}")
    
    # Show sample of new columns
    lookback_cols = [col for col in enhanced_defect_df.columns if any(group in col for group in ['MONTW', '8GAB', '0GAB'])]
    print(f"\nSample of new lookback columns:")
    print(enhanced_defect_df[['WAFER_ID', 'OPERATION', 'SUBENTITY'] + lookback_cols[:6]].head())