from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _env_path(name: str) -> Optional[Path]:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser()


@dataclass(frozen=True)
class PipelinePaths:
    workspace_root: Path
    query_dir: Path
    modular_dir: Path
    merged_sources_dir: Path
    outputs_dir: Path
    wafer_outputs_dir: Path
    defect_outputs_dir: Path
    benchmark_outputs_dir: Path
    surf_outputs_dir: Path
    artifacts_dir: Path
    image_dir: Path
    surf_image_dir: Path
    legacy_image_dir: Path
    alternate_legacy_image_dir: Path
    benchmark_dir: Path
    shared_data_root: Path

    @classmethod
    def discover(cls) -> "PipelinePaths":
        query_dir = Path(__file__).resolve().parent
        default_workspace_root = query_dir.parent
        workspace_root = _env_path("BE_PIPELINE_ROOT") or default_workspace_root
        query_dir = workspace_root / "BE_QUERY_FILES"

        shared_default = Path(
            r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson"
        )
        shared_data_root = _env_path("BE_SHARED_DATA_ROOT") or shared_default

        return cls(
            workspace_root=workspace_root,
            query_dir=query_dir,
            modular_dir=query_dir / "modular_processor",
            merged_sources_dir=query_dir / "merged_sources",
            outputs_dir=workspace_root / "outputs",
            wafer_outputs_dir=workspace_root / "outputs" / "wafer",
            defect_outputs_dir=workspace_root / "outputs" / "defects",
            benchmark_outputs_dir=workspace_root / "outputs" / "benchmarks",
            surf_outputs_dir=workspace_root / "outputs" / "surf_scan",
            artifacts_dir=workspace_root / "artifacts",
            image_dir=workspace_root / "images" / "defects",
            surf_image_dir=workspace_root / "images" / "surf_scan",
            legacy_image_dir=workspace_root / "DefectImages",
            alternate_legacy_image_dir=shared_data_root / "Defects" / "BE_60day" / "BE_60day_QUERY_FILES" / "DefectImages",
            benchmark_dir=workspace_root / "outputs" / "benchmarks",
            shared_data_root=shared_data_root,
        )

    @property
    def m5_jsl_csv(self) -> Path:
        return self.query_dir / "8M5CL_NCDD.csv"

    @property
    def m6_jsl_csv(self) -> Path:
        return self.query_dir / "8M6CL_NCDD.csv"

    @property
    def merged_m5_csv(self) -> Path:
        return self.merged_sources_dir / "8M5CL_NCDD_merged_dedup.csv"

    @property
    def merged_m6_csv(self) -> Path:
        return self.merged_sources_dir / "8M6CL_NCDD_merged_dedup.csv"

    @property
    def extended_output_csv(self) -> Path:
        return self.wafer_outputs_dir / "8M5CL_8M6CL_EXTENDED.csv"

    @property
    def defect_coordinates_csv(self) -> Path:
        return self.defect_outputs_dir / "DEFECT_COORDINATES_EXTENDED.csv"

    @property
    def defect_images_manifest_csv(self) -> Path:
        return self.defect_outputs_dir / "DEFECT_COORDINATES_EXTENDED_IMAGES.csv"

    @property
    def surf_coordinates_csv(self) -> Path:
        return self.surf_outputs_dir / "SS_COORDINATES.csv"

    @property
    def surf_metrics_csv(self) -> Path:
        return self.surf_outputs_dir / "SS_METRICS.csv"

    @property
    def surf_edx_csv(self) -> Path:
        return self.surf_outputs_dir / "SS_EDX.csv"

    @property
    def surf_edx_stacked_csv(self) -> Path:
        return self.surf_outputs_dir / "SS_EDX_STACKED.csv"

    @property
    def surf_edx_stacked_y_csv(self) -> Path:
        return self.surf_outputs_dir / "SS_EDX_STACKED_Y.csv"

    @property
    def surf_image_manifest_csv(self) -> Path:
        return self.surf_outputs_dir / "SS_EDX_IMAGES.csv"

    @property
    def surf_zero_summary_csv(self) -> Path:
        return self.surf_outputs_dir / "SS_ZEROS" / "SS_ZERO_fraction_by_event_entity_7day.csv"

    @property
    def surf_zero_wide_summary_csv(self) -> Path:
        return self.surf_outputs_dir / "SS_ZEROS" / "SS_ZERO_fraction_by_event_entity_7day_wide.csv"

    @property
    def surf_run_artifact_manifest(self) -> Path:
        return self.artifacts_dir / "surf_scan_run_artifacts.json"

    @property
    def lot_level_output_csv(self) -> Path:
        return self.wafer_outputs_dir / "8M5CL_8M6CL_2025_LOT.csv"

    @property
    def main_artifact_manifest(self) -> Path:
        return self.artifacts_dir / "main_run_artifacts.json"

    @property
    def defect_artifact_manifest(self) -> Path:
        return self.artifacts_dir / "defect_coordinates_artifacts.json"

    @property
    def benchmark_artifact_manifest(self) -> Path:
        return self.artifacts_dir / "benchmark_artifacts.json"

    @property
    def update_run_artifact_manifest(self) -> Path:
        return self.artifacts_dir / "update_run_artifacts.json"

    @property
    def pumpdown_fail_path(self) -> Path:
        return self.shared_data_root / "BE_AME_PUMPDOWN_FAILS.csv"

    @property
    def leak_rate_path(self) -> Path:
        return self.shared_data_root / "BE_AME_CHLEAK.csv"

    @property
    def leak_by_path(self) -> Path:
        return self.shared_data_root / "LEAKBY" / "processed_mfc_leak_data.csv"

    @property
    def spc_monitor_path(self) -> Path:
        return self.shared_data_root / "SPC_MONS" / "SPC_SS.csv"

    @property
    def parts_path(self) -> Path:
        return self.shared_data_root / "PLT" / "PLT_CURRENTLY_INSTALLED.csv"

    @property
    def pilot_dates_path(self) -> Path:
        return self.shared_data_root / "BE_AME_PILOT_TURN_ON_DATES.csv"

    @property
    def legacy_image_dirs(self) -> Tuple[Path, ...]:
        return (self.legacy_image_dir, self.alternate_legacy_image_dir)


PIPELINE_PATHS = PipelinePaths.discover()


def build_artifact_manifest(extra_outputs: Optional[Dict[str, Path]] = None) -> Dict[str, str]:
    manifest = {
        "workspace_root": str(PIPELINE_PATHS.workspace_root),
        "query_dir": str(PIPELINE_PATHS.query_dir),
        "modular_dir": str(PIPELINE_PATHS.modular_dir),
        "merged_sources_dir": str(PIPELINE_PATHS.merged_sources_dir),
        "outputs_dir": str(PIPELINE_PATHS.outputs_dir),
        "wafer_outputs_dir": str(PIPELINE_PATHS.wafer_outputs_dir),
        "defect_outputs_dir": str(PIPELINE_PATHS.defect_outputs_dir),
        "benchmark_outputs_dir": str(PIPELINE_PATHS.benchmark_outputs_dir),
        "surf_outputs_dir": str(PIPELINE_PATHS.surf_outputs_dir),
        "artifacts_dir": str(PIPELINE_PATHS.artifacts_dir),
        "m5_jsl_csv": str(PIPELINE_PATHS.m5_jsl_csv),
        "m6_jsl_csv": str(PIPELINE_PATHS.m6_jsl_csv),
        "merged_m5_csv": str(PIPELINE_PATHS.merged_m5_csv),
        "merged_m6_csv": str(PIPELINE_PATHS.merged_m6_csv),
        "extended_output_csv": str(PIPELINE_PATHS.extended_output_csv),
        "defect_coordinates_csv": str(PIPELINE_PATHS.defect_coordinates_csv),
        "defect_images_manifest_csv": str(PIPELINE_PATHS.defect_images_manifest_csv),
        "surf_coordinates_csv": str(PIPELINE_PATHS.surf_coordinates_csv),
        "surf_metrics_csv": str(PIPELINE_PATHS.surf_metrics_csv),
        "surf_edx_csv": str(PIPELINE_PATHS.surf_edx_csv),
        "surf_edx_stacked_csv": str(PIPELINE_PATHS.surf_edx_stacked_csv),
        "surf_edx_stacked_y_csv": str(PIPELINE_PATHS.surf_edx_stacked_y_csv),
        "surf_image_manifest_csv": str(PIPELINE_PATHS.surf_image_manifest_csv),
        "surf_image_dir": str(PIPELINE_PATHS.surf_image_dir),
        "surf_zero_summary_csv": str(PIPELINE_PATHS.surf_zero_summary_csv),
        "surf_zero_wide_summary_csv": str(PIPELINE_PATHS.surf_zero_wide_summary_csv),
        "image_dir": str(PIPELINE_PATHS.image_dir),
        "legacy_image_dir": str(PIPELINE_PATHS.legacy_image_dir),
        "alternate_legacy_image_dir": str(PIPELINE_PATHS.alternate_legacy_image_dir),
        "lot_level_output_csv": str(PIPELINE_PATHS.lot_level_output_csv),
        "pumpdown_fail_path": str(PIPELINE_PATHS.pumpdown_fail_path),
        "leak_rate_path": str(PIPELINE_PATHS.leak_rate_path),
        "leak_by_path": str(PIPELINE_PATHS.leak_by_path),
        "spc_monitor_path": str(PIPELINE_PATHS.spc_monitor_path),
        "parts_path": str(PIPELINE_PATHS.parts_path),
        "pilot_dates_path": str(PIPELINE_PATHS.pilot_dates_path),
    }
    if extra_outputs:
        manifest.update({key: str(value) for key, value in extra_outputs.items()})
    return manifest


def validate_pipeline_paths(required_inputs: Optional[Dict[str, Path]] = None) -> List[str]:
    checks = []
    required_inputs = required_inputs or {}
    for name, path in required_inputs.items():
        status = "OK" if path.exists() else "MISSING"
        checks.append(f"{status}: {name} -> {path}")
    return checks


def write_artifact_manifest(target: Path, extra_outputs: Optional[Dict[str, Path]] = None) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_artifact_manifest(extra_outputs=extra_outputs), indent=2),
        encoding="utf-8",
    )
    return target


def ensure_pipeline_dirs() -> List[Path]:
    dirs = [
        PIPELINE_PATHS.outputs_dir,
        PIPELINE_PATHS.wafer_outputs_dir,
        PIPELINE_PATHS.defect_outputs_dir,
        PIPELINE_PATHS.benchmark_outputs_dir,
        PIPELINE_PATHS.surf_outputs_dir,
        PIPELINE_PATHS.artifacts_dir,
        PIPELINE_PATHS.image_dir,
        PIPELINE_PATHS.surf_image_dir,
        PIPELINE_PATHS.merged_sources_dir,
    ]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)
    return dirs