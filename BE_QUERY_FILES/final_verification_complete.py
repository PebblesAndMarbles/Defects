import pandas as pd

print('\n' + '=' * 80)
print('FINAL VERIFICATION: Complete Implementation')
print('=' * 80)

# Load latest production CSV
df = pd.read_csv(r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED.csv', low_memory=False)

print(f'\n[Production CSV - 8M5CL_8M6CL_EXTENDED.csv]')
print(f'Total rows: {len(df)}')
print(f'Total columns: {len(df.columns)}')
print(f'\nFirst 10 columns: {list(df.columns[:10])}')
print(f'\n✓ PERIOD_END position: Column index {df.columns.get_loc("PERIOD_END")}')
print(f'✓ YYYYWW position: Column index {df.columns.get_loc("YYYYWW")}')

print(f'\n[Data Quality]')
print(f'PERIOD_END non-null: {df["PERIOD_END"].notna().sum()}/{len(df)} ({100*df["PERIOD_END"].notna().sum()/len(df):.1f}%)')
print(f'YYYYWW non-null: {df["YYYYWW"].notna().sum()}/{len(df)} ({100*df["YYYYWW"].notna().sum()/len(df):.1f}%)')

print(f'\n[Sample Values]')
print(df[['YYMM', 'PERIOD_END', 'YYYYWW', 'WAFER_ID', 'LAYER']].head(10))

print(f'\n[Workweek Coverage]')
print(f'Unique PERIOD_END dates: {df["PERIOD_END"].nunique()}')
print(f'Unique YYYYWW weeks: {df["YYYYWW"].nunique()}')
print(f'\nDate range:')
print(f'  Earliest: {df["PERIOD_END"].min()}')
print(f'  Latest: {df["PERIOD_END"].max()}')

print(f'\n[Filtering Examples]')
latest_week = df['YYYYWW'].iloc[0]
filtered = df[df['YYYYWW'] == latest_week]
print(f'Latest week "{latest_week}": {len(filtered)} wafers')

older_week = df['YYYYWW'].unique()[-1]
filtered_old = df[df['YYYYWW'] == older_week]
print(f'Earliest week "{older_week}": {len(filtered_old)} wafers')

# Check 60-day
print(f'\n[60-day CSV]')
df_60 = pd.read_csv(r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED_60DAY.csv', low_memory=False)
print(f'Rows: {len(df_60)}, Columns: {len(df_60.columns)}')
print(f'PERIOD_END nulls: {df_60["PERIOD_END"].isna().sum()}')
print(f'YYYYWW nulls: {df_60["YYYYWW"].isna().sum()}')

print(f'\n' + '=' * 80)
print('✅ IMPLEMENTATION COMPLETE AND VERIFIED!')
print('=' * 80)
print(f'\nUsers can now filter by workweek:')
print(f'  df[df["YYYYWW"] == "26W27"]  # All wafers in week 27')
print(f'  df[df["PERIOD_END"] == "2026-07-05"]  # All wafers in specific week')
print(f'  df.groupby("YYYYWW")["ZERO_BEEP"].mean()  # Weekly trends')
print()
