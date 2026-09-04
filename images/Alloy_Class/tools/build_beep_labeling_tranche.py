"""
Build the next rapid-labeling tranche of SMALL_PARTICLE defect pairs (BEEP vs
SMALL_PARTICLE disposition), for reporting/build_beep_labeling_report.py.

Primary source: outputs/defects/DEFECT_COORDINATES_EXTENDED.csv (full history,
never time-pruned -- see docs/TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md
plan notes). DEFECT_COORDINATES_EXTENDED_IMAGES.csv is used only as a secondary
lookup for currently-available LOCAL_IMAGE_FILE paths (it is a rolling ~60-day
window and is NOT the population source).

Selection: newest INSPECTION_TIME first, excluding any pair_key already present
in the ground-truth CSV or in any prior tranche_*_cases.csv file, so re-running
this script naturally surfaces new manifest additions at the front of the queue
without ever re-serving an already-labeled or already-tranched case.

Usage:
    python build_beep_labeling_tranche.py [--tranche-size 100] [--allow-redownload]
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

ALLOY_CLASS_ROOT = Path(__file__).resolve().parents[1]
BE_ROOT = ALLOY_CLASS_ROOT.parents[1]  # Alloy_Class -> images -> BE
BE_QUERY_FILES_DIR = BE_ROOT / "BE_QUERY_FILES"

COORDS_CSV = BE_ROOT / "outputs" / "defects" / "DEFECT_COORDINATES_EXTENDED.csv"
RAW_IMAGE_MANIFEST_CSV = Path(r"C:\RAW_IMAGES\manifest.csv")
OUTPUT_DIR = ALLOY_CLASS_ROOT / "outputs" / "beep_evidence"
GROUND_TRUTH_CSV = OUTPUT_DIR / "beep_evidence_ground_truth.csv"

DEFAULT_TRANCHE_SIZE = 100
CLASS_OF_INTEREST = "SMALL_PARTICLE"


def _pair_key(row: pd.Series) -> str:
    insp = pd.to_datetime(row["INSPECTION_TIME"], errors="coerce")
    insp_str = insp.strftime("%Y%m%d_%H%M%S") if pd.notna(insp) else "UNKNOWN"
    return f"{row['WAFER_KEY']}_{insp_str}_{row['DEFECT_ID']}"


def _normalize_join_value(value: object) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _load_candidate_population(coords_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(coords_csv, low_memory=False)
    df = df[df["CLASS"] == CLASS_OF_INTEREST].copy()
    for col in ("WAFER_KEY", "DEFECT_ID"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["WAFER_KEY", "DEFECT_ID", "INSPECTION_TIME"])
    df["WAFER_KEY"] = df["WAFER_KEY"].astype("int64")
    df["DEFECT_ID"] = df["DEFECT_ID"].astype("int64")
    df["INSPECTION_TIME_DT"] = pd.to_datetime(df["INSPECTION_TIME"], errors="coerce")
    df["pair_key"] = df.apply(_pair_key, axis=1)
    # Coordinate CSV accumulation keeps the newest row per (WAFER_KEY,
    # INSPECTION_TIME, DEFECT_ID) key already, but guard here too.
    df = df.drop_duplicates(subset=["pair_key"], keep="last")
    return df


def _attach_local_image_paths(candidates: pd.DataFrame, images_csv: Path) -> pd.DataFrame:
    out = candidates.copy()
    if not images_csv.exists():
        out["bright_image_path"] = None
        out["dark_image_path"] = None
        return out

    img = pd.read_csv(images_csv, low_memory=False, dtype=str)
    required = {"wafer_key", "defect_id", "inspection_time", "image_id", "local_path"}
    missing = required - set(img.columns)
    if missing:
        raise RuntimeError(f"Raw image manifest missing required columns: {', '.join(sorted(missing))}")

    img["wafer_key"] = pd.to_numeric(img["wafer_key"], errors="coerce")
    img["defect_id"] = pd.to_numeric(img["defect_id"], errors="coerce")
    img["image_id"] = pd.to_numeric(img["image_id"], errors="coerce")
    img = img.dropna(subset=["wafer_key", "defect_id", "inspection_time", "image_id", "local_path"])
    img["wafer_key"] = img["wafer_key"].astype("int64")
    img["defect_id"] = img["defect_id"].astype("int64")
    img["image_id"] = img["image_id"].astype("int64")
    img = img[img["local_path"].fillna("").astype(str).str.strip() != ""]
    img = img[img["local_path"].apply(lambda p: os.path.isfile(str(p)))]

    img["inspection_time_dt"] = pd.to_datetime(img["inspection_time"], errors="coerce")
    img = img.dropna(subset=["inspection_time_dt"])
    img["inspection_time_norm"] = img["inspection_time_dt"].dt.strftime("%Y%m%d_%H%M%S")

    img["join_wafer_key"] = img["wafer_key"].astype(str)
    img["join_defect_id"] = img["defect_id"].astype(str)

    def _join_key_frame(frame: pd.DataFrame) -> pd.DataFrame:
        cols = ["join_wafer_key", "inspection_time_norm", "join_defect_id", "local_path"]
        return frame[cols].copy()

    bright = img[img["image_id"] == 2].copy()
    bright = _join_key_frame(bright)
    bright = bright.drop_duplicates(subset=["join_wafer_key", "inspection_time_norm", "join_defect_id"], keep="last")
    bright = bright.rename(columns={"local_path": "bright_image_path"})

    dark = img[img["image_id"] == 3].copy()
    dark = _join_key_frame(dark)
    dark = dark.drop_duplicates(subset=["join_wafer_key", "inspection_time_norm", "join_defect_id"], keep="last")
    dark = dark.rename(columns={"local_path": "dark_image_path"})

    out["join_wafer_key"] = out["WAFER_KEY"].map(_normalize_join_value)
    out["join_defect_id"] = out["DEFECT_ID"].map(_normalize_join_value)
    out["inspection_time_dt"] = pd.to_datetime(out["INSPECTION_TIME"], errors="coerce")
    out["inspection_time_norm"] = out["inspection_time_dt"].dt.strftime("%Y%m%d_%H%M%S")

    out = out.merge(bright, on=["join_wafer_key", "inspection_time_norm", "join_defect_id"], how="left")
    out = out.merge(dark, on=["join_wafer_key", "inspection_time_norm", "join_defect_id"], how="left")
    out = out.drop(columns=["join_wafer_key", "join_defect_id", "inspection_time_dt", "inspection_time_norm"])

    if "bright_image_path" not in out.columns:
        out["bright_image_path"] = None
    if "dark_image_path" not in out.columns:
        out["dark_image_path"] = None
    return out


def _already_labeled_pair_keys(ground_truth_csv: Path) -> set[str]:
    if not ground_truth_csv.exists():
        return set()
    gt = pd.read_csv(ground_truth_csv, dtype=str)
    if "pair_key" not in gt.columns:
        return set()
    return set(gt["pair_key"].dropna().unique())


def _already_tranched_pair_keys(output_dir: Path) -> set[str]:
    keys: set[str] = set()
    for path in glob.glob(str(output_dir / "tranche_*_cases.csv")):
        try:
            df = pd.read_csv(path, dtype=str, usecols=["pair_key"])
        except Exception:
            continue
        keys.update(df["pair_key"].dropna().unique())
    return keys


def _next_tranche_number(output_dir: Path) -> int:
    existing = glob.glob(str(output_dir / "tranche_*_cases.csv"))
    numbers = []
    for path in existing:
        stem = Path(path).stem  # tranche_0007_cases
        parts = stem.split("_")
        if len(parts) >= 2 and parts[1].isdigit():
            numbers.append(int(parts[1]))
    return (max(numbers) + 1) if numbers else 1


def _attempt_redownload_missing(
    missing: pd.DataFrame,
    image_folder: Path,
) -> dict[tuple[int, int, int], str]:
    """
    Best-effort on-demand redownload for cases missing a local image, reusing
    the routine pipeline's SecureFTP/GAJT-dependent functions. Fail-open: any
    import/connection/runtime problem is logged and treated as "unavailable"
    rather than crashing the tranche build (matches DEFECT_COORDINATES_QUERY.py's
    own convention for the same dependency).

    Returns a {(WAFER_KEY, DEFECT_ID, IMAGE_ID): LOCAL_IMAGE_FILE} mapping for
    whatever was successfully fetched (possibly empty).
    """
    if missing.empty:
        return {}

    sys.path.insert(0, str(BE_QUERY_FILES_DIR))
    try:
        import DEFECT_COORDINATES_QUERY as dcq  # noqa: N813
    except Exception as exc:
        print(f"  WARNING: redownload unavailable (import failed): {exc}")
        return {}

    try:
        conn = dcq._connect(dcq.DATABASE)
    except Exception as exc:
        print(f"  WARNING: redownload unavailable (DB connect failed): {exc}")
        return {}

    try:
        defects_subset = missing.drop(columns=["INSPECTION_TIME"], errors="ignore").copy()
        defects_subset = defects_subset.rename(columns={"INSPECTION_TIME_DT": "INSPECTION_TIME"})
        image_df = dcq._fetch_image_metadata(conn, defects_subset, image_id_filter=[2, 3])
    finally:
        conn.close()

    if image_df.empty:
        print("  Redownload: no image metadata found for missing cases.")
        return {}

    image_df = dcq._enrich_image_rows_with_defect_context(image_df, defects_subset)
    image_df = dcq._download_and_reorganize_images(
        image_df,
        defects_subset,
        str(image_folder),
        dcq.APP_NAME,
        technology=dcq.TECHNOLOGY,
        ftp_chunk_size=dcq.IMAGE_FTP_CHUNK_SIZE,
        annotate=dcq.ANNOTATE_IMAGES,
    )
    if image_df.empty:
        print("  Redownload skipped: SecureFTP runtime unavailable.")
        return {}

    mapping: dict[tuple[int, int, int], str] = {}
    for _, row in image_df.iterrows():
        if pd.notna(row.get("LOCAL_IMAGE_FILE")):
            key = (int(row["WAFER_KEY"]), int(row["DEFECT_ID"]), int(float(row["IMAGE_ID"])))
            mapping[key] = row["LOCAL_IMAGE_FILE"]
    return mapping


def _build_raw_cache_dir(base_dir: Path, tranche_id: str) -> Path:
    return base_dir / tranche_id


def build_tranche(
    tranche_size: int,
    allow_redownload: bool,
    raw_cache_root: Path | None = None,
) -> tuple[Path, int, int]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    candidates = _load_candidate_population(COORDS_CSV)
    candidates = _attach_local_image_paths(candidates, RAW_IMAGE_MANIFEST_CSV)

    excluded = _already_labeled_pair_keys(GROUND_TRUTH_CSV) | _already_tranched_pair_keys(OUTPUT_DIR)
    candidates = candidates[~candidates["pair_key"].isin(excluded)].copy()

    candidates = candidates.sort_values("INSPECTION_TIME_DT", ascending=False)
    selected = candidates.head(tranche_size).copy()

    tranche_num = _next_tranche_number(OUTPUT_DIR)
    tranche_id = f"tranche_{tranche_num:04d}"
    cache_root = raw_cache_root or Path(r"C:\RAW_IMAGES")
    tranche_cache_dir = _build_raw_cache_dir(cache_root, tranche_id)

    missing_mask = selected["bright_image_path"].isna() | selected["dark_image_path"].isna()
    if missing_mask.any():
        missing_rows = selected[missing_mask].copy()
        if allow_redownload:
            print(f"Attempting on-demand redownload for {len(missing_rows)} case(s)...")
            print(f"  Raw image cache: {tranche_cache_dir}")
            tranche_cache_dir.mkdir(parents=True, exist_ok=True)
            fetched = _attempt_redownload_missing(missing_rows, tranche_cache_dir)
            for idx, row in selected[missing_mask].iterrows():
                wk, did = int(row["WAFER_KEY"]), int(row["DEFECT_ID"])
                if pd.isna(row["bright_image_path"]):
                    path = fetched.get((wk, did, 2))
                    if path:
                        selected.at[idx, "bright_image_path"] = path
                if pd.isna(row["dark_image_path"]):
                    path = fetched.get((wk, did, 3))
                    if path:
                        selected.at[idx, "dark_image_path"] = path
        else:
            print(
                f"  {len(missing_rows)} candidate case(s) are missing bright/dark images "
                "locally; skipping redownload (pass --allow-redownload to attempt it)."
            )

    still_missing_mask = selected["bright_image_path"].isna() | selected["dark_image_path"].isna()
    complete = selected[~still_missing_mask].copy()
    skipped = selected[still_missing_mask].copy()

    out_cols = [
        "pair_key", "WAFER_KEY", "INSPECTION_TIME", "LOT", "DEFECT_ID", "LAYER",
        "SUBENTITY", "CLASS", "bright_image_path", "dark_image_path",
    ]
    out_cols = [c for c in out_cols if c in complete.columns]
    cases_path = OUTPUT_DIR / f"{tranche_id}_cases.csv"
    complete[out_cols].rename(columns={
        "WAFER_KEY": "wafer_key", "INSPECTION_TIME": "inspection_time", "LOT": "lot",
        "DEFECT_ID": "defect_id", "LAYER": "layer", "SUBENTITY": "subentity",
        "CLASS": "factory_class",
    }).to_csv(cases_path, index=False)

    if not skipped.empty:
        skipped_path = OUTPUT_DIR / f"{tranche_id}_skipped_missing_images.csv"
        skipped[out_cols].rename(columns={
            "WAFER_KEY": "wafer_key", "INSPECTION_TIME": "inspection_time", "LOT": "lot",
            "DEFECT_ID": "defect_id", "LAYER": "layer", "SUBENTITY": "subentity",
            "CLASS": "factory_class",
        }).to_csv(skipped_path, index=False)
        print(f"  {len(skipped)} case(s) skipped (missing images) -> {skipped_path}")

    print(f"Tranche '{tranche_id}': {len(complete)} case(s) -> {cases_path}")
    return cases_path, len(complete), len(skipped)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tranche-size", type=int, default=DEFAULT_TRANCHE_SIZE)
    parser.add_argument(
        "--allow-redownload", action="store_true",
        help="Attempt on-demand SecureFTP redownload for cases missing local images "
        "(requires the same GAJT/CLR runtime as the routine pipeline).",
    )
    parser.add_argument(
        "--raw-cache-root",
        default=r"C:\RAW_IMAGES",
        help="Local root for staged raw image downloads; each tranche gets its own subfolder.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    build_tranche(
        tranche_size=args.tranche_size,
        allow_redownload=args.allow_redownload,
        raw_cache_root=Path(args.raw_cache_root),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
