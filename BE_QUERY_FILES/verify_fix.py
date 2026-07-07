import pandas as pd

df = pd.read_csv(r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED.csv', low_memory=False)

print(f'Production CSV: {len(df)} rows\n')

unknown_count = (df['CLASS_BEEP'] == 'UNKNOWN').sum()
print(f'CLASS_BEEP=UNKNOWN: {unknown_count} / {len(df)}')

if unknown_count == 0:
    print('✓ SUCCESS - No CLASS_BEEP=UNKNOWN rows!\n')
else:
    print(f'⚠ Still have {unknown_count} UNKNOWN rows\n')

print('CLASS_BEEP distribution:')
print(df['CLASS_BEEP'].value_counts())

print(f'\nBEEP_NCDD nulls: {df["BEEP_NCDD"].isna().sum()}')
print(f'BEEP_EDI nulls: {df["BEEP_EDI"].isna().sum()}')
