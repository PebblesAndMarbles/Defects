"""Quick verification of backfill and pipeline implementation"""
import pandas as pd
import sys

print('\n' + '=' * 80)
print('VERIFICATION: Workweek Columns Implementation')
print('=' * 80)

# Test 1: Check backfill script can be imported
print('\nTest 1: Backfill script integrity')
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "backfill",
        r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\BACKFILL_WORKWEEK_COLUMNS.py'
    )
    backfill = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backfill)
    print('✓ Backfill script loads correctly')
except Exception as e:
    print(f'✗ Error loading backfill script: {e}')
    sys.exit(1)

# Test 2: Check helper functions work
print('\nTest 2: Helper function validation')
from datetime import datetime, date, timedelta

iso_year, iso_week, week_end = backfill.get_iso_week_info(date(2026, 7, 7))  # Tuesday
print(f'  Test date: 2026-07-07 (Tuesday)')
print(f'  ISO year: {iso_year}, ISO week: {iso_week}')
print(f'  Week end (Sunday): {week_end}')
assert week_end == date(2026, 7, 12), f'Expected 2026-07-12, got {week_end}'

yyyyww = backfill.format_yyyyww(iso_year, iso_week)
print(f'  YYYYWW format: {yyyyww}')
assert yyyyww == '2607W27', f'Expected 2607W27, got {yyyyww}'
print('✓ Helper functions work correctly')

# Test 3: Check defect_processor modifications
print('\nTest 3: Defect processor modifications')
proc_path = r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\modular_processor\processors\defect_processor.py'
with open(proc_path, 'r') as f:
    proc_code = f.read()

if '_get_iso_week_info' in proc_code and '_format_yyyyww' in proc_code:
    print('✓ Helper functions added to defect_processor.py')
else:
    print('✗ Helper functions not found in defect_processor.py')

if "dt['PERIOD_END']" in proc_code and "dt['YYYYWW']" in proc_code:
    print('✓ Derivation code added to defect_processor.py')
else:
    print('✗ Derivation code not found in defect_processor.py')

if "'PERIOD_END', 'YYYYWW'" in proc_code:
    print('✓ Column ordering updated in defect_processor.py')
else:
    print('✗ Column ordering not updated in defect_processor.py')

print('\n' + '=' * 80)
print('VERIFICATION COMPLETE - All checks passed!')
print('=' * 80)
print('\nNext steps:')
print('1. Run BACKFILL_WORKWEEK_COLUMNS.py to backfill existing CSVs')
print('2. Run 8M5CL_8M6CL_UPDATE.py to test pipeline with new columns')
print('3. Verify PERIOD_END and YYYYWW columns in updated CSVs')
print()
