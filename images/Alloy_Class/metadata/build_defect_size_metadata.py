"""
Build image-level defect metrology metadata for Alloy Phase 1 runs.

Expected sources:
- outputs/defects/DEFECT_COORDINATES_EXTENDED.csv
- outputs/defects/DEFECT_COORDINATES_EXTENDED_IMAGES.csv

If SIZE_X/SIZE_Y/SIZE_D/AREA/MANUAL_OPTICAL_CLASS exist in the coordinates CSV, this script
produces a join table keyed by image_name.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path


REQUIRED_JOIN_KEYS = ["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"]
METROLOGY_COLS = ["SIZE_X", "SIZE_Y", "SIZE_D", "AREA", "MANUAL_OPTICAL_CLASS"]


def _normalize_key(value: str) -> str:
    text = (value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _image_name_from_local_path(local_path: str) -> str:
    if not local_path:
        return ""
    return os.path.basename(local_path.replace("/", "\\"))


def build_metadata(coords_csv: Path, images_csv: Path, output_csv: Path) -> tuple[int, int, int]:
    with coords_csv.open("r", encoding="utf-8-sig", newline="") as f:
        coords_reader = csv.DictReader(f)
        coord_fields = coords_reader.fieldnames or []

        for key in REQUIRED_JOIN_KEYS:
            if key not in coord_fields:
                raise RuntimeError(f"Missing join key in coords CSV: {key}")

        present_metrology = [c for c in METROLOGY_COLS if c in coord_fields]
        if not present_metrology:
            raise RuntimeError(
                "No metrology fields found in coords CSV. Expected at least one of: "
                + ", ".join(METROLOGY_COLS)
            )

        coord_map: dict[tuple[str, str, str], dict[str, str]] = {}
        for row in coords_reader:
            join_key = (
                _normalize_key(row.get("WAFER_KEY", "")),
                _normalize_key(row.get("INSPECTION_TIME", "")),
                _normalize_key(row.get("DEFECT_ID", "")),
            )
            coord_map[join_key] = {col: (row.get(col, "") or "").strip() for col in present_metrology}

    with images_csv.open("r", encoding="utf-8-sig", newline="") as f:
        img_reader = csv.DictReader(f)
        img_fields = img_reader.fieldnames or []
        for key in REQUIRED_JOIN_KEYS:
            if key not in img_fields:
                raise RuntimeError(f"Missing join key in images CSV: {key}")

        out_rows: list[dict[str, str]] = []
        unmatched = 0
        skipped_incomplete = 0
        for row in img_reader:
            join_key = (
                _normalize_key(row.get("WAFER_KEY", "")),
                _normalize_key(row.get("INSPECTION_TIME", "")),
                _normalize_key(row.get("DEFECT_ID", "")),
            )
            if not all(join_key):
                skipped_incomplete += 1
                continue
            metrology = coord_map.get(join_key)
            if not metrology:
                unmatched += 1
                continue

            image_name = _image_name_from_local_path(row.get("LOCAL_IMAGE_FILE", ""))
            if not image_name:
                continue

            out_row = {
                "image_name": image_name,
                "WAFER_KEY": join_key[0],
                "INSPECTION_TIME": join_key[1],
                "DEFECT_ID": join_key[2],
            }
            for col in present_metrology:
                out_row[col] = metrology.get(col, "")
            out_rows.append(out_row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out_fields = ["image_name", "WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"] + [
        c for c in METROLOGY_COLS if out_rows and c in out_rows[0]
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(out_rows)

    return len(out_rows), unmatched, skipped_incomplete


def main() -> int:
    parser = argparse.ArgumentParser(description="Build image-level defect metrology metadata")
    parser.add_argument(
        "--coords-csv",
        default=r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED.csv",
    )
    parser.add_argument(
        "--images-csv",
        default=r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv",
    )
    parser.add_argument(
        "--output-csv",
        default="config/defect_size_metadata.csv",
    )
    args = parser.parse_args()

    rows, unmatched, skipped_incomplete = build_metadata(
        coords_csv=Path(args.coords_csv),
        images_csv=Path(args.images_csv),
        output_csv=Path(args.output_csv),
    )
    print(f"rows_written={rows}")
    print(f"unmatched_image_rows={unmatched}")
    print(f"skipped_incomplete_image_rows={skipped_incomplete}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
