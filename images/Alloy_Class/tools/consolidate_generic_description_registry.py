"""Consolidate the generic-description processed registry into one deduped VLM pair
and optionally run the production enrichment step against the consolidated outputs.

The processed registry is provenance only: it tracks which successful probe rows
were already processed, but it does not contain the structured VLM attributes.
This script walks the registry, pulls the winning row for each join_key from the
referenced run files, emits a single consolidated JSONL + manifest CSV pair, and
then feeds that pair into the existing production enrichment flow.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from enrich_production_with_vlm_attributes import (  # type: ignore  # noqa: E402
    DEFAULT_CURRENT_CLASS_CSV,
    DEFAULT_GROUND_TRUTH_CSV,
    DEFAULT_PRODUCTION_CSV,
    DEFAULT_RECLASS_CSV,
    _truth_alignment_state,
)


DEFAULT_REGISTRY_CSV = Path(r"C:\RAW_IMAGES\generic_description_registry\generic_description_processed_registry.csv")
DEFAULT_OUTPUT_ROOT = Path(r"C:\RAW_IMAGES\generic_description_registry\generic_description_consolidated_v9")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
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
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y%m%d_%H%M%S")
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y%m%d_%H%M%S")
    except ValueError:
        return "UNKNOWN"


def _join_key(wafer_key: object, inspection_time: object, defect_id: object) -> str:
    return (
        f"{_normalize_join_value(wafer_key)}_"
        f"{_inspection_time_norm(inspection_time)}_"
        f"{_normalize_join_value(defect_id)}"
    )


def _registry_key(row: dict[str, str]) -> str:
    join_key = str(row.get("join_key") or "").strip()
    if join_key:
        return join_key
    return _join_key(row.get("wafer_key"), row.get("inspection_time"), row.get("defect_id"))


def _load_registry_rows(path: Path, prompt_version: str | None = None) -> list[dict[str, str]]:
    rows = _load_csv_rows(path)
    selected: dict[str, dict[str, str]] = {}
    for row in rows:
        if str(row.get("status") or "").strip().lower() != "ok":
            continue
        if prompt_version and str(row.get("prompt_version") or "").strip() != prompt_version:
            continue
        key = _registry_key(row)
        if not key:
            continue
        existing = selected.get(key)
        if existing is None or str(row.get("processed_at_utc") or "") >= str(existing.get("processed_at_utc") or ""):
            selected[key] = row
    return sorted(selected.values(), key=lambda row: (str(row.get("processed_at_utc") or ""), _registry_key(row)))


def _load_source_lookup(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    manifest_lookup: dict[str, dict[str, str]] = {}
    jsonl_lookup: dict[str, dict[str, Any]] = {}

    manifest_path = path
    if manifest_path.exists():
        for row in _load_csv_rows(manifest_path):
            key = _join_key(row.get("wafer_key"), row.get("inspection_time"), row.get("defect_id"))
            if key:
                manifest_lookup[key] = row

    jsonl_path = path.with_suffix(".jsonl")
    if jsonl_path.exists():
        for row in _load_jsonl_rows(jsonl_path):
            key = _join_key(row.get("wafer_key"), row.get("inspection_time"), row.get("defect_id"))
            if key:
                jsonl_lookup[key] = row

    return manifest_lookup, jsonl_lookup


def _collect_source_pair_paths(registry_rows: list[dict[str, str]]) -> dict[tuple[Path, Path], list[dict[str, str]]]:
    grouped: dict[tuple[Path, Path], list[dict[str, str]]] = defaultdict(list)
    for row in registry_rows:
        jsonl_path = Path(str(row.get("run_jsonl_path") or "").strip())
        manifest_path_text = str(row.get("run_manifest_csv_path") or "").strip()
        manifest_path = Path(manifest_path_text) if manifest_path_text else jsonl_path.with_name(f"{jsonl_path.stem}_manifest.csv")
        grouped[(jsonl_path, manifest_path)].append(row)
    return grouped


def _build_consolidated_outputs(registry_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str], list[Path]]:
    grouped_sources = _collect_source_pair_paths(registry_rows)
    source_cache: dict[Path, tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]] = {}

    consolidated_jsonl_rows: list[dict[str, Any]] = []
    consolidated_manifest_rows: list[dict[str, str]] = []
    manifest_fieldnames: list[str] = []
    manifest_field_seen: set[str] = set()
    source_paths: list[Path] = []

    for (jsonl_path, manifest_path), rows in grouped_sources.items():
        source_paths.extend([jsonl_path, manifest_path])
        if jsonl_path not in source_cache:
            manifest_lookup: dict[str, dict[str, str]] = {}
            jsonl_lookup: dict[str, dict[str, Any]] = {}
            if manifest_path.exists():
                for manifest_row in _load_csv_rows(manifest_path):
                    key = _join_key(manifest_row.get("wafer_key"), manifest_row.get("inspection_time"), manifest_row.get("defect_id"))
                    if key:
                        manifest_lookup[key] = manifest_row
                        for field in manifest_row.keys():
                            if field not in manifest_field_seen:
                                manifest_field_seen.add(field)
                                manifest_fieldnames.append(field)
            if jsonl_path.exists():
                for jsonl_row in _load_jsonl_rows(jsonl_path):
                    key = _join_key(jsonl_row.get("wafer_key"), jsonl_row.get("inspection_time"), jsonl_row.get("defect_id"))
                    if key:
                        jsonl_lookup[key] = jsonl_row
            source_cache[jsonl_path] = (manifest_lookup, jsonl_lookup)

        manifest_lookup, jsonl_lookup = source_cache[jsonl_path]
        for registry_row in rows:
            key = _registry_key(registry_row)
            manifest_row = manifest_lookup.get(key)
            jsonl_row = jsonl_lookup.get(key)
            if manifest_row is None and jsonl_row is None:
                raise KeyError(f"Missing source row for join_key={key} in {jsonl_path}")
            if manifest_row is not None:
                consolidated_manifest_rows.append(manifest_row)
            if jsonl_row is not None:
                consolidated_jsonl_rows.append(jsonl_row)

    consolidated_jsonl_rows = sorted(
        consolidated_jsonl_rows,
        key=lambda row: (
            str(row.get("timestamp_utc") or ""),
            _join_key(row.get("wafer_key"), row.get("inspection_time"), row.get("defect_id")),
        ),
    )
    consolidated_manifest_rows = sorted(
        consolidated_manifest_rows,
        key=lambda row: (
            str(row.get("vlm_timestamp_utc") or ""),
            _join_key(row.get("wafer_key"), row.get("inspection_time"), row.get("defect_id")),
        ),
    )
    return consolidated_jsonl_rows, consolidated_manifest_rows, manifest_fieldnames, sorted(set(source_paths))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_manifest_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    ordered_fieldnames: list[str] = []
    for field in fieldnames:
        if field not in seen:
            seen.add(field)
            ordered_fieldnames.append(field)
    for row in rows:
        for field in row.keys():
            if field not in seen:
                seen.add(field)
                ordered_fieldnames.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ordered_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _load_ground_truth_lookup(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    rows = [row for row in _load_csv_rows(path) if str(row.get("tranche_id") or "")]
    rows.sort(key=lambda row: (str(row.get("pair_key") or ""), str(row.get("submitted_at_utc") or "")))

    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        pair_key = str(row.get("pair_key") or "").strip()
        if not pair_key:
            continue
        existing = deduped.get(pair_key)
        if existing is None or str(row.get("submitted_at_utc") or "") >= str(existing.get("submitted_at_utc") or ""):
            deduped[pair_key] = row
    return deduped


def _load_lookup_by_join_key(path: Path, key_fields: tuple[str, str, str]) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    lookup: dict[str, dict[str, str]] = {}
    for row in _load_csv_rows(path):
        key = _join_key(row.get(key_fields[0]), row.get(key_fields[1]), row.get(key_fields[2]))
        if key:
            lookup[key] = row
    return lookup


def _load_current_class_lookup(path: Path) -> dict[str, dict[str, str]]:
    return _load_lookup_by_join_key(path, ("WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"))


def _load_reclass_lookup(path: Path) -> dict[str, dict[str, str]]:
    return _load_lookup_by_join_key(path, ("WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"))


def _truth_label_by_join_key(registry_rows: list[dict[str, str]], ground_truth_lookup: dict[str, dict[str, str]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for row in registry_rows:
        join_key = _registry_key(row)
        gt = ground_truth_lookup.get(join_key)
        if gt:
            labels[join_key] = str(gt.get("label") or "")
    return labels


def _flatten_model_call(parsed: dict[str, Any]) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for key, value in parsed.items():
        flattened[key] = "" if value is None else str(value)
    return flattened


def _collect_vlm_fields(vlm_row: dict[str, str], vlm_jsonl_row: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in vlm_row.items():
        out[key] = "" if value is None else str(value)

    if vlm_jsonl_row:
        model_call = vlm_jsonl_row.get("model_call") or {}
        if isinstance(model_call, dict):
            parsed = model_call.get("parsed") or {}
            if isinstance(parsed, dict):
                for key, value in _flatten_model_call(parsed).items():
                    if not out.get(key):
                        out[key] = value
    return out


def _summary_bucket_key(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "UNKNOWN"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return "UNKNOWN"


def _build_registry_enriched_rows(
    registry_rows: list[dict[str, str]],
    manifest_lookup: dict[str, dict[str, str]],
    jsonl_lookup: dict[str, dict[str, Any]],
    ground_truth_lookup: dict[str, dict[str, str]],
    current_class_lookup: dict[str, dict[str, str]],
    reclass_lookup: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], int, int]:
    enriched_rows: list[dict[str, str]] = []
    summary_rows_by_day: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    attr_counter: Counter[str] = Counter()
    attr_interest_counter: Counter[str] = Counter()
    attr_interest_fields = {
        "coarse_shape",
        "shape_jagged",
        "shape_concave",
        "shape_flake",
        "defect_count",
        "coarse_texture",
        "texture_scraggly",
        "location_relative",
    }
    missing_vlm_rows = 0
    truth_beep_count = 0
    adopted_extra_columns: set[str] = set()

    for row in registry_rows:
        join_key = _registry_key(row)
        vlm_row = manifest_lookup.get(join_key, {})
        vlm_jsonl_row = jsonl_lookup.get(join_key)
        truth_row = ground_truth_lookup.get(join_key, {})
        current_class_row = current_class_lookup.get(join_key, {})
        reclass_row = reclass_lookup.get(join_key, {})

        enriched: dict[str, str] = {str(key): "" if value is None else str(value) for key, value in row.items()}
        enriched["enrichment_join_key"] = join_key
        enriched["enrichment_status"] = "joined" if (vlm_row or vlm_jsonl_row) else "missing_vlm"
        enriched["truth_label"] = str(truth_row.get("label") or "")
        enriched["truth_reviewer"] = str(truth_row.get("reviewer") or "")
        enriched["truth_submitted_at_utc"] = str(truth_row.get("submitted_at_utc") or "")
        enriched["truth_tranche_id"] = str(truth_row.get("tranche_id") or "")
        enriched["truth_is_beep"] = "true" if str(truth_row.get("label") or "").upper() == "BEEP" else "false"
        enriched["current_class"] = str(current_class_row.get("CLASS") or current_class_row.get("class") or "")
        enriched["current_reclass"] = str(reclass_row.get("CLASS_new") or reclass_row.get("class_new") or "")
        enriched["truth_alignment_state"] = _truth_alignment_state(enriched["truth_label"], enriched["current_class"], enriched["current_reclass"])

        vlm_fields = _collect_vlm_fields(vlm_row, vlm_jsonl_row)
        if not vlm_fields:
            missing_vlm_rows += 1
        for key, value in vlm_fields.items():
            if key in enriched:
                if not str(enriched.get(key) or "").strip():
                    enriched[key] = value
            else:
                enriched[key] = value
                adopted_extra_columns.add(key)

        if enriched["truth_is_beep"] == "true":
            truth_beep_count += 1

        summary_rows_by_day[_summary_bucket_key(enriched.get("INSPECTION_TIME") or enriched.get("inspection_time") or row.get("inspection_time"))].append(enriched)

        for key, value in vlm_fields.items():
            if key == "description" or value == "":
                continue
            attr_counter[key] += 1
            if key in attr_interest_fields:
                attr_interest_counter[key] += 1

        enriched_rows.append(enriched)

    summary_rows: list[dict[str, str]] = []
    for bucket_key, rows in sorted(summary_rows_by_day.items()):
        total = len(rows)
        beep_excluded = sum(1 for row in rows if row.get("truth_is_beep") == "true")
        true_particle = total - beep_excluded
        rate = (true_particle / total) if total else 0.0
        summary_rows.append(
            {
                "bucket": bucket_key,
                "total_rows": str(total),
                "truth_beep_rows": str(beep_excluded),
                "true_particle_rows": str(true_particle),
                "true_particle_rate": f"{rate:.6f}",
            }
        )

    output_columns = list(
        dict.fromkeys(
            [
                *registry_rows[0].keys(),
                "enrichment_join_key",
                "enrichment_status",
                "truth_label",
                "truth_reviewer",
                "truth_submitted_at_utc",
                "truth_tranche_id",
                "truth_is_beep",
                "truth_alignment_state",
                "current_class",
                "current_reclass",
                *sorted(adopted_extra_columns),
            ]
        )
    )

    return enriched_rows, summary_rows, output_columns, missing_vlm_rows, truth_beep_count


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consolidate the generic-description processed registry and build the corresponding enriched CSV.")
    parser.add_argument("--registry-csv", default=str(DEFAULT_REGISTRY_CSV), help="Processed-registry CSV with join_key + source file paths.")
    parser.add_argument("--prompt-version", default="generic_description_v9", help="Optional prompt-version filter to keep the consolidation scoped to one probe lineage.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Directory for consolidated and enriched outputs.")
    parser.add_argument("--production-csv", default=str(DEFAULT_PRODUCTION_CSV), help="Production CSV to enrich with the consolidated VLM attributes.")
    parser.add_argument("--ground-truth-csv", default=str(DEFAULT_GROUND_TRUTH_CSV), help="Ground-truth CSV used to exclude BEEP rows in the enrichment summary.")
    parser.add_argument("--current-class-csv", default=str(DEFAULT_CURRENT_CLASS_CSV), help="Production coordinate CSV used for current_class lookup.")
    parser.add_argument("--reclass-csv", default=str(DEFAULT_RECLASS_CSV), help="Reclass log CSV used for current_reclass lookup.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    registry_csv = Path(args.registry_csv)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    registry_rows = _load_registry_rows(registry_csv, prompt_version=args.prompt_version)
    if not registry_rows:
        raise RuntimeError(f"No successful registry rows found in {registry_csv}")

    consolidated_jsonl_rows, consolidated_manifest_rows, manifest_fieldnames, source_paths = _build_consolidated_outputs(registry_rows)
    ground_truth_lookup = _load_ground_truth_lookup(Path(args.ground_truth_csv))
    current_class_lookup = _load_current_class_lookup(Path(args.current_class_csv))
    reclass_lookup = _load_reclass_lookup(Path(args.reclass_csv))

    manifest_lookup = {}
    for row in consolidated_manifest_rows:
        key = _join_key(row.get("wafer_key"), row.get("inspection_time"), row.get("defect_id"))
        if key:
            manifest_lookup[key] = row

    jsonl_lookup = {}
    for row in consolidated_jsonl_rows:
        key = _join_key(row.get("wafer_key"), row.get("inspection_time"), row.get("defect_id"))
        if key:
            jsonl_lookup[key] = row

    enriched_rows, summary_rows, output_columns, missing_vlm_rows, truth_beep_count = _build_registry_enriched_rows(
        registry_rows,
        manifest_lookup,
        jsonl_lookup,
        ground_truth_lookup,
        current_class_lookup,
        reclass_lookup,
    )

    consolidated_jsonl = output_root / f"{args.prompt_version}_consolidated.jsonl"
    consolidated_manifest = output_root / f"{args.prompt_version}_consolidated_manifest.csv"
    _write_jsonl(consolidated_jsonl, consolidated_jsonl_rows)
    _write_manifest_csv(consolidated_manifest, consolidated_manifest_rows, manifest_fieldnames)

    enriched_output_dir = output_root / f"{args.prompt_version}_enriched"
    enriched_output_dir.mkdir(parents=True, exist_ok=True)
    enriched_csv = enriched_output_dir / "production_with_vlm_attributes.csv"
    summary_csv = enriched_output_dir / "production_with_vlm_attributes_summary.csv"
    summary_json = enriched_output_dir / "production_with_vlm_attributes_summary.json"

    with enriched_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched_rows)

    with summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["bucket", "total_rows", "truth_beep_rows", "true_particle_rows", "true_particle_rate"])
        writer.writeheader()
        writer.writerows(summary_rows)

    summary = {
        "source_production_csv": str(Path(args.production_csv)),
        "source_vlm_manifest_csv": str(consolidated_manifest),
        "source_vlm_jsonl": str(consolidated_jsonl),
        "source_ground_truth_csv": str(Path(args.ground_truth_csv)),
        "source_current_class_csv": str(Path(args.current_class_csv)),
        "source_reclass_csv": str(Path(args.reclass_csv)),
        "join_mode": "registry-preserving",
        "output_enriched_csv": str(enriched_csv),
        "output_summary_csv": str(summary_csv),
        "total_rows": len(enriched_rows),
        "joined_rows": sum(1 for row in enriched_rows if row.get("enrichment_status") == "joined"),
        "missing_vlm_rows": missing_vlm_rows,
        "filtered_out_rows": 0,
        "truth_beep_rows": truth_beep_count,
        "truth_non_beep_rows": len(enriched_rows) - truth_beep_count,
        "attr_presence_counts": {},
        "attr_interest_presence_counts": {},
        "by_bucket": summary_rows,
    }

    summary_path = output_root / f"{args.prompt_version}_consolidation_summary.json"
    summary_payload = {
        "registry_csv": str(registry_csv),
        "prompt_version": args.prompt_version,
        "registry_rows": len(registry_rows),
        "consolidated_jsonl_rows": len(consolidated_jsonl_rows),
        "consolidated_manifest_rows": len(consolidated_manifest_rows),
        "source_paths": [str(path) for path in source_paths],
        "consolidated_jsonl": str(consolidated_jsonl),
        "consolidated_manifest_csv": str(consolidated_manifest),
        "enriched_output_dir": str(enriched_output_dir),
        "enriched_csv": str(enriched_csv),
        "enrichment_summary_csv": str(summary_csv),
        "enrichment_summary_json": str(summary_json),
        "enrichment_summary": summary,
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())