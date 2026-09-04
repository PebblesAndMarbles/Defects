"""
Orchestrate a transient-raw Stage run from existing burned library images.

Workflow:
1) Select BF/DF pairs from the existing image manifest (IMAGE_ID 2 and 3).
2) Copy burned source images into a run-scoped output input folder.
3) Run classify_phase1_batch.py in raw-image mode (download raw -> infer -> delete temp).
4) Optionally run captioning and build a combined HTML report.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path


DEFAULT_MANIFEST = (
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson"
    r"\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv"
)


def _load_manifest_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def _norm_key(row: dict[str, str]) -> tuple[str, str, str]:
    wafer = str((row.get("WAFER_KEY") or row.get("wafer_key") or "").strip()).replace(".0", "")
    insp = str((row.get("INSPECTION_TIME") or row.get("inspection_time") or "").strip())
    defect = str((row.get("DEFECT_ID") or row.get("defect_id") or "").strip()).replace(".0", "")
    return wafer, insp, defect


def _row_class(row: dict[str, str]) -> str:
    value = (row.get("CLASS") or row.get("class") or row.get("target_label") or "").strip()
    return value.upper()


def _row_source_path(row: dict[str, str]) -> Path:
    value = (
        row.get("LOCAL_IMAGE_FILE")
        or row.get("local_path")
        or row.get("image_path")
        or row.get("source_path")
        or row.get("source_filespec")
        or ""
    ).strip()
    return Path(value)


def _to_image_id(row: dict[str, str]) -> int | None:
    raw = (row.get("IMAGE_ID") or row.get("image_id") or "").strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _label_from_name(name: str) -> str:
    up = name.upper()
    if "_SMP_" in up:
        return "SMP"
    if "_BEEP_" in up:
        return "BEEP"
    return "UNKNOWN"


def _row_matches_target(row: dict[str, str], target_label: str) -> bool:
    if not target_label:
        return True

    label = target_label.upper()
    row_class = _row_class(row)
    if row_class:
        if label == "SMP":
            return row_class == "SMALL_PARTICLE"
        if label == "BEEP":
            return row_class == "BEEP"

    source_path = _row_source_path(row)
    if source_path.name:
        return _label_from_name(source_path.name) == label
    return False


def _load_pairs_from_csv(pair_list_csv: Path, max_pairs: int, target_label: str) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    with pair_list_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bright_text = (row.get("bright_path") or "").strip()
            dark_text = (row.get("dark_path") or "").strip()
            if not bright_text or not dark_text:
                continue

            bright = Path(bright_text)
            dark = Path(dark_text)
            if not bright.exists() or not bright.is_file():
                continue
            if not dark.exists() or not dark.is_file():
                continue

            if target_label:
                bright_label = _label_from_name(bright.name)
                dark_label = _label_from_name(dark.name)
                if bright_label != target_label.upper() or dark_label != target_label.upper():
                    continue

            pairs.append((bright, dark))
            if max_pairs > 0 and len(pairs) >= max_pairs:
                break
    return pairs


def _load_pairs_from_manifest(manifest_csv: Path, max_pairs: int, target_label: str) -> list[tuple[Path, Path]]:
    return select_pairs(manifest_csv, max_pairs=max_pairs, target_label=target_label)


def select_pairs(manifest_csv: Path, max_pairs: int, target_label: str) -> list[tuple[Path, Path]]:
    grouped: dict[tuple[str, str, str], dict[int, Path]] = {}
    for row in _load_manifest_rows(manifest_csv):
        image_id = _to_image_id(row)
        if image_id not in {2, 3}:
            continue

        local_path = _row_source_path(row)
        if not local_path.name:
            continue
        if not local_path.exists() or not local_path.is_file():
            continue

        if not _row_matches_target(row, target_label):
            continue

        grouped.setdefault(_norm_key(row), {})[image_id] = local_path

    pairs: list[tuple[Path, Path]] = []
    for key in sorted(grouped.keys(), reverse=True):
        images = grouped[key]
        bright = images.get(2)
        dark = images.get(3)
        if bright and dark:
            pairs.append((bright, dark))
        if len(pairs) >= max_pairs:
            break
    return pairs


def _copy_pairs(pairs: list[tuple[Path, Path]], dest_inputs: Path) -> dict[str, int]:
    dest_inputs.mkdir(parents=True, exist_ok=True)
    copied = 0
    for bright, dark in pairs:
        for src in (bright, dark):
            dst = dest_inputs / src.name
            shutil.copy2(src, dst)
            copied += 1
    return {"pairs": len(pairs), "images_copied": copied}


def _run(cmd: list[str]) -> None:
    print(f"running: {' '.join(str(part) for part in cmd)}", flush=True)
    subprocess.run(cmd, check=True)


def _summarize_structured_outputs(folder: Path) -> dict:
    result_jsonl = folder / "phase1_results.jsonl"
    status_jsonl = folder / "phase1_status.jsonl"

    rows = 0
    raw_used = 0
    status_rows = 0
    if result_jsonl.exists():
        for line in result_jsonl.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            rows += 1
            try:
                rec = json.loads(text)
                if int(rec.get("used_transient_raw", 0)) == 1:
                    raw_used += 1
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

    if status_jsonl.exists():
        for line in status_jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                status_rows += 1

    return {
        "result_rows": rows,
        "result_rows_used_transient_raw": raw_used,
        "status_rows": status_rows,
    }


def orchestrate(
    python_exe: str,
    be_root: Path,
    run_id: str,
    max_pairs: int,
    phase1_settings: Path,
    runtime_paths: Path,
    local_work_root: Path,
    output_root: Path,
    target_label: str,
    pair_list_csv: Path | None,
    manifest_source_csv: Path,
    report_image_path_source: str,
    copy_burned_to_run: bool,
    use_source_inputs: bool,
    require_raw: bool,
    run_caption: bool,
    build_html: bool,
    max_images: int,
) -> dict:
    run_root = output_root / run_id
    burned_inputs = run_root / "source_burned_inputs"
    phase1_out = run_root / "phase1_structured"
    captions_out = run_root / "captions"
    html_out_dir = run_root / "html"
    html_out = html_out_dir / "phase1_combined_report.html"
    local_inputs = local_work_root / run_id / "inputs"
    temp_raw = local_work_root / run_id / "raw_temp"
    cfg_dir = run_root / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    html_out_dir.mkdir(parents=True, exist_ok=True)
    local_inputs.mkdir(parents=True, exist_ok=True)
    temp_raw.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    effective_max_pairs = max_pairs
    if max_images > 0:
        effective_max_pairs = max(1, math.ceil(max_images / 2))

    pair_selection_mode = "manifest_scan"
    if pair_list_csv:
        pair_selection_mode = "frozen_pair_list"
        pairs = _load_pairs_from_csv(pair_list_csv, max_pairs=effective_max_pairs, target_label=target_label)
    elif use_source_inputs:
        pair_selection_mode = "local_manifest"
        pairs = _load_pairs_from_manifest(manifest_source_csv, max_pairs=effective_max_pairs, target_label=target_label)
    else:
        pairs = select_pairs(manifest_source_csv, max_pairs=effective_max_pairs, target_label=target_label)
    t_select = time.perf_counter() - t0
    if not pairs:
        raise RuntimeError("No BF/DF pairs found with existing burned source files.")

    print(
        f"selected_pairs={len(pairs)} pair_selection_mode={pair_selection_mode} max_pairs={max_pairs} effective_max_pairs={effective_max_pairs} max_images={max_images}",
        flush=True,
    )

    if use_source_inputs:
        source_dirs = {str(path.parent.resolve()) for pair in pairs for path in pair}
        if len(source_dirs) != 1:
            raise RuntimeError("use_source_inputs requires all selected images to share one source directory")
        input_dir = Path(next(iter(source_dirs)))
    else:
        input_dir = local_inputs

    t1 = time.perf_counter()
    if copy_burned_to_run:
        print(f"copying burned source images into {burned_inputs}", flush=True)
        copy_summary = _copy_pairs(pairs, burned_inputs)
    else:
        copy_summary = {"pairs": len(pairs), "images_copied": 0, "images_copied_burned": 0}
    if use_source_inputs:
        copy_summary["images_copied_local"] = 0
    else:
        print(f"copying local input images into {local_inputs}", flush=True)
        local_copy_summary = _copy_pairs(pairs, local_inputs)
        copy_summary["images_copied_local"] = local_copy_summary.get("images_copied", 0)
    t_copy = time.perf_counter() - t1

    base_settings = json.loads(phase1_settings.read_text(encoding="utf-8-sig"))
    # Use short local paths during inference to avoid Windows max-path issues
    # while retaining burned-source organization under outputs for traceability.
    base_settings["input_folder"] = str(input_dir)
    base_settings["output_folder"] = str(phase1_out)
    base_settings["max_pairs"] = max_pairs
    base_settings["require_bf_df_pairs"] = True
    settings_run = cfg_dir / "phase1_settings_raw_stage.json"
    settings_run.write_text(json.dumps(base_settings, indent=2) + "\n", encoding="utf-8")
    print(f"wrote settings {settings_run}", flush=True)

    t2 = time.perf_counter()
    classify_cmd = [
        python_exe,
        str(be_root / "images" / "Alloy_Class" / "pipelines" / "classify_phase1_batch.py"),
        "--runtime-paths",
        str(runtime_paths),
        "--phase1-settings",
        str(settings_run),
        "--run-id",
        run_id,
        "--max-pairs",
        str(effective_max_pairs),
        "--raw-image-mode",
        "--raw-manifest-csv",
        str(manifest_source_csv),
        "--raw-temp-dir",
        str(temp_raw),
    ]
    if require_raw:
        classify_cmd.append("--raw-strict")
    print("starting phase1 VLM submission", flush=True)
    _run(classify_cmd)
    t_classify = time.perf_counter() - t2

    t_caption = 0.0
    if run_caption:
        t3 = time.perf_counter()
        print("starting caption pass", flush=True)
        caption_cmd = [
            python_exe,
            str(be_root / "images" / "Alloy_Class" / "pipelines" / "caption_phase1_batch.py"),
            "--input-folder",
            str(local_inputs),
            "--output-folder",
            str(captions_out),
            "--run-id",
            f"caption_{run_id}",
        ]
        _run(caption_cmd)
        t_caption = time.perf_counter() - t3

    t_html = 0.0
    if build_html:
        t4 = time.perf_counter()
        print("starting HTML report build", flush=True)
        report_inputs_dir = burned_inputs if copy_burned_to_run else input_dir
        report_cmd = [
            python_exe,
            str(be_root / "images" / "Alloy_Class" / "reporting" / "build_phase1_html_report.py"),
            "--inputs-dir",
            str(report_inputs_dir),
            "--caption-jsonl",
            str(captions_out / "caption_results.jsonl"),
            "--structured-jsonl",
            str(phase1_out / "phase1_results.jsonl"),
            "--output-html",
            str(html_out),
            "--image-path-source",
            report_image_path_source,
        ]
        _run(report_cmd)
        t_html = time.perf_counter() - t4

    total_sec = time.perf_counter() - t0
    structured_diag = _summarize_structured_outputs(phase1_out)

    summary = {
        "run_id": run_id,
        "target_label": target_label,
        "pair_selection_mode": pair_selection_mode,
        "pair_list_csv": str(pair_list_csv) if pair_list_csv else "",
        "report_image_path_source": report_image_path_source,
        "copy_burned_to_run": bool(copy_burned_to_run),
        "use_source_inputs": bool(use_source_inputs),
        "run_root": str(run_root),
        "source_burned_inputs": str(burned_inputs),
        "local_inference_inputs": str(input_dir),
        "local_raw_temp": str(temp_raw),
        "phase1_output": str(phase1_out),
        "captions_output": str(captions_out),
        "html_output": str(html_out),
        "timing_seconds": {
            "select_pairs": round(t_select, 3),
            "copy_inputs": round(t_copy, 3),
            "classify_raw_stage": round(t_classify, 3),
            "caption": round(t_caption, 3),
            "html": round(t_html, 3),
            "total": round(total_sec, 3),
        },
        "timing_per_pair_seconds": round(total_sec / max(1, len(pairs)), 3),
        **structured_diag,
        **copy_summary,
    }
    summary_path = run_root / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run transient-raw Stage workflow on auto-selected BF/DF pairs")
    parser.add_argument("--python-exe", default="python")
    parser.add_argument(
        "--be-root",
        default=r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE",
    )
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--pair-list-csv",
        default="",
        help="Optional frozen pair list CSV with bright_path,dark_path columns. When set, skips manifest-wide selection scan.",
    )
    parser.add_argument("--max-pairs", type=int, default=20)
    parser.add_argument(
        "--max-images",
        type=int,
        default=0,
        help="Limit by total images instead of pairs; the pair workflow rounds up to the needed pair count.",
    )
    parser.add_argument(
        "--target-label",
        default="SMP",
        choices=["SMP", "BEEP", "ALL"],
        help="Select only SMP or BEEP pairs by filename token, or ALL.",
    )
    parser.add_argument(
        "--phase1-settings",
        default=r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\config\phase1_settings.json",
    )
    parser.add_argument(
        "--runtime-paths",
        default=r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\config\runtime_paths.json",
    )
    parser.add_argument(
        "--output-root",
        default=r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\outputs\raw_runs",
        help="Run output root under outputs/ (shorter path avoids Windows path length limits).",
    )
    parser.add_argument(
        "--local-work-root",
        default=r"C:\temp\alloy_raw_stage",
        help="Short local staging root to avoid long path issues during raw download/inference",
    )
    parser.add_argument(
        "--require-raw",
        action="store_true",
        help="Fail rows when transient raw download cannot be used.",
    )
    parser.add_argument("--run-id", default=f"raw_stage_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    parser.add_argument("--skip-caption", action="store_true")
    parser.add_argument("--skip-html", action="store_true")
    parser.add_argument(
        "--no-copy-burned",
        action="store_true",
        help="Do not copy burned/source library images into run output; HTML should use structured path source.",
    )
    parser.add_argument(
        "--report-image-path-source",
        default="structured",
        choices=["inputs", "structured", "auto"],
        help="How HTML resolves image paths for display.",
    )
    parser.add_argument(
        "--use-source-inputs",
        action="store_true",
        help="Use the selected source image directory directly instead of copying the images into a run-local input folder.",
    )
    parser.add_argument(
        "--manifest-source-csv",
        default=DEFAULT_MANIFEST,
        help="Local or UNC image manifest CSV to select from when using source inputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = orchestrate(
        python_exe=args.python_exe,
        be_root=Path(args.be_root),
        run_id=args.run_id,
        max_pairs=args.max_pairs,
        phase1_settings=Path(args.phase1_settings),
        runtime_paths=Path(args.runtime_paths),
        local_work_root=Path(args.local_work_root),
        output_root=Path(args.output_root),
        target_label="" if args.target_label == "ALL" else args.target_label,
        pair_list_csv=Path(args.pair_list_csv) if args.pair_list_csv else None,
        report_image_path_source=args.report_image_path_source,
        copy_burned_to_run=not args.no_copy_burned,
        use_source_inputs=args.use_source_inputs,
        require_raw=args.require_raw,
        run_caption=not args.skip_caption,
        build_html=not args.skip_html,
        max_images=args.max_images,
        manifest_source_csv=Path(args.manifest_source_csv),
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
