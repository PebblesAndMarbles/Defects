"""
One-time utility to reconcile image manifest paths and prune image files.

What it does:
1. Backfills LOCAL_IMAGE_FILE for manifest rows by computing expected organized
   destinations and checking if files exist.
2. Optionally renames/moves found files into expected organized destinations.
3. Prunes image files older than retention window, including unreferenced files.

Defaults to dry-run. Use --apply to write changes/deletions.
"""

from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from pipeline_config import PIPELINE_PATHS

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
CLASS_ABBREV = {"SMALL_PARTICLE": "SMP"}
AMBIGUOUS_CLASSES = {"OTHER_UNKNOWN", "UNCLASSIFIED", "NVD_FALSE"}
AMBIGUOUS_IMAGE_FOLDER = "AMBIGUOUS_REVIEW"


@dataclass
class Stats:
    backfilled: int = 0
    renamed: int = 0
    prune_deleted: int = 0
    prune_candidates: int = 0
    unreferenced_files: int = 0
    inventory_appended: int = 0


def _sanitize_path_token(value: object) -> str:
    token = str(value or "UNKNOWN").strip()
    for ch in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
        token = token.replace(ch, "_")
    return token or "UNKNOWN"


def _build_expected_path(row: pd.Series, image_root: str) -> str:
    end_ts = pd.to_datetime(row.get("SUBENTITY_END_TIME"), errors="coerce")
    ts = end_ts.strftime("%y%m%d_%H%M") if not pd.isna(end_ts) else "000000_0000"

    lot7 = _sanitize_path_token(row.get("LOT7", "UNK"))
    waf_raw = str(row.get("WAFER_ID", "")).strip()
    short_w = _sanitize_path_token(waf_raw[5:8] if len(waf_raw) >= 8 else waf_raw)

    cls_raw = _sanitize_path_token(row.get("CLASS", "UNK"))
    cls = _sanitize_path_token(CLASS_ABBREV.get(cls_raw, cls_raw))
    layer = _sanitize_path_token(row.get("LAYER", ""))

    defid = str(int(float(row.get("DEFECT_ID")))) if pd.notna(row.get("DEFECT_ID")) else "0"
    picid = str(int(float(row.get("IMAGE_ID")))) if pd.notna(row.get("IMAGE_ID")) else "0"

    spec = str(row.get("IMAGE_FILESPEC", ""))
    ext = os.path.splitext(spec)[1].lower() if spec else ".jpg"

    subentity = _sanitize_path_token(row.get("SUBENTITY", "UNKNOWN"))
    if cls_raw in AMBIGUOUS_CLASSES:
        dest_dir = os.path.join(image_root, AMBIGUOUS_IMAGE_FOLDER, cls_raw, subentity)
    else:
        dest_dir = os.path.join(image_root, subentity)

    fname = f"{ts}_{lot7}_{short_w}_{cls}_{layer}_{defid}_{picid}{ext}"
    return os.path.join(dest_dir, fname)


def _parse_ts_from_filename(path: str) -> Optional[datetime]:
    name = os.path.basename(path)
    m = re.match(r"^(\d{6})_(\d{4})_", name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%y%m%d%H%M")
    except ValueError:
        return None


def _normalize_manifest_schema(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    time_col = None
    for candidate in ("INSPECTION_TIME", "SUBENTITY_END_TIME", "INSPECT_TIME"):
        if candidate in normalized.columns:
            time_col = candidate
            break

    if time_col is not None:
        normalized["YYMM"] = pd.to_datetime(normalized[time_col], errors="coerce").dt.strftime("%y%m")

    if "YYMM" in normalized.columns:
        ordered = ["YYMM"] + [col for col in normalized.columns if col != "YYMM"]
        normalized = normalized[ordered]

    return normalized


def _list_image_files(image_root: str) -> List[str]:
    out: List[str] = []
    for root, _, files in os.walk(image_root):
        for name in files:
            if Path(name).suffix.lower() in IMAGE_EXTS:
                out.append(os.path.normpath(os.path.join(root, name)))
    return out


def _append_missing_inventory_rows(
    manifest: pd.DataFrame,
    image_root: str,
    apply: bool,
    manifest_path: str,
) -> Tuple[pd.DataFrame, int]:
    """
    Ensure every image file currently on disk has a corresponding manifest row.

    For files not already referenced in LOCAL_IMAGE_FILE, append inventory rows
    using the existing manifest schema and populate the fields that can be
    derived from organized filenames.
    """
    if "LOCAL_IMAGE_FILE" not in manifest.columns:
        raise ValueError("Manifest missing required LOCAL_IMAGE_FILE column")

    all_files = [os.path.normpath(p) for p in _list_image_files(image_root)]
    existing_paths = set(
        os.path.normpath(str(p))
        for p in manifest["LOCAL_IMAGE_FILE"].dropna().astype(str)
        if str(p).strip()
    )
    missing_paths = [p for p in all_files if p not in existing_paths]

    if not missing_paths:
        return manifest, 0

    cols = manifest.columns.tolist()
    rows: List[Dict[str, object]] = []

    # Organized image filenames follow:
    # yymmdd_hhmm_lot7_waf_class_layer_defectid_imageid.ext
    name_re = re.compile(
        r"^(?P<ts>\d{6}_\d{4})_[^_]+_[^_]+_[^_]+_[^_]+_(?P<did>\d+)_(?P<iid>\d+)(?:\.[^.]+)?$"
    )

    for path in missing_paths:
        row = {c: pd.NA for c in cols}
        row["LOCAL_IMAGE_FILE"] = path

        base = os.path.basename(path)
        m = name_re.match(base)
        if m:
            if "DEFECT_ID" in cols:
                row["DEFECT_ID"] = m.group("did")
            if "IMAGE_ID" in cols:
                row["IMAGE_ID"] = m.group("iid")
            if "INSPECTION_TIME" in cols:
                try:
                    dt = datetime.strptime(m.group("ts"), "%y%m%d_%H%M")
                    row["INSPECTION_TIME"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

        rows.append(row)

    appended_df = pd.DataFrame(rows, columns=cols)
    out = pd.concat([manifest, appended_df], ignore_index=True)

    key_cols = [c for c in ["WAFER_KEY", "DEFECT_ID", "IMAGE_ID", "LOCAL_IMAGE_FILE"] if c in out.columns]
    if key_cols:
        out = out.drop_duplicates(subset=key_cols, keep="last")

    out = _normalize_manifest_schema(out)

    if apply:
        out.to_csv(manifest_path, index=False)

    return out, len(rows)


def _build_coords_lookup(coords_df: pd.DataFrame) -> pd.DataFrame:
    work = coords_df.copy()
    work["_WK"] = pd.to_numeric(work["WAFER_KEY"], errors="coerce").astype("Int64")
    work["_DID"] = pd.to_numeric(work["DEFECT_ID"], errors="coerce").astype("Int64")
    if "SUBENTITY_END_TIME" in work.columns:
        work["SUBENTITY_END_TIME"] = pd.to_datetime(work["SUBENTITY_END_TIME"], errors="coerce")
        work = work.sort_values("SUBENTITY_END_TIME").drop_duplicates(["_WK", "_DID"], keep="last")
    else:
        work = work.drop_duplicates(["_WK", "_DID"], keep="last")
    return work


def _reconcile_manifest(
    manifest_path: str,
    coords_path: str,
    image_root: str,
    apply: bool,
    rename_missing: bool,
) -> Tuple[pd.DataFrame, Stats]:
    stats = Stats()

    manifest = pd.read_csv(manifest_path, low_memory=False)
    coords = pd.read_csv(coords_path, low_memory=False)
    coords_lookup = _build_coords_lookup(coords)

    manifest["_WK"] = pd.to_numeric(manifest["WAFER_KEY"], errors="coerce").astype("Int64")
    manifest["_DID"] = pd.to_numeric(manifest["DEFECT_ID"], errors="coerce").astype("Int64")

    enrich_cols = [
        c for c in ["_WK", "_DID", "LOT7", "WAFER_ID", "CLASS", "LAYER", "SUBENTITY", "SUBENTITY_END_TIME"]
        if c in coords_lookup.columns
    ]
    merged = manifest.merge(coords_lookup[enrich_cols], on=["_WK", "_DID"], how="left")

    # Build quick filename index for optional rename step.
    file_index: Dict[str, List[str]] = {}
    for fp in _list_image_files(image_root):
        file_index.setdefault(os.path.basename(fp).lower(), []).append(fp)

    updated_local = []
    for _, row in merged.iterrows():
        current = row.get("LOCAL_IMAGE_FILE")
        current = None if pd.isna(current) or str(current).strip() == "" else os.path.normpath(str(current))

        expected = _build_expected_path(row, image_root)
        expected_exists = os.path.isfile(expected)

        final_path = current
        if expected_exists:
            final_path = expected
        elif current and os.path.isfile(current):
            final_path = current
        elif rename_missing:
            key = os.path.basename(expected).lower()
            candidates = file_index.get(key, [])
            if len(candidates) == 1:
                src = candidates[0]
                os.makedirs(os.path.dirname(expected), exist_ok=True)
                if apply:
                    shutil.move(src, expected)
                    file_index[key] = [expected]
                final_path = expected
                stats.renamed += 1

        if final_path and (current != final_path):
            stats.backfilled += 1
        updated_local.append(final_path)

    merged["LOCAL_IMAGE_FILE"] = updated_local

    keep_cols = [c for c in manifest.columns if c not in {"_WK", "_DID"}]
    out = _normalize_manifest_schema(merged[keep_cols].copy())

    if apply:
        out.to_csv(manifest_path, index=False)

    return out, stats


def _prune_files(
    manifest: pd.DataFrame,
    image_root: str,
    retention_days: int,
    apply: bool,
) -> Stats:
    stats = Stats()

    work = manifest.copy()
    time_col = "SUBENTITY_END_TIME" if "SUBENTITY_END_TIME" in work.columns else "INSPECTION_TIME"
    if time_col not in work.columns:
        raise ValueError("Manifest missing both SUBENTITY_END_TIME and INSPECTION_TIME")

    work[time_col] = pd.to_datetime(work[time_col], errors="coerce")
    newest_ts = work[time_col].max()
    if pd.isna(newest_ts):
        newest_ts = datetime.now()

    cutoff = newest_ts - timedelta(days=retention_days)

    # Prune manifest-referenced files first.
    refs = work["LOCAL_IMAGE_FILE"].dropna().astype(str)
    refs = [os.path.normpath(p) for p in refs if p.strip()]
    ref_set = set(refs)

    candidates = []
    for p in ref_set:
        ts = _parse_ts_from_filename(p)
        if ts and ts < cutoff:
            candidates.append(p)

    stats.prune_candidates += len(candidates)

    # Also prune unreferenced files older than cutoff.
    all_files = _list_image_files(image_root)
    unref = [p for p in all_files if os.path.normpath(p) not in ref_set]
    stats.unreferenced_files = len(unref)

    unref_old = []
    for p in unref:
        ts = _parse_ts_from_filename(p)
        if ts and ts < cutoff:
            unref_old.append(p)

    stats.prune_candidates += len(unref_old)

    if apply:
        for p in candidates + unref_old:
            try:
                if os.path.isfile(p):
                    os.remove(p)
                    stats.prune_deleted += 1
            except OSError:
                pass

        # Drop manifest rows for deleted referenced files.
        deleted_set = set(os.path.normpath(p) for p in candidates)
        if deleted_set:
            if "LOCAL_IMAGE_FILE" in work.columns:
                keep = ~work["LOCAL_IMAGE_FILE"].fillna("").astype(str).map(lambda p: os.path.normpath(p) in deleted_set)
                work = work[keep].copy()
                work = _normalize_manifest_schema(work)

    print(f"Cutoff (retention={retention_days}d): {cutoff:%Y-%m-%d %H:%M:%S}")
    print(f"Referenced prune candidates: {len(candidates)}")
    print(f"Unreferenced files: {len(unref)}")
    print(f"Unreferenced old candidates: {len(unref_old)}")

    if apply and "LOCAL_IMAGE_FILE" in work.columns:
        manifest_path = str(PIPELINE_PATHS.defect_images_manifest_csv)
        work.to_csv(manifest_path, index=False)

    return stats


def run_reconcile_prune(
    manifest_path: str,
    coords_path: str,
    image_root: str,
    retention_days: int = 60,
    rename_missing: bool = False,
    append_inventory: bool = False,
    apply: bool = False,
    verbose: bool = True,
) -> Stats:
    manifest_path = os.path.normpath(manifest_path)
    coords_path = os.path.normpath(coords_path)
    image_root = os.path.normpath(image_root)

    if verbose:
        print("=== Reconcile + Prune Images ===")
        print(f"Manifest: {manifest_path}")
        print(f"Coords:   {coords_path}")
        print(f"Images:   {image_root}")
        print(f"Mode:     {'APPLY' if apply else 'DRY-RUN'}")

    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    if not os.path.isfile(coords_path):
        raise FileNotFoundError(f"Coordinates CSV not found: {coords_path}")
    if not os.path.isdir(image_root):
        raise FileNotFoundError(f"Image root not found: {image_root}")

    reconciled, stats_recon = _reconcile_manifest(
        manifest_path=manifest_path,
        coords_path=coords_path,
        image_root=image_root,
        apply=apply,
        rename_missing=rename_missing,
    )

    stats_prune = _prune_files(
        manifest=reconciled,
        image_root=image_root,
        retention_days=retention_days,
        apply=apply,
    )

    manifest_after_prune = reconciled
    if apply and os.path.isfile(manifest_path):
        manifest_after_prune = pd.read_csv(manifest_path, low_memory=False)

    if append_inventory:
        _, appended = _append_missing_inventory_rows(
            manifest=manifest_after_prune,
            image_root=image_root,
            apply=apply,
            manifest_path=manifest_path,
        )
        stats_prune.inventory_appended = appended

    combined = Stats(
        backfilled=stats_recon.backfilled,
        renamed=stats_recon.renamed,
        prune_deleted=stats_prune.prune_deleted,
        prune_candidates=stats_prune.prune_candidates,
        unreferenced_files=stats_prune.unreferenced_files,
        inventory_appended=stats_prune.inventory_appended,
    )

    if verbose:
        print("=== Summary ===")
        print(f"Manifest backfilled rows: {combined.backfilled}")
        print(f"Files renamed into expected path: {combined.renamed}")
        print(f"Prune candidates: {combined.prune_candidates}")
        print(f"Files deleted: {combined.prune_deleted}")
        print(f"Unreferenced files currently on disk: {combined.unreferenced_files}")
        print(f"Inventory rows appended: {combined.inventory_appended}")

    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile + prune defect image files")
    parser.add_argument("--manifest", default=str(PIPELINE_PATHS.defect_images_manifest_csv))
    parser.add_argument("--coords", default=str(PIPELINE_PATHS.defect_coordinates_csv))
    parser.add_argument("--image-root", default=str(PIPELINE_PATHS.image_dir))
    parser.add_argument("--retention-days", type=int, default=60)
    parser.add_argument("--rename-missing", action="store_true", help="Move uniquely matched files into expected organized path")
    parser.add_argument(
        "--append-inventory",
        action="store_true",
        help="Append manifest rows for image files on disk that are not currently referenced",
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    args = parser.parse_args()

    run_reconcile_prune(
        manifest_path=args.manifest,
        coords_path=args.coords,
        image_root=args.image_root,
        retention_days=args.retention_days,
        rename_missing=args.rename_missing,
        append_inventory=args.append_inventory,
        apply=args.apply,
        verbose=True,
    )


if __name__ == "__main__":
    main()
