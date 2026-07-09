from __future__ import annotations

import json
import os
from pathlib import Path
import time

import pandas as pd

from pipeline_config import PIPELINE_PATHS


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif", ".webp"}
KNOWN_CASES = [
    ("AME401_PM1", "260609_1317"),
    ("AME401_PM1", "260611_0547"),
    ("AME403_PM2", "260610_1244"),
]
RESULT_PATH = Path(PIPELINE_PATHS.artifacts_dir) / "surf_scan_manifest_audit.json"


def _norm_path(value: object) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


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


def _load_manifest() -> pd.DataFrame:
    manifest_path = Path(PIPELINE_PATHS.surf_image_manifest_csv)
    if not manifest_path.exists():
        return pd.DataFrame()
    return pd.read_csv(manifest_path, low_memory=False)


def _list_disk_files() -> list[Path]:
    image_root = Path(PIPELINE_PATHS.surf_image_dir)
    if not image_root.exists():
        return []
    files: list[Path] = []
    seen = 0
    t0 = time.time()
    for path in image_root.rglob("*"):
        if not path.is_file():
            continue
        seen += 1
        if seen % 5000 == 0:
            elapsed = max(time.time() - t0, 1e-9)
            rate = seen / elapsed
            print(f"[audit] scanned_files={seen} kept_images={len(files)} rate={rate:.1f}/s", flush=True)
        if path.suffix.lower() in IMAGE_EXTS:
            files.append(path)
    return files


def main() -> None:
    manifest_path = Path(PIPELINE_PATHS.surf_image_manifest_csv)
    image_root = Path(PIPELINE_PATHS.surf_image_dir)
    df = _load_manifest()
    files = _list_disk_files()
    file_set = {_norm_path(path) for path in files}

    out: dict[str, object] = {
        "manifest_path": str(manifest_path),
        "image_root": str(image_root),
        "manifest_exists": manifest_path.exists(),
        "image_root_exists": image_root.exists(),
        "manifest_rows": int(len(df)),
        "disk_files": int(len(files)),
        "manifest_columns": list(df.columns),
    }

    if "LOCAL_IMAGE_FILE" in df.columns:
        local_paths = [
            str(path).strip()
            for path in df["LOCAL_IMAGE_FILE"].dropna().astype(str)
            if str(path).strip()
        ]
    else:
        local_paths = []

    manifest_path_set = {_norm_path(path) for path in local_paths}
    out["manifest_nonnull_paths"] = len(local_paths)

    if "LOCAL_IMAGE_FILE" in df.columns:
        missing_rows = df[df["LOCAL_IMAGE_FILE"].notna()].copy()
        missing_rows["__norm"] = missing_rows["LOCAL_IMAGE_FILE"].astype(str).map(_norm_path)
        missing_rows = missing_rows[~missing_rows["__norm"].isin(file_set)]
    else:
        missing_rows = pd.DataFrame()

    out["missing_manifest_paths"] = int(len(missing_rows))
    out["missing_manifest_path_examples"] = (
        missing_rows["LOCAL_IMAGE_FILE"].astype(str).head(5).tolist()
        if "LOCAL_IMAGE_FILE" in missing_rows.columns else []
    )

    orphan_files = sorted(file_set - manifest_path_set)
    out["orphan_files"] = len(orphan_files)
    out["orphan_file_examples"] = orphan_files[:5]

    chamber_mismatch_examples: list[dict[str, str]] = []
    chamber_mismatches = 0
    if "LOCAL_IMAGE_FILE" in df.columns:
        for _, row in df[df["LOCAL_IMAGE_FILE"].notna()].iterrows():
            local_path = str(row["LOCAL_IMAGE_FILE"]).strip()
            if not local_path:
                continue
            actual = Path(local_path).parent.name
            expected = _chamber_for_row(row)
            if actual != expected:
                chamber_mismatches += 1
                if len(chamber_mismatch_examples) < 5:
                    chamber_mismatch_examples.append({
                        "expected": expected,
                        "actual": actual,
                        "path": local_path,
                    })
    out["chamber_mismatches"] = chamber_mismatches
    out["chamber_mismatch_examples"] = chamber_mismatch_examples

    duplicate_key_summary: dict[str, object] = {}
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
        duplicate_key_summary = {
            "cross_context_keys": int(len(cross)),
            "sample": cross.head(10).to_dict(orient="records"),
        }
    out["duplicate_key_summary"] = duplicate_key_summary

    known_cases: list[dict[str, object]] = []
    for chamber, token in KNOWN_CASES:
        subset = df.copy()
        if "LOCAL_IMAGE_FILE" in subset.columns:
            subset = subset[subset["LOCAL_IMAGE_FILE"].astype(str).str.contains(token, na=False)]
        if "PRIMARY_EQUIP" in subset.columns:
            subset = subset[subset["PRIMARY_EQUIP"].astype(str).eq(chamber)]

        disk_case = [
            path for path in files
            if path.parent.name == chamber and path.name.startswith(token + "_")
        ]
        manifest_ids = sorted(set(subset["IMAGE_ID"].dropna().astype(str))) if "IMAGE_ID" in subset.columns else []
        disk_ids = sorted(set(path.stem.split("_")[-1] for path in disk_case))
        known_cases.append({
            "chamber": chamber,
            "token": token,
            "manifest_rows": int(len(subset)),
            "manifest_image_ids": manifest_ids[:20],
            "disk_files": len(disk_case),
            "disk_image_ids": disk_ids[:20],
        })
    out["known_cases"] = known_cases

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, indent=2, default=str))
    print(f"[audit] wrote {RESULT_PATH}", flush=True)


if __name__ == "__main__":
    main()