import pandas as pd

print('=' * 80)
print('NCDD COVERAGE CHECK - Raw Source Files (No Merge)')
print('=' * 80)

# Load NCDD only files
m5_ncdd = pd.read_csv(r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M5CL_NCDD.csv', low_memory=False)
m6_ncdd = pd.read_csv(r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M6CL_NCDD.csv', low_memory=False)

print(f'\n[8M5CL_NCDD.csv] (Raw file from today)')
print(f'  Rows: {len(m5_ncdd)}')
print(f'  Columns: {list(m5_ncdd.columns)}')

# Check if JMP format columns exist
if 'DEFECT@WAFER@CLASS_NCDD@BEEP' in m5_ncdd.columns:
    m5_ncdd_col = 'DEFECT@WAFER@CLASS_NCDD@BEEP'
    m5_coverage = (1 - m5_ncdd[m5_ncdd_col].isna().sum() / len(m5_ncdd)) * 100
    print(f'  NCDD BEEP non-null: {m5_ncdd[m5_ncdd_col].notna().sum()} / {len(m5_ncdd)} ({m5_coverage:.1f}%)')
elif 'BEEP_NCDD' in m5_ncdd.columns:
    m5_coverage = (1 - m5_ncdd['BEEP_NCDD'].isna().sum() / len(m5_ncdd)) * 100
    print(f'  NCDD BEEP non-null: {m5_ncdd["BEEP_NCDD"].notna().sum()} / {len(m5_ncdd)} ({m5_coverage:.1f}%)')
else:
    print(f'  WARNING: NCDD BEEP column not found')
    m5_coverage = 0

print(f'\n[8M6CL_NCDD.csv] (Raw file from today)')
print(f'  Rows: {len(m6_ncdd)}')
print(f'  Columns: {list(m6_ncdd.columns)}')

# Check if JMP format columns exist
if 'DEFECT@WAFER@CLASS_NCDD@BEEP' in m6_ncdd.columns:
    m6_ncdd_col = 'DEFECT@WAFER@CLASS_NCDD@BEEP'
    m6_coverage = (1 - m6_ncdd[m6_ncdd_col].isna().sum() / len(m6_ncdd)) * 100
    print(f'  NCDD BEEP non-null: {m6_ncdd[m6_ncdd_col].notna().sum()} / {len(m6_ncdd)} ({m6_coverage:.1f}%)')
elif 'BEEP_NCDD' in m6_ncdd.columns:
    m6_coverage = (1 - m6_ncdd['BEEP_NCDD'].isna().sum() / len(m6_ncdd)) * 100
    print(f'  NCDD BEEP non-null: {m6_ncdd["BEEP_NCDD"].notna().sum()} / {len(m6_ncdd)} ({m6_coverage:.1f}%)')
else:
    print(f'  WARNING: NCDD BEEP column not found')
    m6_coverage = 0

# Combined
print(f'\n[COMBINED NCDD COVERAGE]')
total_rows = len(m5_ncdd) + len(m6_ncdd)
print(f'  Total rows if combined: {total_rows}')

# Load extended for comparison
prod_full = pd.read_csv(r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED.csv', low_memory=False)
print(f'\n[8M5CL_8M6CL_EXTENDED.csv] (Current production)')
print(f'  Total rows: {len(prod_full)}')
ncdd_ext_coverage = (1 - prod_full['BEEP_NCDD'].isna().sum() / len(prod_full)) * 100
print(f'  NCDD BEEP coverage: {ncdd_ext_coverage:.1f}%')
print(f'  NCDD BEEP non-null: {prod_full["BEEP_NCDD"].notna().sum()} / {len(prod_full)}')

print(f'\n' + '=' * 80)
print(f'COVERAGE ANALYSIS')
print(f'=' * 80)
print(f'Raw NCDD files combined: {total_rows} rows')
print(f'Production EXTENDED: {len(prod_full)} rows')
print(f'Missing rows in raw NCDD: {len(prod_full) - total_rows} ({100*(len(prod_full) - total_rows)/len(prod_full):.1f}%)')
print(f'\nIf NCDD had full coverage from raw sources:')
print(f'  Potential NCDD coverage: ~{(total_rows/len(prod_full)*100):.1f}%')
print(f'  vs Current: {ncdd_ext_coverage:.1f}%')
print(f'\nComparison to EDI:')
print(f'  EDI current coverage: 90.8%')
print(f'  NCDD potential (raw): {(total_rows/len(prod_full)*100):.1f}%')
