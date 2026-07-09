import pandas as pd
import os
from datetime import datetime

def concatenate_elwc_files():
    """
    Concatenate two ELWC files and remove duplicates
    """
    
    # File paths
    file1 = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\2026-02-11 450 days ALL_CHAMBERS ELWC.csv"
    file2 = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\2026-01-12 420 days ALL_CHAMBERS ELWC.csv"
    
    # Output path (current folder)
    output_file = "COMBINED_ELWC_DEDUPLICATED.csv"
    
    print("🔄 ELWC FILE CONCATENATION & DEDUPLICATION")
    print("=" * 60)
    
    # Load first file
    print(f"📁 Loading file 1: 2026-02-11 (450 days)...")
    try:
        df1 = pd.read_csv(file1)
        print(f"✅ File 1 loaded: {len(df1):,} rows × {len(df1.columns)} columns")
        print(f"   Memory usage: {df1.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
    except Exception as e:
        print(f"❌ Error loading file 1: {e}")
        return
    
    # Load second file
    print(f"\n📁 Loading file 2: 2026-01-12 (420 days)...")
    try:
        df2 = pd.read_csv(file2)
        print(f"✅ File 2 loaded: {len(df2):,} rows × {len(df2.columns)} columns")
        print(f"   Memory usage: {df2.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
    except Exception as e:
        print(f"❌ Error loading file 2: {e}")
        return
    
    # Check column compatibility
    print(f"\n🔍 Checking column compatibility...")
    cols1 = set(df1.columns)
    cols2 = set(df2.columns)
    
    if cols1 == cols2:
        print(f"✅ Columns match perfectly ({len(cols1)} columns)")
    else:
        print(f"⚠️  Column differences found:")
        only_in_1 = cols1 - cols2
        only_in_2 = cols2 - cols1
        
        if only_in_1:
            print(f"   Only in file 1: {list(only_in_1)}")
        if only_in_2:
            print(f"   Only in file 2: {list(only_in_2)}")
        
        # Use intersection of columns
        common_cols = list(cols1 & cols2)
        print(f"   Using {len(common_cols)} common columns")
        df1 = df1[common_cols]
        df2 = df2[common_cols]
    
    # Concatenate
    print(f"\n🔗 Concatenating files...")
    combined_df = pd.concat([df1, df2], ignore_index=True)
    print(f"✅ Combined dataset: {len(combined_df):,} rows")
    print(f"   Memory usage: {combined_df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
    
    # Remove duplicates
    print(f"\n🧹 Removing duplicates...")
    initial_count = len(combined_df)
    
    # Remove exact duplicates across all columns
    combined_df = combined_df.drop_duplicates()
    
    final_count = len(combined_df)
    duplicates_removed = initial_count - final_count
    
    print(f"✅ Deduplication complete:")
    print(f"   Initial rows: {initial_count:,}")
    print(f"   Final rows: {final_count:,}")
    print(f"   Duplicates removed: {duplicates_removed:,}")
    print(f"   Duplicate rate: {duplicates_removed/initial_count*100:.2f}%")
    
    # Show date range if we can find a time column
    print(f"\n📅 Checking date range...")
    time_cols = [col for col in combined_df.columns if any(word in col.upper() 
                for word in ['TIME', 'DATE', 'START', 'END', 'PROCESS'])]
    
    if time_cols:
        time_col = time_cols[0]  # Use first time column found
        try:
            combined_df[time_col] = pd.to_datetime(combined_df[time_col])
            date_min = combined_df[time_col].min()
            date_max = combined_df[time_col].max()
            date_range_days = (date_max - date_min).days
            
            print(f"   Time column: {time_col}")
            print(f"   Date range: {date_min.date()} to {date_max.date()}")
            print(f"   Total days: {date_range_days}")
            print(f"   Avg records/day: {final_count/max(1, date_range_days):,.0f}")
        except:
            print(f"   Could not parse time column: {time_col}")
    else:
        print(f"   No time columns detected")
    
    # Save combined file
    print(f"\n💾 Saving combined file...")
    try:
        combined_df.to_csv(output_file, index=False)
        
        # Check file size
        file_size_mb = os.path.getsize(output_file) / 1024**2
        
        print(f"✅ File saved successfully:")
        print(f"   Path: {os.path.abspath(output_file)}")
        print(f"   Size: {file_size_mb:.1f} MB")
        print(f"   Rows: {len(combined_df):,}")
        print(f"   Columns: {len(combined_df.columns)}")
        
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return
    
    # Show column summary
    print(f"\n📋 Final dataset columns:")
    for i, col in enumerate(combined_df.columns, 1):
        print(f"   {i:2d}. {col}")
    
    print(f"\n🎉 CONCATENATION COMPLETE!")
    print(f"📁 Output file: {output_file}")
    
    return output_file

if __name__ == "__main__":
    concatenate_elwc_files()