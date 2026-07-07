#!/usr/bin/env python3
"""Phase 2b: Evaluate suitability of rolling 10-day NCDD_EDI files for regular updates"""

import pandas as pd
from datetime import datetime

print('=' * 80)
print('PHASE 2B: ROLLING UPDATE EVALUATION')
print('Assessing 8M5CL_NCDD_EDI.csv & 8M6CL_NCDD_EDI.csv for regular refresh cadence')
print('=' * 80)

# ============================================================================
# STEP 1: Load rolling files
# ============================================================================
print('\n[1/6] Loading 10-day rolling NCDD_EDI files...')

try:
    rolling_5 = pd.read_csv('BE_QUERY_FILES/8M5CL_NCDD_EDI.csv', low_memory=False)
    print(f'  8M5CL_NCDD_EDI.csv: {len(rolling_5):,} rows')
except Exception as e:
    print(f'  ✗ Failed to load 8M5CL_NCDD_EDI.csv: {e}')
    rolling_5 = None

try:
    rolling_6 = pd.read_csv('BE_QUERY_FILES/8M6CL_NCDD_EDI.csv', low_memory=False)
    print(f'  8M6CL_NCDD_EDI.csv: {len(rolling_6):,} rows')
except Exception as e:
    print(f'  ✗ Failed to load 8M6CL_NCDD_EDI.csv: {e}')
    rolling_6 = None

if rolling_5 is None or rolling_6 is None:
    print('\n[ERROR] Cannot proceed without both rolling files')
    exit(1)

# ============================================================================
# STEP 2: Verify column structure
# ============================================================================
print('\n[2/6] Verifying column structure...')

required_cols = ['WAFER_ID', 'INSPECTION_TIME@DEFECT', 'LAYER']
required_ncdd = ['DEFECT@WAFER@CLASS_NCDD@BEEP', 'DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE']
required_edi = ['DEFECT@WAFER@CLASS_EDI@BEEP', 'DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE']

print('\n  8M5CL_NCDD_EDI.csv:')
all_cols_5 = True
for col in required_cols:
    status = '✓' if col in rolling_5.columns else '✗'
    print(f'    {status} {col}')
    if col not in rolling_5.columns:
        all_cols_5 = False

for col in required_ncdd:
    status = '✓' if col in rolling_5.columns else '✗'
    print(f'    {status} {col} (NCDD)')
    if col not in rolling_5.columns:
        all_cols_5 = False

for col in required_edi:
    status = '✓' if col in rolling_5.columns else '✗'
    print(f'    {status} {col} (EDI)')
    if col not in rolling_5.columns:
        all_cols_5 = False

print('\n  8M6CL_NCDD_EDI.csv:')
all_cols_6 = True
for col in required_cols:
    status = '✓' if col in rolling_6.columns else '✗'
    print(f'    {status} {col}')
    if col not in rolling_6.columns:
        all_cols_6 = False

for col in required_ncdd:
    status = '✓' if col in rolling_6.columns else '✗'
    print(f'    {status} {col} (NCDD)')
    if col not in rolling_6.columns:
        all_cols_6 = False

for col in required_edi:
    status = '✓' if col in rolling_6.columns else '✗'
    print(f'    {status} {col} (EDI)')
    if col not in rolling_6.columns:
        all_cols_6 = False

if not (all_cols_5 and all_cols_6):
    print('\n[ERROR] Rolling files missing required columns for join/derivation')
    exit(1)

# ============================================================================
# STEP 3: Load production data for comparison
# ============================================================================
print('\n[3/6] Loading production CSV for overlap assessment...')

prod = pd.read_csv('outputs/wafer/8M5CL_8M6CL_EXTENDED.csv', low_memory=False)
print(f'  Production CSV: {len(prod):,} rows')

# ============================================================================
# STEP 4: Assess temporal characteristics
# ============================================================================
print('\n[4/6] Analyzing temporal characteristics...')

# Parse timestamps with proper format handling
rolling_5['_dt'] = pd.to_datetime(
    rolling_5['INSPECTION_TIME@DEFECT'],
    format='%m/%d/%Y %I:%M:%S %p',
    errors='coerce'
)
rolling_6['_dt'] = pd.to_datetime(
    rolling_6['INSPECTION_TIME@DEFECT'],
    format='%m/%d/%Y %I:%M:%S %p',
    errors='coerce'
)
prod['_dt'] = pd.to_datetime(
    prod['INSPECT_TIME'],
    format='%Y-%m-%d %H:%M:%S',
    errors='coerce'
)

print('\n  8M5CL_NCDD_EDI date range:')
print(f'    First: {rolling_5["_dt"].min()}')
print(f'    Last:  {rolling_5["_dt"].max()}')
date_span_5 = (rolling_5['_dt'].max() - rolling_5['_dt'].min()).days
print(f'    Span: {date_span_5} days')

print('\n  8M6CL_NCDD_EDI date range:')
print(f'    First: {rolling_6["_dt"].min()}')
print(f'    Last:  {rolling_6["_dt"].max()}')
date_span_6 = (rolling_6['_dt'].max() - rolling_6['_dt'].min()).days
print(f'    Span: {date_span_6} days')

print('\n  Production date range:')
print(f'    First: {prod["_dt"].min()}')
print(f'    Last:  {prod["_dt"].max()}')

# Check if rolling files are truly 10-day lookback
print(f'\n  Assessment: Rolling files represent {date_span_5}/{date_span_6} day span (expect ~10 days)')
if date_span_5 <= 10 and date_span_6 <= 10:
    print('    ✓ Consistent with 10-day rolling window specification')
else:
    print('    ⚠ Wider than expected 10-day window - may need clarification')

# ============================================================================
# STEP 5: Data overlap with production (using production CSVs from backfill)
# ============================================================================
print('\n[5/6] Analyzing data overlap with production...')

# Create join keys
rolling_5['_key'] = list(zip(rolling_5['WAFER_ID'], rolling_5['_dt'], rolling_5['LAYER']))
rolling_6['_key'] = list(zip(rolling_6['WAFER_ID'], rolling_6['_dt'], rolling_6['LAYER']))
prod['_key'] = list(zip(prod['WAFER_ID'], prod['_dt'], prod['LAYER']))

rolling_5_keys = set(rolling_5['_key'])
rolling_6_keys = set(rolling_6['_key'])
prod_keys = set(prod['_key'])

overlap_5 = rolling_5_keys & prod_keys
overlap_6 = rolling_6_keys & prod_keys

pct_5 = len(overlap_5) / len(rolling_5_keys) * 100 if len(rolling_5_keys) > 0 else 0
pct_6 = len(overlap_6) / len(rolling_6_keys) * 100 if len(rolling_6_keys) > 0 else 0

print(f'\n  8M5CL_NCDD_EDI:')
print(f'    Total rows: {len(rolling_5):,}')
print(f'    Overlap with production: {len(overlap_5):,}/{len(rolling_5_keys):,} ({pct_5:.1f}%)')
print(f'    New/non-overlapping: {len(rolling_5_keys) - len(overlap_5):,}')

print(f'\n  8M6CL_NCDD_EDI:')
print(f'    Total rows: {len(rolling_6):,}')
print(f'    Overlap with production: {len(overlap_6):,}/{len(rolling_6_keys):,} ({pct_6:.1f}%)')
print(f'    New/non-overlapping: {len(rolling_6_keys) - len(overlap_6):,}')

# ============================================================================
# STEP 6: Data completeness assessment
# ============================================================================
print('\n[6/6] Assessing data completeness and suitability...')

print('\n  NCDD metrics in rolling files:')
ncdd_beep_5_null = rolling_5['DEFECT@WAFER@CLASS_NCDD@BEEP'].isna().sum()
ncdd_smp_5_null = rolling_5['DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE'].isna().sum()
print(f'    8M5CL BEEP_NCDD: {len(rolling_5) - ncdd_beep_5_null:,}/{len(rolling_5):,} non-null')
print(f'    8M5CL SMP_NCDD: {len(rolling_5) - ncdd_smp_5_null:,}/{len(rolling_5):,} non-null')

ncdd_beep_6_null = rolling_6['DEFECT@WAFER@CLASS_NCDD@BEEP'].isna().sum()
ncdd_smp_6_null = rolling_6['DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE'].isna().sum()
print(f'    8M6CL BEEP_NCDD: {len(rolling_6) - ncdd_beep_6_null:,}/{len(rolling_6):,} non-null')
print(f'    8M6CL SMP_NCDD: {len(rolling_6) - ncdd_smp_6_null:,}/{len(rolling_6):,} non-null')

print('\n  EDI metrics in rolling files:')
edi_beep_5_null = rolling_5['DEFECT@WAFER@CLASS_EDI@BEEP'].isna().sum()
edi_smp_5_null = rolling_5['DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE'].isna().sum()
print(f'    8M5CL BEEP_EDI: {len(rolling_5) - edi_beep_5_null:,}/{len(rolling_5):,} non-null')
print(f'    8M5CL SMP_EDI: {len(rolling_5) - edi_smp_5_null:,}/{len(rolling_5):,} non-null')

edi_beep_6_null = rolling_6['DEFECT@WAFER@CLASS_EDI@BEEP'].isna().sum()
edi_smp_6_null = rolling_6['DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE'].isna().sum()
print(f'    8M6CL BEEP_EDI: {len(rolling_6) - edi_beep_6_null:,}/{len(rolling_6):,} non-null')
print(f'    8M6CL SMP_EDI: {len(rolling_6) - edi_smp_6_null:,}/{len(rolling_6):,} non-null')

# ============================================================================
# FINAL RECOMMENDATION
# ============================================================================
print('\n' + '=' * 80)
print('SUITABILITY ASSESSMENT FOR ROLLING UPDATES')
print('=' * 80)

# Check all criteria
criteria_met = True
issues = []

if not (all_cols_5 and all_cols_6):
    criteria_met = False
    issues.append('Missing required columns for join/derivation')

if pct_5 < 70 or pct_6 < 70:
    criteria_met = False
    issues.append(f'Low overlap with production (8M5CL: {pct_5:.1f}%, 8M6CL: {pct_6:.1f}%)')

if date_span_5 > 11 or date_span_6 > 11:
    criteria_met = False
    issues.append(f'Date span wider than expected 10-day window')

if (len(rolling_5) - ncdd_beep_5_null) < len(rolling_5) * 0.95:
    issues.append(f'8M5CL NCDD completeness < 95%')

if (len(rolling_6) - ncdd_beep_6_null) < len(rolling_6) * 0.95:
    issues.append(f'8M6CL NCDD completeness < 95%')

if (len(rolling_5) - edi_beep_5_null) < len(rolling_5) * 0.90:
    issues.append(f'8M5CL EDI completeness < 90%')

if (len(rolling_6) - edi_beep_6_null) < len(rolling_6) * 0.90:
    issues.append(f'8M6CL EDI completeness < 90%')

if criteria_met:
    print('\n✓ SUITABLE FOR REGULAR ROLLING UPDATES')
    print('\nRecommendation: Enable 8M5CL_NCDD_EDI.csv & 8M6CL_NCDD_EDI.csv as primary rolling source')
    print('Benefits:')
    print('  - Single JMP pull combines both NCDD and EDI metrics')
    print('  - Aligns with 10-day JSL refresh cadence')
    print('  - Reduces source data management complexity')
    print('  - Both metrics updated simultaneously')
else:
    print('\n⚠ CONDITIONAL SUITABILITY')
    print('\nIssues detected:')
    for issue in issues:
        print(f'  - {issue}')
    print('\nRecommendation: Investigate issues before enabling regular updates')
    print('Consider:')
    if date_span_5 > 11 or date_span_6 > 11:
        print('  1. Verify JMP query is configured for 10-day lookback window')
    if any('overlap' in i for i in issues):
        print('  2. Clarify if 10-day rolling is supposed to include future data not yet in production')
    if any('completeness' in i for i in issues):
        print('  3. Investigate why metrics are missing in rolling files')

print('\n' + '=' * 80)
print('RECOMMENDED IMPLEMENTATION STRATEGY')
print('=' * 80)
print('''
Current Setup (Post-Phase 1 backfill):
  - Full historical EDI: 8M5CL_EDI.csv, 8M6CL_EDI.csv (one-time backfill complete)
  - Full historical NCDD: Sources in JSL
  - Production CSVs: Pre-backfilled with EDI columns
  
Candidate Rolling Approach:
  - Use 8M5CL_NCDD_EDI.csv & 8M6CL_NCDD_EDI.csv for regular refresh
  - Separate EDI refresh cadence (new dedicated JSL queries if needed)
  
Decision Factors:
  1. If rolling files SUITABLE: Migrate to combined NCDD_EDI source
     → Single JMP pull, single update step, lower maintenance
  2. If rolling files CONDITIONAL: 
     → Investigate issues, then decide between:
       a) Fix/clarify rolling source → migrate to combined
       b) Keep separate NCDD/EDI refresh cadence → maintain current approach
  3. If rolling files UNSUITABLE:
     → Maintain separate refresh streams (NCDD from existing JSL, EDI TBD)
''')

print('=' * 80)
