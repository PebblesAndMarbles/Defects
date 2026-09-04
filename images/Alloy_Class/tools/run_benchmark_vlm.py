"""
Stage benchmark image pairs and run the Stage A/B prompt test pipeline on them.

Reads a benchmark pair list CSV (benchmark_id, pair_key, bright_image_path,
dark_image_path, ...), copies images to a run-scoped staging folder, then
delegates to run_stage_ab_prompt_tests.py.

The staging folder image names are preserved so the scoring join works via
bright_image_name stem (pair_key derived by stripping _2/_3 suffix).
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPORTING_DIR = SCRIPT_DIR.parent / "reporting"
STAGE_AB_RUNNER = REPORTING_DIR / "run_stage_ab_prompt_tests.py"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_pairs(pair_list_csv: Path) -> list[dict[str, str]]:
    with pair_list_csv.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _row_path(row: dict[str, str], primary: str, fallback: str) -> Path:
    value = (row.get(primary) or row.get(fallback) or "").strip()
    return Path(value)


def stage_images(rows: list[dict[str, str]], staging_dir: Path) -> tuple[int, list[str]]:
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged = 0
    missing: list[str] = []
    for row in rows:
        for col, fallback in (("bright_image_path", "bright_path"), ("dark_image_path", "dark_path")):
            src = _row_path(row, col, fallback)
            if not src.exists():
                missing.append(f"{row.get('benchmark_id','?')} {col}={src}")
                continue
            dst = staging_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
            staged += 1
    return staged, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage A/B VLM on benchmark pair list")
    parser.add_argument("--pair-list-csv", required=True, help="benchmark_pairs_*.csv")
    parser.add_argument("--config", required=True, help="Stage A/B config JSON (e.g. stage_ab_prompt_tests_substrate_tier1_v1.json)")
    parser.add_argument("--output-folder", required=True, help="Root output folder for this run")
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--run-id", default=f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    parser.add_argument("--raw-image-mode", action="store_true")
    parser.add_argument("--raw-strict", action="store_true")
    parser.add_argument("--raw-stage-a-only", action="store_true")
    parser.add_argument("--stage-a-brightfield-only", action="store_true")
    parser.add_argument("--stage-b-multi-image", action="store_true")
    parser.add_argument("--stage-b-describe-then-classify", action="store_true")
    args = parser.parse_args()

    pair_list = Path(args.pair_list_csv)
    output_root = Path(args.output_folder) / args.run_id
    staging_dir = output_root / "inputs"
    results_dir = output_root / "stage_ab_results"

    rows = _load_pairs(pair_list)
    print(f"pair_list_rows={len(rows)}")

    staged, missing = stage_images(rows, staging_dir)
    print(f"staged_images={staged}")
    if missing:
        print(f"MISSING ({len(missing)}):")
        for m in missing:
            print(f"  {m}")

    # Write a benchmark_id lookup alongside results for scorer join
    lookup_path = output_root / "benchmark_id_lookup.csv"
    with lookup_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["benchmark_id", "pair_key_benchmark", "bright_stem", "source_pool", "adjudicated_coarse_class"])
        for row in rows:
            bname = _row_path(row, "bright_image_path", "bright_path").name
            bright_stem = Path(bname).stem  # includes _2 suffix
            w.writerow([
                row.get("benchmark_id", ""),
                row.get("pair_key", ""),
                bright_stem,
                row.get("source_pool", ""),
                row.get("adjudicated_coarse_class", ""),
            ])
    print(f"lookup_written={lookup_path}")

    cmd = [
        args.python_exe,
        str(STAGE_AB_RUNNER),
        "--config", args.config,
        "--input-folder", str(staging_dir),
        "--output-folder", str(results_dir),
        "--run-root-folder", str(output_root),
        "--run-id", args.run_id,
    ]
    if args.raw_image_mode:
        cmd.append("--raw-image-mode")
    if args.raw_strict:
        cmd.append("--raw-strict")
    if args.raw_stage_a_only:
        cmd.append("--raw-stage-a-only")
    if args.stage_a_brightfield_only:
        cmd.append("--stage-a-brightfield-only")
    if args.stage_b_multi_image:
        cmd.append("--stage-b-multi-image")
    if args.stage_b_describe_then_classify:
        cmd.append("--stage-b-describe-then-classify")

    print(f"run_id={args.run_id}")
    print(f"staging_dir={staging_dir}")
    print(f"results_dir={results_dir}")
    print("launching stage_ab runner ...")
    subprocess.run(cmd, check=True)

    manifest = {
        "run_id": args.run_id,
        "run_at_utc": _utc_now(),
        "pair_list_csv": str(pair_list.resolve()),
        "pair_count": len(rows),
        "staged_images": staged,
        "config": args.config,
        "stage_a_brightfield_only": bool(args.stage_a_brightfield_only),
        "stage_b_multi_image": bool(args.stage_b_multi_image),
        "stage_b_describe_then_classify": bool(args.stage_b_describe_then_classify),
        "results_dir": str(results_dir.resolve()),
        "prompt_bundle_path": str((output_root / "prompt_bundle.json").resolve()),
        "prompt_bundle_txt_path": str((output_root / "prompt_bundle.txt").resolve()),
        "lookup_csv": str(lookup_path.resolve()),
    }
    (output_root / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
