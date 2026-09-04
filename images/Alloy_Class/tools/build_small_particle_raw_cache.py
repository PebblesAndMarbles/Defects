"""Build a local raw-image cache for SMALL_PARTICLE BF/DF pairs.

This tool stages raw image files from the image manifest into a local cache,
writes a local manifest CSV with join keys and provenance, and supports a
small pilot slice plus chunked expansion to the full available SMALL_PARTICLE
set.

Default behavior:
- Select the most recent 30 SMALL_PARTICLE defect groups for a pilot.
- Download only IMAGE_ID 2 and 3.
- Store raw files under C:\RAW_IMAGES\images by default.
- Write a manifest CSV to C:\RAW_IMAGES\manifest.csv by default.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

_ALLOY_CLASS_DIR = Path(__file__).resolve().parents[1]
for _subdir in ("reporting", "pipelines"):
    _path = _ALLOY_CLASS_DIR / _subdir
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

BE_QUERY_FILES_DIR = _ALLOY_CLASS_DIR.parent.parent / "BE_QUERY_FILES"
if str(BE_QUERY_FILES_DIR) not in sys.path:
    sys.path.insert(0, str(BE_QUERY_FILES_DIR))

from classify_phase1_batch import (  # type: ignore  # noqa: E402
    DEFAULT_GAJT_DLL_SEARCH_PATHS,
    RawImageConfig,
    _download_raw_image_to_temp,
)


DEFAULT_SOURCE_MANIFEST = (
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson"
    r"\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED.csv"
)
DEFAULT_CACHE_ROOT = r"C:\RAW_IMAGES"
DEFAULT_IMAGE_DIR = r"C:\RAW_IMAGES\images"
DEFAULT_MANIFEST_CSV = r"C:\RAW_IMAGES\manifest.csv"
DEFAULT_MODEL_TECHNOLOGY = "1278"
DEFAULT_APP_NAME = "GAJT_INLINE_24601"
DEFAULT_CHUNK_SIZE = 50
DEFAULT_PILOT_SIZE = 30
DEFAULT_OFFSET_GROUPS = 0

JOIN_COLUMNS = ["wafer_key", "inspection_time", "defect_id", "image_id"]
GROUP_COLUMNS = ["wafer_key", "inspection_time", "defect_id"]
MANIFEST_COLUMNS = [
    "case_id",
    "wafer_key",
    "inspection_time",
    "defect_id",
    "image_id",
    "class",
    "subentity",
    "lot",
    "lot7",
    "layer",
    "image_count",
    "query_site",
    "source_filespec",
    "local_path",
    "download_status",
    "raw_download_status",
    "raw_datasource",
    "raw_image_spec",
    "downloaded_utc",
]


@dataclass(frozen=True)
class CacheConfig:
    source_manifest: Path
    cache_root: Path
    image_dir: Path
    manifest_csv: Path
    temp_dir: Path
    app_name: str
    technology: str
    gajt_dll_search_paths: list[str]
    keep_temp: bool
    chunk_size: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _load_source_manifest(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False, dtype=str)
    required = {"CLASS", "WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"}
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise RuntimeError(f"Source manifest missing required columns: {', '.join(missing)}")
    return df


def _load_image_manifest(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False, dtype=str)
    required = {"wafer_key", "inspection_time", "defect_id", "image_id", "local_path"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Raw image manifest missing required columns: {', '.join(sorted(missing))}")
    return df


def _load_image_manifest_index(path: Path) -> dict[tuple[str, str, str, int], str]:
    manifest = _load_image_manifest(path)
    if manifest.empty:
        return {}

    index: dict[tuple[str, str, str, int], str] = {}
    work = manifest.copy()
    work["wafer_key"] = work["wafer_key"].map(_normalize_text)
    work["inspection_time"] = pd.to_datetime(work["inspection_time"], errors="coerce")
    work["inspection_time_norm"] = work["inspection_time"].dt.strftime("%Y%m%d_%H%M%S")
    work["defect_id"] = work["defect_id"].map(_normalize_text)
    work["image_id"] = pd.to_numeric(work["image_id"], errors="coerce").astype("Int64")
    work = work[work["local_path"].fillna("").astype(str).str.strip().ne("")].copy()

    for _, row in work.iterrows():
        image_id = row["image_id"]
        if pd.isna(image_id):
            continue
        key = (
            str(row["wafer_key"]),
            str(row["inspection_time_norm"]),
            str(row["defect_id"]),
            int(image_id),
        )
        index[key] = str(row["local_path"])
    return index


def _load_existing_manifest(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=MANIFEST_COLUMNS)
    return pd.read_csv(path, low_memory=False, dtype=str)


def _group_key_frame(df: pd.DataFrame) -> pd.DataFrame:
    column_map = {
        "wafer_key": "wafer_key" if "wafer_key" in df.columns else "WAFER_KEY",
        "inspection_time": "inspection_time" if "inspection_time" in df.columns else "INSPECTION_TIME",
        "defect_id": "defect_id" if "defect_id" in df.columns else "DEFECT_ID",
    }
    work = df[[column_map["wafer_key"], column_map["inspection_time"], column_map["defect_id"]]].copy()
    work.columns = GROUP_COLUMNS
    return work.drop_duplicates().copy()


def _select_rows(df: pd.DataFrame, pilot_size: int, offset_groups: int = 0) -> pd.DataFrame:
    work = df.copy()
    work = work[work["CLASS"] == "SMALL_PARTICLE"].copy()
    selected = work.drop_duplicates(subset=["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"]).copy()
    if selected.empty:
        return selected

    selected["inspection_time_dt"] = pd.to_datetime(selected["INSPECTION_TIME"], errors="coerce")
    selected = selected.sort_values(["inspection_time_dt", "WAFER_KEY", "DEFECT_ID"], ascending=[False, False, False])
    if offset_groups > 0:
        selected = selected.iloc[offset_groups:]
    if pilot_size > 0:
        selected = selected.head(pilot_size)
    selected = selected.drop(columns=["inspection_time_dt"])
    selected = selected.reset_index(drop=True)
    return selected


def _stage_flat_raw_images(candidates: pd.DataFrame, config: CacheConfig) -> pd.DataFrame:
    try:
        module_path = BE_QUERY_FILES_DIR / "DEFECT_COORDINATES_QUERY.py"
        spec = importlib.util.spec_from_file_location("DEFECT_COORDINATES_QUERY", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load helper module from {module_path}")
        dcq = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dcq)
    except Exception as exc:
        raise RuntimeError(f"Unable to load inline image helpers: {exc}") from exc

    defects = candidates.copy()
    manifest_for_inline = config.manifest_csv
    if config.manifest_csv.exists():
        manifest_df = pd.read_csv(config.manifest_csv, low_memory=False, dtype=str)
        manifest_df.columns = [str(col).upper() for col in manifest_df.columns]
        config.temp_dir.mkdir(parents=True, exist_ok=True)
        manifest_for_inline = config.temp_dir / "manifest_inline_upper.csv"
        manifest_df.to_csv(manifest_for_inline, index=False)

    defects = dcq._filter_defects_needing_images(defects, str(manifest_for_inline), [2, 3])
    if defects.empty:
        return pd.DataFrame()

    conn = dcq._connect(dcq.DATABASE)
    try:
        image_df = dcq._fetch_image_metadata(conn, defects, image_id_filter=[2, 3])
    finally:
        conn.close()

    if image_df.empty:
        return image_df

    image_df = dcq._enrich_image_rows_with_defect_context(image_df, defects)

    raw_cfg = RawImageConfig(
        enabled=True,
        manifest_csv=config.manifest_csv,
        temp_dir=config.temp_dir,
        app_name=config.app_name,
        technology=config.technology,
        gajt_dll_search_paths=config.gajt_dll_search_paths,
        strict=False,
        keep_temp=config.keep_temp,
    )

    output_rows: list[dict[str, str]] = []
    for _, row in image_df.iterrows():
        image_id = _to_int(row.get("IMAGE_ID"))
        if image_id not in {2, 3}:
            continue

        manifest_row = {
            "IMAGE_FILESPEC": str(row.get("IMAGE_FILESPEC", "")),
            "QUERY_SITE": str(row.get("QUERY_SITE", row.get("SITE", ""))),
        }
        local_name = _build_local_name(row, image_id)
        temp_file, info = _download_raw_image_to_temp(manifest_row, raw_cfg)
        if temp_file is not None:
            output_path = config.image_dir / local_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temp_file), str(output_path))
            local_path = output_path
        else:
            local_path = None

        output_rows.append(
            {
                "case_id": f"{_normalize_text(row.get('WAFER_KEY', ''))}|{_normalize_text(row.get('INSPECTION_TIME', ''))}|{_normalize_text(row.get('DEFECT_ID', ''))}",
                "wafer_key": str(row.get("WAFER_KEY", "")),
                "inspection_time": str(row.get("INSPECTION_TIME", "")),
                "defect_id": str(row.get("DEFECT_ID", "")),
                "image_id": str(image_id),
                "class": str(row.get("CLASS", "")),
                "subentity": str(row.get("SUBENTITY", "")),
                "lot": str(row.get("LOT", "")),
                "lot7": str(row.get("LOT7", "")),
                "layer": str(row.get("LAYER", "")),
                "image_count": str(row.get("IMAGE_COUNT", "")),
                "query_site": str(row.get("QUERY_SITE", row.get("SITE", ""))),
                "source_filespec": str(row.get("IMAGE_FILESPEC", "")),
                "local_path": str(local_path or ""),
                "download_status": "ok" if local_path else "failed",
                "raw_download_status": str(info.get("raw_download_status", "failed")),
                "raw_datasource": str(info.get("raw_datasource", row.get("QUERY_SITE", row.get("SITE", "")))),
                "raw_image_spec": str(info.get("raw_image_spec", row.get("IMAGE_FILESPEC", ""))),
                "downloaded_utc": _utc_now(),
            }
        )

    return pd.DataFrame(output_rows)


def _safe_row_value(row: pd.Series, *keys: str, default: str = "") -> str:
    for key in keys:
        if key in row and pd.notna(row[key]):
            text = str(row[key]).strip()
            if text:
                return text
    return default


def _safe_token(value: object) -> str:
    text = _normalize_text(value)
    return text.replace(" ", "_").replace(":", "").replace("/", "-").replace("\\", "-")


def _build_local_name(row: pd.Series, image_id: int) -> str:
    date_token = _safe_token(str(_safe_row_value(row, "inspection_time", "INSPECTION_TIME"))[:10])
    lot_token = _safe_token(_safe_row_value(row, "lot", "LOT"))
    wafer_token = _safe_token(_safe_row_value(row, "wafer_key", "WAFER_KEY"))
    defect_token = _safe_token(_safe_row_value(row, "defect_id", "DEFECT_ID"))
    return f"{date_token}_{lot_token}_{wafer_token}_{defect_token}_{image_id}.jpg"


def _finalize_download(
    temp_file: Path | None,
    info: dict[str, str],
    output_path: Path,
    manifest_row: dict[str, str],
) -> dict[str, str]:
    if temp_file is None:
        return {
            "download_status": "failed",
            "raw_download_status": info.get("raw_download_status", "failed"),
            "raw_datasource": info.get("raw_datasource", ""),
            "raw_image_spec": info.get("raw_image_spec", manifest_row.get("IMAGE_FILESPEC", "")),
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(temp_file), str(output_path))

    return {
        "download_status": "ok",
        "raw_download_status": info.get("raw_download_status", "ok"),
        "raw_datasource": info.get("raw_datasource", ""),
        "raw_image_spec": info.get("raw_image_spec", manifest_row.get("IMAGE_FILESPEC", "")),
    }


def _row_to_manifest_records(row: pd.Series, local_bright: Path, local_dark: Path, bright_info: dict[str, str], dark_info: dict[str, str]) -> list[dict[str, str]]:
    base = {
        "case_id": str(row["case_id"]),
        "wafer_key": str(row["wafer_key"]),
        "inspection_time": str(row["inspection_time"]),
        "defect_id": str(row["defect_id"]),
        "class": str(row["class"]),
        "subentity": str(row["subentity"]),
        "lot": str(row["lot"]),
        "lot7": str(row["lot7"]),
        "layer": str(row["layer"]),
        "image_count": str(row["image_count"]),
        "query_site": str(row["query_site"]),
        "downloaded_utc": _utc_now(),
    }
    bright = {
        **base,
        "image_id": "2",
        "source_filespec": str(row["bright_image_filespec"]),
        "local_path": str(local_bright),
        **bright_info,
    }
    dark = {
        **base,
        "image_id": "3",
        "source_filespec": str(row["dark_image_filespec"]),
        "local_path": str(local_dark),
        **dark_info,
    }
    return [bright, dark]


def _write_manifest(path: Path, records: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow({col: record.get(col, "") for col in MANIFEST_COLUMNS})


def _append_manifest(path: Path, records: list[dict[str, str]]) -> None:
    existing = _load_existing_manifest(path)
    combined = pd.concat([existing, pd.DataFrame(records)], ignore_index=True)
    combined = combined.drop_duplicates(subset=JOIN_COLUMNS, keep="last")
    _write_manifest(path, combined.fillna("").astype(str).to_dict(orient="records"))


def _filter_existing_groups(selected: pd.DataFrame, existing_manifest: pd.DataFrame) -> pd.DataFrame:
    if selected.empty or existing_manifest.empty:
        return selected

    existing_keys = _group_key_frame(existing_manifest)
    work = selected.copy()
    work.columns = [str(col).lower() for col in work.columns]
    merged = work.merge(existing_keys, on=GROUP_COLUMNS, how="left", indicator=True)
    return merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])


def build_cache(config: CacheConfig, pilot_size: int, offset_groups: int = 0) -> dict[str, int]:
    source_df = _load_source_manifest(config.source_manifest)
    selected = _select_rows(source_df, pilot_size=0, offset_groups=offset_groups)
    if selected.empty:
        return {"selected_groups": 0, "downloaded_images": 0, "failed_images": 0, "manifest_rows": 0}

    existing_manifest = _load_existing_manifest(config.manifest_csv)
    if not existing_manifest.empty:
        selected = _filter_existing_groups(selected, existing_manifest)
        if selected.empty:
            return {"selected_groups": 0, "downloaded_images": 0, "failed_images": 0, "manifest_rows": 0}

    selected.columns = [str(col).lower() for col in selected.columns]
    if pilot_size > 0:
        selected = selected.head(pilot_size)

    staged = _stage_flat_raw_images(selected.rename(columns={c: c.upper() for c in selected.columns}), config)
    if staged.empty:
        return {"selected_groups": len(selected), "downloaded_images": 0, "failed_images": 0, "manifest_rows": 0}

    manifest_records = []
    for _, row in staged.iterrows():
        manifest_records.append(
            {
                "case_id": str(row.get("case_id", "")),
                "wafer_key": str(row.get("wafer_key", "")),
                "inspection_time": str(row.get("inspection_time", "")),
                "defect_id": str(row.get("defect_id", "")),
                "image_id": str(row.get("image_id", "")),
                "class": str(row.get("class", "")),
                "subentity": str(row.get("subentity", "")),
                "lot": str(row.get("lot", "")),
                "lot7": str(row.get("lot7", "")),
                "layer": str(row.get("layer", "")),
                "image_count": str(row.get("image_count", "")),
                "query_site": str(row.get("query_site", "")),
                "source_filespec": str(row.get("source_filespec", "")),
                "local_path": str(row.get("local_path", "")),
                "download_status": str(row.get("download_status", "failed")),
                "raw_download_status": str(row.get("raw_download_status", "failed")),
                "raw_datasource": str(row.get("raw_datasource", "")),
                "raw_image_spec": str(row.get("raw_image_spec", "")),
                "downloaded_utc": str(row.get("downloaded_utc", _utc_now())),
            }
        )

    downloaded = sum(1 for rec in manifest_records if rec["download_status"] == "ok")
    failed = len(manifest_records) - downloaded
    _append_manifest(config.manifest_csv, manifest_records)
    return {
        "selected_groups": len(selected),
        "downloaded_images": downloaded,
        "failed_images": failed,
        "manifest_rows": len(manifest_records),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local raw cache for SMALL_PARTICLE BF/DF images")
    parser.add_argument("--source-manifest-csv", default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--cache-root", default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--image-dir", default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--temp-dir", default=str(Path(DEFAULT_CACHE_ROOT) / "_temp"))
    parser.add_argument("--pilot-size", type=int, default=DEFAULT_PILOT_SIZE)
    parser.add_argument("--offset-groups", type=int, default=DEFAULT_OFFSET_GROUPS, help="Skip this many newest defect groups before selecting the pilot-size window")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--app-name", default=DEFAULT_APP_NAME)
    parser.add_argument("--technology", default=DEFAULT_MODEL_TECHNOLOGY)
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--rebuild", action="store_true", help="Overwrite manifest instead of appending")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = CacheConfig(
        source_manifest=Path(args.source_manifest_csv),
        cache_root=Path(args.cache_root),
        image_dir=Path(args.image_dir),
        manifest_csv=Path(args.manifest_csv),
        temp_dir=Path(args.temp_dir),
        app_name=args.app_name,
        technology=args.technology,
        gajt_dll_search_paths=DEFAULT_GAJT_DLL_SEARCH_PATHS,
        keep_temp=args.keep_temp,
        chunk_size=args.chunk_size,
    )

    if args.rebuild and config.manifest_csv.exists():
        config.manifest_csv.unlink()

    summary = build_cache(config, pilot_size=args.pilot_size, offset_groups=args.offset_groups)
    print(json.dumps(summary, indent=2))
    print(f"manifest_csv={config.manifest_csv}")
    print(f"image_dir={config.image_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())