import pandas as pd

# Generate 60-day export
prod_csv = r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED.csv'
export_60d_csv = r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED_60DAY.csv'

df = pd.read_csv(prod_csv, low_memory=False)

# Parse inspect time and filter to 60 days
df['INSPECT_TIME'] = pd.to_datetime(df['INSPECT_TIME'], errors='coerce')
newest = df['INSPECT_TIME'].max()
cutoff = newest - pd.Timedelta(days=60)

df_60d = df[df['INSPECT_TIME'] >= cutoff].copy()

df_60d.to_csv(export_60d_csv, index=False)

print(f'60-Day Export Generated:')
print(f'  Total rows: {len(df_60d)} (from {len(df)})')
print(f'  Date range: {df_60d["INSPECT_TIME"].min()} to {df_60d["INSPECT_TIME"].max()}')
print(f'  Saved to: {export_60d_csv}')

edi_coverage = (1 - df_60d['BEEP_EDI'].isna().sum()/len(df_60d))*100
ncdd_coverage = (1 - df_60d['BEEP_NCDD'].isna().sum()/len(df_60d))*100

print(f'\n  EDI Coverage: {edi_coverage:.1f}%')
print(f'  NCDD Coverage: {ncdd_coverage:.1f}%')
