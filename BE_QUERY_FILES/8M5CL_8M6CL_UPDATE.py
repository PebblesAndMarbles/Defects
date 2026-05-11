from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd

CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(0, str(CURRENT_DIR / "modular_processor"))

from DEFECT_COORDINATES_QUERY import query_defect_coordinates
from modular_processor.EXTEND_BENCHMARK import main as run_benchmark_extension
from modular_processor.main import main as run_wafer_update
from pipeline_config import PIPELINE_PATHS, ensure_pipeline_dirs, validate_pipeline_paths, write_artifact_manifest
from reconcile_prune_images import run_reconcile_prune


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
LOGGER = logging.getLogger("update_run")

RAW_INPUT_MAX_AGE_DAYS = 7
IMAGE_MANIFEST_RETENTION_DAYS = 60
WAFER_60DAY_LOOKBACK_DAYS = 60


@dataclass
class StepResult:
    name: str
    started_at: datetime
    finished_at: datetime
    success: bool
    rows: int | None = None
    error: str | None = None


def _check_recent_raw_inputs(max_age_days: int) -> List[str]:
    checks = []
    now = pd.Timestamp.now()
    for label, path in {
        "m5_jsl_csv": PIPELINE_PATHS.m5_jsl_csv,
        "m6_jsl_csv": PIPELINE_PATHS.m6_jsl_csv,
    }.items():
        if not path.exists():
            checks.append(f"MISSING: {label} -> {path}")
            continue
        age_days = (now - pd.Timestamp(path.stat().st_mtime, unit="s")).total_seconds() / 86400.0
        status = "OK" if age_days <= max_age_days else "STALE"
        checks.append(f"{status}: {label} -> {path} (age_days={age_days:.2f})")
    return checks


def _require_fresh_raw_inputs(max_age_days: int) -> None:
    checks = _check_recent_raw_inputs(max_age_days)
    stale_or_missing = [line for line in checks if line.startswith("MISSING") or line.startswith("STALE")]
    for line in checks:
        LOGGER.info(line)
    if stale_or_missing:
        raise RuntimeError(
            "Raw JSL inputs are missing or stale. Run the 10-day lookback JSL files first. "
            + " | ".join(stale_or_missing)
        )


def _rows_for_csv(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return len(pd.read_csv(path, low_memory=False))
    except Exception:
        return None


def _run_step(name: str, func, *, raise_on_error: bool = True) -> StepResult:
    started_at = datetime.now()
    LOGGER.info("[%s] started", name)
    try:
        result = func()
        finished_at = datetime.now()

        rows = None
        if hasattr(result, "shape"):
            rows = int(result.shape[0])

        LOGGER.info("[%s] finished", name)
        return StepResult(
            name=name,
            started_at=started_at,
            finished_at=finished_at,
            success=True,
            rows=rows,
        )
    except Exception as exc:
        finished_at = datetime.now()
        LOGGER.exception("[%s] failed", name)
        if raise_on_error:
            raise
        return StepResult(
            name=name,
            started_at=started_at,
            finished_at=finished_at,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def _sync_image_manifest_inventory() -> None:
    stats = run_reconcile_prune(
        manifest_path=str(PIPELINE_PATHS.defect_images_manifest_csv),
        coords_path=str(PIPELINE_PATHS.defect_coordinates_csv),
        image_root=str(PIPELINE_PATHS.image_dir),
        retention_days=IMAGE_MANIFEST_RETENTION_DAYS,
        rename_missing=True,
        append_inventory=True,
        apply=True,
        verbose=False,
    )
    LOGGER.info(
        "[manifest_sync] backfilled=%s renamed=%s appended=%s prune_candidates=%s deleted=%s unreferenced=%s",
        stats.backfilled,
        stats.renamed,
        stats.inventory_appended,
        stats.prune_candidates,
        stats.prune_deleted,
        stats.unreferenced_files,
    )
    LOGGER.info(
        "[manifest_sync] summary manifest=%s appended=%s existing_unreferenced=%s retention_days=%s",
        PIPELINE_PATHS.defect_images_manifest_csv,
        stats.inventory_appended,
        stats.unreferenced_files,
        IMAGE_MANIFEST_RETENTION_DAYS,
    )


def _wafer_60day_output_path() -> Path:
    base = PIPELINE_PATHS.extended_output_csv
    return base.with_name(f"{base.stem}_60DAY{base.suffix}")


def _export_wafer_60day_subset() -> pd.DataFrame:
    src = PIPELINE_PATHS.extended_output_csv
    out = _wafer_60day_output_path()
    if not src.exists():
        raise FileNotFoundError(f"Extended wafer output not found: {src}")

    df = pd.read_csv(src, low_memory=False)
    time_col = "INSPECT_TIME" if "INSPECT_TIME" in df.columns else "INSPECTION_TIME"
    if time_col not in df.columns:
        raise KeyError("Extended wafer output missing INSPECT_TIME/INSPECTION_TIME")

    work = df.copy()
    work[time_col] = pd.to_datetime(work[time_col], errors="coerce")
    newest = work[time_col].max()
    if pd.isna(newest):
        subset = work.iloc[0:0].copy()
    else:
        cutoff = newest - pd.Timedelta(days=WAFER_60DAY_LOOKBACK_DAYS)
        subset = work[work[time_col] >= cutoff].copy()

    subset.to_csv(out, index=False)
    LOGGER.info(
        "[wafer_60day_export] source=%s output=%s rows=%s lookback_days=%s",
        src,
        out,
        len(subset),
        WAFER_60DAY_LOOKBACK_DAYS,
    )
    return subset


def main() -> List[StepResult]:
    ensure_pipeline_dirs()

    for line in validate_pipeline_paths(
        {
            "m5_jsl_csv": PIPELINE_PATHS.m5_jsl_csv,
            "m6_jsl_csv": PIPELINE_PATHS.m6_jsl_csv,
        }
    ):
        LOGGER.info(line)

    _require_fresh_raw_inputs(RAW_INPUT_MAX_AGE_DAYS)

    results = [
        _run_step("wafer_update", run_wafer_update),
        _run_step("wafer_60day_export", _export_wafer_60day_subset),
        _run_step("defect_coordinates", query_defect_coordinates),
        _run_step("manifest_sync", _sync_image_manifest_inventory),
        _run_step("benchmark_extension", run_benchmark_extension, raise_on_error=False),
    ]

    failed_steps = [step.name for step in results if not step.success]
    if failed_steps:
        LOGGER.warning("Non-fatal step failures: %s", ", ".join(failed_steps))

    manifest_path = write_artifact_manifest(
        PIPELINE_PATHS.update_run_artifact_manifest,
        extra_outputs={
            "wafer_output_csv": PIPELINE_PATHS.extended_output_csv,
            "wafer_output_rows": _rows_for_csv(PIPELINE_PATHS.extended_output_csv),
            "wafer_60day_output_csv": _wafer_60day_output_path(),
            "wafer_60day_output_rows": _rows_for_csv(_wafer_60day_output_path()),
            "defect_output_csv": PIPELINE_PATHS.defect_coordinates_csv,
            "defect_output_rows": _rows_for_csv(PIPELINE_PATHS.defect_coordinates_csv),
            "defect_image_manifest_csv": PIPELINE_PATHS.defect_images_manifest_csv,
            "benchmark_output_dir": PIPELINE_PATHS.benchmark_outputs_dir,
            "steps_completed": ", ".join(step.name for step in results if step.success),
            "steps_failed": ", ".join(failed_steps),
        },
    )
    LOGGER.info("Update-run artifact manifest saved to: %s", manifest_path)

    for step in results:
        duration = step.finished_at - step.started_at
        LOGGER.info(
            "[%s] duration=%s success=%s rows=%s error=%s",
            step.name,
            duration,
            step.success,
            step.rows,
            step.error,
        )

    return results


if __name__ == "__main__":
    main()