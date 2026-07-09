from __future__ import annotations

import json
from pathlib import Path
import time

import pandas as pd

from pipeline_config import PIPELINE_PATHS


KNOWN_CASES = [
    ("AME401_PM1", "260609_1317"),
    ("AME401_PM1", "260611_0547"),
    ("AME403_PM2", "260610_1244"),
]


def _chamber_for_row(row: pd.Series) -> str:
    for key in ("SUBENTITY", "subentity", "PRIMARY_EQUIP"):
        if key not in row.index:
            continue
        value = row.get(key)
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return "UNKNOWN"


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

    # 1) Missing manifest paths (path exists check only; no full disk walk)
    missing = pd.DataFrame()
    if "LOCAL_IMAGE_FILE" in df.columns:
        nonnull = df[df["LOCAL_IMAGE_FILE"].notna()].copy()
        t0 = time.time()
        exists_flags = []
        total = len(nonnull)
        for idx, path in enumerate(nonnull["LOCAL_IMAGE_FILE"].astype(str), start=1):
            exists_flags.append(Path(path).exists())
            if idx % 5000 == 0:
                elapsed = max(time.time() - t0, 1e-9)
                rate = idx / elapsed
                print(f"[targeted-audit] exists_checked={idx}/{total} rate={rate:.1f}/s", flush=True)
        nonnull["__exists"] = exists_flags
        missing = nonnull[~nonnull["__exists"]].copy()
        out["manifest_nonnull_paths"] = int(len(nonnull))
    else:
        out["manifest_nonnull_paths"] = 0
    out["missing_manifest_paths"] = int(len(missing))
    out["missing_manifest_path_examples"] = (
        missing["LOCAL_IMAGE_FILE"].astype(str).head(10).tolist()
        if "LOCAL_IMAGE_FILE" in missing.columns else []
    )

    # 2) Chamber mismatch (manifest expected chamber vs local file parent)
    chamber_mismatches = 0
    chamber_examples: list[dict[str, str]] = []
    if "LOCAL_IMAGE_FILE" in df.columns:
        for _, row in df[df["LOCAL_IMAGE_FILE"].notna()].iterrows():
            local_path = str(row["LOCAL_IMAGE_FILE"]).strip()
            if not local_path:
                continue
            actual_chamber = Path(local_path).parent.name
            expected_chamber = _chamber_for_row(row)
            if actual_chamber != expected_chamber:
                chamber_mismatches += 1
                if len(chamber_examples) < 10:
                    chamber_examples.append(
                        {
                            "expected": expected_chamber,
                            "actual": actual_chamber,
                            "path": local_path,
                        }
                    )
    out["chamber_mismatches"] = chamber_mismatches
    out["chamber_mismatch_examples"] = chamber_examples

    # 3) Cross-context collision risk check on legacy key shape
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

    # 4) Known-case event/chamber validation (targeted disk scan only)
    known_case_results: list[dict[str, object]] = []
    for chamber, token in KNOWN_CASES:
        subset = df.copy()
        if "LOCAL_IMAGE_FILE" in subset.columns:
            subset = subset[subset["LOCAL_IMAGE_FILE"].astype(str).str.contains(token, na=False)]
        if "PRIMARY_EQUIP" in subset.columns:
            subset = subset[subset["PRIMARY_EQUIP"].astype(str) == chamber]

        chamber_dir = image_root / chamber
        if chamber_dir.exists():
            disk_case = [p for p in chamber_dir.glob(f"{token}_*") if p.is_file()]
        else:
            disk_case = []

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