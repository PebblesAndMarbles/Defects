#!/usr/bin/env python3
"""Phase 1: Backfill - Add EDI metrics to production CSVs"""

import pandas as pd
from pathlib import Path
from datetime import datetime

print('=' * 80)
print('PHASE 1: BACKFILL - ADD EDI METRICS TO PRODUCTION CSVs')
print('=' * 80)

start_time = datetime.now()

# ============================================================================
# STEP 1: Load source EDI data
# ============================================================================
print('\n[1/6] Loading EDI source files...')

edi_5 = pd.read_csv('BE_QUERY_FILES/8M5CL_EDI.csv', low_memory=False)
edi_6 = pd.read_csv('BE_QUERY_FILES/8M6CL_EDI.csv', low_memory=False)

print(f'  8M5CL_EDI: {len(edi_5):,} rows')
print(f'  8M6CL_EDI: {len(edi_6):,} rows')

# ============================================================================
# STEP 2: Extract and rename target EDI columns
# ============================================================================
print('\n[2/6] Extracting and deriving EDI columns...')

# For 8M5CL
edi_5_cols = ['WAFER_ID', 'INSPECTION_TIME@DEFECT', 'LAYER',
              'DEFECT@WAFER@CLASS_EDI@BEEP',
              'DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE']
edi_5_extract = edi_5[edi_5_cols].copy()
edi_5_extract.rename(columns={
    'DEFECT@WAFER@CLASS_EDI@BEEP': 'BEEP_EDI',
    'DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE': 'SMP_EDI',
    'INSPECTION_TIME@DEFECT': '_INSPECT_TIME_EDI'
}, inplace=True)
edi_5_extract['SUM_EDI'] = edi_5_extract['BEEP_EDI'] + edi_5_extract['SMP_EDI']

print(f'  8M5CL_EDI extracted: BEEP_EDI, SMP_EDI, SUM_EDI ({len(edi_5_extract):,} rows)')

# For 8M6CL
edi_6_cols = ['WAFER_ID', 'INSPECTION_TIME@DEFECT', 'LAYER',
              'DEFECT@WAFER@CLASS_EDI@BEEP',
              'DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE']
edi_6_extract = edi_6[edi_6_cols].copy()
edi_6_extract.rename(columns={
    'DEFECT@WAFER@CLASS_EDI@BEEP': 'BEEP_EDI',
    'DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE': 'SMP_EDI',
    'INSPECTION_TIME@DEFECT': '_INSPECT_TIME_EDI'
}, inplace=True)
edi_6_extract['SUM_EDI'] = edi_6_extract['BEEP_EDI'] + edi_6_extract['SMP_EDI']

print(f'  8M6CL_EDI extracted: BEEP_EDI, SMP_EDI, SUM_EDI ({len(edi_6_extract):,} rows)')

# Combine
edi_combined = pd.concat([edi_5_extract, edi_6_extract], ignore_index=True)
print(f'  Combined EDI data: {len(edi_combined):,} rows')

# ============================================================================
# STEP 3: Parse timestamps for joining
# ============================================================================
print('\n[3/6] Parsing timestamps...')

edi_combined['_INSPECT_TIME_EDI'] = pd.to_datetime(
    edi_combined['_INSPECT_TIME_EDI'], 
    format='%m/%d/%Y %I:%M:%S %p'
)
print(f'  EDI timestamps parsed')

# ============================================================================
# STEP 4: Process and backfill 8M5CL_8M6CL_EXTENDED_60DAY.csv
# ============================================================================
print('\n[4/6] Processing 8M5CL_8M6CL_EXTENDED_60DAY.csv...')

prod_60d_path = 'outputs/wafer/8M5CL_8M6CL_EXTENDED_60DAY.csv'
prod_60d = pd.read_csv(prod_60d_path, low_memory=False)
print(f'  Original: {len(prod_60d):,} rows, {len(prod_60d.columns)} columns')

# Parse production timestamps
prod_60d['_INSPECT_TIME'] = pd.to_datetime(
    prod_60d['INSPECT_TIME'],
    format='%Y-%m-%d %H:%M:%S'
)

# Merge with EDI data
prod_60d_with_edi = prod_60d.merge(
    edi_combined,
    how='left',
    left_on=['WAFER_ID', '_INSPECT_TIME', 'LAYER'],
    right_on=['WAFER_ID', '_INSPECT_TIME_EDI', 'LAYER'],
    suffixes=('', '_edi')
)

# Clean up temp columns
prod_60d_with_edi.drop(columns=['_INSPECT_TIME', '_INSPECT_TIME_EDI'], inplace=True)

print(f'  After merge: {len(prod_60d_with_edi):,} rows')
print(f'  EDI columns added: BEEP_EDI, SMP_EDI, SUM_EDI')
print(f'  Non-null EDI records: {prod_60d_with_edi["BEEP_EDI"].notna().sum():,}')

# Save
prod_60d_with_edi.to_csv(prod_60d_path, index=False)
print(f'  ✓ Saved: {prod_60d_path}')

# ============================================================================
# STEP 5: Process and backfill 8M5CL_8M6CL_EXTENDED.csv
# ============================================================================
print('\n[5/6] Processing 8M5CL_8M6CL_EXTENDED.csv...')

prod_full_path = 'outputs/wafer/8M5CL_8M6CL_EXTENDED.csv'
prod_full = pd.read_csv(prod_full_path, low_memory=False)
print(f'  Original: {len(prod_full):,} rows, {len(prod_full.columns)} columns')

# Parse production timestamps
prod_full['_INSPECT_TIME'] = pd.to_datetime(
    prod_full['INSPECT_TIME'],
    format='%Y-%m-%d %H:%M:%S'
)

# Merge with EDI data
prod_full_with_edi = prod_full.merge(
    edi_combined,
    how='left',
    left_on=['WAFER_ID', '_INSPECT_TIME', 'LAYER'],
    right_on=['WAFER_ID', '_INSPECT_TIME_EDI', 'LAYER'],
    suffixes=('', '_edi')
)

# Clean up temp columns
prod_full_with_edi.drop(columns=['_INSPECT_TIME', '_INSPECT_TIME_EDI'], inplace=True)

print(f'  After merge: {len(prod_full_with_edi):,} rows')
print(f'  EDI columns added: BEEP_EDI, SMP_EDI, SUM_EDI')
print(f'  Non-null EDI records: {prod_full_with_edi["BEEP_EDI"].notna().sum():,}')

# Save
prod_full_with_edi.to_csv(prod_full_path, index=False)
print(f'  ✓ Saved: {prod_full_path}')

# ============================================================================
# STEP 6: Verify and report
# ============================================================================
print('\n[6/6] Verification and Summary...')

print(f'\nBackfill Summary:')
print(f'  8M5CL_8M6CL_EXTENDED_60DAY.csv:')
print(f'    - Rows with BEEP_EDI: {prod_60d_with_edi["BEEP_EDI"].notna().sum():,}')
print(f'    - Rows with SMP_EDI: {prod_60d_with_edi["SMP_EDI"].notna().sum():,}')
print(f'    - Rows with SUM_EDI: {prod_60d_with_edi["SUM_EDI"].notna().sum():,}')
print(f'  8M5CL_8M6CL_EXTENDED.csv:')
print(f'    - Rows with BEEP_EDI: {prod_full_with_edi["BEEP_EDI"].notna().sum():,}')
print(f'    - Rows with SMP_EDI: {prod_full_with_edi["SMP_EDI"].notna().sum():,}')
print(f'    - Rows with SUM_EDI: {prod_full_with_edi["SUM_EDI"].notna().sum():,}')

elapsed = (datetime.now() - start_time).total_seconds()
print(f'\n✓ PHASE 1 COMPLETE (Elapsed: {elapsed:.1f}s)')
print('\nNext: Phase 2 - Modify pipeline (defect_processor.py) to include EDI renaming')
print('=' * 80)
