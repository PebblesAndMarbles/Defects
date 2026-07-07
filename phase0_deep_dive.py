#!/usr/bin/env python3
"""Phase 0 Deep Dive: Investigate timestamp mismatch"""

import pandas as pd

print('=' * 80)
print('PHASE 0 DEEP DIVE: TIMESTAMP MISMATCH INVESTIGATION')
print('=' * 80)

# Load data
edi_5 = pd.read_csv('BE_QUERY_FILES/8M5CL_EDI.csv', low_memory=False)
prod = pd.read_csv('outputs/wafer/8M5CL_8M6CL_EXTENDED.csv', low_memory=False)

# Check all columns in production that might be time-related
print('\n[Production] All columns:')
for i, col in enumerate(prod.columns):
    print(f'  {i:2d}. {col}')

print('\n[8M5CL_EDI] All columns:')
for i, col in enumerate(edi_5.columns):
    print(f'  {i:2d}. {col}')

# Look for time columns
print('\n' + '=' * 80)
print('TIME-RELATED COLUMNS')
print('=' * 80)

prod_time_cols = [c for c in prod.columns if 'time' in c.lower() or 'date' in c.lower() or 'timestamp' in c.lower()]
edi_time_cols = [c for c in edi_5.columns if 'time' in c.lower() or 'date' in c.lower() or 'timestamp' in c.lower()]

print(f'\n[Production] Time columns: {prod_time_cols}')
print(f'[8M5CL_EDI] Time columns: {edi_time_cols}')

# Sample time columns in production
if prod_time_cols:
    print('\n[Production] Sample values:')
    for col in prod_time_cols:
        print(f'  {col}:')
        print(f'    {prod[col].iloc[0]}')
        print(f'    {prod[col].iloc[1]}')

# Check if WAFER_ID alone can be used for join
print('\n' + '=' * 80)
print('WAFER_ID ONLY JOIN TEST')
print('=' * 80)

# Get unique WAFER_ID from each source
edi_wafers = set(edi_5['WAFER_ID'].unique())
prod_wafers = set(prod['WAFER_ID'].unique())

overlap_wafers = edi_wafers & prod_wafers

print(f'\n8M5CL_EDI unique WAFER_IDs: {len(edi_wafers)}')
print(f'Production unique WAFER_IDs: {len(prod_wafers)}')
print(f'Overlap: {len(overlap_wafers)} ({len(overlap_wafers)/len(edi_wafers)*100:.1f}%)')

# For a shared WAFER_ID, how many production rows exist?
if len(overlap_wafers) > 0:
    test_wafer = list(overlap_wafers)[0]
    edi_rows = edi_5[edi_5['WAFER_ID'] == test_wafer]
    prod_rows = prod[prod['WAFER_ID'] == test_wafer]
    
    print(f'\nExample: WAFER_ID {test_wafer}')
    print(f'  EDI rows: {len(edi_rows)}')
    print(f'  Production rows: {len(prod_rows)}')
    
    if len(edi_rows) > 0:
        print(f'  EDI INSPECTION_TIME@DEFECT: {edi_rows["INSPECTION_TIME@DEFECT"].iloc[0]}')
    if len(prod_rows) > 0:
        if 'INSPECT_TIME' in prod_rows.columns:
            print(f'  Prod INSPECT_TIME: {prod_rows["INSPECT_TIME"].iloc[0]}')
        if 'SUBENTITY_END_TIME' in prod_rows.columns:
            print(f'  Prod SUBENTITY_END_TIME: {prod_rows["SUBENTITY_END_TIME"].iloc[0]}')

# Check date ranges
print('\n' + '=' * 80)
print('DATE RANGE ANALYSIS')
print('=' * 80)

print(f'\n[8M5CL_EDI] INSPECTION_TIME@DEFECT range:')
print(f'  First: {edi_5["INSPECTION_TIME@DEFECT"].min()}')
print(f'  Last: {edi_5["INSPECTION_TIME@DEFECT"].max()}')

print(f'\n[Production] INSPECT_TIME range:')
print(f'  First: {prod["INSPECT_TIME"].min()}')
print(f'  Last: {prod["INSPECT_TIME"].max()}')

print('\n' + '=' * 80)
print('CONCLUSION')
print('=' * 80)
print('\nThe EDI data appears to be from April 2025, while production is from April 2026.')
print('This suggests EDI may be historical/test data not yet integrated.')
print('\nRecommendation: Verify with user whether:')
print('  1. EDI data should be joined on WAFER_ID + LAYER only (ignoring timestamps)?')
print('  2. Or if there\'s a different join strategy?')
print('  3. Or if EDI data is indeed separate/new with its own timeline?')
print('\n' + '=' * 80)
