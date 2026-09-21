"""
Normalize Lineage A (production Stage A/B runner, `stage_ab_results.jsonl`) and
Lineage B (throwaway `tools/probe_*.py` scripts) raw JSONL output into one
generic per-case contract, so a single scorer and a single HTML report can
consume either lineage -- or any future N-call architecture -- without
hardcoding "stage_a/stage_b" or "call1/call2" anywhere.

See docs/PROBE_OUTPUT_SCORING_AND_HTML_REPORT_GAP.md section 5 for the contract
this module produces, and sections 1-2 for the two raw shapes it consumes.

Generic contract (one dict per case):
    case_id            benchmark_id if resolved, else "" (scorer resolves this)
    vlm_pair_key        lineage-A join key (stem with _2/_3 suffix stripped); "" for lineage B
    run_id              best-effort run identity (explicit field, else source file stem)
    config_version      whatever identifies "which approach produced this" (prompt version / model)
    lineage             "a" or "b"
    images              [{"role": "brightfield"|"darkfield", "path": "..."}, ...]
    model_calls         ORDERED list of {"call_label", "prompt_version", "raw_text",
                         "parsed_json", "skipped", "skip_reason", "usage"} -- a skipped/gated
                         call still appears here, never silently dropped
    final_verdict       normalized from the LAST non-skipped model_calls entry's parsed_json:
                         {"coarse_class", "blocked_etch_evidence", "confidence",
                          "review_required", "evidence_checks": {...}, "rationale"}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text:
            rows.append(json.loads(text))
    return rows


def _strip_role_suffix(stem: str) -> str:
    """Remove _2 or _3 image-role suffix to get the pair identifier."""
    for sfx in ("_2", "_3"):
        if stem.endswith(sfx):
            return stem[: -len(sfx)]
    return stem


def is_lineage_a_row(row: dict[str, Any]) -> bool:
    return "pair_role" in row and "stage_a" in row


def is_lineage_b_row(row: dict[str, Any]) -> bool:
    return "case_id" in row and ("call1_observation" in row or "call2_parsed" in row)


def detect_lineage(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        if is_lineage_a_row(row):
            return "a"
        if is_lineage_b_row(row):
            return "b"
    raise ValueError(
        "Could not detect lineage: rows have neither Lineage A (pair_role/stage_a) "
        "nor Lineage B (case_id/call1_observation) shape."
    )


def group_lineage_a_by_pair(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """pair_key -> {"brightfield": row, "darkfield": row}"""
    by_pair: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        pair_key = str(row.get("pair_key", ""))
        role = str(row.get("pair_role", "unknown"))
        by_pair.setdefault(pair_key, {})[role] = row
    return by_pair


def _final_verdict_from_stage_b(stage_b: dict[str, Any]) -> dict[str, Any]:
    return {
        "coarse_class": str(stage_b.get("defect_coarse_class", "")).strip().lower(),
        "blocked_etch_evidence": str(stage_b.get("blocked_etch_evidence", "")).strip().lower(),
        "confidence": stage_b.get("confidence"),
        "review_required": stage_b.get("review_required"),
        "evidence_checks": {
            "inset_surface_lines": stage_b.get("evidence_check_inset_surface_lines"),
            "boundary_conformance": stage_b.get("evidence_check_boundary_conformance"),
            "sunken_residual": stage_b.get("evidence_check_sunken_residual"),
        },
        "rationale": stage_b.get("rationale", ""),
    }


def normalize_lineage_a_pair(pair_key: str, roles: dict[str, dict[str, Any]], source_run_id: str = "") -> dict[str, Any]:
    """
    Maps one Stage A/B pair (brightfield + darkfield raw JSONL rows, grouped by
    `group_lineage_a_by_pair`) into the generic contract. Stage B is evaluated
    once per pair in current configs (identical result copied to both roles
    when stage_b_multi_image=True) -- the brightfield role is taken as
    canonical, matching tools/score_benchmark_run.py's existing convention.
    """
    bf = roles.get("brightfield", {})
    df = roles.get("darkfield", {})
    canonical = bf or df

    images: list[dict[str, str]] = []
    if bf:
        images.append({"role": "brightfield", "path": bf.get("burned_image_path") or bf.get("image_name", "")})
    if df:
        images.append({"role": "darkfield", "path": df.get("burned_image_path") or df.get("image_name", "")})

    stage_a = canonical.get("stage_a") if isinstance(canonical.get("stage_a"), dict) else {}
    stage_b = canonical.get("stage_b") if isinstance(canonical.get("stage_b"), dict) else {}

    model_calls: list[dict[str, Any]] = [
        {
            "call_label": "stage_a",
            "prompt_version": canonical.get("stage_a_prompt_version", ""),
            "raw_text": canonical.get("stage_a_raw_excerpt", ""),
            "parsed_json": stage_a or None,
            "skipped": False,
            "skip_reason": None,
            "usage": canonical.get("stage_a_usage"),
        },
    ]
    # v13+ describe-then-classify: an extra free-text call is folded into stage_b's prompt
    if isinstance(canonical.get("stage_b_call1_observation"), str):
        model_calls.append(
            {
                "call_label": "stage_b_call1_observation",
                "prompt_version": canonical.get("stage_b_prompt_version", ""),
                "raw_text": canonical.get("stage_b_call1_observation", ""),
                "parsed_json": None,
                "skipped": False,
                "skip_reason": None,
                "usage": canonical.get("stage_b_call1_usage"),
            }
        )
    model_calls.append(
        {
            "call_label": "stage_b",
            "prompt_version": canonical.get("stage_b_prompt_version", ""),
            "raw_text": canonical.get("stage_b_raw_excerpt", ""),
            "parsed_json": stage_b or None,
            "skipped": False,
            "skip_reason": None,
            "usage": canonical.get("stage_b_usage"),
        }
    )

    return {
        "case_id": "",  # resolved by the scorer via benchmark_id_lookup.csv (pair_key join)
        "vlm_pair_key": _strip_role_suffix(pair_key),
        "run_id": canonical.get("run_id") or source_run_id,
        "config_version": canonical.get("stage_b_prompt_version", ""),
        "lineage": "a",
        "images": images,
        "model_calls": model_calls,
        "final_verdict": _final_verdict_from_stage_b(stage_b),
    }


def normalize_lineage_b_row(row: dict[str, Any], source_run_id: str = "") -> dict[str, Any]:
    """Maps one probe script's flat JSON record (v13/v14 describe-then-classify shape) into the generic contract."""
    images: list[dict[str, str]] = []
    if row.get("bf_image"):
        images.append({"role": "brightfield", "path": row["bf_image"]})
    if row.get("df_image"):
        images.append({"role": "darkfield", "path": row["df_image"]})

    call1_parsed = {"verdict": row["call1_verdict"]} if row.get("call1_verdict") is not None else None
    gated = bool(row.get("gated"))
    call2_parsed = row.get("call2_parsed") if isinstance(row.get("call2_parsed"), dict) else None

    model_calls: list[dict[str, Any]] = [
        {
            "call_label": "call1_observation",
            "prompt_version": "",
            "raw_text": row.get("call1_observation", ""),
            "parsed_json": call1_parsed,
            "skipped": False,
            "skip_reason": None,
            "usage": row.get("call1_usage"),
        },
        {
            "call_label": "call2_classify",
            "prompt_version": "",
            "raw_text": row.get("call2_raw_text", ""),
            "parsed_json": call2_parsed,
            "skipped": gated,
            "skip_reason": f"call1_verdict={row.get('call1_verdict')}" if gated else None,
            "usage": row.get("call2_usage"),
        },
    ]

    last_parsed: dict[str, Any] | None = None
    for call in reversed(model_calls):
        if call["parsed_json"]:
            last_parsed = call["parsed_json"]
            break

    final_verdict = _final_verdict_from_stage_b(last_parsed) if last_parsed else {}

    return {
        "case_id": row.get("case_id", ""),
        "vlm_pair_key": "",
        "run_id": row.get("run_id") or source_run_id,
        "config_version": row.get("model", ""),
        "lineage": "b",
        "category": row.get("category", ""),
        "notes": row.get("notes", ""),
        "hardcoded_gt_class": row.get("gt_class", ""),  # NOT authoritative -- see gap doc section 2a
        "images": images,
        "model_calls": model_calls,
        "final_verdict": final_verdict,
    }


def normalize_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a raw JSONL file (either lineage, auto-detected) and return generic-contract records."""
    rows = load_jsonl(path)
    if not rows:
        return []
    lineage = detect_lineage(rows)
    source_run_id = path.stem
    if lineage == "b":
        return [normalize_lineage_b_row(r, source_run_id) for r in rows if is_lineage_b_row(r)]
    by_pair = group_lineage_a_by_pair([r for r in rows if is_lineage_a_row(r)])
    return [normalize_lineage_a_pair(pk, roles, source_run_id) for pk, roles in by_pair.items()]
