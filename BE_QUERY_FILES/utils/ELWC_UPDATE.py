# -*- coding: utf-8 -*-
"""
ELWC Incremental CSV Updater
-----------------------------
Reads the existing COMBINED_ELWC_DEDUPLICATED.csv, determines the most recent
start_date already in it, then queries only the overlap window forward.

OVERLAP_DAYS: how many days before the CSV's max date to re-query.
  - This captures any records that were late-committed to the DB after the last run.
  - 10 days is a conservative buffer; reduce to 5 if you run daily.

Run frequency suggestions:
  - Daily  → OVERLAP_DAYS = 5   (total query ~ 6 days)
  - Weekly → OVERLAP_DAYS = 10  (total query ~17 days)
  - Monthly→ OVERLAP_DAYS = 14  (total query ~45 days)
"""

OVERLAP_DAYS = 10          # days before the CSV max-date to re-query
FALLBACK_DAYS = 30         # days to pull if the CSV is missing or empty

COMBINED_CSV = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\ELWC\COMBINED_ELWC_DEDUPLICATED.csv"

CHAMBERS_LIST = [
    'AME401_PM1', 'AME401_PM2', 'AME401_PM3',
    'AME403_PM1', 'AME403_PM2', 'AME403_PM3', 'AME403_PM4', 'AME403_PM5', 'AME403_PM6',
    'AME409_PM1', 'AME409_PM2', 'AME409_PM3', 'AME409_PM4', 'AME409_PM5', 'AME409_PM6',
    'AME411_PM1', 'AME411_PM2', 'AME411_PM3', 'AME411_PM4',
    'AME417_PM1', 'AME417_PM2', 'AME417_PM3', 'AME417_PM4', 'AME417_PM5', 'AME417_PM6',
    'AME419_PM3', 'AME419_PM4', 'AME419_PM5', 'AME419_PM6',
    'AME421_PM1', 'AME421_PM2', 'AME421_PM3', 'AME421_PM4', 'AME421_PM5', 'AME421_PM6',
    'AME423_PM1', 'AME423_PM2', 'AME423_PM3', 'AME423_PM4', 'AME423_PM5', 'AME423_PM6',
    'AME425_PM1', 'AME425_PM2', 'AME425_PM3', 'AME425_PM4', 'AME425_PM5', 'AME425_PM6',
    'AME427_PM1', 'AME427_PM2', 'AME427_PM3', 'AME427_PM4', 'AME427_PM5', 'AME427_PM6',
]


def update_elwc_csv():
    import os
    import pandas as pd
    import PyUber
    import warnings
    from datetime import datetime, timedelta

    warnings.filterwarnings('ignore')
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)

    print("=" * 65)
    print("  ELWC INCREMENTAL CSV UPDATER")
    print(f"  Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    # ------------------------------------------------------------------
    # 1. Load existing CSV and determine query start date
    # ------------------------------------------------------------------
    existing_df = None
    query_from_dt = datetime.now() - timedelta(days=FALLBACK_DAYS)

    if os.path.exists(COMBINED_CSV):
        print(f"\nLoading existing CSV: {COMBINED_CSV}")
        try:
            existing_df = pd.read_csv(COMBINED_CSV)
            print(f"  Loaded {len(existing_df):,} rows x {len(existing_df.columns)} columns")

            # Find the date column (case-insensitive match)
            date_col = next(
                (c for c in existing_df.columns if c.upper() == 'START_DATE'),
                None
            )
            if date_col:
                existing_df[date_col] = pd.to_datetime(existing_df[date_col], errors='coerce')
                csv_max_date = existing_df[date_col].max()
                query_from_dt = csv_max_date - timedelta(days=OVERLAP_DAYS)
                print(f"  CSV max start_date : {csv_max_date}")
                print(f"  Querying from      : {query_from_dt}  (overlap = {OVERLAP_DAYS} days)")
            else:
                print(f"  WARNING: start_date column not found – falling back to {FALLBACK_DAYS}-day pull")
        except Exception as e:
            print(f"  WARNING: Could not read existing CSV ({e}) – falling back to {FALLBACK_DAYS}-day pull")
            existing_df = None
    else:
        print(f"\nExisting CSV not found – performing {FALLBACK_DAYS}-day fallback pull")

    query_from_str = query_from_dt.strftime('%Y-%m-%d %H:%M:%S')

    # ------------------------------------------------------------------
    # 2. Build and execute the incremental query
    # ------------------------------------------------------------------
    chambers_str = "', '".join(CHAMBERS_LIST)

    print(f"\nQuerying {len(CHAMBERS_LIST)} chambers from {query_from_str} …")

    query = f"""
    /*BEGIN SQL*/
    SELECT
              CASE WHEN  wch.operation  = 8288  THEN '>>'
                   WHEN  wch.operation  = 116398 THEN '[]'
                   WHEN  wch.operation  = 8289   THEN '[]'
                   ELSE '--' END AS WT
             ,wch.wafer           AS wafer
             ,e.entity            AS entity
             ,wch.subentity       AS subentity
             ,wch.lot             AS lot
             ,wch.slot            AS slot
             ,wch.operation       AS oper
             ,To_Char(wch.start_time,'yyyy-mm-dd hh24:mi:ss') AS start_date
             ,wch.state           AS state
             ,lwr.recipe          AS seq_recipe
             ,lrc.oper_short_desc AS oper_short_desc
             ,lwr.recipe          AS wafer_recipe
             ,leh.product         AS lot_product
             ,Replace(Replace(Replace(Replace(Replace(Replace(
                  p.product_description,',',';'),chr(9),' '),chr(10),' '),chr(13),' '),chr(34),''''),chr(7),' ')
                  AS product_description
    FROM  F_LotEntityHist     leh
    INNER JOIN F_WaferChamberHist wch ON leh.runkey = wch.runkey
    INNER JOIN F_Entity           e   ON e.facility NOT IN ('Test','Intel')
                                     AND e.entity = wch.entity
                                     AND e.entity = leh.entity
    INNER JOIN F_Lot_Wafer_Recipe lwr ON lwr.recipe_id = wch.wafer_chamber_recipe_id
    INNER JOIN F_Lot_Run_card     lrc ON lrc.lotoperkey = wch.lotoperkey
    INNER JOIN F_Product          p   ON p.product = lrc.product
                                     AND p.facility = lrc.facility
                                     AND p.latest_version = 'Y'
    WHERE  wch.start_time >= TO_DATE('{query_from_str}', 'YYYY-MM-DD HH24:MI:SS')
      AND  leh.entity  LIKE 'AME%'
      AND  wch.subentity IN ('{chambers_str}')
    ORDER BY wch.subentity, wch.start_time DESC
    /*END SQL*/
    """

    new_df = pd.read_sql(query, PyUber.connect('D1D_PROD_XEUS_LOCAL'))
    print(f"  Retrieved {len(new_df):,} new/overlap records")

    if new_df.empty:
        print("\nNo new records returned – CSV is already up to date.")
        return

    # Normalise column names to match the existing CSV (uppercase → lowercase etc.)
    # Both files use lowercase aliases in the SQL, so this should be consistent.
    new_df.columns = [c.lower() for c in new_df.columns]
    if existing_df is not None:
        existing_df.columns = [c.lower() for c in existing_df.columns]

    # ------------------------------------------------------------------
    # 3. Merge, deduplicate, sort, and save
    # ------------------------------------------------------------------
    print("\nMerging with existing CSV …")
    if existing_df is not None and not existing_df.empty:
        # Align columns (keep only the intersection to be safe)
        common_cols = [c for c in existing_df.columns if c in new_df.columns]
        combined = pd.concat(
            [existing_df[common_cols], new_df[common_cols]],
            ignore_index=True
        )
    else:
        combined = new_df.copy()

    before = len(combined)
    combined = combined.drop_duplicates()
    after  = len(combined)
    print(f"  Rows before dedup : {before:,}")
    print(f"  Duplicates removed: {before - after:,}")
    print(f"  Rows after dedup  : {after:,}")

    # Sort by subentity then start_date descending
    if 'start_date' in combined.columns:
        combined['start_date'] = pd.to_datetime(combined['start_date'], errors='coerce')
        combined = combined.sort_values(['subentity', 'start_date'], ascending=[True, False])
        combined['start_date'] = combined['start_date'].dt.strftime('%Y-%m-%d %H:%M:%S')

    print(f"\nSaving updated CSV → {COMBINED_CSV}")
    combined.to_csv(COMBINED_CSV, index=False)

    file_size_mb = os.path.getsize(COMBINED_CSV) / 1024 ** 2
    print(f"  Saved: {after:,} rows  |  {len(combined.columns)} columns  |  {file_size_mb:.1f} MB")

    # ------------------------------------------------------------------
    # 4. Summary
    # ------------------------------------------------------------------
    if 'start_date' in combined.columns:
        dates = pd.to_datetime(combined['start_date'], errors='coerce')
        print(f"\n  Date range in CSV: {dates.min().date()}  →  {dates.max().date()}")
        print(f"  Total days covered: {(dates.max() - dates.min()).days}")

    print(f"\n  Chambers with data: {combined['subentity'].nunique()} / {len(CHAMBERS_LIST)}")
    print("\nDone.")
    return combined


if __name__ == "__main__":
    update_elwc_csv()
