from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple

import pandas as pd

from pipeline_config import PIPELINE_PATHS, ensure_pipeline_dirs, write_artifact_manifest
import surf_scan_coordinates as surf_coords
import surf_scan_images as surf_images
from surf_scan_elwc_pm_stage_backfill import apply_stage_to_production, build_stage
from surf_scan_config import (
    DEFAULT_IMAGE_RETENTION_DAYS,
    DEFAULT_INCREMENTAL_LOOKBACK_DAYS,
    DEFAULT_SEED_LOOKBACK_DAYS,
)



logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
LOGGER = logging.getLogger("surf_scan_update")
ELWC_STAGE_CHUNK_EVENTS = 100


@dataclass
class RunSummary:
    mode: str
    lookback_days: int
    run_images: bool
    rows_coordinates: int
    rows_metrics: int
    rows_stacked: int
    rows_stacked_y: int
    files_pruned: int
    prune_cutoff_utc: str


@dataclass
class StepResult:
    name: str
    started_at: datetime
    finished_at: datetime
    rows: int | None = None


def _run_coordinates(
    lookback_days: int,
    incremental_update: bool,
    enable_legacy_nearest_pm_enrichment: bool,
) -> pd.DataFrame | None:
    surf_coords.OUTPUT_CSV = str(PIPELINE_PATHS.surf_coordinates_csv)
    surf_coords.METRICS_OUTPUT_CSV = str(PIPELINE_PATHS.surf_metrics_csv)
    surf_coords.EDX_OUTPUT_CSV = str(PIPELINE_PATHS.surf_edx_csv)
    surf_coords.LOOKBACK_DAYS = int(lookback_days)
    surf_coords.INCREMENTAL_UPDATE = bool(incremental_update)
    surf_coords.ENABLE_LEGACY_NEAREST_PM_ENRICHMENT = bool(enable_legacy_nearest_pm_enrichment)

    LOGGER.info("[coordinates] starting in-repo SS coordinate query")
    result = surf_coords.query_ss_coordinates()
    LOGGER.info("[coordinates] completed in-repo SS coordinate query")
    return result


def _run_elwc_rf_refresh(lookback_days: int, chunk_events: int = ELWC_STAGE_CHUNK_EVENTS) -> pd.DataFrame:
    LOGGER.info(
        "[elwc_rf_refresh] building staged ELWC metrics for lookback=%s chunk_events=%s",
        lookback_days,
        chunk_events,
    )
    stage_payload = build_stage(lookback_days=lookback_days, chunk_events=chunk_events)

    stage_metrics_output = stage_payload.get("stage_metrics_output")
    if not stage_metrics_output:
        LOGGER.warning("[elwc_rf_refresh] no stage output produced; skipping production apply")
        return pd.DataFrame({"rf_rows_updated": [0]})

    apply_payload = apply_stage_to_production(
        Path(str(stage_metrics_output)),
        keep_diagnostics=False,
    )
    LOGGER.info("[elwc_rf_refresh] applied RF columns: %s", apply_payload.get("target_pm_columns"))

    metrics_rows = int(apply_payload.get("metrics", {}).get("rows", 0))
    coords_rows = int(apply_payload.get("coordinates", {}).get("rows", 0))
    return pd.DataFrame({"rf_rows_updated": [metrics_rows + coords_rows]})


def _build_stacked_edx(input_csv: Path, output_csv: Path, output_y_csv: Path) -> Tuple[int, int]:
    if not input_csv.exists():
        return 0, 0

    df = pd.read_csv(input_csv, low_memory=False)
    if df.empty:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(output_csv, index=False)
        pd.DataFrame().to_csv(output_y_csv, index=False)
        return 0, 0

    edx_pattern = re.compile(r"^EDX_ELEM(\d+)_([A-Z]+)$", re.IGNORECASE)
    edx_cols = [c for c in df.columns if edx_pattern.match(c)]
    if not edx_cols:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(output_csv, index=False)
        pd.DataFrame().to_csv(output_y_csv, index=False)
        return 0, 0

    id_cols = [c for c in df.columns if c not in edx_cols]
    df["IMAGE_COUNT"] = pd.to_numeric(df.get("IMAGE_COUNT", 0), errors="coerce")
    df_edx = df[df["IMAGE_COUNT"] > 0].copy()

    for col in edx_cols:
        df_edx[col] = pd.to_numeric(df_edx[col], errors="coerce")

    melted = df_edx.melt(
        id_vars=id_cols,
        value_vars=edx_cols,
        var_name="EDX_COL",
        value_name="EDX_VALUE",
    )
    melted = melted[melted["EDX_VALUE"] > 0].copy()

    def parse_edx_col(col_name: str):
        match = edx_pattern.match(col_name)
        if not match:
            return None, str(col_name)
        return int(match.group(1)), match.group(2).upper()

    parsed = melted["EDX_COL"].map(parse_edx_col)
    melted["EDX_ELEM_NUM"] = [p[0] for p in parsed]
    melted["ELEMENT"] = [p[1] for p in parsed]

    element_label_map = {
        "ALUMINUM": "ALUMINUM",
        "ALUMINIUM": "ALUMINUM",
        "CALCIUM": "CALCIUM",
        "CARBON": "CARBON",
        "FLUORINE": "FLUORINE",
        "IRON": "IRON",
        "MAGNESIUM": "MAGNESIUM",
        "NICKEL": "NICKEL",
        "NITROGEN": "NITROGEN",
        "OSMIUM": "YPO",
        "PHOSPHORUS": "YPO",
        "OXYGEN": "OXYGEN",
        "SILICON": "SILICON",
        "TITANIUM": "TITANIUM",
        "YTTRIUM": "YPO",
        "PLATINUM": "PLATINUM",
    }

    melted["ORIGINAL_ELEMENT"] = melted["ELEMENT"].astype(str).str.upper()
    melted = melted[melted["ORIGINAL_ELEMENT"].isin(element_label_map)].copy()
    melted["ELEMENT"] = melted["ORIGINAL_ELEMENT"].map(element_label_map)

    size_num = pd.to_numeric(melted.get("SIZE_D_UM"), errors="coerce")
    melted["SIZE"] = size_num.eq(100).map({True: "LARGE", False: "SMALL"})

    final_cols = id_cols + [
        "SIZE",
        "ELEMENT",
        "ORIGINAL_ELEMENT",
        "EDX_ELEM_NUM",
        "EDX_COL",
        "EDX_VALUE",
    ]
    out = melted[final_cols]
    sort_cols = [c for c in ["WAFER_KEY", "DEFECT_ID", "EDX_ELEM_NUM"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols).reset_index(drop=True)
    else:
        out = out.reset_index(drop=True)

    out_y = out[
        out["ORIGINAL_ELEMENT"].isin(["OSMIUM", "PHOSPHORUS", "YTTRIUM"])
    ].copy()

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)
    out_y.to_csv(output_y_csv, index=False)
    return len(out), len(out_y)


def _build_zero_timebin_summary(input_csv: Path, output_csv: Path, output_wide_csv: Path) -> None:
    if not input_csv.exists():
        return

    df = pd.read_csv(input_csv, low_memory=False)
    required = {"INSPECTION_TIME", "PRIMARY_EQUIP", "EVENT", "ADDER_DEFECTS"}
    if not required.issubset(df.columns):
        return

    df["INSPECTION_TIME"] = pd.to_datetime(df["INSPECTION_TIME"], errors="coerce")
    valid_times = df["INSPECTION_TIME"].dropna()
    if valid_times.empty:
        return

    start_day = valid_times.min().normalize()
    days_since_start = (df["INSPECTION_TIME"].dt.floor("D") - start_day).dt.days
    df["END_DATE"] = start_day + pd.to_timedelta((days_since_start // 7) * 7 + 6, unit="D")

    primary = df["PRIMARY_EQUIP"].fillna("").astype(str)
    entity = primary.str[:6]
    last_char = primary.str[-1]

    suffix = pd.Series("", index=df.index, dtype="object")
    suffix = suffix.mask(last_char.isin(["1", "3", "5"]), "_L")
    suffix = suffix.mask(last_char.isin(["2", "4", "6"]), "_R")

    df["ENTITY"] = entity
    df["ENTITY_L"] = df["ENTITY"] + "_L"
    df["ENTITY_R"] = df["ENTITY"] + "_R"
    df.loc[suffix != "_L", "ENTITY_L"] = ""
    df.loc[suffix != "_R", "ENTITY_R"] = ""

    adder_numeric = pd.to_numeric(df["ADDER_DEFECTS"], errors="coerce")
    df["ZERO_COUNT_VAL"] = adder_numeric.eq(0).astype(int)

    def summarize(group_col: str) -> pd.DataFrame:
        use = df[["END_DATE", "EVENT", group_col, "ZERO_COUNT_VAL"]].copy()
        if group_col in {"ENTITY_L", "ENTITY_R"}:
            use = use[use[group_col] != ""]
        use = use.dropna(subset=["END_DATE", "EVENT", group_col])
        out = (
            use.groupby(["END_DATE", "EVENT", group_col], dropna=False)
            .agg(ROW_COUNT=("ZERO_COUNT_VAL", "size"), ZERO_COUNT=("ZERO_COUNT_VAL", "sum"))
            .reset_index()
        )
        out["END_DATE"] = out["END_DATE"].dt.strftime("%Y-%m-%d")
        out["ZERO_FRACTION"] = out["ZERO_COUNT"] / out["ROW_COUNT"]
        out = out.rename(columns={group_col: "GROUP_VALUE"})
        out["GROUP_TYPE"] = group_col
        return out[["END_DATE", "EVENT", "GROUP_TYPE", "GROUP_VALUE", "ROW_COUNT", "ZERO_COUNT", "ZERO_FRACTION"]]

    combined = pd.concat(
        [summarize("ENTITY"), summarize("ENTITY_L"), summarize("ENTITY_R")],
        ignore_index=True,
    ).sort_values(["END_DATE", "EVENT", "GROUP_TYPE", "GROUP_VALUE"], kind="mergesort")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_csv, index=False)

    entity = combined[combined["GROUP_TYPE"] == "ENTITY"][
        ["END_DATE", "EVENT", "GROUP_VALUE", "ZERO_FRACTION"]
    ].rename(columns={"ZERO_FRACTION": "ENTITY_ZFRAC"})

    entity_l = combined[combined["GROUP_TYPE"] == "ENTITY_L"][
        ["END_DATE", "EVENT", "GROUP_VALUE", "ZERO_FRACTION"]
    ].copy()
    entity_l["GROUP_VALUE"] = entity_l["GROUP_VALUE"].str[:-2]
    entity_l = entity_l.rename(columns={"ZERO_FRACTION": "ENTITY_L_ZFRAC"})

    entity_r = combined[combined["GROUP_TYPE"] == "ENTITY_R"][
        ["END_DATE", "EVENT", "GROUP_VALUE", "ZERO_FRACTION"]
    ].copy()
    entity_r["GROUP_VALUE"] = entity_r["GROUP_VALUE"].str[:-2]
    entity_r = entity_r.rename(columns={"ZERO_FRACTION": "ENTITY_R_ZFRAC"})

    wide = (
        entity.merge(entity_l, on=["END_DATE", "EVENT", "GROUP_VALUE"], how="outer")
        .merge(entity_r, on=["END_DATE", "EVENT", "GROUP_VALUE"], how="outer")
        .sort_values(["END_DATE", "EVENT", "GROUP_VALUE"], kind="mergesort")
        .reset_index(drop=True)
    )
    output_wide_csv.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(output_wide_csv, index=False)


def _run_image_query(lookback_days: int) -> None:
    surf_images.SS_COORDS_CSV = str(PIPELINE_PATHS.surf_coordinates_csv)
    surf_images.IMAGE_OUTPUT_FOLDER = str(PIPELINE_PATHS.surf_image_dir)
    surf_images.IMAGE_MANIFEST_CSV = str(PIPELINE_PATHS.surf_image_manifest_csv)
    surf_images.N_DAYS = int(max(lookback_days, DEFAULT_IMAGE_RETENTION_DAYS))

    LOGGER.info("[images] starting in-repo SS EDX image query")
    surf_images.query_edx_images()
    LOGGER.info("[images] completed in-repo SS EDX image query")


def _run_step(name: str, func) -> StepResult:
    started_at = datetime.now()
    LOGGER.info("[%s] started", name)
    result = func()
    finished_at = datetime.now()
    rows = None
    if hasattr(result, "shape"):
        rows = int(result.shape[0])
    LOGGER.info("[%s] finished", name)
    return StepResult(name=name, started_at=started_at, finished_at=finished_at, rows=rows)


def _prune_old_image_files(
    image_root: Path,
    retention_days: int = 60,
    dry_run: bool = False,
    manifest_path: Path | None = None,
) -> Tuple[int, str]:
    if not image_root.exists():
        return 0, datetime.now().isoformat()

    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

    tracked_paths: set[str] = set()
    if manifest_path is not None and manifest_path.exists():
        try:
            manifest = pd.read_csv(manifest_path, low_memory=False)
            if {"INSPECTION_TIME", "LOCAL_IMAGE_FILE"}.issubset(manifest.columns):
                manifest = manifest.dropna(subset=["INSPECTION_TIME", "LOCAL_IMAGE_FILE"]).copy()
                manifest["INSPECTION_TIME"] = pd.to_datetime(manifest["INSPECTION_TIME"], errors="coerce")
                manifest = manifest.dropna(subset=["INSPECTION_TIME"])

                old_rows = manifest[manifest["INSPECTION_TIME"] < pd.Timestamp(cutoff)]
                for local_path in old_rows["LOCAL_IMAGE_FILE"].astype(str):
                    normalized = os.path.normcase(os.path.normpath(local_path))
                    tracked_paths.add(normalized)
                    path_obj = Path(local_path)
                    if path_obj.exists() and path_obj.suffix.lower() in allowed_suffixes:
                        removed += 1
                        if not dry_run:
                            try:
                                path_obj.unlink()
                            except OSError:
                                pass
        except Exception:
            pass

    for file_path in image_root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in allowed_suffixes:
            continue

        normalized = os.path.normcase(os.path.normpath(str(file_path)))
        if normalized in tracked_paths:
            continue

        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        if mtime < cutoff:
            removed += 1
            if not dry_run:
                try:
                    file_path.unlink()
                except OSError:
                    pass

    return removed, cutoff.isoformat()


def _row_count(csv_path: Path) -> int:
    if not csv_path.exists():
        return 0
    try:
        return len(pd.read_csv(csv_path, low_memory=False))
    except Exception:
        return 0


def run(
    mode: str,
    lookback_days: int,
    run_images: bool,
    prune_dry_run: bool,
    enable_legacy_nearest_pm_enrichment: bool,
) -> RunSummary:
    ensure_pipeline_dirs()

    incremental_update = mode == "incremental"
    step_results: list[StepResult] = []
    step_results.append(
        _run_step(
            "coordinates",
            lambda: _run_coordinates(
                lookback_days,
                incremental_update,
                enable_legacy_nearest_pm_enrichment,
            ),
        )
    )
    step_results.append(
        _run_step(
            "elwc_rf_refresh",
            lambda: _run_elwc_rf_refresh(lookback_days, ELWC_STAGE_CHUNK_EVENTS),
        )
    )

    rows_stacked = 0
    rows_stacked_y = 0

    def _run_stacked() -> pd.DataFrame:
        nonlocal rows_stacked, rows_stacked_y
        rows_stacked, rows_stacked_y = _build_stacked_edx(
            PIPELINE_PATHS.surf_coordinates_csv,
            PIPELINE_PATHS.surf_edx_stacked_csv,
            PIPELINE_PATHS.surf_edx_stacked_y_csv,
        )
        return pd.DataFrame({"rows_stacked": [rows_stacked], "rows_stacked_y": [rows_stacked_y]})

    step_results.append(_run_step("stacked_edx", _run_stacked))

    step_results.append(
        _run_step(
            "zero_timebin",
            lambda: _build_zero_timebin_summary(
                PIPELINE_PATHS.surf_metrics_csv,
                PIPELINE_PATHS.surf_zero_summary_csv,
                PIPELINE_PATHS.surf_zero_wide_summary_csv,
            ),
        )
    )

    if run_images:
        step_results.append(
            _run_step("images", lambda: _run_image_query(lookback_days))
        )

    files_pruned = 0
    cutoff_iso = datetime.now().isoformat()

    def _run_prune() -> pd.DataFrame:
        nonlocal files_pruned, cutoff_iso
        files_pruned, cutoff_iso = _prune_old_image_files(
            PIPELINE_PATHS.surf_image_dir,
            retention_days=DEFAULT_IMAGE_RETENTION_DAYS,
            dry_run=prune_dry_run,
            manifest_path=PIPELINE_PATHS.surf_image_manifest_csv,
        )
        LOGGER.info(
            "[image_prune] dry_run=%s files_pruned=%s cutoff=%s manifest=%s",
            prune_dry_run,
            files_pruned,
            cutoff_iso,
            PIPELINE_PATHS.surf_image_manifest_csv,
        )
        return pd.DataFrame({"files_pruned": [files_pruned]})

    step_results.append(_run_step("image_prune", _run_prune))

    write_artifact_manifest(
        PIPELINE_PATHS.surf_run_artifact_manifest,
        extra_outputs={
            "surf_coordinates_csv": PIPELINE_PATHS.surf_coordinates_csv,
            "surf_metrics_csv": PIPELINE_PATHS.surf_metrics_csv,
            "surf_edx_csv": PIPELINE_PATHS.surf_edx_csv,
            "surf_edx_stacked_csv": PIPELINE_PATHS.surf_edx_stacked_csv,
            "surf_edx_stacked_y_csv": PIPELINE_PATHS.surf_edx_stacked_y_csv,
            "surf_image_manifest_csv": PIPELINE_PATHS.surf_image_manifest_csv,
            "surf_zero_summary_csv": PIPELINE_PATHS.surf_zero_summary_csv,
            "surf_zero_wide_summary_csv": PIPELINE_PATHS.surf_zero_wide_summary_csv,
            "surf_image_dir": PIPELINE_PATHS.surf_image_dir,
            "steps_completed": ", ".join(step.name for step in step_results),
        },
    )

    summary = RunSummary(
        mode=mode,
        lookback_days=int(lookback_days),
        run_images=bool(run_images),
        rows_coordinates=_row_count(PIPELINE_PATHS.surf_coordinates_csv),
        rows_metrics=_row_count(PIPELINE_PATHS.surf_metrics_csv),
        rows_stacked=rows_stacked,
        rows_stacked_y=rows_stacked_y,
        files_pruned=files_pruned,
        prune_cutoff_utc=cutoff_iso,
    )

    summary_path = PIPELINE_PATHS.artifacts_dir / "surf_scan_run_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary.__dict__, indent=2), encoding="utf-8")

    for step in step_results:
        LOGGER.info("[%s] duration=%s rows=%s", step.name, step.finished_at - step.started_at, step.rows)

    return summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consolidated SURF scan pipeline (seed/backfill and scheduled incremental)."
    )
    parser.add_argument(
        "--mode",
        choices=["seed", "incremental"],
        default="incremental",
        help="Run mode: seed for initialization/backfill, incremental for scheduled overlap updates.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Override lookback days; defaults are 760 for seed and 7 for incremental.",
    )
    parser.add_argument(
        "--run-images",
        action="store_true",
        help="Run surf-scan EDX image retrieval workflow before retention pruning.",
    )
    parser.add_argument(
        "--prune-dry-run",
        action="store_true",
        help="Report 60-day image retention deletions without deleting files.",
    )
    parser.add_argument(
        "--enable-legacy-nearest-pm-enrichment",
        action="store_true",
        help=(
            "Enable legacy nearest-time PM enrichment during coordinates stage. "
            "Default is disabled for orchestrated production runs; ELWC stage/apply refresh remains active."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.lookback_days is None:
        lookback_days = DEFAULT_SEED_LOOKBACK_DAYS if args.mode == "seed" else DEFAULT_INCREMENTAL_LOOKBACK_DAYS
    else:
        lookback_days = args.lookback_days

    summary = run(
        mode=args.mode,
        lookback_days=lookback_days,
        run_images=args.run_images,
        prune_dry_run=args.prune_dry_run,
        enable_legacy_nearest_pm_enrichment=bool(args.enable_legacy_nearest_pm_enrichment),
    )

    print("\n[surf] Consolidated run summary")
    print(json.dumps(summary.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
