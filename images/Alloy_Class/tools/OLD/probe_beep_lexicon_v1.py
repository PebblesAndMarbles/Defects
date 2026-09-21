"""
Fresh probe built directly from the user's BEEP_Evidence lexicon
(images/Alloy_Class/BEEP_Evidence copy.txt, 2026-08-28), not a patch on the V11/v13/v14
lineage. Single call per image pair -- no separate Call 1 free-observation pass -- per
the user's explicit goal of a tight prompt with a direct, inspectable translation of the
lexicon's ideas, rather than the V11-derived prompt's accumulated per-pathway patches
(which grew to ~19,000 chars and started causing vocabulary over-indexing, e.g. the
model echoing "parallelogram" in cases where it didn't apply).

Key structural ideas carried over from the lexicon (see the source .txt for the full
definitions this prompt is translating):
- Comparator occlusion state (occluding vs non-occluding) determines which boundary-
  conformance check applies, instead of one generic check with ownership caveats bolted
  on afterward.
- Inset surface lines are defined by confirming a strip's texture/contrast MATCHES real
  SiO -- a positive, falsifiable test -- rather than the old "material distinguishable
  from the defect's own body" negative test.
- A trench split mid-span by a bridge is just an extreme case of inset surface lines
  (a strip wide enough to bridge the comparator), not a separate pathway.
- Three positioning scenarios (spans a comparator / entirely within one / spans none)
  replace running all evidence pathways unconditionally regardless of geometry.
- Multiple material defects can appear in one image; strong evidence for any one of them
  makes the whole site pre-etch (this is what should let a case like BMK_0029 resolve
  correctly: the visible defect body and the separately-bridged trench elsewhere in the
  field are two distinct material defects, not one ambiguous signal).
- Strong evidence in either brightfield or darkfield alone is sufficient.

Reuses FN_CASES / PARTICLE_CONTROLS / EDGE_CASE_CONTROLS / FP21_CASES and _pair_paths
from tools/probe_describe_then_classify_v14.py rather than re-duplicating ~90 lines of
case metadata a third time -- a deliberate deviation from that script's own
duplicate-don't-import convention, justified here because this script is a genuinely
fresh prompt attempt over the SAME benchmark cases, not an independent one-off.

Output is written in the same flat Lineage B shape normalize_probe_output.py already
understands (case_id / call1_observation / call2_parsed / ...) so the existing
tools/score_probe_run.py and reporting/build_probe_html_report.py work unmodified. This
is a single-call architecture, so call1_observation is left empty and the full response
is stored under call2_parsed/call2_raw_text -- see normalize_lineage_b_row() if this
mislabeling ever needs a cleaner dedicated single-call shape.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPORTING_DIR = Path(__file__).resolve().parents[1] / "reporting"
if str(_REPORTING_DIR) not in sys.path:
    sys.path.insert(0, str(_REPORTING_DIR))
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from run_stage_ab_prompt_tests import (  # type: ignore  # noqa: E402
    _call_image,
    _extract_json_payload,
    _load_env_from_supported_locations,
)
from probe_describe_then_classify_v14 import (  # type: ignore  # noqa: E402
    FN_CASES,
    PARTICLE_CONTROLS,
    EDGE_CASE_CONTROLS,
    FP21_CASES,
    _pair_paths,
)

TEST_CASES: list[dict[str, str]] = FN_CASES + PARTICLE_CONTROLS + EDGE_CASE_CONTROLS + FP21_CASES

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 1800

LEXICON_PROMPT_V1 = (
    "You are analyzing a BEOL SEM defect image pair (brightfield + darkfield) of the same site, "
    "imaged at an angle normal to the wafer surface. Strong evidence in either image alone is "
    "sufficient to confirm a Blocked Etch verdict; compare the two images to reduce uncertainty, "
    "but consistency between them confirms only the defect's existence and position, not pre-etch "
    "status by itself.\n\n"
    "SUBSTRATE: Bright regions in both images are SiO surface, with a relatively uniform, bumpy "
    "texture.\n\n"
    "COMPARATORS (etched structures, dark regions): Contrast can vary slightly within a comparator "
    "depending on light-source position -- this alone is never evidence of anything. Long "
    "dimensions of all comparators in an image are parallel to each other; positioning may be "
    "regular or irregular, in one or both dimensions. A line trench may terminate in a rounded cap "
    "in the frame, or span the full image height/width; short line trenches round-cap at both ends. "
    "Vias have a long and short side with rounded corners. Wide vias have a longer long-side than "
    "standard vias but a short side comparable to a via's, also rounded. Vias and wide vias may only "
    "partially land in the image frame.\n\n"
    "MATERIAL DEFECTS: Residual material resting on the SiO surface, on a comparator, or both. "
    "Defect boundaries do not match regular comparator shapes -- they can be round, angular, "
    "porous, or layered, and large defects can appear out of focus. Defect material is infrequently "
    "similar, and never identical, to SiO texture. An image can contain more than one material "
    "defect; if strong evidence confirms pre-etch behavior for any one of them, treat every material "
    "defect in the image as pre-etch.\n\n"
    "GOAL: For each material defect, decide pre-etch (blocked etch) or post-etch (particle), based "
    "only on inference from the interaction between the SiO surface, the comparator, and the defect "
    "in that defect's direct vicinity.\n\n"
    "COMPARATOR CONCAVITY: Slight concavity is normal, especially along the long dimension of vias "
    "and wide vias, or as undulations in a line trench boundary -- if uncertain whether a concavity "
    "is normal, compare against other comparators in the image. Sharp concavities or acute angles in "
    "a comparator boundary are pre-etch evidence regardless of whether a material defect is directly "
    "present at that location.\n\n"
    "INSET SURFACE LINES: A strip of SiO substrate bounded by a comparator concavity and a defect "
    "boundary. A strip extending far enough can bridge fully across a comparator. Evidence is "
    "strengthened when the strip's texture AND contrast both match the surrounding SiO substrate.\n\n"
    "OCCLUDING BOUNDARY CONFORMANCE (the defect covers/hides the comparator boundary at this point): "
    "confirmed when a line within the defect's own body closely matches the comparator's inferred "
    "boundary -- look for a distinct contrast change within the defect where it crosses that inferred "
    "line. The conforming line can be curved or mostly straight.\n\n"
    "NON-OCCLUDING BOUNDARY CONFORMANCE (the real comparator boundary is directly visible): "
    "confirmed when the defect's own boundary closely matches the real comparator boundary line; a "
    "small bump or portion of that line may extend into the comparator. Can be curved or mostly "
    "straight.\n\n"
    "SUNKEN RESIDUAL MATERIAL: defect material inside a comparator that shares a conforming boundary "
    "(partial or full width) with defect material on the SiO surface, usually darker in contrast "
    "than the SiO. Supporting evidence only -- use it to raise confidence when a conforming boundary "
    "is a near-but-imperfect match; never treat it as sufficient evidence on its own.\n\n"
    "COMPARATOR OCCLUSION: whether and how much a defect occludes a comparator determines which "
    "evidence pathways above even apply. An occluded comparator's expected boundary may need to be "
    "inferred by comparison to other same-type comparators -- most reliable for regular, repeating "
    "layouts, less reliable for irregular ones.\n\n"
    "ASSESS EACH MATERIAL DEFECT UNDER EXACTLY ONE OF THESE THREE SCENARIOS:\n"
    "1. Spans at least one inferred comparator boundary -> check (a) comparator concavity supported "
    "by inset surface lines, and (b) occluding boundary conformance, supported by sunken residual "
    "material.\n"
    "2. Entirely within a real or inferred comparator boundary -> confirm pre-etch ONLY via "
    "contrast/texture confirmation that the within-boundary material is SiO substrate, not defect "
    "material. No other pathway applies to this scenario.\n"
    "3. Spans no real comparator boundary -> inspect nearby comparators for sharp concavities or "
    "acute-angle boundaries; only natural undulations count as normal.\n\n"
    "OUTPUT CONTRACT -- strict JSON only, output the JSON object as the first and only content in "
    "your response, no explanatory text outside it. confidence must be a decimal float between 0.0 "
    "and 1.0, never a word like \"high\" or \"medium\". Use exactly these top-level keys in exactly "
    "this order: material_defects, evidence_check_inset_surface_lines, "
    "evidence_check_boundary_conformance, evidence_check_sunken_residual, defect_coarse_class, "
    "blocked_etch_evidence, confidence, review_required, rationale.\n\n"
    "material_defects: array, one entry per distinct material defect you identify in the image pair, "
    "each with keys defect_id (short label, e.g. \"primary\" or \"secondary_1\"), scenario "
    "(spans_comparator | within_comparator | no_comparator_span), evidence_check_inset_surface_lines "
    "/ evidence_check_boundary_conformance / evidence_check_sunken_residual (each yes/no/unclear), "
    "pre_etch_confirmed (boolean), and rationale (one sentence).\n\n"
    "Top-level evidence_check_* fields: yes if confirmed for ANY material defect in the image, "
    "unclear if genuinely ambiguous for every defect, no otherwise.\n"
    "defect_coarse_class: possible_beep if any material defect has pre_etch_confirmed true; particle "
    "if every defect is confirmed post-etch; indeterminate if visibility is too degraded to assess "
    "any defect.\n"
    "blocked_etch_evidence: strong if a primary pathway (occluding boundary conformance, a "
    "full-width bridging inset surface line, or scenario 2's SiO confirmation) is confirmed AND "
    "supporting evidence (sunken residual or comparator concavity) is also present; moderate if a "
    "primary pathway is confirmed alone; weak if only supporting evidence exists without a confirmed "
    "primary pathway; none if no evidence is found for any material defect.\n"
    "confidence: your confidence in defect_coarse_class.\n"
    "review_required: true if evidence is borderline, occlusion made boundary inference difficult, "
    "or scenario assessment was ambiguous for any defect.\n"
    "rationale: 2-3 sentences summarizing the verdict across all material defects in the image."
)


def _run_case(case: dict[str, str], model: str, max_completion_tokens: int) -> dict[str, Any]:
    bf, df = _pair_paths(case)
    parsed, raw_text, usage = _call_image([bf, df], LEXICON_PROMPT_V1, model, max_completion_tokens)

    if not isinstance(parsed, dict) or "defect_coarse_class" not in parsed:
        reparsed, _reparsed_text, _native = _extract_json_payload(raw_text)
        if isinstance(reparsed, dict) and "defect_coarse_class" in reparsed:
            parsed = reparsed

    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "gt_class": case["gt_class"],
        "notes": case["notes"],
        "bf_image": str(bf),
        "df_image": str(df),
        "model": model,
        "call1_observation": "",
        "call1_usage": None,
        "call2_prompt_chars": len(LEXICON_PROMPT_V1),
        "call2_parsed": parsed if isinstance(parsed, dict) else None,
        "call2_raw_text": raw_text,
        "call2_usage": usage,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fresh single-call probe built directly from the BEEP_Evidence lexicon."
    )
    parser.add_argument(
        "--cases", default="all", help="Comma-separated case_ids to run, or 'all' (default: 5 FN + 4 particle controls + 1 edge case + 21 FP cases)."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-completion-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSONL path (default: outputs/probes/beep_lexicon_v1_<UTC timestamp>.jsonl).",
    )
    args = parser.parse_args()

    _load_env_from_supported_locations()

    requested_ids = None if args.cases == "all" else {c.strip() for c in args.cases.split(",")}
    cases = [c for c in TEST_CASES if requested_ids is None or c["case_id"] in requested_ids]
    if not cases:
        raise SystemExit(f"No matching cases for --cases {args.cases!r}")

    if args.output:
        output_path = Path(args.output)
    else:
        alloy_class_root = Path(__file__).resolve().parents[1]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = alloy_class_root / "outputs" / "probes" / f"beep_lexicon_v1_{stamp}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    call_count = 0
    with output_path.open("w", encoding="utf-8") as out_f:
        for case in cases:
            bf, df = _pair_paths(case)
            if not bf.is_file() or not df.is_file():
                print(f"SKIP {case['case_id']}: missing image file(s) ({bf}, {df})", file=sys.stderr)
                continue

            record = _run_case(case, args.model, args.max_completion_tokens)
            call_count += 1
            out_f.write(json.dumps(record) + "\n")

            call2 = record["call2_parsed"] or {}
            isl = call2.get("evidence_check_inset_surface_lines", "?")
            bc = call2.get("evidence_check_boundary_conformance", "?")
            cls = call2.get("defect_coarse_class", "?")
            n_defects = len(call2.get("material_defects", []) or [])
            print(
                f"{case['case_id']} [{case['category']}, gt={case['gt_class']}]: "
                f"n_defects={n_defects} ISL={isl} BC={bc} class={cls}"
            )

    print(f"\nDone. {call_count} VLM calls across {len(cases)} cases. Results written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
