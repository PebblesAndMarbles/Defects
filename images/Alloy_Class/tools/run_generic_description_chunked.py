"""Orchestrate chunked generic-description probe runs with cumulative tranche outputs.

This wrapper keeps the HTML review artifact per chunk, while accumulating the
JSONL and manifest CSV outputs into stable tranche files inside a registry
workspace. It also seeds the processed-registry CSV from a prior successful
JSONL so the next tranche starts after already-processed defects.
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
from typing import Any

from probe_generic_description import _load_source_manifest, _select_local_cache_pairs  # type: ignore  # noqa: E402


ALLOY_CLASS_DIR = Path(__file__).resolve().parents[1]
BE_ROOT = ALLOY_CLASS_DIR.parents[1]

DEFAULT_PROMPT_CONFIG = ALLOY_CLASS_DIR / "config" / "generic_description_prompt_v9.json"
DEFAULT_PROBE_SCRIPT = ALLOY_CLASS_DIR / "tools" / "probe_generic_description.py"
DEFAULT_REGISTRY_ROOT = Path(r"C:\RAW_IMAGES\generic_description_registry")
DEFAULT_SOURCE_MANIFEST = Path(r"C:\RAW_IMAGES\manifest.csv")
DEFAULT_PROCESSED_REGISTRY = DEFAULT_REGISTRY_ROOT / "generic_description_processed_registry.csv"
DEFAULT_SOURCE_MANIFEST_SNAPSHOT = DEFAULT_REGISTRY_ROOT / "source_manifest_snapshot.csv"
DEFAULT_SEED_JSONL = DEFAULT_REGISTRY_ROOT / "bootstrap_seed.jsonl"
DEFAULT_SEED_MANIFEST = DEFAULT_REGISTRY_ROOT / "bootstrap_seed_manifest.csv"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text:
            rows.append(json.loads(text))
    return rows


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows.extend(reader)
    return rows


def _normalize_join_value(value: object) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _inspection_time_norm(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "UNKNOWN"
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return "UNKNOWN"
    return dt.strftime("%Y%m%d_%H%M%S")


def _join_key(wafer_key: object, inspection_time: object, defect_id: object) -> str:
    return (
        f"{_normalize_join_value(wafer_key)}_"
        f"{_inspection_time_norm(inspection_time)}_"
        f"{_normalize_join_value(defect_id)}"
    )


def _seed_registry_from_jsonl(registry_csv: Path, jsonl_path: Path, prompt_version: str) -> int:
    rows = _load_jsonl_rows(jsonl_path)
    successful = [row for row in rows if str(row.get("status") or "").strip().lower() == "ok"]
    if not successful:
        return 0

    registry_csv.parent.mkdir(parents=True, exist_ok=True)
    existing_keys: set[str] = set()
    if registry_csv.exists():
        with registry_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                key = str(row.get("join_key") or "").strip()
                if key:
                    existing_keys.add(key)

    fieldnames = [
        "join_key",
        "wafer_key",
        "inspection_time",
        "defect_id",
        "prompt_version",
        "status",
        "run_jsonl_path",
        "run_manifest_csv_path",
        "processed_at_utc",
    ]
    write_header = not registry_csv.exists()
    appended = 0
    with registry_csv.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for row in successful:
            join_key = _join_key(row.get("wafer_key"), row.get("inspection_time"), row.get("defect_id"))
            if join_key in existing_keys:
                continue
            writer.writerow(
                {
                    "join_key": join_key,
                    "wafer_key": str(row.get("wafer_key") or ""),
                    "inspection_time": str(row.get("inspection_time") or ""),
                    "defect_id": str(row.get("defect_id") or ""),
                    "prompt_version": prompt_version,
                    "status": "ok",
                    "run_jsonl_path": str(jsonl_path),
                    "run_manifest_csv_path": "",
                    "processed_at_utc": str(row.get("timestamp_utc") or ""),
                }
            )
            existing_keys.add(join_key)
            appended += 1
    return appended


def _append_jsonl(source: Path, dest: Path) -> int:
    if not source.exists():
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with source.open("r", encoding="utf-8") as src, dest.open("a", encoding="utf-8") as out:
        for line in src:
            text = line.rstrip("\n")
            if not text.strip():
                continue
            out.write(text + "\n")
            count += 1
    return count


def _append_csv_rows(source: Path, dest: Path) -> int:
    if not source.exists():
        return 0
    with source.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        rows = list(reader)
    if not rows:
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_header = not dest.exists()
    with dest.open("a", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _copy_seed_artifacts(seed_jsonl: Path, seed_manifest: Path, registry_root: Path) -> tuple[Path, Path]:
    registry_root.mkdir(parents=True, exist_ok=True)
    seed_jsonl_copy = registry_root / DEFAULT_SEED_JSONL.name
    seed_manifest_copy = registry_root / DEFAULT_SEED_MANIFEST.name
    shutil.copy2(seed_jsonl, seed_jsonl_copy)
    shutil.copy2(seed_manifest, seed_manifest_copy)
    return seed_jsonl_copy, seed_manifest_copy


def _refresh_source_manifest_snapshot(source_manifest: Path, snapshot_manifest: Path) -> Path:
    snapshot_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_manifest, snapshot_manifest)
    return snapshot_manifest


def _select_local_cache_pairs_preview(source_manifest: Path, max_pairs: int, excluded_join_keys: set[str]) -> list[str]:
    """Reuses the real probe's selection function (not a separate reimplementation) so this
    preview stays exclusion- and ordering-consistent with the actual chunk that will run."""
    rows = _select_local_cache_pairs(_load_source_manifest(source_manifest), max_pairs, excluded_join_keys)
    return [_join_key(row.get("wafer_key"), row.get("inspection_time"), row.get("defect_id")) for row in rows]


def _preflight_check(seed_keys: set[str], source_manifest_snapshot: Path, first_chunk_size: int) -> None:
    candidate_keys = _select_local_cache_pairs_preview(source_manifest_snapshot, first_chunk_size, seed_keys)
    overlap = sorted(set(candidate_keys) & seed_keys)
    if overlap:
        sample = ", ".join(overlap[:10])
        raise RuntimeError(
            "Preflight check failed: the first chunk still overlaps already-processed seed keys. "
            f"overlap_count={len(overlap)} sample={sample}"
        )


def _run_probe(
    python_exe: str,
    probe_script: Path,
    prompt_config: Path,
    source_manifest: Path,
    processed_registry_csv: Path,
    max_pairs: int,
    chunk_jsonl: Path,
    chunk_manifest_csv: Path,
    chunk_html: Path,
) -> None:
    cmd = [
        python_exe,
        str(probe_script),
        "--use-local-cache",
        "--max-pairs",
        str(max_pairs),
        "--prompt-config",
        str(prompt_config),
        "--source-manifest-csv",
        str(source_manifest),
        "--processed-registry-csv",
        str(processed_registry_csv),
        "--output-jsonl",
        str(chunk_jsonl),
        "--output-manifest-csv",
        str(chunk_manifest_csv),
        "--output-html",
        str(chunk_html),
    ]
    subprocess.run(cmd, check=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run chunked generic-description tranches with cumulative JSONL/CSV outputs and per-run HTML.")
    parser.add_argument("--python-exe", default=r"c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe")
    parser.add_argument("--probe-script", default=str(DEFAULT_PROBE_SCRIPT))
    parser.add_argument("--prompt-config", default=str(DEFAULT_PROMPT_CONFIG))
    parser.add_argument("--source-manifest-csv", default=str(DEFAULT_SOURCE_MANIFEST))
    parser.add_argument("--processed-registry-csv", default=str(DEFAULT_PROCESSED_REGISTRY))
    parser.add_argument("--registry-root", default=str(DEFAULT_REGISTRY_ROOT), help="Folder that owns the accumulating tranche files, registry CSV, and manifest snapshot.")
    parser.add_argument("--seed-jsonl", default="", help="Prior successful JSONL to seed the processed registry before chunked runs begin.")
    parser.add_argument("--seed-manifest-csv", default="", help="Optional explicit CSV copy of the seed tranche; defaults to the sibling _manifest.csv beside --seed-jsonl.")
    parser.add_argument("--tranche-size", type=int, default=400, help="Number of new cases to collect into the cumulative tranche set.")
    parser.add_argument("--chunk-size", type=int, default=400, help="Per-run max-pairs passed to the canonical probe.")
    parser.add_argument("--preflight-check", "--pfc", action="store_true", help="Fail fast if the first selected chunk overlaps the seeded processed registry.")
    parser.add_argument("--run-prefix", default="generic_description_next")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    prompt_cfg = json.loads(Path(args.prompt_config).read_text(encoding="utf-8-sig"))
    prompt_version = str(prompt_cfg.get("prompt_version", "generic_description"))
    registry_root = Path(args.registry_root)
    registry_root.mkdir(parents=True, exist_ok=True)

    source_manifest = Path(args.source_manifest_csv)
    source_manifest_snapshot = _refresh_source_manifest_snapshot(
        source_manifest,
        DEFAULT_SOURCE_MANIFEST_SNAPSHOT if registry_root == DEFAULT_REGISTRY_ROOT else registry_root / "source_manifest_snapshot.csv",
    )

    processed_registry_csv = Path(args.processed_registry_csv)
    if processed_registry_csv == DEFAULT_PROCESSED_REGISTRY:
        processed_registry_csv = registry_root / processed_registry_csv.name
    elif not processed_registry_csv.is_absolute():
        processed_registry_csv = registry_root / processed_registry_csv
    processed_registry_csv.parent.mkdir(parents=True, exist_ok=True)

    cumulative_jsonl = registry_root / f"{args.run_prefix}_{prompt_version}_cumulative.jsonl"
    cumulative_manifest = registry_root / f"{args.run_prefix}_{prompt_version}_cumulative_manifest.csv"
    run_root = registry_root / f"{args.run_prefix}_{prompt_version}_{_utc_stamp()}"
    run_root.mkdir(parents=True, exist_ok=True)

    seed_jsonl_copy = None
    seed_manifest_copy = None
    seeded = 0
    if args.seed_jsonl:
        seed_jsonl = Path(args.seed_jsonl)
        seed_manifest = Path(args.seed_manifest_csv) if args.seed_manifest_csv else seed_jsonl.with_name(f"{seed_jsonl.stem}_manifest.csv")
        seed_jsonl_copy, seed_manifest_copy = _copy_seed_artifacts(seed_jsonl, seed_manifest, registry_root)
        seeded = _seed_registry_from_jsonl(processed_registry_csv, seed_jsonl_copy, prompt_version)

    seed_keys: set[str] = set()
    if processed_registry_csv.exists():
        for row in _load_csv_rows(processed_registry_csv):
            if str(row.get("status") or "").strip().lower() == "ok":
                key = str(row.get("join_key") or "").strip()
                if key:
                    seed_keys.add(key)

    if args.preflight_check and seed_keys:
        _preflight_check(seed_keys, source_manifest_snapshot, min(args.chunk_size, args.tranche_size))

    collected = 0
    chunk_index = 0
    while collected < args.tranche_size:
        chunk_index += 1
        this_chunk_size = min(args.chunk_size, args.tranche_size - collected)
        chunk_dir = run_root / f"chunk_{chunk_index:03d}"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_jsonl = chunk_dir / f"{args.run_prefix}_{prompt_version}_chunk_{chunk_index:03d}.jsonl"
        chunk_manifest = chunk_dir / f"{args.run_prefix}_{prompt_version}_chunk_{chunk_index:03d}_manifest.csv"
        chunk_html = chunk_dir / f"{args.run_prefix}_{prompt_version}_chunk_{chunk_index:03d}_review.html"

        _run_probe(
            python_exe=str(args.python_exe),
            probe_script=Path(args.probe_script),
            prompt_config=Path(args.prompt_config),
            source_manifest=source_manifest_snapshot,
            processed_registry_csv=processed_registry_csv,
            max_pairs=this_chunk_size,
            chunk_jsonl=chunk_jsonl,
            chunk_manifest_csv=chunk_manifest,
            chunk_html=chunk_html,
        )

        new_rows = _append_jsonl(chunk_jsonl, cumulative_jsonl)
        _append_csv_rows(chunk_manifest, cumulative_manifest)

        if new_rows == 0:
            break
        collected += new_rows

    summary = {
        "prompt_version": prompt_version,
        "seeded_rows": seeded,
        "seed_jsonl_copy": str(seed_jsonl_copy) if seed_jsonl_copy else "",
        "seed_manifest_copy": str(seed_manifest_copy) if seed_manifest_copy else "",
        "tranche_size_requested": args.tranche_size,
        "chunk_size": args.chunk_size,
        "collected_rows": collected,
        "cumulative_jsonl": str(cumulative_jsonl),
        "cumulative_manifest_csv": str(cumulative_manifest),
        "processed_registry_csv": str(processed_registry_csv),
        "source_manifest_snapshot": str(source_manifest_snapshot),
        "run_root": str(run_root),
    }
    summary_path = run_root / "orchestration_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())