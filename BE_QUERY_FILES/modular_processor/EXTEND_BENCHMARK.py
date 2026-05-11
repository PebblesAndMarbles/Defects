"""
EXTEND_BENCHMARK.py
-------------------
Extends an existing FLEET_BENCHMARK_ELWC_7DAY CSV by processing only the
new data beyond its last PERIOD_END, then appending and saving.

Usage:
    python EXTEND_BENCHMARK.py

Workflow:
    1. Load the existing benchmark file -> find max PERIOD_END (the "cutoff")
    2. Load updated defect data, filter INSPECT_TIME strictly after cutoff day
    3. Load updated ELWC data (already handled internally by the aggregator)
    4. Run create_fixed_period_aggregation_with_elwc on the new slice
    5. Concatenate existing + new rows, sort, deduplicate, save
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline_config import PIPELINE_PATHS, ensure_pipeline_dirs, validate_pipeline_paths, write_artifact_manifest

# Import the aggregation engine from the sibling script
from TIME_BIN_AGGREGATOR import (
    create_fixed_period_aggregation_with_elwc,
    analyze_fleet_benchmarking_with_elwc_results,
)

# ============================================================================
# CONFIGURATION - edit these paths as needed
# ============================================================================

# Optional explicit seed override for one-off backfill or recovery reruns.
# Prefer setting BE_BENCHMARK_SEED_PATH in the shell that launches the script.
BENCHMARK_SEED_PATH_OVERRIDE = None

BE_QUERY_FILES_DIR = str(PIPELINE_PATHS.query_dir)

# 60-day joined defect file (pre-processed, missing DEVICE/ZERO_*/SCAN cols)
DEFECT_FILEPATH = (
    str(PIPELINE_PATHS.extended_output_csv)
)

# Raw per-layer query files used to join DEVICE back onto the 60-day file
RAW_M5_CURRENT_PATH = str(Path(BE_QUERY_FILES_DIR) / "8M5CL_NCDD.csv")
RAW_M6_CURRENT_PATH = str(Path(BE_QUERY_FILES_DIR) / "8M6CL_NCDD.csv")

MERGED_SOURCE_DIR = str(PIPELINE_PATHS.merged_sources_dir)
MERGED_M5_OUTPUT_PATH = str(PIPELINE_PATHS.merged_m5_csv)
MERGED_M6_OUTPUT_PATH = str(PIPELINE_PATHS.merged_m6_csv)

# ELWC mode
# ADHOC_ELWC = True  -> use the pre-pulled 60-day file (initial / backfill run)
# ADHOC_ELWC = False -> live 10-day PyUber query runs automatically (scheduled)
ADHOC_ELWC = False

# Pre-pulled 60-day ELWC file (used when ADHOC_ELWC = True)
ELWC_ADHOC_PATH = (
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson"
    r"\2026-04-16 60 days ALL_CHAMBERS ELWC.csv"
)

# Working file written by the live fetch (used when ADHOC_ELWC = False)
ELWC_WORKING_PATH = (
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson"
    r"\ELWC\ELWC_WORKING_10DAY.csv"
)

# Days to pull on each scheduled (non-adhoc) run
ELWC_LIVE_DAYS = 10

# Output path for the extended file - datestamped with today
_today = datetime.today().strftime("%Y%m%d")
OUTPUT_PATH = (
    str(PIPELINE_PATHS.benchmark_dir / f"{_today}_8M5CL_8M6CL_202606_FLEET_BENCHMARK_ELWC_7DAY.csv")
)

# Aggregation settings - must match the original run
N_DAYS = 7
MIN_SAMPLES = 10

# ============================================================================


# Chamber list shared by fetch_elwc_fresh()
_ELWC_CHAMBERS = [
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


def resolve_existing_benchmark_path():
    env_override = os.environ.get("BE_BENCHMARK_SEED_PATH")
    if env_override:
        override_path = Path(env_override)
        if not override_path.exists():
            raise FileNotFoundError(
                f"BE_BENCHMARK_SEED_PATH was set but does not exist: {override_path}"
            )
        return override_path

    if BENCHMARK_SEED_PATH_OVERRIDE:
        override_path = Path(BENCHMARK_SEED_PATH_OVERRIDE)
        if not override_path.exists():
            raise FileNotFoundError(
                f"Configured BENCHMARK_SEED_PATH_OVERRIDE does not exist: {override_path}"
            )
        return override_path

    benchmark_dir = Path(PIPELINE_PATHS.benchmark_outputs_dir)
    candidates = sorted(
        benchmark_dir.glob("*_8M5CL_8M6CL_202606_FLEET_BENCHMARK_ELWC_7DAY.csv")
    )
    output_path = Path(OUTPUT_PATH).resolve()
    candidates = [path for path in candidates if path.resolve() != output_path]
    if not candidates:
        raise FileNotFoundError(
            f"No benchmark seed files found in {benchmark_dir}"
        )

    def sort_key(path):
        try:
            return datetime.strptime(path.name[:8], "%Y%m%d")
        except ValueError:
            return datetime.fromtimestamp(path.stat().st_mtime)

    return max(candidates, key=sort_key)


def merge_and_dedup_raw_sources(current_path, output_path, layer_label):
    """
    Normalize the current raw source into the merged-source path.

    Dedup key:
        ACTUAL_LOT@DEFECT + WAFER_ID + LAYER + INSPECTION_TIME@DEFECT

    NOTE:
        Daily launcher flow intentionally uses only current JSL raw files.
        Historical seed snapshots are no longer consumed here.
    """
    required = {
        "ACTUAL_LOT@DEFECT",
        "WAFER_ID",
        "LAYER",
        "INSPECTION_TIME@DEFECT",
        "DEVICE@DEFECT",
    }

    print(f"\n[MERGE] {layer_label}: loading current raw source ...")
    current = pd.read_csv(current_path)

    missing_current = sorted(required.difference(current.columns))
    if missing_current:
        raise ValueError(
            f"{layer_label} current source missing required columns: {missing_current}"
        )

    current["INSPECTION_TIME@DEFECT"] = pd.to_datetime(
        current["INSPECTION_TIME@DEFECT"], errors="coerce"
    )

    dedup_key = [
        "ACTUAL_LOT@DEFECT",
        "WAFER_ID",
        "LAYER",
        "INSPECTION_TIME@DEFECT",
    ]
    before = len(current)
    merged = (
        current
        .sort_values(dedup_key)
        .drop_duplicates(subset=dedup_key, keep="last")
        .reset_index(drop=True)
    )
    removed = before - len(merged)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)

    print(
        f"   [OK] {layer_label} merged rows: {len(merged):,} "
        f"(removed {removed:,} duplicates)"
    )
    print(f"   [OK] Wrote merged source -> {out_path}")
    return str(out_path)


def fetch_elwc_fresh(days, output_path):
    """
    Pull `days` days of ELWC data live via PyUber and save to output_path.
    Called automatically on each scheduled run (ADHOC_ELWC = False).
    """
    import PyUber
    import warnings
    warnings.filterwarnings('ignore')

    chambers_str = "', '".join(_ELWC_CHAMBERS)
    print(f"\n[ELWC] Fetching live ELWC data ({days} days, {len(_ELWC_CHAMBERS)} chambers) ...")

    query = f"""
    /*BEGIN SQL*/
    SELECT
              CASE WHEN  wch.operation  = 8288  THEN '>>'
                   WHEN  wch.operation  = 116398 THEN '[]'
                   WHEN  wch.operation  = 8289   THEN '[]'
                   ELSE '--' END AS wt
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
                  p.product_description,',',';'),chr(9),' '),chr(10),' '),
                  chr(13),' '),chr(34),''''),chr(7),' ') AS product_description
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
    WHERE  wch.start_time >= SYSDATE - {days}
      AND  leh.entity LIKE 'AME%'
      AND  wch.subentity IN ('{chambers_str}')
    ORDER BY wch.subentity, wch.start_time DESC
    /*END SQL*/
    """

    elwc_df = pd.read_sql(query, PyUber.connect('D1D_PROD_XEUS_LOCAL'))
    elwc_df.columns = [c.lower() for c in elwc_df.columns]
    print(f"   Retrieved {len(elwc_df):,} records")
    elwc_df.to_csv(output_path, index=False)
    print(f"   Saved -> {output_path}")
    return output_path


def prepare_defect_data(defect_filepath, raw_m5_path, raw_m6_path):
    """
    Load the 60-day joined defect file and derive the columns that the
    aggregator needs but are absent from the pre-processed CSV:

        DEVICE   - joined from the raw per-layer query files via (LOT, WAFER_ID)
        ZERO_BEEP - BEEP_NCDD == 0
        ZERO_SMP  - SMP_NCDD  == 0
        N_SCAN    - wafers scanned per LAYER+LOT
        S_SCAN    - wafers scanned per LAYER+LOT+SUBENTITY
    """
    print("\n[PREP] Preparing defect data (joining DEVICE + deriving columns) ...")

    # Load the 60-day joined file
    df = pd.read_csv(defect_filepath)
    df["INSPECT_TIME"] = pd.to_datetime(df["INSPECT_TIME"])
    print(f"   Loaded {len(df):,} rows from joined file")
    print(f"   Date range: {df['INSPECT_TIME'].min().date()} -> {df['INSPECT_TIME'].max().date()}")

    # Build DEVICE lookup from the raw per-layer query files
    device_frames = []
    for path, label in [(raw_m5_path, "8M5CL"), (raw_m6_path, "8M6CL")]:
        try:
            raw = pd.read_csv(
                path,
                usecols=lambda c: c in ("WAFER_ID", "ACTUAL_LOT@DEFECT", "DEVICE@DEFECT"),
            )
            raw = raw.rename(columns={
                "ACTUAL_LOT@DEFECT": "LOT",
                "DEVICE@DEFECT":     "DEVICE",
            })
            device_frames.append(raw[["LOT", "WAFER_ID", "DEVICE"]].drop_duplicates())
            print(f"   {label} raw file: {len(raw):,} rows, "
                  f"{raw['DEVICE'].nunique()} unique DEVICE values")
        except Exception as e:
            print(f"   [WARN] Could not load {label} raw file: {e}")

    if device_frames:
        device_lookup = pd.concat(device_frames, ignore_index=True).drop_duplicates(
            subset=["LOT", "WAFER_ID"]
        )
        df = df.merge(device_lookup, on=["LOT", "WAFER_ID"], how="left")
        if "DEVICE" not in df.columns:
            existing_device_col = next(
                (col for col in ["DEVICE_x", "DEVICE_left", "DEVICE_orig"] if col in df.columns),
                None,
            )
            lookup_device_col = next(
                (col for col in ["DEVICE_y", "DEVICE_right", "DEVICE_lookup"] if col in df.columns),
                None,
            )

            if existing_device_col and lookup_device_col:
                df["DEVICE"] = df[existing_device_col].combine_first(df[lookup_device_col])
            elif lookup_device_col:
                df["DEVICE"] = df[lookup_device_col]
            elif existing_device_col:
                df["DEVICE"] = df[existing_device_col]

        matched = df["DEVICE"].notna().sum()
        print(f"   DEVICE joined: {matched:,}/{len(df):,} rows matched "
              f"({matched/len(df)*100:.1f}%)")
    else:
        print("   [WARN] No raw files loaded -- DEVICE will be NaN for all rows")
        df["DEVICE"] = None

    # Derive boolean defect flags
    import numpy as np
    beep_num = pd.to_numeric(df["BEEP_NCDD"], errors="coerce")
    smp_num  = pd.to_numeric(df["SMP_NCDD"],  errors="coerce")
    df["ZERO_BEEP"] = beep_num == 0
    df["ZERO_SMP"]  = smp_num  == 0

    # Derive scan-count columns
    df["N_SCAN"] = df.groupby(["LAYER", "LOT"])["WAFER_ID"].transform("size")
    df["S_SCAN"] = df.groupby(["LAYER", "LOT", "SUBENTITY"])["WAFER_ID"].transform("size")

    print("   [OK] Derived: ZERO_BEEP, ZERO_SMP, N_SCAN, S_SCAN")
    return df


def refresh_merged_raw_sources():
    """
    Refresh merged source files from current raw JSL CSVs.

    Returns:
        dict with merged output paths keyed by layer label.
    """
    merged_m5_path = merge_and_dedup_raw_sources(
        RAW_M5_CURRENT_PATH,
        MERGED_M5_OUTPUT_PATH,
        "8M5CL",
    )
    merged_m6_path = merge_and_dedup_raw_sources(
        RAW_M6_CURRENT_PATH,
        MERGED_M6_OUTPUT_PATH,
        "8M6CL",
    )
    return {
        "merged_m5_path": merged_m5_path,
        "merged_m6_path": merged_m6_path,
    }


def main():
    print("EXTEND FLEET BENCHMARK + ELWC FILE")
    print("=" * 70)

    ensure_pipeline_dirs()
    existing_benchmark_path = resolve_existing_benchmark_path()
    print(f"Seed benchmark file: {existing_benchmark_path}")

    for line in validate_pipeline_paths(
        {
            "existing_benchmark": existing_benchmark_path,
            "defect_filepath": Path(DEFECT_FILEPATH),
            "raw_m5_current": Path(RAW_M5_CURRENT_PATH),
            "raw_m6_current": Path(RAW_M6_CURRENT_PATH),
        }
    ):
        print(line)

    # Step -1: Merge and dedup raw layer sources for DEVICE lookup
    merged_paths = refresh_merged_raw_sources()
    merged_m5_path = merged_paths["merged_m5_path"]
    merged_m6_path = merged_paths["merged_m6_path"]

    # Step 0: Resolve ELWC source
    if ADHOC_ELWC:
        elwc_path = ELWC_ADHOC_PATH
        print("\n[ELWC] mode: ADHOC -- using pre-pulled 60-day file")
        print(f"   {elwc_path}")
    else:
        elwc_path = fetch_elwc_fresh(ELWC_LIVE_DAYS, ELWC_WORKING_PATH)

    # -- Step 1: Load existing benchmark, determine cutoff --------------------
    print("\n[FILE] Loading existing benchmark file ...")
    existing_df = pd.read_csv(existing_benchmark_path)
    existing_df["PERIOD_END"] = pd.to_datetime(existing_df["PERIOD_END"])
    existing_df["PERIOD_START"] = pd.to_datetime(existing_df["PERIOD_START"])

    # Stub detection and tail-strip
    # A "stub" is a period shorter than N_DAYS, caused when a previous run ended
    # mid-period. Stubs at the tail are stripped and regenerated. Embedded stubs
    # (from earlier run boundaries) are flagged but left in place -- they can
    # only be fixed by a manual re-run with defect data covering that window.
    existing_df = existing_df.sort_values(["PERIOD_START", "DEVICE", "LAYER"]).reset_index(drop=True)
    period_len = (existing_df["PERIOD_END"] - existing_df["PERIOD_START"]).dt.days + 1

    # Find the max PERIOD_END across ALL unique periods (device-agnostic)
    unique_periods = existing_df[["PERIOD_START", "PERIOD_END"]].drop_duplicates()
    unique_len = (unique_periods["PERIOD_END"] - unique_periods["PERIOD_START"]).dt.days + 1

    all_stub_ends = unique_periods.loc[unique_len < N_DAYS, "PERIOD_END"].unique()
    if len(all_stub_ends) > 0:
        max_period_end = unique_periods["PERIOD_END"].max()
        tail_stubs = [d for d in all_stub_ends if d == max_period_end]
        embedded_stubs = [d for d in all_stub_ends if d != max_period_end]

        if embedded_stubs:
            print(f"   [WARN] {len(embedded_stubs)} embedded stub period(s) found (cannot auto-fix -- "
                  f"need historical defect data to regenerate):")
            for d in sorted(embedded_stubs):
                stub_rows = unique_periods[unique_periods["PERIOD_END"] == d]
                start = stub_rows["PERIOD_START"].iloc[0].date()
                print(f"          {start} -> {d.date()}  "
                      f"({(d - stub_rows['PERIOD_START'].iloc[0]).days + 1} days)")

        if tail_stubs:
            # Remove all rows whose PERIOD_END is a tail stub
            tail_stub_set = set(tail_stubs)
            before = len(existing_df)
            existing_df = existing_df[~existing_df["PERIOD_END"].isin(tail_stub_set)].reset_index(drop=True)
            dropped = before - len(existing_df)
            for d in sorted(tail_stubs):
                stub_rows = unique_periods[unique_periods["PERIOD_END"] == d]
                start = stub_rows["PERIOD_START"].iloc[0].date()
                print(f"   [OK] Dropped tail stub {start} -> {d.date()} "
                      f"({(d - stub_rows['PERIOD_START'].iloc[0]).days + 1} days, "
                      f"{dropped} row(s)) -- will regenerate.")

    cutoff_date = existing_df["PERIOD_END"].max()
    print(f"   Rows in existing file : {len(existing_df):,}")
    print(f"   Existing date range   : "
          f"{existing_df['PERIOD_START'].min().date()} -> {cutoff_date.date()}")
    cutoff_exclusive = cutoff_date.normalize() + pd.Timedelta(days=1)
    print(f"   [OK] Cutoff period end          : {cutoff_date.date()}")
    print(f"   [OK] New data starts on/after  : {cutoff_exclusive.date()}")

    # Step 2: Load and prepare defect data, then filter to new window
    defect_df = prepare_defect_data(DEFECT_FILEPATH, merged_m5_path, merged_m6_path)

    # Keep only wafers inspected strictly after the cutoff period end day.
    new_defect_df = defect_df[defect_df["INSPECT_TIME"] >= cutoff_exclusive].copy()
    print(f"   Records after cutoff ({cutoff_exclusive.date()}): {len(new_defect_df):,}")

    if len(new_defect_df) == 0:
        print("\n[WARN] No new defect data found beyond the existing cutoff date.")
        print("   The updated defect file may not extend past the existing benchmark.")
        return

    new_data_start = new_defect_df["INSPECT_TIME"].min().date()
    new_data_end   = new_defect_df["INSPECT_TIME"].max().date()
    print(f"   New defect window     : {new_data_start} -> {new_data_end}")

    # Step 3: Run aggregation on the new slice only
    print(f"\n[AGG] Running {N_DAYS}-day aggregation on new data slice ...")
    expected_next_period_start = cutoff_exclusive
    new_agg_df = create_fixed_period_aggregation_with_elwc(
        new_defect_df,
        elwc_path,
        n_days=N_DAYS,
        min_samples=MIN_SAMPLES,
        start_date_override=expected_next_period_start,
    )

    if len(new_agg_df) == 0:
        print("\n[WARN] Aggregation produced no rows (min_samples threshold not met.)")
        print("   Try lowering MIN_SAMPLES or check that the new data covers full periods.")
        return

    new_agg_df["PERIOD_START"] = pd.to_datetime(new_agg_df["PERIOD_START"])
    new_agg_df["PERIOD_END"]   = pd.to_datetime(new_agg_df["PERIOD_END"])

    print(f"   [OK] New aggregated rows : {len(new_agg_df):,}")
    print(f"   New period range      : "
          f"{new_agg_df['PERIOD_START'].min().date()} -> "
          f"{new_agg_df['PERIOD_END'].max().date()}")

    # Step 4: Safety check - ensure no overlap with existing periods
    # The aggregator's first bin starts from cutoff_date, so there should be
    # no overlap, but we guard against edge cases explicitly.
    overlap_mask = new_agg_df["PERIOD_START"] <= cutoff_date
    if overlap_mask.any():
        print(f"\n[WARN] Dropping {overlap_mask.sum()} overlapping rows "
              f"(PERIOD_START <= {cutoff_date.date()}) from new data.")
        new_agg_df = new_agg_df[~overlap_mask].copy()

    # Enforce no stubs in newly appended data: keep only full N_DAYS periods.
    new_period_len = (new_agg_df["PERIOD_END"] - new_agg_df["PERIOD_START"]).dt.days + 1
    partial_mask = new_period_len < N_DAYS
    if partial_mask.any():
        dropped_partial = int(partial_mask.sum())
        new_agg_df = new_agg_df.loc[~partial_mask].copy()
        print(f"\n[OK] Dropped {dropped_partial} trailing/partial stub row(s) from new data.")

    if len(new_agg_df) == 0:
        print("\n[WARN] All new aggregated rows were partial or overlapping after safeguards.")
        print("   No rows were appended. Wait for a full period and rerun.")
        return

    # Step 5: Align column dtypes before concat
    # Restore existing columns to their original string format to match CSV output
    existing_df["PERIOD_START"] = existing_df["PERIOD_START"].dt.strftime("%Y-%m-%d")
    existing_df["PERIOD_END"]   = existing_df["PERIOD_END"].dt.strftime("%Y-%m-%d")
    new_agg_df["PERIOD_START"]  = new_agg_df["PERIOD_START"].dt.strftime("%Y-%m-%d")
    new_agg_df["PERIOD_END"]    = new_agg_df["PERIOD_END"].dt.strftime("%Y-%m-%d")

    # Step 6: Concatenate
    combined_df = pd.concat([existing_df, new_agg_df], ignore_index=True)

    # Deduplicate on (PERIOD_START, PERIOD_END, DEVICE, LAYER) - keep last (new wins)
    key_cols = ["PERIOD_START", "PERIOD_END", "DEVICE", "LAYER"]
    before_dedup = len(combined_df)
    combined_df = (
        combined_df
        .drop_duplicates(subset=key_cols, keep="last")
        .sort_values(["DEVICE", "LAYER", "PERIOD_START"])
        .reset_index(drop=True)
    )
    removed = before_dedup - len(combined_df)
    if removed:
        print(f"\n   Removed {removed} duplicate period rows after concat.")

    print("\n[SUMMARY] Combined file:")
    print(f"   Total rows            : {len(combined_df):,}")
    print(f"   Existing rows         : {len(existing_df):,}")
    print(f"   New rows appended     : {len(new_agg_df):,}")
    print(f"   Full date range       : "
          f"{combined_df['PERIOD_START'].min()} -> "
          f"{combined_df['PERIOD_END'].max()}")

    # Step 7: Save
    combined_df.to_csv(OUTPUT_PATH, index=False)
    print(f"\n[SAVE] Extended file saved to:\n   {OUTPUT_PATH}")
    manifest_path = write_artifact_manifest(
        PIPELINE_PATHS.benchmark_artifact_manifest,
        extra_outputs={
            "existing_benchmark": existing_benchmark_path,
            "defect_input_csv": Path(DEFECT_FILEPATH),
            "extended_benchmark_csv": Path(OUTPUT_PATH),
        },
    )
    print(f"[SAVE] Artifact manifest saved to:\n   {manifest_path}")
    print("[DONE] EXTENSION COMPLETE!")


if __name__ == "__main__":
    main()
