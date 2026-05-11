"""
surf_scan_images.py
-------------------
Downloads and organizes EDX defect images for SS (test) wafers.

Input source: SS_COORDINATES.csv — already contains defect coordinates
              joined with INSP_ELEMENT (EDX_ELEM*) data produced by
              SS_COORDINATES_QUERY.py.

Unlike SS_COORDINATES_QUERY.py, this script does NOT re-query defect
coordinates or EDX element data.  Everything needed is already in the CSV.
The only DB call is UDB.INSP_WAFER_IMAGE to resolve image file paths.

Annotation burned into each downloaded image:
  Bottom band (line 1):  <INSPECTION_TIME>  <CHAMBER>  <WAFER_ID>
  Bottom band (line 2):  EDX elements with value > 0  (e.g. "Si 99.3%  C 0.7%")

Flow:
  1. Load SS_COORDINATES.csv, filter to the last N_DAYS days.
  2. Keep only rows where IMAGE_COUNT > 0 (EDX-imaged defects).
  3. Pick the N_EVENTS most recent unique (WAFER_KEY, INSPECTION_TIME) events.
  4. Query UDB.INSP_WAFER_IMAGE for image file paths.
  5. Pre-filter: skip images already organized on disk.
  6. Download remaining images via SecureFTP.
  7. Organize into the current BE surf image library under {CHAMBER}/ and burn
      in annotation text.
  8. Save / accumulate image manifest (EDX_IMAGES.csv).

Folder structure:
    images/surf_scan/
    {CHAMBER}/          <- CHAMBER = subentity if non-empty, else PRIMARY_EQUIP
      {yymmdd_hhmm}_{lot7}_{wafer_short}_{defid}_{picid}.jpg

Database: D1D_PROD_YAS_1278  (PyUber)
"""

import gc
import logging
import os
import re
import sys
import warnings

import PyUber
import pandas as pd

from pipeline_config import PIPELINE_PATHS
from surf_scan_config import (
    DATABASE_NAME as CFG_DATABASE_NAME,
    DEFAULT_IMAGE_ANNOTATION as CFG_DEFAULT_IMAGE_ANNOTATION,
    DEFAULT_IMAGE_QUERY_LOOKBACK_DAYS as CFG_DEFAULT_IMAGE_QUERY_LOOKBACK_DAYS,
    DEFAULT_IMAGE_SUBENTITY_COUNT as CFG_DEFAULT_IMAGE_SUBENTITY_COUNT,
    DEFAULT_IMAGE_TOTAL_DEFECTS as CFG_DEFAULT_IMAGE_TOTAL_DEFECTS,
    DEFAULT_OVER16_DEFECTS as CFG_DEFAULT_OVER16_DEFECTS,
    IMAGE_COUNT_MIN as CFG_IMAGE_COUNT_MIN,
    IMAGE_FTP_CHUNK_SIZE as CFG_IMAGE_FTP_CHUNK_SIZE,
    IMAGE_IDS_BASE as CFG_IMAGE_IDS_BASE,
)

warnings.filterwarnings(
    "ignore",
    message=".*SQLAlchemy.*",
    category=UserWarning,
)

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONFIGURATION  -- edit these for each deployment
# ---------------------------------------------------------------------------

SS_COORDS_CSV = str(PIPELINE_PATHS.surf_coordinates_csv)

# Output folder: organized images deposited here under per-chamber subfolders.
IMAGE_OUTPUT_FOLDER = str(PIPELINE_PATHS.surf_image_dir)

# Accumulated manifest of all images downloaded by this script.
IMAGE_MANIFEST_CSV = str(PIPELINE_PATHS.surf_image_manifest_csv)

DATABASE = CFG_DATABASE_NAME

# --- Scope / volume controls ---

# How many calendar days back from today to include from SS_COORDINATES.csv.
N_DAYS = CFG_DEFAULT_IMAGE_QUERY_LOOKBACK_DAYS

# Number of distinct recent subentities (chambers) to sample from.
N_SUBENTITIES = CFG_DEFAULT_IMAGE_SUBENTITY_COUNT

# Total number of imaged defects to download across all selected subentities.
# Defects are spread evenly across subentities (round-robin, most recent first).
# Set to None to download ALL defects in the date window (no cap).
N_DEFECTS_TOTAL = CFG_DEFAULT_IMAGE_TOTAL_DEFECTS

# Only download defects whose IMAGE_COUNT >= this threshold.
# Defects with fewer images are considered incomplete / not of interest.
IMAGE_COUNT_MIN = CFG_IMAGE_COUNT_MIN

# Base IMAGE_ID positions within one standard 16-image EDX block.
# For IMAGE_COUNT == 16: these are fetched as-is.
# For IMAGE_COUNT > 16 (scanner repeated the block): an offset of
#   (IMAGE_COUNT - 16) is added so the LAST block's images are retrieved.
#   e.g. IMAGE_COUNT=31 -> offset=15 -> actual IDs fetched = [17, 18, 19, 23]
# 2=brightfield, 3=darkfield, 4=extra BF, 8=spectrum (absolute keV scale).
IMAGE_IDS_BASE = CFG_IMAGE_IDS_BASE

# --- Over-16 pass ---
# Defects with IMAGE_COUNT > IMAGE_COUNT_MIN use the same offset-shifted
# IMAGE_IDS_BASE scheme and are saved to the SAME folder and manifest as
# the standard pass (grouped by subentity just like standard defects).
# Set to 0 to skip the over-16 pull entirely.
N_DEFECTS_OVER16 = CFG_DEFAULT_OVER16_DEFECTS          # how many >16-image defects to sample

# Set to True to burn inspection/chamber/EDX metadata into each downloaded image.
# Requires Pillow (pip install pillow).
ANNOTATE_IMAGES = CFG_DEFAULT_IMAGE_ANNOTATION

# ---------------------------------------------------------------------------
# GAJT / FTP CREDENTIALS
# ---------------------------------------------------------------------------
# GAJT_DLL_DIR is resolved automatically (first existing path wins):
#   Local dev machine (JMP addin): C:\Users\<user>\AppData\...\wijt
#   ScriptHost:                    D:\gajtv\configurations\wijt
# Override by setting the env var GAJT_DLL_DIR, or edit _GAJT_DLL_CANDIDATES.
_GAJT_DLL_CANDIDATES = [
    os.path.join(os.path.expanduser("~"), r"AppData\Roaming\SAS\JMP\AddIns\gajtv.intel.com\wijt"),
    r"D:\gajtv\configurations\wijt",
]


def _resolve_gajt_dll_dir():
    env_override = os.environ.get("GAJT_DLL_DIR", "").strip()
    if env_override:
        return env_override
    for candidate in _GAJT_DLL_CANDIDATES:
        dll = os.path.join(candidate, "Intel.FabAuto.Quarc.Utilities.dll")
        if os.path.isfile(dll):
            return candidate
    # Fall back to first candidate — will fail with a clear message at load time
    return _GAJT_DLL_CANDIDATES[0]


GAJT_DLL_DIR = _resolve_gajt_dll_dir()
APP_NAME      = "GAJT_INLINE_24601"
TECHNOLOGY    = "1278"

# Max IMAGE_FILESPEC paths sent in a single SecureFTP.FtpFiles() call.
IMAGE_FTP_CHUNK_SIZE = CFG_IMAGE_FTP_CHUNK_SIZE

# ---------------------------------------------------------------------------
# ELEMENT SYMBOL MAP  (atomic number -> symbol)
# Covers the range that appears in UDB INSP_ELEMENT EDX_ELEM* columns.
# ---------------------------------------------------------------------------
ELEMENT_SYMBOLS = {
    1: "H",   2: "He",  3: "Li",  4: "Be",  5: "B",
    6: "C",   7: "N",   8: "O",   9: "F",  10: "Ne",
    11: "Na", 12: "Mg", 13: "Al", 14: "Si", 15: "P",
    16: "S",  17: "Cl", 18: "Ar", 19: "K",  20: "Ca",
    21: "Sc", 22: "Ti", 23: "V",  24: "Cr", 25: "Mn",
    26: "Fe", 27: "Co", 28: "Ni", 29: "Cu", 30: "Zn",
    31: "Ga", 32: "Ge", 33: "As", 34: "Se", 35: "Br",
    36: "Kr", 37: "Rb", 38: "Sr", 39: "Y",  40: "Zr",
    41: "Nb", 42: "Mo", 43: "Tc", 44: "Ru", 45: "Rh",
    46: "Pd", 47: "Ag", 48: "Cd", 49: "In", 50: "Sn",
    51: "Sb", 52: "Te", 53: "I",  54: "Xe", 55: "Cs",
    56: "Ba", 57: "La", 58: "Ce", 59: "Pr", 60: "Nd",
    61: "Pm", 62: "Sm", 63: "Eu", 64: "Gd", 65: "Tb",
    66: "Dy", 67: "Ho", 68: "Er", 69: "Tm", 70: "Yb",
    71: "Lu", 72: "Hf", 73: "Ta", 74: "W",  75: "Re",
    76: "Os", 77: "Ir", 78: "Pt", 79: "Au", 80: "Hg",
    81: "Tl", 82: "Pb", 83: "Bi", 84: "Po",
}


# ---------------------------------------------------------------------------
# HELPERS: EDX column parsing
# ---------------------------------------------------------------------------

def _edx_columns(df):
    """
    Return list of EDX_ELEM* column names from df, sorted by atomic number.
    Pattern: EDX_ELEM<num>_<name>
    """
    cols = []
    for col in df.columns:
        m = re.match(r"EDX_ELEM(\d+)_", col, re.IGNORECASE)
        if m:
            cols.append((int(m.group(1)), col))
    cols.sort()
    return [col for _, col in cols]


def _edx_label(row, edx_cols):
    """
    Build a compact EDX annotation string for one defect row.
    Format:  {sym1}{sym2}{sym3} - ({int1},{int2},{int3})
    where integer values are the EDX percentages rounded to nearest integer,
    sorted descending by value.  Elements with value <= 0 are omitted.
    Example: "SiC - (99,1)"   or   "SiCO - (92,5,3)"
    Returns empty string if no EDX data is present for this defect.
    """
    parts = []
    for col in edx_cols:
        val = pd.to_numeric(row.get(col), errors="coerce")
        if pd.isna(val) or val <= 0:
            continue
        m = re.match(r"EDX_ELEM(\d+)_", col, re.IGNORECASE)
        atomic_num = int(m.group(1)) if m else 0
        symbol = ELEMENT_SYMBOLS.get(atomic_num, col.split("_")[-1][:2].capitalize())
        parts.append((val, symbol, round(val)))
    parts.sort(reverse=True)
    if not parts:
        return ""
    symbols = "".join(p[1] for p in parts)
    values  = ",".join(str(p[2]) for p in parts)
    return f"{symbols} - ({values})"


# ---------------------------------------------------------------------------
# HELPERS: image annotation
# ---------------------------------------------------------------------------

def _annotate_image(path, line1, line2):
    """
    Burn two text lines into a semi-transparent black banner at the bottom
    of the image in-place.  Pure Pillow — no NumPy dependency.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log.warning("Pillow not installed — skipping image annotation.")
        return
    try:
        img = Image.open(path).convert("RGB")
        w, h = img.size
        font_size = max(24, int(min(w, h) * 0.05))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default(size=font_size)
        pad      = max(4, font_size // 4)
        banner_h = font_size * 2 + pad * 3
        banner   = Image.new("RGB", (w, banner_h), (0, 0, 0))
        img.paste(banner, (0, h - banner_h))
        draw = ImageDraw.Draw(img)
        draw.text((pad, h - banner_h + pad),                line1, fill="white",   font=font)
        draw.text((pad, h - banner_h + font_size + pad * 2), line2, fill="#FFDD88", font=font)
        img.save(path, quality=92)
    except Exception as exc:
        log.warning("Annotation failed for %s: %s", path, exc)


# ---------------------------------------------------------------------------
# HELPERS: DB query
# ---------------------------------------------------------------------------

def _fetch_image_metadata(conn, defects_df, base_ids=None):
    """
    Query UDB.INSP_WAFER_IMAGE for image file paths for all defect rows
    in defects_df that have IMAGE_COUNT > 0.

    When base_ids is provided (e.g. [2, 3, 4, 8]), the actual IMAGE_IDs
    fetched per defect are offset to the LAST 16-image EDX block:

        offset      = max(0, IMAGE_COUNT - 16)
        actual_ids  = [id + offset for id in base_ids]

    Examples:
        IMAGE_COUNT=16 -> offset=0  -> fetch IDs [2, 3, 4, 8]
        IMAGE_COUNT=31 -> offset=15 -> fetch IDs [17, 18, 19, 23]

    Different defects in the same inspection can have different IMAGE_COUNTs
    so we sub-group by IMAGE_COUNT and issue one SQL per (WAFER_KEY,
    INSPECTION_TIME, IMAGE_COUNT) bucket.

    When base_ids is None, all available IMAGE_IDs are fetched.

    Returns DataFrame with columns:
        SITE, QUERY_SITE, WAFER_KEY, INSPECTION_TIME, DEFECT_ID,
        IMAGE_ID, IMAGE_SERVER_ID, IMAGE_FILESPEC
    """
    df = defects_df.copy()
    df["_IMG_CNT"] = pd.to_numeric(df.get("IMAGE_COUNT", 0), errors="coerce").fillna(0).astype(int)
    df = df[df["_IMG_CNT"] > 0]

    if df.empty:
        log.info("No defects with IMAGE_COUNT > 0 — skipping image metadata query.")
        return pd.DataFrame()

    # Group by (WAFER_KEY, INSPECTION_TIME, _IMG_CNT) so each bucket gets
    # its own offset-shifted IMAGE_ID filter.
    groups = list(df.groupby(["WAFER_KEY", "INSPECTION_TIME", "_IMG_CNT"]))
    log.info("[INSP_WAFER_IMAGE] querying %d wafer/count group(s)...", len(groups))
    all_chunks = []

    for (wafer_key, insp_time, img_cnt), group in groups:
        defect_ids = ", ".join(
            str(int(float(d))) for d in group["DEFECT_ID"].dropna().unique()
        )
        if not defect_ids:
            continue

        insp_time_str = pd.Timestamp(insp_time).strftime("%Y%m%d%H%M%S")

        img_id_clause = ""
        if base_ids is not None:
            offset     = max(0, int(img_cnt) - 16)
            actual_ids = [id_ + offset for id_ in base_ids]
            id_list    = ", ".join(str(i) for i in actual_ids)
            img_id_clause = f"  AND i.IMAGE_ID IN ({id_list})"
            log.info(
                "  WK=%-10s  IMG_CNT=%d  offset=%d  IDs=%s",
                int(wafer_key), img_cnt, offset, actual_ids,
            )

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
    log.info("  -> %d image record(s) found", len(result))
    return result


# ---------------------------------------------------------------------------
# HELPERS: FTP download
# ---------------------------------------------------------------------------

def _download_images(image_df, image_folder, app_name,
                     technology="1278", ftp_chunk_size=50):
    """
    Download defect images via SecureFTP (Intel.FabAuto.Quarc.Utilities).

    Sets LOCAL_IMAGE_FILE to the staged path for each row.
    Files already present in the staging tree are skipped.
    Returns image_df with LOCAL_IMAGE_FILE column populated.
    """
    import clr

    if GAJT_DLL_DIR not in sys.path:
        sys.path.append(GAJT_DLL_DIR)

    try:
        clr.AddReference("Intel.FabAuto.Quarc.Utilities")
        from Intel.FabAuto.Quarc import SecureFTP
    except Exception as exc:
        log.error(
            "Could not load Intel.FabAuto.Quarc.Utilities from '%s': %s\n"
            "Verify GAJT_DLL_DIR in the config section.",
            GAJT_DLL_DIR, exc,
        )
        raise

    os.makedirs(image_folder, exist_ok=True)

    df = image_df.copy()
    df["LOCAL_IMAGE_FILE"] = df["IMAGE_FILESPEC"].apply(
        lambda p: os.path.join(image_folder, p.lstrip("/\\").replace("/", os.sep))
                  if pd.notna(p) else None
    )

    query_site_col = "QUERY_SITE" if "QUERY_SITE" in df.columns else "SITE"
    for query_site, grp in df.groupby(query_site_col):
        files = grp["IMAGE_FILESPEC"].dropna().unique().tolist()
        if not files:
            continue
        ds = f"{query_site}_PROD_YAS_{technology}_FTP"

        files_to_dl = [
            spec for spec in files
            if not os.path.isfile(
                os.path.join(image_folder, spec.lstrip("/\\").replace("/", os.sep))
            )
        ]
        n_cached = len(files) - len(files_to_dl)
        if n_cached:
            log.info(
                "[%s] %d/%d already staged — skipping FTP for those",
                query_site, n_cached, len(files),
            )

        if files_to_dl:
            n_dl = len(files_to_dl)
            log.info(
                "[%s] Downloading %d file(s) via %s -> %s",
                query_site, n_dl, ds, image_folder,
            )
            for chunk_start in range(0, n_dl, ftp_chunk_size):
                chunk = files_to_dl[chunk_start: chunk_start + ftp_chunk_size]
                chunk_num    = chunk_start // ftp_chunk_size + 1
                total_chunks = (n_dl + ftp_chunk_size - 1) // ftp_chunk_size
                log.info("  chunk %d/%d (%d files)...", chunk_num, total_chunks, len(chunk))
                SecureFTP.FtpFiles(query_site, ds, ",".join(chunk), image_folder, app_name)
            log.info("[%s] Download complete.", query_site)
        else:
            log.info("[%s] All files already staged — no FTP needed.", query_site)

    return df


# ---------------------------------------------------------------------------
# HELPERS: reorganize (copy to named folder) + annotate
# ---------------------------------------------------------------------------

def _chamber_for_row(row):
    """
    Return the folder name for this defect.
    Tries SUBENTITY (uppercase, from SS_COORDINATES.csv) first, then
    PRIMARY_EQUIP.  NaN / empty / literal 'nan' values are skipped.
    """
    for key in ("SUBENTITY", "subentity", "PRIMARY_EQUIP"):
        val = row.get(key)
        try:
            if pd.isna(val):
                continue
        except (TypeError, ValueError):
            pass
        s = str(val).strip()
        if s and s.lower() != "nan":
            return s
    return "UNKNOWN"


def _organized_dest(row, image_folder, ext=".jpg"):
    """
    Compute the organized destination path for one image row.
    Pattern: {image_folder}/{CHAMBER}/{yymmdd_hhmm}_{lot7}_{wafer_short}_{defid}_{picid}{ext}
    """
    insp_time = pd.to_datetime(row.get("INSPECTION_TIME"), errors="coerce")
    ts = insp_time.strftime("%y%m%d_%H%M") if not pd.isna(insp_time) else "000000_0000"

    lot7 = str(row.get("LOT7") or "").strip()
    if not lot7:
        # Fall back to first 7 chars of ACTUAL_LOT
        lot7 = str(row.get("ACTUAL_LOT") or "UNK")[:7]

    waf_raw = str(row.get("WAFER_ID", "")).strip()
    short_w = waf_raw[5:8] if len(waf_raw) >= 8 else waf_raw

    defid = str(int(row["_DID"])) if pd.notna(row.get("_DID")) else "0"
    picid = str(int(float(row["IMAGE_ID"]))) if pd.notna(row.get("IMAGE_ID")) else "0"

    fname   = f"{ts}_{lot7}_{short_w}_{defid}_{picid}{ext}"
    chamber = _chamber_for_row(row)
    return os.path.join(image_folder, chamber, fname)


def _reorganize_images(image_df, coords_df, image_folder,
                       annotate=False, edx_cols=None):
    """
    Copy downloaded images from the SecureFTP staging tree into:
        {image_folder}/{CHAMBER}/{yymmdd_hhmm}_{lot7}_{wafer_short}_{defid}_{picid}.ext

    Annotation burned into each copied image:
      Line 1 (white):   INSPECTION_TIME  CHAMBER  WAFER_ID
      Line 2 (yellow):  EDX elements with value > 0

    After copying the staging 'yas' subfolder is removed (only if it is a
    direct child of image_folder — safety guard against path misconfiguration).

    Returns image_df with LOCAL_IMAGE_FILE updated to organized paths.
    """
    import shutil

    if edx_cols is None:
        edx_cols = []

    # -- Merge context from coords_df onto image_df --
    # image_df carries: WAFER_KEY, INSPECTION_TIME (from DB), DEFECT_ID, IMAGE_ID,
    #                   IMAGE_FILESPEC, LOCAL_IMAGE_FILE (staged path)
    # coords_df carries: all SS_COORDINATES.csv columns incl. EDX_ELEM*, subentity, PRIMARY_EQUIP

    img = image_df.copy()
    img["_WK"]  = pd.to_numeric(img["WAFER_KEY"],  errors="coerce").astype("Int64")
    img["_DID"] = pd.to_numeric(img["DEFECT_ID"],  errors="coerce").astype("Int64")

    ctx = coords_df.copy()
    ctx["_WK"]  = pd.to_numeric(ctx["WAFER_KEY"],  errors="coerce").astype("Int64")
    ctx["_DID"] = pd.to_numeric(ctx["DEFECT_ID"],  errors="coerce").astype("Int64")

    # Carry only what we need; omit INSPECTION_TIME from ctx (img already has it).
    carry = [c for c in (
        ["_WK", "_DID", "LOT7", "lot", "ACTUAL_LOT", "WAFER_ID",
         "CLASS", "LAYER", "subentity", "PRIMARY_EQUIP"]
        + edx_cols
    ) if c in ctx.columns]
    ctx_small = ctx[carry].drop_duplicates(subset=["_WK", "_DID"])

    merged = img.merge(ctx_small, on=["_WK", "_DID"], how="left")

    # Prefer WAFER_ID from ctx (more reliable for annotation) but fall back to img
    if "WAFER_ID_y" in merged.columns:
        merged["WAFER_ID"] = merged["WAFER_ID_y"].fillna(merged.get("WAFER_ID_x", ""))
    if "LOT7_y" in merged.columns:
        merged["LOT7"] = merged["LOT7_y"].fillna(merged.get("LOT7_x", ""))

    new_paths = []
    n_copied = n_skipped = n_missing = 0

    for _, row in merged.iterrows():
        src = row.get("LOCAL_IMAGE_FILE")
        if src:
            src = os.path.normpath(str(src))

        insp_time = pd.to_datetime(row.get("INSPECTION_TIME"), errors="coerce")
        ts_label  = insp_time.strftime("%Y/%m/%d %H:%M") if not pd.isna(insp_time) else ""

        chamber = _chamber_for_row(row)
        waf_raw = str(row.get("WAFER_ID", "")).strip()
        ext     = os.path.splitext(src)[1].lower() if src else ".jpg"

        dest = _organized_dest(row, image_folder, ext=ext)
        dest_dir = os.path.dirname(dest)
        os.makedirs(dest_dir, exist_ok=True)

        if os.path.isfile(dest):
            new_paths.append(dest)
            n_skipped += 1
        elif src and os.path.isfile(src):
            import shutil as _sh
            _sh.copy2(src, dest)
            if annotate:
                defid     = str(int(row["_DID"])) if pd.notna(row.get("_DID")) else "?"
                picid     = str(int(float(row["IMAGE_ID"]))) if pd.notna(row.get("IMAGE_ID")) else "?"
                short_w   = waf_raw[5:8] if len(waf_raw) >= 8 else waf_raw
                edx_str   = _edx_label(row, edx_cols) if edx_cols else ""
                line1 = f"{ts_label}  {chamber}"
                line2 = f"W{short_w} D{defid} #{picid}  {edx_str}".strip()
                _annotate_image(dest, line1, line2)
            new_paths.append(dest)
            n_copied += 1
        else:
            new_paths.append(None)
            n_missing += 1

    img["LOCAL_IMAGE_FILE"] = new_paths
    img.drop(columns=["_WK", "_DID"], inplace=True, errors="ignore")

    log.info(
        "Organize: %d copied+annotated, %d already present (skipped), "
        "%d source not found (server unavailable or missing file)",
        n_copied, n_skipped, n_missing,
    )

    # Remove SecureFTP staging tree only when it is a direct child of image_folder.
    staging_root    = os.path.join(image_folder, "yas")
    expected_parent = os.path.normpath(image_folder)
    actual_parent   = os.path.normpath(os.path.dirname(staging_root))
    if os.path.isdir(staging_root) and actual_parent == expected_parent:
        shutil.rmtree(staging_root)
        log.info("Staging tree removed: %s", staging_root)
    elif os.path.isdir(staging_root):
        log.warning(
            "Staging root '%s' is not a direct child of image_folder — "
            "skipping rmtree for safety.",
            staging_root,
        )

    return img


def _filter_new_images(image_df, coords_df, image_folder, edx_cols=None):
    """
    Return the subset of image_df whose organized destination file does not
    yet exist on disk.  Avoids unnecessary FTP calls on re-runs.
    """
    if edx_cols is None:
        edx_cols = []

    img = image_df.copy()
    img["_WK"]  = pd.to_numeric(img["WAFER_KEY"],  errors="coerce").astype("Int64")
    img["_DID"] = pd.to_numeric(img["DEFECT_ID"],  errors="coerce").astype("Int64")

    ctx = coords_df.copy()
    ctx["_WK"]  = pd.to_numeric(ctx["WAFER_KEY"],  errors="coerce").astype("Int64")
    ctx["_DID"] = pd.to_numeric(ctx["DEFECT_ID"],  errors="coerce").astype("Int64")

    carry = [c for c in
             ["_WK", "_DID", "LOT7", "lot", "ACTUAL_LOT", "WAFER_ID",
              "subentity", "PRIMARY_EQUIP"]
             if c in ctx.columns]
    ctx_small = ctx[carry].drop_duplicates(subset=["_WK", "_DID"])

    merged = img.merge(ctx_small, on=["_WK", "_DID"], how="left")

    if "WAFER_ID_y" in merged.columns:
        merged["WAFER_ID"] = merged["WAFER_ID_y"].fillna(merged.get("WAFER_ID_x", ""))
    if "LOT7_y" in merged.columns:
        merged["LOT7"] = merged["LOT7_y"].fillna(merged.get("LOT7_x", ""))

    def _dest_row(row):
        spec = str(row.get("IMAGE_FILESPEC", ""))
        ext  = os.path.splitext(spec)[1].lower() if spec else ".jpg"
        return _organized_dest(row, image_folder, ext=ext)

    already_exists = merged.apply(lambda r: os.path.isfile(_dest_row(r)), axis=1)
    n_exist = int(already_exists.sum())
    n_total = len(image_df)

    if n_exist:
        log.info(
            "Pre-filter: %d/%d images already organized — skipping FTP for those",
            n_exist, n_total,
        )
    else:
        log.info("Pre-filter: all %d image(s) are new", n_total)

    return image_df[~already_exists.values].copy()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def query_edx_images():
    log.info("GAJT_DLL_DIR resolved to: %s", GAJT_DLL_DIR)

    # ------------------------------------------------------------------
    # 1. Load SS_COORDINATES.csv and apply filters
    # ------------------------------------------------------------------
    log.info("Loading SS_COORDINATES CSV: %s", SS_COORDS_CSV)
    df = pd.read_csv(SS_COORDS_CSV, low_memory=False)
    log.info("  %d rows loaded, %d columns", len(df), len(df.columns))

    # Parse INSPECTION_TIME
    df["INSPECTION_TIME"] = pd.to_datetime(df["INSPECTION_TIME"], errors="coerce")

    # Filter to last N_DAYS
    cutoff      = pd.Timestamp.now() - pd.Timedelta(days=N_DAYS)
    before_n    = len(df)
    df          = df[df["INSPECTION_TIME"] >= cutoff]
    log.info(
        "  N_DAYS=%d filter (>= %s): %d -> %d rows",
        N_DAYS, cutoff.strftime("%Y-%m-%d"), before_n, len(df),
    )

    if df.empty:
        log.info("No records in the last %d days. Exiting.", N_DAYS)
        return

    # Keep only defects with IMAGE_COUNT >= IMAGE_COUNT_MIN
    df["IMAGE_COUNT"] = pd.to_numeric(df.get("IMAGE_COUNT", 0), errors="coerce").fillna(0)
    before_img = len(df)
    df         = df[df["IMAGE_COUNT"] >= IMAGE_COUNT_MIN]
    log.info(
        "  IMAGE_COUNT >= %d filter: %d -> %d rows",
        IMAGE_COUNT_MIN, before_img, len(df),
    )

    if df.empty:
        log.info("No imaged defects in the last %d days. Exiting.", N_DAYS)
        return

    # Split into exactly-16 pool and over-16 pool
    df_std     = df[df["IMAGE_COUNT"] == IMAGE_COUNT_MIN].copy()
    df_over16  = df[df["IMAGE_COUNT"] >  IMAGE_COUNT_MIN].copy()
    log.info(
        "  IMAGE_COUNT == %d: %d rows  |  IMAGE_COUNT > %d: %d rows",
        IMAGE_COUNT_MIN, len(df_std), IMAGE_COUNT_MIN, len(df_over16),
    )

    # Parse WAFER_KEY
    df["WAFER_KEY"]       = pd.to_numeric(df["WAFER_KEY"],       errors="coerce")
    df_std["WAFER_KEY"]   = pd.to_numeric(df_std["WAFER_KEY"],   errors="coerce")
    df_over16["WAFER_KEY"]= pd.to_numeric(df_over16["WAFER_KEY"],errors="coerce")

    # Identify EDX columns for annotation
    edx_cols = _edx_columns(df)
    log.info("  EDX element columns detected: %d", len(edx_cols))

    # Resolve chamber label for every row in both pools
    df_std["_chamber"]    = df_std.apply(_chamber_for_row, axis=1)
    df_over16["_chamber"] = df_over16.apply(_chamber_for_row, axis=1)

    # ------------------------------------------------------------------
    # Helper: round-robin selection from a defect pool
    # ------------------------------------------------------------------
    def _select_defects(pool_df, n_defects, n_subentities, label):
        """
        Pick n_defects unique (WAFER_KEY, DEFECT_ID) pairs spread evenly
        across the n_subentities most recently active chambers, newest first.
        n_defects=None means no cap (return all defects in the pool).
        n_subentities=None means no cap (use all available chambers).
        Returns a DataFrame of selected defect rows.
        """
        if pool_df.empty:
            log.info("  [%s] pool is empty — skipping.", label)
            return pd.DataFrame()

        # If both limits are None, just return the whole pool directly.
        if n_defects is None and n_subentities is None:
            sel = pool_df.sort_values("INSPECTION_TIME", ascending=False).copy()
            n_def = sel[["WAFER_KEY", "DEFECT_ID"]].drop_duplicates().shape[0]
            log.info("  [%s] No caps — returning all %d defect(s) across all chambers.", label, n_def)
            return sel

        pool_sorted = pool_df.sort_values("INSPECTION_TIME", ascending=False)
        chambers = (
            pool_sorted[pool_sorted["_chamber"] != "UNKNOWN"]
            .drop_duplicates(subset="_chamber")["_chamber"]
            .head(n_subentities)   # head(None) returns all rows
            .tolist()
        )
        log.info("  [%s] %d subentit(ies): %s", label, len(chambers), chambers)
        if not chambers:
            log.info("  [%s] No valid subentities — skipping.", label)
            return pd.DataFrame()

        # If only n_subentities is capped (n_defects=None), return all defects
        # for the selected chambers without a count limit.
        if n_defects is None:
            sel = pool_sorted[pool_sorted["_chamber"].isin(chambers)].copy()
            n_def = sel[["WAFER_KEY", "DEFECT_ID"]].drop_duplicates().shape[0]
            log.info("  [%s] No defect cap — returning all %d defect(s) across %d chamber(s).",
                     label, n_def, len(chambers))
            return sel

        ch_pools = {ch: pool_sorted[pool_sorted["_chamber"] == ch] for ch in chambers}
        parts, taken = [], set()

        while len(parts) < n_defects:
            added = 0
            for ch in chambers:
                if len(parts) >= n_defects:
                    break
                for _, row in ch_pools[ch].iterrows():
                    key = (row["WAFER_KEY"], row["DEFECT_ID"])
                    if key not in taken:
                        taken.add(key)
                        parts.append(
                            pool_sorted[
                                (pool_sorted["WAFER_KEY"] == row["WAFER_KEY"])
                                & (pool_sorted["DEFECT_ID"] == row["DEFECT_ID"])
                                & (pool_sorted["_chamber"]  == ch)
                            ]
                        )
                        added += 1
                        break
            if added == 0:
                break

        if not parts:
            return pd.DataFrame()

        sel = pd.concat(parts, ignore_index=True)
        log.info("  [%s] Selection (%d defect row(s)):", label, len(sel))
        for ch in chambers:
            ch_rows = sel[sel["_chamber"] == ch]
            n_def = ch_rows[["WAFER_KEY", "DEFECT_ID"]].drop_duplicates().shape[0]
            if n_def:
                insp = ch_rows["INSPECTION_TIME"].max().strftime("%Y-%m-%d %H:%M")
                log.info("    %-22s  %s  %d defect(s)", ch, insp, n_def)
        return sel

    # ------------------------------------------------------------------
    # Helper: DB query + download + manifest for one pass
    # ------------------------------------------------------------------
    def _run_pass(selected, image_id_filter, out_folder, manifest_csv, label):
        if selected.empty:
            log.info("[%s] Nothing to process.", label)
            return

        n_events = selected.groupby(["WAFER_KEY", "INSPECTION_TIME"]).ngroups
        log.info(
            "[%s] Querying INSP_WAFER_IMAGE for %d event(s), IMAGE_ID_FILTER=%s...",
            label, n_events, image_id_filter,
        )

        conn = PyUber.connect(DATABASE)
        try:
            image_df = _fetch_image_metadata(
                conn, selected, base_ids=image_id_filter,
            )
        finally:
            conn.close()
            del conn
            gc.collect()

        if image_df.empty:
            log.info("[%s] No image records returned from DB.", label)
            return

        image_df_new = _filter_new_images(
            image_df, selected, out_folder, edx_cols=edx_cols,
        )

        if not image_df_new.empty:
            image_df_new = _download_images(
                image_df_new, out_folder, APP_NAME,
                technology=TECHNOLOGY, ftp_chunk_size=IMAGE_FTP_CHUNK_SIZE,
            )
            image_df_new = _reorganize_images(
                image_df_new, selected, out_folder,
                annotate=ANNOTATE_IMAGES, edx_cols=edx_cols,
            )
        else:
            log.info("[%s] All images already organized — no FTP needed.", label)

        # Accumulate manifest — join EDX element + key context columns from
        # selected so the manifest can be filtered by element composition.
        current_rows = image_df.copy()

        # Columns to carry from selected into the manifest
        ctx_carry = [c for c in (
            ["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID",
             "WAFER_ID", "LOT7", "ACTUAL_LOT", "LAYER",
             "subentity", "PRIMARY_EQUIP", "IMAGE_COUNT", "CLASS"]
            + edx_cols
        ) if c in selected.columns]
        ctx_for_join = (
            selected[ctx_carry]
            .copy()
            .drop_duplicates(subset=["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"])
        )
        for col in ("WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"):
            ctx_for_join[col] = ctx_for_join[col].astype(str)
            current_rows[col]  = current_rows[col].astype(str)

        current_rows = current_rows.merge(
            ctx_for_join,
            on=["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"],
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
                path_updates, on=["WAFER_KEY", "DEFECT_ID", "IMAGE_ID"], how="left",
            )

        if os.path.isfile(manifest_csv):
            try:
                existing = pd.read_csv(manifest_csv, low_memory=False)
                combined = pd.concat([existing, current_rows], ignore_index=True)
                combined["_sort"] = combined["LOCAL_IMAGE_FILE"].notna().astype(int)
                combined = (
                    combined
                    .sort_values("_sort")
                    .drop(columns=["_sort"])
                    .drop_duplicates(
                        subset=["WAFER_KEY", "DEFECT_ID", "IMAGE_ID"],
                        keep="last",
                    )
                )
                accumulated = combined
            except Exception as exc:
                log.warning("[%s] Cannot accumulate manifest (%s) — saving current run only.", label, exc)
                accumulated = current_rows
        else:
            accumulated = current_rows

        accumulated.to_csv(manifest_csv, index=False)
        log.info("[%s] Manifest saved (%d rows) -> %s", label, len(accumulated), manifest_csv)

    # ------------------------------------------------------------------
    # 2. Standard pass: IMAGE_COUNT == 16, images 2/3/4/8
    # ------------------------------------------------------------------
    log.info("\n=== PASS 1: standard (IMAGE_COUNT == %d) ===", IMAGE_COUNT_MIN)
    selected_std = _select_defects(df_std, N_DEFECTS_TOTAL, N_SUBENTITIES, "standard")
    _run_pass(selected_std, IMAGE_IDS_BASE, IMAGE_OUTPUT_FOLDER,
              IMAGE_MANIFEST_CSV, "standard")

    # ------------------------------------------------------------------
    # 3. Over-16 pass: IMAGE_COUNT > 16, same base IDs with offset,
    #    same output folder and manifest as the standard pass.
    # ------------------------------------------------------------------
    if N_DEFECTS_OVER16 > 0:
        log.info("\n=== PASS 2: over-16 (IMAGE_COUNT > %d) ===", IMAGE_COUNT_MIN)
        selected_over16 = _select_defects(df_over16, N_DEFECTS_OVER16, N_SUBENTITIES, "over16")
        _run_pass(selected_over16, IMAGE_IDS_BASE, IMAGE_OUTPUT_FOLDER,
                  IMAGE_MANIFEST_CSV, "over16")
    else:
        log.info("N_DEFECTS_OVER16=0 — skipping over-16 test pull.")

    log.info("\nDone.")


if __name__ == "__main__":
    query_edx_images()
