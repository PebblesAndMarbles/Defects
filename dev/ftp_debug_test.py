"""
ftp_debug_test.py
-----------------
Ad-hoc FTP debug script: downloads a handful of EDX images for defects
already present in production CSVs, using the exact same SecureFTP path
as surf_scan_images.py.

Also probes for companion spectrum data files (.txt, .spc, .csv, .dat)
alongside each image on the FTP server by inspecting the remote directory
listing for the same WAFER_KEY / INSPECTION_TIME folder.

Usage (run from the pipeline root):
    python ftp_debug_test.py
    python ftp_debug_test.py --n-defects 3 --image-ids 2 3 4 8
    python ftp_debug_test.py --n-defects 5 --probe-spectrum --verbose
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG  -- mirrors surf_scan_images.py exactly
# ---------------------------------------------------------------------------

COORDS_CSV = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\surf_scan\SS_COORDINATES.csv"
MANIFEST_CSV = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\surf_scan\EDX_IMAGES.csv"
DEBUG_OUTPUT_DIR = Path(r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\surf_scan\ftp_debug")

# Mirror surf_scan_images.py constants
DATABASE    = "D1D_PROD_YAS_1278"
APP_NAME    = "GAJT_INLINE_24601"
TECHNOLOGY  = "1278"

# Same DLL resolution as surf_scan_images.py
_GAJT_DLL_CANDIDATES = [
    os.path.join(os.path.expanduser("~"), r"AppData\Roaming\SAS\JMP\AddIns\gajtv.intel.com\wijt"),
    r"D:\gajtv\configurations\wijt",
]

# Spectrum file extensions to probe for on the FTP server
SPECTRUM_EXTENSIONS = [".txt", ".spc", ".csv", ".dat", ".msa"]

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ftp_debug")


# ---------------------------------------------------------------------------
# DLL resolution (identical to surf_scan_images.py)
# ---------------------------------------------------------------------------

def _resolve_gajt_dll_dir() -> str:
    env_override = os.environ.get("GAJT_DLL_DIR", "").strip()
    if env_override:
        return env_override
    for candidate in _GAJT_DLL_CANDIDATES:
        dll = os.path.join(candidate, "Intel.FabAuto.Quarc.Utilities.dll")
        if os.path.isfile(dll):
            return candidate
    return _GAJT_DLL_CANDIDATES[0]


GAJT_DLL_DIR = _resolve_gajt_dll_dir()


# ---------------------------------------------------------------------------
# STEP 1: pick a handful of defects from production CSVs
# ---------------------------------------------------------------------------

def _pick_defects(
    n_defects: int,
    lookback_days: int,
    chamber_filter: list[str] | None,
) -> pd.DataFrame:
    """
    Load SS_COORDINATES.csv and return up to n_defects rows that have
    IMAGE_COUNT > 0, from the most recent lookback_days, optionally
    filtered to specific chambers.
    """
    log.info("Loading coords CSV: %s", COORDS_CSV)
    df = pd.read_csv(COORDS_CSV, low_memory=False)
    log.info("  %d rows, %d columns", len(df), len(df.columns))

    df["INSPECTION_TIME"] = pd.to_datetime(df["INSPECTION_TIME"], errors="coerce")
    df["IMAGE_COUNT"]     = pd.to_numeric(df.get("IMAGE_COUNT", 0), errors="coerce").fillna(0)
    df["WAFER_KEY"]       = pd.to_numeric(df["WAFER_KEY"], errors="coerce")
    df["DEFECT_ID"]       = pd.to_numeric(df["DEFECT_ID"], errors="coerce")

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
    df = df[df["INSPECTION_TIME"] >= cutoff]
    log.info("  After lookback filter (%dd): %d rows", lookback_days, len(df))

    df = df[df["IMAGE_COUNT"] > 0]
    log.info("  After IMAGE_COUNT > 0 filter: %d rows", len(df))

    if chamber_filter:
        mask = df.get("PRIMARY_EQUIP", pd.Series(dtype=str)).isin(chamber_filter)
        df = df[mask]
        log.info("  After chamber filter %s: %d rows", chamber_filter, len(df))

    if df.empty:
        log.warning("No candidate defects found — check filters / lookback_days")
        return df

    # Pick one row per unique (WAFER_KEY, DEFECT_ID), most recent first
    df = (
        df.sort_values("INSPECTION_TIME", ascending=False)
        .drop_duplicates(subset=["WAFER_KEY", "DEFECT_ID"])
        .head(n_defects)
        .reset_index(drop=True)
    )

    log.info("  Selected %d defect(s):", len(df))
    for _, r in df.iterrows():
        log.info(
            "    WK=%-10s  DID=%-6s  IMG_CNT=%-4s  EQUIP=%s  TIME=%s",
            int(r["WAFER_KEY"]),
            int(r["DEFECT_ID"]),
            int(r["IMAGE_COUNT"]),
            r.get("PRIMARY_EQUIP", "?"),
            r["INSPECTION_TIME"],
        )
    return df


# ---------------------------------------------------------------------------
# STEP 2: query INSP_WAFER_IMAGE for file paths (mirrors _fetch_image_metadata)
# ---------------------------------------------------------------------------

def _fetch_image_paths(
    defects_df: pd.DataFrame,
    image_ids: list[int],
) -> pd.DataFrame:
    """
    Query UDB.INSP_WAFER_IMAGE for the requested IMAGE_IDs.
    Returns DataFrame with WAFER_KEY, INSPECTION_TIME, DEFECT_ID,
    IMAGE_ID, IMAGE_SERVER_ID, IMAGE_FILESPEC.
    """
    import PyUber

    all_chunks = []
    conn = PyUber.connect(DATABASE)

    try:
        for _, row in defects_df.iterrows():
            wk       = int(row["WAFER_KEY"])
            did      = int(row["DEFECT_ID"])
            img_cnt  = int(row.get("IMAGE_COUNT", 16))
            insp_str = pd.Timestamp(row["INSPECTION_TIME"]).strftime("%Y%m%d%H%M%S")

            # Apply same offset logic as surf_scan_images.py
            offset     = max(0, img_cnt - 16)
            actual_ids = [i + offset for i in image_ids]
            id_list    = ", ".join(str(i) for i in actual_ids)

            log.info(
                "  Querying WK=%s DID=%s IMG_CNT=%s offset=%s -> IDs=%s",
                wk, did, img_cnt, offset, actual_ids,
            )

            sql = f"""
SELECT
    i.WAFER_KEY,
    i.INSPECTION_TIME,
    i.DEFECT_ID,
    i.IMAGE_ID,
    i.IMAGE_SERVER_ID,
    i.IMAGE_FILESPEC
FROM UDB.INSP_WAFER_IMAGE i
WHERE i.WAFER_KEY        = {wk}
  AND i.INSPECTION_TIME  = TO_DATE('{insp_str}','YYYYMMDDHH24MISS')
  AND i.DEFECT_ID        = {did}
  AND i.IMAGE_ID         IN ({id_list})
"""
            chunk = pd.read_sql(sql, conn)
            log.info("    -> %d row(s) returned", len(chunk))

            if not chunk.empty:
                log.info("    IMAGE_FILESPEC values:")
                for spec in chunk["IMAGE_FILESPEC"].tolist():
                    log.info("      %s", spec)
            all_chunks.append(chunk)

    finally:
        conn.close()

    if not all_chunks:
        return pd.DataFrame()

    result = pd.concat(all_chunks, ignore_index=True)
    log.info("Total image records from DB: %d", len(result))
    return result


# ---------------------------------------------------------------------------
# STEP 3: probe FTP directory for spectrum companion files
# ---------------------------------------------------------------------------

def _probe_ftp_directory(
    image_df: pd.DataFrame,
    verbose: bool = False,
) -> pd.DataFrame:
    """
    For each unique IMAGE_FILESPEC directory on the FTP server, list ALL
    files present and flag any that look like spectrum data files.

    Uses SecureFTP indirectly — we derive the FTP datasource string from
    SITE/QUERY_SITE exactly as surf_scan_images.py does, then attempt a
    directory listing.

    Returns a DataFrame of all files found, with columns:
        WAFER_KEY, DEFECT_ID, REMOTE_DIR, FILENAME, EXT, IS_SPECTRUM
    """
    import clr

    if GAJT_DLL_DIR not in sys.path:
        sys.path.append(GAJT_DLL_DIR)

    try:
        clr.AddReference("Intel.FabAuto.Quarc.Utilities")
        from Intel.FabAuto.Quarc import SecureFTP
    except Exception as exc:
        log.error("Could not load SecureFTP DLL: %s", exc)
        return pd.DataFrame()

    rows = []
    seen_dirs: set[str] = set()

    for _, img_row in image_df.iterrows():
        spec = str(img_row.get("IMAGE_FILESPEC", ""))
        if not spec:
            continue

        remote_dir = spec.rsplit("/", 1)[0] if "/" in spec else spec
        if remote_dir in seen_dirs:
            continue
        seen_dirs.add(remote_dir)

        wk  = img_row.get("WAFER_KEY")
        did = img_row.get("DEFECT_ID")

        # Datasource string mirrors surf_scan_images.py:
        # query_site = "D1D", ds = "D1D_PROD_YAS_1278_FTP"
        ds = f"D1D_PROD_YAS_{TECHNOLOGY}_FTP"

        log.info("  Probing FTP dir: %s  (ds=%s)", remote_dir, ds)

        try:
            # SecureFTP.ListFiles returns a comma- or newline-delimited string
            # of filenames in the remote directory.
            listing_raw = SecureFTP.ListFiles("D1D", ds, remote_dir, APP_NAME)

            if verbose:
                log.info("    Raw listing: %s", listing_raw)

            # Parse the listing — handle comma, newline, or semicolon delimiters
            filenames = [
                f.strip()
                for f in re.split(r"[,\n;]+", str(listing_raw))
                if f.strip()
            ]

            log.info("    %d file(s) found in directory", len(filenames))

            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                is_spectrum = ext in SPECTRUM_EXTENSIONS
                if is_spectrum:
                    log.info("    *** SPECTRUM FILE: %s", fname)
                elif verbose:
                    log.info("    file: %s", fname)

                rows.append({
                    "WAFER_KEY":   wk,
                    "DEFECT_ID":   did,
                    "REMOTE_DIR":  remote_dir,
                    "FILENAME":    fname,
                    "EXT":         ext,
                    "IS_SPECTRUM": is_spectrum,
                })

        except Exception as exc:
            log.warning("    Directory listing failed for %s: %s", remote_dir, exc)
            rows.append({
                "WAFER_KEY":   wk,
                "DEFECT_ID":   did,
                "REMOTE_DIR":  remote_dir,
                "FILENAME":    None,
                "EXT":         None,
                "IS_SPECTRUM": False,
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# STEP 4: download the images (mirrors _download_images exactly)
# ---------------------------------------------------------------------------

def _download_debug_images(
    image_df: pd.DataFrame,
    out_dir: Path,
) -> pd.DataFrame:
    """
    Download IMAGE_FILESPEC paths via SecureFTP into out_dir.
    Mirrors surf_scan_images.py _download_images() exactly.
    """
    import clr

    if GAJT_DLL_DIR not in sys.path:
        sys.path.append(GAJT_DLL_DIR)

    try:
        clr.AddReference("Intel.FabAuto.Quarc.Utilities")
        from Intel.FabAuto.Quarc import SecureFTP
    except Exception as exc:
        log.error("Could not load SecureFTP DLL: %s", exc)
        raise

    out_dir.mkdir(parents=True, exist_ok=True)
    df = image_df.copy()

    df["LOCAL_PATH"] = df["IMAGE_FILESPEC"].apply(
        lambda p: str(out_dir / p.lstrip("/\\").replace("/", os.sep))
        if pd.notna(p) else None
    )

    files = df["IMAGE_FILESPEC"].dropna().unique().tolist()
    if not files:
        log.warning("No IMAGE_FILESPEC values to download")
        return df

    ds = f"D1D_PROD_YAS_{TECHNOLOGY}_FTP"
    log.info("Downloading %d file(s) via %s -> %s", len(files), ds, out_dir)

    for i, spec in enumerate(files, 1):
        local = out_dir / spec.lstrip("/\\").replace("/", os.sep)
        if local.exists():
            log.info("  [%d/%d] already exists: %s", i, len(files), local.name)
            continue
        log.info("  [%d/%d] %s", i, len(files), spec)
        try:
            local.parent.mkdir(parents=True, exist_ok=True)
            SecureFTP.FtpFiles("D1D", ds, spec, str(out_dir), APP_NAME)
            log.info("    -> OK  local=%s", local)
        except Exception as exc:
            log.warning("    -> FAILED: %s", exc)

    return df


# ---------------------------------------------------------------------------
# STEP 5: print summary of what was downloaded
# ---------------------------------------------------------------------------

def _print_summary(
    defects_df: pd.DataFrame,
    image_df: pd.DataFrame,
    dir_listing_df: pd.DataFrame,
    out_dir: Path,
) -> None:
    print("\n" + "=" * 70)
    print("FTP DEBUG SUMMARY")
    print("=" * 70)

    print(f"\nDefects sampled: {len(defects_df)}")
    print(f"Image records from INSP_WAFER_IMAGE: {len(image_df)}")

    if not image_df.empty:
        print("\nIMAGE_FILESPEC paths returned by DB:")
        for spec in image_df["IMAGE_FILESPEC"].tolist():
            local = out_dir / spec.lstrip("/\\").replace("/", os.sep)
            exists = "EXISTS" if local.exists() else "MISSING"
            print(f"  [{exists}]  {spec}")

    if not dir_listing_df.empty:
        spectrum_files = dir_listing_df[dir_listing_df["IS_SPECTRUM"]]
        print(f"\nSpectrum files found on FTP server: {len(spectrum_files)}")
        if not spectrum_files.empty:
            print(spectrum_files[["WAFER_KEY", "DEFECT_ID", "REMOTE_DIR", "FILENAME"]].to_string(index=False))
        else:
            print("  (none found — only image files present in those directories)")

        print(f"\nAll file extensions seen in probed directories:")
        ext_counts = dir_listing_df["EXT"].value_counts()
        print(ext_counts.to_string())

    # Save results
    out_dir.mkdir(parents=True, exist_ok=True)
    if not image_df.empty:
        image_df.to_csv(out_dir / "debug_image_records.csv", index=False)
        log.info("Saved image records -> %s", out_dir / "debug_image_records.csv")
    if not dir_listing_df.empty:
        dir_listing_df.to_csv(out_dir / "debug_dir_listing.csv", index=False)
        log.info("Saved dir listing  -> %s", out_dir / "debug_dir_listing.csv")

    print("=" * 70)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def run(
    n_defects: int,
    lookback_days: int,
    image_ids: list[int],
    chamber_filter: list[str] | None,
    probe_spectrum: bool,
    download: bool,
    verbose: bool,
) -> None:

    log.info("GAJT_DLL_DIR: %s", GAJT_DLL_DIR)
    log.info("Output dir:   %s", DEBUG_OUTPUT_DIR)

    # 1. Pick defects
    defects_df = _pick_defects(n_defects, lookback_days, chamber_filter)
    if defects_df.empty:
        log.error("No defects to process — exiting")
        return

    # 2. Query INSP_WAFER_IMAGE
    log.info("\n--- Step 2: Query INSP_WAFER_IMAGE (IMAGE_IDs=%s) ---", image_ids)
    image_df = _fetch_image_paths(defects_df, image_ids)

    if image_df.empty:
        log.warning("No image records returned from DB")
        _print_summary(defects_df, image_df, pd.DataFrame(), DEBUG_OUTPUT_DIR)
        return

    # 3. Probe FTP directory for spectrum files
    dir_listing_df = pd.DataFrame()
    if probe_spectrum:
        log.info("\n--- Step 3: Probe FTP directories for spectrum files ---")
        dir_listing_df = _probe_ftp_directory(image_df, verbose=verbose)

    # 4. Download images
    if download:
        log.info("\n--- Step 4: Download images -> %s ---", DEBUG_OUTPUT_DIR)
        image_df = _download_debug_images(image_df, DEBUG_OUTPUT_DIR)
    else:
        log.info("--download not set — skipping FTP download")

    # 5. Summary
    _print_summary(defects_df, image_df, dir_listing_df, DEBUG_OUTPUT_DIR)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="FTP debug test for EDX images")
    p.add_argument(
        "--n-defects", type=int, default=3,
        help="Number of defects to sample (default: 3)",
    )
    p.add_argument(
        "--lookback-days", type=int, default=60,
        help="Days back to search in SS_COORDINATES.csv (default: 60)",
    )
    p.add_argument(
        "--image-ids", type=int, nargs="+", default=[2, 3, 4, 8],
        help="IMAGE_ID values to fetch (default: 2 3 4 8). "
             "8=spectrum keV scale image.",
    )
    p.add_argument(
        "--chamber", type=str, nargs="+", default=None,
        help="Optional PRIMARY_EQUIP filter e.g. --chamber AME401_PM1 AME419_PM6",
    )
    p.add_argument(
        "--probe-spectrum", action="store_true",
        help="List all files in each defect's FTP directory to find "
             "companion .txt/.spc spectrum data files",
    )
    p.add_argument(
        "--download", action="store_true",
        help="Actually download the images (omit for DB query only)",
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="Print full FTP directory listings",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    run(
        n_defects=args.n_defects,
        lookback_days=args.lookback_days,
        image_ids=args.image_ids,
        chamber_filter=args.chamber,
        probe_spectrum=args.probe_spectrum,
        download=args.download,
        verbose=args.verbose,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())