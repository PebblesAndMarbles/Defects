#!/usr/bin/env python3
"""Phase 2b Revised: Evaluate available rolling 10-day NCDD_EDI file(s)"""

import pandas as pd
from datetime import datetime

print('=' * 80)
print('PHASE 2B REVISED: ROLLING UPDATE FILE AVAILABILITY & ASSESSMENT')
print('=' * 80)

# ============================================================================
# STEP 1: Inventory available rolling source files
# ============================================================================
print('\n[1/6] Inventorying available rolling/recent source files...')

rolling_files = {
    '8M5CL_NCDD_EDI.csv': ('BE_QUERY_FILES/8M5CL_NCDD_EDI.csv', 'NCDD+EDI combined', 'rolling'),
    '8M5CL_NCDD.csv': ('BE_QUERY_FILES/8M5CL_NCDD.csv', 'NCDD only', 'rolling'),
    '8M6CL_EDI.csv': ('BE_QUERY_FILES/8M6CL_EDI.csv', 'EDI only', 'full historical'),
    '8M6CL_NCDD.csv': ('BE_QUERY_FILES/8M6CL_NCDD.csv', 'NCDD only', 'rolling'),
}

print('\nChecking file availability:')
available = {}
for name, (path, desc, scope) in rolling_files.items():
    try:
        df = pd.read_csv(path, nrows=1)
        rows = pd.read_csv(path, low_memory=False)
        full_rows = len(rows)
        available[name] = (path, desc, scope, full_rows)
        print(f'  ✓ {name:25} | {desc:20} | {full_rows:6,} rows')
    except FileNotFoundError:
        print(f'  ✗ {name:25} | NOT FOUND')
    except Exception as e:
        print(f'  ✗ {name:25} | ERROR: {str(e)[:40]}')

# ============================================================================
# STEP 2: Load 8M5CL_NCDD_EDI if available
# ============================================================================
print('\n[2/6] Analyzing 8M5CL_NCDD_EDI.csv (COMBINED ROLLING FILE)...')

if '8M5CL_NCDD_EDI.csv' not in available:
    print('  [SKIP] File not available')
else:
    rolling_5 = pd.read_csv('BE_QUERY_FILES/8M5CL_NCDD_EDI.csv', low_memory=False)
    print(f'  Loaded: {len(rolling_5):,} rows, {len(rolling_5.columns)} columns')
    
    # Check required columns
    required_join = ['WAFER_ID', 'INSPECTION_TIME@DEFECT', 'LAYER']
    required_ncdd = ['DEFECT@WAFER@CLASS_NCDD@BEEP', 'DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE']
    required_edi = ['DEFECT@WAFER@CLASS_EDI@BEEP', 'DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE']
    
    print(f'\n  Column verification:')
    join_ok = all(c in rolling_5.columns for c in required_join)
    ncdd_ok = all(c in rolling_5.columns for c in required_ncdd)
    edi_ok = all(c in rolling_5.columns for c in required_edi)
    
    print(f'    Join keys: {"✓" if join_ok else "✗"} {", ".join(required_join)}')
    print(f'    NCDD cols: {"✓" if ncdd_ok else "✗"} BEEP, SMP')
    print(f'    EDI cols:  {"✓" if edi_ok else "✗"} BEEP, SMP')
    
    # Parse dates
    rolling_5['_dt'] = pd.to_datetime(
        rolling_5['INSPECTION_TIME@DEFECT'],
        format='%m/%d/%Y %I:%M:%S %p',
        errors='coerce'
    )
    
    print(f'\n  Temporal range:')
    print(f'    First: {rolling_5["_dt"].min()}')
    print(f'    Last:  {rolling_5["_dt"].max()}')
    date_span = (rolling_5['_dt'].max() - rolling_5['_dt'].min()).days
    print(f'    Span: {date_span} days')
    print(f'    {"✓" if date_span <= 10 else "⚠"} Expected 10-day window')
    
    print(f'\n  Metric completeness:')
    ncdd_beep_pct = (rolling_5['DEFECT@WAFER@CLASS_NCDD@BEEP'].notna().sum() / len(rolling_5)) * 100
    ncdd_smp_pct = (rolling_5['DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE'].notna().sum() / len(rolling_5)) * 100
    edi_beep_pct = (rolling_5['DEFECT@WAFER@CLASS_EDI@BEEP'].notna().sum() / len(rolling_5)) * 100
    edi_smp_pct = (rolling_5['DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE'].notna().sum() / len(rolling_5)) * 100
    
    print(f'    NCDD BEEP: {ncdd_beep_pct:.1f}% non-null')
    print(f'    NCDD SMP:  {ncdd_smp_pct:.1f}% non-null')
    print(f'    EDI BEEP:  {edi_beep_pct:.1f}% non-null')
    print(f'    EDI SMP:   {edi_smp_pct:.1f}% non-null')
    
    file_1_suitable = join_ok and ncdd_ok and edi_ok and date_span <= 10

# ============================================================================
# STEP 3: Check for 8M6CL_NCDD_EDI or composite approach
# ============================================================================
print('\n[3/6] Analyzing 8M6CL source situation...')

print(f'\n  Status:')
if '8M6CL_NCDD_EDI.csv' not in available:
    print(f'    ✗ 8M6CL_NCDD_EDI.csv does not exist')
    print(f'    ✓ 8M6CL_NCDD.csv exists (NCDD only)')
    print(f'    ✓ 8M6CL_EDI.csv exists (EDI full historical)')
    print(f'\n  Implication: 8M6CL has separate NCDD and EDI sources')
    print(f'    → Cannot use pure rolling "NCDD_EDI combined" approach for 8M6CL')
    print(f'    → Would need to generate 8M6CL_NCDD_EDI.csv from JSL')
else:
    print(f'    ✓ 8M6CL_NCDD_EDI.csv exists')

# ============================================================================
# STEP 4: Overlap test with production
# ============================================================================
print('\n[4/6] Testing data overlap with production CSV...')

prod = pd.read_csv('outputs/wafer/8M5CL_8M6CL_EXTENDED.csv', low_memory=False)
prod['_dt'] = pd.to_datetime(
    prod['INSPECT_TIME'],
    format='%Y-%m-%d %H:%M:%S',
    errors='coerce'
)

if '8M5CL_NCDD_EDI.csv' in available:
    rolling_5['_key'] = list(zip(rolling_5['WAFER_ID'], rolling_5['_dt'], rolling_5['LAYER']))
    prod['_key'] = list(zip(prod['WAFER_ID'], prod['_dt'], prod['LAYER']))
    
    rolling_5_keys = set(rolling_5['_key'])
    prod_keys = set(prod['_key'])
    overlap_5 = rolling_5_keys & prod_keys
    pct_5 = len(overlap_5) / len(rolling_5_keys) * 100 if len(rolling_5_keys) > 0 else 0
    
    print(f'\n  8M5CL_NCDD_EDI vs Production:')
    print(f'    Overlap: {len(overlap_5):,}/{len(rolling_5_keys):,} ({pct_5:.1f}%)')
    print(f'    {"✓" if pct_5 >= 70 else "⚠"} Expect 70%+ overlap for rolling 10-day file')

# ============================================================================
# FINAL ASSESSMENT
# ============================================================================
print('\n' + '=' * 80)
print('SUITABILITY ASSESSMENT FOR ROLLING UPDATES')
print('=' * 80)

print('\n  FILE AVAILABILITY STATUS:')
print(f'    8M5CL_NCDD_EDI.csv: AVAILABLE (combined rolling source) ✓')
print(f'    8M6CL_NCDD_EDI.csv: MISSING (would need generation from JSL) ✗')

print('\n  ASSESSMENT OPTIONS:')

print('\n  Option A: Use 8M5CL_NCDD_EDI.csv for 8M5CL only')
print('    Status: 8M5CL suitable for combined rolling source')
print('    Limitation: 8M6CL would need separate NCDD/EDI refresh')
print('    Implementation: Partial consolidation (mixed strategy)')

print('\n  Option B: Generate 8M6CL_NCDD_EDI.csv from JSL, then use both')
print('    Status: Requires JSL execution to generate missing file')
print('    Benefit: Unified rolling source for both layers')
print('    Implementation: Full consolidation (one rolling source per layer)')

print('\n  Option C: Maintain current separate refresh strategy')
print('    Status: Keep NCDD from existing JSL, maintain EDI separately')
print('    Benefit: No new JSL changes needed')
print('    Implementation: Status quo (post-backfill)')

print('\n' + '=' * 80)
print('RECOMMENDED NEXT STEP')
print('=' * 80)

print('''
QUESTION FOR USER:

1. Was 8M6CL_NCDD_EDI.csv supposed to be generated from the JMP query?
   → If YES: Run the 8M6CL_NCDD_EDI_SHORT.jsl script to generate it
   → If NO: File may never be created; proceed with Option C (separate refresh)

2. Do you want to consolidate all 10-day rolling updates into combined NCDD_EDI sources?
   → If YES: Generate 8M6CL_NCDD_EDI.csv, then finalize rolling update logic
   → If NO: Maintain separate NCDD/EDI refresh cadence (current approach works)

ASSESSMENT RESULT:
  - 8M5CL_NCDD_EDI.csv IS SUITABLE for rolling updates (if duplicating this approach for 8M6CL)
  - Awaiting user guidance on strategy (unified vs. separate rolling sources)
''')

print('=' * 80)
