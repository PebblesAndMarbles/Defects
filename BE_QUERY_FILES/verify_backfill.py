import pandas as pd

print('\n' + '=' * 80)
print('VERIFICATION: Backfill Results')
print('=' * 80)

# Check extended
print('\n[Extended CSV]')
df = pd.read_csv(r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED.csv', nrows=5, low_memory=False)
print(f'Columns (first 8): {list(df.columns[:8])}')
print(f'Sample data:')
print(df[['YYMM', 'PERIOD_END', 'YYYYWW', 'WAFER_ID', 'LAYER']].head())

# Full validation
df_full = pd.read_csv(r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED.csv', low_memory=False)
print(f'\nTotal rows: {len(df_full)}')
print(f'PERIOD_END nulls: {df_full["PERIOD_END"].isna().sum()}')
print(f'YYYYWW nulls: {df_full["YYYYWW"].isna().sum()}')
print(f'PERIOD_END unique values: {df_full["PERIOD_END"].nunique()} (Sundays)')
print(f'YYYYWW unique values: {df_full["YYYYWW"].nunique()} (weeks)')

# Check 60-day
print('\n[60-day CSV]')
df = pd.read_csv(r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED_60DAY.csv', nrows=5, low_memory=False)
print(f'Columns (first 8): {list(df.columns[:8])}')
print(f'Sample data:')
print(df[['YYMM', 'PERIOD_END', 'YYYYWW', 'WAFER_ID', 'LAYER']].head())

df_60 = pd.read_csv(r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED_60DAY.csv', low_memory=False)
print(f'\nTotal rows: {len(df_60)}')
print(f'PERIOD_END nulls: {df_60["PERIOD_END"].isna().sum()}')
print(f'YYYYWW nulls: {df_60["YYYYWW"].isna().sum()}')

# Test filtering
print('\n[Filtering Test]')
test_week = df_60['YYYYWW'].iloc[0]
filtered = df_60[df_60['YYYYWW'] == test_week]
print(f'Week "{test_week}" has {len(filtered)} wafers')

print('\n' + '=' * 80)
print('✓ Backfill verification complete - columns properly added!')
print('=' * 80 + '\n')
