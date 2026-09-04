"""
Phase 2/3 diagnostic probe: describe-then-classify two-call Stage B architecture.

Call 1 (free observation): no Stage A context, no JSON contract -- a plain
junction-zone description, reusing the framing validated in the FN
feature-perception probe (see docs/v12_post_mortem.md addenda).

Call 2 (classify from observation): image(s) + Call 1's raw text output inserted
as context, plus an evidence-check framework drawn directly (at runtime, from the
actual config file -- not hand-copied) from the V11 Stage B prompt
(`stageB_substrate_tier1_v10` in config/stage_ab_prompt_tests_substrate_tier1_v11.json),
NOT V12. Per the external review of the v13 plan (docs/iGPT_v13_plan_feedback2.md):
V11 had zero FP rate, and the ~15 guidance/variant blocks V12 added on top of it
are what caused the evidence-agreement regression on BMK_0018 -- so Call 2 must
not carry those forward. Only the Stage-A-context-dependent opening sentence is
stripped from V11's text and replaced with a reference to Call 1's observation;
the three evidence-check definitions and the JSON output contract are otherwise
unchanged from V11.

Test set: the 5 known FN cases (BMK_0050, BMK_0029, BMK_0009, BMK_0005, BMK_0001)
plus 4 particle ground-truth controls (BMK_0008 from the scored 15-pair benchmark,
plus BMK_0002/BMK_0004/BMK_0092 from the broader candidate pool -- all selected
for being wall-adjacent particles per the external review's FP-risk guidance,
not open-field particles).

Intentionally NOT wired into the scored benchmark pipeline -- throwaway/ad hoc,
same convention as tools/probe_fn_feature_perception.py.
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

from run_stage_ab_prompt_tests import (  # type: ignore  # noqa: E402
    _call_image,
    _extract_json_payload,
    _load_env_from_supported_locations,
)

V11_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "stage_ab_prompt_tests_substrate_tier1_v11.json"

# The 5 known FN cases from outputs/raw_runs/offset_surface_lines_15_v12_compare
# (ground truth possible_beep, pipeline called particle). Kept in sync with
# tools/probe_fn_feature_perception.py's FN_CASES; duplicated here (not imported)
# to keep this throwaway script independently readable/runnable.
FN_CASES: list[dict[str, str]] = [
    {
        "case_id": "BMK_0050",
        "category": "fn_case",
        "gt_class": "possible_beep",
        "folder": "AME403_PM4",
        "stem": "260728_2212_D617642_539_BEEP_8M5CL_916",
        "notes": "narrow wall continuity or a concave terminus at the trench-comparator junction",
    },
    {
        "case_id": "BMK_0029",
        "category": "fn_case",
        "gt_class": "possible_beep",
        "folder": "AME417_PM2",
        "stem": "260801_0609_D618239_604_BEEP_8M6CL_1032",
        "notes": "a dark flanking void adjacent to the defect-wall contact point",
    },
    {
        "case_id": "BMK_0009",
        "category": "fn_case",
        "gt_class": "possible_beep",
        "folder": "AME417_PM5",
        "stem": "260802_1913_D616521_130_SMP_8M5CL_3110",
        "notes": "a crescent-shaped area of substrate material occupying the comparator interior",
    },
    {
        "case_id": "BMK_0005",
        "category": "fn_case",
        "gt_class": "possible_beep",
        "folder": "AME401_PM1",
        "stem": "260803_1754_D616533_204_SMP_8M6CL_3139",
        "notes": "bridging material spanning across the trench wall at the contact point",
    },
    {
        "case_id": "BMK_0001",
        "category": "fn_case",
        "gt_class": "possible_beep",
        "folder": "AME403_PM3",
        "stem": "260803_1800_D616465_064_SMP_8M6CL_10911",
        "notes": "an interruption in the trench wall's edge line exactly where the defect meets it",
    },
]

# Particle ground-truth controls: BMK_0008 is the one true-positive/particle case
# in the scored 15-pair benchmark; the other 3 are wall-adjacent particles sourced
# from artifacts/benchmark_candidates_14day.csv, filtered on the ADJUDICATED
# ground truth (`adjudicated_coarse_class` == "particle", adjudicated by TB) --
# NOT `factory_class_label`, which is just the pre-adjudication factory label used
# to build the initial non_beep_control candidate pool and is NOT ground truth
# (an earlier version of this script incorrectly used factory_class_label and
# mislabeled 3 genuine possible_beep cases as particle controls). Also filtered on
# comparator_visible=yes AND comparator_boundary_line_present=yes per the external
# review's instruction to prioritize wall-adjacent over open-field particles --
# these are what actually stress-test Call 2's boundary_conformance evidence
# check for over-calling BEEP. All BF/DF image files verified present on disk.
PARTICLE_CONTROLS: list[dict[str, str]] = [
    {
        "case_id": "BMK_0008",
        "category": "particle_control",
        "gt_class": "particle",
        "folder": "AME421_PM6",
        "stem": "260803_1434_D615293_015_SMP_8M5CL_851",
        "notes": "particle fully inside a comparator, no direct substrate evidence outside boundary (existing 15-pair benchmark control)",
    },
    {
        "case_id": "BMK_0020",
        "category": "particle_control",
        "gt_class": "particle",
        "folder": "AME421_PM3",
        "stem": "260802_1256_D619289_829_SMP_8M5CL_1150",
        "notes": "flat particle sits adjacent to a line trench, long side almost exactly matching the trench side, slight jut suggesting sunken residual but too slight to confirm pre-etch (adjudicated particle)",
    },
    {
        "case_id": "BMK_0024",
        "category": "particle_control",
        "gt_class": "particle",
        "folder": "AME421_PM4",
        "stem": "260802_1234_D619289_825_SMP_8M5CL_5399",
        "notes": "tiny spherical particle sits on the right edge of a full-height line trench, flush with the boundary but no blocked-edge evidence (adjudicated particle)",
    },
    {
        "case_id": "BMK_0100",
        "category": "particle_control",
        "gt_class": "particle",
        "folder": "AME417_PM6",
        "stem": "260724_1740_D617601_340_SMP_8M6CL_363",
        "notes": "angular vertex of particle protrudes slightly into a comparator with a faint boundary line, ambiguous but adjudicated particle",
    },
]

TEST_CASES: list[dict[str, str]] = FN_CASES + PARTICLE_CONTROLS

DEFAULT_MODEL = "claude-sonnet-4-6"
# Per Phase 1 finding (docs/v12_post_mortem.md addendum): 400 tokens produced a 25%
# empty-response rate vs 0% at 1800; default to production parity for this probe.
DEFAULT_MAX_TOKENS = 1800

CALL1_PROMPT = (
    "You are looking at a BEOL SEM defect image pair (brightfield + darkfield) of the same site. "
    "Describe what you see at the defect-comparator/trench junction zone in these images. Focus on: "
    "the defect's position relative to trench or comparator walls; any geometric irregularities "
    "(asymmetry, shortened or narrowed extent, tonal differences) in the nearest comparator or trench "
    "relative to other similar structures elsewhere in the field; and any material visible inside "
    "features that should otherwise be clear. Do not classify the defect as particle or BEEP. Do not "
    "use structured output or JSON. Describe only what is visually present, in 3-5 sentences."
)

# This exact sentence is removed from the V11 stage_b prompt text (it references
# Stage A, which does not run in this two-call experiment) and replaced with a
# reference to Call 1's observation. If the V11 config's wording ever changes,
# this check fails loudly instead of silently keeping a stale Stage A reference.
_STAGE_A_CONTEXT_SENTENCE = (
    "Use Stage A substrate context as prior. Note: when Stage A flags offset_surface_lines "
    "as a background confounder, that refers to substrate field texture away from the defect "
    "\u2014 always independently assess the defect boundary for blocking evidence regardless of that flag. "
)

_CLASSIFIER_INTRO = (
    "You are a BEOL SEM defect classifier distinguishing particle contamination from "
    "pre-etch blocking events (possible BEEP). "
)


def _load_v11_stage_b_prompt() -> str:
    cfg = json.loads(V11_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    return cfg["stage_b"]["prompt"]


def _build_call2_prompt(observation: str) -> str:
    base = _load_v11_stage_b_prompt()
    if _STAGE_A_CONTEXT_SENTENCE not in base:
        raise RuntimeError(
            "V11 stage_b prompt text no longer matches the expected Stage A context "
            "sentence -- update _STAGE_A_CONTEXT_SENTENCE in this script to match "
            "config/stage_ab_prompt_tests_substrate_tier1_v11.json before proceeding."
        )
    base = base.replace(_STAGE_A_CONTEXT_SENTENCE, "")

    observation_block = (
        "A separate observation pass already examined this image pair's defect-junction "
        "zone, with no classification bias, and wrote the following description:\n\n"
        f'"""\n{observation.strip()}\n"""\n\n'
        "Use this observation together with the images as supporting evidence, but verify "
        "each evidence check directly against the images yourself -- do not simply restate "
        "the observation's wording. "
    )
    if _CLASSIFIER_INTRO not in base:
        raise RuntimeError(
            "V11 stage_b prompt text no longer starts with the expected classifier intro "
            "sentence -- update _CLASSIFIER_INTRO in this script to match "
            "config/stage_ab_prompt_tests_substrate_tier1_v11.json before proceeding."
        )
    return base.replace(_CLASSIFIER_INTRO, _CLASSIFIER_INTRO + observation_block, 1)


def _pair_paths(case: dict[str, str]) -> tuple[Path, Path]:
    images_root = Path(
        r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\defects"
    )
    folder = images_root / case["folder"]
    bf = folder / f"{case['stem']}_2.jpg"
    df = folder / f"{case['stem']}_3.jpg"
    return bf, df


def _run_case(case: dict[str, str], model: str, max_completion_tokens: int) -> dict[str, Any]:
    bf, df = _pair_paths(case)
    call1_parsed, call1_text, call1_usage = _call_image([bf, df], CALL1_PROMPT, model, max_completion_tokens)
    call2_prompt = _build_call2_prompt(call1_text)
    call2_result, call2_text, call2_usage = _call_image([bf, df], call2_prompt, model, max_completion_tokens)

    # Call 2's contract expects a JSON object; re-parse defensively since _call_image
    # already ran _extract_json_payload once internally but only kept the dict form.
    if not isinstance(call2_result, dict) or "evidence_check_inset_surface_lines" not in call2_result:
        reparsed, _reparsed_text, _native = _extract_json_payload(call2_text)
        if isinstance(reparsed, dict) and "evidence_check_inset_surface_lines" in reparsed:
            call2_result = reparsed

    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "gt_class": case["gt_class"],
        "notes": case["notes"],
        "bf_image": str(bf),
        "df_image": str(df),
        "model": model,
        "call1_observation": call1_text,
        "call1_usage": call1_usage,
        "call2_prompt_chars": len(call2_prompt),
        "call2_parsed": call2_result if isinstance(call2_result, dict) else None,
        "call2_raw_text": call2_text,
        "call2_usage": call2_usage,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Describe-then-classify (Call 1 free observation -> Call 2 classify) probe, "
        "Call 2 drafted from V11 (not V12) per external review of the v13 plan."
    )
    parser.add_argument(
        "--cases", default="all", help="Comma-separated case_ids to run, or 'all' (default: 5 FN + 4 particle controls)."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-completion-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSONL path (default: outputs/probes/describe_then_classify_<UTC timestamp>.jsonl).",
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
        output_path = alloy_class_root / "outputs" / "probes" / f"describe_then_classify_{stamp}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    call_count = 0
    with output_path.open("w", encoding="utf-8") as out_f:
        for case in cases:
            bf, df = _pair_paths(case)
            if not bf.is_file() or not df.is_file():
                print(f"SKIP {case['case_id']}: missing image file(s) ({bf}, {df})", file=sys.stderr)
                continue

            record = _run_case(case, args.model, args.max_completion_tokens)
            call_count += 2
            out_f.write(json.dumps(record) + "\n")

            call2 = record["call2_parsed"] or {}
            isl = call2.get("evidence_check_inset_surface_lines", "?")
            bc = call2.get("evidence_check_boundary_conformance", "?")
            cls = call2.get("defect_coarse_class", "?")
            print(
                f"{case['case_id']} [{case['category']}, gt={case['gt_class']}]: "
                f"ISL={isl} BC={bc} class={cls}"
            )

    print(f"\nDone. {call_count} VLM calls across {len(cases)} cases. Results written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
