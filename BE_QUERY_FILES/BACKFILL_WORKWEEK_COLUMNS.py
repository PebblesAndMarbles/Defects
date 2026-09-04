"""
Backfill PERIOD_END and YYYYWW workweek columns into existing production CSVs.

Purpose: Add ISO workweek metadata to 8M5CL_8M6CL_EXTENDED.csv and 60-day variant
so users can filter/query specific wafers for pilot analysis.

Columns added:
- PERIOD_END: End-of-week Sunday date (YYYY-MM-DD format)
- YYYYWW: ISO week identifier (YYWOQ format, e.g., '2607W26')

Execution: One-time backfill after merge fix (2026-07-09)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import shutil
import os

def get_iso_week_info(date):
    """
    Get ISO week information for a given date.
    
    Returns: (year, week, ndays_in_week)
    - year: ISO week year (Thursday's year)
    - week: ISO week number (1-53)
    - ndays_in_week: Number of days from this date to end of ISO week (Sunday)
    """
    iso_year, iso_week, iso_weekday = date.isocalendar()
    days_until_sunday = 7 - iso_weekday
    week_end = date + timedelta(days=days_until_sunday)
    ndays = (week_end - date).days + 1
    return iso_year, iso_week, ndays


def format_yyyyww(iso_year, iso_week):
    """Format ISO year and week as YYYYWW (e.g., '2607W26')"""
    yy = iso_year % 100
    return f"{yy:02d}W{iso_week:02d}"


def backfill_csv(csv_path):
    """
    Load CSV, add PERIOD_END and YYYYWW columns, save with backup.
    
    Args:
        csv_path: Path to production CSV file
    
    Returns:
        dict with status information
    """
    print(f'\n{"=" * 80}')
    print(f'Backfilling: {os.path.basename(csv_path)}')
    print(f'{"=" * 80}')
    
    # Load CSV
    print(f'Loading CSV...')
    df = pd.read_csv(csv_path, low_memory=False)
    original_row_count = len(df)
    print(f'  Rows loaded: {original_row_count}')
    print(f'  Columns before: {len(df.columns)}')
    
    # Check if INSPECT_TIME exists
    if 'INSPECT_TIME' not in df.columns:
        print('  ERROR: INSPECT_TIME column not found!')
        return {'status': 'ERROR', 'reason': 'INSPECT_TIME missing'}
    
    # Check if columns already exist (skip if already present)
    if 'PERIOD_END' in df.columns and 'YYYYWW' in df.columns:
        print('  INFO: PERIOD_END and YYYYWW already present, skipping backfill')
        return {'status': 'SKIPPED', 'reason': 'Columns already exist'}
    
    # Parse INSPECT_TIME to datetime
    print(f'Parsing INSPECT_TIME to datetime...')
    inspect_dt = pd.to_datetime(df['INSPECT_TIME'], errors='coerce')
    print(f'  Valid datetimes: {inspect_dt.notna().sum()} / {len(df)}')
    
    # Derive PERIOD_END (end-of-week Sunday)
    print(f'Deriving PERIOD_END (end-of-week Sunday dates)...')
    def get_period_end(dt):
        if pd.isna(dt):
            return None
        date = dt.date()
        iso_year, iso_week, _ = get_iso_week_info(date)
        iso_weekday = date.isocalendar()[2]
        days_until_sunday = 7 - iso_weekday
        period_end = date + timedelta(days=days_until_sunday)
        return period_end
    
    df['PERIOD_END'] = inspect_dt.apply(get_period_end)
    print(f'  Non-null PERIOD_END: {df["PERIOD_END"].notna().sum()} / {len(df)}')
    
    # Derive YYYYWW (ISO week identifier)
    print(f'Deriving YYYYWW (ISO week format YYWOQ)...')
    def get_yyyyww(dt):
        if pd.isna(dt):
            return None
        date = dt.date()
        iso_year, iso_week, _ = get_iso_week_info(date)
        return format_yyyyww(iso_year, iso_week)
    
    df['YYYYWW'] = inspect_dt.apply(get_yyyyww)
    print(f'  Non-null YYYYWW: {df["YYYYWW"].notna().sum()} / {len(df)}')
    
    # Find insertion point (after YYMM if present, otherwise after first temporal columns)
    if 'YYMM' in df.columns:
        yymm_idx = df.columns.get_loc('YYMM')
        new_order = (list(df.columns[:yymm_idx+1]) + 
                     ['PERIOD_END', 'YYYYWW'] +
                     list(df.columns[yymm_idx+1:]))
    else:
        # If YYMM not present, add after INSPECT_TIME
        if 'INSPECT_TIME' in df.columns:
            inspect_idx = df.columns.get_loc('INSPECT_TIME')
            new_order = (list(df.columns[:inspect_idx+1]) + 
                         ['PERIOD_END', 'YYYYWW'] +
                         list(df.columns[inspect_idx+1:]))
        else:
            # Add at start
            new_order = ['PERIOD_END', 'YYYYWW'] + list(df.columns)
    
    df = df[new_order]
    print(f'  Columns after: {len(df.columns)}')
    print(f'  Columns added: PERIOD_END, YYYYWW')
    
    # Verify no row loss
    if len(df) != original_row_count:
        print(f'  ERROR: Row count mismatch! Before={original_row_count}, After={len(df)}')
        return {'status': 'ERROR', 'reason': 'Row count mismatch'}
    
    # Create backup with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'{csv_path}.backup_{timestamp}'
    print(f'Creating backup: {os.path.basename(backup_path)}')
    shutil.copy2(csv_path, backup_path)
    
    # Save backfilled CSV
    print(f'Saving backfilled CSV...')
    df.to_csv(csv_path, index=False)
    
    # Verify file written
    rows_written = len(pd.read_csv(csv_path, nrows=1, low_memory=False))
    print(f'✓ Backfill complete')
    
    return {
        'status': 'SUCCESS',
        'rows': len(df),
        'period_end_non_null': df['PERIOD_END'].notna().sum(),
        'yyyyww_non_null': df['YYYYWW'].notna().sum(),
        'backup_path': backup_path
    }


def main():
    """Backfill both production CSVs"""
    
    print('\n' + '=' * 80)
    print('WORKWEEK COLUMN BACKFILL')
    print('=' * 80)
    print('Purpose: Add PERIOD_END and YYYYWW columns to production CSVs')
    print('Enables user filtering by workweek for pilot analysis')
    
    # Define CSV paths
    extended_csv = r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED.csv'
    extended_60d_csv = r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer\8M5CL_8M6CL_EXTENDED_60DAY.csv'
    
    results = {}
    
    # Backfill extended
    if os.path.exists(extended_csv):
        results['extended'] = backfill_csv(extended_csv)
    else:
        print(f'ERROR: {extended_csv} not found')
        results['extended'] = {'status': 'ERROR', 'reason': 'File not found'}
    
    # Backfill 60-day
    if os.path.exists(extended_60d_csv):
        results['60day'] = backfill_csv(extended_60d_csv)
    else:
        print(f'ERROR: {extended_60d_csv} not found')
        results['60day'] = {'status': 'ERROR', 'reason': 'File not found'}
    
    # Summary
    print(f'\n' + '=' * 80)
    print('BACKFILL SUMMARY')
    print('=' * 80)
    for name, result in results.items():
        status = result.get('status', 'UNKNOWN')
        print(f'{name:15} {status:12}', end='')
        if status == 'SUCCESS':
            print(f' Rows: {result.get("rows")}')
        elif status == 'SKIPPED':
            print(f' ({result.get("reason")})')
        else:
            print(f' ({result.get("reason")})')
    
    print(f'{"=" * 80}\n')
    
    return results


if __name__ == '__main__':
    main()
