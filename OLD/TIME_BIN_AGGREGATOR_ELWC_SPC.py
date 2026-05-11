import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# File paths
surf_scan_file = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\SPC_MONS\RAW_TOTAL_ADDERS.csv"
wafer_data_file = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\2026-01-12 420 days ALL_CHAMBERS ELWC.csv"

# Output folder
output_folder = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE"

# CONFIGURABLE PARAMETER - Change this to adjust window size
DAYS_PER_WINDOW = 7  # Change to 3, 30, or whatever you want

def analyze_data_types_and_structure(df, dataset_name):
    """
    Analyze the data types and structure of the DataFrame
    """
    print(f"=== DATA TYPE ANALYSIS - {dataset_name} ===")
    print(f"DataFrame shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print("\nFirst few rows:")
    print(df.head())
    
    if dataset_name == "SURF SCAN DATA":
        print("\nPROCESS_DATE column info:")
        if 'PROCESS_DATE' in df.columns:
            print(f"Non-null dates: {df['PROCESS_DATE'].notna().sum()}")
            print(f"Date range: {df['PROCESS_DATE'].min()} to {df['PROCESS_DATE'].max()}")
    
    elif dataset_name == "WAFER DATA":
        print("\nSTART_DATE column info:")
        if 'START_DATE' in df.columns:
            print(f"Non-null dates: {df['START_DATE'].notna().sum()}")
            print(f"Date range: {df['START_DATE'].min()} to {df['START_DATE'].max()}")
    
    print("=" * 50)

def create_optimized_windows(surf_df, wafer_df, days_per_window):
    """
    Optimized window creation for large datasets using pandas operations
    """
    print("Processing surf scan data...")
    # Convert dates efficiently
    surf_df['PROCESS_DATE'] = pd.to_datetime(surf_df['PROCESS_DATE'], errors='coerce').dt.date
    surf_clean = surf_df.dropna(subset=['PROCESS_DATE', 'VALUE']).copy()
    
    print("Processing wafer data...")
    # For large wafer dataset, process more efficiently
    wafer_df['START_DATE'] = pd.to_datetime(wafer_df['START_DATE'], errors='coerce').dt.date
    wafer_clean = wafer_df.dropna(subset=['START_DATE']).copy()
    
    # Get date ranges
    surf_min = surf_clean['PROCESS_DATE'].min() if len(surf_clean) > 0 else None
    surf_max = surf_clean['PROCESS_DATE'].max() if len(surf_clean) > 0 else None
    wafer_min = wafer_clean['START_DATE'].min() if len(wafer_clean) > 0 else None
    wafer_max = wafer_clean['START_DATE'].max() if len(wafer_clean) > 0 else None
    
    # Determine overall date range
    min_date = min([d for d in [surf_min, wafer_min] if d is not None])
    max_date = max([d for d in [surf_max, wafer_max] if d is not None])
    
    print(f"Creating {days_per_window}-day windows from {min_date} to {max_date}")
    print(f"Surf scan data: {surf_min} to {surf_max} ({len(surf_clean)} records)")
    print(f"Wafer data: {wafer_min} to {wafer_max} ({len(wafer_clean)} records)")
    
    # Create window boundaries more efficiently
    current_date = min_date
    window_boundaries = []
    window_id = 1
    
    while current_date <= max_date:
        period_start = current_date
        period_end = min(current_date + timedelta(days=days_per_window - 1), max_date)
        
        window_boundaries.append({
            'WINDOW_ID': window_id,
            'PERIOD_START': period_start,
            'PERIOD_END': period_end
        })
        
        current_date = period_end + timedelta(days=1)
        window_id += 1
    
    windows_df = pd.DataFrame(window_boundaries)
    print(f"Created {len(windows_df)} windows")
    
    # OPTIMIZED: Use pandas cut/groupby instead of row-by-row assignment
    print("Assigning surf scan data to windows...")
    
    # Create a mapping of dates to window IDs
    date_to_window = {}
    for _, window in windows_df.iterrows():
        current = window['PERIOD_START']
        while current <= window['PERIOD_END']:
            date_to_window[current] = {
                'WINDOW_ID': window['WINDOW_ID'],
                'PERIOD_START': window['PERIOD_START'],
                'PERIOD_END': window['PERIOD_END']
            }
            current += timedelta(days=1)
    
    # Map surf scan data
    surf_clean['WINDOW_ID'] = surf_clean['PROCESS_DATE'].map(lambda x: date_to_window.get(x, {}).get('WINDOW_ID'))
    surf_clean['PERIOD_START'] = surf_clean['PROCESS_DATE'].map(lambda x: date_to_window.get(x, {}).get('PERIOD_START'))
    surf_clean['PERIOD_END'] = surf_clean['PROCESS_DATE'].map(lambda x: date_to_window.get(x, {}).get('PERIOD_END'))
    surf_clean = surf_clean.dropna(subset=['WINDOW_ID'])
    
    print("Assigning wafer data to windows (this may take a moment for large datasets)...")
    
    # OPTIMIZED: Use vectorized operations for wafer data
    wafer_clean['WINDOW_ID'] = wafer_clean['START_DATE'].map(lambda x: date_to_window.get(x, {}).get('WINDOW_ID'))
    wafer_clean['PERIOD_START'] = wafer_clean['START_DATE'].map(lambda x: date_to_window.get(x, {}).get('PERIOD_START'))
    wafer_clean['PERIOD_END'] = wafer_clean['START_DATE'].map(lambda x: date_to_window.get(x, {}).get('PERIOD_END'))
    wafer_clean = wafer_clean.dropna(subset=['WINDOW_ID'])
    
    print(f"Final assignment complete:")
    print(f"Surf scan data in windows: {len(surf_clean)} records")
    print(f"Wafer data in windows: {len(wafer_clean)} records")
    
    return surf_clean, wafer_clean, windows_df

def calculate_integrated_statistics_fast(surf_df, wafer_df):
    """
    Fast calculation of integrated statistics using pandas groupby
    """
    print("Calculating surf scan statistics...")
    # Surf scan statistics - vectorized operations
    surf_stats = surf_df.groupby(['WINDOW_ID']).agg({
        'VALUE': ['count', 'mean', 'std', 'min', 'max'],
        'PERIOD_START': 'first',
        'PERIOD_END': 'first'
    })
    
    # Flatten column names
    surf_stats.columns = ['SURF_SCAN_COUNT', 'MEAN_TOTAL_ADDERS', 'STD_VALUE', 'MIN_VALUE', 'MAX_VALUE', 'PERIOD_START', 'PERIOD_END']
    
    # Calculate zero/non-zero counts efficiently
    zero_nonzero = surf_df.groupby('WINDOW_ID')['VALUE'].apply(lambda x: pd.Series({
        'NON_ZERO_COUNT': (x != 0).sum(),
        'ZERO_COUNT': (x == 0).sum()
    })).unstack()
    
    surf_stats = surf_stats.join(zero_nonzero)
    
    print("Calculating wafer statistics...")
    # Wafer statistics - simple count
    wafer_stats = wafer_df.groupby('WINDOW_ID').size().to_frame('WAFER_COUNT')
    
    print("Combining statistics...")
    # Combine statistics
    combined_stats = surf_stats.join(wafer_stats, how='outer').fillna(0)
    
    # Calculate ZERO_SS
    combined_stats['ZERO_SS'] = np.where(
        combined_stats['SURF_SCAN_COUNT'] > 0,
        (combined_stats['NON_ZERO_COUNT'] / combined_stats['SURF_SCAN_COUNT']).round(4),
        0
    )
    
    # Reset index and format
    combined_stats = combined_stats.reset_index()
    
    # Format dates
    combined_stats['PERIOD_START'] = combined_stats['PERIOD_START'].apply(lambda x: x.strftime('%Y/%m/%d'))
    combined_stats['PERIOD_END'] = combined_stats['PERIOD_END'].apply(lambda x: x.strftime('%Y/%m/%d'))
    
    # Convert to integers where appropriate
    int_columns = ['SURF_SCAN_COUNT', 'NON_ZERO_COUNT', 'ZERO_COUNT', 'WAFER_COUNT']
    for col in int_columns:
        combined_stats[col] = combined_stats[col].astype(int)
    
    # Round numeric columns
    combined_stats['MEAN_TOTAL_ADDERS'] = combined_stats['MEAN_TOTAL_ADDERS'].round(4)
    combined_stats['STD_VALUE'] = combined_stats['STD_VALUE'].round(4)
    
    # Reorder columns
    column_order = ['WINDOW_ID', 'PERIOD_START', 'PERIOD_END', 'SURF_SCAN_COUNT', 'WAFER_COUNT',
                   'ZERO_SS', 'MEAN_TOTAL_ADDERS', 'NON_ZERO_COUNT', 'ZERO_COUNT', 
                   'STD_VALUE', 'MIN_VALUE', 'MAX_VALUE']
    combined_stats = combined_stats[column_order]
    
    return combined_stats

def main():
    """
    Optimized main function for large datasets
    """
    try:
        # Check if files exist
        if not os.path.exists(surf_scan_file):
            print(f"Error: Surf scan file not found at {surf_scan_file}")
            return
        
        if not os.path.exists(wafer_data_file):
            print(f"Error: Wafer data file not found at {wafer_data_file}")
            return
        
        print(f"Loading data with {DAYS_PER_WINDOW}-day windows...")
        
        # Load surf scan data
        print("Loading surf scan data...")
        surf_df = pd.read_csv(surf_scan_file)
        analyze_data_types_and_structure(surf_df, "SURF SCAN DATA")
        
        # Load wafer data with progress indication
        print("Loading wafer data (large file - please wait)...")
        wafer_df = pd.read_csv(wafer_data_file)
        analyze_data_types_and_structure(wafer_df, "WAFER DATA")
        
        # Check required columns
        if 'VALUE' not in surf_df.columns or 'PROCESS_DATE' not in surf_df.columns:
            print("Error: Missing required columns in surf scan data")
            return
        
        if 'START_DATE' not in wafer_df.columns:
            print("Error: Missing START_DATE column in wafer data")
            return
        
        print("Creating optimized date windows...")
        surf_windowed, wafer_windowed, windows_df = create_optimized_windows(
            surf_df, wafer_df, DAYS_PER_WINDOW
        )
        
        print("Calculating integrated statistics...")
        summary_df = calculate_integrated_statistics_fast(surf_windowed, wafer_windowed)
        
        # Display results
        print(f"\n=== INTEGRATED SUMMARY RESULTS ({DAYS_PER_WINDOW}-DAY WINDOWS) ===")
        print(summary_df.to_string(index=False))
        
        # Save results
        output_file = os.path.join(output_folder, f"integrated_surf_wafer_{DAYS_PER_WINDOW}day_summary.csv")
        
        try:
            summary_df.to_csv(output_file, index=False)
            print(f"\nResults saved to: {output_file}")
        except Exception as e:
            print(f"Could not save to network folder: {e}")
            fallback_file = f"integrated_surf_wafer_{DAYS_PER_WINDOW}day_summary.csv"
            summary_df.to_csv(fallback_file, index=False)
            print(f"Results saved to current directory: {fallback_file}")
        
        # Quick insights
        print(f"\n=== QUICK INSIGHTS ===")
        print(f"Total windows: {len(summary_df)}")
        print(f"Average wafers per window: {summary_df['WAFER_COUNT'].mean():.1f}")
        print(f"Total wafers: {summary_df['WAFER_COUNT'].sum()}")
        print(f"Average ZERO_SS: {summary_df['ZERO_SS'].mean():.4f}")
        
        return summary_df
        
    except Exception as e:
        print(f"Error processing data: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = main()