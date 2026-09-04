"""
query_other_unknown_adhoc.py
----------------------------
One-shot ad hoc query for OTHER_UNKNOWN defects from a specified CSV.

This script imports the core query machinery from DEFECT_COORDINATES_QUERY.py
and temporarily overrides the CLASS_FILTER to target only OTHER_UNKNOWN defects.

Input CSV should be in the format output by the JSL query plugin (NCDD CONCAT format).

Usage:
  python query_other_unknown_adhoc.py --input-csv <path> [--output-dir <dir>]

Example:
  python query_other_unknown_adhoc.py \
    --input-csv rollups/OTHER_UNKNOWN/OTHER_UNKNOWN.csv \
    --output-dir outputs/OTHER_UNKNOWN_REVIEW

If --output-dir is omitted, defaults to outputs/OTHER_UNKNOWN_ADHOC.
"""

import argparse
import sys
import os
import gc
from pathlib import Path

# Add BE_QUERY_FILES to path so we can import the core query module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import PyUber
from pipeline_config import PIPELINE_PATHS, ensure_pipeline_dirs, validate_pipeline_paths, write_artifact_manifest

# ============================================================================
# IMPORT CORE QUERY FUNCTIONS FROM DEFECT_COORDINATES_QUERY
# ============================================================================
from DEFECT_COORDINATES_QUERY import (
    _connect,
    _fetch_wafer_summary,
    _fetch_defect_coords,
    _fetch_image_metadata,
    _filter_defects_needing_images,
    _enrich_image_rows_with_defect_context,
    _filter_new_images,
    _download_images,
    _reorganize_images,
    _backfill_local_image_paths,
    _filter_recent_rows,
    _accumulate_coordinates,
    _normalize_coordinate_schema,
    _prune_old_images,
    _print_recent_image_manifest_validation,
    _sanitize_identifier,
    GAJT_DLL_SEARCH_PATHS,
    APP_NAME,
    TECHNOLOGY,
    IMAGE_ID_FILTER,
    IMAGE_FTP_CHUNK_SIZE,
    ANNOTATE_IMAGES,
    CONTEXT_COLS,
    METROLOGY_COLS,
    DEFECT_CHUNK_SIZE,
    LOT_CHUNK_SIZE,
    AMBIGUOUS_CLASSES,
    AMBIGUOUS_IMAGE_FOLDER,
)

# ============================================================================
# CONFIGURATION FOR OTHER_UNKNOWN QUERIES
# ============================================================================

DATABASE = "D1D_PROD_YAS_1278"

# Always query only OTHER_UNKNOWN for this script
CLASS_FILTER = ['OTHER_UNKNOWN']

# Optional filters (set to None to disable)
LAYER_FILTER = ['8M5CL', '8M6CL']  # Query both layers
LOT_FILTER = None
STATUS_FILTER = None
N_ROWS = None

# Lookback window for accumulated coordinates (180 days = 6 months)
RECENT_LOOKBACK_DAYS = 180
IMAGE_RETENTION_DAYS = 60

# Image download settings
DOWNLOAD_IMAGES = True
IMAGE_ID_FILTER = [2, 3]  # brightfield + darkfield

# Required columns in input CSV
_REQUIRED_COLUMNS = {"LOT", "WAFER_ID", "LAYER", "INSPECTION_TIME@DEFECT"}




def _rename_images_with_lot_wafer(manifest_df, image_folder):
    """
    Rename downloaded images to include lot/wafer info from manifest for traceability.
    
    Renames files from: 000000_0000_UNK_UNKNOWN_UNK_UNKNOWN_{defid}_{imgid}.jpg
    To:                {lot7}_{short_wafer}_{defid}_{imgid}.jpg
    
    This makes it easy to identify which lot/wafer a concerning defect came from.
    """
    import os
    
    if manifest_df.empty or "LOCAL_IMAGE_FILE" not in manifest_df.columns:
        print("  No images to rename (missing manifest or LOCAL_IMAGE_FILE column)")
        return
    
    renamed_count = 0
    for idx, row in manifest_df.iterrows():
        src_path = str(row.get("LOCAL_IMAGE_FILE", "")).strip()
        if not src_path or not os.path.isfile(src_path):
            continue
        
        # Extract lot, wafer, defect ID from manifest
        lot7 = str(row.get("LOT7", "UNK")).strip()[:7]
        wafer_id = str(row.get("WAFER_ID", "UNK")).strip()
        short_w = wafer_id[5:8] if len(wafer_id) >= 8 else wafer_id[:3]
        defid = str(int(float(row.get("DEFECT_ID", 0)))).strip()
        imgid = str(int(float(row.get("IMAGE_ID", 0)))).strip()
        
        # Build new filename: LOT7_WAFER_DEFID_IMGID.ext
        src_dir = os.path.dirname(src_path)
        _, ext = os.path.splitext(src_path)
        new_filename = f"{lot7}_{short_w}_{defid}_{imgid}{ext}"
        new_path = os.path.join(src_dir, new_filename)
        
        # Rename file if new name is different
        if src_path != new_path and not os.path.exists(new_path):
            try:
                os.rename(src_path, new_path)
                renamed_count += 1
                # Update manifest with new path
                manifest_df.at[idx, "LOCAL_IMAGE_FILE"] = new_path
            except OSError as e:
                print(f"  WARNING: Could not rename {os.path.basename(src_path)}: {e}")
    
    if renamed_count:
        print(f"  Renamed {renamed_count} image file(s) to include lot/wafer info")


def _normalize_input_csv(df):
    """
    Normalize raw NCDD CONCAT CSV input into pipeline column format.
    
    Converts NCDD column names to internal pipeline names:
      - INSPECTION_TIME@DEFECT -> INSPECT_TIME
      - Extracts LOT7 from LOT (first 7 chars)
      - Ensures SUBENTITY, SUBENTITY_END_TIME, RECIPE, etc. are present
    
    Returns normalized dataframe.
    """
    df = df.copy()
    
    # Rename INSPECTION_TIME@DEFECT to INSPECT_TIME
    if "INSPECTION_TIME@DEFECT" in df.columns:
        df["INSPECT_TIME"] = df["INSPECTION_TIME@DEFECT"]
    elif "INSPECTION_TIME" not in df.columns and "INSPECT_TIME" not in df.columns:
        raise ValueError("Neither INSPECTION_TIME@DEFECT nor INSPECTION_TIME found in CSV")
    
    # Ensure INSPECT_TIME is a proper datetime string
    if "INSPECT_TIME" in df.columns:
        df["INSPECT_TIME"] = pd.to_datetime(df["INSPECT_TIME"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    
    # Parse INSPECT_TIME for matching (needed for timestamp comparison in defect lookup)
    df["INSPECT_TIME_DT"] = pd.to_datetime(df["INSPECT_TIME"], errors="coerce")
    
    # Extract LOT7 from LOT
    if "LOT" in df.columns and "LOT7" not in df.columns:
        df["LOT7"] = df["LOT"].astype(str).str[:7]
    
    # Extract SUBENTITY from layer-specific columns in JSL CSV
    # Input CSV has columns like: SUBENTITY@NTSC@Process-1@AME@E_8M5_HM_ETCH, SUBENTITY@NTSC@Process-1@AME@E_8M6_HM_ETCH
    if "SUBENTITY" not in df.columns:
        df["SUBENTITY"] = ""
    
    # For each row, try to get SUBENTITY from the layer-specific column
    def extract_subentity(row):
        layer = str(row.get("LAYER", "")).strip()
        # Extract layer prefix (e.g., "8M5" from "8M5CL", "8M6" from "8M6CL")
        layer_prefix = layer[:3] if len(layer) >= 3 else ""
        
        # Try to find layer-specific SUBENTITY column
        if layer_prefix:
            for col in df.columns:
                if "SUBENTITY" in col and layer_prefix in col:
                    val = row.get(col, "")
                    if isinstance(val, str):
                        val = val.strip()
                    if val and str(val).upper() not in ["NAN", "NONE", ""]:
                        return val
        
        # Fallback to generic SUBENTITY column if it exists
        val = row.get("SUBENTITY", "")
        if isinstance(val, str):
            val = val.strip()
        if val and str(val).upper() not in ["NAN", "NONE", ""]:
            return val
        
        return "ALL_CHAMBERS"
    
    df["SUBENTITY"] = df.apply(extract_subentity, axis=1)
    
    # Use INSPECT_TIME as proxy for SUBENTITY_END_TIME (when the image was captured)
    if "SUBENTITY_END_TIME" not in df.columns:
        df["SUBENTITY_END_TIME"] = df["INSPECT_TIME"]
    else:
        # Ensure it's properly formatted
        df["SUBENTITY_END_TIME"] = pd.to_datetime(df["SUBENTITY_END_TIME"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    
    # Fill missing RECIPE with placeholder
    if "RECIPE" not in df.columns:
        df["RECIPE"] = "UNKNOWN"
    df["RECIPE"] = df["RECIPE"].fillna("UNKNOWN").astype(str)
    
    # Ensure LOT column exists (required for context merge)
    if "LOT" not in df.columns:
        df["LOT"] = df.get("LOT7", "UNKNOWN")
    
    return df


def query_other_unknown(input_csv, output_dir):
    """
    Query OTHER_UNKNOWN defects from the given input CSV.
    
    Parameters
    ----------
    input_csv : str
        Path to NCDD CONCAT output CSV (JSL query plugin format)
    output_dir : str
        Root directory for outputs (coordinates, images, manifest)
    """
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    coords_csv = str(output_path / "OTHER_UNKNOWN_COORDINATES.csv")
    image_csv = str(output_path / "OTHER_UNKNOWN_IMAGES_MANIFEST.csv")
    image_folder = str(output_path / "images")
    
    print(f"\n{'='*70}")
    print(f"OTHER_UNKNOWN DEFECT QUERY (Ad Hoc)")
    print(f"{'='*70}")
    print(f"Input CSV:           {input_csv}")
    print(f"Output coordinates:  {coords_csv}")
    print(f"Output image CSV:    {image_csv}")
    print(f"Image folder:        {image_folder}")
    print(f"Class filter:        {CLASS_FILTER}")
    print(f"Database:            {DATABASE}")
    print(f"{'='*70}\n")
    
    # -----------------------------------------------------------------------
    # 1. Load and filter input CSV
    # -----------------------------------------------------------------------
    if not os.path.isfile(input_csv):
        print(f"ERROR: Input CSV not found: {input_csv}")
        return None
    
    print(f"Loading input CSV: {input_csv}")
    df = pd.read_csv(input_csv)
    print(f"  {len(df)} rows loaded")
    
    # Normalize raw NCDD CSV column names to pipeline format
    df = _normalize_input_csv(df)
    
    missing_cols = _REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise KeyError(
            "Missing required columns in input CSV: "
            f"{sorted(missing_cols)}. Found columns: {sorted(df.columns.tolist())}"
        )
    
    if LAYER_FILTER:
        df = df[df["LAYER"].isin(LAYER_FILTER if isinstance(LAYER_FILTER, list) else [LAYER_FILTER])]
        print(f"  After LAYER filter: {len(df)} rows")
    
    if LOT_FILTER:
        df = df[df["LOT7"].isin(LOT_FILTER if isinstance(LOT_FILTER, list) else [LOT_FILTER])]
        print(f"  After LOT filter: {len(df)} rows")
    
    if STATUS_FILTER:
        df = df[df["STATUS"].isin(STATUS_FILTER if isinstance(STATUS_FILTER, list) else [STATUS_FILTER])]
        print(f"  After STATUS filter: {len(df)} rows")
    
    if N_ROWS is not None:
        df = df.head(N_ROWS)
        print(f"  Trimmed to first {N_ROWS} rows")
    
    if df.empty:
        print("No rows remain after filtering. Exiting.")
        return None
    
    # -----------------------------------------------------------------------
    # 2. Resolve unique (LOT7, WAFER_ID, LAYER) -> WAFER_KEY + INSPECTION_TIME
    # -----------------------------------------------------------------------
    lot7_list = df["LOT7"].dropna().unique().tolist()
    layers = df["LAYER"].dropna().unique().tolist()
    
    print(f"\nStep 1: Resolving WAFER_KEY from INSP_WAFER_SUMMARY")
    print(f"  {len(lot7_list)} unique LOT7 values, layers: {layers}")
    
    conn = _connect(DATABASE)
    try:
        summary_df = _fetch_wafer_summary(conn, lot7_list, layers)
    finally:
        conn.close()
        del conn
        gc.collect()
    
    if summary_df.empty:
        print("No wafer summary records found. Check LOT7/LAYER values.")
        return None
    
    print(f"  Total INSP_WAFER_SUMMARY records: {len(summary_df)}")
    
    # -----------------------------------------------------------------------
    # 3. Match summary records to input rows (pin to INSPECT_TIME)
    # -----------------------------------------------------------------------
    summary_df["INSPECTION_TIME"] = pd.to_datetime(summary_df["INSPECTION_TIME"], errors="coerce")
    
    lookup = df[["LOT7", "WAFER_ID", "LAYER", "INSPECT_TIME_DT"]].drop_duplicates()
    merged = lookup.merge(summary_df, on=["LOT7", "WAFER_ID", "LAYER"], how="inner")
    
    # Pin to specific inspection (±1 second tolerance)
    merged["time_delta"] = (
        (merged["INSPECTION_TIME"] - merged["INSPECT_TIME_DT"])
        .abs()
        .dt.total_seconds()
    )
    matched = merged[merged["time_delta"] <= 1].copy()
    
    if matched.empty:
        print(
            "\nWARNING: Exact INSPECT_TIME match returned 0 rows. "
            "Falling back to LOT7+WAFER_ID+LAYER match only (all inspections)."
        )
        matched = merged.copy()
    
    print(f"  Matched {len(matched)} wafer inspection record(s)")
    
    if matched.empty:
        print("No matching wafer records found. Exiting.")
        return None
    
    # -----------------------------------------------------------------------
    # 4. Query defect coordinates for OTHER_UNKNOWN class
    # -----------------------------------------------------------------------
    pairs = [
        (row["INSPECTION_TIME"], int(row["WAFER_KEY"]))
        for _, row in matched.iterrows()
    ]
    pairs = list(dict.fromkeys(pairs))  # Deduplicate
    
    print(f"\nStep 2: Querying INSP_DEFECT for {len(pairs)} wafer inspections")
    print(f"  Class filter: {CLASS_FILTER}")
    
    conn = _connect(DATABASE)
    try:
        defects_df = _fetch_defect_coords(conn, pairs, class_filter=CLASS_FILTER)
    finally:
        conn.close()
        del conn
        gc.collect()
    
    if defects_df.empty:
        print("No OTHER_UNKNOWN defect records returned from database.")
        print("The input wafers may not have any OTHER_UNKNOWN class defects.")
        return None
    
    print(f"\nTotal OTHER_UNKNOWN defect records: {len(defects_df)}")
    
    # -----------------------------------------------------------------------
    # 5. Prepare result with all defect and image metadata
    # -----------------------------------------------------------------------
    # The defects_df from database provides most columns (CLASS, ACTUAL_LOT, LAYER, etc.)
    # We need to add SUBENTITY and SUBENTITY_END_TIME from the input for image organization
    for col in ("WAFER_X_MM", "WAFER_Y_MM"):
        defects_df[col] = pd.to_numeric(defects_df[col], errors="coerce")
    
    # Extract SUBENTITY and SUBENTITY_END_TIME from input CSV for image organization
    subentity_context = df[["LOT7", "WAFER_ID", "LAYER", "SUBENTITY", "SUBENTITY_END_TIME"]].drop_duplicates()
    
    # Merge with database defect data
    result = defects_df.merge(subentity_context, on=["LOT7", "WAFER_ID", "LAYER"], how="left", suffixes=('_db', ''))
    
    # Fill any missing SUBENTITY/SUBENTITY_END_TIME with defaults
    result["SUBENTITY"] = result["SUBENTITY"].fillna("ALL_CHAMBERS")
    result["SUBENTITY_END_TIME"] = result["SUBENTITY_END_TIME"].fillna(result["INSPECTION_TIME"])
    
    # CRITICAL: Ensure LOT column exists for image burn-in annotation
    # Database returns ACTUAL_LOT; we need a LOT column for the annotation function
    if "LOT" not in result.columns:
        # Use ACTUAL_LOT as LOT if available, otherwise use LOT7
        result["LOT"] = result["ACTUAL_LOT"] if "ACTUAL_LOT" in result.columns else result["LOT7"]
    
    # Normalize coordinate schema (adds YYMM column and reorders)
    result = _normalize_coordinate_schema(result)
    
    # Tidy column order (include only columns that exist)
    id_cols = ["YYMM", "LOT", "LOT7", "ACTUAL_LOT", "WAFER_ID", "LAYER",
               "WAFER_KEY", "INSPECTION_TIME", "SUBENTITY", "SUBENTITY_END_TIME"]
    coord_cols = [
        "DEFECT_ID", "CLASS", "FINEBIN", "WAFER_X_MM", "WAFER_Y_MM",
        "IMAGE_COUNT", *METROLOGY_COLS,
    ]
    
    # Build ordered column list (filter to only columns that exist in result)
    ordered = (
        [c for c in id_cols if c in result.columns]
        + [c for c in coord_cols if c in result.columns]
        + [c for c in result.columns if c not in id_cols and c not in coord_cols]
    )
    result = result[ordered]
    
    # -----------------------------------------------------------------------
    # 6. Save coordinates
    # -----------------------------------------------------------------------
    result.to_csv(coords_csv, index=False)
    print(f"\nSaved {len(result)} defect coordinate records -> {coords_csv}")
    
    print("\nSample output (first 5 records):")
    print(result[["LOT7", "WAFER_ID", "LAYER", "DEFECT_ID", "CLASS", 
                   "WAFER_X_MM", "WAFER_Y_MM", "IMAGE_COUNT"]].head().to_string())
    
    # -----------------------------------------------------------------------
    # 7. (Optional) Fetch image metadata and download via SecureFTP
    # -----------------------------------------------------------------------
    if DOWNLOAD_IMAGES:
        defects_needing_imgs = _filter_defects_needing_images(
            defects_df, image_csv, IMAGE_ID_FILTER
        )
        
        if defects_needing_imgs.empty:
            print("\nAll wafer groups fully covered in manifest — skipping image DB query.")
        else:
            n_img_groups = defects_needing_imgs.groupby(["WAFER_KEY", "INSPECTION_TIME"]).ngroups
            print(f"\nStep 3: Fetching image metadata from INSP_WAFER_IMAGE "
                  f"({n_img_groups} wafer group(s))...")
            
            conn = _connect(DATABASE)
            try:
                image_df = _fetch_image_metadata(
                    conn, defects_needing_imgs, image_id_filter=IMAGE_ID_FILTER
                )
            finally:
                conn.close()
                del conn
                gc.collect()
            
            if not image_df.empty:
                # IMPORTANT: Enrich with defect context (CLASS, LAYER, metrology)
                image_df = _enrich_image_rows_with_defect_context(image_df, result)
                image_df_new = _filter_new_images(image_df, result, image_folder)
                
                if not image_df_new.empty:
                    image_df_new = _download_images(
                        image_df_new, image_folder, APP_NAME,
                        technology=TECHNOLOGY, ftp_chunk_size=IMAGE_FTP_CHUNK_SIZE
                    )
                    
                    if not image_df_new.empty:
                        # Remove context columns that will be merged by _reorganize_images
                        # This prevents suffix issues when merging with result in _reorganize_images
                        cols_to_drop = ["SUBENTITY", "SUBENTITY_END_TIME", "LOT", "ACTUAL_LOT", "CLASS", "LAYER", "FINEBIN"]
                        image_df_new = image_df_new.drop(columns=[c for c in cols_to_drop if c in image_df_new.columns], errors="ignore")
                        
                        # Pass image_df_new to _reorganize_images
                        # The function will merge with result to get the correct annotation columns
                        image_df_new = _reorganize_images(
                            image_df_new, result, image_folder, annotate=ANNOTATE_IMAGES
                        )
                        print(f"\nImages organized to: {image_folder}")
                        
                        # Update manifest with organized paths
                        current_rows = image_df.copy()
                        existing_path_updates = _backfill_local_image_paths(
                            image_df, result, image_folder
                        )
                        for col in ("WAFER_KEY", "DEFECT_ID", "IMAGE_ID"):
                            existing_path_updates[col] = existing_path_updates[col].astype(str)
                            current_rows[col] = current_rows[col].astype(str)
                        
                        current_rows = current_rows.drop(columns=["LOCAL_IMAGE_FILE"], errors="ignore")
                        current_rows = current_rows.merge(
                            existing_path_updates,
                            on=["WAFER_KEY", "DEFECT_ID", "IMAGE_ID"],
                            how="left",
                        )
                        
                        if not image_df_new.empty and "LOCAL_IMAGE_FILE" in image_df_new.columns:
                            path_updates = image_df_new[
                                ["WAFER_KEY", "DEFECT_ID", "IMAGE_ID", "LOCAL_IMAGE_FILE"]
                            ].copy()
                            for col in ("WAFER_KEY", "DEFECT_ID", "IMAGE_ID"):
                                path_updates[col] = path_updates[col].astype(str)
                                current_rows[col] = current_rows[col].astype(str)
                            current_rows = current_rows.drop(columns=["LOCAL_IMAGE_FILE"], errors="ignore")
                            current_rows = current_rows.merge(
                                path_updates,
                                on=["WAFER_KEY", "DEFECT_ID", "IMAGE_ID"],
                                how="left",
                            )
                        
                        current_rows = _normalize_coordinate_schema(current_rows)
                        current_rows.to_csv(image_csv, index=False)
                        print(f"Image manifest saved ({len(current_rows)} total rows) -> {image_csv}")
                        
                        # Post-process: rename image files to include lot/wafer info for traceability
                        _rename_images_with_lot_wafer(current_rows, image_folder)
                        
                        # Save updated manifest with new filenames
                        current_rows.to_csv(image_csv, index=False)
                        print(f"Manifest updated with renamed file paths -> {image_csv}")
                    else:
                        print("Image download skipped due to unavailable SecureFTP runtime.")
                else:
                    print("All images already organized — no FTP needed.")
            else:
                print("No image records returned from DB.")
    else:
        print("\n(Image download skipped — set DOWNLOAD_IMAGES = True to enable)")
    
    print(f"\n{'='*70}")
    print(f"Query complete. Results saved to: {output_dir}")
    print(f"{'='*70}\n")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Ad hoc query for OTHER_UNKNOWN defects with image download",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Query the standard OTHER_UNKNOWN.csv rollup
  python query_other_unknown_adhoc.py \\
    --input-csv rollups/OTHER_UNKNOWN/OTHER_UNKNOWN.csv

  # Query with custom output directory
  python query_other_unknown_adhoc.py \\
    --input-csv rollups/OTHER_UNKNOWN/OTHER_UNKNOWN.csv \\
    --output-dir outputs/OTHER_UNKNOWN_REVIEW_20260727
        """
    )
    
    parser.add_argument(
        "--input-csv",
        required=True,
        help="Path to input NCDD CONCAT CSV (JSL query plugin format)",
    )
    
    parser.add_argument(
        "--output-dir",
        default="rollups/OTHER_UNKNOWN/query_output",
        help="Root directory for coordinates, images, and manifest (default: rollups/OTHER_UNKNOWN/query_output)",
    )
    
    args = parser.parse_args()
    
    try:
        query_other_unknown(args.input_csv, args.output_dir)
    except Exception as exc:
        print(f"\nERROR: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
