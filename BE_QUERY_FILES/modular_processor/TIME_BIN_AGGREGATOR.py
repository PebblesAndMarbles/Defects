import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def create_time_periods(start_date, end_date, n_days=7):
    """
    Create fixed time periods of N days each
    """
    periods = []
    current_start = start_date
    
    while current_start < end_date:
        current_end = min(current_start + timedelta(days=n_days), end_date)
        periods.append((current_start, current_end))
        current_start = current_end
    
    return periods

def load_elwc_data_for_periods(elwc_filepath, periods, time_col='START_DATE', chamber_col='ENTITY'):
    """
    Load ELWC data for specific time periods with memory-efficient chunking
    """
    print("Loading ELWC data for fleet processing metrics...")
    
    # Find min/max dates across all periods
    all_starts = [p[0] for p in periods]
    all_ends = [p[1] for p in periods]
    data_start = min(all_starts)
    data_end = max(all_ends)
    
    print(f"   Target date range: {data_start.date()} to {data_end.date()}")
    
    # Load ELWC data in chunks
    chunk_size = 100000
    matching_elwc = []
    total_processed = 0
    
    for chunk in pd.read_csv(elwc_filepath, chunksize=chunk_size):
        total_processed += len(chunk)
        
        # Normalize column names to uppercase (handle mixed-case ELWC files)
        chunk.columns = chunk.columns.str.upper()
        
        # If the ELWC file doesn't have the expected time column, skip this chunk.
        if time_col not in chunk.columns:
            continue

        # Convert time column
        chunk[time_col] = pd.to_datetime(chunk[time_col], errors='coerce')
        
        # Filter to our date range
        period_chunk = chunk[
            (chunk[time_col] >= data_start) & 
            (chunk[time_col] < data_end)
        ]
        
        if len(period_chunk) > 0:
            matching_elwc.append(period_chunk)
        
        # Progress indicator
        if total_processed % 500000 == 0:
            print(f"   Processed {total_processed:,} ELWC records...")
    
    if matching_elwc:
        elwc_df = pd.concat(matching_elwc, ignore_index=True)
        print(f"Loaded {len(elwc_df):,} ELWC records for analysis period")
        print(f"   Memory usage: {elwc_df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
        return elwc_df
    else:
        print("No matching ELWC data found")
        # Return an empty frame with expected schema so downstream logic can run.
        return pd.DataFrame(columns=['START_DATE', 'LOT', 'ENTITY', 'SUBENTITY'])

def calculate_fleet_baselines_with_elwc(df, elwc_df, periods, n_days):
    """
    Calculate layer-specific fleet baselines AND fleet processing metrics for each period
    """
    
    print("Calculating fleet baselines with ELWC processing metrics...")

    # Ensure ELWC frame always has required columns so sparse windows do not crash.
    required_elwc_cols = ['START_DATE', 'LOT', 'ENTITY', 'SUBENTITY']
    if elwc_df is None:
        elwc_df = pd.DataFrame(columns=required_elwc_cols)
    else:
        elwc_df = elwc_df.copy()
        for col in required_elwc_cols:
            if col not in elwc_df.columns:
                elwc_df[col] = pd.Series(dtype='object')
    if 'START_DATE' in elwc_df.columns:
        elwc_df['START_DATE'] = pd.to_datetime(elwc_df['START_DATE'], errors='coerce')
    
    fleet_baselines = {}
    
    for period_start, period_end in periods:
        # Get defect data in this period
        period_data = df[
            (df['INSPECT_TIME'] >= period_start) & 
            (df['INSPECT_TIME'] < period_end)
        ]
        
        # Get ELWC data in this period
        period_elwc = elwc_df[
            (elwc_df['START_DATE'] >= period_start) &
            (elwc_df['START_DATE'] < period_end)
        ]
        
        # Fleet processing metrics (layer-agnostic)
        fleet_metrics = {
            'FLEET_TOTAL_WAFERS': len(period_elwc),
            'FLEET_UNIQUE_LOTS': period_elwc['LOT'].nunique() if len(period_elwc) > 0 else 0,
            'FLEET_ACTIVE_CHAMBERS': period_elwc['ENTITY'].nunique() if len(period_elwc) > 0 else 0,
            'FLEET_ACTIVE_SUBENTITIES': period_elwc['SUBENTITY'].nunique() if len(period_elwc) > 0 else 0,
        }
        
        # Chamber utilization
        if len(period_elwc) > 0:
            chamber_counts = period_elwc['ENTITY'].value_counts()
            fleet_metrics.update({
                'FLEET_TOP_CHAMBER': chamber_counts.index[0] if len(chamber_counts) > 0 else '',
                'FLEET_TOP_CHAMBER_WAFERS': chamber_counts.iloc[0] if len(chamber_counts) > 0 else 0,
                'FLEET_AVG_WAFERS_PER_CHAMBER': chamber_counts.mean(),
                'FLEET_CHAMBER_UTILIZATION_STD': chamber_counts.std(),
            })
        else:
            fleet_metrics.update({
                'FLEET_TOP_CHAMBER': '',
                'FLEET_TOP_CHAMBER_WAFERS': 0,
                'FLEET_AVG_WAFERS_PER_CHAMBER': 0,
                'FLEET_CHAMBER_UTILIZATION_STD': 0,
            })
        
        if len(period_data) == 0:
            # Still store fleet metrics even if no defect data
            for layer in df['LAYER'].unique():
                fleet_baselines[(period_start, layer)] = {
                    'BEEP_FLEET_RATE': np.nan,
                    'SMP_FLEET_RATE': np.nan,
                    'FLEET_WAFERS': 0,
                    **fleet_metrics
                }
            continue
            
        # Calculate fleet defect rates by layer
        for layer in period_data['LAYER'].unique():
            layer_data = period_data[period_data['LAYER'] == layer]
            
            if len(layer_data) > 0:
                # Fleet defect rates = total defective wafers / total wafers
                beep_defective = (layer_data['ZERO_BEEP'] == False).sum()
                smp_defective = (layer_data['ZERO_SMP'] == False).sum()
                total_wafers = len(layer_data)
                
                fleet_baselines[(period_start, layer)] = {
                    'BEEP_FLEET_RATE': beep_defective / total_wafers,
                    'SMP_FLEET_RATE': smp_defective / total_wafers,
                    'FLEET_WAFERS': total_wafers,
                    **fleet_metrics  # Add all fleet processing metrics
                }
    
    return fleet_baselines

def create_fixed_period_aggregation_with_elwc(
    df,
    elwc_filepath,
    n_days=7,
    min_samples=3,
    start_date_override=None,
):
    """
    Create fixed N-day period aggregation with fleet benchmarking AND ELWC processing metrics
    """
    
    print(f"CREATING FIXED {n_days}-DAY PERIOD AGGREGATION WITH FLEET BENCHMARKING + ELWC")
    print("=" * 80)
    
    # Prepare the data
    df = df.copy()
    df['INSPECT_TIME'] = pd.to_datetime(df['INSPECT_TIME'])
    
    # Convert ON/OFF to boolean for easier processing
    boolean_cols = ['CCMR2', 'ICCR2', 'GF', 'CV', 'SRCIP']
    for col in boolean_cols:
        if col in df.columns:
            df[f'{col}_BOOL'] = (df[col] == 'ON')
    
    # Get data range
    if start_date_override is not None:
        start_date = pd.to_datetime(start_date_override).normalize()
    else:
        start_date = df['INSPECT_TIME'].min().normalize()
    end_date = df['INSPECT_TIME'].max().normalize() + timedelta(days=1)
    
    print(f"Data range: {start_date.date()} to {end_date.date()}")
    
    # Create time periods
    periods = create_time_periods(start_date, end_date, n_days)
    print(f"Created {len(periods)} periods of {n_days} days each")
    
    # Load ELWC data for these periods
    elwc_df = load_elwc_data_for_periods(elwc_filepath, periods)
    
    # Calculate fleet baselines with ELWC metrics for each period-layer combination
    fleet_baselines = calculate_fleet_baselines_with_elwc(df, elwc_df, periods, n_days)
    
    # Get unique combinations of DEVICE and LAYER
    device_layer_combos = df[['DEVICE', 'LAYER']].drop_duplicates()
    print(f"Processing {len(device_layer_combos)} DEVICE-LAYER combinations...")
    
    all_results = []
    
    for _, combo in device_layer_combos.iterrows():
        device = combo['DEVICE']
        layer = combo['LAYER']
        
        # Filter data for this device-layer combination
        group_df = df[(df['DEVICE'] == device) & (df['LAYER'] == layer)]
        
        print(f"  {device}-{layer}: {len(group_df)} wafers")
        
        # Process each time period
        for period_start, period_end in periods:
            # Get data in this period
            period_data = group_df[
                (group_df['INSPECT_TIME'] >= period_start) & 
                (group_df['INSPECT_TIME'] < period_end)
            ]
            
            # Skip if insufficient data
            if len(period_data) < min_samples:
                continue
            
            # Get fleet baseline for this period-layer (now includes ELWC metrics)
            fleet_baseline = fleet_baselines.get((period_start, layer), {})
            
            # Create aggregated row for this period
            agg_row = create_period_aggregated_row_with_elwc(
                period_data, period_start, period_end, device, layer, n_days, fleet_baseline
            )
            all_results.append(agg_row)
    
    # Convert to DataFrame
    result_df = pd.DataFrame(all_results)
    
    if len(result_df) > 0:
        result_df = result_df.sort_values(['DEVICE', 'LAYER', 'PERIOD_START'])
    
    print(f"Created {len(result_df)} period aggregations from {len(df)} input wafers")
    if len(result_df) > 0:
        print(f"Compression ratio: {len(df)/len(result_df):.1f}x")
    else:
        print("Compression ratio: N/A (no aggregation rows created)")
    
    return result_df

def create_period_aggregated_row_with_elwc(period_data, period_start, period_end, device, layer, n_days, fleet_baseline):
    """
    Create a single aggregated row from period data with fleet benchmarking AND ELWC metrics
    """
    
    agg_row = {
        'PERIOD_START': period_start.date(),
        'PERIOD_END': (period_end - timedelta(days=1)).date(),
        'DEVICE': device,
        'LAYER': layer,
        'PERIOD_DAYS': n_days,
        'SAMPLE_SIZE': len(period_data),
        'FIRST_WAFER_TIME': period_data['INSPECT_TIME'].min(),
        'LAST_WAFER_TIME': period_data['INSPECT_TIME'].max()
    }
    
    # 1. DEVICE DEFECT RATES
    if 'ZERO_BEEP' in period_data.columns:
        beep_defective_count = (period_data['ZERO_BEEP'] == False).sum()
        beep_rate = beep_defective_count / len(period_data)
        agg_row['BEEP_RATE'] = beep_rate
        agg_row['BEEP_DEFECTIVE_COUNT'] = beep_defective_count
    
    if 'ZERO_SMP' in period_data.columns:
        smp_defective_count = (period_data['ZERO_SMP'] == False).sum()
        smp_rate = smp_defective_count / len(period_data)
        agg_row['SMP_RATE'] = smp_rate
        agg_row['SMP_DEFECTIVE_COUNT'] = smp_defective_count
    
    # 2. FLEET BASELINES (from fleet_baseline dict)
    agg_row['BEEP_FLEET_RATE'] = fleet_baseline.get('BEEP_FLEET_RATE', np.nan)
    agg_row['SMP_FLEET_RATE'] = fleet_baseline.get('SMP_FLEET_RATE', np.nan)
    agg_row['FLEET_WAFERS'] = fleet_baseline.get('FLEET_WAFERS', 0)
    
    # 3. ELWC FLEET PROCESSING METRICS (NEW!)
    agg_row['FLEET_TOTAL_WAFERS'] = fleet_baseline.get('FLEET_TOTAL_WAFERS', 0)
    agg_row['FLEET_UNIQUE_LOTS'] = fleet_baseline.get('FLEET_UNIQUE_LOTS', 0)
    agg_row['FLEET_ACTIVE_CHAMBERS'] = fleet_baseline.get('FLEET_ACTIVE_CHAMBERS', 0)
    agg_row['FLEET_ACTIVE_SUBENTITIES'] = fleet_baseline.get('FLEET_ACTIVE_SUBENTITIES', 0)
    agg_row['FLEET_TOP_CHAMBER'] = fleet_baseline.get('FLEET_TOP_CHAMBER', '')
    agg_row['FLEET_TOP_CHAMBER_WAFERS'] = fleet_baseline.get('FLEET_TOP_CHAMBER_WAFERS', 0)
    agg_row['FLEET_AVG_WAFERS_PER_CHAMBER'] = fleet_baseline.get('FLEET_AVG_WAFERS_PER_CHAMBER', 0)
    agg_row['FLEET_CHAMBER_UTILIZATION_STD'] = fleet_baseline.get('FLEET_CHAMBER_UTILIZATION_STD', 0)
    
    # 4. FLEET CONTEXT RATIOS (NEW!)
    if agg_row['FLEET_TOTAL_WAFERS'] > 0:
        agg_row['DEVICE_SHARE_OF_FLEET'] = agg_row['SAMPLE_SIZE'] / agg_row['FLEET_TOTAL_WAFERS']
        agg_row['DEFECT_SAMPLE_RATE'] = agg_row['FLEET_WAFERS'] / agg_row['FLEET_TOTAL_WAFERS']
    else:
        agg_row['DEVICE_SHARE_OF_FLEET'] = 0
        agg_row['DEFECT_SAMPLE_RATE'] = 0
    
    # 5. WEIGHTED DEVICE RATES
    if agg_row['FLEET_WAFERS'] > 0:
        device_weight = agg_row['SAMPLE_SIZE'] / agg_row['FLEET_WAFERS']
        agg_row['BEEP_WEIGHTED_RATE'] = agg_row['BEEP_RATE'] * device_weight
        agg_row['SMP_WEIGHTED_RATE'] = agg_row['SMP_RATE'] * device_weight
    else:
        agg_row['BEEP_WEIGHTED_RATE'] = np.nan
        agg_row['SMP_WEIGHTED_RATE'] = np.nan
    
    # 6. EXPECTED DEFECTS (device wafers x fleet rate)
    if not pd.isna(agg_row['BEEP_FLEET_RATE']):
        agg_row['BEEP_EXPECTED'] = agg_row['SAMPLE_SIZE'] * agg_row['BEEP_FLEET_RATE']
    else:
        agg_row['BEEP_EXPECTED'] = np.nan
        
    if not pd.isna(agg_row['SMP_FLEET_RATE']):
        agg_row['SMP_EXPECTED'] = agg_row['SAMPLE_SIZE'] * agg_row['SMP_FLEET_RATE']
    else:
        agg_row['SMP_EXPECTED'] = np.nan
    
    # 7. OBSERVED DEFECTS
    agg_row['BEEP_OBSERVED'] = agg_row.get('BEEP_DEFECTIVE_COUNT', 0)
    agg_row['SMP_OBSERVED'] = agg_row.get('SMP_DEFECTIVE_COUNT', 0)
    
    # 8. EXCESS DEFECTS (observed - expected)
    if not pd.isna(agg_row['BEEP_EXPECTED']):
        agg_row['BEEP_EXCESS'] = agg_row['BEEP_OBSERVED'] - agg_row['BEEP_EXPECTED']
    else:
        agg_row['BEEP_EXCESS'] = np.nan
        
    if not pd.isna(agg_row['SMP_EXPECTED']):
        agg_row['SMP_EXCESS'] = agg_row['SMP_OBSERVED'] - agg_row['SMP_EXPECTED']
    else:
        agg_row['SMP_EXCESS'] = np.nan
    
    # 9. BOOLEAN RATES (fraction of TRUE/ON)
    boolean_cols = ['CCMR2_BOOL', 'ICCR2_BOOL', 'GF_BOOL', 'CV_BOOL', 'SRCIP_BOOL']
    for col in boolean_cols:
        if col in period_data.columns:
            true_rate = period_data[col].mean()
            col_name = col.replace('_BOOL', '')
            agg_row[f'{col_name}_ON_RATE'] = true_rate
    
    # 10. NUMERIC COLUMNS - Split by BEEP and SMP defects
    numeric_cols = ['P_ORDER', 'UNW_12HRS']
    
    for num_col in numeric_cols:
        if num_col in period_data.columns:
            
            # Split by BEEP defects
            if 'ZERO_BEEP' in period_data.columns:
                beep_clean = period_data[period_data['ZERO_BEEP'] == True][num_col]
                beep_defective = period_data[period_data['ZERO_BEEP'] == False][num_col]
                
                agg_row[f'{num_col}_BEEP_CLEAN_AVG'] = beep_clean.mean() if len(beep_clean) > 0 else np.nan
                agg_row[f'{num_col}_BEEP_DEFECTIVE_AVG'] = beep_defective.mean() if len(beep_defective) > 0 else np.nan
                agg_row[f'{num_col}_BEEP_CLEAN_COUNT'] = len(beep_clean)
                agg_row[f'{num_col}_BEEP_DEFECTIVE_COUNT'] = len(beep_defective)
            
            # Split by SMP defects
            if 'ZERO_SMP' in period_data.columns:
                smp_clean = period_data[period_data['ZERO_SMP'] == True][num_col]
                smp_defective = period_data[period_data['ZERO_SMP'] == False][num_col]
                
                agg_row[f'{num_col}_SMP_CLEAN_AVG'] = smp_clean.mean() if len(smp_clean) > 0 else np.nan
                agg_row[f'{num_col}_SMP_DEFECTIVE_AVG'] = smp_defective.mean() if len(smp_defective) > 0 else np.nan
                agg_row[f'{num_col}_SMP_CLEAN_COUNT'] = len(smp_clean)
                agg_row[f'{num_col}_SMP_DEFECTIVE_COUNT'] = len(smp_defective)
    
    # 11. COUNT TOTALS (with unique lot averaging for N_SCAN)
    count_cols = ['S_SCAN', 'N_SCAN']
    for col in count_cols:
        if col in period_data.columns:
            agg_row[f'{col}_TOTAL'] = period_data[col].sum()
            
            # Unique lot average for N_SCAN (avoid double-counting lots)
            if col == 'N_SCAN' and 'LOT' in period_data.columns:
                unique_lot_values = period_data.groupby('LOT')[col].first()
                agg_row[f'{col}_UNIQUE_AVG'] = unique_lot_values.mean()
                agg_row[f'{col}_UNIQUE_LOTS'] = len(unique_lot_values)
            else:
                agg_row[f'{col}_AVG'] = period_data[col].mean()
    
    return agg_row

def analyze_fleet_benchmarking_with_elwc_results(df, n_days):
    """
    Analyze the results with focus on fleet benchmarking AND ELWC processing metrics
    """
    print(f"\n{n_days}-DAY FLEET BENCHMARKING + ELWC ANALYSIS")
    print("=" * 60)
    
    print("Dataset Overview:")
    print(f"  Total periods: {len(df):,}")
    print(f"  Date range: {df['PERIOD_START'].min()} to {df['PERIOD_END'].max()}")
    
    print("\nGrouping Summary:")
    devices = sorted(df['DEVICE'].unique())
    layers = sorted(df['LAYER'].unique())
    print(f"  Devices ({len(devices)}): {devices}")
    print(f"  Layers ({len(layers)}): {layers}")
    
    print("\nFleet Processing Overview:")
    total_fleet_wafers = df['FLEET_TOTAL_WAFERS'].sum()
    avg_chambers = df['FLEET_ACTIVE_CHAMBERS'].mean()
    avg_lots = df['FLEET_UNIQUE_LOTS'].mean()
    
    print(f"  Total fleet wafers processed: {total_fleet_wafers:,}")
    print(f"  Average active chambers per period: {avg_chambers:.1f}")
    print(f"  Average unique lots per period: {avg_lots:.1f}")
    
    # Top chambers analysis
    if 'FLEET_TOP_CHAMBER' in df.columns:
        top_chambers = df['FLEET_TOP_CHAMBER'].value_counts().head()
        print(f"  Most frequently top-producing chambers:")
        for chamber, count in top_chambers.items():
            if chamber:  # Skip empty strings
                print(f"    {chamber}: {count} periods")
    
    print("\nFleet vs Device Performance:")
    
    for layer in layers:
        layer_data = df[df['LAYER'] == layer]
        if len(layer_data) == 0:
            continue
            
        print(f"\n  {layer} Layer:")
        
        # Fleet averages
        fleet_beep = layer_data['BEEP_FLEET_RATE'].mean()
        fleet_smp = layer_data['SMP_FLEET_RATE'].mean()
        print(f"    Fleet BEEP rate: {fleet_beep:.3f} ({fleet_beep*100:.1f}%)")
        print(f"    Fleet SMP rate:  {fleet_smp:.3f} ({fleet_smp*100:.1f}%)")
        
        # Device performance vs fleet
        print(f"    Device performance vs fleet:")
        for device in devices:
            device_data = layer_data[layer_data['DEVICE'] == device]
            if len(device_data) == 0:
                continue
                
            avg_beep_rate = device_data['BEEP_RATE'].mean()
            avg_smp_rate = device_data['SMP_RATE'].mean()
            avg_beep_excess = device_data['BEEP_EXCESS'].mean()
            avg_smp_excess = device_data['SMP_EXCESS'].mean()
            avg_fleet_share = device_data['DEVICE_SHARE_OF_FLEET'].mean()
            
            print(f"      {device}: BEEP {avg_beep_rate:.3f} (excess: {avg_beep_excess:+.1f}), SMP {avg_smp_rate:.3f} (excess: {avg_smp_excess:+.1f}), Fleet share: {avg_fleet_share:.1%}")
    
    print("\nSample Size Distribution:")
    sample_stats = df['SAMPLE_SIZE'].describe()
    print(f"  Min samples per period: {sample_stats['min']:.0f}")
    print(f"  Mean samples per period: {sample_stats['mean']:.1f}")
    print(f"  Max samples per period: {sample_stats['max']:.0f}")
    
    print("\nFleet Context:")
    fleet_share_stats = df['DEVICE_SHARE_OF_FLEET'].describe()
    print(f"  Device share of fleet processing:")
    print(f"    Min: {fleet_share_stats['min']:.1%}")
    print(f"    Mean: {fleet_share_stats['mean']:.1%}")
    print(f"    Max: {fleet_share_stats['max']:.1%}")

def main():
    """
    Main execution function with ELWC integration
    """
    
    # CONFIGURATION
    defect_filepath = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_202606.csv"
    elwc_filepath = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\ELWC\COMBINED_ELWC_DEDUPLICATED.csv"  # Your combined file
    
    # CONFIGURABLE PARAMETERS
    N_DAYS_OPTIONS = [7]  # Start with 7-day periods
    MIN_SAMPLES = 10
    
    print("FLEET BENCHMARKING + ELWC AGGREGATION PROCESSOR")
    print("=" * 70)
    
    # Load data
    print("Loading defect data from file...")
    try:
        df = pd.read_csv(defect_filepath)
        print(f"Successfully loaded {len(df):,} defect records x {len(df.columns)} columns")
        
        # Check if INSPECT_TIME exists
        if 'INSPECT_TIME' not in df.columns:
            print("INSPECT_TIME column not found!")
            print(f"Available time columns: {[col for col in df.columns if 'TIME' in col.upper()]}")
            return
            
    except Exception as e:
        print(f"Error loading defect data: {e}")
        return
    
    # Process each time period size
    for n_days in N_DAYS_OPTIONS:
        print(f"\n" + "="*70)
        print(f"PROCESSING {n_days}-DAY FIXED PERIODS WITH FLEET BENCHMARKING + ELWC")
        print(f"="*70)
        
        # Create aggregation with ELWC
        agg_df = create_fixed_period_aggregation_with_elwc(
            df, elwc_filepath, n_days=n_days, min_samples=MIN_SAMPLES
        )
        
        if len(agg_df) > 0:
            # Analyze results
            analyze_fleet_benchmarking_with_elwc_results(agg_df, n_days)
            
            # Save results
            output_path = defect_filepath.replace('.csv', f'_FLEET_BENCHMARK_ELWC_{n_days}DAY.csv')
            agg_df.to_csv(output_path, index=False)
            print(f"\nSaved {n_days}-day fleet benchmark + ELWC: {output_path}")
            
        else:
            print(f"WARNING: No data met minimum sample requirements for {n_days}-day periods")
    
    print("\nPROCESSING COMPLETE!")

if __name__ == "__main__":
    main()