import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import combinations
import warnings
warnings.filterwarnings('ignore')

# Load the data
file_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_2025_DEVICE_FLEET_BENCHMARK_7DAY.csv"

try:
    df = pd.read_csv(file_path)
    print("Data loaded successfully!")
    print(f"Dataset shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
except Exception as e:
    print(f"Error loading data: {e}")
    print("Please check the file path and ensure you have access to the network location.")
    exit()

# Initial data screening
print("\n" + "="*60)
print("INITIAL DATA SCREENING")
print("="*60)

# Check for required columns
required_cols = ['LAYER', 'DEVICE', 'BEEP_WEIGHTED_RATE', 'SMP_WEIGHTED_RATE']
missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
    print(f"Warning: Missing columns: {missing_cols}")
    print("Available columns:", list(df.columns))

# Filter for 8M5CL and 8M6CL layers
df_filtered = df[df['LAYER'].isin(['8M5CL', '8M6CL'])].copy()
print(f"\nFiltered dataset shape (8M5CL & 8M6CL only): {df_filtered.shape}")

# Basic info about the filtered dataset
print(f"\nLayers in dataset: {df_filtered['LAYER'].value_counts().to_dict()}")
print(f"Devices in dataset: {df_filtered['DEVICE'].value_counts().to_dict()}")

# Check for missing values
print(f"\nMissing values:")
print(f"BEEP_WEIGHTED_RATE: {df_filtered['BEEP_WEIGHTED_RATE'].isna().sum()}")
print(f"SMP_WEIGHTED_RATE: {df_filtered['SMP_WEIGHTED_RATE'].isna().sum()}")

# Remove rows with missing values in key columns
df_clean = df_filtered.dropna(subset=['BEEP_WEIGHTED_RATE', 'SMP_WEIGHTED_RATE'])
print(f"Clean dataset shape: {df_clean.shape}")

def perform_outlier_analysis(df, metric_col, layer, device_col='DEVICE'):
    """Perform outlier analysis for a given metric and layer"""
    
    layer_data = df[df['LAYER'] == layer].copy()
    
    print(f"\n{'='*50}")
    print(f"OUTLIER ANALYSIS: {metric_col} - {layer}")
    print(f"{'='*50}")
    
    # Overall statistics
    overall_stats = layer_data[metric_col].describe()
    print(f"\nOverall {metric_col} statistics for {layer}:")
    print(overall_stats)
    
    # Device-level statistics
    device_stats = layer_data.groupby(device_col)[metric_col].agg([
        'count', 'mean', 'std', 'median', 'min', 'max'
    ]).round(6)
    
    print(f"\nDevice-level statistics:")
    print(device_stats)
    
    # Identify potential outlier devices using IQR method
    Q1 = device_stats['mean'].quantile(0.25)
    Q3 = device_stats['mean'].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    outlier_devices = device_stats[
        (device_stats['mean'] < lower_bound) | 
        (device_stats['mean'] > upper_bound)
    ]
    
    print(f"\nPotential outlier devices (based on mean {metric_col}):")
    if len(outlier_devices) > 0:
        print(outlier_devices)
    else:
        print("No outlier devices detected using IQR method.")
    
    return layer_data, device_stats, outlier_devices

def mann_whitney_analysis(df, metric_col, layer, device_col='DEVICE', alpha=0.05):
    """Perform Mann-Whitney U tests comparing each device to the rest"""
    
    layer_data = df[df['LAYER'] == layer].copy()
    devices = layer_data[device_col].unique()
    
    print(f"\n{'='*50}")
    print(f"MANN-WHITNEY U TESTS: {metric_col} - {layer}")
    print(f"{'='*50}")
    
    results = []
    
    for device in devices:
        # Get data for current device
        device_data = layer_data[layer_data[device_col] == device][metric_col].values
        
        # Get data for all other devices
        other_data = layer_data[layer_data[device_col] != device][metric_col].values
        
        if len(device_data) < 3 or len(other_data) < 3:
            print(f"\nSkipping {device}: insufficient data (n_device={len(device_data)}, n_others={len(other_data)})")
            continue
        
        # Perform Mann-Whitney U test
        try:
            statistic, p_value = stats.mannwhitneyu(
                device_data, other_data, 
                alternative='two-sided'
            )
            
            # Calculate effect size (rank-biserial correlation)
            n1, n2 = len(device_data), len(other_data)
            effect_size = 1 - (2 * statistic) / (n1 * n2)
            
            # Determine significance
            significant = p_value < alpha
            
            results.append({
                'Device': device,
                'n_device': n1,
                'n_others': n2,
                'device_median': np.median(device_data),
                'others_median': np.median(other_data),
                'U_statistic': statistic,
                'p_value': p_value,
                'effect_size': effect_size,
                'significant': significant
            })
            
        except Exception as e:
            print(f"Error testing {device}: {e}")
    
    # Convert to DataFrame and sort by p-value
    results_df = pd.DataFrame(results)
    if len(results_df) > 0:
        results_df = results_df.sort_values('p_value')
        
        print(f"\nMann-Whitney U Test Results (α = {alpha}):")
        print("="*80)
        
        for _, row in results_df.iterrows():
            significance = "***" if row['significant'] else ""
            print(f"Device: {row['Device']:<8} | "
                  f"n={row['n_device']:<3} | "
                  f"Device_median={row['device_median']:.6f} | "
                  f"Others_median={row['others_median']:.6f} | "
                  f"p={row['p_value']:.6f} {significance}")
        
        # Summary of significant results
        significant_devices = results_df[results_df['significant']]
        if len(significant_devices) > 0:
            print(f"\n*** SIGNIFICANT DEVICES (p < {alpha}) ***")
            for _, row in significant_devices.iterrows():
                direction = "HIGHER" if row['device_median'] > row['others_median'] else "LOWER"
                print(f"{row['Device']}: {direction} than others (p={row['p_value']:.6f})")
        else:
            print(f"\nNo devices significantly different from others at α = {alpha}")
    
    return results_df

def create_visualizations(df, metric_col, layer, device_col='DEVICE'):
    """Create visualizations for the analysis"""
    
    layer_data = df[df['LAYER'] == layer].copy()
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle(f'{metric_col} Analysis - {layer}', fontsize=16)
    
    # Box plot by device
    sns.boxplot(data=layer_data, x=device_col, y=metric_col, ax=axes[0,0])
    axes[0,0].set_title('Distribution by Device')
    axes[0,0].tick_params(axis='x', rotation=45)
    
    # Histogram of overall distribution
    axes[0,1].hist(layer_data[metric_col], bins=30, alpha=0.7, edgecolor='black')
    axes[0,1].set_title('Overall Distribution')
    axes[0,1].set_xlabel(metric_col)
    
    # Device means comparison
    device_means = layer_data.groupby(device_col)[metric_col].mean().sort_values()
    device_means.plot(kind='bar', ax=axes[1,0])
    axes[1,0].set_title('Mean by Device')
    axes[1,0].tick_params(axis='x', rotation=45)
    
    # Q-Q plot for normality check
    stats.probplot(layer_data[metric_col], dist="norm", plot=axes[1,1])
    axes[1,1].set_title('Q-Q Plot (Normality Check)')
    
    plt.tight_layout()
    plt.show()

# Main analysis
if 'df_clean' in locals():
    metrics = ['BEEP_WEIGHTED_RATE', 'SMP_WEIGHTED_RATE']
    layers = ['8M5CL', '8M6CL']
    
    all_results = {}
    
    for layer in layers:
        for metric in metrics:
            print(f"\n{'#'*80}")
            print(f"ANALYZING: {metric} for {layer}")
            print(f"{'#'*80}")
            
            # Outlier analysis
            layer_data, device_stats, outliers = perform_outlier_analysis(
                df_clean, metric, layer
            )
            
            # Mann-Whitney tests
            mw_results = mann_whitney_analysis(
                df_clean, metric, layer
            )
            
            # Store results
            all_results[f"{layer}_{metric}"] = {
                'device_stats': device_stats,
                'outliers': outliers,
                'mann_whitney': mw_results
            }
            
            # Create visualizations
            create_visualizations(df_clean, metric, layer)
    
    # Summary across all analyses
    print(f"\n{'#'*80}")
    print("SUMMARY OF ALL ANALYSES")
    print(f"{'#'*80}")
    
    for analysis_key, results in all_results.items():
        layer, metric = analysis_key.split('_', 1)
        mw_results = results['mann_whitney']
        
        if len(mw_results) > 0:
            significant_count = mw_results['significant'].sum()
            print(f"\n{layer} - {metric}:")
            print(f"  Devices tested: {len(mw_results)}")
            print(f"  Significantly different: {significant_count}")
            
            if significant_count > 0:
                sig_devices = mw_results[mw_results['significant']]['Device'].tolist()
                print(f"  Significant devices: {sig_devices}")

else:
    print("Data not loaded successfully. Please check the file path and try again.")