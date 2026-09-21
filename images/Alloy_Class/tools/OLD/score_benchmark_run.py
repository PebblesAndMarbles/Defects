"""
Score a Stage A/B VLM benchmark run against adjudicated ground truth.

Joins JSONL results to the frozen benchmark CSV via bright_image_name stem,
then computes per-split metrics and writes a per-row comparison CSV + summary JSON.

Join key:
  JSONL  pair_key  = filename stem with _2/_3 suffix stripped  (e.g. "XYZ_10911")
  Benchmark lookup = bright_stem column in benchmark_id_lookup.csv (e.g. "XYZ_10911_2")
                   -> strip trailing "_2" -> "XYZ_10911"
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

# Maps Stage B JSONL field names to benchmark adjudicated field names.
FIELD_MAP = {
    "defect_coarse_class":   "adjudicated_coarse_class",
    "blocked_etch_evidence": "adjudicated_blocked_etch_evidence",
    "review_required":       "review_required_expected",
}

STAGE_B_REQUIRED_FIELDS = [
    "defect_coarse_class",
    "blocked_etch_evidence",
    "review_required",
    "confidence",
    "evidence_check_inset_surface_lines",
    "evidence_check_boundary_conformance",
    "evidence_check_sunken_residual",
    "rationale",
]

# Canonicalize shorthand values that can appear in adjudication columns.
GT_NORMALIZE = {
    "adjudicated_coarse_class": {
        "b": "possible_beep",
        "p": "particle",
        "i": "indeterminate",
    },
    "adjudicated_blocked_etch_evidence": {
        "s": "strong",
        "m": "moderate",
        "n": "none",
        "w": "weak",
    },
    "adjudicated_confidence": {
        "h": "high",
        "m": "medium",
        "l": "low",
    },
    "comparator_visible": {
        "y": "yes",
        "n": "no",
        "p": "partial",
    },
    "notes_needed": {"y": "yes", "n": "no"},
    "occlusion_present": {"y": "yes", "n": "no"},
    "offset_surface_lines_present": {"y": "yes", "n": "no"},
    "sunken_residual_continuity_present": {"y": "yes", "n": "no"},
    "comparator_boundary_line_present": {"y": "yes", "n": "no"},
    "mult_particles_present": {"y": "yes", "n": "no"},
    "review_required_expected": {"y": "yes", "n": "no"},
}

COARSE_CLASS_ORDER = ["possible_beep", "indeterminate", "particle"]
EVIDENCE_ORDER = ["strong", "moderate", "weak", "none"]


def _strip_role_suffix(stem: str) -> str:
    """Remove _2 or _3 image-role suffix to get the pair identifier."""
    for sfx in ("_2", "_3"):
        if stem.endswith(sfx):
            return stem[: -len(sfx)]
    return stem


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _load_benchmark_csv(path: Path) -> dict[str, dict[str, str]]:
    """Index benchmark rows by pair_key (benchmark CSV pair_key column)."""
    out: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pk = (row.get("pair_key") or "").strip()
            if pk:
                out[pk] = row
    return out


def _load_lookup(path: Path) -> dict[str, dict[str, str]]:
    """
    Index lookup rows by derived pair key (bright_stem minus _2 suffix).
    Maps vlm_pair_key -> {benchmark_id, pair_key_benchmark, source_pool, adjudicated_coarse_class}
    """
    out: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            bright_stem = (row.get("bright_stem") or "").strip()
            vlm_key = _strip_role_suffix(bright_stem)
            if vlm_key:
                out[vlm_key] = row
    return out


def _review_required_bool(value: str) -> bool:
    v = str(value).strip().lower()
    return v in {"true", "1", "yes"}


def _review_required_expected_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _coerce_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _normalize_gt_value(field_name: str, value: str) -> str:
    raw = str(value).strip()
    if not raw:
        return ""
    lower = raw.lower()
    mapping = GT_NORMALIZE.get(field_name, {})
    return mapping.get(lower, raw)


def _compute_metrics(rows: list[dict]) -> dict:
    total = len(rows)
    if total == 0:
        return {"total": 0}

    # Class agreement
    coarse_match = sum(1 for r in rows if r["vlm_coarse_class"] == r["gt_coarse_class"])

    # FN: ground truth = possible_beep, vlm predicted particle or indeterminate
    beep_gt = [r for r in rows if r["gt_coarse_class"] == "possible_beep"]
    fn_beep = sum(1 for r in beep_gt if r["vlm_coarse_class"] in {"particle", "indeterminate"})

    # FP: ground truth = particle, vlm predicted possible_beep
    particle_gt = [r for r in rows if r["gt_coarse_class"] == "particle"]
    fp_beep = sum(1 for r in particle_gt if r["vlm_coarse_class"] == "possible_beep")

    # review_required calibration
    rr_match = sum(
        1 for r in rows
        if _review_required_bool(r["vlm_review_required"]) == _review_required_expected_bool(r["gt_review_required"])
    )

    # Evidence agreement
    evidence_match = sum(1 for r in rows if r["vlm_blocked_etch_evidence"] == r["gt_blocked_etch_evidence"])

    return {
        "total": total,
        "coarse_class_agreement_rate": round(coarse_match / total, 4),
        "coarse_class_matches": coarse_match,
        "fn_beep_rate": round(fn_beep / len(beep_gt), 4) if beep_gt else None,
        "fn_beep_count": fn_beep,
        "beep_gt_count": len(beep_gt),
        "fp_beep_rate": round(fp_beep / len(particle_gt), 4) if particle_gt else None,
        "fp_beep_count": fp_beep,
        "particle_gt_count": len(particle_gt),
        "evidence_agreement_rate": round(evidence_match / total, 4),
        "evidence_matches": evidence_match,
        "review_required_calibration_rate": round(rr_match / total, 4),
        "review_required_matches": rr_match,
    }


def _stage_b_contract_summary(rows: list[dict]) -> dict[str, object]:
    total = len(rows)
    if total == 0:
        return {
            "total": 0,
            "rows_with_raw_text_fallback": 0,
            "rows_missing_required_stage_b_fields": 0,
            "rows_with_non_numeric_stage_b_confidence": 0,
            "missing_required_stage_b_fields_by_name": {field: 0 for field in STAGE_B_REQUIRED_FIELDS},
        }

    missing_by_field = {field: 0 for field in STAGE_B_REQUIRED_FIELDS}
    rows_with_raw_text_fallback = 0
    rows_with_missing_required = 0
    rows_with_non_numeric_confidence = 0

    for row in rows:
        stage_b = row.get("stage_b") if isinstance(row.get("stage_b"), dict) else {}
        if isinstance(stage_b, dict) and "raw_text" in stage_b:
            rows_with_raw_text_fallback += 1

        row_missing_required = False
        for field in STAGE_B_REQUIRED_FIELDS:
            value = stage_b.get(field) if isinstance(stage_b, dict) else None
            if not str(value or "").strip():
                missing_by_field[field] += 1
                row_missing_required = True
        if row_missing_required:
            rows_with_missing_required += 1

        if _coerce_float(stage_b.get("confidence") if isinstance(stage_b, dict) else None) is None:
            rows_with_non_numeric_confidence += 1

    return {
        "total": total,
        "rows_with_raw_text_fallback": rows_with_raw_text_fallback,
        "rows_missing_required_stage_b_fields": rows_with_missing_required,
        "rows_with_non_numeric_stage_b_confidence": rows_with_non_numeric_confidence,
        "missing_required_stage_b_fields_by_name": missing_by_field,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score Stage A/B VLM run against benchmark ground truth")
    parser.add_argument("--results-jsonl", required=True, help="stage_ab_results.jsonl from run_benchmark_vlm.py")
    parser.add_argument("--benchmark-csv", required=True, help="benchmark_v1_frozen.csv (canonical adjudicated labels)")
    parser.add_argument("--lookup-csv", required=True, help="benchmark_id_lookup.csv from run_benchmark_vlm.py output")
    parser.add_argument("--output-folder", required=True)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()

    results_path = Path(args.results_jsonl)
    benchmark_path = Path(args.benchmark_csv)
    lookup_path = Path(args.lookup_csv)
    output_dir = Path(args.output_folder)
    output_dir.mkdir(parents=True, exist_ok=True)

    jsonl_rows = _load_jsonl(results_path)
    benchmark_index = _load_benchmark_csv(benchmark_path)
    lookup_index = _load_lookup(lookup_path)

    print(f"jsonl_rows={len(jsonl_rows)}")
    print(f"benchmark_rows={len(benchmark_index)}")
    print(f"lookup_entries={len(lookup_index)}")

    # Collect one record per pair (brightfield row carries Stage B; skip darkfield rows)
    per_pair: dict[str, dict] = {}
    for row in jsonl_rows:
        role = (row.get("pair_role") or "").strip().lower()
        pair_key = (row.get("pair_key") or "").strip()
        if role != "brightfield":
            continue
        stage_b = row.get("stage_b") or {}
        stage_a = row.get("stage_a") or {}
        per_pair[pair_key] = {
            "vlm_pair_key": pair_key,
            "vlm_coarse_class": (stage_b.get("defect_coarse_class") or "").strip().lower(),
            "vlm_blocked_etch_evidence": (stage_b.get("blocked_etch_evidence") or "").strip().lower(),
            "vlm_review_required": str(stage_b.get("review_required", "")).strip(),
            "vlm_stage_a_confidence": str(stage_a.get("context_confidence", "")),
            "vlm_stage_b_confidence": str(stage_b.get("confidence", "")),
            # v2 evidence check fields (empty string when running v1 config)
            "vlm_ec_inset_surface_lines": (stage_b.get("evidence_check_inset_surface_lines") or "").strip().lower(),
            "vlm_ec_boundary_conformance": (stage_b.get("evidence_check_boundary_conformance") or "").strip().lower(),
            "vlm_ec_sunken_residual": (stage_b.get("evidence_check_sunken_residual") or "").strip().lower(),
            "vlm_rationale": (stage_b.get("rationale") or "").strip(),
        }

    print(f"pairs_with_stage_b={len(per_pair)}")

    contract_summary = _stage_b_contract_summary(jsonl_rows)
    print(
        "stage_b_contract: "
        f"raw_text_fallback_rows={contract_summary['rows_with_raw_text_fallback']} "
        f"rows_missing_required={contract_summary['rows_missing_required_stage_b_fields']} "
        f"non_numeric_confidence={contract_summary['rows_with_non_numeric_stage_b_confidence']}"
    )

    # Join to benchmark via lookup
    scored_rows: list[dict] = []
    unmatched_vlm: list[str] = []

    for vlm_key, vlm in per_pair.items():
        lookup = lookup_index.get(vlm_key)
        if not lookup:
            unmatched_vlm.append(vlm_key)
            continue
        bmark_pk = (lookup.get("pair_key_benchmark") or "").strip()
        bmark = benchmark_index.get(bmark_pk, {})
        row = {
            "benchmark_id": lookup.get("benchmark_id", ""),
            "pair_key_benchmark": bmark_pk,
            "vlm_pair_key": vlm_key,
            "split": bmark.get("split", ""),
            "source_pool": lookup.get("source_pool", ""),
            "gt_coarse_class": _normalize_gt_value("adjudicated_coarse_class", bmark.get("adjudicated_coarse_class") or lookup.get("adjudicated_coarse_class") or ""),
            "gt_blocked_etch_evidence": _normalize_gt_value("adjudicated_blocked_etch_evidence", bmark.get("adjudicated_blocked_etch_evidence") or ""),
            "gt_confidence": _normalize_gt_value("adjudicated_confidence", bmark.get("adjudicated_confidence") or ""),
            "gt_comparator_visible": _normalize_gt_value("comparator_visible", bmark.get("comparator_visible") or ""),
            "gt_occlusion_present": _normalize_gt_value("occlusion_present", bmark.get("occlusion_present") or ""),
            "gt_offset_surface_lines_present": _normalize_gt_value("offset_surface_lines_present", bmark.get("offset_surface_lines_present") or ""),
            "gt_sunken_residual_continuity_present": _normalize_gt_value("sunken_residual_continuity_present", bmark.get("sunken_residual_continuity_present") or ""),
            "gt_comparator_boundary_line_present": _normalize_gt_value("comparator_boundary_line_present", bmark.get("comparator_boundary_line_present") or ""),
            "gt_mult_particles_present": _normalize_gt_value("mult_particles_present", bmark.get("mult_particles_present") or ""),
            "gt_review_required": _normalize_gt_value("review_required_expected", bmark.get("review_required_expected") or ""),
            **vlm,
        }
        row["coarse_class_match"] = str(row["vlm_coarse_class"] == row["gt_coarse_class"]).lower()
        row["evidence_match"] = str(row["vlm_blocked_etch_evidence"] == row["gt_blocked_etch_evidence"]).lower()
        scored_rows.append(row)

    print(f"scored_rows={len(scored_rows)}")
    if unmatched_vlm:
        print(f"unmatched_vlm_keys ({len(unmatched_vlm)}): {unmatched_vlm}")

    # Per-row output CSV
    row_csv = output_dir / "benchmark_scored_rows.csv"
    if scored_rows:
        fieldnames = list(scored_rows[0].keys())
        with row_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(scored_rows)
        print(f"row_csv={row_csv}")

    # Metrics by split
    splits_seen = sorted({r["split"] for r in scored_rows})
    metrics_by_split: dict[str, dict] = {}
    for sp in (splits_seen + ["all"]):
        subset = scored_rows if sp == "all" else [r for r in scored_rows if r["split"] == sp]
        metrics_by_split[sp] = _compute_metrics(subset)

    summary = {
        "run_id": args.run_id,
        "results_jsonl": str(results_path.resolve()),
        "benchmark_csv": str(benchmark_path.resolve()),
        "pairs_scored": len(scored_rows),
        "unmatched_vlm_keys": unmatched_vlm,
        "stage_b_contract": contract_summary,
        "metrics": metrics_by_split,
    }
    summary_path = output_dir / "benchmark_score_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"summary={summary_path}")

    # Print quick table
    for sp, m in metrics_by_split.items():
        print(f"\n--- {sp} (n={m['total']}) ---")
        for k, v in m.items():
            if k != "total":
                print(f"  {k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
