"""
WEEKLY_ZERO_RATE_AGGREGATOR.py
==============================
Lightweight aggregator for weekly ZERO_RATE metrics from production CSV.

Features:
- No sample-size filtering (includes all devices)
- ISO weeks (Sunday start)
- Device="ALL" rows for fleet-wide aggregation
- Outputs: Timestamped archive + stable CURRENT file (with file-lock protection)
- Columns: PERIOD_END, YYYYWW, LAYER, DEVICE, SAMPLE_SIZE, 
           BEEP_RATE, BEEP_ZERO_RATE, SMP_RATE, SMP_ZERO_RATE, NDays

Usage:
    python WEEKLY_ZERO_RATE_AGGREGATOR.py <input_csv> <output_dir>

Or from pipeline (conditional on Sunday):
    python WEEKLY_ZERO_RATE_AGGREGATOR.py \
        "\\path\\to\\8M5CL_8M6CL_EXTENDED.csv" \
        "\\path\\to\\outputs\\benchmarks"
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging
import time
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_sunday():
    """Check if today is Sunday (first day of new week)"""
    today = datetime.now()
    # weekday() returns 0-6 where Monday=0, Sunday=6
    return today.weekday() == 6


def get_iso_week_info(date):
    """
    Get ISO week information for a given date.
    
    Returns: (year, week, ndays_in_week)
    - year: ISO week year (Thursday's year)
    - week: ISO week number (1-53)
    - ndays_in_week: Number of days from this date to end of ISO week (Sunday)
    """
    # ISO calendar: week belongs to year of Thursday in that week
    iso_year, iso_week, iso_weekday = date.isocalendar()
    
    # Calculate end of week (Sunday, which is ISO day 7)
    days_until_sunday = 7 - iso_weekday  # 0 days if already Sunday, 6 if Monday
    week_end = date + timedelta(days=days_until_sunday)
    
    # NDays = days from current date through end of week (inclusive)
    ndays = (week_end - date).days + 1
    
    return iso_year, iso_week, ndays


def format_yyyyww(iso_year, iso_week):
    """Format ISO year and week as YYYYWW (e.g., '2607W26')"""
    # iso_year is 4-digit, reduce to 2-digit year
    yy = iso_year % 100
    return f"{yy:02d}W{iso_week:02d}"


def load_production_csv(csv_path):
    """Load production CSV with proper type handling"""
    logger.info(f"Loading production CSV: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)
    
    # Parse INSPECT_TIME to datetime
    df['INSPECT_TIME'] = pd.to_datetime(df['INSPECT_TIME'], errors='coerce')
    
    logger.info(f"Loaded {len(df):,} rows from {len(df.columns)} columns")
    logger.info(f"Date range: {df['INSPECT_TIME'].min()} to {df['INSPECT_TIME'].max()}")
    
    return df


def aggregate_weekly_metrics(df):
    """
    Aggregate data by LAYER + DEVICE + ISO WEEK.
    
    Returns DataFrame with weekly zero-rate metrics (no min_samples filtering).
    """
    logger.info("Aggregating weekly metrics by LAYER + DEVICE + WEEK...")
    
    results = []
    
    # Get unique layer-device combinations
    layer_device_combos = df[['LAYER', 'DEVICE']].drop_duplicates()
    logger.info(f"Processing {len(layer_device_combos):,} LAYER-DEVICE combinations")
    
    for _, combo in layer_device_combos.iterrows():
        layer = combo['LAYER']
        device = combo['DEVICE']
        
        # Filter for this device-layer
        group_df = df[(df['LAYER'] == layer) & (df['DEVICE'] == device)].copy()
        
        if len(group_df) == 0:
            continue
        
        # Group by ISO week
        for (iso_year, iso_week), week_data in group_df.groupby(
            group_df['INSPECT_TIME'].dt.isocalendar()[['year', 'week']].apply(tuple, axis=1)
        ):
            if len(week_data) == 0:
                continue
            
            # Get week end date and NDays
            first_date = week_data['INSPECT_TIME'].min().date()
            week_end = week_data['INSPECT_TIME'].max().date()
            iso_yy, iso_ww, ndays = get_iso_week_info(first_date)
            yyyyww = format_yyyyww(iso_yy, iso_ww)
            
            # Calculate rates
            sample_size = len(week_data)
            
            # BEEP_RATE: defective wafers / total wafers
            beep_total = week_data['BEEP_NCDD'].notna().sum()
            beep_defective = (week_data['ZERO_BEEP'] == False).sum() if 'ZERO_BEEP' in week_data.columns else 0
            beep_rate = beep_defective / beep_total if beep_total > 0 else np.nan
            
            # SMP_RATE: defective wafers / total wafers
            smp_total = week_data['SMP_NCDD'].notna().sum()
            smp_defective = (week_data['ZERO_SMP'] == False).sum() if 'ZERO_SMP' in week_data.columns else 0
            smp_rate = smp_defective / smp_total if smp_total > 0 else np.nan
            
            row = {
                'PERIOD_END': week_end,
                'YYYYWW': yyyyww,
                'LAYER': layer,
                'DEVICE': device,
                'SAMPLE_SIZE': sample_size,
                'BEEP_RATE': beep_rate,
                'BEEP_ZERO_RATE': 1 - beep_rate if not np.isnan(beep_rate) else np.nan,
                'SMP_RATE': smp_rate,
                'SMP_ZERO_RATE': 1 - smp_rate if not np.isnan(smp_rate) else np.nan,
                'NDays': ndays
            }
            results.append(row)
    
    result_df = pd.DataFrame(results)
    logger.info(f"Created {len(result_df):,} device-week aggregations")
    return result_df


def create_fleet_all_rows(device_df):
    """
    Create DEVICE="ALL" rows for fleet-wide aggregation by LAYER + WEEK.
    """
    logger.info("Creating DEVICE='ALL' fleet-wide aggregation rows...")
    
    all_rows = []
    
    # Group by LAYER + YYYYWW
    for (layer, yyyyww), group_data in device_df.groupby(['LAYER', 'YYYYWW']):
        
        # Aggregate across all devices in this layer-week
        period_end = group_data['PERIOD_END'].iloc[0]  # Same for all devices in week
        ndays = group_data['NDays'].iloc[0]
        sample_size = group_data['SAMPLE_SIZE'].sum()
        
        # Recalculate rates from original data across all devices
        # (rates from device rows can't be averaged directly; must recalc from wafer counts)
        total_beep_defective = (group_data['BEEP_RATE'] * group_data['SAMPLE_SIZE']).sum()
        total_smp_defective = (group_data['SMP_RATE'] * group_data['SAMPLE_SIZE']).sum()
        
        beep_rate = total_beep_defective / sample_size if sample_size > 0 else np.nan
        smp_rate = total_smp_defective / sample_size if sample_size > 0 else np.nan
        
        row = {
            'PERIOD_END': period_end,
            'YYYYWW': yyyyww,
            'LAYER': layer,
            'DEVICE': 'ALL',
            'SAMPLE_SIZE': sample_size,
            'BEEP_RATE': beep_rate,
            'BEEP_ZERO_RATE': 1 - beep_rate if not np.isnan(beep_rate) else np.nan,
            'SMP_RATE': smp_rate,
            'SMP_ZERO_RATE': 1 - smp_rate if not np.isnan(smp_rate) else np.nan,
            'NDays': ndays
        }
        all_rows.append(row)
    
    all_df = pd.DataFrame(all_rows)
    logger.info(f"Created {len(all_df):,} DEVICE='ALL' aggregations")
    
    # Combine device rows + ALL rows
    combined = pd.concat([device_df, all_df], ignore_index=True)
    combined = combined.sort_values(['LAYER', 'YYYYWW', 'DEVICE'])
    
    return combined


def write_with_retry(df, output_path, max_retries=5):
    """
    Write CSV with retry logic for file-lock protection.
    
    Args:
        df: DataFrame to write
        output_path: Path where file should be written
        max_retries: Maximum retry attempts (default 5)
    
    Returns:
        bool: True if write succeeded, False if all retries failed
    """
    output_path = Path(output_path)
    
    for attempt in range(1, max_retries + 1):
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_path, index=False)
            logger.info(f"Successfully wrote {len(df):,} rows to {output_path}")
            return True
        except PermissionError as e:
            if attempt < max_retries:
                wait_time = attempt  # 1, 2, 3, 4, 5 seconds
                logger.warning(
                    f"File {output_path} is locked (attempt {attempt}/{max_retries}). "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(
                    f"Failed to write {output_path} after {max_retries} retries. "
                    f"File may be open in another application. Skipping CURRENT file update."
                )
                return False
        except Exception as e:
            logger.error(f"Error writing to {output_path}: {e}")
            return False
    
    return False


def generate_timestamped_filename(output_dir):
    """Generate timestamped filename: YYYYMMDD_HHMM_8M5CL_8M6CL_ZERO_RATES.csv"""
    now = datetime.now()
    return f"{now.strftime('%Y%m%d_%H%M')}_8M5CL_8M6CL_ZERO_RATES.csv"


def main(input_csv, output_dir, force_execute=False):
    """Main execution function"""
    
    logger.info("=" * 80)
    logger.info("WEEKLY ZERO-RATE AGGREGATOR")
    logger.info("=" * 80)
    
    # Check if Sunday (unless forced)
    if not force_execute and not is_sunday():
        today = datetime.now().strftime('%A')
        logger.info(f"Today is {today} (not Sunday). Skipping aggregation.")
        logger.info("Aggregation runs only on Sundays to ensure complete week data.")
        return
    
    logger.info("Today is Sunday - proceeding with aggregation")
    
    # Load data
    try:
        df = load_production_csv(input_csv)
    except Exception as e:
        logger.error(f"Failed to load production CSV: {e}")
        sys.exit(1)
    
    # Aggregate metrics
    try:
        device_metrics = aggregate_weekly_metrics(df)
    except Exception as e:
        logger.error(f"Failed to aggregate weekly metrics: {e}")
        sys.exit(1)
    
    # Create fleet-wide aggregations
    try:
        final_metrics = create_fleet_all_rows(device_metrics)
    except Exception as e:
        logger.error(f"Failed to create fleet aggregations: {e}")
        sys.exit(1)
    
    # Write outputs
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Timestamped archive
        timestamped_filename = generate_timestamped_filename(output_dir)
        timestamped_path = output_dir / timestamped_filename
        write_with_retry(final_metrics, timestamped_path)
        
        # Stable CURRENT file (with retry protection)
        current_path = output_dir / "8M5CL_8M6CL_ZERO_RATES_CURRENT.csv"
        success = write_with_retry(final_metrics, current_path, max_retries=5)
        
        if success:
            logger.info(f"CURRENT file updated: {current_path}")
        else:
            logger.warning(f"CURRENT file update failed (file may be open). Archive created: {timestamped_path}")
        
    except Exception as e:
        logger.error(f"Failed to write output files: {e}")
        sys.exit(1)
    
    logger.info("=" * 80)
    logger.info(f"AGGREGATION COMPLETE - {len(final_metrics):,} weekly metric rows created")
    logger.info("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python WEEKLY_ZERO_RATE_AGGREGATOR.py <input_csv> <output_dir> [--force]")
        print()
        print("Options:")
        print("  --force   Force execution even if not Sunday (for testing)")
        print()
        print("Example:")
        print('  python WEEKLY_ZERO_RATE_AGGREGATOR.py \\')
        print('    "\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Defects\\BE\\outputs\\wafer\\8M5CL_8M6CL_EXTENDED.csv" \\')
        print('    "\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Defects\\BE\\outputs\\benchmarks"')
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_dir = sys.argv[2]
    force_execute = "--force" in sys.argv
    
    if force_execute:
        logger.info("Force execution mode enabled (bypassing Sunday check)")
    
    main(input_csv, output_dir, force_execute=force_execute)
