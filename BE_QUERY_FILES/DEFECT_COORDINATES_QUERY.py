"""
DEFECT_COORDINATES_QUERY.py
---------------------------
Queries UDB (D1D_PROD_YAS_1278) for individual adder-defect X/Y coordinates,
CLASS, and FINEBIN for wafers present in the NCDD CONCAT output CSV.

Flow:
  1. Load 8M5CL_8M6CL_NCDD_60DAY.csv (CONCAT output)
  2. Optionally filter rows (by layer, lot list, status, n_rows)
  3. Query udb.INSP_WAFER_SUMMARY to resolve WAFER_KEY + INSPECTION_TIME
     for each unique (LOT7, WAFER_ID, LAYER) combination
  4. Match back to CONCAT's specific INSPECT_TIME to pin to the right
     inspection session (avoids multiple-inspection ambiguity)
  5. Query UDB.INSP_DEFECT with the resolved (INSPECTION_TIME, WAFER_KEY)
     pairs to retrieve per-defect coordinate data
  6. Join NCDD context columns back and save to CSV
  7. (Optional) Query UDB.INSP_WAFER_IMAGE for image file paths and
     download via SecureFTP (set DOWNLOAD_IMAGES = True to enable)

Intended for eventual incorporation into 8M5CL_8M6CL_CONCAT.py.

Database:  D1D_PROD_YAS_1278  (PyUber)
"""

import gc
import os
import re
from pathlib import Path
import PyUber
import pandas as pd
from pipeline_config import PIPELINE_PATHS, ensure_pipeline_dirs, validate_pipeline_paths, write_artifact_manifest

# ---------------------------------------------------------------------------
# CONFIGURATION  -- edit these for each test run
# ---------------------------------------------------------------------------

NCDD_CSV = (
    str(PIPELINE_PATHS.extended_output_csv)
)

OUTPUT_CSV = (
    str(PIPELINE_PATHS.defect_coordinates_csv)
)

# NCDD_CSV = (
#     r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME"
#     r"\tbatson\Defects\BE\8M5CL_8M6CL_202606.csv"
# )

# OUTPUT_CSV = (
#     r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME"
#     r"\tbatson\Defects\BE_60day\BE_60day_QUERY_FILES\DEFECT_COORDINATES_365.csv"
# )


DATABASE = "D1D_PROD_YAS_1278"

# --- Optional filters (set to None to disable) ---

# Limit to the first N rows of the CONCAT CSV (useful for quick tests)
N_ROWS = None

# Filter to specific layers.  e.g. ['8M5CL'] or ['8M5CL','8M6CL'] or None
LAYER_FILTER = None  # None = both layers

# Filter to specific LOT7 values.  e.g. ['D550182','D550963'] or None
LOT_FILTER = None

# Filter to specific STATUS values.  e.g. ['HIGHFLIER'] or None
STATUS_FILTER = None

# Filter defect CLASS names returned by the coordinate query.
# Applied as a SQL WHERE filter so only matching defects are fetched.
# Set to None to return all classes.
CLASS_FILTER = ['SMALL_PARTICLE', 'BEEP']

# Query only a recent overlap window from the accumulated wafer-level table.
# This keeps DB load bounded while allowing recent reclassifications to replace
# older coordinate rows in the accumulated output.
RECENT_LOOKBACK_DAYS = 10
IMAGE_RETENTION_DAYS = 60
AMBIGUOUS_CLASSES = ['OTHER_UNKNOWN', 'UNCLASSIFIED', 'NVD_FALSE']
AMBIGUOUS_IMAGE_FOLDER = 'AMBIGUOUS_REVIEW'

# ---------------------------------------------------------------------------
# IMAGE DOWNLOAD (optional) -- requires SecureFTP / Intel.FabAuto.Quarc.Utilities
# ---------------------------------------------------------------------------

# Set to True to query UDB.INSP_WAFER_IMAGE and download images via SecureFTP.
DOWNLOAD_IMAGES = True

# Local folder where downloaded images will be saved (created if absent).
IMAGE_OUTPUT_FOLDER = (
    str(PIPELINE_PATHS.image_dir)
)

# Candidate GAJT folders that may contain Intel.FabAuto.Quarc.Utilities.
# ScriptHost jobs usually use D:\gajtv\configurations\wijt while local JMP
# runs typically resolve from the user AddIns path.
GAJT_DLL_SEARCH_PATHS = [
    r"D:\gajtv\configurations\wijt",
    r"C:\Users\tbatson\AppData\Roaming\SAS\JMP\AddIns\gajtv.intel.com\wijt",
]

# Application credential name for SecureFTP authentication (securekey / AppName).
# The value is JMP-encrypted and stored in:
#   ...\gajtv.intel.com\Tools\Standard\GetData\DrilldownQueries\xSupport\InlineAppName.jsl
# To extract the plaintext, run this one-liner in the JMP Script Editor (Ctrl+Shift+E):
#   Print( Include("C:\Users\tbatson\AppData\Roaming\SAS\JMP\AddIns\gajtv.intel.com\Tools\Standard\GetData\DrilldownQueries\xSupport\InlineAppName.jsl") );
# Copy the printed value from the JMP log and paste it below.
# NOTE: GAJT_INLINE_24601 is the shared app identity deployed by the GAJT addin.
# It is acceptable for authorized personal automation, but consider registering
# a dedicated AppName with IT before scheduling this as a production job.
APP_NAME = "GAJT_INLINE_24601"

# Technology string matching <Technology> in the GAJT task XML.
# Used to build the FTP datasource: '{QUERY_SITE}_PROD_YAS_{TECHNOLOGY}_FTP'
TECHNOLOGY = "1278"

# Which IMAGE_IDs to retrieve from INSP_WAFER_IMAGE and download.
#   1 = low-res scan overview (.png)  -- quick situational context, rarely needed
#   2 = brightfield review (.jpg)     -- primary image
#   3 = darkfield review (.jpg)       -- secondary contrast
#   4/5 = extra review-arm pairs      -- only present for high-priority defects
# Set to None to pull all IMAGE_IDs.
IMAGE_ID_FILTER = [2, 3]

# Max IMAGE_FILESPEC paths sent in a single SecureFTP.FtpFiles() call.
# The FTP server accepts a comma-separated list; very long strings can time out
# or be silently truncated on large runs.  50 is conservative and safe.
IMAGE_FTP_CHUNK_SIZE = 50

# Set to True to burn lot/wafer/layer metadata into each downloaded image.
# Requires Pillow (pip install pillow).  Falls back gracefully if not installed.
ANNOTATE_IMAGES = True

# Columns from the CONCAT to carry through to the final defect output
CONTEXT_COLS = [
    "LOT", "LOT7", "WAFER_ID", "LAYER",
    "SUBENTITY", "RECIPE", "SUBENTITY_END_TIME", "INSPECT_TIME", "INSPECT_TOOL",
    "SRCIP", "CCMR2", "ICCR2", "CV", "GF", "TS",
    "PILOT_STATUS", "SUM_NCDD", "STATUS", "BEEP_NCDD", "SMP_NCDD"
]

# Max number of (INSPECTION_TIME, WAFER_KEY) pairs per INSP_DEFECT query chunk
# (Oracle row-value IN clause; keep conservative)
DEFECT_CHUNK_SIZE = 500

# Max number of LOT7 values per INSP_WAFER_SUMMARY query chunk
# (controls size of the LIKE clause block)
LOT_CHUNK_SIZE = 30

# Required columns that must be present in the CONCAT CSV.
_REQUIRED_COLUMNS = {"LOT7", "WAFER_ID", "LAYER", "INSPECT_TIME"}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _build_like_clause(lot7_list):
    """Return an OR-joined set of LOT_ID LIKE conditions for a list of LOT7s."""
    parts = [f"s.LOT_ID LIKE '{_sanitize_identifier(lot7)}%' ESCAPE '\\'" for lot7 in lot7_list]
    return " OR ".join(parts)


def _sanitize_identifier(value):
    """
    Strip any character that is not alphanumeric or underscore from a value
    before it is interpolated into SQL.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", str(value))
    if not cleaned:
        raise ValueError(f"SQL identifier sanitized to empty string from input: {value!r}")
    return cleaned


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


def _fetch_wafer_summary(conn, lot7_list, layers):
    """
    Query INSP_WAFER_SUMMARY in chunks and return a combined DataFrame.

    Returned columns:
        WAFER_KEY, INSPECTION_TIME, WAFER_ID (scribe), LOT7, ACTUAL_LOT,
        LAYER, INSPECTION_TOOL, WAFER_NUM (numeric), CENTER_X, CENTER_Y,
        N_DEFECTS, ADDER_DEFECTS
    """
    layer_in = ", ".join([f"'{l}'" for l in layers])
    all_chunks = []

    for i in range(0, len(lot7_list), LOT_CHUNK_SIZE):
        chunk_lots = lot7_list[i : i + LOT_CHUNK_SIZE]
        like_clause = _build_like_clause(chunk_lots)

        sql = f"""
SELECT
    s.WAFER_KEY,
    s.INSPECTION_TIME,
    s.SCRIBE_ID                    AS WAFER_ID,
    SUBSTR(s.LOT_ID, 1, 7)         AS LOT7,
    s.LOT_ID                       AS ACTUAL_LOT,
    s.LAYER_ID                     AS LAYER,
    s.INSPECT_EQUIP_ID             AS INSPECTION_TOOL,
    s.WAFER_ID                     AS WAFER_NUM,
    s.CENTER_X,
    s.CENTER_Y,
    s.DEFECTS                      AS N_DEFECTS,
    s.ADDER_DEFECTS
FROM udb.INSP_WAFER_SUMMARY s
WHERE ({like_clause})
  AND s.LAYER_ID IN ({layer_in})
  AND NVL(LENGTH(TRIM(TRANSLATE(s.WAFER_ID, ' 0123456789', ' '))), 0) = 0
"""
        print(
            f"  [INSP_WAFER_SUMMARY] chunk {i // LOT_CHUNK_SIZE + 1}: "
            f"{len(chunk_lots)} lots..."
        )
        chunk_df = pd.read_sql(sql, conn)
        print(f"    -> {len(chunk_df)} rows")
        all_chunks.append(chunk_df)

    if not all_chunks:
        return pd.DataFrame()
    return pd.concat(all_chunks, ignore_index=True)


def _fetch_defect_coords(conn, pairs, class_filter=None):
    """
    Query UDB.INSP_DEFECT for adder defects given a list of
    (INSPECTION_TIME datetime, WAFER_KEY int) tuples.

    Parameters
    ----------
    class_filter : list of str or None
        When provided, only defects whose CLASS name is in this list are
        returned (filter applied in SQL).  e.g. ['SMALL_PARTICLE', 'BEEP']

    Returned columns:
        WAFER_KEY, INSPECTION_TIME, WAFER_ID (scribe), LOT7, ACTUAL_LOT,
        LAYER, DEFECT_ID, CLASS, FINEBIN, WAFER_X_MM, WAFER_Y_MM, IMAGE_COUNT
    """
    class_sql_filter = ""
    if class_filter:
        quoted = ", ".join(f"'{_sanitize_identifier(c)}'" for c in class_filter)
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
            f"{len(chunk)} wafers..."
        )
        chunk_df = pd.read_sql(sql, conn)
        print(f"    -> {len(chunk_df)} defect records")
        all_chunks.append(chunk_df)

    if not all_chunks:
        return pd.DataFrame()
    return pd.concat(all_chunks, ignore_index=True)


def _fetch_image_metadata(conn, defects_df, image_id_filter=None):
    """
    Query UDB.INSP_WAFER_IMAGE for image file paths for defects in
    defects_df that have IMAGE_COUNT > 0.

    Mirrors GetSurfscanImages.SelectSQL() / FromSQL() / WhereSQL().
    Iterates one (WAFER_KEY, INSPECTION_TIME) group at a time, passing
    the matching DEFECT_IDs — identical to the plugin's ForEachSQLStatement.

    image_id_filter : list of int or None
        When set, only rows whose IMAGE_ID is in this list are returned.
        e.g. [2, 3] fetches only the brightfield/darkfield pair.

    Returns a DataFrame with columns:
        SITE, QUERY_SITE, WAFER_KEY, INSPECTION_TIME, DEFECT_ID,
        IMAGE_ID, IMAGE_SERVER_ID, IMAGE_FILESPEC
    """
    df = defects_df.copy()
    df["_IMG_CNT"] = pd.to_numeric(df["IMAGE_COUNT"], errors="coerce").fillna(0).astype(int)
    df = df[df["_IMG_CNT"] > 0]

    if df.empty:
        print("  No defects with IMAGE_COUNT > 0 — skipping image metadata query.")
        return pd.DataFrame()

    groups = df.groupby(["WAFER_KEY", "INSPECTION_TIME"])
    print(f"  [INSP_WAFER_IMAGE] querying {len(groups)} wafer inspections...")
    all_chunks = []

    for (wafer_key, insp_time), group in groups:
        defect_ids = ", ".join(
            str(int(float(d))) for d in group["DEFECT_ID"].dropna().unique()
        )
        if not defect_ids:
            continue
        insp_time_str = pd.Timestamp(insp_time).strftime("%Y%m%d%H%M%S")

        img_id_clause = ""
        if image_id_filter:
            id_list = ", ".join(str(i) for i in image_id_filter)
            img_id_clause = f"  AND i.IMAGE_ID IN ({id_list})"

        sql = f"""
SELECT 'D1V'                    AS SITE,
       'D1D'                    AS QUERY_SITE,
       i.WAFER_KEY,
       i.INSPECTION_TIME,
       i.DEFECT_ID,
       i.IMAGE_ID,
       i.IMAGE_SERVER_ID,
       i.IMAGE_FILESPEC
FROM UDB.INSP_WAFER_IMAGE i
WHERE i.WAFER_KEY = {int(wafer_key)}
  AND i.INSPECTION_TIME = TO_DATE('{insp_time_str}','YYYYMMDDHH24MISS')
  AND i.DEFECT_ID IN ({defect_ids}){img_id_clause}
"""
        chunk_df = pd.read_sql(sql, conn)
        all_chunks.append(chunk_df)

    if not all_chunks:
        return pd.DataFrame()

    result = pd.concat(all_chunks, ignore_index=True)
    print(f"    -> {len(result)} image records found")
    return result


def _sanitize_path_token(value):
    token = str(value or "UNKNOWN").strip()
    for char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
        token = token.replace(char, '_')
    return token or "UNKNOWN"


def _build_image_destination(row, image_folder):
    class_abbrev = {"SMALL_PARTICLE": "SMP"}

    end_ts = pd.to_datetime(row.get("SUBENTITY_END_TIME"), errors="coerce")
    ts = end_ts.strftime("%y%m%d_%H%M") if not pd.isna(end_ts) else "000000_0000"

    lot7 = _sanitize_path_token(row.get("LOT7", "UNK"))
    waf_raw = str(row.get("WAFER_ID", "")).strip()
    short_w = _sanitize_path_token(waf_raw[5:8] if len(waf_raw) >= 8 else waf_raw)
    cls_raw = _sanitize_path_token(row.get("CLASS", "UNK"))
    cls = _sanitize_path_token(class_abbrev.get(cls_raw, cls_raw))
    layer = _sanitize_path_token(row.get("LAYER", ""))
    defid = str(int(row["_DID"])) if pd.notna(row.get("_DID")) else "0"
    picid = str(int(float(row["IMAGE_ID"]))) if pd.notna(row.get("IMAGE_ID")) else "0"
    spec = str(row.get("IMAGE_FILESPEC", ""))
    ext = os.path.splitext(spec)[1].lower() if spec else ".jpg"

    subentity = _sanitize_path_token(row.get("SUBENTITY", "UNKNOWN"))
    if cls_raw in AMBIGUOUS_CLASSES:
        dest_dir = os.path.join(image_folder, AMBIGUOUS_IMAGE_FOLDER, cls_raw, subentity)
    else:
        dest_dir = os.path.join(image_folder, subentity)

    fname = f"{ts}_{lot7}_{short_w}_{cls}_{layer}_{defid}_{picid}{ext}"
    return os.path.join(dest_dir, fname)


def _retire_stale_reclassified_images(existing_manifest, current_rows):
    if existing_manifest.empty or current_rows.empty:
        return 0

    existing = existing_manifest.copy()
    current = current_rows.copy()
    key_cols = ["WAFER_KEY", "DEFECT_ID", "IMAGE_ID"]

    for col in key_cols:
        existing[col] = existing[col].astype(str)
        current[col] = current[col].astype(str)

    joined = existing.merge(
        current[key_cols + ["LOCAL_IMAGE_FILE"]],
        on=key_cols,
        how="inner",
        suffixes=("_old", "_new"),
    )
    stale = joined[
        joined["LOCAL_IMAGE_FILE_old"].notna()
        & joined["LOCAL_IMAGE_FILE_new"].notna()
        & (joined["LOCAL_IMAGE_FILE_old"] != joined["LOCAL_IMAGE_FILE_new"])
    ]

    deleted = 0
    for path in stale["LOCAL_IMAGE_FILE_old"].dropna().unique().tolist():
        try:
            if os.path.isfile(path):
                os.remove(path)
                deleted += 1
        except OSError as exc:
            print(f"  WARNING: Could not remove stale image {path} ({exc})")
    if deleted:
        print(f"  Retired {deleted} stale reclassified image(s)")
    return deleted


def _cleanup_empty_dirs(root_dir):
    if not os.path.isdir(root_dir):
        return
    for current_root, dirs, files in os.walk(root_dir, topdown=False):
        if current_root == root_dir:
            continue
        if not dirs and not files:
            try:
                os.rmdir(current_root)
            except OSError:
                pass


def _prune_old_images(manifest_path, image_folder, retention_days, active_overlap_days):
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        return 0

    try:
        manifest = pd.read_csv(manifest_file, low_memory=False)
    except Exception as exc:
        print(f"  WARNING: Could not read image manifest for pruning ({exc})")
        return 0

    if manifest.empty or "LOCAL_IMAGE_FILE" not in manifest.columns:
        return 0

    time_col = "SUBENTITY_END_TIME" if "SUBENTITY_END_TIME" in manifest.columns else "INSPECTION_TIME"
    manifest[time_col] = pd.to_datetime(manifest[time_col], errors="coerce")
    newest_ts = manifest[time_col].max()
    if pd.isna(newest_ts):
        return 0

    prune_before = newest_ts - pd.Timedelta(days=retention_days)
    overlap_floor = newest_ts - pd.Timedelta(days=active_overlap_days)
    candidates = manifest[
        manifest[time_col].notna()
        & (manifest[time_col] < prune_before)
        & (manifest[time_col] < overlap_floor)
        & manifest["LOCAL_IMAGE_FILE"].notna()
    ].copy()

    if candidates.empty:
        return 0

    deleted = 0
    deleted_paths = set()
    for path in candidates["LOCAL_IMAGE_FILE"].dropna().unique().tolist():
        try:
            if os.path.isfile(path):
                os.remove(path)
                deleted += 1
            deleted_paths.add(path)
        except OSError as exc:
            print(f"  WARNING: Could not prune old image {path} ({exc})")

    if deleted_paths:
        remaining = manifest[~manifest["LOCAL_IMAGE_FILE"].isin(deleted_paths)].copy()
        remaining.to_csv(manifest_file, index=False)
        _cleanup_empty_dirs(image_folder)

    if deleted:
        print(f"  Pruned {deleted} image(s) older than {retention_days} days")
    return deleted


def _download_images(image_df, image_folder, app_name, technology="1278",
                     ftp_chunk_size=50):
    """
    Download defect images via SecureFTP.

    Mirrors GetSurfscanImages.PostProcessData() exactly:
      - Groups IMAGE_FILESPEC paths by QUERY_SITE
      - Builds datasource as '{query_site}_PROD_YAS_{technology}_FTP'
      - Calls SecureFTP.FtpFiles(site, ds, files_csv, folder, securekey)
        once per site group

    IMAGE_FILESPEC from the DB is a relative path, e.g.:
      yas\\data\\images21\\rf3pap1118x005\\20260310\\03\\1748_3260850\\...jpg
    The full local path after download is: os.path.join(image_folder, IMAGE_FILESPEC)

    Returns image_df with a LOCAL_IMAGE_FILE column appended.
    """
    import os
    import sys
    import clr

    # Add known GAJT folders to the CLR assembly search path so the same code
    # can run on ScriptHost and local workstations.
    for dll_dir in GAJT_DLL_SEARCH_PATHS:
        if os.path.isdir(dll_dir) and dll_dir not in sys.path:
            sys.path.append(dll_dir)

    try:
        clr.AddReference("Intel.FabAuto.Quarc.Utilities")
        SecureFTP = __import__("Intel.FabAuto.Quarc", fromlist=["SecureFTP"]).SecureFTP
    except Exception as exc:
        print("  WARNING: SecureFTP runtime unavailable; skipping image download for this run.")
        print(f"  SEARCH_PATHS: {GAJT_DLL_SEARCH_PATHS}")
        print(f"  DETAIL: {exc}")
        # Return empty frame so caller can safely skip image reorg/manifest updates.
        return pd.DataFrame()

    os.makedirs(image_folder, exist_ok=True)

    df = image_df.copy()
    # IMAGE_FILESPEC from the DB starts with a leading '/' (e.g. /yas/data/...)
    # Strip it before joining so os.path.join doesn't treat it as an absolute
    # path and discard image_folder entirely (Windows behaviour).
    df["LOCAL_IMAGE_FILE"] = df["IMAGE_FILESPEC"].apply(
        lambda p: os.path.join(image_folder, p.lstrip("/\\").replace("/", os.sep))
                  if pd.notna(p) else None
    )

    # Group by QUERY_SITE -- mirrors filelist[query_site] in PostProcessData
    query_site_col = "QUERY_SITE" if "QUERY_SITE" in df.columns else "SITE"
    for query_site, grp in df.groupby(query_site_col):
        files = grp["IMAGE_FILESPEC"].dropna().unique().tolist()
        if not files:
            continue
        ds = f"{query_site}_PROD_YAS_{technology}_FTP"
        total = len(files)

        # Skip files already present in the staging tree from a prior interrupted run.
        # The staging path is image_folder + relative IMAGE_FILESPEC (leading slash stripped).
        files_to_dl = [
            spec for spec in files
            if not os.path.isfile(
                os.path.join(image_folder, spec.lstrip("/\\").replace("/", os.sep))
            )
        ]
        n_cached = total - len(files_to_dl)
        if n_cached:
            print(f"  [{query_site}] {n_cached}/{total} already in staging cache — skipping FTP for those")

        if not files_to_dl:
            print(f"  [{query_site}] All {total} file(s) already staged — no FTP needed.")
        else:
            n_dl = len(files_to_dl)
            print(f"  [{query_site}] Downloading {n_dl}/{total} file(s) via {ds} -> {image_folder}")
            for chunk_start in range(0, n_dl, ftp_chunk_size):
                chunk = files_to_dl[chunk_start : chunk_start + ftp_chunk_size]
                chunk_num = chunk_start // ftp_chunk_size + 1
                total_chunks = (n_dl + ftp_chunk_size - 1) // ftp_chunk_size
                print(f"    chunk {chunk_num}/{total_chunks} ({len(chunk)} files)...")
                SecureFTP.FtpFiles(query_site, ds, ",".join(chunk), image_folder, app_name)
            print(f"  [{query_site}] Download complete.")

    return df


def _reorganize_images(image_df, defects_result, image_folder, annotate=False):
    """
    Move downloaded images from the SecureFTP staging tree into a flat,
    human-readable structure:

        {image_folder}/{SUBENTITY}/yymmdd_hhmm_lot7_wafid_class_layer_defid_picid.ext

    Timestamp comes from SUBENTITY_END_TIME (from the NCDD context joined onto
    defects_result) rather than INSPECTION_TIME, so that images for a wafer
    that inspects near midnight sort correctly within a chamber folder.

    Wafer short-ID: 3-digit slice starting at position 5 of WAFER_ID
        e.g.  GS9YT027JKH1  ->  027
              MCFFQ020WAD4  ->  020

    CLASS abbreviation: SMALL_PARTICLE -> SMP, all others kept as-is.

    After copying all files the staging 'yas' subfolder is removed.
    Returns image_df with LOCAL_IMAGE_FILE updated to the new organized paths.
    """
    import shutil

    # -- Pillow annotation helper (no-op if Pillow not installed) --
    def _annotate(path, label_top, label_bot):
        """Burn two lines of text onto the image in-place."""
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return  # Pillow not available — skip silently
        try:
            img = Image.open(path).convert("RGB")
            w, h = img.size
            draw = ImageDraw.Draw(img)
            # Use a proportional font size (~5 % of shorter dimension)
            font_size = max(24, int(min(w, h) * 0.05))
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except OSError:
                font = ImageFont.load_default(size=font_size)  # Pillow >= 10.0
            pad = max(4, font_size // 4)
            # Draw solid black banner with pure Pillow (no NumPy dependency).
            banner_h = font_size * 2 + pad * 3
            banner = Image.new("RGB", (w, banner_h), (0, 0, 0))
            img.paste(banner, (0, h - banner_h))
            draw = ImageDraw.Draw(img)
            draw.text((pad, h - banner_h + pad),       label_top, fill="white", font=font)
            draw.text((pad, h - banner_h + font_size + pad*2), label_bot, fill="#FFDD88", font=font)
            img.save(path, quality=92)
        except Exception:
            pass  # never crash the pipeline over annotation

    # ---- normalize join keys to a common integer type ----
    img = image_df.copy()
    img["_WK"]  = pd.to_numeric(img["WAFER_KEY"],  errors="coerce").astype("Int64")
    img["_DID"] = pd.to_numeric(img["DEFECT_ID"],  errors="coerce").astype("Int64")

    ctx = defects_result.copy()
    ctx["_WK"]  = pd.to_numeric(ctx["WAFER_KEY"],  errors="coerce").astype("Int64")
    ctx["_DID"] = pd.to_numeric(ctx["DEFECT_ID"],  errors="coerce").astype("Int64")

    wanted = [c for c in ["_WK", "_DID", "LOT", "LOT7", "ACTUAL_LOT", "WAFER_ID",
                           "CLASS", "LAYER", "SUBENTITY", "SUBENTITY_END_TIME"]
              if c in ctx.columns]
    ctx_small = ctx[wanted].drop_duplicates(subset=["_WK", "_DID"])

    merged = img.merge(ctx_small, on=["_WK", "_DID"], how="left")

    new_paths = []
    n_skipped = n_copied = n_missing = 0
    for _, row in merged.iterrows():
        src = row.get("LOCAL_IMAGE_FILE")
        if src:
            # Normalize any residual forward slashes to backslashes
            src = os.path.normpath(str(src))

        end_ts = pd.to_datetime(row.get("SUBENTITY_END_TIME"), errors="coerce")
        ts       = end_ts.strftime("%y%m%d_%H%M") if not pd.isna(end_ts) else "000000_0000"
        ts_label = end_ts.strftime("%Y/%m/%d %H:%M") if not pd.isna(end_ts) else "0000/00/00 00:00"

        # -- lot / wafer --
        lot7    = str(row.get("LOT7", "UNK")).strip()
        # Prefer full LOT from NCDD context; fall back to ACTUAL_LOT from DB, then LOT7
        full_lot = str(row.get("LOT") or row.get("ACTUAL_LOT") or lot7).strip()
        waf_raw = str(row.get("WAFER_ID", "")).strip()
        short_w = waf_raw[5:8] if len(waf_raw) >= 8 else waf_raw

        cls_raw = str(row.get("CLASS", "UNK")).strip()
        cls = _sanitize_path_token({"SMALL_PARTICLE": "SMP"}.get(cls_raw, cls_raw))

        layer  = str(row.get("LAYER", "")).strip()
        defid  = str(int(row["_DID"])) if pd.notna(row["_DID"]) else "0"
        picid  = str(int(float(row["IMAGE_ID"]))) if pd.notna(row.get("IMAGE_ID")) else "0"
        subentity = str(row.get("SUBENTITY", "UNKNOWN")).strip() or "UNKNOWN"
        dest = _build_image_destination(row, image_folder)
        dest_dir = os.path.dirname(dest)
        os.makedirs(dest_dir, exist_ok=True)

        if os.path.isfile(dest):
            # Already organized from a previous run — no copy or re-annotation needed
            new_paths.append(dest)
            n_skipped += 1
        elif src and os.path.isfile(src):
            shutil.copy2(src, dest)
            if annotate:
                line1 = f"{ts_label} {subentity} {layer}"
                line2 = f"{full_lot} W{short_w} ID{defid} {cls}  #{picid}"
                _annotate(dest, line1, line2)
            new_paths.append(dest)
            n_copied += 1
        else:
            new_paths.append(None)
            n_missing += 1

    img["LOCAL_IMAGE_FILE"] = new_paths
    img.drop(columns=["_WK", "_DID"], inplace=True, errors="ignore")

    print(f"  Organize: {n_copied} copied+annotated, {n_skipped} already present (skipped), "
          f"{n_missing} source not found (unavailable server/missing file)")

    # -- remove SecureFTP staging tree (guarded) --
    staging_root = os.path.join(image_folder, "yas")
    expected_parent = os.path.normpath(image_folder)
    actual_parent = os.path.normpath(os.path.dirname(staging_root))
    if os.path.isdir(staging_root) and actual_parent == expected_parent:
        shutil.rmtree(staging_root)
        print(f"  Staging tree removed: {staging_root}")
    elif os.path.isdir(staging_root):
        print(
            f"  WARNING: Staging root '{staging_root}' is not a direct child of "
            f"'{image_folder}' — skipping delete for safety."
        )

    return img


def _filter_new_images(image_df, defects_result, image_folder):
    """
    Return the subset of image_df whose organized destination does not yet exist
    on disk.  Pre-computes the filename that _reorganize_images would create for
    each row and skips any already present, avoiding unnecessary FTP downloads
    when re-running against a 60-day window that overlaps a prior pull.
    """
    img = image_df.copy()
    img["_WK"]  = pd.to_numeric(img["WAFER_KEY"],  errors="coerce").astype("Int64")
    img["_DID"] = pd.to_numeric(img["DEFECT_ID"],  errors="coerce").astype("Int64")

    ctx = defects_result.copy()
    ctx["_WK"]  = pd.to_numeric(ctx["WAFER_KEY"],  errors="coerce").astype("Int64")
    ctx["_DID"] = pd.to_numeric(ctx["DEFECT_ID"],  errors="coerce").astype("Int64")

    wanted = [c for c in ["_WK", "_DID", "LOT7", "WAFER_ID", "CLASS", "LAYER",
                           "SUBENTITY", "SUBENTITY_END_TIME"]
              if c in ctx.columns]
    ctx_small = ctx[wanted].drop_duplicates(subset=["_WK", "_DID"])
    merged = img.merge(ctx_small, on=["_WK", "_DID"], how="left")

    def _dest(row):
        return _build_image_destination(row, image_folder)

    already_exists = merged.apply(lambda r: os.path.isfile(_dest(r)), axis=1)
    n_exist = int(already_exists.sum())
    n_total = len(image_df)

    if n_exist:
        print(f"  Pre-filter: {n_exist}/{n_total} images already organized — "
              f"skipping FTP for those")
    else:
        print(f"  Pre-filter: all {n_total} images are new")

    return image_df[~already_exists.values].copy()


def _backfill_local_image_paths(image_df, defects_result, image_folder):
    """
    Build LOCAL_IMAGE_FILE mappings for image rows that already exist on disk.

    This is used to keep the manifest populated even when files were skipped from
    FTP (already organized) or migrated previously.
    """
    img = image_df.copy()
    img["_WK"] = pd.to_numeric(img["WAFER_KEY"], errors="coerce").astype("Int64")
    img["_DID"] = pd.to_numeric(img["DEFECT_ID"], errors="coerce").astype("Int64")

    ctx = defects_result.copy()
    ctx["_WK"] = pd.to_numeric(ctx["WAFER_KEY"], errors="coerce").astype("Int64")
    ctx["_DID"] = pd.to_numeric(ctx["DEFECT_ID"], errors="coerce").astype("Int64")

    wanted = [
        c for c in [
            "_WK", "_DID", "LOT7", "WAFER_ID", "CLASS", "LAYER",
            "SUBENTITY", "SUBENTITY_END_TIME",
        ]
        if c in ctx.columns
    ]
    ctx_small = ctx[wanted].drop_duplicates(subset=["_WK", "_DID"])
    merged = img.merge(ctx_small, on=["_WK", "_DID"], how="left")

    resolved = []
    for _, row in merged.iterrows():
        dest = _build_image_destination(row, image_folder)
        resolved.append(dest if os.path.isfile(dest) else None)

    out = merged[["WAFER_KEY", "DEFECT_ID", "IMAGE_ID"]].copy()
    out["LOCAL_IMAGE_FILE"] = resolved
    return out


def _filter_defects_needing_images(defects_df, manifest_path, image_id_filter):
    """
    Pre-filter defects_df to only those wafer inspection groups that are NOT
    yet fully covered in the image manifest CSV.

    A (WAFER_KEY, INSPECTION_TIME) group is considered "complete" when every
    defect with IMAGE_COUNT > 0 already has a manifest entry for each IMAGE_ID
    in image_id_filter.  Complete groups are excluded so _fetch_image_metadata
    makes zero DB round-trips for them.

    On the very first run the manifest may be sparse (or absent); subsequent
    runs benefit progressively as the manifest accumulates.

    Returns the filtered subset of defects_df (or the full DataFrame if the
    manifest is missing/unreadable), plus prints a coverage summary.
    """
    import os

    n_groups = defects_df.groupby(["WAFER_KEY", "INSPECTION_TIME"]).ngroups

    if not os.path.isfile(manifest_path):
        print(f"  No existing image manifest — all {n_groups} wafer group(s) will be queried.")
        return defects_df

    try:
        manifest = pd.read_csv(manifest_path, dtype=str, low_memory=False)
    except Exception as exc:
        print(f"  WARNING: Cannot read image manifest ({exc}) — querying all groups.")
        return defects_df

    if manifest.empty:
        print(f"  Image manifest is empty — all {n_groups} wafer group(s) will be queried.")
        return defects_df

    required_ids = set(image_id_filter) if image_id_filter else {2, 3}

    # Build lookup set of (WK, DID, IID) tuples already in the manifest
    m = manifest.copy()
    m["_WK"]  = pd.to_numeric(m["WAFER_KEY"],  errors="coerce")
    m["_DID"] = pd.to_numeric(m["DEFECT_ID"],  errors="coerce")
    m["_IID"] = pd.to_numeric(m["IMAGE_ID"],   errors="coerce")
    manifest_set = set(zip(m["_WK"], m["_DID"], m["_IID"]))

    df = defects_df.copy()
    df["_WK"]      = pd.to_numeric(df["WAFER_KEY"],  errors="coerce")
    df["_DID"]     = pd.to_numeric(df["DEFECT_ID"],  errors="coerce")
    df["_IMG_CNT"] = pd.to_numeric(
        df["IMAGE_COUNT"] if "IMAGE_COUNT" in df.columns else pd.Series(0, index=df.index),
        errors="coerce"
    ).fillna(0).astype(int)

    # Build expected (WK, DID, IID) combinations for defects that have images
    has_imgs = df[df["_IMG_CNT"] > 0][["_WK", "_DID", "WAFER_KEY", "INSPECTION_TIME"]]
    if has_imgs.empty:
        print("  No defects with IMAGE_COUNT > 0 — skipping image queries.")
        return pd.DataFrame(columns=defects_df.columns)

    parts = []
    for iid in required_ids:
        tmp = has_imgs.copy()
        tmp["_IID"] = float(iid)
        parts.append(tmp)
    expected = pd.concat(parts, ignore_index=True)

    # Vectorized membership check
    expected["_FOUND"] = [
        (wk, did, iid) in manifest_set
        for wk, did, iid in zip(expected["_WK"], expected["_DID"], expected["_IID"])
    ]

    # Incomplete groups = those with at least one missing expected entry
    missing = expected[~expected["_FOUND"]][["WAFER_KEY", "INSPECTION_TIME"]].drop_duplicates()
    n_incomplete = len(missing)
    n_complete   = n_groups - n_incomplete

    print(
        f"  Image manifest pre-filter: {n_complete}/{n_groups} wafer group(s) fully covered"
        f" — {n_incomplete} group(s) still need DB image queries"
    )

    if n_incomplete == 0:
        return pd.DataFrame(columns=defects_df.columns)

    # Inner-join to return only rows belonging to incomplete groups
    filtered = defects_df.merge(missing, on=["WAFER_KEY", "INSPECTION_TIME"], how="inner")
    return filtered


def _filter_recent_rows(df, output_csv, lookback_days):
    if lookback_days is None:
        return df

    recent_df = df.copy()
    recent_df["INSPECT_TIME_DT"] = pd.to_datetime(recent_df["INSPECT_TIME"], errors="coerce")
    max_time = recent_df["INSPECT_TIME_DT"].max()
    if pd.isna(max_time):
        return recent_df

    cutoff = max_time - pd.Timedelta(days=lookback_days)
    output_path = Path(output_csv)
    if output_path.exists():
        try:
            existing = pd.read_csv(output_path, usecols=["INSPECTION_TIME"])
            existing["INSPECTION_TIME"] = pd.to_datetime(existing["INSPECTION_TIME"], errors="coerce")
            existing_max = existing["INSPECTION_TIME"].max()
            if pd.notna(existing_max):
                cutoff = existing_max - pd.Timedelta(days=lookback_days)
        except Exception as exc:
            print(f"WARNING: Could not read existing coordinates output for overlap cutoff ({exc})")

    filtered = recent_df[recent_df["INSPECT_TIME_DT"] >= cutoff].copy()
    print(
        f"  Recent overlap filter: {len(filtered)}/{len(df)} rows retained "
        f"from {cutoff.strftime('%Y-%m-%d %H:%M:%S')} forward"
    )
    return filtered


def _accumulate_coordinates(result, output_csv):
    output_path = Path(output_csv)
    key_cols = ["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"]

    # Transitional migration support:
    # seed accumulation from both legacy root-level coordinates and the
    # canonical outputs/defects file when present. Later sources overwrite
    # earlier ones on duplicate keys, so canonical output and current run win.
    seed_paths = []
    legacy_seed = PIPELINE_PATHS.workspace_root / output_path.name
    for candidate in [legacy_seed, output_path]:
        if candidate.exists() and candidate not in seed_paths:
            seed_paths.append(candidate)

    if not seed_paths:
        print(f"  Coordinates output does not exist yet; writing {len(result)} rows")
        return _normalize_coordinate_schema(result)

    frames = []
    seed_counts = []
    for seed_path in seed_paths:
        seed_df = pd.read_csv(seed_path, low_memory=False)
        seed_df = _normalize_coordinate_schema(seed_df)
        frames.append(seed_df)
        seed_counts.append(f"{seed_path.name}={len(seed_df)}")

    frames.append(_normalize_coordinate_schema(result))
    combined = pd.concat(frames, ignore_index=True, sort=False)

    missing_keys = [col for col in key_cols if col not in combined.columns]
    if missing_keys:
        raise KeyError(
            "Missing coordinate dedup key columns: "
            f"{missing_keys}. Found columns: {sorted(combined.columns.tolist())}"
        )

    combined = combined.drop_duplicates(subset=key_cols, keep="last")
    print(
        "  Accumulated coordinates output using seeds "
        f"[{', '.join(seed_counts)}] + new={len(result)} -> {len(combined)} deduplicated"
    )
    return _normalize_coordinate_schema(combined)


def _normalize_coordinate_schema(df):
    normalized = df.copy()
    time_col = None
    for candidate in ("INSPECTION_TIME", "SUBENTITY_END_TIME", "INSPECT_TIME"):
        if candidate in normalized.columns:
            time_col = candidate
            break

    if time_col is not None:
        normalized["YYMM"] = pd.to_datetime(normalized[time_col], errors="coerce").dt.strftime("%y%m")

    if "YYMM" in normalized.columns:
        ordered = ["YYMM"] + [col for col in normalized.columns if col != "YYMM"]
        normalized = normalized[ordered]

    return normalized


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def query_defect_coordinates():
    ensure_pipeline_dirs()

    # ------------------------------------------------------------------
    # 1. Load and filter CONCAT output
    # ------------------------------------------------------------------
    print(f"Loading CONCAT CSV: {NCDD_CSV}")
    for line in validate_pipeline_paths({"ncdd_csv": Path(NCDD_CSV)}):
        print(line)
    df = pd.read_csv(NCDD_CSV)
    print(f"  {len(df)} rows loaded")

    missing_cols = _REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise KeyError(
            "Missing required columns in CONCAT CSV: "
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

    df = _filter_recent_rows(df, OUTPUT_CSV, RECENT_LOOKBACK_DAYS)

    if df.empty:
        print("No rows remain after filtering. Exiting.")
        return None

    # Parse INSPECT_TIME for matching to INSP_WAFER_SUMMARY.INSPECTION_TIME
    df = df.copy()
    df["INSPECT_TIME_DT"] = pd.to_datetime(df["INSPECT_TIME"], errors="coerce")

    # ------------------------------------------------------------------
    # 2. Resolve unique (LOT7, WAFER_ID, LAYER) -> WAFER_KEY + INSPECTION_TIME
    # ------------------------------------------------------------------
    lot7_list = df["LOT7"].dropna().unique().tolist()
    layers    = df["LAYER"].dropna().unique().tolist()

    print(f"\nStep 1: Querying INSP_WAFER_SUMMARY")
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

    # ------------------------------------------------------------------
    # 3. Match summary records to CONCAT rows
    #    Join on LOT7 + WAFER_ID + LAYER, then pin to INSPECT_TIME
    # ------------------------------------------------------------------
    # summary INSPECTION_TIME arrives as Python datetime via PyUber
    summary_df["INSPECTION_TIME"] = pd.to_datetime(summary_df["INSPECTION_TIME"], errors="coerce")

    # Start with exact LOT7 + WAFER_ID + LAYER match
    lookup = df[["LOT7", "WAFER_ID", "LAYER", "INSPECT_TIME_DT"]].drop_duplicates()
    merged = lookup.merge(summary_df, on=["LOT7", "WAFER_ID", "LAYER"], how="inner")

    # Pin to the specific inspection by matching INSPECT_TIME to the second
    # (tolerance ±1 second to guard against sub-second rounding)
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

    print(f"  Matched {len(matched)} wafer inspection records")

    if matched.empty:
        print("No matching wafer records found after merge. Exiting.")
        return None

    # ------------------------------------------------------------------
    # 4. Query defect coordinates
    # ------------------------------------------------------------------
    pairs = [
        (row["INSPECTION_TIME"], int(row["WAFER_KEY"]))
        for _, row in matched.iterrows()
    ]
    # Deduplicate in case the same wafer appears in multiple CONCAT rows
    pairs = list(dict.fromkeys(pairs))

    print(f"\nStep 2: Querying INSP_DEFECT for {len(pairs)} unique wafer inspections")

    conn = _connect(DATABASE)
    try:
        defects_df = _fetch_defect_coords(conn, pairs, class_filter=CLASS_FILTER)
    finally:
        conn.close()
        del conn
        gc.collect()

    if defects_df.empty:
        print("No defect records returned.")
        return defects_df

    print(f"\nTotal adder defect records: {len(defects_df)}")

    # ------------------------------------------------------------------
    # 5. Join NCDD context columns back onto the defect records
    # ------------------------------------------------------------------
    # Cast numeric columns for clean output
    for col in ("WAFER_X_MM", "WAFER_Y_MM"):
        defects_df[col] = pd.to_numeric(defects_df[col], errors="coerce")

    context_cols_present = [c for c in CONTEXT_COLS if c in df.columns]
    context = (
        df[context_cols_present]
        .drop_duplicates(subset=["LOT7", "WAFER_ID", "LAYER"])
    )

    result = defects_df.merge(context, on=["LOT7", "WAFER_ID", "LAYER"], how="left")
    result["YYMM"] = pd.to_datetime(result["INSPECTION_TIME"], errors="coerce").dt.strftime("%y%m")

    # Tidy column order: identifiers first, then coordinates, then context
    id_cols   = ["YYMM", "LOT", "LOT7", "ACTUAL_LOT", "WAFER_ID", "LAYER",
                 "WAFER_KEY", "INSPECTION_TIME"]
    coord_cols = ["DEFECT_ID", "CLASS", "FINEBIN",
                  "WAFER_X_MM", "WAFER_Y_MM", "IMAGE_COUNT"]
    ctx_cols  = [c for c in context_cols_present if c not in id_cols]

    ordered = (
          [c for c in id_cols   if c in result.columns]
        + [c for c in coord_cols if c in result.columns]
        + [c for c in ctx_cols  if c in result.columns]
        + [c for c in result.columns if c not in id_cols + coord_cols + ctx_cols]
    )
    result = _normalize_coordinate_schema(result[ordered])

    # ------------------------------------------------------------------
    # 6. Save coordinates
    # ------------------------------------------------------------------
    accumulated_result = _accumulate_coordinates(result, OUTPUT_CSV)
    accumulated_result.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved {len(accumulated_result)} accumulated records -> {OUTPUT_CSV}")
    manifest_path = write_artifact_manifest(
        PIPELINE_PATHS.defect_artifact_manifest,
        extra_outputs={
            "defect_coordinates_csv": Path(OUTPUT_CSV),
            "defect_images_folder": Path(IMAGE_OUTPUT_FOLDER),
        },
    )
    print(f"Artifact manifest saved to: {manifest_path}")

    print("\nSample output (first 5 rows):")
    print(accumulated_result.head().to_string())

    # ------------------------------------------------------------------
    # 7. (Optional) Fetch image metadata and download via SecureFTP
    # ------------------------------------------------------------------
    if DOWNLOAD_IMAGES:
        image_csv = str(PIPELINE_PATHS.defect_images_manifest_csv)

        # Pre-filter: skip wafer groups already fully covered in the manifest.
        # This avoids one Oracle round-trip per already-handled wafer group,
        # which is the main source of slowness on repeat runs over the 60-day
        # rolling window (most groups overlap with the previous day's run).
        defects_needing_imgs = _filter_defects_needing_images(
            defects_df, image_csv, IMAGE_ID_FILTER
        )

        if defects_needing_imgs.empty:
            print("  All wafer groups fully covered in manifest — skipping image DB query.")
        else:
            n_img_groups = defects_needing_imgs.groupby(["WAFER_KEY", "INSPECTION_TIME"]).ngroups
            print(f"\nStep 3: Fetching image metadata from INSP_WAFER_IMAGE "
                  f"({n_img_groups} wafer group(s) not yet in manifest)...")
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
                image_df_new = _filter_new_images(image_df, result, IMAGE_OUTPUT_FOLDER)
                if not image_df_new.empty:
                    image_df_new = _download_images(
                        image_df_new, IMAGE_OUTPUT_FOLDER, APP_NAME,
                        technology=TECHNOLOGY, ftp_chunk_size=IMAGE_FTP_CHUNK_SIZE
                    )
                    if not image_df_new.empty:
                        image_df_new = _reorganize_images(
                            image_df_new, result, IMAGE_OUTPUT_FOLDER, annotate=ANNOTATE_IMAGES
                        )
                    else:
                        print("  Image download skipped due to unavailable SecureFTP runtime.")
                else:
                    print("  All images already organized — no FTP needed.")

                # Accumulate manifest: record ALL image records queried this run
                # (not just newly downloaded ones) so future runs can skip these
                # groups entirely.  Merge organized LOCAL_IMAGE_FILE paths for
                # newly downloaded files; preserve existing paths for the rest.
                current_rows = image_df.copy()
                existing_path_updates = _backfill_local_image_paths(
                    image_df, result, IMAGE_OUTPUT_FOLDER
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
                current_rows = _normalize_coordinate_schema(current_rows)

                if not image_df_new.empty and "LOCAL_IMAGE_FILE" in image_df_new.columns:
                    path_updates = image_df_new[
                        ["WAFER_KEY", "DEFECT_ID", "IMAGE_ID", "LOCAL_IMAGE_FILE"]
                    ].copy()
                    for col in ("WAFER_KEY", "DEFECT_ID", "IMAGE_ID"):
                        path_updates[col] = path_updates[col].astype(str)
                        current_rows[col] = current_rows[col].astype(str)
                    current_rows = current_rows.drop(columns=["LOCAL_IMAGE_FILE"], errors="ignore")
                    current_rows = current_rows.merge(
                        path_updates, on=["WAFER_KEY", "DEFECT_ID", "IMAGE_ID"], how="left"
                    )
                    current_rows = _normalize_coordinate_schema(current_rows)

                if os.path.isfile(image_csv):
                    try:
                        existing = _normalize_coordinate_schema(pd.read_csv(image_csv, low_memory=False))
                        _retire_stale_reclassified_images(existing, current_rows)
                        combined = pd.concat([existing, current_rows], ignore_index=True)
                        # When deduplicating, prefer rows that have LOCAL_IMAGE_FILE set
                        combined["_sort"] = combined["LOCAL_IMAGE_FILE"].notna().astype(int)
                        combined = (
                            combined
                            .sort_values("_sort")
                            .drop(columns=["_sort"])
                            .drop_duplicates(
                                subset=["WAFER_KEY", "DEFECT_ID", "IMAGE_ID"],
                                keep="last"
                            )
                        )
                        accumulated = _normalize_coordinate_schema(combined)
                    except Exception as exc:
                        print(f"  WARNING: Could not accumulate manifest ({exc})"
                              " — saving current run only.")
                        accumulated = _normalize_coordinate_schema(current_rows)
                else:
                    accumulated = _normalize_coordinate_schema(current_rows)

                accumulated.to_csv(image_csv, index=False)
                print(f"Image manifest updated ({len(accumulated)} total rows) -> {image_csv}")
                _prune_old_images(
                    image_csv,
                    IMAGE_OUTPUT_FOLDER,
                    retention_days=IMAGE_RETENTION_DAYS,
                    active_overlap_days=RECENT_LOOKBACK_DAYS,
                )
            else:
                print("  No image records returned from DB for the queried groups.")
    else:
        print("\n(Image download skipped — set DOWNLOAD_IMAGES = True to enable)")

    return accumulated_result


if __name__ == "__main__":
    query_defect_coordinates()
