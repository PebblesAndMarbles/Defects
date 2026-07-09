#!/usr/bin/env python3
"""Phase 2b: Rolling Update Evaluation - Assess 10-day NCDD+EDI CSVs for scheduled refresh"""

import pandas as pd
from datetime import datetime, timedelta

print('=' * 90)
print('PHASE 2B: ROLLING UPDATE EVALUATION - 10-DAY NCDD+EDI FILES')
print('=' * 90)

start_time = datetime.now()

# ============================================================================
# STEP 1: Load rolling source files and production baseline
# ============================================================================
print('\n[1/7] Loading source files...')

rolling_5 = pd.read_csv('8M5CL_NCDD_EDI.csv', low_memory=False)
rolling_6 = pd.read_csv('8M6CL_NCDD_EDI.csv', low_memory=False)
prod_60d = pd.read_csv('../outputs/wafer/8M5CL_8M6CL_EXTENDED_60DAY.csv', low_memory=False)
prod_full = pd.read_csv('../outputs/wafer/8M5CL_8M6CL_EXTENDED.csv', low_memory=False)

print(f'  8M5CL_NCDD_EDI.csv: {len(rolling_5):,} rows')
print(f'  8M6CL_NCDD_EDI.csv: {len(rolling_6):,} rows')
print(f'  Production 60-day: {len(prod_60d):,} rows')
print(f'  Production full: {len(prod_full):,} rows')

# ============================================================================
# STEP 2: Column inventory and comparison
# ============================================================================
print('\n[2/7] Column structure verification...')

print('\n8M5CL_NCDD_EDI.csv columns (first 20):')
for i, col in enumerate(rolling_5.columns[:20], 1):
    print(f'  {i:2d}. {col}')

print(f'\n8M6CL_NCDD_EDI.csv columns (first 20):')
for i, col in enumerate(rolling_6.columns[:20], 1):
    print(f'  {i:2d}. {col}')

# Check for required columns
print('\n' + '=' * 90)
print('COLUMN VERIFICATION')
print('=' * 90)

required_cols = ['WAFER_ID', 'INSPECTION_TIME@DEFECT', 'LAYER',
                 'DEFECT@WAFER@CLASS_NCDD@BEEP', 'DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE',
                 'DEFECT@WAFER@CLASS_EDI@BEEP', 'DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE']

for csv_name, df in [('8M5CL_NCDD_EDI', rolling_5), ('8M6CL_NCDD_EDI', rolling_6)]:
    print(f'\n{csv_name}:')
    for col in required_cols:
        status = '✓' if col in df.columns else '✗'
        print(f'  {status} {col}')

# ============================================================================
# STEP 3: Dual-metric coverage analysis
# ============================================================================
print('\n[3/7] Dual-metric coverage analysis...')

for csv_name, df in [('8M5CL_NCDD_EDI', rolling_5), ('8M6CL_NCDD_EDI', rolling_6)]:
    print(f'\n{csv_name}:')
    
    # NCDD coverage
    beep_ncdd_nonnull = df['DEFECT@WAFER@CLASS_NCDD@BEEP'].notna().sum()
    smp_ncdd_nonnull = df['DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE'].notna().sum()
    
    # EDI coverage
    beep_edi_nonnull = df['DEFECT@WAFER@CLASS_EDI@BEEP'].notna().sum()
    smp_edi_nonnull = df['DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE'].notna().sum()
    
    print(f'  NCDD Metrics:')
    print(f'    BEEP: {beep_ncdd_nonnull}/{len(df)} ({beep_ncdd_nonnull/len(df)*100:.1f}%)')
    print(f'    SMP:  {smp_ncdd_nonnull}/{len(df)} ({smp_ncdd_nonnull/len(df)*100:.1f}%)')
    print(f'  EDI Metrics:')
    print(f'    BEEP: {beep_edi_nonnull}/{len(df)} ({beep_edi_nonnull/len(df)*100:.1f}%)')
    print(f'    SMP:  {smp_edi_nonnull}/{len(df)} ({smp_edi_nonnull/len(df)*100:.1f}%)')

# ============================================================================
# STEP 4: Parse timestamps and verify data freshness
# ============================================================================
print('\n[4/7] Timestamp analysis and freshness check...')

rolling_5['_inspect_dt'] = pd.to_datetime(rolling_5['INSPECTION_TIME@DEFECT'], format='%m/%d/%Y %I:%M:%S %p')
rolling_6['_inspect_dt'] = pd.to_datetime(rolling_6['INSPECTION_TIME@DEFECT'], format='%m/%d/%Y %I:%M:%S %p')
prod_60d['_inspect_dt'] = pd.to_datetime(prod_60d['INSPECT_TIME'], format='%Y-%m-%d %H:%M:%S')
prod_full['_inspect_dt'] = pd.to_datetime(prod_full['INSPECT_TIME'], format='%Y-%m-%d %H:%M:%S')

now = datetime.now()

for csv_name, df in [('8M5CL_NCDD_EDI', rolling_5), ('8M6CL_NCDD_EDI', rolling_6)]:
    min_dt = df['_inspect_dt'].min()
    max_dt = df['_inspect_dt'].max()
    span_days = (max_dt - min_dt).days
    
    days_old_min = (now - min_dt).days
    days_old_max = (now - max_dt).days
    
    print(f'\n{csv_name}:')
    print(f'  Oldest record: {min_dt.strftime("%Y-%m-%d %H:%M:%S")} ({days_old_min} days old)')
    print(f'  Newest record: {max_dt.strftime("%Y-%m-%d %H:%M:%S")} ({days_old_max} days old)')
    print(f'  Time span: {span_days} days')

# ============================================================================
# STEP 5: Overlap with production 60-day baseline
# ============================================================================
print('\n[5/7] Data overlap with production 60-day baseline...')

# Create join keys
rolling_5['_join_key'] = list(zip(rolling_5['WAFER_ID'], rolling_5['_inspect_dt'], rolling_5['LAYER']))
rolling_6['_join_key'] = list(zip(rolling_6['WAFER_ID'], rolling_6['_inspect_dt'], rolling_6['LAYER']))
prod_60d['_join_key'] = list(zip(prod_60d['WAFER_ID'], prod_60d['_inspect_dt'], prod_60d['LAYER']))

rolling_5_keys = set(rolling_5['_join_key'])
rolling_6_keys = set(rolling_6['_join_key'])
prod_60d_keys = set(prod_60d['_join_key'])

overlap_5_60d = rolling_5_keys & prod_60d_keys
overlap_6_60d = rolling_6_keys & prod_60d_keys

pct_5_60d = (len(overlap_5_60d) / len(rolling_5_keys) * 100) if len(rolling_5_keys) > 0 else 0
pct_6_60d = (len(overlap_6_60d) / len(rolling_6_keys) * 100) if len(rolling_6_keys) > 0 else 0

print(f'\n8M5CL_NCDD_EDI vs 60-day production:')
print(f'  Rolling keys: {len(rolling_5_keys):,}')
print(f'  Production 60d keys: {len(prod_60d_keys):,}')
print(f'  Matched: {len(overlap_5_60d):,} ({pct_5_60d:.1f}%)')
print(f'  Unique to rolling: {len(rolling_5_keys) - len(overlap_5_60d):,}')
print(f'  Unique to production: {len(prod_60d_keys) - len(overlap_5_60d):,}')

print(f'\n8M6CL_NCDD_EDI vs 60-day production:')
print(f'  Rolling keys: {len(rolling_6_keys):,}')
print(f'  Production 60d keys: {len(prod_60d_keys):,}')
print(f'  Matched: {len(overlap_6_60d):,} ({pct_6_60d:.1f}%)')
print(f'  Unique to rolling: {len(rolling_6_keys) - len(overlap_6_60d):,}')
print(f'  Unique to production: {len(prod_60d_keys) - len(overlap_6_60d):,}')

# ============================================================================
# STEP 6: Overlap with full production baseline
# ============================================================================
print('\n[6/7] Data overlap with full production baseline...')

prod_full['_join_key'] = list(zip(prod_full['WAFER_ID'], prod_full['_inspect_dt'], prod_full['LAYER']))
prod_full_keys = set(prod_full['_join_key'])

overlap_5_full = rolling_5_keys & prod_full_keys
overlap_6_full = rolling_6_keys & prod_full_keys

pct_5_full = (len(overlap_5_full) / len(rolling_5_keys) * 100) if len(rolling_5_keys) > 0 else 0
pct_6_full = (len(overlap_6_full) / len(rolling_6_keys) * 100) if len(rolling_6_keys) > 0 else 0

print(f'\n8M5CL_NCDD_EDI vs full production:')
print(f'  Matched: {len(overlap_5_full):,} ({pct_5_full:.1f}%)')
print(f'  New records (not in full production): {len(rolling_5_keys) - len(overlap_5_full):,}')

print(f'\n8M6CL_NCDD_EDI vs full production:')
print(f'  Matched: {len(overlap_6_full):,} ({pct_6_full:.1f}%)')
print(f'  New records (not in full production): {len(rolling_6_keys) - len(overlap_6_full):,}')

# ============================================================================
# STEP 7: Data quality and consistency checks
# ============================================================================
print('\n[7/7] Data quality and consistency checks...')

for csv_name, df in [('8M5CL_NCDD_EDI', rolling_5), ('8M6CL_NCDD_EDI', rolling_6)]:
    print(f'\n{csv_name}:')
    
    # Duplicate key check
    unique_keys = len(set(zip(df['WAFER_ID'], df['INSPECTION_TIME@DEFECT'], df['LAYER'])))
    duplicate_rate = (1 - unique_keys / len(df)) * 100
    print(f'  Duplicate join keys: {len(df) - unique_keys} ({duplicate_rate:.1f}%)')
    
    # Null value check
    print(f'  WAFER_ID nulls: {df["WAFER_ID"].isna().sum()}')
    print(f'  LAYER nulls: {df["LAYER"].isna().sum()}')
    print(f'  INSPECTION_TIME@DEFECT nulls: {df["INSPECTION_TIME@DEFECT"].isna().sum()}')

# ============================================================================
# RECOMMENDATIONS
# ============================================================================
print('\n' + '=' * 90)
print('PHASE 2B SUITABILITY ASSESSMENT')
print('=' * 90)

print('\n✓ ADVANTAGES OF ROLLING 10-DAY NCDD+EDI FILES:')
print('  1. Dual metrics in single source (no separate file coordination needed)')
print('  2. Smaller file size (10-day lookback vs. full historical)')
print('  3. JSL query already scheduled/automated')
print('  4. Matches pipeline 10-day overlap window perfectly')

print('\n⚠ CONSIDERATIONS:')
print('  1. Rolling files lose historical depth for long-term trend analysis')
print('  2. Recommend keeping full historical EDI CSV as archival backup')
print('  3. New records (not in production): ~' + 
      f'{((len(rolling_5_keys) - len(overlap_5_full)) + (len(rolling_6_keys) - len(overlap_6_full))) // 2} rows per refresh')
print('  4. Data freshness depends on JSL execution cadence')

if pct_5_full > 50 and pct_6_full > 50:
    print('\n✓ RECOMMENDATION: SUITABLE FOR ROLLING UPDATE')
    print('  - Replace separate 8M5CL_NCDD.csv + 8M6CL_NCDD.csv with these dual-metric files')
    print('  - Scheduled frequency: Match JSL query schedule (recommend 10-day refresh)')
    print('  - Implementation: Modify main.py to load 8M5CL_NCDD_EDI.csv + 8M6CL_NCDD_EDI.csv')
    print('  - Benefit: Both NCDD and EDI metrics automatically included in each refresh')
else:
    print('\n✗ RECOMMENDATION: FURTHER INVESTIGATION NEEDED')
    print(f'  - Current overlap with production: 8M5CL {pct_5_full:.1f}%, 8M6CL {pct_6_full:.1f}%')
    print('  - Recommend reviewing timestamp alignment and join key assumptions')

elapsed = (datetime.now() - start_time).total_seconds()
print(f'\n✓ PHASE 2B COMPLETE (Elapsed: {elapsed:.1f}s)')
print('=' * 90)
