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

def create_fixed_period_aggregation(df, n_days=7, min_samples=3):
    """
    Create fixed N-day period aggregation with fleet benchmarking
    """
    
    print(f"📅 CREATING FIXED {n_days}-DAY PERIOD AGGREGATION WITH FLEET BENCHMARKING")
    print("=" * 70)
    
    # Prepare the data
    df = df.copy()
    df['INSPECT_TIME'] = pd.to_datetime(df['INSPECT_TIME'])
    
    # Convert ON/OFF to boolean for easier processing
    boolean_cols = ['CCMR2', 'ICCR2', 'GF', 'CV', 'SRCIP']
    for col in boolean_cols:
        if col in df.columns:
            df[f'{col}_BOOL'] = (df[col] == 'ON')
    
    # Get data range
    start_date = df['INSPECT_TIME'].min().normalize()
    end_date = df['INSPECT_TIME'].max().normalize() + timedelta(days=1)
    
    print(f"📊 Data range: {start_date.date()} to {end_date.date()}")
    
    # Create time periods
    periods = create_time_periods(start_date, end_date, n_days)
    print(f"📊 Created {len(periods)} periods of {n_days} days each")
    
    # Calculate fleet baselines for each period-layer combination
    fleet_baselines = calculate_fleet_baselines(df, periods, n_days)
    
    # Get unique combinations of DEVICE and LAYER
    device_layer_combos = df[['DEVICE', 'LAYER']].drop_duplicates()
    print(f"📊 Processing {len(device_layer_combos)} DEVICE-LAYER combinations...")
    
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
            
            # Get fleet baseline for this period-layer
            fleet_baseline = fleet_baselines.get((period_start, layer), {})
            
            # Create aggregated row for this period
            agg_row = create_period_aggregated_row(
                period_data, period_start, period_end, device, layer, n_days, fleet_baseline
            )
            all_results.append(agg_row)
    
    # Convert to DataFrame
    result_df = pd.DataFrame(all_results)
    
    if len(result_df) > 0:
        result_df = result_df.sort_values(['DEVICE', 'LAYER', 'PERIOD_START'])
    
    print(f"✅ Created {len(result_df)} period aggregations from {len(df)} input wafers")
    print(f"📉 Compression ratio: {len(df)/len(result_df):.1f}x")
    
    return result_df

def create_period_aggregated_row(period_data, period_start, period_end, device, layer, n_days, fleet_baseline):
    """
    Create a single aggregated row from period data with fleet benchmarking
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
    
    # 1. DEVICE DEFECT RATES (renamed from ZERO_*_DEFECT_RATE)
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
    
    # 2. BSL COLUMNS (filtered by STATUS_* = 'BSL')
    # BEEP BSL
    if all(col in period_data.columns for col in ['BEEP_NCDD', 'STATUS_BEEP']):
        beep_bsl_data = period_data[period_data['STATUS_BEEP'] == 'BSL']['BEEP_NCDD']
        if len(beep_bsl_data) > 0:
            agg_row['BEEP_BSL'] = beep_bsl_data.mean()
            agg_row['BEEP_BSL_COUNT'] = len(beep_bsl_data)
        else:
            agg_row['BEEP_BSL'] = np.nan
            agg_row['BEEP_BSL_COUNT'] = 0
    else:
        agg_row['BEEP_BSL'] = np.nan
        agg_row['BEEP_BSL_COUNT'] = 0
    
    # SMP BSL
    if all(col in period_data.columns for col in ['SMP_NCDD', 'STATUS_SMP']):
        smp_bsl_data = period_data[period_data['STATUS_SMP'] == 'BSL']['SMP_NCDD']
        if len(smp_bsl_data) > 0:
            agg_row['SMP_BSL'] = smp_bsl_data.mean()
            agg_row['SMP_BSL_COUNT'] = len(smp_bsl_data)
        else:
            agg_row['SMP_BSL'] = np.nan
            agg_row['SMP_BSL_COUNT'] = 0
    else:
        agg_row['SMP_BSL'] = np.nan
        agg_row['SMP_BSL_COUNT'] = 0
    
    # 3. FLEET BASELINES (from fleet_baseline dict)
    agg_row['BEEP_FLEET_RATE'] = fleet_baseline.get('BEEP_FLEET_RATE', np.nan)
    agg_row['SMP_FLEET_RATE'] = fleet_baseline.get('SMP_FLEET_RATE', np.nan)
    agg_row['BEEP_FLEET_BSL'] = fleet_baseline.get('BEEP_FLEET_BSL', np.nan)
    agg_row['SMP_FLEET_BSL'] = fleet_baseline.get('SMP_FLEET_BSL', np.nan)
    agg_row['FLEET_WAFERS'] = fleet_baseline.get('FLEET_WAFERS', 0)
    agg_row['FLEET_BSL_WAFERS'] = fleet_baseline.get('FLEET_BSL_WAFERS', 0)
    
    # 4. WEIGHTED DEVICE RATES AND BSL
    if agg_row['FLEET_WAFERS'] > 0:
        device_weight = agg_row['SAMPLE_SIZE'] / agg_row['FLEET_WAFERS']
        agg_row['BEEP_RATE_WEIGHTED'] = agg_row['BEEP_RATE'] * device_weight
        agg_row['SMP_RATE_WEIGHTED'] = agg_row['SMP_RATE'] * device_weight
    else:
        agg_row['BEEP_RATE_WEIGHTED'] = np.nan
        agg_row['SMP_RATE_WEIGHTED'] = np.nan
    
    # BSL weighted (use BSL sample count for weighting)
    if agg_row['FLEET_BSL_WAFERS'] > 0:
        beep_bsl_weight = agg_row['BEEP_BSL_COUNT'] / agg_row['FLEET_BSL_WAFERS']
        smp_bsl_weight = agg_row['SMP_BSL_COUNT'] / agg_row['FLEET_BSL_WAFERS']
        
        if not pd.isna(agg_row['BEEP_BSL']):
            agg_row['BEEP_BSL_WEIGHTED'] = agg_row['BEEP_BSL'] * beep_bsl_weight
        else:
            agg_row['BEEP_BSL_WEIGHTED'] = np.nan
            
        if not pd.isna(agg_row['SMP_BSL']):
            agg_row['SMP_BSL_WEIGHTED'] = agg_row['SMP_BSL'] * smp_bsl_weight
        else:
            agg_row['SMP_BSL_WEIGHTED'] = np.nan
    else:
        agg_row['BEEP_BSL_WEIGHTED'] = np.nan
        agg_row['SMP_BSL_WEIGHTED'] = np.nan
    
    # 5. EXPECTED DEFECTS (device wafers × fleet rate)
    if not pd.isna(agg_row['BEEP_FLEET_RATE']):
        agg_row['BEEP_EXPECTED'] = agg_row['SAMPLE_SIZE'] * agg_row['BEEP_FLEET_RATE']
    else:
        agg_row['BEEP_EXPECTED'] = np.nan
        
    if not pd.isna(agg_row['SMP_FLEET_RATE']):
        agg_row['SMP_EXPECTED'] = agg_row['SAMPLE_SIZE'] * agg_row['SMP_FLEET_RATE']
    else:
        agg_row['SMP_EXPECTED'] = np.nan
    
    # 6. OBSERVED DEFECTS (already calculated as BEEP_DEFECTIVE_COUNT, SMP_DEFECTIVE_COUNT)
    agg_row['BEEP_OBSERVED'] = agg_row.get('BEEP_DEFECTIVE_COUNT', 0)
    agg_row['SMP_OBSERVED'] = agg_row.get('SMP_DEFECTIVE_COUNT', 0)
    
    # 7. EXCESS DEFECTS (observed - expected)
    if not pd.isna(agg_row['BEEP_EXPECTED']):
        agg_row['BEEP_EXCESS'] = agg_row['BEEP_OBSERVED'] - agg_row['BEEP_EXPECTED']
    else:
        agg_row['BEEP_EXCESS'] = np.nan
        
    if not pd.isna(agg_row['SMP_EXPECTED']):
        agg_row['SMP_EXCESS'] = agg_row['SMP_OBSERVED'] - agg_row['SMP_EXPECTED']
    else:
        agg_row['SMP_EXCESS'] = np.nan
    
    # ... rest of the function stays the same (boolean rates, numeric columns, count totals)
    
    return agg_row

def calculate_fleet_baselines(df, periods, n_days):
    """
    Calculate layer-specific fleet baselines for each period (including BSL baselines)
    """
    
    print("📊 Calculating fleet baselines (rates + BSL)...")
    
    fleet_baselines = {}
    
    for period_start, period_end in periods:
        # Get all data in this period
        period_data = df[
            (df['INSPECT_TIME'] >= period_start) & 
            (df['INSPECT_TIME'] < period_end)
        ]
        
        if len(period_data) == 0:
            continue
            
        # Calculate fleet rates and BSL by layer
        for layer in period_data['LAYER'].unique():
            layer_data = period_data[period_data['LAYER'] == layer]
            
            if len(layer_data) > 0:
                # Fleet defect rates = total defective wafers / total wafers
                beep_defective = (layer_data['ZERO_BEEP'] == False).sum()
                smp_defective = (layer_data['ZERO_SMP'] == False).sum()
                total_wafers = len(layer_data)
                
                # Fleet BSL averages (filtered by STATUS_* = 'BSL')
                beep_fleet_bsl = np.nan
                smp_fleet_bsl = np.nan
                fleet_bsl_wafers = 0
                
                if all(col in layer_data.columns for col in ['BEEP_NCDD', 'STATUS_BEEP']):
                    beep_bsl_data = layer_data[layer_data['STATUS_BEEP'] == 'BSL']['BEEP_NCDD']
                    if len(beep_bsl_data) > 0:
                        beep_fleet_bsl = beep_bsl_data.mean()
                
                if all(col in layer_data.columns for col in ['SMP_NCDD', 'STATUS_SMP']):
                    smp_bsl_data = layer_data[layer_data['STATUS_SMP'] == 'BSL']['SMP_NCDD']
                    if len(smp_bsl_data) > 0:
                        smp_fleet_bsl = smp_bsl_data.mean()
                
                # Count of BSL wafers (union of BEEP and SMP BSL wafers)
                bsl_mask = pd.Series(False, index=layer_data.index)
                if 'STATUS_BEEP' in layer_data.columns:
                    bsl_mask |= (layer_data['STATUS_BEEP'] == 'BSL')
                if 'STATUS_SMP' in layer_data.columns:
                    bsl_mask |= (layer_data['STATUS_SMP'] == 'BSL')
                fleet_bsl_wafers = bsl_mask.sum()
                
                fleet_baselines[(period_start, layer)] = {
                    'BEEP_FLEET_RATE': beep_defective / total_wafers,
                    'SMP_FLEET_RATE': smp_defective / total_wafers,
                    'BEEP_FLEET_BSL': beep_fleet_bsl,
                    'SMP_FLEET_BSL': smp_fleet_bsl,
                    'FLEET_WAFERS': total_wafers,
                    'FLEET_BSL_WAFERS': fleet_bsl_wafers
                }
    
    return fleet_baselines

def analyze_fleet_benchmarking_results(df, n_days):
    """
    Analyze the results with focus on fleet benchmarking (including BSL)
    """
    print(f"\n📊 {n_days}-DAY FLEET BENCHMARKING ANALYSIS (WITH BSL)")
    print("=" * 60)
    
    print(f"📈 Dataset Overview:")
    print(f"  Total periods: {len(df):,}")
    print(f"  Date range: {df['PERIOD_START'].min()} to {df['PERIOD_END'].max()}")
    
    print(f"\n🏷️  Grouping Summary:")
    devices = sorted(df['DEVICE'].unique())
    layers = sorted(df['LAYER'].unique())
    print(f"  Devices ({len(devices)}): {devices}")
    print(f"  Layers ({len(layers)}): {layers}")
    
    print(f"\n🎯 Fleet vs Device Performance:")
    
    for layer in layers:
        layer_data = df[df['LAYER'] == layer]
        if len(layer_data) == 0:
            continue
            
        print(f"\n  {layer} Layer:")
        
        # Fleet averages
        fleet_beep_rate = layer_data['BEEP_FLEET_RATE'].mean()
        fleet_smp_rate = layer_data['SMP_FLEET_RATE'].mean()
        fleet_beep_bsl = layer_data['BEEP_FLEET_BSL'].mean()
        fleet_smp_bsl = layer_data['SMP_FLEET_BSL'].mean()
        
        print(f"    Fleet BEEP rate: {fleet_beep_rate:.3f} ({fleet_beep_rate*100:.1f}%)")
        print(f"    Fleet SMP rate:  {fleet_smp_rate:.3f} ({fleet_smp_rate*100:.1f}%)")
        print(f"    Fleet BEEP BSL:  {fleet_beep_bsl:.2f}")
        print(f"    Fleet SMP BSL:   {fleet_smp_bsl:.2f}")
        
        # Device performance vs fleet
        print(f"    Device performance vs fleet:")
        for device in devices:
            device_data = layer_data[layer_data['DEVICE'] == device]
            if len(device_data) == 0:
                continue
                
            avg_beep_rate = device_data['BEEP_RATE'].mean()
            avg_smp_rate = device_data['SMP_RATE'].mean()
            avg_beep_bsl = device_data['BEEP_BSL'].mean()
            avg_smp_bsl = device_data['SMP_BSL'].mean()
            avg_beep_excess = device_data['BEEP_EXCESS'].mean()
            avg_smp_excess = device_data['SMP_EXCESS'].mean()
            
            print(f"      {device}:")
            print(f"        Rates - BEEP: {avg_beep_rate:.3f} (excess: {avg_beep_excess:+.1f}), SMP: {avg_smp_rate:.3f} (excess: {avg_smp_excess:+.1f})")
            print(f"        BSL   - BEEP: {avg_beep_bsl:.2f}, SMP: {avg_smp_bsl:.2f}")
    
    print(f"\n📊 BSL Data Coverage:")
    beep_bsl_coverage = (df['BEEP_BSL_COUNT'] > 0).mean() * 100
    smp_bsl_coverage = (df['SMP_BSL_COUNT'] > 0).mean() * 100
    print(f"  Periods with BEEP BSL data: {beep_bsl_coverage:.1f}%")
    print(f"  Periods with SMP BSL data: {smp_bsl_coverage:.1f}%")
    
    avg_beep_bsl_count = df['BEEP_BSL_COUNT'].mean()
    avg_smp_bsl_count = df['SMP_BSL_COUNT'].mean()
    print(f"  Average BEEP BSL wafers per period: {avg_beep_bsl_count:.1f}")
    print(f"  Average SMP BSL wafers per period: {avg_smp_bsl_count:.1f}")

def main():
    """
    Main execution function
    """
    
    # CONFIGURATION
    filepath = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_202603.csv"
    
    # CONFIGURABLE PARAMETERS
    N_DAYS_OPTIONS = [7]  # Start with 7 and 14-day periods
    MIN_SAMPLES = 10
    
    print("🚀 FLEET BENCHMARKING AGGREGATION PROCESSOR")
    print("=" * 60)
    
    # Load data
    print(f"📁 Loading data from file...")
    try:
        df = pd.read_csv(filepath)
        print(f"✅ Successfully loaded {len(df):,} rows × {len(df.columns)} columns")
        
        # Check if INSPECT_TIME exists
        if 'INSPECT_TIME' not in df.columns:
            print("❌ INSPECT_TIME column not found!")
            print(f"Available time columns: {[col for col in df.columns if 'TIME' in col.upper()]}")
            return
        
        # # FILTER OUT ROWS WHERE PILOT_STATUS = 'SRCIP'
        # if 'PILOT_STATUS' in df.columns:
        #     initial_count = len(df)
        #     srcip_count = (df['PILOT_STATUS'] == 'SRCIP').sum()
        #     df = df[df['PILOT_STATUS'] != 'SRCIP']
        #     final_count = len(df)
            
        #     print(f"🔍 PILOT_STATUS Filter Applied:")
        #     print(f"  Initial rows: {initial_count:,}")
        #     print(f"  SRCIP rows removed: {srcip_count:,}")
        #     print(f"  Final rows: {final_count:,}")
        #     print(f"  Retention rate: {(final_count/initial_count)*100:.1f}%")
        # else:
        #     print("⚠️  PILOT_STATUS column not found - no filtering applied")
            
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return
    
    # Process each time period size
    for n_days in N_DAYS_OPTIONS:
        print(f"\n" + "="*60)
        print(f"📅 PROCESSING {n_days}-DAY FIXED PERIODS WITH FLEET BENCHMARKING")
        print(f"="*60)
        
        # Create aggregation
        agg_df = create_fixed_period_aggregation(df, n_days=n_days, min_samples=MIN_SAMPLES)
        
        if len(agg_df) > 0:
            # Analyze results
            analyze_fleet_benchmarking_results(agg_df, n_days)
            
            # Save results
            output_path = filepath.replace('.csv', f'_FLEET_BENCHMARK_{n_days}DAY.csv')
            agg_df.to_csv(output_path, index=False)
            print(f"\n💾 Saved {n_days}-day fleet benchmark: {output_path}")
            
        else:
            print(f"⚠️  No data met minimum sample requirements for {n_days}-day periods")
    
    print(f"\n🎉 PROCESSING COMPLETE!")

if __name__ == "__main__":
    main()