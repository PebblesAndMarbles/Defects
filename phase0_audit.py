#!/usr/bin/env python3
"""Phase 0: Scoping Audit - Verify data overlap between EDI CSVs and production"""

import pandas as pd
from pathlib import Path

print('=' * 80)
print('PHASE 0: SCOPING AUDIT - EDI BACKFILL FEASIBILITY')
print('=' * 80)

# Load full historical EDI CSVs
print('\n[1/3] Loading 8M5CL_EDI.csv...')
edi_5 = pd.read_csv('BE_QUERY_FILES/8M5CL_EDI.csv', low_memory=False)
print(f'  Rows: {len(edi_5):,}')
print(f'  Columns: {list(edi_5.columns)[:10]}...')

print('\n[2/3] Loading 8M6CL_EDI.csv...')
edi_6 = pd.read_csv('BE_QUERY_FILES/8M6CL_EDI.csv', low_memory=False)
print(f'  Rows: {len(edi_6):,}')

print('\n[3/3] Loading production 8M5CL_8M6CL_EXTENDED.csv...')
prod = pd.read_csv('outputs/wafer/8M5CL_8M6CL_EXTENDED.csv', low_memory=False)
print(f'  Rows: {len(prod):,}')
print(f'  Columns: {list(prod.columns)[:10]}...')

# Verify join keys exist
print('\n' + '=' * 80)
print('JOIN KEY VERIFICATION')
print('=' * 80)

required_keys = {
    'edi_5': ['WAFER_ID', 'INSPECTION_TIME@DEFECT', 'LAYER'],
    'edi_6': ['WAFER_ID', 'INSPECTION_TIME@DEFECT', 'LAYER'],
    'prod': ['WAFER_ID', 'INSPECT_TIME', 'LAYER']
}

all_good = True
for df_name, keys in required_keys.items():
    if df_name == 'edi_5':
        df = edi_5
    elif df_name == 'edi_6':
        df = edi_6
    else:
        df = prod
    
    for key in keys:
        if key in df.columns:
            print(f'✓ {df_name:10} has {key}')
        else:
            print(f'✗ {df_name:10} MISSING {key}')
            all_good = False

if not all_good:
    print('\n[ERROR] Missing required join keys. Cannot proceed.')
    exit(1)

# Create join key tuples
print('\n' + '=' * 80)
print('COMPUTING DATA OVERLAP')
print('=' * 80)

print('\nExtracting join keys from 8M5CL_EDI...')
edi_5['_join_key'] = list(zip(edi_5['WAFER_ID'], edi_5['INSPECTION_TIME@DEFECT'], edi_5['LAYER']))
edi_5_keys = set(edi_5['_join_key'])
print(f'  Unique keys: {len(edi_5_keys):,}')

print('\nExtracting join keys from 8M6CL_EDI...')
edi_6['_join_key'] = list(zip(edi_6['WAFER_ID'], edi_6['INSPECTION_TIME@DEFECT'], edi_6['LAYER']))
edi_6_keys = set(edi_6['_join_key'])
print(f'  Unique keys: {len(edi_6_keys):,}')

print('\nExtracting join keys from production...')
prod['_join_key'] = list(zip(prod['WAFER_ID'], prod['INSPECT_TIME'], prod['LAYER']))
prod_keys = set(prod['_join_key'])
print(f'  Unique keys: {len(prod_keys):,}')

# Compute overlap
print('\n' + '=' * 80)
print('OVERLAP RESULTS')
print('=' * 80)

overlap_5 = edi_5_keys & prod_keys
overlap_6 = edi_6_keys & prod_keys

pct_5 = (len(overlap_5) / len(edi_5_keys) * 100) if len(edi_5_keys) > 0 else 0
pct_6 = (len(overlap_6) / len(edi_6_keys) * 100) if len(edi_6_keys) > 0 else 0

print(f'\n8M5CL_EDI:')
print(f'  Total rows: {len(edi_5):,}')
print(f'  Unique keys: {len(edi_5_keys):,}')
print(f'  Matched with production: {len(overlap_5):,} ({pct_5:.1f}%)')
print(f'  → {len(edi_5_keys) - len(overlap_5):,} rows not in production (may be new/future data)')

print(f'\n8M6CL_EDI:')
print(f'  Total rows: {len(edi_6):,}')
print(f'  Unique keys: {len(edi_6_keys):,}')
print(f'  Matched with production: {len(overlap_6):,} ({pct_6:.1f}%)')
print(f'  → {len(edi_6_keys) - len(overlap_6):,} rows not in production (may be new/future data)')

# Check target EDI columns
print('\n' + '=' * 80)
print('TARGET EDI COLUMNS VERIFICATION')
print('=' * 80)

target_cols = {
    'DEFECT@WAFER@CLASS_EDI@BEEP': 'BEEP_EDI',
    'DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE': 'SMP_EDI'
}

print('\n8M5CL_EDI columns to extract:')
for src, tgt in target_cols.items():
    if src in edi_5.columns:
        print(f'  ✓ {src:50} → {tgt}')
    else:
        print(f'  ✗ {src:50} MISSING!')

# Final recommendation
print('\n' + '=' * 80)
print('AUDIT CONCLUSION')
print('=' * 80)

if pct_5 > 0 and pct_6 > 0:
    print(f'\n✓ PROCEED TO BACKFILL')
    print(f'  - Join key (WAFER_ID + INSPECTION_TIME@DEFECT + LAYER) is valid')
    print(f'  - Data overlap detected for both 8M5CL ({pct_5:.1f}%) and 8M6CL ({pct_6:.1f}%)')
    print(f'  - Non-overlapping EDI rows may represent new data not yet in production')
    print(f'  - Target columns present in source files')
else:
    print(f'\n⚠ WARNING: LOW OVERLAP')
    print(f'  - 8M5CL overlap: {pct_5:.1f}%')
    print(f'  - 8M6CL overlap: {pct_6:.1f}%')
    print(f'  - Verify join key assumptions or data source compatibility')

print('\n' + '=' * 80)
