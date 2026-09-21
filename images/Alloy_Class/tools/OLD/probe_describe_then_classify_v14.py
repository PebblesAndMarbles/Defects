"""
Phase 7 diagnostic probe: v14 verdict-gate fix on top of the v13 describe-then-classify
architecture (docs/iGPT_v13_FN_plan_passdown.md Step 3), plus two domain-feedback fixes
not yet incorporated anywhere upstream. Throwaway/ad hoc, same convention as
tools/probe_describe_then_classify.py (v13) -- NOT wired into the scored benchmark
pipeline, and reporting/run_stage_ab_prompt_tests.py (production runner) is untouched.

Changes vs v13 (tools/probe_describe_then_classify.py):

1. VERDICT GATE (passdown Step 3): Call 1 now ends with a mandatory VERDICT line. If
   the verdict is "No blocking evidence observed", Call 2 is skipped entirely and a
   particle result is returned directly (hard gate). "Possible blocking evidence" or
   "Ambiguous" verdicts run the full V11-derived pathway assessment as before.

2. TONAL/DARKNESS BAN (domain feedback, 2026-08-27): trench/comparator interior
   tone-or-darkness comparisons ("this trench is lighter/darker than that one") must
   NOT be used as blocking-etch evidence -- per the user, this varies with light-source
   angle/position and has no established connection to etch state. V11's PATHWAY 1
   (TONAL FILL) is rewritten to require a discrete, locatable material patch instead of
   a bare tone/darkness comparison; Call 1's observation prompt gets the same caveat so
   the bias isn't introduced upstream of Call 2 either.

   Root-cause note: manually reviewing the actual Call 1 texts from
   benchmark_particle25_v13_describe_then_classify_rerun2 (the 21-FP run) found the
   passdown's Category-A claim ("Call 1 texts explicitly state no blocked etch
   evidence") did not hold -- 0 of 21 FP Call 1 texts contained negative/no-evidence
   language; all 21 contained tonal-fill-style affirmative language. That's exactly the
   pathway this fix targets, so the verdict gate alone (item 1) may not have been
   sufficient without also fixing Pathway 1's underlying bias.

3. SUNKEN-RESIDUAL TEXTURE CORRELATION (domain feedback, BMK_0011): genuine sunken
   residual is normally paired with matching-texture material visible adjacent to the
   feature on the surrounding SiO substrate, outside the comparator boundary. Inset
   surface lines can still occur with no material at all on the adjacent substrate
   (that absence alone does not disqualify sunken_residual) -- but if material IS
   present inside the recessed feature and its texture does not match anything on the
   adjacent substrate, that mismatch is now a signal favoring particle over sunken
   residual. BMK_0011 is added to the test set as the motivating edge case.

See config/stage_ab_prompt_tests_substrate_tier1_v14.json for the run-level summary.
"""

from __future__ import annotations

import argparse
import json
import re
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

# Same 5 known FN cases as tools/probe_describe_then_classify.py (v13), kept in sync
# by duplication (not import) per that script's own stated convention.
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

# Same 4 particle controls as v13, plus BMK_0011 added below as an EDGE_CASE_CONTROL --
# see module docstring item 3. Per the user: BMK_0011 is a particle stuck entirely
# inside the via. Sunken residual would normally be expected to pair with matching
# material on the adjacent SiO substrate; here there is none, but ALSO the texture of
# the via-occluding material does not match anything on the adjacent SiO surface --
# those two observations together suggest particle, though the user flags it as a
# genuine edge case, not a clean call.
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

EDGE_CASE_CONTROLS: list[dict[str, str]] = [
    {
        "case_id": "BMK_0011",
        "category": "edge_case_control",
        "gt_class": "particle",
        "folder": "AME417_PM6",
        "stem": "260802_1843_D616521_127_SMP_8M5CL_1055",
        "notes": (
            "User-flagged edge case (2026-08-27): particle sits entirely inside the via. No material of "
            "matching texture appears on the adjacent SiO substrate, and the via-occluding material's texture "
            "does not match the adjacent SiO surface texture -- both point toward particle, but the user "
            "explicitly calls this a genuine edge case, not a clean call. Motivating case for the "
            "sunken_residual texture-correlation fix (see module docstring item 3)."
        ),
    },
]

# The 21 v13 false positives from benchmark_particle25_v13_describe_then_classify_rerun2
# (GT particle, VLM called possible_beep). Folder/stem sourced from
# artifacts/benchmark_pairs_full145.csv. gt_class is always "particle" -- these are all
# GT particle, blocked_etch_evidence noted per-case for reference only.
FP21_CASES: list[dict[str, str]] = [
    {"case_id": "BMK_0003", "category": "fp21_case", "gt_class": "particle", "folder": "AME403_PM3", "stem": "260803_1817_D616465_116_SMP_8M6CL_1541", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
    {"case_id": "BMK_0008", "category": "fp21_case", "gt_class": "particle", "folder": "AME421_PM6", "stem": "260803_1434_D615293_015_SMP_8M5CL_851", "notes": "v13 FP, gt_blocked_etch_evidence=weak (also tested as particle_control BMK_0008)"},
    {"case_id": "BMK_0010", "category": "fp21_case", "gt_class": "particle", "folder": "AME417_PM5", "stem": "260802_1913_D616521_130_SMP_8M5CL_3316", "notes": "v13 FP, gt_blocked_etch_evidence=weak"},
    {"case_id": "BMK_0011", "category": "fp21_case", "gt_class": "particle", "folder": "AME417_PM6", "stem": "260802_1843_D616521_127_SMP_8M5CL_1055", "notes": "v13 FP, gt_blocked_etch_evidence=none (also tested as edge_case_control BMK_0011)"},
    {"case_id": "BMK_0013", "category": "fp21_case", "gt_class": "particle", "folder": "AME409_PM3", "stem": "260803_0736_D617123_020_SMP_8M5CL_83572", "notes": "v13 FP, gt_blocked_etch_evidence=weak"},
    {"case_id": "BMK_0022", "category": "fp21_case", "gt_class": "particle", "folder": "AME421_PM3", "stem": "260802_1234_D619289_844_SMP_8M5CL_361", "notes": "v13 FP, gt_blocked_etch_evidence=weak"},
    {"case_id": "BMK_0023", "category": "fp21_case", "gt_class": "particle", "folder": "AME421_PM4", "stem": "260802_1234_D619289_825_SMP_8M5CL_2056", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
    {"case_id": "BMK_0025", "category": "fp21_case", "gt_class": "particle", "folder": "AME421_PM4", "stem": "260802_1245_D619289_925_SMP_8M5CL_6870", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
    {"case_id": "BMK_0026", "category": "fp21_case", "gt_class": "particle", "folder": "AME421_PM4", "stem": "260802_1245_D619289_925_SMP_8M5CL_7191", "notes": "v13 FP, gt_blocked_etch_evidence=none (Category B candidate per passdown -- particle bridging inter-trench land)"},
    {"case_id": "BMK_0028", "category": "fp21_case", "gt_class": "particle", "folder": "AME411_PM1", "stem": "260801_0610_D617643_053_SMP_8M6CL_38", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
    {"case_id": "BMK_0032", "category": "fp21_case", "gt_class": "particle", "folder": "AME423_PM4", "stem": "260730_0511_D616511_022_SMP_8M6CL_4", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
    {"case_id": "BMK_0033", "category": "fp21_case", "gt_class": "particle", "folder": "AME421_PM6", "stem": "260730_0355_D617643_052_SMP_8M5CL_409", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
    {"case_id": "BMK_0034", "category": "fp21_case", "gt_class": "particle", "folder": "AME421_PM6", "stem": "260730_0355_D617643_052_SMP_8M5CL_657", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
    {"case_id": "BMK_0036", "category": "fp21_case", "gt_class": "particle", "folder": "AME403_PM3", "stem": "260728_2021_D616520_630_SMP_8M6CL_20", "notes": "v13 FP, gt_blocked_etch_evidence=none (the clean triangular particle case from Phase 6 diagnosis)"},
    {"case_id": "BMK_0037", "category": "fp21_case", "gt_class": "particle", "folder": "AME411_PM1", "stem": "260729_1956_D614176_029_SMP_8M5CL_22425", "notes": "v13 FP, gt_blocked_etch_evidence=moderate"},
    {"case_id": "BMK_0038", "category": "fp21_case", "gt_class": "particle", "folder": "AME411_PM1", "stem": "260729_1956_D614176_029_SMP_8M5CL_37681", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
    {"case_id": "BMK_0040", "category": "fp21_case", "gt_class": "particle", "folder": "AME403_PM3", "stem": "260728_2313_D617642_538_SMP_8M5CL_1002", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
    {"case_id": "BMK_0041", "category": "fp21_case", "gt_class": "particle", "folder": "AME403_PM3", "stem": "260728_2313_D617642_538_SMP_8M5CL_1009", "notes": "v13 FP, gt_blocked_etch_evidence=weak"},
    {"case_id": "BMK_0043", "category": "fp21_case", "gt_class": "particle", "folder": "AME403_PM3", "stem": "260728_2313_D617642_538_SMP_8M5CL_1063", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
    {"case_id": "BMK_0044", "category": "fp21_case", "gt_class": "particle", "folder": "AME403_PM3", "stem": "260728_2313_D617642_538_SMP_8M5CL_1074", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
    {"case_id": "BMK_0046", "category": "fp21_case", "gt_class": "particle", "folder": "AME403_PM3", "stem": "260728_2313_D617642_538_SMP_8M5CL_990", "notes": "v13 FP, gt_blocked_etch_evidence=none"},
]

TEST_CASES: list[dict[str, str]] = FN_CASES + PARTICLE_CONTROLS + EDGE_CASE_CONTROLS + FP21_CASES

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 1800

CALL1_PROMPT_V14 = (
    "You are looking at a BEOL SEM defect image pair (brightfield + darkfield) of the same site. "
    "Describe what you see at the defect-comparator/trench junction zone in these images. Focus on: "
    "the defect's position relative to trench or comparator walls, including whether there is a clean "
    "contact line or standoff gap versus wall-continuous or bridging geometry; any geometric "
    "irregularities (asymmetry, shortened or narrowed extent) in the nearest comparator or trench "
    "relative to other similar structures elsewhere in the field; and any material visible inside "
    "features that should otherwise be clear. Also scan the broader field, not just the immediate "
    "junction: if any line trench that should run continuously appears split into two segments by an "
    "intervening bridge of material mid-span, describe the shape of the newly formed edge at each side "
    "of that break -- flat, angled like the side of a parallelogram, or concave/curved -- since this is "
    "more informative than a trench's normal rounded end-cap shape seen at its true ends elsewhere. State "
    "whether that bridging material is the SAME object as the defect you already described at the "
    "immediate junction, or a distinct, separately identifiable region elsewhere in the field. "
    "Also, wherever the defect meets or overlaps an etched feature's edge, trace the etched feature's own "
    "boundary line independently of the defect's outline: state whether that etched-feature boundary "
    "simply collides into and terminates at the defect's own outline (no distortion visible beyond the "
    "meeting point), or whether the etched feature's boundary itself continues past that point with its "
    "own independent distortion (a notch, step, or concavity that is not just the defect's silhouette). "
    "Do NOT describe or rely on trench/comparator interior "
    "tone or darkness differences (one feature appearing lighter, darker, grayer, or less uniform than "
    "another) -- this is a normal lighting/imaging artifact with no established connection to etch or "
    "pre-etch state, and must not be used as evidence of anything. Do not classify the defect as "
    "particle or BEEP. Do not use structured output or JSON. Describe only what is visually present, "
    "in 3-5 sentences.\n\n"
    "After your description, end with exactly one verdict line, on its own line, choosing whichever of "
    "the following three best matches what you described:\n"
    "VERDICT: No blocking evidence observed.\n"
    "VERDICT: Possible blocking evidence -- [one short phrase naming the specific signal].\n"
    "VERDICT: Ambiguous -- blocking evidence cannot be confirmed or excluded."
)

# Unchanged from v13 -- this exact sentence is stripped from the V11 stage_b prompt
# text (it references Stage A, which does not run in this two-call experiment).
_STAGE_A_CONTEXT_SENTENCE = (
    "Use Stage A substrate context as prior. Note: when Stage A flags offset_surface_lines "
    "as a background confounder, that refers to substrate field texture away from the defect "
    "\u2014 always independently assess the defect boundary for blocking evidence regardless of that flag. "
)

_CLASSIFIER_INTRO = (
    "You are a BEOL SEM defect classifier distinguishing particle contamination from "
    "pre-etch blocking events (possible BEEP). "
)

# V11's original PATHWAY 1 text -- replaced because it scores substrate occupancy from
# a bare trench/comparator tone-darkness comparison, which is exactly the artifact the
# user flagged as unreliable (light-source angle/position dependent, no established
# connection to etch state).
_PATHWAY1_TONAL_FILL_TEXT = (
    "PATHWAY 1 \u2014 TONAL FILL: Identify at least one unaffected reference trench or comparator of the same "
    "type elsewhere in the image. Compare the interior tone/darkness of the trench or comparator immediately "
    "adjacent to the defect against this reference. If the adjacent feature interior is measurably lighter, "
    "grayer, or less uniformly dark than the reference, substrate occupancy is indicated. State which "
    "reference was used and what tonal difference was or was not observed. "
)

_PATHWAY1_MATERIAL_PRESENCE_TEXT = (
    "PATHWAY 1 \u2014 SUBSTRATE MATERIAL PRESENCE (tone/darkness alone is NOT evidence, and the material must "
    "be distinguishable from the defect's own body): Identify whether a discrete, bounded patch of foreign "
    "material is visible occupying space inside a comparator or trench where the interior should otherwise "
    "be clear open field. This must be a specific, locatable material patch \u2014 not a general brightness, "
    "grayness, or darkness difference in the trench compared with reference trenches. Trench-to-trench or "
    "via-to-via interior tone/darkness variation (one feature appearing lighter, darker, or less uniform than "
    "another) is a normal lighting/imaging artifact driven by light-source angle and position and has no "
    "established connection to etch or pre-etch state \u2014 do not score this pathway from tone/darkness "
    "comparison alone, and do not cite tonal differences as evidence. CRITICAL: if the 'material occupying "
    "the trench' is simply the visible defect/particle body itself sitting in that space, that is the "
    "defect's own footprint, not independent substrate occupancy, and does NOT count -- a particle sitting "
    "inside a trench will always look like 'material in the trench' by definition, so this alone proves "
    "nothing. Score yes only if you can identify material inside the recessed region that is a separate, "
    "distinguishable region from the main defect body -- for example a distinct texture, a residue trail "
    "extending beyond the defect's own outline, or material visible in a portion of the trench the defect "
    "body does not itself cover. State what specific material patch was observed and how it is distinguished "
    "from the defect's own body, or state explicitly that the only 'material' present is the defect body "
    "itself (which does not count). "
)

# V11's original PATHWAY 3 text -- had the same occlusion blind spot as Pathways 2/4/5
# and boundary_conformance: a particle simply covering/occluding part of a feature makes
# that feature LOOK shorter/narrower without any actual etch-time blocking having
# occurred. BMK_0040 exposed this: Pathway 1 (rewritten) and Pathway 3 (unrewritten)
# were the last two pathways still scoring yes on defect-occlusion alone.
_PATHWAY3_OLD_TEXT = (
    "PATHWAY 3 \u2014 DIMENSIONAL DEFICIT: Identify the specific comparator or via adjacent to the defect and "
    "at least two same-type reference features elsewhere in the image. Compare size, length, and width "
    "directly. A comparator that is measurably smaller, shorter, or narrower than its peers indicates partial "
    "blocking during etch. State which comparator and references were examined and describe the size "
    "comparison explicitly. "
)

_PATHWAY3_NEW_TEXT = (
    "PATHWAY 3 \u2014 DIMENSIONAL DEFICIT (must not be explained by the defect simply occluding the feature): "
    "Identify the specific comparator or via adjacent to the defect and at least two same-type reference "
    "features elsewhere in the image. Compare size, length, and width directly. Before scoring yes, determine "
    "whether the apparent shortening or narrowing is fully explained by the visible defect covering or "
    "occluding part of the feature from view -- if the feature would appear normal-length/normal-width but "
    "for the defect sitting on or across part of it, that is occlusion by the defect, not a true dimensional "
    "deficit from blocked etch, and does NOT count; score no or unclear in that case. Only score yes if the "
    "feature's own etched boundary -- independent of where the defect happens to sit -- is measurably "
    "smaller, shorter, or narrower than its peers, i.e. the etched endpoint itself is displaced, not merely "
    "hidden behind the defect. State which comparator and references were examined, describe the size "
    "comparison explicitly, and state whether the apparent deficit is occlusion-explained or genuinely tied "
    "to the feature's own boundary. "
)


def _add_boundary_ownership_check(base: str) -> str:
    replacements = (
        (_PATHWAY2_OLD_TEXT, _PATHWAY2_NEW_TEXT),
        (_PATHWAY3_OLD_TEXT, _PATHWAY3_NEW_TEXT),
        (_PATHWAY4_OLD_TEXT, _PATHWAY4_NEW_TEXT),
        (_SOURCE_DISCRIMINATION_OLD_TEXT, _SOURCE_DISCRIMINATION_NEW_TEXT),
        (_BOUNDARY_CONFORMANCE_OLD_TEXT, _BOUNDARY_CONFORMANCE_NEW_TEXT),
    )
    for old, new in replacements:
        if old not in base:
            raise RuntimeError(
                f"V11 stage_b prompt text {old[:60]!r}... no longer found -- update "
                "_add_boundary_ownership_check() in this script to match "
                "config/stage_ab_prompt_tests_substrate_tier1_v11.json before proceeding."
            )
        base = base.replace(old, new, 1)
    return base


# NEW pathway, not present in V11 -- per user domain feedback on BMK_0029 (2026-08-27):
# a trench that should run continuously can be split mid-span by a bridge of blocking
# material, distinct from a simple end-of-trench asymmetry (Pathway 2). The cut edges
# at the break show non-native shapes (flat, angled/parallelogram, concave) instead of
# the trench's normal rounded end-cap. This is purely geometric -- not tone/darkness --
# and is assessable across the whole field, not just at the defect's immediate junction.
_PATHWAY5_MID_SPAN_BRIDGING_TEXT = (
    "PATHWAY 5 \u2014 MID-SPAN TRENCH BRIDGING (etched-feature cut edges only, not the visible defect's own "
    "footprint): Look beyond the immediate defect-junction zone at the broader field. Identify any line "
    "trench that should run continuously across the field, based on comparable unbroken trenches of the "
    "same row or orientation elsewhere in the image, but instead appears split into two segments by an "
    "intervening bridge crossing it mid-span, not only at its terminal ends. First determine whether the "
    "material spanning the break is the SAME visible defect body already being assessed at its immediate "
    "junction, or a distinct, separately identifiable region. If the break is simply the visible defect's "
    "own body sitting across or overlapping the trench, apply the same boundary-ownership check used in "
    "Pathway 2 and Pathway 4: only score yes if BOTH cut edges show the etched feature's own boundary "
    "continuing with independent distortion beyond where it meets the defect's outline -- do not count the "
    "defect's own footprint crossing the trench as bridging evidence by itself; that is the same single "
    "observation as Pathway 2/4's wall-contact geometry, not a separate signature. If the break is instead "
    "caused by a distinct, separately identifiable bridge of material not explained by the visible defect's "
    "own outline alone (for example, the defect body sits elsewhere in the field and the bridge material's "
    "boundary is clearly independent of the defect's outline), then examine the shape of the newly formed "
    "edge on each side of the break: a trench's natural end, at the true pattern boundary, has a uniform "
    "rounded end-cap matching other true ends elsewhere; a genuine separate bridge instead produces a flat, "
    "angled (parallelogram-like), or concave/curved cut edge that does not match that natural end-cap shape, "
    "and this counts as independent substrate-occupancy evidence. State which trench(es) show the break, "
    "whether the bridging material is the same object as the visible defect or a distinct region, and "
    "describe the cut-edge shape(s) observed, or state explicitly that no such break was found. "
)

_FOUR_TO_FIVE_REPLACEMENTS = (
    (
        "Assess all four pathways independently and explicitly.",
        "Assess all five pathways independently and explicitly.",
    ),
    (
        "Score no only if all four pathways are explicitly assessed and negative after source discrimination.",
        "Score no only if all five pathways are explicitly assessed and negative after source discrimination.",
    ),
    (
        "Pathway 2 and Pathway 4 remain executable on visible boundary zones.",
        "Pathway 2, Pathway 4, and Pathway 5 remain executable on visible boundary zones and elsewhere in the field.",
    ),
)

_PATHWAY4_TAIL_ANCHOR = (
    "These are independent checks on the same geometric feature and should each be scored accordingly. "
    "SOURCE DISCRIMINATION"
)


def _add_mid_span_bridging_pathway(base: str) -> str:
    if _PATHWAY4_TAIL_ANCHOR not in base:
        raise RuntimeError(
            "V11 stage_b prompt's end-of-Pathway-4 text no longer matches the expected wording -- update "
            "_PATHWAY4_TAIL_ANCHOR in this script to match "
            "config/stage_ab_prompt_tests_substrate_tier1_v11.json before proceeding."
        )
    base = base.replace(
        _PATHWAY4_TAIL_ANCHOR,
        _PATHWAY4_TAIL_ANCHOR.replace("SOURCE DISCRIMINATION", "") + _PATHWAY5_MID_SPAN_BRIDGING_TEXT + "SOURCE DISCRIMINATION",
        1,
    )
    for old, new in _FOUR_TO_FIVE_REPLACEMENTS:
        if old not in base:
            raise RuntimeError(
                f"V11 stage_b prompt text {old!r} no longer found -- update _FOUR_TO_FIVE_REPLACEMENTS in "
                "this script to match config/stage_ab_prompt_tests_substrate_tier1_v11.json before proceeding."
            )
        base = base.replace(old, new, 1)
    return base


# NEW domain-feedback fix (2026-08-28): the 21-FP-set re-run showed Pathway 1's fix
# wasn't enough -- Pathway 2 (Geometric Asymmetry) and Pathway 4 (Wall Continuity) were
# still scoring yes/yes on ordinary wall-adjacent particles (BMK_0025, BMK_0032,
# BMK_0036, BMK_0038, BMK_0040, BMK_0043). Per the user: in each of these, the "etched
# feature boundary" the model is scoring as asymmetric/wall-continuous is actually just
# the particle's OWN boundary -- the true etched-feature edge simply collides into /
# terminates cleanly at the particle's outline, with no independent distortion of the
# feature's own edge beyond that meeting point. Both pathways are rewritten to require
# tracing the etched feature's boundary independently of the defect's outline, and
# SOURCE DISCRIMINATION gets a new item (e) codifying this as a disqualifying explanation.
_PATHWAY2_OLD_TEXT = (
    "PATHWAY 2 \u2014 GEOMETRIC ASYMMETRY: Identify the specific comparator or via adjacent to the defect and "
    "a same-type reference feature elsewhere in the image. Compare boundary shapes directly. A comparator "
    "showing asymmetric boundaries \u2014 one side normally convex and rounded, the opposing side concave, "
    "flattened, or indented \u2014 indicates substrate material present where etch should have cleared it. "
    "State which comparator and reference were examined and describe the boundary shape comparison "
    "explicitly. "
)

_PATHWAY2_NEW_TEXT = (
    "PATHWAY 2 \u2014 GEOMETRIC ASYMMETRY (etched-feature boundary only, not the defect's own outline): "
    "Identify the specific comparator or via adjacent to the defect and a same-type reference feature "
    "elsewhere in the image. Trace the ETCHED FEATURE's own boundary line -- the trench or via edge, "
    "independent of the defect -- out to the point where it meets the defect. If that etched-feature "
    "boundary simply runs cleanly into and terminates at the defect's own outline, with no distortion of "
    "the etched feature's true edge visible beyond that meeting point, the apparent asymmetry is fully "
    "explained by the particle's boundary, not the etched feature's boundary, and does NOT count -- this "
    "pathway must be scored no or unclear, never yes, in that situation. Only score yes if the etched "
    "feature's own boundary itself shows independent distortion -- a notch, step, flattening, or "
    "concavity in the trench/via edge -- that is not merely the collision point where the defect's "
    "outline meets it. State which comparator and reference were examined, describe exactly where the "
    "etched-feature boundary meets the defect, and state explicitly whether that boundary continues past "
    "the meeting point with independent distortion or simply terminates at the defect's outline. "
)

_PATHWAY4_OLD_TEXT = (
    "PATHWAY 4 \u2014 WALL CONTINUITY: Identify the specific zone where the defect contacts or originates at "
    "the trench or comparator wall. Examine that junction zone explicitly \u2014 do not assess wall "
    "continuity from the defect body alone. Is there edge line continuity, shared boundary geometry, or "
    "layer continuity between the defect material and the trench wall implying they are continuous rather "
    "than separate? A particle resting against a wall shows a clean contact line or separation; a blocking "
    "event may show wall-continuous geometry where defect and trench wall share a boundary without "
    "interruption. Note: Pathway 4 is assessable even when the defect occludes comparator interiors \u2014 "
    "the junction zone is on the defect perimeter, not inside the trench. Occlusion of the trench interior "
    "does not prevent wall continuity assessment. Describe what is visible at the junction zone before "
    "scoring. "
)

_PATHWAY4_NEW_TEXT = (
    "PATHWAY 4 \u2014 WALL CONTINUITY (etched-feature boundary only, not the defect's own outline): Identify "
    "the specific zone where the defect contacts or originates at the trench or comparator wall. Examine "
    "that junction zone explicitly \u2014 do not assess wall continuity from the defect body alone. Trace "
    "the etched feature's own wall line out to the contact point: if the wall simply collides into or "
    "terminates cleanly at the defect's own outline, with no continuation of a distorted or displaced wall "
    "line beyond that point, this is a particle resting against or occluding the wall, not wall continuity "
    "-- score no or unclear, never yes, in that situation. Only score yes if the trench or comparator wall "
    "itself shows edge line continuity, shared boundary geometry, or layer continuity with the defect "
    "material that extends BEYOND the simple collision point -- i.e., the wall's own path is altered by "
    "material presence, not just terminated by an object sitting next to or on top of it. A particle "
    "resting against a wall shows a clean contact line where the wall boundary and particle boundary "
    "simply meet and coincide; a blocking event shows the wall's own boundary continuing into or merging "
    "with the defect material in a way not explained by particle placement alone. Note: Pathway 4 is "
    "assessable even when the defect occludes comparator interiors \u2014 the junction zone is on the "
    "defect perimeter, not inside the trench. Occlusion of the trench interior does not prevent wall "
    "continuity assessment. Describe what is visible at the junction zone before scoring, explicitly "
    "stating whether the wall boundary and defect boundary are simply coincident/colliding, or whether the "
    "wall boundary shows independent distortion beyond that point. "
)

_SOURCE_DISCRIMINATION_OLD_TEXT = (
    "(d) a narrow standoff gap between the particle and trench wall. None of these constitute substrate "
    "occupancy inside the trench. "
)

_SOURCE_DISCRIMINATION_NEW_TEXT = (
    "(d) a narrow standoff gap between the particle and trench wall, or (e) the etched feature's own "
    "boundary simply colliding into or terminating at the defect's outline, with no independent distortion "
    "of the feature's true edge visible beyond that meeting point -- meaning the apparent asymmetry or "
    "continuity is fully explained by the particle's boundary, not the etched feature's boundary. None of "
    "these constitute substrate occupancy inside the trench. "
)

# V11's original evidence_check_boundary_conformance text (the top-level check, distinct
# from ISL Pathway 4) -- had the exact same blind spot: it scored yes whenever the
# defect's geometry looked "tied to" a boundary, without distinguishing the etched
# feature's own boundary from the defect's own outline. BMK_0032 exposed this directly:
# Pathway 4 correctly scored no ("wall lines themselves do not visibly continue beyond
# the collision") while boundary_conformance scored yes for the identical geometry.
_BOUNDARY_CONFORMANCE_OLD_TEXT = (
    "2. evidence_check_boundary_conformance Examine each edge of the defect where it meets or abuts a "
    "comparator or trench boundary. Is the main geometry aligned to the boundary in a way that suggests "
    "pre-etch blocking, even if a small portion of the defect juts slightly into the comparator? A small "
    "overhang or slight extension into the comparator can still be compatible with BEEP if the dominant "
    "boundary-following shape is clear. A practical rule of thumb is that a minor intrusion, on the order of "
    "roughly 15% of the conforming extent normal to the boundary, can still count as boundary conformance. "
    "Approximate, drifting, or coincidence-like edges do not qualify. Score yes when the geometry is "
    "meaningfully tied to the boundary rather than simply resting nearby. Note: if the defect edge tracks or "
    "runs co-linear with a trench wall, also assess this observation under ISL Pathway 4. "
)

_BOUNDARY_CONFORMANCE_NEW_TEXT = (
    "2. evidence_check_boundary_conformance (etched-feature boundary only, not the defect's own outline) "
    "Examine each edge of the defect where it meets or abuts a comparator or trench boundary. Apply the same "
    "boundary-ownership check used in ISL Pathway 2/4: trace the etched feature's own boundary line "
    "independently of the defect's outline. If that etched-feature boundary simply collides into and "
    "terminates at the defect's own outline, with no distortion of the feature's true edge continuing "
    "beyond that meeting point, the geometry is fully explained by the defect resting against or over the "
    "boundary -- this does NOT count as boundary conformance, no matter how large the overlap or how aligned "
    "it looks. Only score yes if the etched feature's own boundary line can be traced continuing along or "
    "merging with the defect over a meaningful extent, independent of the defect's own outline. A small "
    "overhang or slight extension into the comparator can still be compatible with BEEP if that dominant "
    "boundary-following shape belongs to the etched feature's own edge, not merely the defect's edge -- a "
    "practical rule of thumb is that a minor intrusion, on the order of roughly 15% of the conforming extent "
    "normal to the boundary, can still count, as long as it is the feature's own boundary being traced. "
    "Approximate, drifting, or coincidence-like edges do not qualify. Note: if the defect edge tracks or runs "
    "co-linear with a trench wall AND that wall's own boundary shows independent distortion beyond the "
    "collision point, also assess this observation under ISL Pathway 4. "
)


# V11's original evidence_check_sunken_residual text -- augmented with a texture
# correlation requirement per the BMK_0011 domain feedback (see module docstring item 3).
_SUNKEN_RESIDUAL_TEXT = (
    "3. evidence_check_sunken_residual Is material visible recessed inside a comparator or trench below the "
    "surface level, with tone or contrast that differs from the surface defect? This is usually a secondary "
    "clue. In most cases, it should be accompanied by a comparator boundary line or by a boundary-linked fade "
    "from lighter to darker shading as you move away from the boundary and into the trench. Do not score yes "
    "when the defect is fully contained within a comparator and there is no defect material directly visible "
    "outside the comparator boundary; in that case, the feature is usually a particle and sunken_residual "
    "should be no or unclear, not yes. A weak boundary line can be reinforced by sunken residual, but sunken "
    "residual alone is not enough to establish BEEP. Score yes if present at any scale and tied to "
    "boundary-linked geometry. Score unclear if a tonal shift is suggested but cannot be confirmed. "
)

_SUNKEN_RESIDUAL_TEXTURE_CHECK_TEXT = (
    "3. evidence_check_sunken_residual Is material visible recessed inside a comparator or trench below the "
    "surface level, with tone or contrast that differs from the surface defect? This is usually a secondary "
    "clue. In most cases, it should be accompanied by a comparator boundary line or by a boundary-linked fade "
    "from lighter to darker shading as you move away from the boundary and into the trench. TEXTURE "
    "CORRELATION CHECK: genuine sunken residual is normally paired with visible material of matching texture "
    "lying adjacent to the feature on the surrounding SiO substrate, outside the comparator boundary. Before "
    "scoring yes, compare the texture of the material occupying/occluding the recessed feature against the "
    "texture of any material visible on the adjacent substrate. Inset surface lines can legitimately occur "
    "inside a feature with no material at all showing on the adjacent substrate \u2014 that absence alone does "
    "not rule out sunken_residual. However, if there IS a material patch inside the recessed feature and its "
    "texture does NOT match anything on the adjacent substrate, that texture mismatch is itself a signal "
    "favoring particle over sunken residual and should be stated explicitly in the rationale. Do not score yes "
    "when the defect is fully contained within a comparator and there is no defect material directly visible "
    "outside the comparator boundary; in that case, the feature is usually a particle and sunken_residual "
    "should be no or unclear, not yes. A weak boundary line can be reinforced by sunken residual, but sunken "
    "residual alone is not enough to establish BEEP. Score yes if present at any scale, tied to boundary-linked "
    "geometry, and not contradicted by a texture mismatch as described above. Score unclear if a tonal shift is "
    "suggested but cannot be confirmed. "
)


def _load_v11_stage_b_prompt() -> str:
    cfg = json.loads(V11_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    return cfg["stage_b"]["prompt"]


def _neutralize_tonal_darkness_pathway(base: str) -> str:
    if _PATHWAY1_TONAL_FILL_TEXT not in base:
        raise RuntimeError(
            "V11 stage_b prompt's PATHWAY 1 (TONAL FILL) text no longer matches the expected wording -- "
            "update _PATHWAY1_TONAL_FILL_TEXT in this script to match "
            "config/stage_ab_prompt_tests_substrate_tier1_v11.json before proceeding."
        )
    return base.replace(_PATHWAY1_TONAL_FILL_TEXT, _PATHWAY1_MATERIAL_PRESENCE_TEXT, 1)


def _add_sunken_residual_texture_check(base: str) -> str:
    if _SUNKEN_RESIDUAL_TEXT not in base:
        raise RuntimeError(
            "V11 stage_b prompt's evidence_check_sunken_residual text no longer matches the expected wording -- "
            "update _SUNKEN_RESIDUAL_TEXT in this script to match "
            "config/stage_ab_prompt_tests_substrate_tier1_v11.json before proceeding."
        )
    return base.replace(_SUNKEN_RESIDUAL_TEXT, _SUNKEN_RESIDUAL_TEXTURE_CHECK_TEXT, 1)


def _build_call2_prompt_v14(observation: str) -> str:
    base = _load_v11_stage_b_prompt()
    base = base.replace(_STAGE_A_CONTEXT_SENTENCE, "")
    base = _neutralize_tonal_darkness_pathway(base)
    base = _add_sunken_residual_texture_check(base)
    base = _add_mid_span_bridging_pathway(base)
    base = _add_boundary_ownership_check(base)

    observation_block = (
        "A separate observation pass already examined this image pair's defect-junction zone, with no "
        "classification bias, and wrote the following description. Its VERDICT line indicated possible or "
        "ambiguous blocking evidence, which is why full pathway assessment is running:\n\n"
        f'"""\n{observation.strip()}\n"""\n\n'
        "Use this observation together with the images as supporting evidence, but verify each evidence check "
        "directly against the images yourself -- do not simply restate the observation's wording. "
    )
    if _CLASSIFIER_INTRO not in base:
        raise RuntimeError(
            "V11 stage_b prompt text no longer starts with the expected classifier intro sentence -- update "
            "_CLASSIFIER_INTRO in this script to match config/stage_ab_prompt_tests_substrate_tier1_v11.json "
            "before proceeding."
        )
    return base.replace(_CLASSIFIER_INTRO, _CLASSIFIER_INTRO + observation_block, 1)


_VERDICT_RE = re.compile(r"VERDICT:\s*(.+)", re.IGNORECASE)


def _parse_call1_verdict(call1_text: str | None) -> str:
    """Returns 'no_evidence', 'possible', 'ambiguous', or 'missing' (unparseable -- treated as ambiguous by callers, fail open rather than silently suppressing)."""
    matches = _VERDICT_RE.findall(call1_text or "")
    if not matches:
        return "missing"
    verdict_text = matches[-1].strip().lower()
    if verdict_text.startswith("no blocking evidence"):
        return "no_evidence"
    if verdict_text.startswith("possible blocking evidence"):
        return "possible"
    if verdict_text.startswith("ambiguous"):
        return "ambiguous"
    return "missing"


def _particle_gate_result(verdict_line: str) -> dict[str, Any]:
    return {
        "evidence_check_inset_surface_lines": "no",
        "evidence_check_boundary_conformance": "no",
        "evidence_check_sunken_residual": "no",
        "defect_coarse_class": "particle",
        "blocked_etch_evidence": "none",
        "confidence": 0.9,
        "review_required": False,
        "particle_location": "unknown",
        "trench_interaction": "none",
        "morphology_summary": "Hard-gated: Call 1 reported no blocking evidence.",
        "rationale": f"Hard-gated on Call 1 verdict ({verdict_line!r}); pathway assessment was not run.",
        "metadata_alignment": "unknown",
    }


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
    call1_parsed, call1_text, call1_usage = _call_image([bf, df], CALL1_PROMPT_V14, model, max_completion_tokens)
    verdict = _parse_call1_verdict(call1_text)

    gated = verdict == "no_evidence"
    if gated:
        call2_prompt = "<hard-gated: Call 2 skipped, particle template returned -- see _particle_gate_result>"
        call2_result: dict[str, Any] | None = _particle_gate_result(verdict)
        call2_text = json.dumps(call2_result)
        call2_usage = None
    else:
        call2_prompt = _build_call2_prompt_v14(call1_text)
        call2_result, call2_text, call2_usage = _call_image([bf, df], call2_prompt, model, max_completion_tokens)
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
        "call1_verdict": verdict,
        "call1_usage": call1_usage,
        "gated": gated,
        "call2_prompt_chars": len(call2_prompt),
        "call2_parsed": call2_result if isinstance(call2_result, dict) else None,
        "call2_raw_text": call2_text,
        "call2_usage": call2_usage,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="v14 verdict-gate probe: Call 1 free observation + VERDICT line -> hard gate or "
        "V11-derived Call 2 (tonal/darkness pathway neutralized, sunken-residual texture check added)."
    )
    parser.add_argument(
        "--cases", default="all", help="Comma-separated case_ids to run, or 'all' (default: 5 FN + 4 particle controls + BMK_0011)."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-completion-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSONL path (default: outputs/probes/describe_then_classify_v14_<UTC timestamp>.jsonl).",
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
        output_path = alloy_class_root / "outputs" / "probes" / f"describe_then_classify_v14_{stamp}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    call_count = 0
    with output_path.open("w", encoding="utf-8") as out_f:
        for case in cases:
            bf, df = _pair_paths(case)
            if not bf.is_file() or not df.is_file():
                print(f"SKIP {case['case_id']}: missing image file(s) ({bf}, {df})", file=sys.stderr)
                continue

            record = _run_case(case, args.model, args.max_completion_tokens)
            call_count += 1 if record["gated"] else 2
            out_f.write(json.dumps(record) + "\n")

            call2 = record["call2_parsed"] or {}
            isl = call2.get("evidence_check_inset_surface_lines", "?")
            bc = call2.get("evidence_check_boundary_conformance", "?")
            cls = call2.get("defect_coarse_class", "?")
            gate_flag = "GATED" if record["gated"] else "ran-call2"
            print(
                f"{case['case_id']} [{case['category']}, gt={case['gt_class']}]: "
                f"verdict={record['call1_verdict']} ({gate_flag}) ISL={isl} BC={bc} class={cls}"
            )

    print(f"\nDone. {call_count} VLM calls across {len(cases)} cases. Results written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
