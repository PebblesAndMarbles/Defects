from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline_config import PIPELINE_PATHS


KNOWN_CASES = [
    ("AME401_PM1", "260609_1317"),
    ("AME401_PM1", "260611_0547"),
    ("AME403_PM2", "260610_1244"),
]


def main() -> None:
    manifest_path = Path(PIPELINE_PATHS.surf_image_manifest_csv)
    image_root = Path(PIPELINE_PATHS.surf_image_dir)

    out: dict[str, object] = {
        "manifest_path": str(manifest_path),
        "image_root": str(image_root),
        "manifest_exists": manifest_path.exists(),
        "image_root_exists": image_root.exists(),
    }

    if not manifest_path.exists():
        print(json.dumps(out, indent=2, default=str))
        return

    df = pd.read_csv(manifest_path, low_memory=False)
    out["manifest_rows"] = int(len(df))
    out["manifest_columns"] = list(df.columns)

    if {"WAFER_KEY", "DEFECT_ID", "IMAGE_ID", "INSPECTION_TIME"}.issubset(df.columns):
        work_cols = ["WAFER_KEY", "DEFECT_ID", "IMAGE_ID", "INSPECTION_TIME"]
        if "PRIMARY_EQUIP" in df.columns:
            work_cols.append("PRIMARY_EQUIP")
        work = df[work_cols].copy()
        for col in ("WAFER_KEY", "DEFECT_ID", "IMAGE_ID", "INSPECTION_TIME"):
            work[col] = work[col].astype(str)

        grouped = work.groupby(["WAFER_KEY", "DEFECT_ID", "IMAGE_ID"], dropna=False).agg(
            contexts=("INSPECTION_TIME", lambda series: len(set(series))),
            equips=("PRIMARY_EQUIP", lambda series: len(set(str(x) for x in series)))
            if "PRIMARY_EQUIP" in work.columns else ("INSPECTION_TIME", "size"),
        ).reset_index()

        cross = grouped[(grouped["contexts"] > 1) | (grouped["equips"] > 1)]
        out["legacy_key_cross_context_count"] = int(len(cross))
        out["legacy_key_cross_context_sample"] = cross.head(20).to_dict(orient="records")
    else:
        out["legacy_key_cross_context_count"] = None
        out["legacy_key_cross_context_sample"] = []

    known_case_results = []
    for chamber, token in KNOWN_CASES:
        subset = df.copy()
        if "LOCAL_IMAGE_FILE" in subset.columns:
            subset = subset[subset["LOCAL_IMAGE_FILE"].astype(str).str.contains(token, na=False)]
        if "PRIMARY_EQUIP" in subset.columns:
            subset = subset[subset["PRIMARY_EQUIP"].astype(str) == chamber]

        chamber_dir = image_root / chamber
        disk_case = [path for path in chamber_dir.glob(f"{token}_*") if path.is_file()] if chamber_dir.exists() else []
        manifest_ids = sorted(set(subset["IMAGE_ID"].dropna().astype(str))) if "IMAGE_ID" in subset.columns else []
        disk_ids = sorted(set(path.stem.split("_")[-1] for path in disk_case))

        known_case_results.append(
            {
                "chamber": chamber,
                "token": token,
                "manifest_rows": int(len(subset)),
                "manifest_image_ids": manifest_ids,
                "disk_files": int(len(disk_case)),
                "disk_image_ids": disk_ids,
            }
        )

    out["known_cases"] = known_case_results
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()