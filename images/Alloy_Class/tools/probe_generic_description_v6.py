"""
probe_generic_description_v6.py
--------------------------------
v6 of the SMALL_PARTICLE generic-description pilot, built from
Particle_Descriptors_v6_canonical.txt:

1. coarse_texture "flat" removed -- never called across v2-v5 (0/40 every run).
2. texture_layered / texture_interior_striation / texture_fractured given three
   clearly distinct one-line trigger definitions (previously interior_striation had
   no explicit definition at all, and layered/fractured overlapped in wording):
   layered = a line following a boundary/edge, interior_striation = a straight line,
   fractured = an actual gap/break (now "one to three parts", down from "two to four").
3. location_relative wording restructured to separate the enum list from its
   explanation -- a v5 case (SMP_PILOT_013) returned the literal phrase "touches
   without crossing" instead of a valid enum value, because the model echoed a
   phrase from the definition text itself rather than picking one of the four
   allowed words.

Uses the SAME pilot manifest as v1-v5 (not a fresh sample) so all runs are directly
apples-to-apples comparable on the same 40 cases.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ALLOY_CLASS_DIR = Path(__file__).resolve().parents[1]
for _subdir in ("reporting", "pipelines"):
    _path = _ALLOY_CLASS_DIR / _subdir
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from run_stage_ab_prompt_tests import (  # type: ignore  # noqa: E402
    _call_image,
    _load_env_from_supported_locations,
)
from classify_phase1_batch import (  # type: ignore  # noqa: E402
    RawImageConfig,
    DEFAULT_GAJT_DLL_SEARCH_PATHS,
    _download_raw_image_to_temp,
)

DEFAULT_PILOT_MANIFEST = (
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson"
    r"\Defects\BE\images\Alloy_Class\outputs\probes\generic_description_pilot_manifest.csv"
)
# Must be a short local path -- staging_root/<full IMAGE_FILESPEC> otherwise exceeds MAX_PATH (260 chars) on Windows.
DEFAULT_RAW_TEMP_DIR = r"C:\Users\tbatson\AppData\Local\Temp\generic_description_raw_temp"

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_MAX_TOKENS = 1800
RETRY_MAX_TOKENS = 2400  # documented workaround for occasional empty/truncated responses at 1800

# Hard cap agreed with user: <= 3000 chars, no BEEP disposition/evidentiary content.
GENERIC_DESCRIPTION_PROMPT_V6 = (
    "You are looking at a BEOL SEM defect image pair (brightfield + darkfield) of the "
    "same site, imaged at an angle normal to the wafer surface. Bright regions in both "
    "images are SiO substrate with a relatively uniform, bumpy texture. Dark regions are "
    "etched comparator structures (line trenches, vias, or wide vias) whose long "
    "dimensions all run parallel to each other; positioning may be regular or irregular. "
    "A comparator's boundary, if covered by a defect, can be inferred from its own "
    "regular shape or neighboring comparators. Do not comment on brightness/contrast of "
    "the defect or comparators, or on comparator color/darkness -- these are constant "
    "properties of this imaging modality, not meaningful observations.\n\n"
    "One or more material defects (residual material) may rest on the SiO surface, inside "
    "a comparator, or both. Look carefully for more than one distinct defect -- a single "
    "fused, multi-lobed blob may actually be several particles merged together; still give "
    "your best defect_count regardless.\n\n"
    "OUTPUT CONTRACT: strict JSON only, no text outside the JSON object. Use exactly these "
    "keys in this order:\n"
    "coarse_shape (single value: circle, round, angular, clumped -- circle only for a "
    "smooth, symmetric outline with no facet or notch anywhere on the boundary; prefer "
    "round/angular if unsure; angular needs a straight edge/corner; clumped only for one "
    "fused/multi-lobed outline, not just defect_count>1 with separate particles)\n"
    "shape_elongated (bool)\n"
    "shape_rounded_corners (bool)\n"
    "shape_rounded_edges (bool)\n"
    "shape_flake_like (bool)\n"
    "shape_shard (bool)\n"
    "shape_jagged (bool)\n"
    "shape_concave (bool)\n"
    "coarse_texture (single value, low-to-high relief: smooth, textured, rough)\n"
    "texture_layered (bool -- a line within the defect that follows a defect boundary or "
    "comparator edge)\n"
    "texture_interior_striation (bool -- a straight line within the defect)\n"
    "texture_fractured (bool -- a visible, irregular gap/break separating or nearly "
    "separating 1-3 parts of the particle body; not a boundary-following line (layered), "
    "a straight line (interior_striation), or general craggy surface (scraggly))\n"
    "texture_scraggly (bool -- overall craggy and nodular surface, many small knobs/lobes "
    "giving a cauliflower-like impression)\n"
    "defect_count (integer, number of distinct material defects visible)\n"
    "size_percent_of_image (decimal float, your visual estimate of defect area as a "
    "percent of total image area)\n"
    "location_relative -- answer must be exactly one of these four words: on_sio, "
    "in_comparator, spanning_both, unclear. on_sio = no touch, or touches without "
    "crossing, a comparator's real/inferred boundary. in_comparator = fully within one. "
    "spanning_both = edge crosses one, part on each side.\n"
    "focus_quality (single value: in_focus, out_of_focus, mixed)\n"
    "confidence (decimal float 0.0-1.0, never a word)\n"
    "review_required (bool, true if image quality or ambiguity limits assessment)\n"
    "description (1-2 sentence free-text visual description, excluding brightness/"
    "contrast and comparator color commentary)"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_pilot_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _is_parsed_ok(parsed: dict[str, Any]) -> bool:
    return bool(parsed) and "description" in parsed and "raw_text" not in parsed


def _resolve_raw_pair(
    row: dict[str, str], raw_cfg: RawImageConfig
) -> tuple[Path | None, Path | None, dict[str, Any]]:
    bright_manifest_row = {
        "IMAGE_FILESPEC": row.get("bright_image_filespec", ""),
        "QUERY_SITE": row.get("query_site", ""),
    }
    dark_manifest_row = {
        "IMAGE_FILESPEC": row.get("dark_image_filespec", ""),
        "QUERY_SITE": row.get("query_site", ""),
    }
    bright_temp, bright_info = _download_raw_image_to_temp(bright_manifest_row, raw_cfg)
    dark_temp, dark_info = _download_raw_image_to_temp(dark_manifest_row, raw_cfg)
    return bright_temp, dark_temp, {
        "bright_raw_download": bright_info,
        "dark_raw_download": dark_info,
    }


def _call_with_retry(bright_path: Path, dark_path: Path, model: str) -> tuple[dict[str, Any], str, dict[str, Any], int]:
    parsed, raw_text, usage = _call_image(
        [bright_path, dark_path], GENERIC_DESCRIPTION_PROMPT_V6, model, DEFAULT_MAX_TOKENS
    )
    if _is_parsed_ok(parsed):
        return parsed, raw_text, usage, DEFAULT_MAX_TOKENS

    parsed, raw_text, usage = _call_image(
        [bright_path, dark_path], GENERIC_DESCRIPTION_PROMPT_V6, model, RETRY_MAX_TOKENS
    )
    return parsed, raw_text, usage, RETRY_MAX_TOKENS


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the v6 generic-description VLM pilot (flat removed, texture triggers clarified, location_relative wording fixed) over the SMALL_PARTICLE sample manifest."
    )
    parser.add_argument("--pilot-manifest-csv", default=DEFAULT_PILOT_MANIFEST)
    parser.add_argument("--output-jsonl", default=None, help="Default: outputs/probes/generic_description_v6_<UTC timestamp>.jsonl")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-pairs", type=int, default=0, help="0 = no limit, process every row in the manifest")
    parser.add_argument("--raw-temp-dir", default=DEFAULT_RAW_TEMP_DIR)
    parser.add_argument("--raw-app-name", default="GAJT_INLINE_24601")
    parser.add_argument("--raw-technology", default="1278")
    parser.add_argument("--keep-temp", action="store_true", help="Keep transient raw temp files instead of deleting after each call")
    return parser.parse_args()


def main() -> int:
    _load_env_from_supported_locations()
    args = _parse_args()

    pilot_manifest_csv = Path(args.pilot_manifest_csv)
    rows = _load_pilot_manifest(pilot_manifest_csv)
    if args.max_pairs > 0:
        rows = rows[: args.max_pairs]

    output_jsonl = Path(args.output_jsonl) if args.output_jsonl else (
        pilot_manifest_csv.parent / f"generic_description_v6_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    )
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    raw_cfg = RawImageConfig(
        enabled=True,
        manifest_csv=pilot_manifest_csv,
        temp_dir=Path(args.raw_temp_dir),
        app_name=args.raw_app_name,
        technology=args.raw_technology,
        gajt_dll_search_paths=DEFAULT_GAJT_DLL_SEARCH_PATHS,
        strict=False,
        keep_temp=args.keep_temp,
    )

    counts = {"total": 0, "raw_ok": 0, "raw_failed": 0, "parsed_ok": 0, "parsed_failed": 0}

    with output_jsonl.open("w", encoding="utf-8") as out_f:
        for row in rows:
            counts["total"] += 1
            case_id = row.get("case_id", "")
            bright_temp, dark_temp, raw_status = _resolve_raw_pair(row, raw_cfg)

            record: dict[str, Any] = {
                "case_id": case_id,
                "timestamp_utc": _utc_now(),
                "model": args.model,
                "wafer_key": row.get("wafer_key", ""),
                "inspection_time": row.get("inspection_time", ""),
                "defect_id": row.get("defect_id", ""),
                "subentity": row.get("subentity", ""),
                "lot": row.get("lot", ""),
                "lot7": row.get("lot7", ""),
                "layer": row.get("layer", ""),
                "wafer_id": row.get("wafer_id", ""),
                "size_x": row.get("size_x", ""),
                "size_y": row.get("size_y", ""),
                "size_d": row.get("size_d", ""),
                "area": row.get("area", ""),
                "finebin": row.get("finebin", ""),
                "inspect_time": row.get("inspect_time", ""),
                **raw_status,
            }

            if bright_temp is None or dark_temp is None:
                counts["raw_failed"] += 1
                record["status"] = "raw_download_failed"
                out_f.write(json.dumps(record) + "\n")
                continue
            counts["raw_ok"] += 1

            try:
                parsed, raw_text, usage, tokens_used = _call_with_retry(bright_temp, dark_temp, args.model)
                record["status"] = "ok"
                record["model_call"] = {
                    "parsed": parsed,
                    "raw_text_excerpt": raw_text[:1000],
                    "usage": usage,
                    "max_completion_tokens_used": tokens_used,
                }
                if _is_parsed_ok(parsed):
                    counts["parsed_ok"] += 1
                else:
                    counts["parsed_failed"] += 1
            except Exception as exc:
                record["status"] = "error"
                record["error_message"] = str(exc)
                counts["parsed_failed"] += 1
            finally:
                if not args.keep_temp:
                    for temp_path in (bright_temp, dark_temp):
                        try:
                            temp_path.unlink()
                        except OSError:
                            pass

            out_f.write(json.dumps(record) + "\n")

    print(f"prompt_char_count={len(GENERIC_DESCRIPTION_PROMPT_V6)}")
    print(f"output_jsonl={output_jsonl}")
    for key, value in counts.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
