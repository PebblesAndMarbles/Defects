#!/usr/bin/env python3
"""Phase 0 Audit (Corrected): Proper timestamp parsing"""

import pandas as pd
from datetime import datetime

print('=' * 80)
print('PHASE 0: CORRECTED AUDIT - PROPER TIMESTAMP PARSING')
print('=' * 80)

# Load data
print('\nLoading files...')
edi_5 = pd.read_csv('BE_QUERY_FILES/8M5CL_EDI.csv', low_memory=False)
edi_6 = pd.read_csv('BE_QUERY_FILES/8M6CL_EDI.csv', low_memory=False)
prod = pd.read_csv('outputs/wafer/8M5CL_8M6CL_EXTENDED.csv', low_memory=False)

# Parse timestamps - EDI format: "MM/DD/YYYY HH:MM:SS AM/PM"
print('Parsing EDI timestamps...')
edi_5['_inspect_dt'] = pd.to_datetime(edi_5['INSPECTION_TIME@DEFECT'], format='%m/%d/%Y %I:%M:%S %p')
edi_6['_inspect_dt'] = pd.to_datetime(edi_6['INSPECTION_TIME@DEFECT'], format='%m/%d/%Y %I:%M:%S %p')

# Parse prod timestamps - format: "YYYY-MM-DD HH:MM:SS"
print('Parsing production timestamps...')
prod['_inspect_dt'] = pd.to_datetime(prod['INSPECT_TIME'], format='%Y-%m-%d %H:%M:%S')

# Create join keys using normalized timestamps
print('Creating join keys...')
edi_5['_join_key'] = list(zip(edi_5['WAFER_ID'], edi_5['_inspect_dt'], edi_5['LAYER']))
edi_6['_join_key'] = list(zip(edi_6['WAFER_ID'], edi_6['_inspect_dt'], edi_6['LAYER']))
prod['_join_key'] = list(zip(prod['WAFER_ID'], prod['_inspect_dt'], prod['LAYER']))

edi_5_keys = set(edi_5['_join_key'])
edi_6_keys = set(edi_6['_join_key'])
prod_keys = set(prod['_join_key'])

# Compute overlap
overlap_5 = edi_5_keys & prod_keys
overlap_6 = edi_6_keys & prod_keys

pct_5 = (len(overlap_5) / len(edi_5_keys) * 100) if len(edi_5_keys) > 0 else 0
pct_6 = (len(overlap_6) / len(edi_6_keys) * 100) if len(edi_6_keys) > 0 else 0

# Results
print('\n' + '=' * 80)
print('CORRECTED OVERLAP RESULTS (With Proper Timestamp Parsing)')
print('=' * 80)

print(f'\n8M5CL_EDI:')
print(f'  Total rows: {len(edi_5):,}')
print(f'  Unique keys: {len(edi_5_keys):,}')
print(f'  Matched with production: {len(overlap_5):,} ({pct_5:.1f}%)')
print(f'  → {len(edi_5_keys) - len(overlap_5):,} rows not in production')

print(f'\n8M6CL_EDI:')
print(f'  Total rows: {len(edi_6):,}')
print(f'  Unique keys: {len(edi_6_keys):,}')
print(f'  Matched with production: {len(overlap_6):,} ({pct_6:.1f}%)')
print(f'  → {len(edi_6_keys) - len(overlap_6):,} rows not in production')

# Verify target columns present
print('\n' + '=' * 80)
print('TARGET EDI COLUMNS')
print('=' * 80)

target_cols = {
    'DEFECT@WAFER@CLASS_EDI@BEEP': 'BEEP_EDI',
    'DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE': 'SMP_EDI'
}

print('\nColumns to extract and rename:')
all_cols_present = True
for src, tgt in target_cols.items():
    if src in edi_5.columns:
        print(f'  ✓ {src:50} → {tgt}')
    else:
        print(f'  ✗ {src:50} MISSING!')
        all_cols_present = False

# Final recommendation
print('\n' + '=' * 80)
print('AUDIT CONCLUSION')
print('=' * 80)

if pct_5 > 50 and pct_6 > 50 and all_cols_present:
    print(f'\n✓ PROCEED TO BACKFILL')
    print(f'  - Join key (WAFER_ID + INSPECT_TIME + LAYER) is valid')
    print(f'  - Strong data overlap: 8M5CL ({pct_5:.1f}%), 8M6CL ({pct_6:.1f}%)')
    print(f'  - Target columns present and ready for extraction')
    print(f'\nBackfill Strategy:')
    print(f'  1. Extract BEEP_EDI and SMP_EDI columns from full historical CSVs')
    print(f'  2. Derive SUM_EDI = BEEP_EDI + SMP_EDI')
    print(f'  3. Full outer join on WAFER_ID + INSPECT_TIME + LAYER')
    print(f'  4. Place EDI columns adjacent to NCDD columns in output')
elif pct_5 > 0 or pct_6 > 0:
    print(f'\n⚠ PARTIAL MATCH')
    print(f'  - 8M5CL overlap: {pct_5:.1f}%')
    print(f'  - 8M6CL overlap: {pct_6:.1f}%')
    print(f'  - May have legitimate unmapped EDI records')
    print(f'  - Review non-overlapping records before deciding on backfill scope')
else:
    print(f'\n✗ NO DATA OVERLAP DETECTED')
    print(f'  - Re-check join key assumptions')

print('\n' + '=' * 80)
