from __future__ import annotations

import shutil
from pathlib import Path

from pipeline_config import PIPELINE_PATHS, ensure_pipeline_dirs, write_artifact_manifest


def _copy_file_if_needed(source: Path, destination: Path, overwrite: bool = False) -> str:
    if not source.exists():
        return f"SKIP missing file: {source}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        return f"SKIP existing file: {destination}"
    shutil.copy2(source, destination)
    return f"COPIED file: {source} -> {destination}"


def _copy_tree_if_needed(source: Path, destination: Path, overwrite: bool = False) -> str:
    if not source.exists():
        return f"SKIP missing directory: {source}"
    if destination.exists() and any(destination.iterdir()) and not overwrite:
        return f"SKIP existing directory contents: {destination}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return f"COPIED directory: {source} -> {destination}"


def _merge_tree(source: Path, destination: Path) -> str:
    if not source.exists():
        return f"SKIP missing directory: {source}"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return f"MERGED directory: {source} -> {destination}"


def migrate_existing_outputs(overwrite: bool = False) -> list[str]:
    ensure_pipeline_dirs()

    legacy_root = PIPELINE_PATHS.workspace_root
    operations = [
        (legacy_root / "8M5CL_8M6CL_EXTENDED.csv", PIPELINE_PATHS.extended_output_csv, False),
        (legacy_root / "DEFECT_COORDINATES_EXTENDED.csv", PIPELINE_PATHS.defect_coordinates_csv, False),
        (legacy_root / "DEFECT_COORDINATES_EXTENDED_IMAGES.csv", PIPELINE_PATHS.defect_images_manifest_csv, False),
        (legacy_root / "8M5CL_8M6CL_2025_LOT.csv", PIPELINE_PATHS.lot_level_output_csv, False),
    ]

    results = []
    for source, destination, is_dir in operations:
        if is_dir:
            results.append(_copy_tree_if_needed(source, destination, overwrite=overwrite))
        else:
            results.append(_copy_file_if_needed(source, destination, overwrite=overwrite))

    for benchmark_csv in sorted(legacy_root.glob("*_FLEET_BENCHMARK_ELWC_7DAY.csv")):
        results.append(
            _copy_file_if_needed(
                benchmark_csv,
                PIPELINE_PATHS.benchmark_outputs_dir / benchmark_csv.name,
                overwrite=overwrite,
            )
        )

    for source_dir in PIPELINE_PATHS.legacy_image_dirs:
        if overwrite:
            results.append(_copy_tree_if_needed(source_dir, PIPELINE_PATHS.image_dir, overwrite=True))
        else:
            results.append(_merge_tree(source_dir, PIPELINE_PATHS.image_dir))

    manifest_path = write_artifact_manifest(
        PIPELINE_PATHS.artifacts_dir / "layout_migration_artifacts.json",
        extra_outputs={
            "legacy_root": legacy_root,
            "migrated_wafer_output": PIPELINE_PATHS.extended_output_csv,
            "migrated_defect_output": PIPELINE_PATHS.defect_coordinates_csv,
            "migrated_images_dir": PIPELINE_PATHS.image_dir,
        },
    )
    results.append(f"WROTE manifest: {manifest_path}")
    return results


def main() -> None:
    print("MIGRATE PIPELINE OUTPUT LAYOUT")
    print("=" * 70)
    for line in migrate_existing_outputs(overwrite=False):
        print(line)


if __name__ == "__main__":
    main()