#!/usr/bin/env python3
"""Phase 0 Debug: Inspect actual data values for join keys"""

import pandas as pd

print('=' * 80)
print('PHASE 0 DEBUG: INVESTIGATING JOIN KEY MISMATCH')
print('=' * 80)

# Load data
edi_5 = pd.read_csv('BE_QUERY_FILES/8M5CL_EDI.csv', low_memory=False)
edi_6 = pd.read_csv('BE_QUERY_FILES/8M6CL_EDI.csv', low_memory=False)
prod = pd.read_csv('outputs/wafer/8M5CL_8M6CL_EXTENDED.csv', low_memory=False)

# Sample data inspection
print('\n[8M5CL_EDI] Sample rows (first 3):')
print(edi_5[['LOT', 'WAFER', 'WAFER_ID', 'LAYER', 'INSPECTION_TIME@DEFECT']].head(3))

print('\n[8M6CL_EDI] Sample rows (first 3):')
print(edi_6[['LOT', 'WAFER', 'WAFER_ID', 'LAYER', 'INSPECTION_TIME@DEFECT']].head(3))

print('\n[Production] Sample rows (first 3):')
prod_cols = [c for c in ['LOT', 'WAFER_ID', 'LAYER', 'INSPECT_TIME'] if c in prod.columns]
print(prod[prod_cols].head(3))

# Check data types
print('\n' + '=' * 80)
print('DATA TYPES')
print('=' * 80)

print('\n[8M5CL_EDI]')
print(f'  WAFER_ID: {edi_5["WAFER_ID"].dtype} | Sample: {edi_5["WAFER_ID"].iloc[0]}')
print(f'  LAYER: {edi_5["LAYER"].dtype} | Sample: {edi_5["LAYER"].iloc[0]}')
print(f'  INSPECTION_TIME@DEFECT: {edi_5["INSPECTION_TIME@DEFECT"].dtype} | Sample: {edi_5["INSPECTION_TIME@DEFECT"].iloc[0]}')

print('\n[Production]')
print(f'  WAFER_ID: {prod["WAFER_ID"].dtype} | Sample: {prod["WAFER_ID"].iloc[0]}')
print(f'  LAYER: {prod["LAYER"].dtype} | Sample: {prod["LAYER"].iloc[0]}')
print(f'  INSPECT_TIME: {prod["INSPECT_TIME"].dtype} | Sample: {prod["INSPECT_TIME"].iloc[0]}')

# Check unique values (sample)
print('\n' + '=' * 80)
print('UNIQUE VALUE SAMPLES (first 5)')
print('=' * 80)

print('\n[8M5CL_EDI LAYER values]')
print(edi_5['LAYER'].unique()[:5])

print('\n[Production LAYER values]')
print(prod['LAYER'].unique()[:5])

print('\n[8M5CL_EDI WAFER_ID values]')
print(edi_5['WAFER_ID'].unique()[:5])

print('\n[Production WAFER_ID values]')
print(prod['WAFER_ID'].unique()[:5])

# Check for overlap on simpler keys first
print('\n' + '=' * 80)
print('SIMPLE KEY OVERLAP TESTS')
print('=' * 80)

wafer_overlap = set(edi_5['WAFER_ID']) & set(prod['WAFER_ID'])
layer_overlap = set(edi_5['LAYER']) & set(prod['LAYER'])
time_overlap = set(edi_5['INSPECTION_TIME@DEFECT']) & set(prod['INSPECT_TIME'])

print(f'\nWAFER_ID overlap: {len(wafer_overlap)} / {len(set(edi_5["WAFER_ID"]))} ({len(wafer_overlap)/len(set(edi_5["WAFER_ID"]))*100:.1f}%)')
print(f'LAYER overlap: {len(layer_overlap)} / {len(set(edi_5["LAYER"]))} ({len(layer_overlap)/len(set(edi_5["LAYER"]))*100:.1f}%)')
print(f'INSPECT_TIME overlap: {len(time_overlap)} / {len(set(edi_5["INSPECTION_TIME@DEFECT"]))} ({len(time_overlap)/len(set(edi_5["INSPECTION_TIME@DEFECT"]))*100:.1f}%)')

if len(wafer_overlap) > 0:
    print(f'\n✓ Sample shared WAFER_ID: {list(wafer_overlap)[:3]}')
if len(layer_overlap) > 0:
    print(f'✓ Sample shared LAYER: {list(layer_overlap)[:3]}')
if len(time_overlap) > 0:
    print(f'✓ Sample shared INSPECT_TIME: {list(time_overlap)[:3]}')

# Check for NaN/NULL issues
print('\n' + '=' * 80)
print('NULL/NaN CHECK')
print('=' * 80)

print(f'\n[8M5CL_EDI]')
print(f'  WAFER_ID NaN: {edi_5["WAFER_ID"].isna().sum()}')
print(f'  LAYER NaN: {edi_5["LAYER"].isna().sum()}')
print(f'  INSPECTION_TIME@DEFECT NaN: {edi_5["INSPECTION_TIME@DEFECT"].isna().sum()}')

print(f'\n[Production]')
print(f'  WAFER_ID NaN: {prod["WAFER_ID"].isna().sum()}')
print(f'  LAYER NaN: {prod["LAYER"].isna().sum()}')
print(f'  INSPECT_TIME NaN: {prod["INSPECT_TIME"].isna().sum()}')

print('\n' + '=' * 80)
