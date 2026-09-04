"""
Backfill selected source metadata columns into DEFECT_COORDINATES_EXTENDED.csv.

This script adds the current retained metadata set used as candidate inputs
for downstream VLM analysis:
    - SIZE_X, SIZE_Y, SIZE_D, AREA
    - MANUAL_OPTICAL_CLASS

It does not restore deprecated production columns such as SIZE_Z or
ROUGH_BIN_CLASS.

Process:
  1. Load existing DEFECT_COORDINATES_EXTENDED.csv
  2. Extract unique (WAFER_KEY, INSPECTION_TIME, DEFECT_ID) tuples
  3. Query UDB.INSP_DEFECT for metadata columns (in chunks)
  4. Left-join results back onto existing CSV
  5. Validate row count unchanged
  6. Write updated CSV with new columns populated

Column mappings:
    - SIZE_X, SIZE_Y, SIZE_D, AREA, MANUAL_OPTICAL_CLASS

Columns already in production CSV but may be sparse/null:
    - SIZE_X, SIZE_Y, SIZE_D, AREA (will be populated by backfill)
"""

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import PyUber

CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))

from pipeline_config import PIPELINE_PATHS

DATABASE = "D1D_PROD_YAS_1278"

# Configuration
DEFECT_CHUNK_SIZE = 500  # Max defects per database query
BACKFILL_DRY_RUN = False  # Set to True to test without writing


def _connect(database):
    """Open a PyUber connection with a clear diagnostic on failure."""
    try:
        return PyUber.connect(database)
    except Exception as exc:
        print(
            f"ERROR: Failed to connect to database '{database}': {exc}\n"
            "Check network connectivity, VPN, and that PyUber is configured correctly."
        )
        raise


def _fetch_metadata_for_defects(conn, defect_tuples):
    """
    Query UDB.INSP_DEFECT for metadata columns given list of
    (WAFER_KEY int, INSPECTION_TIME datetime, DEFECT_ID int) tuples.

    Returns a DataFrame with columns:
        WAFER_KEY, INSPECTION_TIME, DEFECT_ID,
        SIZE_X, SIZE_Y, SIZE_D, AREA, MANUAL_OPTICAL_CLASS
    """
    if not defect_tuples:
        return pd.DataFrame()

    all_chunks = []

    for i in range(0, len(defect_tuples), DEFECT_CHUNK_SIZE):
        chunk = defect_tuples[i : i + DEFECT_CHUNK_SIZE]

        # Build value list for WHERE IN clause
        def _format_tuple(k, t, d):
            t_str = t.strftime("%Y%m%d%H%M%S")
            return f"({k}, TO_DATE('{t_str}','YYYYMMDDHH24MISS'), {d})"
        
        rows = ",\n".join(_format_tuple(k, t, d) for k, t, d in chunk)

        sql = f"""
SELECT
    d.WAFER_KEY,
    d.INSPECTION_TIME,
    TO_CHAR(d.DEFECT_ID)                AS DEFECT_ID,
    TO_CHAR(d.SIZE_X)                   AS SIZE_X,
    TO_CHAR(d.SIZE_Y)                   AS SIZE_Y,
    TO_CHAR(d.SIZE_D)                   AS SIZE_D,
    TO_CHAR(d.AREA)                     AS AREA,
    TO_CHAR(d.MANUAL_OPTICAL_CLASS)     AS MANUAL_OPTICAL_CLASS
FROM UDB.INSP_DEFECT d
WHERE (d.WAFER_KEY, d.INSPECTION_TIME, d.DEFECT_ID) IN (
{rows}
)
"""
        print(
            f"  [INSP_DEFECT metadata] chunk {i // DEFECT_CHUNK_SIZE + 1}: "
            f"{len(chunk)} defect records..."
        )
        chunk_df = pd.read_sql(sql, conn)
        print(f"    -> {len(chunk_df)} rows fetched")
        all_chunks.append(chunk_df)

    if not all_chunks:
        return pd.DataFrame()
    return pd.concat(all_chunks, ignore_index=True)


def backfill_vlm_metadata():
    """Main backfill process."""
    print("=" * 80)
    print("SOURCE METADATA BACKFILL")
    print("=" * 80)

    # Load existing CSV
    csv_path = PIPELINE_PATHS.defect_coordinates_csv
    print(f"\n1. Loading existing CSV: {csv_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df_existing = pd.read_csv(csv_path, low_memory=False)
    original_row_count = len(df_existing)
    print(f"   Loaded {original_row_count} rows, {len(df_existing.columns)} columns")

    # Check for required columns
    required = {"WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"}
    missing = required - set(df_existing.columns)
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    # Extract unique defect tuples
    print(f"\n2. Extracting unique defect keys...")
    df_working = df_existing.copy()
    df_working["INSPECTION_TIME"] = pd.to_datetime(df_working["INSPECTION_TIME"], errors="coerce")
    df_working["DEFECT_ID"] = pd.to_numeric(df_working["DEFECT_ID"], errors="coerce")

    unique_tuples = df_working[["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"]].drop_duplicates()
    unique_tuples = [
        (int(row["WAFER_KEY"]), row["INSPECTION_TIME"], int(row["DEFECT_ID"]))
        for _, row in unique_tuples.iterrows()
        if pd.notna(row["WAFER_KEY"]) and pd.notna(row["INSPECTION_TIME"]) and pd.notna(row["DEFECT_ID"])
    ]
    print(f"   Found {len(unique_tuples)} unique (WAFER_KEY, INSPECTION_TIME, DEFECT_ID) tuples")

    # Query database
    print(f"\n3. Querying database for metadata columns...")
    conn = _connect(DATABASE)
    try:
        df_metadata = _fetch_metadata_for_defects(conn, unique_tuples)
    finally:
        conn.close()

    if df_metadata.empty:
        print("   WARNING: No metadata records returned from database")
        return

    print(f"   Retrieved metadata for {len(df_metadata)} defect records")

    # Convert keys to match existing CSV
    df_metadata["WAFER_KEY"] = df_metadata["WAFER_KEY"].astype(int)
    df_metadata["INSPECTION_TIME"] = pd.to_datetime(df_metadata["INSPECTION_TIME"], errors="coerce")
    df_metadata["DEFECT_ID"] = df_metadata["DEFECT_ID"].astype(int)

    # Left-join metadata onto existing CSV
    print(f"\n4. Merging metadata onto existing CSV...")
    df_result = df_existing.copy()
    df_result["INSPECTION_TIME"] = pd.to_datetime(df_result["INSPECTION_TIME"], errors="coerce")
    df_result["DEFECT_ID"] = pd.to_numeric(df_result["DEFECT_ID"], errors="coerce")
    df_result["WAFER_KEY"] = pd.to_numeric(df_result["WAFER_KEY"], errors="coerce").astype(int)

    # Merge on the three-key tuple
    df_result = df_result.merge(
        df_metadata,
        on=["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"],
        how="left",
        suffixes=("", "_NEW"),
    )

    # For columns that exist in both, take the new values if not null, else keep original
    new_cols = ["SIZE_X", "SIZE_Y", "SIZE_D", "AREA", "MANUAL_OPTICAL_CLASS"]
    for col in new_cols:
        if f"{col}_NEW" in df_result.columns:
            df_result[col] = df_result[f"{col}_NEW"].fillna(df_result[col])
            df_result = df_result.drop(columns=[f"{col}_NEW"])
        elif col not in df_result.columns:
            df_result[col] = df_metadata.get(col, pd.Series(dtype="object"))

    # Validate
    print(f"\n5. Validating backfill...")
    if len(df_result) != original_row_count:
        raise ValueError(
            f"Row count mismatch: original={original_row_count}, "
            f"after merge={len(df_result)}"
        )
    print(f"   ✓ Row count preserved: {len(df_result)}")

    # Count populated cells per new column
    print(f"\n6. Metadata population statistics:")
    for col in new_cols:
        if col in df_result.columns:
            non_null = df_result[col].notna().sum()
            pct = (non_null / len(df_result)) * 100 if len(df_result) > 0 else 0
            print(f"   {col:30s} {non_null:6d} / {len(df_result):6d} ({pct:5.1f}%)")

    # Write output
    if BACKFILL_DRY_RUN:
        print(f"\n7. DRY RUN: No changes written (BACKFILL_DRY_RUN=True)")
        print(f"   Would write to: {csv_path}")
    else:
        print(f"\n7. Writing updated CSV...")
        df_result.to_csv(csv_path, index=False)
        print(f"   ✓ Wrote {len(df_result)} rows to {csv_path}")

    print(f"\n{datetime.now().isoformat()} - BACKFILL COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    backfill_vlm_metadata()
