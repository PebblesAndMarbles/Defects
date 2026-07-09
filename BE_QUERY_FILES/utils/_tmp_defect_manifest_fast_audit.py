from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline_config import PIPELINE_PATHS


def main() -> None:
    manifest_path = Path(PIPELINE_PATHS.defect_images_manifest_csv)
    image_root = Path(PIPELINE_PATHS.image_dir)

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

    if "LOCAL_IMAGE_FILE" in df.columns:
        out["manifest_nonnull_paths"] = int(df["LOCAL_IMAGE_FILE"].notna().sum())
    else:
        out["manifest_nonnull_paths"] = 0

    if {"WAFER_KEY", "DEFECT_ID", "IMAGE_ID"}.issubset(df.columns):
        work_cols = ["WAFER_KEY", "DEFECT_ID", "IMAGE_ID"]
        time_col = "INSPECTION_TIME" if "INSPECTION_TIME" in df.columns else ("SUBENTITY_END_TIME" if "SUBENTITY_END_TIME" in df.columns else None)
        equip_col = "SUBENTITY" if "SUBENTITY" in df.columns else ("subentity" if "subentity" in df.columns else None)
        if time_col:
            work_cols.append(time_col)
        if equip_col:
            work_cols.append(equip_col)

        work = df[work_cols].copy()
        for col in ("WAFER_KEY", "DEFECT_ID", "IMAGE_ID"):
            work[col] = work[col].astype(str)
        if time_col:
            work[time_col] = work[time_col].astype(str)
        if equip_col:
            work[equip_col] = work[equip_col].astype(str)

        agg = {}
        if time_col:
            agg["contexts"] = (time_col, lambda series: len(set(series)))
        if equip_col:
            agg["equips"] = (equip_col, lambda series: len(set(series)))

        grouped = work.groupby(["WAFER_KEY", "DEFECT_ID", "IMAGE_ID"], dropna=False).agg(**agg).reset_index() if agg else pd.DataFrame()

        if not grouped.empty:
            if "contexts" in grouped.columns and "equips" in grouped.columns:
                cross = grouped[(grouped["contexts"] > 1) | (grouped["equips"] > 1)]
            elif "contexts" in grouped.columns:
                cross = grouped[grouped["contexts"] > 1]
            elif "equips" in grouped.columns:
                cross = grouped[grouped["equips"] > 1]
            else:
                cross = grouped.iloc[0:0]
            out["legacy_key_cross_context_count"] = int(len(cross))
            out["legacy_key_cross_context_sample"] = cross.head(20).to_dict(orient="records")
        else:
            out["legacy_key_cross_context_count"] = 0
            out["legacy_key_cross_context_sample"] = []
    else:
        out["legacy_key_cross_context_count"] = None
        out["legacy_key_cross_context_sample"] = []

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
