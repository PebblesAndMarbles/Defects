"""
surf_scan_coordinates.py
------------------------
Queries UDB (D1D_PROD_YAS_1278) for individual adder-defect X/Y coordinates
for SURFSCAN (SS) and SEGMENTATION (SEG) test wafers.

Flow:
  1. Query INSP_WAFER_SUMMARY WHERE
       PROCESS_EQUIP_ID IN (...)              -- etch chamber ('Pri Eqp' in UDB UI)
       LAYER_ID         IN ('6BARE_L029_PST') -- PST scan only
       INSPECTION_TIME  >= SYSDATE - LOOKBACK_DAYS
     PROCESS_EQUIP_ID + LAYER_ID is highly selective; no SCRIBE_ID filter needed.
  2. Query INSP_DEFECT for the resolved (INSPECTION_TIME, WAFER_KEY) pairs.
  3. Join wafer-run context (N_WAFERS_IN_RUN, EVENT, STATUS, etc.) and save to
      the current BE surf-scan outputs.

Database:  D1D_PROD_YAS_1278  (PyUber)
"""

import gc
import warnings
import PyUber
import pandas as pd
import numpy as np

from pipeline_config import PIPELINE_PATHS
from surf_scan_config import (
    DATABASE_NAME as CFG_DATABASE_NAME,
    DEFAULT_CLASS_FILTER as CFG_DEFAULT_CLASS_FILTER,
    DEFAULT_FETCH_EDX as CFG_DEFAULT_FETCH_EDX,
    DEFAULT_FETCH_SEG as CFG_DEFAULT_FETCH_SEG,
    DEFAULT_LOT_FILTER as CFG_DEFAULT_LOT_FILTER,
    DEFAULT_PRIMARY_EQUIP_FILTER as CFG_DEFAULT_PRIMARY_EQUIP_FILTER,
    DEFAULT_SEED_LOOKBACK_DAYS as CFG_DEFAULT_SEED_LOOKBACK_DAYS,
    DEFECT_CHUNK_SIZE as CFG_DEFECT_CHUNK_SIZE,
    EDX_CHUNK_SIZE as CFG_EDX_CHUNK_SIZE,
    SEG_LAYER_FILTER as CFG_SEG_LAYER_FILTER,
    SEG_RECIPE_SEQUENCE as CFG_SEG_RECIPE_SEQUENCE,
    SEG_WAFERS_PER_RECIPE as CFG_SEG_WAFERS_PER_RECIPE,
    SS_LAYER_FILTER as CFG_SS_LAYER_FILTER,
    SS_RUN_GAP_HOURS as CFG_SS_RUN_GAP_HOURS,
    SURF_SUBENTITY_FILTER as CFG_SURF_SUBENTITY_FILTER,
)

# Suppress pandas warning about non-SQLAlchemy connectables (PyUber is a
# validated DBAPI2 connection; the warning is informational only).
warnings.filterwarnings(
    "ignore",
    message=".*SQLAlchemy.*",
    category=UserWarning,
)

# ---------------------------------------------------------------------------
# CONFIGURATION  -- edit these for each test run
# ---------------------------------------------------------------------------
# Run modes:
#   Backfill (one-time, extended history): LOOKBACK_DAYS = 730, INCREMENTAL_UPDATE = False
#   Scheduled (regular cadence):           LOOKBACK_DAYS = 7,   INCREMENTAL_UPDATE = True
# ---------------------------------------------------------------------------

OUTPUT_CSV = str(PIPELINE_PATHS.surf_coordinates_csv)

METRICS_OUTPUT_CSV = str(PIPELINE_PATHS.surf_metrics_csv)

EDX_OUTPUT_CSV = str(PIPELINE_PATHS.surf_edx_csv)

DATABASE = CFG_DATABASE_NAME
COUNTER_DATABASE = "D1D_PROD_XEUS_GAJT"

# When True, the script merges new results into an existing OUTPUT_CSV rather
# than overwriting it.  Rows in the existing file whose INSPECTION_TIME falls
# within the current lookback window are replaced; older rows are preserved.
# Set False for a full overwrite (e.g. initial backfill).
INCREMENTAL_UPDATE = False

# Legacy nearest-time PM enrichment toggle.
# Keep True for explicit diagnostics, but orchestrated production runs should
# disable this and rely on ELWC stage/apply RF refresh.
ENABLE_LEGACY_NEAREST_PM_ENRICHMENT = True

# --- Optional filters (set to None to disable) ---

# Filter to specific chamber subentities -- default source for PRIMARY_EQUIP_FILTER below.
# Uncomment the full list below to run across all AME chambers at once.
# SUBENTITY_FILTER = ['AME419_PM6']
SUBENTITY_FILTER = CFG_SURF_SUBENTITY_FILTER

# Filter to specific lot IDs (full lot, not LOT7).  e.g. ['D307THPV1'] or None
LOT_FILTER = CFG_DEFAULT_LOT_FILTER

# Only POST scans are retrieved.  '6BARE_L029_PST' is the confirmed PST
# layer ID across all AME chambers and both SS seq_recipes.  Set to None
# to fall back to the wildcard '%_PST' filter.
SS_LAYER_FILTER = CFG_SS_LAYER_FILTER

# Primary equipment filter -- the 'Pri Eqp' / PROCESS_EQUIP_ID column in UDB.
# This is the etch chamber that processed the wafer, NOT the inspection scanner.
# Defaults to SUBENTITY_FILTER when None.
PRIMARY_EQUIP_FILTER = CFG_DEFAULT_PRIMARY_EQUIP_FILTER   # None -> use SUBENTITY_FILTER

# The INSP_WAFER_SUMMARY column that holds the etch chamber ID.
# Confirmed via ALL_TAB_COLUMNS on D1D_PROD_YAS_1278: PROCESS_EQUIP_ID.
CHAMBER_COL = 'PROCESS_EQUIP_ID'

# How many days back from today to search for PST inspections.
# Backfill: 760.  Scheduled cadence: 7.  Set to None for no date restriction
# (not recommended -- test wafers have multi-year global history).
LOOKBACK_DAYS = CFG_DEFAULT_SEED_LOOKBACK_DAYS

# Optional upper bound for backfill window.
# When set (e.g. 90), only rows older than SYSDATE - 90 are queried.
UPPER_BOUND_DAYS = None

# Filter defect CLASS names in the INSP_DEFECT query.
# Set to None on first runs to return all classes.
CLASS_FILTER = CFG_DEFAULT_CLASS_FILTER

# When True, query UDB.INSP_ELEMENT for EDX elemental data on all defects
# where IMAGE_COUNT > 0, and save results to EDX_OUTPUT_CSV.
# Mirrors the GAJT EDXQuery plugin pattern (SELECT e.* ... WHERE WAFER_KEY=...
# AND INSPECTION_TIME=... AND DEFECT_ID IN (...)).
FETCH_EDX = CFG_DEFAULT_FETCH_EDX

# When True, query INSP_WAFER_SUMMARY for MAMEBARE_L029_PST segmentation wafers
# and assign SEG_RECIPE to each wafer based on WAFER_NUM rank order within each
# (INSPECTION_TIME, PRIMARY_EQUIP) group (21 wafers per event, 3 per recipe).
FETCH_SEG = CFG_DEFAULT_FETCH_SEG

# Layer ID for segmentation PST scans.
SEG_LAYER_FILTER = CFG_SEG_LAYER_FILTER

# Ordered recipe sequence for seg events.  WAFER_NUM rank 1-3 = first recipe,
# 4-6 = second, ..., 19-21 = last.  MECH run always has the lowest WAFER_NUMs.
SEG_RECIPE_SEQUENCE = CFG_SEG_RECIPE_SEQUENCE

# Number of wafers per recipe block in a complete seg event.
SEG_WAFERS_PER_RECIPE = CFG_SEG_WAFERS_PER_RECIPE

# ---------------------------------------------------------------------------
# CHUNK / BATCH SIZES
# ---------------------------------------------------------------------------

# Max (INSPECTION_TIME, WAFER_KEY) pairs per INSP_DEFECT query chunk
DEFECT_CHUNK_SIZE = CFG_DEFECT_CHUNK_SIZE

# Max inspection events per INSP_ELEMENT (EDX) query chunk.
# Each event generates one OR-condition block in the WHERE clause.
EDX_CHUNK_SIZE = CFG_EDX_CHUNK_SIZE

# Minimum gap between consecutive wafer INSPECTION_TIMEs (within the same
# ACTUAL_LOT + PRIMARY_EQUIP group) that signals the start of a NEW scan run.
# Within a single batch, consecutive wafers are typically scanned 10-20 minutes
# apart.  A gap larger than this threshold means a new introduction has started.
SS_RUN_GAP_HOURS = CFG_SS_RUN_GAP_HOURS
PILOT_COLUMNS = ["CCMR2", "ICCR2", "GF", "CV", "SRCIP", "TS"]
PM_COUNTER_OUTPUT_COLS = ["FULLPM_RF", "MINIPM_RF"]
PRODUCTION_RF_COUNTER_COLS = ["FULLPM_RF", "MINIPM_RF"]
LEGACY_COUNTER_COLUMNS_TO_REMOVE = ["FULLPM", "MINIPM", "CNTR_SS"]
INSP_EXTRA_OUTPUT_COLS = [
    "ADDER_CLUSTERS", "CLUSTERS", "ADDER_RANDOM_DEFECTS",
    *PM_COUNTER_OUTPUT_COLS,
]

PM_COUNTER_PARAM_MAP = {
    "FULLPM_RF": "FullPMRFCounter",
    "MINIPM_RF": "MiniPMRFCounter",
}


def _ensure_columns(df: pd.DataFrame, columns) -> pd.DataFrame:
    """Ensure optional columns exist so downstream selectors do not KeyError."""
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = np.nan
    return out

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _incremental_save(new_df, output_path, lookback_days, dedup_keys=None):
    """
    Persist ``new_df`` to ``output_path``, merging with any existing file.

    Strategy (``INCREMENTAL_UPDATE = True``):
        1. Load the existing CSV.
        2. Parse INSPECTION_TIME as datetime in both DataFrames.
        3. Drop rows from the existing file whose INSPECTION_TIME falls at or
           after ``cutoff = now() - lookback_days``.  These rows are covered
           by the current run and will be replaced.
        4. Concatenate surviving old rows with ``new_df``, sort by
           INSPECTION_TIME descending, then deduplicate on
           (WAFER_KEY, INSPECTION_TIME, DEFECT_ID) keeping the first
           occurrence (newest run wins).
        5. Save.

    When ``INCREMENTAL_UPDATE = False`` or the output file does not yet exist,
    ``new_df`` is saved as-is (full overwrite / initial write).
    """
    import os

    # Enforce RF-only production schema regardless of historical file headers.
    new_df = new_df.drop(columns=[c for c in LEGACY_COUNTER_COLUMNS_TO_REMOVE if c in new_df.columns], errors="ignore")

    if INCREMENTAL_UPDATE and os.path.exists(output_path):
        print(f"  [incremental] Loading existing CSV: {output_path}")
        existing = pd.read_csv(output_path)
        existing = existing.drop(columns=[c for c in LEGACY_COUNTER_COLUMNS_TO_REMOVE if c in existing.columns], errors="ignore")
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)

        existing["INSPECTION_TIME"] = pd.to_datetime(
            existing["INSPECTION_TIME"], errors="coerce"
        )
        new_df["INSPECTION_TIME"] = pd.to_datetime(
            new_df["INSPECTION_TIME"], errors="coerce"
        )

        n_before = len(existing)
        surviving = existing[existing["INSPECTION_TIME"] < cutoff].copy()
        print(f"  [incremental] {n_before} existing rows; "
              f"{n_before - len(surviving)} dropped (within lookback window); "
              f"{len(surviving)} preserved")

        combined = pd.concat([surviving, new_df], ignore_index=True)
        combined = combined.sort_values("INSPECTION_TIME", ascending=False)
        if dedup_keys is None:
            dedup_keys = ("WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID")
        dedup_keys = [k for k in dedup_keys if k in combined.columns]
        if dedup_keys:
            combined = combined.drop_duplicates(subset=dedup_keys, keep="first")
        combined = combined.drop(columns=[c for c in LEGACY_COUNTER_COLUMNS_TO_REMOVE if c in combined.columns], errors="ignore")
        combined.to_csv(output_path, index=False)
        print(f"  [incremental] Saved {len(combined)} total records -> {output_path}")
    else:
        new_df = new_df.drop(columns=[c for c in LEGACY_COUNTER_COLUMNS_TO_REMOVE if c in new_df.columns], errors="ignore")
        new_df.to_csv(output_path, index=False)
        print(f"Saved {len(new_df)} records -> {output_path}")


def _fetch_wafer_summary_ss(conn, lookback_days=365, layer_filter=None,
                             chamber_filter=None, upper_bound_days=None):
    """
    Query INSP_WAFER_SUMMARY for PST inspection events.

    Filters (all AND-ed):
      PROCESS_EQUIP_ID IN (...)    -- etch chamber ('Pri Eqp' in UDB UI)
      LAYER_ID IN (...) or LIKE    -- PST scan step
      INSPECTION_TIME >= SYSDATE - lookback_days

    PROCESS_EQUIP_ID + LAYER_ID is highly selective; no SCRIBE_ID filter
    is needed since the layer ID is SS-test-wafer-specific.

    chamber_filter : list of str or None
        PROCESS_EQUIP_ID values to match (e.g. ['AME401_PM1']).
    """
    date_clause = (
        f"  AND s.INSPECTION_TIME >= SYSDATE - {int(lookback_days)}"
        if lookback_days else ""
    )
    upper_date_clause = (
        f"  AND s.INSPECTION_TIME < SYSDATE - {int(upper_bound_days)}"
        if upper_bound_days is not None else ""
    )
    if layer_filter:
        layer_in = ", ".join(f"'{l}'" for l in layer_filter)
        layer_clause = f"  AND s.LAYER_ID IN ({layer_in})"
    else:
        layer_clause = "  AND s.LAYER_ID LIKE '%\\_PST' ESCAPE '\\'"

    if chamber_filter:
        ch_in = ", ".join(f"'{c}'" for c in chamber_filter)
        chamber_clause = f"  AND s.{CHAMBER_COL} IN ({ch_in})"
    else:
        chamber_clause = ""

    sql = f"""
SELECT
    s.WAFER_KEY,
    s.INSPECTION_TIME,
    'POST'                         AS SCAN_TYPE,
    s.SCRIBE_ID                    AS WAFER_ID,
    SUBSTR(s.LOT_ID, 1, 7)         AS LOT7,
    s.LOT_ID                       AS ACTUAL_LOT,
    s.LAYER_ID                     AS LAYER,
    s.INSPECT_EQUIP_ID             AS INSPECTION_TOOL,
    s.{CHAMBER_COL}                AS PRIMARY_EQUIP,
    s.SLOT_ID                      AS WAFER_NUM,
    s.CENTER_X,
    s.CENTER_Y,
    s.DEFECTS                      AS N_DEFECTS,
    s.ADDER_DEFECTS,
    s.ADDER_CLUSTERS,
    s.CLUSTERS,
    s.ADDER_RANDOM_DEFECTS
FROM udb.INSP_WAFER_SUMMARY s
WHERE 1=1
{date_clause}
{upper_date_clause}
{layer_clause}
{chamber_clause}
"""
    lookback_str = f"{lookback_days}d" if lookback_days else "all history"
    upper_str = f"<{int(upper_bound_days)}d" if upper_bound_days is not None else "none"
    print(f"  [INSP_WAFER_SUMMARY] chamber={chamber_filter}, "
          f"layer={layer_filter}, lookback={lookback_str}, upper_bound={upper_str}")
    result_df = pd.read_sql(sql, conn)
    print(f"    -> {len(result_df)} rows")
    return result_df


def _fetch_pm_counter_history(
    chamber_filter=None,
    lookback_days=None,
    upper_bound_days=None,
    start_time=None,
    end_time=None,
):
    """Fetch PM counter snapshots from XEUS history tables for requested chambers."""
    if not chamber_filter:
        return pd.DataFrame(columns=["PRIMARY_EQUIP", "COUNTER_TIME", *PM_COUNTER_OUTPUT_COLS])

    ch_in = ", ".join(f"'{c}'" for c in chamber_filter)
    attr_in = ", ".join(f"'{v}'" for v in PM_COUNTER_PARAM_MAP.values())

    date_clause = (
        f"  AND h.TXN_DATE >= SYSDATE - {int(lookback_days)}"
        if lookback_days else ""
    )
    upper_date_clause = (
        f"  AND h.TXN_DATE < SYSDATE - {int(upper_bound_days)}"
        if upper_bound_days is not None else ""
    )
    start_clause = ""
    if start_time is not None and pd.notna(start_time):
        start_s = pd.Timestamp(start_time).strftime("%Y-%m-%d %H:%M:%S")
        start_clause = f"  AND h.TXN_DATE >= TO_DATE('{start_s}','YYYY-MM-DD HH24:MI:SS')"
    end_clause = ""
    if end_time is not None and pd.notna(end_time):
        end_s = pd.Timestamp(end_time).strftime("%Y-%m-%d %H:%M:%S")
        end_clause = f"  AND h.TXN_DATE <= TO_DATE('{end_s}','YYYY-MM-DD HH24:MI:SS')"

    sql = f"""
SELECT
    h.ENTITY            AS PRIMARY_EQUIP,
    h.TXN_DATE          AS COUNTER_TIME,
    h.ATTRIBUTE_NAME    AS ATTRIBUTE_NAME,
    TRIM(h.ATTRIBUTE_VALUE) AS ATTRIBUTE_VALUE
FROM F_ENTITYATTRIBUTEHIST h
WHERE h.ENTITY IN ({ch_in})
  AND h.ATTRIBUTE_NAME IN ({attr_in})
  AND LENGTH(TRIM(h.ATTRIBUTE_VALUE)) > 0
  AND NVL(LENGTH(TRANSLATE(TRIM(h.ATTRIBUTE_VALUE), ' 0123456789.-', 'X')), 0) = 0
  AND NVL(h.HISTORY_DELETED_FLAG, 'N') = 'N'
{date_clause}
{upper_date_clause}
{start_clause}
{end_clause}
"""

    conn = PyUber.connect(COUNTER_DATABASE)
    try:
        raw = pd.read_sql(sql, conn)
    finally:
        conn.close()
        del conn
        gc.collect()

    if raw.empty:
        return pd.DataFrame(columns=["PRIMARY_EQUIP", "COUNTER_TIME", *PM_COUNTER_OUTPUT_COLS])

    raw["COUNTER_TIME"] = pd.to_datetime(raw["COUNTER_TIME"], errors="coerce")
    raw["ATTRIBUTE_VALUE"] = pd.to_numeric(raw["ATTRIBUTE_VALUE"], errors="coerce")
    raw = raw.dropna(subset=["COUNTER_TIME", "ATTRIBUTE_VALUE"])
    if raw.empty:
        return pd.DataFrame(columns=["PRIMARY_EQUIP", "COUNTER_TIME", *PM_COUNTER_OUTPUT_COLS])

    inv_map = {v: k for k, v in PM_COUNTER_PARAM_MAP.items()}
    raw["OUTPUT_COL"] = raw["ATTRIBUTE_NAME"].map(inv_map)
    raw = raw.dropna(subset=["OUTPUT_COL"])

    piv = (
        raw.pivot_table(
            index=["PRIMARY_EQUIP", "COUNTER_TIME"],
            columns="OUTPUT_COL",
            values="ATTRIBUTE_VALUE",
            aggfunc="max",
        )
        .reset_index()
    )

    for c in PM_COUNTER_OUTPUT_COLS:
        if c not in piv.columns:
            piv[c] = np.nan

    return piv[["PRIMARY_EQUIP", "COUNTER_TIME", *PM_COUNTER_OUTPUT_COLS]]


def _attach_pm_counters_nearest(df: pd.DataFrame, chamber_filter=None,
                                lookback_days=None, upper_bound_days=None) -> pd.DataFrame:
    """Nearest-time join PM counters onto wafer events by PRIMARY_EQUIP."""
    if df.empty or "INSPECTION_TIME" not in df.columns or "PRIMARY_EQUIP" not in df.columns:
        return df

    left = df.copy()
    left["INSPECTION_TIME"] = pd.to_datetime(left["INSPECTION_TIME"], errors="coerce")

    merged_parts = []
    counters_by_equip = {}
    for equip, grp in left.groupby("PRIMARY_EQUIP", dropna=False, sort=False):
        if pd.isna(equip):
            z = grp.copy()
            for c in PM_COUNTER_OUTPUT_COLS:
                if c not in z.columns:
                    z[c] = np.nan
            merged_parts.append(z)
            continue

        gmin = grp["INSPECTION_TIME"].min()
        gmax = grp["INSPECTION_TIME"].max()
        window_start = (gmin - pd.Timedelta(days=2)) if pd.notna(gmin) else None
        window_end = (gmax + pd.Timedelta(days=2)) if pd.notna(gmax) else None

        if equip not in counters_by_equip:
            counters_by_equip[equip] = _fetch_pm_counter_history(
                chamber_filter=[equip],
                lookback_days=lookback_days,
                upper_bound_days=upper_bound_days,
                start_time=window_start,
                end_time=window_end,
            )

        ctr = counters_by_equip[equip].sort_values("COUNTER_TIME")
        if ctr.empty:
            z = grp.copy()
            for c in PM_COUNTER_OUTPUT_COLS:
                if c not in z.columns:
                    z[c] = np.nan
            merged_parts.append(z)
            continue

        gs = grp.sort_values("INSPECTION_TIME")
        joined = pd.merge_asof(
            gs,
            ctr,
            left_on="INSPECTION_TIME",
            right_on="COUNTER_TIME",
            direction="nearest",
        )
        joined = joined.drop(columns=["PRIMARY_EQUIP_y", "COUNTER_TIME"], errors="ignore")
        joined = joined.rename(columns={"PRIMARY_EQUIP_x": "PRIMARY_EQUIP"})
        merged_parts.append(joined)

    out = pd.concat(merged_parts, ignore_index=True)
    for c in PM_COUNTER_OUTPUT_COLS:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        else:
            out[c] = np.nan
    return out


def _create_pilot_status_from_flags(df: pd.DataFrame) -> pd.Series:
    """Build PILOT_STATUS from individual pilot ON/OFF flags."""
    srcip_on = df["SRCIP"] == "ON"

    base = pd.Series("ERROR", index=df.index, dtype="object")
    ccmr2_on = df["CCMR2"] == "ON"
    iccr2_on = df["ICCR2"] == "ON"

    base[(~ccmr2_on) & (~iccr2_on)] = "POR"
    base[(ccmr2_on) & (~iccr2_on)] = "CCMR2"
    base[(~ccmr2_on) & (iccr2_on)] = "ICCR2"
    base[(ccmr2_on) & (iccr2_on)] = "CCMR2+ICCR2"

    suffix = pd.Series("", index=df.index, dtype="object")
    suffix = suffix.mask(df["CV"] == "ON", suffix + "+CV")
    suffix = suffix.mask(df["GF"] == "ON", suffix + "+GF")

    status = base + suffix
    status = status.mask(srcip_on, "SRCIP")
    return status


def _add_pilot_status(df: pd.DataFrame, time_col: str = "INSPECTION_TIME") -> pd.DataFrame:
    """
    Add PILOT_STATUS using BE pilot turn-on dates.

    Key matching fallback in SURF data:
      1) SUBENTITY
      2) PRIMARY_EQUIP
    """
    out = df.copy()
    out = out.drop(columns=PILOT_COLUMNS, errors="ignore")
    out["PILOT_STATUS"] = "POR"

    if time_col not in out.columns:
        return out

    data_key_col = next((c for c in ("SUBENTITY", "PRIMARY_EQUIP") if c in out.columns), None)
    if data_key_col is None:
        return out

    pilot_path = PIPELINE_PATHS.pilot_dates_path
    if not pilot_path.exists():
        print(f"  WARNING: Pilot dates file missing; defaulting PILOT_STATUS=POR ({pilot_path})")
        return out

    pilot_df = pd.read_csv(pilot_path, low_memory=False)
    pilot_key_col = next((c for c in ("SUBENTITY", "PRIMARY_EQUIP") if c in pilot_df.columns), None)
    if pilot_key_col is None:
        print("  WARNING: Pilot dates file missing SUBENTITY/PRIMARY_EQUIP key; defaulting PILOT_STATUS=POR")
        return out

    available_pilot_cols = [c for c in PILOT_COLUMNS if c in pilot_df.columns]
    if not available_pilot_cols:
        print("  WARNING: Pilot dates file has no pilot columns; defaulting PILOT_STATUS=POR")
        return out

    merge_right_cols = [pilot_key_col] + available_pilot_cols
    pilot_map = pilot_df[merge_right_cols].copy()
    for col in available_pilot_cols:
        pilot_map[col] = pd.to_datetime(pilot_map[col], errors="coerce")

    out["__PILOT_KEY"] = out[data_key_col].astype(str)
    pilot_map = pilot_map.rename(columns={pilot_key_col: "__PILOT_KEY"})

    merged = out.merge(pilot_map, on="__PILOT_KEY", how="left")
    data_time = pd.to_datetime(merged[time_col], errors="coerce")

    for col in PILOT_COLUMNS:
        if col in available_pilot_cols:
            col_time = pd.to_datetime(merged[col], errors="coerce")
            merged[col] = (col_time.notna() & data_time.notna() & (col_time < data_time)).map({True: "ON", False: "OFF"})
        else:
            merged[col] = "OFF"

    merged["PILOT_STATUS"] = _create_pilot_status_from_flags(merged)
    merged = merged.drop(columns=["__PILOT_KEY"], errors="ignore")
    return merged


def _fetch_defect_coords(conn, pairs, class_filter=None):
    """
    Query UDB.INSP_DEFECT for adder defects given a list of
    (INSPECTION_TIME datetime, WAFER_KEY int) tuples.

    Parameters
    ----------
    class_filter : list of str or None
        When provided, only defects whose CLASS name is in this list are
        returned.  e.g. ['SMALL_PARTICLE', 'BEEP'].  None = all classes.

    Returned columns:
        WAFER_KEY, INSPECTION_TIME, WAFER_ID (scribe), LOT7, ACTUAL_LOT,
        LAYER, DEFECT_ID, CLASS, FINEBIN, WAFER_X_MM, WAFER_Y_MM, IMAGE_COUNT
    """
    class_sql_filter = ""
    if class_filter:
        quoted = ", ".join(f"'{c}'" for c in class_filter)
        class_sql_filter = f"  AND c.NAME IN ({quoted})"

    all_chunks = []

    for i in range(0, len(pairs), DEFECT_CHUNK_SIZE):
        chunk = pairs[i : i + DEFECT_CHUNK_SIZE]

        date_strings = [t.strftime("%Y%m%d%H%M%S") for t, k in chunk]
        rows = ",\n".join(
            f"(TO_DATE('{ds}','YYYYMMDDHH24MISS'), {k})"
            for ds, (t, k) in zip(date_strings, chunk)
        )

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
    TO_CHAR(d.SIZE_D   / 1000.0)                      AS SIZE_D_UM,
    TO_CHAR(d.IMAGES)                                 AS IMAGE_COUNT
FROM UDB.INSP_WAFER_SUMMARY s
INNER JOIN UDB.INSP_DEFECT d
    ON  d.WAFER_KEY       = s.WAFER_KEY
    AND d.INSPECTION_TIME = s.INSPECTION_TIME
    AND d.ADDER           = 1
LEFT JOIN udb.CLASS c
    ON  c.CLASS_ID = d.CLASS_NUMBER
LEFT JOIN udb.FINEBIN f
    ON  f.FINEBIN_ID = d.AUTOMATED_OPTICAL_CLASS
WHERE (s.INSPECTION_TIME, s.WAFER_KEY) IN (
{rows}
){class_sql_filter}
"""
        print(
            f"  [INSP_DEFECT] chunk {i // DEFECT_CHUNK_SIZE + 1}: "
            f"{len(chunk)} wafer inspections..."
        )
        chunk_df = pd.read_sql(sql, conn)
        print(f"    -> {len(chunk_df)} defect records")
        all_chunks.append(chunk_df)

    if not all_chunks:
        return pd.DataFrame()
    return pd.concat(all_chunks, ignore_index=True)


def _fetch_edx_data(conn, image_defects_df):
    """
    Query UDB.INSP_ELEMENT for EDX elemental data for defects where
    IMAGE_COUNT > 0.  Mirrors the GAJT EDXQuery plugin SQL pattern:

        SELECT e.*
        FROM UDB.INSP_ELEMENT e
        WHERE e.WAFER_KEY = <key>
          AND e.INSPECTION_TIME = TO_DATE('<ts>','YYYYMMDDHH24MISS')
          AND e.DEFECT_ID IN (<ids>)

    Multiple inspection events are batched into a single query using OR
    conditions (EDX_CHUNK_SIZE events per query).

    Parameters
    ----------
    image_defects_df : DataFrame
        Rows from _fetch_defect_coords() where IMAGE_COUNT > 0.
        Must contain WAFER_KEY, INSPECTION_TIME, DEFECT_ID.

    Returns
    -------
    DataFrame of all INSP_ELEMENT rows (e.*) for the matched defects,
    with WAFER_KEY and INSPECTION_TIME added for join-back convenience.
    """
    if image_defects_df.empty:
        return pd.DataFrame()

    # Build list of (wafer_key, insp_time_dt, [defect_id_strs]) per event
    groups = [
        (key, grp)
        for key, grp in image_defects_df.groupby(["WAFER_KEY", "INSPECTION_TIME"])
    ]

    all_chunks = []

    for i in range(0, len(groups), EDX_CHUNK_SIZE):
        batch = groups[i : i + EDX_CHUNK_SIZE]

        conditions = []
        for (wafer_key, insp_time), grp in batch:
            defect_ids = ", ".join(str(d) for d in grp["DEFECT_ID"].tolist())
            dt_str = pd.Timestamp(insp_time).strftime("%Y%m%d%H%M%S")
            conditions.append(
                f"(e.WAFER_KEY = {int(wafer_key)}"
                f" AND e.INSPECTION_TIME = TO_DATE('{dt_str}','YYYYMMDDHH24MISS')"
                f" AND e.DEFECT_ID IN ({defect_ids}))"
            )

        where_clause = "\n   OR ".join(conditions)
        sql = f"""
SELECT e.*
FROM UDB.INSP_ELEMENT e
WHERE {where_clause}
"""
        print(
            f"  [INSP_ELEMENT] chunk {i // EDX_CHUNK_SIZE + 1}: "
            f"{len(batch)} inspection event(s)..."
        )
        chunk_df = pd.read_sql(sql, conn)
        print(f"    -> {len(chunk_df)} EDX records")
        if not chunk_df.empty:
            all_chunks.append(chunk_df)

    if not all_chunks:
        return pd.DataFrame()
    return pd.concat(all_chunks, ignore_index=True)


# ---------------------------------------------------------------------------
# DIAGNOSTICS
# ---------------------------------------------------------------------------

def show_layer_distribution(conn, lookback_days=None, chamber_filter=None,
                             top_n=20):
    """
    Print a frequency table of LAYER_ID values scoped to the same
    PROCESS_EQUIP_ID and lookback window used by the main query.
    """
    date_clause = (
        f"  AND s.INSPECTION_TIME >= SYSDATE - {int(lookback_days)}"
        if lookback_days else ""
    )
    if chamber_filter:
        ch_in = ", ".join(f"'{c}'" for c in chamber_filter)
        chamber_clause = f"  AND s.{CHAMBER_COL} IN ({ch_in})"
    else:
        chamber_clause = ""
    sql = f"""
SELECT s.LAYER_ID, COUNT(*) AS CNT
FROM udb.INSP_WAFER_SUMMARY s
WHERE 1=1
{date_clause}
{chamber_clause}
GROUP BY s.LAYER_ID
ORDER BY CNT DESC
FETCH FIRST {top_n} ROWS ONLY
"""
    df = pd.read_sql(sql, conn)
    print("\n--- LAYER_ID distribution for selected scribe IDs ---")
    print(df.to_string(index=False))
    print()
    return df


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------


def _assign_seg_recipes(seg_summary_df, recipe_sequence, wafers_per_recipe):
    """
    Assign SEG_RECIPE to each row in seg_summary_df based on WAFER_NUM rank
    order within each (INSPECTION_TIME, PRIMARY_EQUIP) group.

    All 21 wafers in a complete seg event share one INSPECTION_TIME.  Rows are
    ranked by WAFER_NUM ascending within the group; blocks of `wafers_per_recipe`
    consecutive ranks map to successive entries in `recipe_sequence`.

    Groups with a count != len(recipe_sequence) * wafers_per_recipe are flagged
    as PARTIAL_RUN rather than silently misassigning recipes.

    Returns seg_summary_df with a SEG_RECIPE column added.
    """
    expected = len(recipe_sequence) * wafers_per_recipe
    records = []

    for (insp_time, equip), grp in seg_summary_df.groupby(
        ["INSPECTION_TIME", "PRIMARY_EQUIP"], sort=False
    ):
        grp_sorted = grp.sort_values("WAFER_NUM").reset_index(drop=True)

        if len(grp_sorted) != expected:
            grp_sorted["SEG_RECIPE"] = "PARTIAL_RUN"
        else:
            recipes = [
                recipe_sequence[i // wafers_per_recipe]
                for i in range(expected)
            ]
            grp_sorted["SEG_RECIPE"] = recipes

        records.append(grp_sorted)

    if not records:
        return seg_summary_df.assign(SEG_RECIPE=pd.NA)
    return pd.concat(records, ignore_index=True)


def _add_event_wafer_column(df: pd.DataFrame) -> pd.DataFrame:
    """Add EVENT_WAFER using SLOT_ID normalized within each inspection event."""
    if df.empty:
        return df

    out = df.copy()
    out["SLOT_ID"] = pd.to_numeric(out.get("SLOT_ID"), errors="coerce")
    event_keys = [c for c in ["ACTUAL_LOT", "PRIMARY_EQUIP", "INSPECTION_TIME", "EVENT"] if c in out.columns]
    if not event_keys:
        return out

    sort_keys = event_keys + [c for c in ["SLOT_ID", "WAFER_ID", "WAFER_KEY", "DEFECT_ID"] if c in out.columns]
    out = out.sort_values(sort_keys, kind="mergesort")
    out["_ROW_IN_EVENT"] = out.groupby(event_keys, dropna=False).cumcount() + 1

    out["EVENT_WAFER"] = out.groupby(event_keys, dropna=False)["SLOT_ID"].rank(method="dense")
    out.loc[out["EVENT_WAFER"].isna(), "EVENT_WAFER"] = out.loc[
        out["EVENT_WAFER"].isna(), "_ROW_IN_EVENT"
    ]
    out["EVENT_WAFER"] = pd.to_numeric(out["EVENT_WAFER"], errors="coerce").astype("Int64")
    return out.drop(columns=["_ROW_IN_EVENT"], errors="ignore")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def query_ss_coordinates():
    # ------------------------------------------------------------------
    # 1. Query INSP_WAFER_SUMMARY (PROCESS_EQUIP_ID + layer + lookback)
    # ------------------------------------------------------------------
    # Resolve PRIMARY_EQUIP_FILTER: default to SUBENTITY_FILTER if not set.
    primary_equip = PRIMARY_EQUIP_FILTER or (
        SUBENTITY_FILTER if isinstance(SUBENTITY_FILTER, list) else
        [SUBENTITY_FILTER] if SUBENTITY_FILTER else None
    )
    if primary_equip:
        print(f"  {CHAMBER_COL} filter: {primary_equip}")
    if LOOKBACK_DAYS:
        print(f"  Lookback window: {LOOKBACK_DAYS} days from today")

    print(f"\nStep 1: Querying INSP_WAFER_SUMMARY")
    if SS_LAYER_FILTER:
        print(f"  Layer filter: {SS_LAYER_FILTER}")
    else:
        print("  Layer filter: LAYER_ID LIKE '%_PST' (default)")

    conn = PyUber.connect(DATABASE)
    try:
        show_layer_distribution(conn,
                                lookback_days=LOOKBACK_DAYS,
                                chamber_filter=primary_equip)

        summary_df = _fetch_wafer_summary_ss(
            conn,
            lookback_days=LOOKBACK_DAYS,
            layer_filter=SS_LAYER_FILTER,
            chamber_filter=primary_equip,
            upper_bound_days=UPPER_BOUND_DAYS,
        )
    finally:
        conn.close()
        del conn
        gc.collect()

    if summary_df.empty:
        print(
            "No wafer summary records found.\n"
            "  -> If the layer convention differs, set SS_LAYER_FILTER explicitly."
        )
        return None

    summary_df["INSPECTION_TIME"] = pd.to_datetime(
        summary_df["INSPECTION_TIME"], errors="coerce"
    )
    if ENABLE_LEGACY_NEAREST_PM_ENRICHMENT:
        summary_df = _attach_pm_counters_nearest(
            summary_df,
            chamber_filter=primary_equip,
            lookback_days=LOOKBACK_DAYS,
            upper_bound_days=UPPER_BOUND_DAYS,
        )
    else:
        print("  Legacy nearest PM enrichment disabled; using RF refresh path only.")
    summary_df = _ensure_columns(summary_df, INSP_EXTRA_OUTPUT_COLS)
    summary_df["SLOT_ID"] = pd.to_numeric(summary_df.get("WAFER_NUM"), errors="coerce")
    for col in INSP_EXTRA_OUTPUT_COLS:
        if col in summary_df.columns:
            summary_df[col] = pd.to_numeric(summary_df[col], errors="coerce")

    print(f"  Total PST inspection records: {len(summary_df)}")
    print(f"  Unique LAYER_IDs found: {summary_df['LAYER'].unique().tolist()}")

    # Assign a run_id within each (ACTUAL_LOT, PRIMARY_EQUIP) group by splitting
    # on time gaps larger than SS_RUN_GAP_HOURS.  Consecutive wafers in the same
    # scan session are minutes apart; a new introduction shows a gap of hours.
    # This correctly separates e.g. a 3-wafer and a 10-wafer run of the same lot
    # on the same chamber that happened hours apart.
    _sd = summary_df.sort_values(["ACTUAL_LOT", "PRIMARY_EQUIP", "INSPECTION_TIME"])
    _gap = pd.Timedelta(hours=SS_RUN_GAP_HOURS)
    _run_id_parts = []
    for _, _grp in _sd.groupby(["ACTUAL_LOT", "PRIMARY_EQUIP"], sort=False):
        _sorted = _grp.sort_values("INSPECTION_TIME")
        _is_new = _sorted["INSPECTION_TIME"].diff() > _gap
        _run_id_parts.append(_is_new.cumsum().rename("_run_id"))
    summary_df = summary_df.copy()
    summary_df["_run_id"] = pd.concat(_run_id_parts).reindex(summary_df.index)

    # Count distinct wafers per run (batch size = 1, 3, 10, etc.)
    lot_size = (
        summary_df.groupby(["ACTUAL_LOT", "PRIMARY_EQUIP", "_run_id"])["WAFER_ID"]
        .nunique()
        .rename("N_WAFERS_IN_RUN")
        .reset_index()
    )
    # Lookup table to carry _run_id onto the defect result rows
    run_id_lookup = (
        summary_df[["ACTUAL_LOT", "PRIMARY_EQUIP", "WAFER_ID", "INSPECTION_TIME", "_run_id"]]
        .drop_duplicates()
    )
    print(f"  Wafers per chamber-lot run (distribution): "
          f"{dict(lot_size['N_WAFERS_IN_RUN'].value_counts().sort_index())}")

    matched = summary_df.copy()

    # ------------------------------------------------------------------
    # 1b. Query SEG wafer summary and assign recipes (MAMEBARE_L029_PST)
    # ------------------------------------------------------------------
    seg_summary_df = pd.DataFrame()
    if FETCH_SEG:
        print(f"\nStep 1b: Querying SEG INSP_WAFER_SUMMARY")
        if SEG_LAYER_FILTER:
            print(f"  SEG layer filter: {SEG_LAYER_FILTER}")

        conn = PyUber.connect(DATABASE)
        try:
            seg_summary_df = _fetch_wafer_summary_ss(
                conn,
                lookback_days=LOOKBACK_DAYS,
                layer_filter=SEG_LAYER_FILTER,
                chamber_filter=primary_equip,
                upper_bound_days=UPPER_BOUND_DAYS,
            )
        finally:
            conn.close()
            del conn
            gc.collect()

        if seg_summary_df.empty:
            print("  No SEG wafer summary records found -- skipping SEG path.")
        else:
            seg_summary_df["INSPECTION_TIME"] = pd.to_datetime(
                seg_summary_df["INSPECTION_TIME"], errors="coerce"
            )
            if ENABLE_LEGACY_NEAREST_PM_ENRICHMENT:
                seg_summary_df = _attach_pm_counters_nearest(
                    seg_summary_df,
                    chamber_filter=primary_equip,
                    lookback_days=LOOKBACK_DAYS,
                    upper_bound_days=UPPER_BOUND_DAYS,
                )
            seg_summary_df = _ensure_columns(seg_summary_df, INSP_EXTRA_OUTPUT_COLS)
            seg_summary_df["SLOT_ID"] = pd.to_numeric(seg_summary_df.get("WAFER_NUM"), errors="coerce")
            for col in INSP_EXTRA_OUTPUT_COLS:
                if col in seg_summary_df.columns:
                    seg_summary_df[col] = pd.to_numeric(seg_summary_df[col], errors="coerce")
            # All 21 wafers in a seg event share the same INSPECTION_TIME, so the
            # gap diff within a single event is 0. Multiple events of the same
            # lot x chamber are correctly split if they are hours apart.
            _sd_seg = seg_summary_df.sort_values(
                ["ACTUAL_LOT", "PRIMARY_EQUIP", "INSPECTION_TIME"]
            )
            _run_id_seg_parts = []
            for _, _grp in _sd_seg.groupby(
                ["ACTUAL_LOT", "PRIMARY_EQUIP"], sort=False
            ):
                _sorted = _grp.sort_values("INSPECTION_TIME")
                _is_new = _sorted["INSPECTION_TIME"].diff() > _gap
                _run_id_seg_parts.append(_is_new.cumsum().rename("_run_id"))
            seg_summary_df = seg_summary_df.copy()
            seg_summary_df["_run_id"] = pd.concat(_run_id_seg_parts).reindex(
                seg_summary_df.index
            )
            seg_lot_size = (
                seg_summary_df.groupby(
                    ["ACTUAL_LOT", "PRIMARY_EQUIP", "_run_id"]
                )["WAFER_ID"]
                .nunique()
                .rename("N_WAFERS_IN_RUN")
                .reset_index()
            )
            seg_run_id_lookup = (
                seg_summary_df[
                    ["ACTUAL_LOT", "PRIMARY_EQUIP", "WAFER_ID", "INSPECTION_TIME", "_run_id"]
                ].drop_duplicates()
            )
            seg_summary_df = _assign_seg_recipes(
                seg_summary_df, SEG_RECIPE_SEQUENCE, SEG_WAFERS_PER_RECIPE
            )
            print(f"  {len(seg_summary_df)} SEG inspection records; "
                  f"recipe distribution: "
                  f"{dict(seg_summary_df['SEG_RECIPE'].value_counts().sort_index())}")

    # ------------------------------------------------------------------
    # 2. Query defect coordinates for all PST inspections
    # ------------------------------------------------------------------
    print(f"\nStep 2: Querying INSP_DEFECT for {matched['WAFER_KEY'].nunique()} "
          f"PST wafer inspections ({len(matched)} rows)")

    pairs = [
        (row["INSPECTION_TIME"], int(row["WAFER_KEY"]))
        for _, row in matched.iterrows()
        if pd.notna(row["INSPECTION_TIME"]) and pd.notna(row["WAFER_KEY"])
    ]
    pairs = list(dict.fromkeys(pairs))

    conn = PyUber.connect(DATABASE)
    try:
        defects_df = _fetch_defect_coords(conn, pairs, class_filter=CLASS_FILTER)
    finally:
        conn.close()
        del conn
        gc.collect()

    if defects_df.empty:
        print("No adder defect records returned. "
              "The wafers may be clean, or CLASS_FILTER may be too restrictive.")
        return defects_df

    print(f"\nTotal adder defect records: {len(defects_df)}")

    # Convert numeric strings returned by TO_CHAR() in the defect query.
    for col in ("WAFER_X_MM", "WAFER_Y_MM", "SIZE_D_UM", "IMAGE_COUNT"):
        defects_df[col] = pd.to_numeric(defects_df[col], errors="coerce")

    # ------------------------------------------------------------------
    # 2b. Query SEG defect coordinates and concat with SS defects
    # ------------------------------------------------------------------
    if FETCH_SEG and not seg_summary_df.empty:
        seg_pairs = [
            (row["INSPECTION_TIME"], int(row["WAFER_KEY"]))
            for _, row in seg_summary_df.iterrows()
            if pd.notna(row["INSPECTION_TIME"]) and pd.notna(row["WAFER_KEY"])
        ]
        seg_pairs = list(dict.fromkeys(seg_pairs))
        print(f"\nStep 2b: Querying INSP_DEFECT for "
              f"{seg_summary_df['WAFER_KEY'].nunique()} SEG wafer inspections "
              f"({len(seg_summary_df)} rows)")
        conn = PyUber.connect(DATABASE)
        try:
            seg_defects_df = _fetch_defect_coords(
                conn, seg_pairs, class_filter=CLASS_FILTER
            )
        finally:
            conn.close()
            del conn
            gc.collect()

        if not seg_defects_df.empty:
            for col in ("WAFER_X_MM", "WAFER_Y_MM", "SIZE_D_UM", "IMAGE_COUNT"):
                seg_defects_df[col] = pd.to_numeric(seg_defects_df[col], errors="coerce")
            defects_df = pd.concat([defects_df, seg_defects_df], ignore_index=True)
            print(f"  Combined SS + SEG defect records: {len(defects_df)}")

    # ------------------------------------------------------------------
    # 2b. Optionally query INSP_ELEMENT for EDX data on imaged defects
    # ------------------------------------------------------------------
    edx_df = pd.DataFrame()   # populated below when FETCH_EDX is True
    if FETCH_EDX:
        image_defects = defects_df[
            defects_df["IMAGE_COUNT"].fillna(0) > 0
        ].copy()
        n_img = len(image_defects)
        n_events = image_defects.groupby(["WAFER_KEY", "INSPECTION_TIME"]).ngroups
        print(
            f"\nStep 2b: Querying INSP_ELEMENT (EDX) for {n_img} imaged defects "
            f"across {n_events} inspection event(s)..."
        )
        if image_defects.empty:
            print("  No defects with IMAGE_COUNT > 0 -- skipping EDX query.")
        else:
            conn = PyUber.connect(DATABASE)
            try:
                edx_df = _fetch_edx_data(conn, image_defects)
            finally:
                conn.close()
                del conn
                gc.collect()

            if edx_df.empty:
                print("  No EDX records returned from INSP_ELEMENT.")
            else:
                # Drop columns that duplicate data already in SS_COORDINATES.csv:
                #   X / Y          -> raw detector units; we have WAFER_X_MM / WAFER_Y_MM
                #   CLASS_NAME     -> already present as CLASS
                #   WAFER_ID       -> already present from INSP_WAFER_SUMMARY
                drop_redundant = [c for c in ("X", "Y", "CLASS_NAME", "WAFER_ID")
                                  if c in edx_df.columns]
                edx_csv = edx_df.drop(columns=drop_redundant)
                edx_csv.to_csv(EDX_OUTPUT_CSV, index=False)
                print(f"  Saved {len(edx_csv)} EDX records ({len(edx_csv.columns)} columns) "
                      f"-> {EDX_OUTPUT_CSV}")

                # Merge all EDX_ELEM* columns into the main defect table so
                # they appear in SS_COORDINATES.csv.  Column set is fully
                # dynamic -- whatever INSP_ELEMENT returns is picked up.
                # Unimaged defects (IMAGE_COUNT == 0) receive NaN.
                #
                # DEFECT_ID type note: _fetch_defect_coords wraps DEFECT_ID in
                # TO_CHAR() so defects_df carries it as a string; INSP_ELEMENT
                # SELECT e.* returns it as numeric.  Cast both to str.
                edx_join = edx_df.copy()
                edx_join["DEFECT_ID"] = edx_join["DEFECT_ID"].astype(str)
                defects_df["DEFECT_ID"] = defects_df["DEFECT_ID"].astype(str)

                join_key = ["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"]
                edx_elem_cols = [c for c in edx_join.columns
                                 if c.upper().startswith("EDX_ELEM")]
                if edx_elem_cols:
                    edx_slim = (
                        edx_join[join_key + edx_elem_cols]
                        .drop_duplicates(subset=join_key)
                    )
                    defects_df = defects_df.merge(
                        edx_slim,
                        on=join_key,
                        how="left",
                    )
                    print(f"  Merged {len(edx_elem_cols)} EDX_ELEM columns "
                          f"into main defect table.")
                else:
                    print("  No EDX_ELEM* columns found in INSP_ELEMENT result.")

    # ------------------------------------------------------------------
    # 3. Build wafer-level metrics (includes clean wafers with no defect rows)
    # ------------------------------------------------------------------
    defect_event_agg = (
        defects_df.groupby(["WAFER_KEY", "INSPECTION_TIME"], as_index=False)
        .agg(
            DEFECT_ROW_COUNT=("DEFECT_ID", "size"),
            IMAGE_DEFECT_COUNT=(
                "IMAGE_COUNT", lambda s: int((pd.to_numeric(s, errors="coerce").fillna(0) > 0).sum())
            ),
        )
    )
    defect_event_agg["HAS_DEFECT_ROWS"] = 1
    defect_event_agg["HAS_EDX"] = (defect_event_agg["IMAGE_DEFECT_COUNT"] > 0).astype(int)

    if FETCH_EDX and not edx_df.empty:
        edx_event_agg = (
            edx_df.groupby(["WAFER_KEY", "INSPECTION_TIME"], as_index=False)
            .size()
            .rename(columns={"size": "EDX_ROW_COUNT"})
        )
        defect_event_agg = defect_event_agg.merge(
            edx_event_agg,
            on=["WAFER_KEY", "INSPECTION_TIME"],
            how="left",
        )
        defect_event_agg["EDX_ROW_COUNT"] = defect_event_agg["EDX_ROW_COUNT"].fillna(0).astype(int)
        defect_event_agg["HAS_EDX"] = (defect_event_agg["EDX_ROW_COUNT"] > 0).astype(int)

    _event_map = {1: "SS0", 3: "SS1", 10: "SS7"}

    ss_metrics = summary_df[
        [
            "WAFER_KEY", "INSPECTION_TIME", "PRIMARY_EQUIP", "ACTUAL_LOT",
            "WAFER_ID", "LAYER", "SCAN_TYPE", "N_DEFECTS", "ADDER_DEFECTS",
            "LOT7", "_run_id", "SLOT_ID", *INSP_EXTRA_OUTPUT_COLS,
        ]
    ].drop_duplicates(subset=["WAFER_KEY", "INSPECTION_TIME"])
    ss_metrics = ss_metrics.merge(
        lot_size,
        on=["ACTUAL_LOT", "PRIMARY_EQUIP", "_run_id"],
        how="left",
    )
    ss_metrics["EVENT"] = ss_metrics["N_WAFERS_IN_RUN"].map(_event_map)
    ss_metrics["STATUS"] = ss_metrics["ADDER_DEFECTS"].apply(
        lambda x: "BASELINE" if pd.notna(x) and x < 10 else "HIGHFLIER"
    )
    ss_metrics["YYMM"] = pd.to_datetime(
        ss_metrics["INSPECTION_TIME"], errors="coerce"
    ).dt.strftime("%y%m")

    metrics_parts = [ss_metrics]

    if FETCH_SEG and not seg_summary_df.empty:
        seg_metrics = seg_summary_df[
            [
                "WAFER_KEY", "INSPECTION_TIME", "PRIMARY_EQUIP", "ACTUAL_LOT",
                "WAFER_ID", "LAYER", "SCAN_TYPE", "N_DEFECTS", "ADDER_DEFECTS",
                "LOT7", "_run_id", "SEG_RECIPE", "SLOT_ID", *INSP_EXTRA_OUTPUT_COLS,
            ]
        ].drop_duplicates(subset=["WAFER_KEY", "INSPECTION_TIME"])
        seg_metrics = seg_metrics.merge(
            seg_lot_size,
            on=["ACTUAL_LOT", "PRIMARY_EQUIP", "_run_id"],
            how="left",
        )
        seg_metrics["EVENT"] = seg_metrics["SEG_RECIPE"]
        seg_metrics["STATUS"] = seg_metrics["ADDER_DEFECTS"].apply(
            lambda x: "BASELINE" if pd.notna(x) and x < 10 else "HIGHFLIER"
        )
        seg_metrics["YYMM"] = pd.to_datetime(
            seg_metrics["INSPECTION_TIME"], errors="coerce"
        ).dt.strftime("%y%m")
        metrics_parts.append(seg_metrics)

    metrics_df = pd.concat(metrics_parts, ignore_index=True)
    metrics_df = metrics_df.merge(
        defect_event_agg,
        on=["WAFER_KEY", "INSPECTION_TIME"],
        how="left",
    )
    metrics_df["DEFECT_ROW_COUNT"] = metrics_df["DEFECT_ROW_COUNT"].fillna(0).astype(int)
    metrics_df["IMAGE_DEFECT_COUNT"] = metrics_df["IMAGE_DEFECT_COUNT"].fillna(0).astype(int)
    metrics_df["HAS_DEFECT_ROWS"] = metrics_df["HAS_DEFECT_ROWS"].fillna(0).astype(int)
    metrics_df["HAS_EDX"] = metrics_df["HAS_EDX"].fillna(0).astype(int)
    if "EDX_ROW_COUNT" in metrics_df.columns:
        metrics_df["EDX_ROW_COUNT"] = metrics_df["EDX_ROW_COUNT"].fillna(0).astype(int)

    metrics_df = _add_pilot_status(metrics_df, time_col="INSPECTION_TIME")
    metrics_df = _add_event_wafer_column(metrics_df)

    metrics_df = metrics_df.drop(columns=["_run_id", "SEG_RECIPE"], errors="ignore")
    metrics_lead_cols = [
        "YYMM", "INSPECTION_TIME", "PRIMARY_EQUIP", "EVENT", "EVENT_WAFER", "SLOT_ID",
        "ACTUAL_LOT", "WAFER_ID", "WAFER_KEY", "LAYER", "SCAN_TYPE", "LOT7",
        "N_DEFECTS", "ADDER_DEFECTS", "ADDER_CLUSTERS", "CLUSTERS", "ADDER_RANDOM_DEFECTS", "STATUS",
        *PRODUCTION_RF_COUNTER_COLS,
        "SRCIP", "CCMR2", "ICCR2", "CV", "GF", "TS", "PILOT_STATUS",
        "N_WAFERS_IN_RUN",
        "HAS_DEFECT_ROWS", "HAS_EDX", "DEFECT_ROW_COUNT", "IMAGE_DEFECT_COUNT", "EDX_ROW_COUNT",
    ]
    metrics_ordered = (
        [c for c in metrics_lead_cols if c in metrics_df.columns]
        + [c for c in metrics_df.columns if c not in metrics_lead_cols]
    )
    metrics_df = metrics_df[metrics_ordered]

    # ------------------------------------------------------------------
    # 4. Join run context back onto defect records
    # ------------------------------------------------------------------
    matched = matched.copy()
    matched["INSPECTION_TIME"] = pd.to_datetime(
        matched["INSPECTION_TIME"], errors="coerce"
    )

    extra_cols = [
        "WAFER_KEY", "INSPECTION_TIME", "SCAN_TYPE", "PRIMARY_EQUIP",
        "N_DEFECTS", "ADDER_DEFECTS", "SLOT_ID", *INSP_EXTRA_OUTPUT_COLS,
    ]
    ctx_keep = [c for c in extra_cols if c in matched.columns]

    # --- SS defect context join ---
    ss_mask = (
        defects_df["LAYER"].isin(SS_LAYER_FILTER)
        if SS_LAYER_FILTER else
        ~defects_df["LAYER"].isin(SEG_LAYER_FILTER or [])
    )
    ss_defects = defects_df[ss_mask].copy()

    context = matched[ctx_keep].drop_duplicates(subset=["WAFER_KEY", "INSPECTION_TIME"])
    result = ss_defects.merge(context, on=["WAFER_KEY", "INSPECTION_TIME"], how="left")
    result = result.merge(
        run_id_lookup,
        on=["ACTUAL_LOT", "PRIMARY_EQUIP", "WAFER_ID", "INSPECTION_TIME"],
        how="left",
    )
    result = result.merge(lot_size, on=["ACTUAL_LOT", "PRIMARY_EQUIP", "_run_id"], how="left")
    result["STATUS"] = result["ADDER_DEFECTS"].apply(
        lambda x: "BASELINE" if pd.notna(x) and x < 10 else "HIGHFLIER"
    )
    result["EVENT"] = result["N_WAFERS_IN_RUN"].map(_event_map)

    # --- SEG defect context join ---
    if FETCH_SEG and not seg_summary_df.empty:
        seg_defects_subset = defects_df[~ss_mask].copy()

        seg_ctx_cols = [c for c in ctx_keep if c in seg_summary_df.columns]
        seg_context = (
            seg_summary_df[seg_ctx_cols]
            .drop_duplicates(subset=["WAFER_KEY", "INSPECTION_TIME"])
        )
        seg_result = seg_defects_subset.merge(
            seg_context, on=["WAFER_KEY", "INSPECTION_TIME"], how="left"
        )
        seg_result = seg_result.merge(
            seg_run_id_lookup,
            on=["ACTUAL_LOT", "PRIMARY_EQUIP", "WAFER_ID", "INSPECTION_TIME"],
            how="left",
        )
        seg_result = seg_result.merge(
            seg_lot_size, on=["ACTUAL_LOT", "PRIMARY_EQUIP", "_run_id"], how="left"
        )
        seg_result["STATUS"] = seg_result["ADDER_DEFECTS"].apply(
            lambda x: "BASELINE" if pd.notna(x) and x < 10 else "HIGHFLIER"
        )
        seg_recipe_lookup = (
            seg_summary_df[
                ["ACTUAL_LOT", "PRIMARY_EQUIP", "WAFER_ID", "INSPECTION_TIME", "SEG_RECIPE"]
            ].drop_duplicates()
        )
        seg_result = seg_result.merge(
            seg_recipe_lookup,
            on=["ACTUAL_LOT", "PRIMARY_EQUIP", "WAFER_ID", "INSPECTION_TIME"],
            how="left",
        )
        seg_result["EVENT"] = seg_result["SEG_RECIPE"]
        result = pd.concat([result, seg_result], ignore_index=True)

    # YYMM: 2-digit year + 2-digit month of inspection (e.g. "2603" for Mar 2026)
    result["YYMM"] = pd.to_datetime(
        result["INSPECTION_TIME"], errors="coerce"
    ).dt.strftime("%y%m")
    result = _add_event_wafer_column(result)
    result = _add_pilot_status(result, time_col="INSPECTION_TIME")

    # Preferred leading columns; all remaining columns follow in their natural order.
    # Drop internal working columns not wanted in final output.
    result = result.drop(columns=["SEG_RECIPE", "_run_id"], errors="ignore")
    lead_cols = [
        "YYMM", "INSPECTION_TIME", "PRIMARY_EQUIP", "EVENT", "EVENT_WAFER", "SLOT_ID",
        "ACTUAL_LOT", "WAFER_ID", "DEFECT_ID",
        "WAFER_X_MM", "WAFER_Y_MM", "SIZE_D_UM", "CLASS", "FINEBIN",
        "N_DEFECTS", "ADDER_DEFECTS", "ADDER_CLUSTERS", "CLUSTERS", "ADDER_RANDOM_DEFECTS", "STATUS",
        *PRODUCTION_RF_COUNTER_COLS,
        "SRCIP", "CCMR2", "ICCR2", "CV", "GF", "TS", "PILOT_STATUS",
        "LAYER", "SCAN_TYPE", "WAFER_KEY", "LOT7",
    ]
    ordered = (
        [c for c in lead_cols if c in result.columns]
        + [c for c in result.columns if c not in lead_cols]
    )
    result = result[ordered]

    # ------------------------------------------------------------------
    # 5. Save
    # ------------------------------------------------------------------
    _incremental_save(
        metrics_df,
        METRICS_OUTPUT_CSV,
        LOOKBACK_DAYS,
        dedup_keys=["WAFER_KEY", "INSPECTION_TIME"],
    )
    _incremental_save(result, OUTPUT_CSV, LOOKBACK_DAYS)

    print("\nSample output (first 10 rows):")
    print(result.head(10).to_string())

    if "LAYER" in result.columns:
        print("\nUnique LAYER values in defect output:")
        print(result["LAYER"].value_counts().to_string())

    return result


if __name__ == "__main__":
    query_ss_coordinates()
