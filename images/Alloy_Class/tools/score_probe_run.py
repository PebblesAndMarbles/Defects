"""
Generic scorer for normalized VLM probe/run output (see tools/normalize_probe_output.py).

Consumes one or more raw JSONL files -- Lineage A (`stage_ab_results.jsonl`
production runner shape) or Lineage B (`tools/probe_*.py` throwaway shape),
auto-detected per file -- normalizes each into the generic per-case contract,
joins ground truth from the adjudicated candidates CSV by `case_id`
(`benchmark_id`), and writes:

  <output-folder>/probe_scored_rows.csv     flat, one row per case (for quick filtering/Excel)
  <output-folder>/probe_scored_cases.jsonl  full nested record per case (images + model_calls +
                                             gt/match fields) -- input for build_probe_html_report.py
  <output-folder>/probe_score_summary.json  aggregate metrics

Ground truth join:
  - Lineage B records already carry `case_id` (== benchmark_id) directly from the probe script's
    hardcoded test-case list -- no extra lookup needed.
  - Lineage A records carry `vlm_pair_key` (pair_key with role suffix stripped) but not `case_id`;
    pass --lookup-csv (the run's benchmark_id_lookup.csv) to resolve vlm_pair_key -> benchmark_id.
    Without --lookup-csv, Lineage A records are scored as "no_gt".

Positive class for confusion_label is "possible_beep", matching
tools/score_benchmark_run.py's existing fn_beep_rate/fp_beep_rate convention -- do not invent a
new convention here.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize_probe_output import normalize_jsonl  # noqa: E402
from score_benchmark_run import GT_NORMALIZE, _normalize_gt_value  # noqa: E402


def _strip_role_suffix(stem: str) -> str:
    for sfx in ("_2", "_3"):
        if stem.endswith(sfx):
            return stem[: -len(sfx)]
    return stem


def _load_gt_index(path: Path) -> dict[str, dict[str, str]]:
    """benchmark_id -> row, from artifacts/benchmark_candidates_14day.csv."""
    out: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            bid = (row.get("benchmark_id") or "").strip()
            if bid:
                out[bid] = row
    return out


def _load_pair_lookup_index(path: Path) -> dict[str, str]:
    """vlm_pair_key (bright_stem minus _2/_3) -> benchmark_id, from a run's benchmark_id_lookup.csv."""
    out: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            bright_stem = (row.get("bright_stem") or "").strip()
            vlm_key = _strip_role_suffix(bright_stem)
            bid = (row.get("benchmark_id") or "").strip()
            if vlm_key and bid:
                out[vlm_key] = bid
    return out


def _bool_str(value: Any) -> str:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _confusion_label(gt_coarse_class: str, vlm_coarse_class: str) -> str:
    if not gt_coarse_class:
        return "no_gt"
    if gt_coarse_class == "possible_beep":
        return "TP" if vlm_coarse_class == "possible_beep" else "FN"
    if gt_coarse_class == "particle":
        return "FP" if vlm_coarse_class == "possible_beep" else "TN"
    return "indeterminate"


def score_records(
    records: list[dict[str, Any]],
    gt_index: dict[str, dict[str, str]],
    lookup_index: dict[str, str] | None,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for rec in records:
        case_id = rec.get("case_id") or ""
        if not case_id and rec.get("lineage") == "a" and lookup_index:
            case_id = lookup_index.get(rec.get("vlm_pair_key", ""), "")
        rec = dict(rec)
        rec["case_id"] = case_id

        gt_row = gt_index.get(case_id) if case_id else None
        gt_coarse_class = _normalize_gt_value("adjudicated_coarse_class", gt_row.get("adjudicated_coarse_class", "")) if gt_row else ""
        gt_blocked_etch_evidence = (
            _normalize_gt_value("adjudicated_blocked_etch_evidence", gt_row.get("adjudicated_blocked_etch_evidence", "")) if gt_row else ""
        )
        gt_review_required = _normalize_gt_value("review_required_expected", gt_row.get("review_required_expected", "")) if gt_row else ""
        # Adjudication CSV field names differ from the VLM's evidence_check_* names but are the same three signatures.
        gt_evidence_checks = {
            "inset_surface_lines": _normalize_gt_value("offset_surface_lines_present", gt_row.get("offset_surface_lines_present", "")) if gt_row else "",
            "boundary_conformance": _normalize_gt_value("comparator_boundary_line_present", gt_row.get("comparator_boundary_line_present", "")) if gt_row else "",
            "sunken_residual": _normalize_gt_value("sunken_residual_continuity_present", gt_row.get("sunken_residual_continuity_present", "")) if gt_row else "",
        }

        final_verdict = rec.get("final_verdict") or {}
        vlm_coarse_class = str(final_verdict.get("coarse_class", "")).strip().lower()
        vlm_blocked_etch_evidence = str(final_verdict.get("blocked_etch_evidence", "")).strip().lower()
        vlm_review_required = final_verdict.get("review_required")

        rec["gt_source"] = "artifacts/benchmark_candidates_14day.csv" if gt_row else ""
        rec["gt_coarse_class"] = gt_coarse_class
        rec["gt_blocked_etch_evidence"] = gt_blocked_etch_evidence
        rec["gt_review_required"] = gt_review_required
        rec["gt_evidence_checks"] = gt_evidence_checks
        rec["coarse_class_match"] = (gt_coarse_class == vlm_coarse_class) if gt_row else None
        rec["evidence_match"] = (gt_blocked_etch_evidence == vlm_blocked_etch_evidence) if gt_row else None
        rec["review_required_match"] = (
            _bool_str(vlm_review_required) == _bool_str(gt_review_required) if gt_row else None
        )
        rec["confusion_label"] = _confusion_label(gt_coarse_class, vlm_coarse_class)
        scored.append(rec)
    return scored


def _compute_metrics(scored: list[dict[str, Any]]) -> dict[str, Any]:
    with_gt = [r for r in scored if r["confusion_label"] != "no_gt"]
    total = len(scored)
    counts = {"TP": 0, "TN": 0, "FP": 0, "FN": 0, "indeterminate": 0, "no_gt": 0}
    for r in scored:
        counts[r["confusion_label"]] += 1

    beep_gt_count = counts["TP"] + counts["FN"]
    particle_gt_count = counts["FP"] + counts["TN"]
    coarse_matches = sum(1 for r in with_gt if r["coarse_class_match"])
    evidence_matches = sum(1 for r in with_gt if r["evidence_match"])
    review_matches = sum(1 for r in with_gt if r["review_required_match"])

    return {
        "total_cases": total,
        "cases_with_gt": len(with_gt),
        "confusion_counts": counts,
        "coarse_class_agreement_rate": round(coarse_matches / len(with_gt), 4) if with_gt else None,
        "fn_beep_rate": round(counts["FN"] / beep_gt_count, 4) if beep_gt_count else None,
        "fn_beep_count": counts["FN"],
        "beep_gt_count": beep_gt_count,
        "fp_beep_rate": round(counts["FP"] / particle_gt_count, 4) if particle_gt_count else None,
        "fp_beep_count": counts["FP"],
        "particle_gt_count": particle_gt_count,
        "evidence_agreement_rate": round(evidence_matches / len(with_gt), 4) if with_gt else None,
        "review_required_calibration_rate": round(review_matches / len(with_gt), 4) if with_gt else None,
    }


def _flat_row(rec: dict[str, Any]) -> dict[str, Any]:
    final_verdict = rec.get("final_verdict") or {}
    return {
        "case_id": rec.get("case_id", ""),
        "lineage": rec.get("lineage", ""),
        "run_id": rec.get("run_id", ""),
        "config_version": rec.get("config_version", ""),
        "category": rec.get("category", ""),
        "vlm_coarse_class": str(final_verdict.get("coarse_class", "")),
        "vlm_blocked_etch_evidence": str(final_verdict.get("blocked_etch_evidence", "")),
        "vlm_confidence": final_verdict.get("confidence", ""),
        "vlm_review_required": final_verdict.get("review_required", ""),
        "gt_coarse_class": rec.get("gt_coarse_class", ""),
        "gt_blocked_etch_evidence": rec.get("gt_blocked_etch_evidence", ""),
        "gt_review_required": rec.get("gt_review_required", ""),
        "gt_evidence_inset_surface_lines": rec.get("gt_evidence_checks", {}).get("inset_surface_lines", ""),
        "gt_evidence_boundary_conformance": rec.get("gt_evidence_checks", {}).get("boundary_conformance", ""),
        "gt_evidence_sunken_residual": rec.get("gt_evidence_checks", {}).get("sunken_residual", ""),
        "coarse_class_match": rec.get("coarse_class_match"),
        "evidence_match": rec.get("evidence_match"),
        "review_required_match": rec.get("review_required_match"),
        "confusion_label": rec.get("confusion_label", ""),
        "notes": rec.get("notes", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score normalized VLM probe/run output (Lineage A or B) against adjudicated GT")
    parser.add_argument("--input-jsonl", nargs="+", required=True, help="One or more raw JSONL files (Lineage A or B, auto-detected per file)")
    parser.add_argument(
        "--gt-csv",
        default=str(Path(__file__).resolve().parents[1] / "artifacts" / "benchmark_candidates_14day.csv"),
        help="Adjudicated GT CSV keyed by benchmark_id (default: artifacts/benchmark_candidates_14day.csv)",
    )
    parser.add_argument("--lookup-csv", default=None, help="benchmark_id_lookup.csv, required to resolve case_id for Lineage A input")
    parser.add_argument("--output-folder", required=True)
    args = parser.parse_args()

    gt_index = _load_gt_index(Path(args.gt_csv))
    lookup_index = _load_pair_lookup_index(Path(args.lookup_csv)) if args.lookup_csv else None

    records: list[dict[str, Any]] = []
    for jsonl_path in args.input_jsonl:
        recs = normalize_jsonl(Path(jsonl_path))
        print(f"{jsonl_path}: lineage={recs[0]['lineage'] if recs else 'n/a'} cases={len(recs)}")
        records.extend(recs)

    scored = score_records(records, gt_index, lookup_index)
    unmatched = [r["case_id"] or r.get("vlm_pair_key", "<unknown>") for r in scored if r["confusion_label"] == "no_gt"]

    output_dir = Path(args.output_folder)
    output_dir.mkdir(parents=True, exist_ok=True)

    row_csv = output_dir / "probe_scored_rows.csv"
    if scored:
        flat_rows = [_flat_row(r) for r in scored]
        with row_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(flat_rows[0].keys()))
            w.writeheader()
            w.writerows(flat_rows)

    cases_jsonl = output_dir / "probe_scored_cases.jsonl"
    with cases_jsonl.open("w", encoding="utf-8") as f:
        for r in scored:
            f.write(json.dumps(r) + "\n")

    summary = {
        "input_jsonl": [str(Path(p).resolve()) for p in args.input_jsonl],
        "gt_csv": str(Path(args.gt_csv).resolve()),
        "unmatched_cases": unmatched,
        "metrics": _compute_metrics(scored),
    }
    summary_path = output_dir / "probe_score_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"scored_cases={len(scored)} unmatched={len(unmatched)}")
    print(f"row_csv={row_csv}")
    print(f"cases_jsonl={cases_jsonl}")
    print(f"summary={summary_path}")
    print(json.dumps(summary["metrics"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
