"""
fetch_spectrum_txt.py
---------------------
Focused script to locate and download raw EDX spectrum .txt files
from the YAS FTP server for defects that have spectrum images.

The spectrum .txt file lives in the same FTP directory as the images.
Naming convention candidates based on observed image filename pattern:
  D062826@115911W0007135045F0000000003I008K251214944.txt  <- same as img, .txt ext
  D062826@115911W0007135045F0000000003.txt                <- no image ID suffix
  W0007135045F0000000003.txt                              <- wafer+defect only
  7135045_3.txt                                           <- short wafer_defect
  spectrum_F0000000003.txt                                <- spectrum prefix

Usage:
    python fetch_spectrum_txt.py
    python fetch_spectrum_txt.py --n-defects 5 --lookback-days 60
    python fetch_spectrum_txt.py --wafer-key 7135045 --defect-id 3
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

COORDS_CSV = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\surf_scan\SS_COORDINATES.csv"
DEBUG_OUTPUT_DIR = Path(r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\surf_scan\ftp_debug\spectra")

DATABASE   = "D1D_PROD_YAS_1278"
APP_NAME   = "GAJT_INLINE_24601"
TECHNOLOGY = "1278"

_GAJT_DLL_CANDIDATES = [
    os.path.join(os.path.expanduser("~"), r"AppData\Roaming\SAS\JMP\AddIns\gajtv.intel.com\wijt"),
    r"D:\gajtv\configurations\wijt",
]

# IMAGE_IDs that correspond to spectrum images
# Script will look for .txt companion at same path with .txt extension
SPECTRUM_IMAGE_IDS = [13, 14, 15]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fetch_spectrum_txt")


# ---------------------------------------------------------------------------
# DLL resolution
# ---------------------------------------------------------------------------

def _resolve_gajt_dll_dir() -> str:
    env = os.environ.get("GAJT_DLL_DIR", "").strip()
    if env:
        return env
    for c in _GAJT_DLL_CANDIDATES:
        if os.path.isfile(os.path.join(c, "Intel.FabAuto.Quarc.Utilities.dll")):
            return c
    return _GAJT_DLL_CANDIDATES[0]

GAJT_DLL_DIR = _resolve_gajt_dll_dir()


# ---------------------------------------------------------------------------
# STEP 1: Query INSP_WAFER_IMAGE for spectrum image rows
#         — gives us the exact FTP directory and filename stem
# ---------------------------------------------------------------------------

def _fetch_spectrum_image_paths(
    defects_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Query INSP_WAFER_IMAGE for IMAGE_IDs 8-12 (spectrum positions).
    Returns rows with IMAGE_FILESPEC so we know the exact FTP path.
    Also fetches IMAGE_ID=1 as fallback to confirm the directory exists.
    """
    import PyUber

    id_list = ", ".join(str(i) for i in SPECTRUM_IMAGE_IDS)
    all_chunks = []

    conn = PyUber.connect(DATABASE)
    try:
        for _, row in defects_df.iterrows():
            wk       = int(row["WAFER_KEY"])
            did      = int(row["DEFECT_ID"])
            img_cnt  = int(row.get("IMAGE_COUNT", 16))
            insp_str = pd.Timestamp(row["INSPECTION_TIME"]).strftime("%Y%m%d%H%M%S")

            # Apply offset for over-16 blocks
            offset = max(0, img_cnt - 16)
            actual_ids = [i + offset for i in SPECTRUM_IMAGE_IDS]
            actual_id_list = ", ".join(str(i) for i in actual_ids)

            log.info(
                "  Querying WK=%s DID=%s IMG_CNT=%s offset=%s -> spectrum IDs=%s",
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
WHERE i.WAFER_KEY       = {wk}
  AND i.INSPECTION_TIME = TO_DATE('{insp_str}','YYYYMMDDHH24MISS')
  AND i.DEFECT_ID       = {did}
  AND i.IMAGE_ID        IN ({actual_id_list})
ORDER BY i.IMAGE_ID
"""
            chunk = pd.read_sql(sql, conn)
            log.info("    -> %d spectrum image record(s)", len(chunk))
            for _, r in chunk.iterrows():
                log.info("      IMAGE_ID=%s  FILESPEC=%s", r["IMAGE_ID"], r["IMAGE_FILESPEC"])
            all_chunks.append(chunk)

    finally:
        conn.close()

    if not all_chunks:
        return pd.DataFrame()
    return pd.concat(all_chunks, ignore_index=True)


# ---------------------------------------------------------------------------
# STEP 2: Build .txt candidate paths from image FILESPEC
# ---------------------------------------------------------------------------

def _build_txt_candidates(image_filespec: str) -> list[str]:
    """
    Given an image FILESPEC, generate candidate .emsa paths.

    Observed pattern:
      /yas/data/images20/rf3pap1118x006/20260625/23/5306_7046563/
        D1D-D344TD1N1-062526@235306-179-0000000003I013K250678593.emsa

    IMAGE_IDs 13 and 14 are the .emsa spectrum files.
    JPG images use IMAGE_IDs 1-12.
    """
    import re

    spec       = image_filespec.strip()
    remote_dir = spec.rsplit("/", 1)[0]
    filename   = spec.rsplit("/", 1)[1]
    stem       = filename.rsplit(".", 1)[0]   # strip extension

    # Parse components
    # D1D-D344TD1N1-062526@235306-179-0000000003I013K250678593
    did_match  = re.search(r"-(\d{10})I(\d+)K(\d+)$", stem)
    dt_match   = re.search(r"(\d{6}@\d{6})", stem)
    tool_match = re.search(r"D1D-([^-]+)-", stem)

    did_str    = did_match.group(1)  if did_match  else ""   # 0000000003
    img_id_str = did_match.group(2)  if did_match  else ""   # 013
    k_str      = did_match.group(3)  if did_match  else ""   # 250678593
    dt_str     = dt_match.group(1)   if dt_match   else ""   # 062526@235306
    tool_str   = tool_match.group(1) if tool_match else ""   # D344TD1N1

    # Base stem without I###K### suffix
    base_stem = re.sub(r"I\d+K\d+$", "", stem).rstrip("-")

    candidates = []

    # 1. Exact filename with .emsa (same IMAGE_ID)
    candidates.append(f"{remote_dir}/{stem}.emsa")

    # 2. Try IMAGE_IDs 13 and 14 explicitly with same K value
    if did_str and k_str and dt_str and tool_str:
        prefix = f"D1D-{tool_str}-{dt_str}"
        # extract the middle index (179 in example)
        idx_match = re.search(rf"{re.escape(dt_str)}-(\d+)-", stem)
        idx_str = idx_match.group(1) if idx_match else ""
        if idx_str:
            for iid in [13, 14, 15]:
                candidates.append(
                    f"{remote_dir}/{prefix}-{idx_str}-{did_str}I{iid:03d}K{k_str}.emsa"
                )

    # 3. Base stem (no image ID) with .emsa
    if base_stem != stem:
        candidates.append(f"{remote_dir}/{base_stem}.emsa")

    # 4. Also try .txt and .msa just in case
    candidates.append(f"{remote_dir}/{stem}.txt")
    candidates.append(f"{remote_dir}/{stem}.msa")
    if base_stem != stem:
        candidates.append(f"{remote_dir}/{base_stem}.txt")
        candidates.append(f"{remote_dir}/{base_stem}.msa")

    # Deduplicate preserving order
    seen = set()
    out  = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out

# ---------------------------------------------------------------------------
# STEP 3: Try to download each candidate via SecureFTP.FtpFiles
# ---------------------------------------------------------------------------

def _try_download_txt(
    candidates: list[str],
    out_dir: Path,
    dry_run: bool = False,
) -> tuple[str | None, Path | None]:
    """
    Try each candidate path via SecureFTP.FtpFiles.
    Returns (remote_path_that_worked, local_path) or (None, None).

    SecureFTP.FtpFiles raises on file-not-found, so we catch per candidate.
    """
    import clr
    if GAJT_DLL_DIR not in sys.path:
        sys.path.append(GAJT_DLL_DIR)
    clr.AddReference("Intel.FabAuto.Quarc.Utilities")
    from Intel.FabAuto.Quarc import SecureFTP

    ds = f"D1D_PROD_YAS_{TECHNOLOGY}_FTP"

    for candidate in candidates:
        fname     = candidate.rsplit("/", 1)[-1]
        local_path = out_dir / fname
        out_dir.mkdir(parents=True, exist_ok=True)

        log.info("    trying: %s", candidate)

        if dry_run:
            log.info("    [dry_run] would attempt: %s", candidate)
            continue

        try:
            SecureFTP.FtpFiles("D1D", ds, candidate, str(out_dir), APP_NAME)
            # If no exception, file was found and downloaded
            if local_path.exists() and local_path.stat().st_size > 0:
                log.info("    SUCCESS: %s -> %s", candidate, local_path)
                return candidate, local_path
            else:
                log.info("    FtpFiles returned but file empty/missing locally")
        except Exception as exc:
            log.debug("    not found (%s)", exc)
            continue

    return None, None


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def run(
    n_defects: int,
    lookback_days: int,
    wafer_key: int | None,
    defect_id: int | None,
    dry_run: bool,
) -> None:

    log.info("GAJT_DLL_DIR: %s", GAJT_DLL_DIR)
    log.info("Output dir:   %s", DEBUG_OUTPUT_DIR)

    # ------------------------------------------------------------------
    # Build defect list
    # ------------------------------------------------------------------
    if wafer_key and defect_id:
        # Manual override — look up this specific defect
        log.info("Manual mode: WK=%s DID=%s", wafer_key, defect_id)
        df = pd.read_csv(COORDS_CSV, low_memory=False)
        df["WAFER_KEY"]  = pd.to_numeric(df["WAFER_KEY"],  errors="coerce")
        df["DEFECT_ID"]  = pd.to_numeric(df["DEFECT_ID"],  errors="coerce")
        df["IMAGE_COUNT"]= pd.to_numeric(df.get("IMAGE_COUNT", 0), errors="coerce").fillna(0)
        df["INSPECTION_TIME"] = pd.to_datetime(df["INSPECTION_TIME"], errors="coerce")
        defects_df = df[
            (df["WAFER_KEY"] == wafer_key) &
            (df["DEFECT_ID"] == defect_id)
        ].drop_duplicates(subset=["WAFER_KEY", "DEFECT_ID"]).head(1)

        if defects_df.empty:
            log.error("WK=%s DID=%s not found in coords CSV", wafer_key, defect_id)
            return
    else:
        # Auto-select: most recent defects with IMAGE_COUNT >= 8
        log.info("Auto mode: selecting %d defects with IMAGE_COUNT >= 8", n_defects)
        df = pd.read_csv(COORDS_CSV, low_memory=False)
        df["WAFER_KEY"]  = pd.to_numeric(df["WAFER_KEY"],  errors="coerce")
        df["DEFECT_ID"]  = pd.to_numeric(df["DEFECT_ID"],  errors="coerce")
        df["IMAGE_COUNT"]= pd.to_numeric(df.get("IMAGE_COUNT", 0), errors="coerce").fillna(0)
        df["INSPECTION_TIME"] = pd.to_datetime(df["INSPECTION_TIME"], errors="coerce")

        cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
        df = df[
            (df["INSPECTION_TIME"] >= cutoff) &
            (df["IMAGE_COUNT"] >= 8)
        ]
        log.info("  Defects with IMAGE_COUNT >= 8 in last %dd: %d", lookback_days, len(df))

        if df.empty:
            log.warning("No defects with IMAGE_COUNT >= 8 found — widening to IMAGE_COUNT > 0")
            df = pd.read_csv(COORDS_CSV, low_memory=False)
            df["WAFER_KEY"]  = pd.to_numeric(df["WAFER_KEY"],  errors="coerce")
            df["DEFECT_ID"]  = pd.to_numeric(df["DEFECT_ID"],  errors="coerce")
            df["IMAGE_COUNT"]= pd.to_numeric(df.get("IMAGE_COUNT", 0), errors="coerce").fillna(0)
            df["INSPECTION_TIME"] = pd.to_datetime(df["INSPECTION_TIME"], errors="coerce")
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
            df = df[(df["INSPECTION_TIME"] >= cutoff) & (df["IMAGE_COUNT"] > 0)]

        defects_df = (
            df.sort_values("INSPECTION_TIME", ascending=False)
            .drop_duplicates(subset=["WAFER_KEY", "DEFECT_ID"])
            .head(n_defects)
            .reset_index(drop=True)
        )

    log.info("Processing %d defect(s):", len(defects_df))
    for _, r in defects_df.iterrows():
        log.info(
            "  WK=%-10s DID=%-6s IMG_CNT=%-4s TIME=%s",
            int(r["WAFER_KEY"]), int(r["DEFECT_ID"]),
            int(r["IMAGE_COUNT"]), r["INSPECTION_TIME"],
        )

    # ------------------------------------------------------------------
    # Query INSP_WAFER_IMAGE for spectrum image rows (IMAGE_ID 8-12)
    # ------------------------------------------------------------------
    log.info("\n--- Querying INSP_WAFER_IMAGE for spectrum IMAGE_IDs %s ---",
             SPECTRUM_IMAGE_IDS)
    image_df = _fetch_spectrum_image_paths(defects_df)

    if image_df.empty:
        log.warning(
            "No spectrum image records found for IMAGE_IDs %s\n"
            "  -> These defects may have IMAGE_COUNT < 8\n"
            "  -> Try --lookback-days 120 or specify --wafer-key / --defect-id manually",
            SPECTRUM_IMAGE_IDS,
        )
        return

    # ------------------------------------------------------------------
    # For each spectrum image row, try to download companion .txt
    # ------------------------------------------------------------------
    log.info("\n--- Attempting .txt companion file download ---")
    results = []

    for _, img_row in image_df.iterrows():
        spec = str(img_row.get("IMAGE_FILESPEC", ""))
        if not spec:
            continue

        wk  = img_row["WAFER_KEY"]
        did = img_row["DEFECT_ID"]
        iid = img_row["IMAGE_ID"]

        log.info(
            "\nWK=%s DID=%s IMAGE_ID=%s\n  FILESPEC=%s",
            wk, did, iid, spec,
        )

        candidates = _build_txt_candidates(spec)
        log.info("  %d candidate path(s) to try:", len(candidates))

        remote_found, local_path = _try_download_txt(
            candidates, DEBUG_OUTPUT_DIR, dry_run=dry_run
        )

        results.append({
            "WAFER_KEY":    wk,
            "DEFECT_ID":    did,
            "IMAGE_ID":     iid,
            "IMAGE_FILESPEC": spec,
            "TXT_REMOTE":   remote_found,
            "TXT_LOCAL":    str(local_path) if local_path else None,
            "FOUND":        remote_found is not None,
        })

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    results_df = pd.DataFrame(results)
    found    = results_df["FOUND"].sum()
    not_found = (~results_df["FOUND"]).sum()

    print("\n" + "=" * 70)
    print("SPECTRUM TXT FETCH SUMMARY")
    print("=" * 70)
    print(f"Spectrum image records queried: {len(results_df)}")
    print(f"  .txt found and downloaded:    {found}")
    print(f"  .txt not found:               {not_found}")

    if found:
        print("\nDownloaded files:")
        for _, r in results_df[results_df["FOUND"]].iterrows():
            print(f"  WK={r['WAFER_KEY']} DID={r['DEFECT_ID']} -> {r['TXT_LOCAL']}")
            # Peek at first 20 lines of the file
            try:
                lines = Path(r["TXT_LOCAL"]).read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()[:20]
                print("  --- file preview (first 20 lines) ---")
                for line in lines:
                    print(f"    {line}")
                print("  ---")
            except Exception as exc:
                print(f"  (could not preview: {exc})")
    else:
        print("\nNo .txt files found.")
        print("Candidates tried for first record:")
        if not image_df.empty:
            first_spec = str(image_df.iloc[0]["IMAGE_FILESPEC"])
            for c in _build_txt_candidates(first_spec):
                print(f"  {c}")

    # Save results
    DEBUG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = DEBUG_OUTPUT_DIR / "spectrum_txt_search_results.csv"
    results_df.to_csv(out_csv, index=False)
    log.info("\nResults saved -> %s", out_csv)
    print("=" * 70)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Locate and download EDX spectrum .txt files from YAS FTP"
    )
    p.add_argument("--n-defects",    type=int, default=3)
    p.add_argument("--lookback-days",type=int, default=60)
    p.add_argument("--wafer-key",    type=int, default=None,
                   help="Specific WAFER_KEY to target")
    p.add_argument("--defect-id",    type=int, default=None,
                   help="Specific DEFECT_ID to target")
    p.add_argument("--dry-run",      action="store_true",
                   help="Show candidates without downloading")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    run(
        n_defects=args.n_defects,
        lookback_days=args.lookback_days,
        wafer_key=args.wafer_key,
        defect_id=args.defect_id,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())