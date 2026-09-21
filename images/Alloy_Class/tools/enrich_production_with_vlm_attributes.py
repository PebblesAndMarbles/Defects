"""Adhoc production CSV enrichment with generic-description VLM attributes.

This tool joins a production defect CSV to the canonical generic-description
probe outputs using the normalized `(wafer_key, inspection_time, defect_id)`
key shared with the probe and tranche builders.

Default behavior:
- read the production defect CSV from `outputs/defects/DEFECT_COORDINATES_EXTENDED.csv`
- read the VLM manifest CSV emitted by `probe_generic_description.py`
- optionally join the raw JSONL for diagnostics
- exclude defects labeled BEEP in `outputs/beep_evidence/beep_evidence_ground_truth.csv`
  when computing true-particle summary metrics
- write a row-preserving enriched CSV plus summary JSON/CSV artifacts

The enriched CSV preserves the production row, appends the VLM fields, and adds
explicit join/status columns so missing probe coverage is visible instead of
silently dropped.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ALLOY_CLASS_DIR = Path(__file__).resolve().parents[1]
BE_ROOT = ALLOY_CLASS_DIR.parents[1]

DEFAULT_PRODUCTION_CSV = BE_ROOT / "outputs" / "defects" / "DEFECT_COORDINATES_EXTENDED.csv"
DEFAULT_CURRENT_CLASS_CSV = BE_ROOT / "outputs" / "defects" / "DEFECT_COORDINATES_EXTENDED.csv"
DEFAULT_VLM_MANIFEST_CSV = Path(r"C:\RAW_IMAGES\generic_description_v9_30case_manifest.csv")
DEFAULT_VLM_JSONL = Path(r"C:\RAW_IMAGES\generic_description_v9_30case.jsonl")
DEFAULT_GROUND_TRUTH_CSV = ALLOY_CLASS_DIR / "outputs" / "beep_evidence" / "beep_evidence_ground_truth.csv"
DEFAULT_RECLASS_CSV = BE_ROOT / "BE_QUERY_FILES" / "DEFECT_COORDINATES_RECLASS_LOG.csv"
DEFAULT_OUTPUT_DIR = ALLOY_CLASS_DIR / "outputs" / "production_vlm_enrichment"
DEFAULT_JOIN_MODE = "inner"


def _normalize_join_value(value: object) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _inspection_time_norm(value: object) -> str:
    insp = pd.to_datetime(value, errors="coerce")
    return insp.strftime("%Y%m%d_%H%M%S") if pd.notna(insp) else "UNKNOWN"


def _join_key(wafer_key: object, inspection_time: object, defect_id: object) -> str:
    return (
        f"{_normalize_join_value(wafer_key)}_"
        f"{_inspection_time_norm(inspection_time)}_"
        f"{_normalize_join_value(defect_id)}"
    )


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text:
            rows.append(json.loads(text))
    return rows


def _require_existing_path(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def _load_ground_truth_lookup(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    rows = _load_csv_rows(path)
    rows = [row for row in rows if str(row.get("tranche_id") or "")]
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


def _load_reclass_lookup(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    lookup: dict[str, dict[str, str]] = {}
    for row in _load_csv_rows(path):
        join_key = _join_key(row.get("WAFER_KEY"), row.get("INSPECTION_TIME"), row.get("DEFECT_ID"))
        if not join_key:
            continue
        lookup[join_key] = row
    return lookup


def _load_current_class_lookup(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    lookup: dict[str, dict[str, str]] = {}
    for row in _load_csv_rows(path):
        join_key = _join_key(row.get("WAFER_KEY"), row.get("INSPECTION_TIME"), row.get("DEFECT_ID"))
        if not join_key:
            continue
        lookup[join_key] = row
    return lookup


def _truth_bucket(value: object) -> str:
    """SMALL_PARTICLE is the only positive bucket; everything else (BEEP, ROUNDMOUND_BEEP,
    SIZE_SMALL, MINI, BLOCKED_TRENCH, ILD_HOLE_TEAROUT, ...) buckets as BEEP -- matches the
    ground-truth labeling convention where BEEP is a catch-all for "not a real small particle",
    not a literal factory BEEP classification."""
    text = str(value or "").strip().upper()
    if not text:
        return ""
    return "SMALL_PARTICLE" if text in ("SMALL_PARTICLE", "PARTICLE") else "BEEP"


def _truth_alignment_state(truth_label: object, current_class: object, current_reclass: object) -> str:
    truth_bucket = _truth_bucket(truth_label)
    class_bucket = _truth_bucket(current_class)
    reclass_bucket = _truth_bucket(current_reclass)

    if truth_bucket:
        if class_bucket == truth_bucket:
            return "matched"
        if reclass_bucket:
            return "matched_reclass" if reclass_bucket == truth_bucket else "mismatched_reclass"
        return "mismatched"

    # When the truth label is empty, the row is treated as reclass-evidenced.
    # In that case, compare the current class against the reclass bucket if present,
    # otherwise fall back to the current class as the only available bucket.
    if reclass_bucket:
        return "matched_reclass" if class_bucket == reclass_bucket else "mismatched_reclass"
    return "matched" if class_bucket else "mismatched"


def _ground_truth_join_key_from_row(row: dict[str, Any]) -> str:
    pair_key = str(row.get("pair_key") or "").strip()
    if pair_key:
        return pair_key
    return _join_key(row.get("WAFER_KEY") or row.get("wafer_key"), row.get("INSPECTION_TIME") or row.get("inspection_time"), row.get("DEFECT_ID") or row.get("defect_id"))


def _load_vlm_manifest_lookup(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    lookup: dict[str, dict[str, str]] = {}
    for row in _load_csv_rows(path):
        join_key = _join_key(row.get("wafer_key"), row.get("inspection_time"), row.get("defect_id"))
        if not join_key:
            continue
        lookup[join_key] = row
    return lookup


def _load_vlm_jsonl_lookup(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    lookup: dict[str, dict[str, Any]] = {}
    for row in _load_jsonl_rows(path):
        join_key = _join_key(row.get("wafer_key"), row.get("inspection_time"), row.get("defect_id"))
        if not join_key:
            source_case_id = str(row.get("source_case_id") or "").strip()
            parts = source_case_id.split("|")
            if len(parts) == 3:
                join_key = _join_key(parts[0], parts[1], parts[2])
        if join_key:
            lookup[join_key] = row
    return lookup


def _load_production_rows(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False, dtype=str)
    for uppercase, lowercase in (("WAFER_KEY", "wafer_key"), ("INSPECTION_TIME", "inspection_time"), ("DEFECT_ID", "defect_id")):
        if uppercase not in df.columns and lowercase in df.columns:
            df[uppercase] = df[lowercase]
    if "WAFER_KEY" not in df.columns or "INSPECTION_TIME" not in df.columns or "DEFECT_ID" not in df.columns:
        raise RuntimeError("Production CSV must contain WAFER_KEY, INSPECTION_TIME, and DEFECT_ID columns")
    df["join_key"] = df.apply(lambda row: _join_key(row.get("WAFER_KEY"), row.get("INSPECTION_TIME"), row.get("DEFECT_ID")), axis=1)
    return df


def _truth_label_by_join_key(production_df: pd.DataFrame, ground_truth_lookup: dict[str, dict[str, str]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    if "pair_key" not in production_df.columns:
        return labels

    for row in production_df.to_dict(orient="records"):
        pair_key = str(row.get("pair_key") or "").strip()
        if not pair_key:
            pair_key = _join_key(row.get("WAFER_KEY"), row.get("INSPECTION_TIME"), row.get("DEFECT_ID"))
        gt = ground_truth_lookup.get(pair_key)
        if gt:
            labels[str(row.get("join_key") or pair_key)] = str(gt.get("label") or "")
    return labels


def _flatten_model_call(parsed: dict[str, Any]) -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in parsed.items():
        flat[key] = "" if value is None else str(value)
    return flat


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


def _summary_bucket_key(row: pd.Series) -> str:
    value = str(row.get("INSPECTION_TIME") or "")
    insp = pd.to_datetime(value, errors="coerce")
    return insp.strftime("%Y-%m-%d") if pd.notna(insp) else "UNKNOWN"


def build_enrichment(
    production_csv: Path,
    vlm_manifest_csv: Path,
    output_dir: Path,
    ground_truth_csv: Path,
    current_class_csv: Path,
    reclass_csv: Path,
    vlm_jsonl: Path | None = None,
    join_mode: str = "inner",
) -> tuple[dict[str, Any], Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    for path, label in (
        (production_csv, "production_csv"),
        (vlm_manifest_csv, "vlm_manifest_csv"),
        (ground_truth_csv, "ground_truth_csv"),
        (current_class_csv, "current_class_csv"),
        (reclass_csv, "reclass_csv"),
    ):
        _require_existing_path(path, label)

    production_df = _load_production_rows(production_csv)
    vlm_manifest_lookup = _load_vlm_manifest_lookup(vlm_manifest_csv)
    vlm_jsonl_lookup = _load_vlm_jsonl_lookup(vlm_jsonl) if vlm_jsonl else {}
    ground_truth_lookup = _load_ground_truth_lookup(ground_truth_csv)
    current_class_lookup = _load_current_class_lookup(current_class_csv)
    reclass_lookup = _load_reclass_lookup(reclass_csv)

    joined_rows: list[dict[str, str]] = []
    missing_vlm_rows = 0
    filtered_out_rows = 0
    truth_beep_count = 0
    row_by_day: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
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

    production_rows = production_df.to_dict(orient="records")
    adopted_extra_columns: set[str] = set()
    for row in production_rows:
        join_key = str(row.get("join_key") or "")
        vlm_row = vlm_manifest_lookup.get(join_key, {})
        vlm_jsonl_row = vlm_jsonl_lookup.get(join_key)
        truth_row = ground_truth_lookup.get(_ground_truth_join_key_from_row(row), {})
        current_class_row = current_class_lookup.get(join_key, {})
        reclass_row = reclass_lookup.get(join_key, {})

        has_vlm_payload = bool(vlm_row) or bool(vlm_jsonl_row)
        if join_mode == "inner" and not has_vlm_payload:
            filtered_out_rows += 1
            continue

        enriched: dict[str, str] = {str(key): "" if value is None else str(value) for key, value in row.items()}
        enriched["enrichment_join_key"] = join_key
        enriched["enrichment_status"] = "joined" if has_vlm_payload else "missing_vlm"
        enriched["truth_label"] = str(truth_row.get("label") or "")
        enriched["truth_reviewer"] = str(truth_row.get("reviewer") or "")
        enriched["truth_submitted_at_utc"] = str(truth_row.get("submitted_at_utc") or "")
        enriched["truth_tranche_id"] = str(truth_row.get("tranche_id") or "")
        enriched["truth_is_beep"] = "true" if str(truth_row.get("label") or "").upper() == "BEEP" else "false"
        enriched["current_class"] = str(current_class_row.get("CLASS") or current_class_row.get("class") or row.get("CLASS") or row.get("class") or "")
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

        bucket_key = _summary_bucket_key(pd.Series(row))
        row_by_day[bucket_key].append(enriched)

        for key, value in vlm_fields.items():
            if key == "description" or value == "":
                continue
            attr_counter[key] += 1
            if key in attr_interest_fields:
                attr_interest_counter[key] += 1

        joined_rows.append(enriched)

    output_columns = list(
        dict.fromkeys(
            [
                *production_df.columns.tolist(),
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

    enriched_csv = output_dir / "production_with_vlm_attributes.csv"
    with enriched_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_columns, extrasaction="ignore")
        writer.writeheader()
        for row in joined_rows:
            writer.writerow(row)

    summary_rows: list[dict[str, str]] = []
    for bucket_key, rows in sorted(row_by_day.items()):
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

    summary_csv = output_dir / "production_with_vlm_attributes_summary.csv"
    with summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["bucket", "total_rows", "truth_beep_rows", "true_particle_rows", "true_particle_rate"])
        writer.writeheader()
        writer.writerows(summary_rows)

    summary_json = {
        "source_production_csv": str(production_csv),
        "source_vlm_manifest_csv": str(vlm_manifest_csv),
        "source_vlm_jsonl": str(vlm_jsonl) if vlm_jsonl else "",
        "source_ground_truth_csv": str(ground_truth_csv),
        "source_current_class_csv": str(current_class_csv),
        "source_reclass_csv": str(reclass_csv),
        "join_mode": join_mode,
        "output_enriched_csv": str(enriched_csv),
        "output_summary_csv": str(summary_csv),
        "total_rows": len(joined_rows),
        "joined_rows": sum(1 for row in joined_rows if row.get("enrichment_status") == "joined"),
        "missing_vlm_rows": missing_vlm_rows,
        "filtered_out_rows": filtered_out_rows,
        "truth_beep_rows": truth_beep_count,
        "truth_non_beep_rows": len(joined_rows) - truth_beep_count,
        "attr_presence_counts": dict(sorted(attr_counter.items())),
        "attr_interest_presence_counts": dict(sorted(attr_interest_counter.items())),
        "by_bucket": summary_rows,
    }

    summary_json_path = output_dir / "production_with_vlm_attributes_summary.json"
    summary_json_path.write_text(json.dumps(summary_json, indent=2), encoding="utf-8")
    return summary_json, enriched_csv, summary_csv, summary_json_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich production defect rows with canonical generic-description VLM attributes")
    parser.add_argument("--production-csv", default=str(DEFAULT_PRODUCTION_CSV), help="Production CSV to enrich")
    parser.add_argument("--vlm-manifest-csv", default=str(DEFAULT_VLM_MANIFEST_CSV), help="Flattened VLM manifest CSV from probe_generic_description.py")
    parser.add_argument("--vlm-jsonl", default=str(DEFAULT_VLM_JSONL), help="Optional raw VLM JSONL for extra provenance fields")
    parser.add_argument("--ground-truth-csv", default=str(DEFAULT_GROUND_TRUTH_CSV), help="beep_evidence_ground_truth.csv path")
    parser.add_argument("--current-class-csv", default=str(DEFAULT_CURRENT_CLASS_CSV), help="DEFECT_COORDINATES_EXTENDED.csv path for current_class lookup")
    parser.add_argument("--reclass-csv", default=str(DEFAULT_RECLASS_CSV), help="DEFECT_COORDINATES_RECLASS_LOG.csv path")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for enriched artifacts")
    parser.add_argument("--join-mode", choices=("inner", "left"), default=DEFAULT_JOIN_MODE, help="Join mode for production rows against VLM data")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    vlm_jsonl = Path(args.vlm_jsonl) if args.vlm_jsonl and Path(args.vlm_jsonl).exists() else None
    summary, enriched_csv, summary_csv, summary_json_path = build_enrichment(
        production_csv=Path(args.production_csv),
        vlm_manifest_csv=Path(args.vlm_manifest_csv),
        output_dir=Path(args.output_dir),
        ground_truth_csv=Path(args.ground_truth_csv),
        current_class_csv=Path(args.current_class_csv),
        reclass_csv=Path(args.reclass_csv),
        vlm_jsonl=vlm_jsonl,
        join_mode=args.join_mode,
    )
    print(json.dumps(summary, indent=2))
    print(str(enriched_csv.resolve()))
    print(str(summary_csv.resolve()))
    print(str(summary_json_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())