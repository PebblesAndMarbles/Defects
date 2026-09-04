"""
query_by_class_direct.py
------------------------
Query COORDINATES database directly by defect CLASS without requiring input CSV.

No input wafers needed — queries all defects matching:
  - CLASS name (e.g., 'OTHER_UNKNOWN')
  - LAYER (e.g., 8M5CL, 8M6CL)
  - ADDER = 1
  - Lookback window (e.g., 180 days)

Usage:
  python query_by_class_direct.py --class OTHER_UNKNOWN [--layers 8M5CL 8M6CL] [--days 180] [--output-dir <dir>]

Example:
  python query_by_class_direct.py --class OTHER_UNKNOWN --layers 8M5CL 8M6CL --days 180 --output-dir rollups/OTHER_UNKNOWN/direct_query
"""

import argparse
import sys
import os
import gc
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import PyUber

from DEFECT_COORDINATES_QUERY import (
    _connect,
    _sanitize_identifier,
    _normalize_coordinate_schema,
    DEFECT_CHUNK_SIZE,
)

# ============================================================================
# CONFIGURATION
# ============================================================================

DATABASE = "D1D_PROD_YAS_1278"
ANNOTATE_IMAGES = True


def query_coordinates_by_class(class_name, layers=None, lookback_days=180, output_dir=None):
    """
    Query INSP_DEFECT coordinates for all defects of a given CLASS name.
    
    Parameters
    ----------
    class_name : str
        Defect class to query (e.g., 'OTHER_UNKNOWN')
    layers : list of str or None
        Layer filters (e.g., ['8M5CL', '8M6CL']). If None, queries all layers.
    lookback_days : int
        How many days back to look from today
    output_dir : str
        Directory for outputs. If None, uses current dir.
    
    Returns
    -------
    DataFrame with coordinates or None if no results
    """
    
    if output_dir is None:
        output_dir = "outputs/CLASS_QUERY"
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    coords_csv = str(output_path / f"{class_name}_COORDINATES.csv")
    
    print(f"\n{'='*70}")
    print(f"QUERY BY CLASS (Direct Database Query)")
    print(f"{'='*70}")
    print(f"Class:           {class_name}")
    print(f"Layers:          {layers if layers else 'ALL'}")
    print(f"Lookback days:   {lookback_days}")
    print(f"Output CSV:      {coords_csv}")
    print(f"Database:        {DATABASE}")
    print(f"{'='*70}\n")
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)
    start_str = start_date.strftime("%Y%m%d%H%M%S")
    end_str = end_date.strftime("%Y%m%d%H%M%S")
    
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print()
    
    # Build layer filter for SQL
    layer_sql_filter = ""
    if layers:
        quoted = ", ".join(f"'{_sanitize_identifier(l)}'" for l in layers)
        layer_sql_filter = f"  AND s.LAYER_ID IN ({quoted})"
    
    # Build class filter for SQL
    class_sql_filter = f"  AND c.NAME = '{_sanitize_identifier(class_name)}'"
    
    # Query coordinates using date range (no need to pass wafers)
    sql = f"""
SELECT
    s.WAFER_KEY,
    s.INSPECTION_TIME,
    s.SCRIBE_ID                                       AS WAFER_ID,
    SUBSTR(s.LOT_ID, 1, 7)                            AS LOT7,
    s.LOT_ID                                          AS ACTUAL_LOT,
    s.LAYER_ID                                        AS LAYER,
    TO_CHAR(d.DEFECT_ID)                              AS DEFECT_ID,
    c.NAME                                            AS CLASS,
    f.NAME                                            AS FINEBIN,
    TO_CHAR((d.WAFER_X - s.CENTER_X) / 1000000.0)    AS WAFER_X_MM,
    TO_CHAR((d.WAFER_Y - s.CENTER_Y) / 1000000.0)    AS WAFER_Y_MM,
    TO_CHAR(d.IMAGES)                                 AS IMAGE_COUNT,
    TO_CHAR(d.SIZE_X)                                 AS SIZE_X,
    TO_CHAR(d.SIZE_Y)                                 AS SIZE_Y,
    TO_CHAR(d.SIZE_D)                                 AS SIZE_D,
    TO_CHAR(d.AREA)                                   AS AREA,
    TO_CHAR(d.MANUAL_OPTICAL_CLASS)                   AS MANUAL_OPTICAL_CLASS
FROM UDB.INSP_WAFER_SUMMARY s
INNER JOIN UDB.INSP_DEFECT d
    ON  d.WAFER_KEY       = s.WAFER_KEY
    AND d.INSPECTION_TIME = s.INSPECTION_TIME
    AND d.ADDER           = 1
LEFT JOIN udb.CLASS c
    ON  c.CLASS_ID = d.CLASS_NUMBER
LEFT JOIN udb.FINEBIN f
    ON  f.FINEBIN_ID = d.AUTOMATED_OPTICAL_CLASS
WHERE s.INSPECTION_TIME >= TO_DATE('{start_str}', 'YYYYMMDDHH24MISS')
  AND s.INSPECTION_TIME <= TO_DATE('{end_str}', 'YYYYMMDDHH24MISS'){layer_sql_filter}{class_sql_filter}
ORDER BY s.INSPECTION_TIME DESC, s.WAFER_KEY, d.DEFECT_ID
"""
    
    print("Querying INSP_DEFECT for all OTHER_UNKNOWN defects...")
    print()
    
    conn = _connect(DATABASE)
    try:
        defects_df = pd.read_sql(sql, conn)
    finally:
        conn.close()
        del conn
        gc.collect()
    
    if defects_df.empty:
        print(f"No {class_name} defect records found in the database.")
        print(f"Checked: {layers if layers else 'all layers'}, {lookback_days}-day lookback")
        return None
    
    # Clean up numeric columns
    for col in ("WAFER_X_MM", "WAFER_Y_MM", "SIZE_X", "SIZE_Y", "SIZE_D", "AREA"):
        defects_df[col] = pd.to_numeric(defects_df[col], errors="coerce")
    
    print(f"Found {len(defects_df)} {class_name} defect records")
    print()
    
    # Show summary
    print("Summary by Layer:")
    print(defects_df['LAYER'].value_counts())
    print()
    
    print("Summary by Lot:")
    print(defects_df.groupby(['LOT7', 'LAYER']).size())
    print()
    
    # Save coordinates
    defects_df = _normalize_coordinate_schema(defects_df)
    defects_df.to_csv(coords_csv, index=False)
    
    print(f"Saved {len(defects_df)} coordinate records -> {coords_csv}")
    print()
    
    print("Sample output (first 10 records):")
    print(defects_df[['LOT7', 'WAFER_ID', 'LAYER', 'DEFECT_ID', 'CLASS', 'WAFER_X_MM', 'WAFER_Y_MM', 'IMAGE_COUNT']].head(10))
    
    print(f"\n{'='*70}")
    print(f"Coordinates query complete. Results saved to: {output_dir}")
    print(f"{'='*70}\n")
    
    return defects_df


def main():
    parser = argparse.ArgumentParser(description="Query defect coordinates by CLASS directly")
    parser.add_argument("--class", dest="class_name", required=True, help="Defect class (e.g., OTHER_UNKNOWN)")
    parser.add_argument("--layers", nargs="+", default=None, help="Layer(s) to query (e.g., 8M5CL 8M6CL)")
    parser.add_argument("--days", type=int, default=180, help="Lookback window in days (default: 180)")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: outputs/CLASS_QUERY)")
    
    args = parser.parse_args()
    
    query_coordinates_by_class(
        class_name=args.class_name,
        layers=args.layers,
        lookback_days=args.days,
        output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
