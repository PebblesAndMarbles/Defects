"""Build a candidate manifest for re-downloading raw (non-burned) defect images.

This tool does not perform downloads. It prepares a filtered and deduplicated
request table from the 60-day image manifest so a follow-on downloader (or DB
query flow) can fetch source images without burned-in overlays.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = (
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson"
    r"\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv"
)
DEFAULT_OUTPUT = "outputs/phase1_pairsafe/raw_redownload_manifest.csv"

# Candidate columns that may carry source-system locations in future schemas.
SOURCE_PATH_CANDIDATES = [
    "YAS_FILE_PATH",
    "RAW_IMAGE_FILE",
    "SOURCE_FILE",
    "IMAGE_PATH",
    "FILE_PATH",
    "IMAGE_FILESPEC",
]

KEEP_BASE = [
    "WAFER_KEY",
    "DEFECT_ID",
    "INSPECTION_TIME",
    "IMAGE_ID",
    "IMAGE_SERVER_ID",
    "IMAGE_FILESPEC",
    "LOCAL_IMAGE_FILE",
    "SITE",
    "QUERY_SITE",
    "LAYER",
    "CLASS",
    "FINEBIN",
    "SUBENTITY",
    "INVENTORY_ONLY",
]


def _to_int_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _pick_first_present(columns: list[str], df: pd.DataFrame) -> list[str]:
    return [c for c in columns if c in df.columns]


def build_manifest(
    input_csv: Path,
    output_csv: Path,
    image_ids: list[int],
    only_non_inventory: bool,
    include_only_missing_source_path: bool,
) -> tuple[int, int, int]:
    df = pd.read_csv(input_csv, low_memory=False)

    required = ["WAFER_KEY", "DEFECT_ID", "INSPECTION_TIME", "IMAGE_ID"]
    for col in required:
        if col not in df.columns:
            raise RuntimeError(f"Missing required column: {col}")

    work = df.copy()
    work["_IMAGE_ID_INT"] = _to_int_series(work["IMAGE_ID"])

    if image_ids:
        work = work[work["_IMAGE_ID_INT"].isin(image_ids)]

    if only_non_inventory and "INVENTORY_ONLY" in work.columns:
        inv = pd.to_numeric(work["INVENTORY_ONLY"], errors="coerce").fillna(0).astype(int)
        work = work[inv == 0]

    present_source_cols = _pick_first_present(SOURCE_PATH_CANDIDATES, work)
    # Prefer explicit raw/source path candidates over IMAGE_FILESPEC.
    explicit_source_cols = [c for c in present_source_cols if c != "IMAGE_FILESPEC"]

    if include_only_missing_source_path:
        if explicit_source_cols:
            has_any_source = pd.Series(False, index=work.index)
            for col in explicit_source_cols:
                has_any_source = has_any_source | work[col].astype(str).str.strip().ne("")
            work = work[~has_any_source]

    keep_cols = _pick_first_present(KEEP_BASE, work)
    for col in SOURCE_PATH_CANDIDATES:
        if col in work.columns and col not in keep_cols:
            keep_cols.append(col)

    out = work[keep_cols].copy()
    out = out.drop_duplicates(
        subset=["WAFER_KEY", "DEFECT_ID", "INSPECTION_TIME", "IMAGE_ID"],
        keep="last",
    )

    # Explicit request key to hand over to raw-image downloader flow.
    out["REQUEST_KEY"] = (
        out["WAFER_KEY"].astype(str)
        + "|"
        + out["INSPECTION_TIME"].astype(str)
        + "|"
        + out["DEFECT_ID"].astype(str)
        + "|"
        + out["IMAGE_ID"].astype(str)
    )

    # Mark whether explicit source path fields are currently populated.
    if explicit_source_cols:
        has_explicit = pd.Series(False, index=out.index)
        for col in explicit_source_cols:
            has_explicit = has_explicit | out[col].astype(str).str.strip().ne("")
        out["HAS_EXPLICIT_SOURCE_PATH"] = has_explicit.astype(int)
    else:
        out["HAS_EXPLICIT_SOURCE_PATH"] = 0

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)

    return len(df), len(work), len(out)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build candidate raw-image redownload manifest")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT)
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--image-ids",
        default="2,3",
        help="Comma-separated IMAGE_ID values to include (default: 2,3)",
    )
    parser.add_argument(
        "--allow-inventory-only",
        action="store_true",
        help="Include INVENTORY_ONLY rows (default excludes them)",
    )
    parser.add_argument(
        "--only-missing-source-path",
        action="store_true",
        help="Keep only rows with no explicit source path fields populated",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    image_ids = []
    for token in str(args.image_ids).split(","):
        token = token.strip()
        if not token:
            continue
        image_ids.append(int(token))

    total, filtered, written = build_manifest(
        input_csv=Path(args.input_csv),
        output_csv=Path(args.output_csv),
        image_ids=image_ids,
        only_non_inventory=not args.allow_inventory_only,
        include_only_missing_source_path=args.only_missing_source_path,
    )
    print(f"rows_input={total}")
    print(f"rows_filtered={filtered}")
    print(f"rows_written={written}")
    print(f"output_csv={Path(args.output_csv).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
