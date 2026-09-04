"""
probe_generic_description_v8.py
--------------------------------
v8 of the SMALL_PARTICLE generic-description pilot, built from
Particle_Descriptors_v8_canonical.txt:

1. Fine shape: Rounded_Edges and Shard removed (Shard specifically because it
   caused a v6 collision -- the model output coarse_shape="shard", echoing the
   fine-flag name instead of a valid coarse value). Elongated/Rounded_Corners/
   Jagged/Concave/Flake given concise, concrete trigger definitions.
2. coarse_shape now carries an explicit "answer must be exactly one of these
   four words" instruction -- defense in depth alongside removing Shard, since
   Elongated/Jagged/Concave remain as fine-shape terms the model could still
   reach for under the same failure pattern (same fix already applied to
   location_relative in v6).
3. coarse_texture is now calibrated relative to the SiO substrate's own visible
   texture wavelength: comparable -> Textured, coarser -> Rough, finer or absent
   -> Smooth.

User accepted this prompt may run a bit over the project's usual 3000-char
soft cap given the added concision/precision in definitions -- char count is
still tracked and printed, not silently ignored.

Uses the SAME pilot manifest as v1-v7 (not a fresh sample) so all runs are
directly apples-to-apples comparable on the same 40 cases.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

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
DEFAULT_SOURCE_MANIFEST = r"C:\RAW_IMAGES\manifest.csv"
# Must be a short local path -- staging_root/<full IMAGE_FILESPEC> otherwise exceeds MAX_PATH (260 chars) on Windows.
DEFAULT_RAW_TEMP_DIR = r"C:\Users\tbatson\AppData\Local\Temp\generic_description_raw_temp"

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_MAX_TOKENS = 1800
RETRY_MAX_TOKENS = 2400  # documented workaround for occasional empty/truncated responses at 1800

# Soft cap ~3000 chars; user accepted running a bit over given the added precision.
GENERIC_DESCRIPTION_PROMPT_V8 = (
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
    "coarse_shape -- answer must be exactly one of these four words: circle, round, "
    "angular, clumped. circle only for a smooth, symmetric outline with no facet or notch "
    "anywhere on the boundary; prefer round/angular if unsure; angular needs at least one "
    "relatively straight edge or corner; clumped only for one fused/multi-lobed outline, "
    "not just defect_count>1 with separate particles.\n"
    "shape_elongated (bool -- outline aspect ratio at least 2x approximate length:width)\n"
    "shape_rounded_corners (bool -- corners are round rather than mostly sharp angles)\n"
    "shape_jagged (bool -- outline contains sharp angled vertices)\n"
    "shape_concave (bool -- a noticeable portion of the outline curves inward, departing "
    "meaningfully from convex, ignoring minor surface irregularities)\n"
    "shape_flake (bool -- flat, thin fragment with an irregular but relatively planar "
    "outline, like a broken chip/flake)\n"
    "coarse_texture (single value, low-to-high relief: smooth, textured, rough)\n"
    "texture_interior_layer (bool -- a line or contrast boundary within the defect "
    "follows the defect's own outline; NOT a comparator edge)\n"
    "texture_interior_line (bool -- a straight line within the defect)\n"
    "texture_interior_fracture (bool -- a visible, irregular gap/break separating or "
    "nearly separating the defect into multiple pieces)\n"
    "texture_scraggly (bool -- craggy, nodular surface with numerous small knobs/lobes, "
    "cauliflower impression)\n"
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


def _load_source_manifest(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False, dtype=str)
    return df


def _norm_text(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def _to_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _select_local_cache_pairs(df: pd.DataFrame, max_pairs: int) -> list[dict[str, str]]:
    normalized = {str(col).lower(): col for col in df.columns}
    class_col = normalized.get("class")
    image_id_col = normalized.get("image_id")
    local_path_col = normalized.get("local_path")
    wafer_col = normalized.get("wafer_key")
    insp_col = normalized.get("inspection_time")
    defect_col = normalized.get("defect_id")

    if not all([class_col, image_id_col, local_path_col, wafer_col, insp_col, defect_col]):
        missing = [name for name, col in (("class", class_col), ("image_id", image_id_col), ("local_path", local_path_col), ("wafer_key", wafer_col), ("inspection_time", insp_col), ("defect_id", defect_col)) if col is None]
        raise RuntimeError(f"Local cache manifest missing required columns: {', '.join(missing)}")

    work = df[df[class_col].fillna("").str.upper().eq("SMALL_PARTICLE")].copy()
    work = work[work[local_path_col].fillna("").apply(lambda value: Path(str(value)).exists())].copy()
    work["_image_id_int"] = work[image_id_col].apply(_to_int)
    work = work[work["_image_id_int"].isin([2, 3])].copy()

    grouped_rows: list[dict[str, str]] = []
    for (wafer_key, inspection_time, defect_id), group in work.groupby([wafer_col, insp_col, defect_col]):
        by_role = {int(row["_image_id_int"]): row for _, row in group.iterrows() if row["_image_id_int"] in {2, 3}}
        bright = by_role.get(2)
        dark = by_role.get(3)
        if bright is None or dark is None:
            continue

        grouped_rows.append({
            "case_id": f"RAW_V8_{len(grouped_rows) + 1:03d}",
            "wafer_key": str(wafer_key),
            "inspection_time": str(inspection_time),
            "defect_id": str(defect_id),
            "bright_local_image_file": str(bright.get(local_path_col, "")),
            "dark_local_image_file": str(dark.get(local_path_col, "")),
            "bright_image_filespec": str(bright.get("image_filespec", bright.get("IMAGE_FILESPEC", ""))),
            "dark_image_filespec": str(dark.get("image_filespec", dark.get("IMAGE_FILESPEC", ""))),
            "query_site": _norm_text(bright, "query_site", "QUERY_SITE", "site", "SITE"),
            "subentity": _norm_text(bright, "subentity", "SUBENTITY"),
            "lot": _norm_text(bright, "lot", "LOT"),
            "lot7": _norm_text(bright, "lot7", "LOT7"),
            "layer": _norm_text(bright, "layer", "LAYER"),
            "wafer_id": _norm_text(bright, "wafer_id", "WAFER_ID"),
            "size_x": _norm_text(bright, "size_x", "SIZE_X"),
            "size_y": _norm_text(bright, "size_y", "SIZE_Y"),
            "size_d": _norm_text(bright, "size_d", "SIZE_D"),
            "area": _norm_text(bright, "area", "AREA"),
            "finebin": _norm_text(bright, "finebin", "FINEBIN"),
            "inspect_time": _norm_text(bright, "inspect_time", "INSPECT_TIME"),
        })

    grouped_rows = sorted(grouped_rows, key=lambda row: (row["inspection_time"], row["wafer_key"], row["defect_id"]), reverse=True)
    if max_pairs > 0:
        grouped_rows = grouped_rows[:max_pairs]
    return grouped_rows


def _is_parsed_ok(parsed: dict[str, Any]) -> bool:
    return bool(parsed) and "description" in parsed and "raw_text" not in parsed


def _resolve_raw_pair(
    row: dict[str, str], raw_cfg: RawImageConfig
) -> tuple[Path | None, Path | None, dict[str, Any]]:
    bright_local = (row.get("bright_local_image_file") or "").strip()
    dark_local = (row.get("dark_local_image_file") or "").strip()
    if bright_local and dark_local:
        bright_path = Path(bright_local)
        dark_path = Path(dark_local)
        return bright_path, dark_path, {
            "bright_raw_download": {"raw_download_status": "local_cache"},
            "dark_raw_download": {"raw_download_status": "local_cache"},
        }

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
        [bright_path, dark_path], GENERIC_DESCRIPTION_PROMPT_V8, model, DEFAULT_MAX_TOKENS
    )
    if _is_parsed_ok(parsed):
        return parsed, raw_text, usage, DEFAULT_MAX_TOKENS

    parsed, raw_text, usage = _call_image(
        [bright_path, dark_path], GENERIC_DESCRIPTION_PROMPT_V8, model, RETRY_MAX_TOKENS
    )
    return parsed, raw_text, usage, RETRY_MAX_TOKENS


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the v8 generic-description VLM pilot (fine-shape terms trimmed, coarse_shape/location_relative hardened, coarse_texture calibrated relative to substrate texture) over the SMALL_PARTICLE sample manifest."
    )
    parser.add_argument("--pilot-manifest-csv", default=DEFAULT_PILOT_MANIFEST)
    parser.add_argument("--source-manifest-csv", default=DEFAULT_SOURCE_MANIFEST, help="Local RAW_IMAGES manifest to stage from when --use-local-cache is set.")
    parser.add_argument("--output-jsonl", default=None, help="Default: outputs/probes/generic_description_v8_<UTC timestamp>.jsonl")
    parser.add_argument("--output-manifest-csv", default=None, help="Optional pair-level manifest CSV to write for the HTML report.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-pairs", type=int, default=0, help="0 = no limit, process every row in the manifest")
    parser.add_argument("--raw-temp-dir", default=DEFAULT_RAW_TEMP_DIR)
    parser.add_argument("--raw-app-name", default="GAJT_INLINE_24601")
    parser.add_argument("--raw-technology", default="1278")
    parser.add_argument("--keep-temp", action="store_true", help="Keep transient raw temp files instead of deleting after each call")
    parser.add_argument("--use-local-cache", action="store_true", help="Read pairs from the local RAW_IMAGES manifest and call the VLM on the local files directly.")
    return parser.parse_args()


def main() -> int:
    _load_env_from_supported_locations()
    args = _parse_args()

    if args.use_local_cache:
        source_manifest = Path(args.source_manifest_csv)
        rows = _select_local_cache_pairs(_load_source_manifest(source_manifest), args.max_pairs)
        source_mode = "local_cache"
    else:
        pilot_manifest_csv = Path(args.pilot_manifest_csv)
        rows = _load_pilot_manifest(pilot_manifest_csv)
        if args.max_pairs > 0:
            rows = rows[: args.max_pairs]
        source_mode = "pilot_manifest"

    output_jsonl = Path(args.output_jsonl) if args.output_jsonl else (
        (Path(args.source_manifest_csv).parent if args.use_local_cache else Path(args.pilot_manifest_csv).parent)
        / f"generic_description_v8_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    )
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    output_manifest_csv = Path(args.output_manifest_csv) if args.output_manifest_csv else output_jsonl.with_name(f"{output_jsonl.stem}_manifest.csv")

    raw_cfg = RawImageConfig(
        enabled=not args.use_local_cache,
        manifest_csv=Path(args.source_manifest_csv if args.use_local_cache else args.pilot_manifest_csv),
        temp_dir=Path(args.raw_temp_dir),
        app_name=args.raw_app_name,
        technology=args.raw_technology,
        gajt_dll_search_paths=DEFAULT_GAJT_DLL_SEARCH_PATHS,
        strict=False,
        keep_temp=args.keep_temp,
    )

    counts = {"total": 0, "raw_ok": 0, "raw_failed": 0, "parsed_ok": 0, "parsed_failed": 0}
    output_manifest_rows: list[dict[str, str]] = []

    with output_jsonl.open("w", encoding="utf-8") as out_f:
        total_rows = len(rows)
        print(f"starting_v8_run total_cases={total_rows} source_mode={source_mode}", flush=True)
        for index, row in enumerate(rows, start=1):
            counts["total"] += 1
            case_id = row.get("case_id", "")
            print(f"case {index}/{total_rows} start case_id={case_id}", flush=True)
            bright_temp, dark_temp, raw_status = _resolve_raw_pair(row, raw_cfg)

            print(
                f"case {index}/{total_rows} resolved bright={bright_temp or row.get('bright_local_image_file') or row.get('bright_image_filespec', '')} dark={dark_temp or row.get('dark_local_image_file') or row.get('dark_image_filespec', '')}",
                flush=True,
            )

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
                print(f"case {index}/{total_rows} raw_download_failed case_id={case_id}", flush=True)
                continue
            counts["raw_ok"] += 1
            print(f"case {index}/{total_rows} inference_start case_id={case_id}", flush=True)

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
                print(f"case {index}/{total_rows} ok case_id={case_id} parsed_ok={_is_parsed_ok(parsed)}", flush=True)
            except Exception as exc:
                record["status"] = "error"
                record["error_message"] = str(exc)
                counts["parsed_failed"] += 1
                print(f"case {index}/{total_rows} error case_id={case_id} error={exc}", flush=True)
            finally:
                if not args.keep_temp and not args.use_local_cache:
                    for temp_path in (bright_temp, dark_temp):
                        try:
                            temp_path.unlink()
                        except OSError:
                            pass

            out_f.write(json.dumps(record) + "\n")
            print(f"case {index}/{total_rows} write_complete case_id={case_id}", flush=True)

            output_manifest_rows.append({
                "case_id": case_id,
                "wafer_key": str(record.get("wafer_key", "")),
                "inspection_time": str(record.get("inspection_time", "")),
                "defect_id": str(record.get("defect_id", "")),
                "bright_local_image_file": str(row.get("bright_local_image_file") or (bright_temp or "")),
                "dark_local_image_file": str(row.get("dark_local_image_file") or (dark_temp or "")),
                "bright_image_filespec": str(row.get("bright_image_filespec", "")),
                "dark_image_filespec": str(row.get("dark_image_filespec", "")),
                "query_site": str(row.get("query_site", "")),
                "subentity": str(record.get("subentity", "")),
                "lot": str(record.get("lot", "")),
                "lot7": str(record.get("lot7", "")),
                "layer": str(record.get("layer", "")),
                "wafer_id": str(record.get("wafer_id", "")),
                "size_x": str(record.get("size_x", "")),
                "size_y": str(record.get("size_y", "")),
                "size_d": str(record.get("size_d", "")),
                "area": str(record.get("area", "")),
                "finebin": str(record.get("finebin", "")),
                "inspect_time": str(record.get("inspect_time", "")),
            })

    print(f"prompt_char_count={len(GENERIC_DESCRIPTION_PROMPT_V8)}")
    print(f"output_jsonl={output_jsonl}")
    for key, value in counts.items():
        print(f"{key}={value}")

    if output_manifest_rows:
        with output_manifest_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(output_manifest_rows[0].keys()))
            writer.writeheader()
            writer.writerows(output_manifest_rows)
        print(f"output_manifest_csv={output_manifest_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())