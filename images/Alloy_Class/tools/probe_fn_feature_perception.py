"""
Ad hoc, low-load diagnostic probe for the 5 known FN (false-negative) cases from the
v12 offset-surface-lines benchmark (see docs/v12_post_mortem.md and agents_history
checkpoint 2026-08-26_001).

Each FN case is submitted directly (BF+DF pair, free text, no Stage A context, no
JSON output contract) with a plain observational prompt (variant p1) and a narrow
yes/no+describe prompt naming the specific missed feature (variant p2). Optionally,
variant p3 repeats p2 against a raw/unburned image (requires the SecureFTP runtime).

This isolates whether the pipeline's current miss is a framing/overhead problem
(Stage A dilution, JSON-contract verbosity, multi-image call) or a genuine
visual-perception ceiling, before committing to crop/FFT or model-upgrade work.

Intentionally NOT wired into the scored benchmark pipeline -- throwaway/ad hoc,
per /memories/session/plan.md.
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
    DEFAULT_GAJT_DLL_SEARCH_PATHS,
    DEFAULT_RAW_MANIFEST,
    _call_image,
    _download_raw_image_to_temp,
    _load_env_from_supported_locations,
    _load_image_manifest_index,
)

IMAGES_ROOT = Path(
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\defects"
)

# The 5 known FN cases from outputs/raw_runs/offset_surface_lines_15_v12_compare
# (ground truth possible_beep, pipeline called particle).
FN_CASES: list[dict[str, str]] = [
    {
        "case_id": "BMK_0050",
        "split": "tune",
        "folder": "AME403_PM4",
        "stem": "260728_2212_D617642_539_BEEP_8M5CL_916",
        "missed_feature": "narrow wall continuity or a concave terminus at the trench-comparator junction",
    },
    {
        "case_id": "BMK_0029",
        "split": "tune",
        "folder": "AME417_PM2",
        "stem": "260801_0609_D618239_604_BEEP_8M6CL_1032",
        "missed_feature": "a dark flanking void adjacent to the defect-wall contact point",
    },
    {
        "case_id": "BMK_0009",
        "split": "tune",
        "folder": "AME417_PM5",
        "stem": "260802_1913_D616521_130_SMP_8M5CL_3110",
        "missed_feature": "a crescent-shaped area of substrate material occupying the comparator interior",
    },
    {
        "case_id": "BMK_0005",
        "split": "tune",
        "folder": "AME401_PM1",
        "stem": "260803_1754_D616533_204_SMP_8M6CL_3139",
        "missed_feature": "bridging material spanning across the trench wall at the contact point",
    },
    {
        "case_id": "BMK_0001",
        "split": "eval",
        "folder": "AME403_PM3",
        "stem": "260803_1800_D616465_064_SMP_8M6CL_10911",
        "missed_feature": "an interruption in the trench wall's edge line exactly where the defect meets it",
    },
]

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 1800  # raised from 400 per Phase 1 finding: 25% empty-response rate at 400 vs 0% at 1800

P1_PROMPT = (
    "You are looking at a BEOL SEM defect image pair (brightfield + darkfield) of the same "
    "site. Ignore defect classification entirely -- do not decide particle vs. BEEP. Look "
    "closely and only at the exact zone where the defect touches or crosses the trench or "
    "comparator wall. In plain language, describe precisely what the wall boundary looks like "
    "at that contact point: its shape, its continuity (is it interrupted or fully intact?), "
    "and whether any material appears to occupy the wall or trench interior there. Describe "
    "only what you visually observe, in 2-4 sentences."
)


def p2_prompt(missed_feature: str) -> str:
    return (
        "Look closely at the exact zone where the defect contacts or crosses the trench or "
        f"comparator wall in this image pair. Specifically: do you see {missed_feature}? "
        "Answer with a direct yes / no / unclear first, then describe in 1-2 sentences exactly "
        "what you observe at that contact point that supports your answer."
    )


def _pair_paths(case: dict[str, str]) -> tuple[Path, Path]:
    folder = IMAGES_ROOT / case["folder"]
    bf = folder / f"{case['stem']}_2.jpg"
    df = folder / f"{case['stem']}_3.jpg"
    return bf, df


def _raw_pair_paths(
    case: dict[str, str],
    bf: Path,
    df: Path,
    manifest_index: dict[str, dict[str, str]],
    raw_temp_dir: Path,
    raw_app_name: str,
    raw_technology: str,
    gajt_dll_search_paths: list[str],
) -> tuple[Path | None, Path | None, dict[str, str]]:
    status: dict[str, str] = {}
    raw_paths: list[Path | None] = []
    for staged in (bf, df):
        row = manifest_index.get(staged.name.lower())
        if row is None:
            status[staged.name] = "manifest_row_not_found"
            raw_paths.append(None)
            continue
        raw_path, info = _download_raw_image_to_temp(
            row, raw_temp_dir, raw_app_name, raw_technology, gajt_dll_search_paths
        )
        status[staged.name] = info.get("raw_download_status", "unknown")
        raw_paths.append(raw_path)
    return raw_paths[0], raw_paths[1], status


def _run_call(
    case_id: str,
    variant: str,
    missed_feature: str,
    prompt: str,
    bf: Path,
    df: Path,
    model: str,
    max_completion_tokens: int,
) -> dict[str, Any]:
    _parsed, output_text, usage = _call_image([bf, df], prompt, model, max_completion_tokens)
    return {
        "case_id": case_id,
        "variant": variant,
        "missed_feature": missed_feature,
        "prompt": prompt,
        "bf_image": str(bf),
        "df_image": str(df),
        "model": model,
        "response_text": output_text,
        # Surfaced from usage for quick inspection; full detail still in "usage" below.
        "usage_source": usage.get("usage_source"),
        "error_class": usage.get("error_class"),
        "empty_response": usage.get("empty_response"),
        "response_char_count": usage.get("response_char_count"),
        "finish_reason": usage.get("finish_reason"),
        "usage": usage,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Low-load FN feature-perception probe on the 5 known v12 FN cases."
    )
    parser.add_argument("--cases", default="all", help="Comma-separated case_ids to run, or 'all' (default).")
    parser.add_argument(
        "--variants", default="p1,p2", help="Comma-separated variants to run: p1,p2,p3 (default p1,p2)."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-completion-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSONL path (default: outputs/probes/fn_feature_probe_<UTC timestamp>.jsonl).",
    )
    parser.add_argument("--raw-manifest-csv", default=DEFAULT_RAW_MANIFEST, help="Manifest CSV for variant p3.")
    parser.add_argument("--raw-temp-dir", default="./outputs/probes/raw_temp", help="Temp dir for variant p3 downloads.")
    parser.add_argument("--raw-app-name", default="GAJT_INLINE_24601", help="SecureFTP app name for variant p3.")
    parser.add_argument("--raw-technology", default="1278", help="Technology token for variant p3 datasource naming.")
    args = parser.parse_args()

    _load_env_from_supported_locations()

    requested_ids = None if args.cases == "all" else {c.strip() for c in args.cases.split(",")}
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]

    cases = [c for c in FN_CASES if requested_ids is None or c["case_id"] in requested_ids]
    if not cases:
        raise SystemExit(f"No matching cases for --cases {args.cases!r}")

    if args.output:
        output_path = Path(args.output)
    else:
        alloy_class_root = Path(__file__).resolve().parents[1]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = alloy_class_root / "outputs" / "probes" / f"fn_feature_probe_{stamp}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_index: dict[str, dict[str, str]] = {}
    if "p3" in variants:
        manifest_index = _load_image_manifest_index(Path(args.raw_manifest_csv))

    call_count = 0
    with output_path.open("w", encoding="utf-8") as out_f:
        for case in cases:
            bf, df = _pair_paths(case)
            if not bf.is_file() or not df.is_file():
                print(f"SKIP {case['case_id']}: missing image file(s) ({bf}, {df})", file=sys.stderr)
                continue

            for variant in variants:
                if variant == "p1":
                    prompt, use_bf, use_df = P1_PROMPT, bf, df
                elif variant == "p2":
                    prompt, use_bf, use_df = p2_prompt(case["missed_feature"]), bf, df
                elif variant == "p3":
                    raw_bf, raw_df, status = _raw_pair_paths(
                        case, bf, df, manifest_index, Path(args.raw_temp_dir),
                        args.raw_app_name, args.raw_technology, DEFAULT_GAJT_DLL_SEARCH_PATHS,
                    )
                    if raw_bf is None or raw_df is None:
                        print(f"SKIP {case['case_id']} / p3: raw image unavailable ({status})", file=sys.stderr)
                        continue
                    prompt, use_bf, use_df = p2_prompt(case["missed_feature"]), raw_bf, raw_df
                else:
                    print(f"SKIP unknown variant {variant!r}", file=sys.stderr)
                    continue

                record = _run_call(
                    case["case_id"], variant, case["missed_feature"], prompt,
                    use_bf, use_df, args.model, args.max_completion_tokens,
                )
                call_count += 1
                out_f.write(json.dumps(record) + "\n")
                print(f"[{call_count}] {case['case_id']} / {variant}: {record['response_text'][:160]!r}")

    print(f"\nDone. {call_count} VLM calls. Results written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
