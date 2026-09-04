"""Build a candidate manifest for re-downloading burn-in-free raw defect images."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


JOIN_KEYS = ("WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID", "IMAGE_ID")
RAW_PATH_COLUMNS = (
    "YAS_FILE_PATH",
    "RAW_IMAGE_FILE",
    "IMAGE_PATH",
    "FILE_PATH",
    "SOURCE_FILE",
)


def _normalize_key(value: str) -> str:
    text = (value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _first_non_empty(row: dict[str, str], columns: tuple[str, ...]) -> tuple[str, str]:
    for col in columns:
        val = (row.get(col, "") or "").strip()
        if val:
            return col, val
    return "", ""


def build_manifest(images_csv: Path, output_csv: Path) -> dict[str, int]:
    with images_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []

        for key in JOIN_KEYS:
            if key not in fields:
                raise RuntimeError(f"Missing required key column: {key}")

        rows_out: list[dict[str, str]] = []
        total = 0
        with_raw_path = 0
        missing_raw_path = 0

        for row in reader:
            total += 1
            key_data = {k: _normalize_key(row.get(k, "")) for k in JOIN_KEYS}
            local_image = (row.get("LOCAL_IMAGE_FILE", "") or "").strip()
            inventory_only = (row.get("INVENTORY_ONLY", "") or "").strip()
            source_col, source_path = _first_non_empty(row, RAW_PATH_COLUMNS)
            if source_path:
                with_raw_path += 1
            else:
                missing_raw_path += 1

            rows_out.append(
                {
                    **key_data,
                    "LOCAL_IMAGE_FILE": local_image,
                    "INVENTORY_ONLY": inventory_only,
                    "RAW_SOURCE_COLUMN": source_col,
                    "RAW_SOURCE_PATH": source_path,
                    "RAW_SOURCE_AVAILABLE": "1" if source_path else "0",
                    "RETRIEVAL_STATUS": "ready" if source_path else "needs_source_path",
                    "RETRIEVAL_NOTE": "" if source_path else "No YAS/raw source path populated in manifest row",
                }
            )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out_fields = [
        *JOIN_KEYS,
        "LOCAL_IMAGE_FILE",
        "INVENTORY_ONLY",
        "RAW_SOURCE_COLUMN",
        "RAW_SOURCE_PATH",
        "RAW_SOURCE_AVAILABLE",
        "RETRIEVAL_STATUS",
        "RETRIEVAL_NOTE",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(rows_out)

    return {
        "rows_total": total,
        "rows_with_raw_source_path": with_raw_path,
        "rows_missing_raw_source_path": missing_raw_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build raw-image redownload candidate manifest")
    parser.add_argument(
        "--images-csv",
        default=r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv",
    )
    parser.add_argument(
        "--output-csv",
        default="outputs/raw_image_redownload_manifest.csv",
    )
    args = parser.parse_args()

    summary = build_manifest(Path(args.images_csv), Path(args.output_csv))
    for k, v in summary.items():
        print(f"{k}={v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
