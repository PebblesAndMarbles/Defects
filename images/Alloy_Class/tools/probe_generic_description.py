"""Canonical generic-description probe for SMALL_PARTICLE local-cache or pilot-manifest runs.

This consolidates the versioned probe scripts into a single config-driven entrypoint.
It preserves the v8 behavior contract while externalizing prompt/model/token settings
into a JSON config supplied on the command line and generating the HTML review report
in the same run.
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

from build_generic_description_html_report import build_report  # type: ignore  # noqa: E402
from run_stage_ab_prompt_tests import (  # type: ignore  # noqa: E402
    _call_image,
    _load_env_from_supported_locations,
)
from classify_phase1_batch import (  # type: ignore  # noqa: E402
    DEFAULT_GAJT_DLL_SEARCH_PATHS,
    RawImageConfig,
    _download_raw_image_to_temp,
)

DEFAULT_PROMPT_CONFIG = _ALLOY_CLASS_DIR / "config" / "generic_description_prompt_v8.json"
DEFAULT_PRODUCTION_COORDS = _ALLOY_CLASS_DIR.parents[1] / "outputs" / "defects" / "DEFECT_COORDINATES_EXTENDED.csv"
DEFAULT_RECLASS_LOG = _ALLOY_CLASS_DIR.parents[1] / "BE_QUERY_FILES" / "DEFECT_COORDINATES_RECLASS_LOG.csv"
DEFAULT_PILOT_MANIFEST = (
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson"
    r"\Defects\BE\images\Alloy_Class\outputs\probes\generic_description_pilot_manifest.csv"
)
DEFAULT_SOURCE_MANIFEST = r"C:\RAW_IMAGES\manifest.csv"
DEFAULT_PROCESSED_REGISTRY_CSV = r"C:\RAW_IMAGES\generic_description_processed_registry.csv"
DEFAULT_RAW_TEMP_DIR = r"C:\Users\tbatson\AppData\Local\Temp\generic_description_raw_temp"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_prompt_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_pilot_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_processed_registry(path: Path) -> set[str]:
    if not path.exists():
        return set()

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    excluded: set[str] = set()
    for row in rows:
        if str(row.get("status") or "").strip().lower() != "ok":
            continue
        join_key = str(row.get("join_key") or "").strip()
        if join_key:
            excluded.add(join_key)
    return excluded


def _append_processed_registry(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "join_key",
        "wafer_key",
        "inspection_time",
        "defect_id",
        "prompt_version",
        "status",
        "run_jsonl_path",
        "run_manifest_csv_path",
        "processed_at_utc",
    ]
    # Skip keys already present so re-running against an existing registry (e.g. after a
    # crash-recovery replay) never reaccumulates duplicate rows for the same defect.
    existing_keys = _load_processed_registry(path) if path.exists() else set()
    new_rows = [row for row in rows if str(row.get("join_key") or "").strip() not in existing_keys]
    if not new_rows:
        return

    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)


def _load_source_manifest(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False, dtype=str)


def _parse_case_id(case_id: object) -> tuple[str, str, str]:
    text = str(case_id or "").strip()
    parts = text.split("|")
    if len(parts) == 3:
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    return "", "", ""


def _load_production_coords_lookup(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        key = _join_key(row.get("WAFER_KEY"), row.get("INSPECTION_TIME"), row.get("DEFECT_ID"))
        lookup[key] = row
    return lookup


def _load_reclass_lookup(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        key = _join_key(row.get("WAFER_KEY"), row.get("INSPECTION_TIME"), row.get("DEFECT_ID"))
        lookup[key] = row
    return lookup


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


def _norm_text(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _enriched_fields(
    row: dict[str, str],
    production_lookup: dict[str, dict[str, str]],
    reclass_lookup: dict[str, dict[str, str]],
) -> dict[str, str]:
    source_case_id = row.get("source_case_id") or row.get("CASE_ID") or row.get("case_id")
    source_wafer_key, source_inspection_time, source_defect_id = _parse_case_id(source_case_id)
    join_key = _join_key(
        source_wafer_key or row.get("wafer_key") or row.get("WAFER_KEY"),
        source_inspection_time or row.get("inspection_time") or row.get("INSPECTION_TIME"),
        source_defect_id or row.get("defect_id") or row.get("DEFECT_ID"),
    )
    production = production_lookup.get(join_key, {})
    reclass = reclass_lookup.get(join_key, {})
    reclass_is_removed = _norm_text(reclass, "CLASS_new", "class_new").upper() == "SIZE_SMALL"
    return {
        "wafer_id": _first_non_empty(
            row.get("wafer_id"),
            row.get("WAFER_ID"),
            production.get("WAFER_ID"),
            reclass.get("WAFER_ID_old") if reclass_is_removed else "",
        ),
        "size_x": _first_non_empty(
            row.get("size_x"),
            row.get("SIZE_X"),
            production.get("SIZE_X"),
            reclass.get("SIZE_X_old") if reclass_is_removed else "",
        ),
        "size_y": _first_non_empty(
            row.get("size_y"),
            row.get("SIZE_Y"),
            production.get("SIZE_Y"),
            reclass.get("SIZE_Y_old") if reclass_is_removed else "",
        ),
        "size_d": _first_non_empty(
            row.get("size_d"),
            row.get("SIZE_D"),
            production.get("SIZE_D"),
            reclass.get("SIZE_D_old") if reclass_is_removed else "",
        ),
        "area": _first_non_empty(
            row.get("area"),
            row.get("AREA"),
            production.get("AREA"),
            reclass.get("AREA_old") if reclass_is_removed else "",
        ),
        "finebin": _first_non_empty(
            row.get("finebin"),
            row.get("FINEBIN"),
            production.get("FINEBIN"),
            reclass.get("CLASS_old") if reclass_is_removed else "",
        ),
        "inspect_time": _first_non_empty(
            row.get("inspect_time"),
            row.get("INSPECT_TIME"),
            row.get("inspection_time"),
            row.get("INSPECTION_TIME"),
            production.get("INSPECT_TIME"),
            reclass.get("INSPECT_TIME_old") if reclass_is_removed else "",
        ),
    }


def _missing_production_join_info(
    row: dict[str, str],
    production_lookup: dict[str, dict[str, str]],
    reclass_lookup: dict[str, dict[str, str]],
) -> dict[str, str]:
    source_case_id = row.get("source_case_id") or row.get("CASE_ID") or row.get("case_id")
    source_wafer_key, source_inspection_time, source_defect_id = _parse_case_id(source_case_id)
    join_key = _join_key(
        source_wafer_key or row.get("wafer_key") or row.get("WAFER_KEY"),
        source_inspection_time or row.get("inspection_time") or row.get("INSPECTION_TIME"),
        source_defect_id or row.get("defect_id") or row.get("DEFECT_ID"),
    )
    if join_key in production_lookup or join_key in reclass_lookup:
        return {}
    return {
        "source_case_id": str(source_case_id or ""),
        "join_key": join_key,
        "source_wafer_key": source_wafer_key,
        "source_inspection_time": source_inspection_time,
        "source_defect_id": source_defect_id,
    }


def _flatten_parsed_fields(parsed: dict[str, Any]) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for key, value in parsed.items():
        flattened[key] = "" if value is None else str(value)
    return flattened


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


def _select_local_cache_pairs(df: pd.DataFrame, max_pairs: int, excluded_join_keys: set[str] | None = None) -> list[dict[str, str]]:
    normalized = {str(col).lower(): col for col in df.columns}
    class_col = normalized.get("class")
    image_id_col = normalized.get("image_id")
    local_path_col = normalized.get("local_path")
    source_filespec_col = normalized.get("source_filespec")
    wafer_col = normalized.get("wafer_key")
    insp_col = normalized.get("inspection_time")
    defect_col = normalized.get("defect_id")
    case_id_col = normalized.get("case_id")

    required = [
        ("class", class_col),
        ("image_id", image_id_col),
        ("local_path", local_path_col),
        ("wafer_key", wafer_col),
        ("inspection_time", insp_col),
        ("defect_id", defect_col),
    ]
    missing = [name for name, col in required if col is None]
    if missing:
        raise RuntimeError(f"Local cache manifest missing required columns: {', '.join(missing)}")

    work = df[df[class_col].fillna("").str.upper().eq("SMALL_PARTICLE")].copy()
    work = work[work[local_path_col].fillna("").apply(lambda value: Path(str(value)).exists())].copy()
    work["_image_id_int"] = work[image_id_col].apply(_to_int)
    work = work[work["_image_id_int"].isin([2, 3])].copy()

    def _row_inspection_time(row: "pd.Series") -> str:
        # Prefer the full-precision timestamp embedded in case_id (matches the value
        # written to the processed registry) over the manifest's separate inspection_time
        # column, which is truncated to the minute (seconds always :00) and would
        # otherwise silently defeat exclusion matching against the registry.
        if case_id_col:
            _, parsed_insp, _ = _parse_case_id(row.get(case_id_col))
            if parsed_insp:
                return parsed_insp
        return row[insp_col]

    work["_join_key"] = work.apply(
        lambda row: _join_key(row[wafer_col], _row_inspection_time(row), row[defect_col]),
        axis=1,
    )
    if excluded_join_keys:
        work = work[~work["_join_key"].isin(excluded_join_keys)].copy()

    grouped_rows: list[dict[str, str]] = []
    for _join_key_value, group in work.groupby("_join_key"):
        by_role = {int(row["_image_id_int"]): row for _, row in group.iterrows() if row["_image_id_int"] in {2, 3}}
        bright = by_role.get(2)
        dark = by_role.get(3)
        if bright is None or dark is None:
            continue

        grouped_rows.append(
            {
                "case_id": f"RAW_V8_{len(grouped_rows) + 1:03d}",
                "source_case_id": str(bright.get("case_id", "")),
                "wafer_key": str(bright.get(wafer_col, "")),
                "inspection_time": str(bright.get(insp_col, "")),
                "defect_id": str(bright.get(defect_col, "")),
                "bright_local_image_file": str(bright.get(local_path_col, "")),
                "dark_local_image_file": str(dark.get(local_path_col, "")),
                "bright_image_filespec": str(bright.get(source_filespec_col or "", bright.get("image_filespec", bright.get("IMAGE_FILESPEC", "")))),
                "dark_image_filespec": str(dark.get(source_filespec_col or "", dark.get("image_filespec", dark.get("IMAGE_FILESPEC", "")))),
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
            }
        )

    grouped_rows = sorted(grouped_rows, key=lambda row: (row["inspection_time"], row["wafer_key"], row["defect_id"]), reverse=True)
    if max_pairs > 0:
        grouped_rows = grouped_rows[:max_pairs]
    return grouped_rows


def _is_parsed_ok(parsed: dict[str, Any]) -> bool:
    return bool(parsed) and "description" in parsed and "raw_text" not in parsed


def _resolve_raw_pair(row: dict[str, str], raw_cfg: RawImageConfig) -> tuple[Path | None, Path | None, dict[str, Any]]:
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


def _call_with_retry(bright_path: Path, dark_path: Path, model: str, prompt: str, max_tokens: int, retry_tokens: int) -> tuple[dict[str, Any], str, dict[str, Any], int]:
    parsed, raw_text, usage = _call_image([bright_path, dark_path], prompt, model, max_tokens)
    if _is_parsed_ok(parsed):
        return parsed, raw_text, usage, max_tokens

    parsed, raw_text, usage = _call_image([bright_path, dark_path], prompt, model, retry_tokens)
    return parsed, raw_text, usage, retry_tokens


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the canonical generic-description VLM probe over the SMALL_PARTICLE sample manifest or local RAW_IMAGES cache."
    )
    parser.add_argument(
        "--prompt-config",
        "--prompt-json",
        dest="prompt_config",
        default=str(DEFAULT_PROMPT_CONFIG),
        help="Path to the prompt config JSON (for example, config/generic_description_prompt_v9.json).",
    )
    parser.add_argument("--pilot-manifest-csv", default=DEFAULT_PILOT_MANIFEST)
    parser.add_argument("--source-manifest-csv", default=DEFAULT_SOURCE_MANIFEST, help="Local RAW_IMAGES manifest to stage from when --use-local-cache is set.")
    parser.add_argument("--processed-registry-csv", default=DEFAULT_PROCESSED_REGISTRY_CSV, help="CSV registry of successful join keys used to exclude already-processed local-cache cases.")
    parser.add_argument("--output-jsonl", default=None, help="Default: outputs/probes/generic_description_<prompt_version>_<UTC timestamp>.jsonl")
    parser.add_argument("--output-manifest-csv", default=None, help="Optional pair-level manifest CSV to write for the HTML report.")
    parser.add_argument("--output-html", default=None, help="Optional HTML review report path. Default: sibling of the JSONL with _review.html suffix.")
    parser.add_argument("--model", default=None, help="Override the model from the prompt config.")
    parser.add_argument("--max-pairs", type=int, default=0, help="0 = no limit, process every row in the manifest")
    parser.add_argument("--raw-temp-dir", default=DEFAULT_RAW_TEMP_DIR)
    parser.add_argument("--raw-app-name", default="GAJT_INLINE_24601")
    parser.add_argument("--raw-technology", default="1278")
    parser.add_argument("--keep-temp", action="store_true", help="Keep transient raw temp files instead of deleting after each call")
    parser.add_argument("--use-local-cache", action="store_true", help="Read pairs from the local RAW_IMAGES manifest and call the VLM on the local files directly.")
    parser.add_argument("--with-feedback-portal", action="store_true", help="Render the HTML review report with the feedback portal widget.")
    return parser.parse_args()


def main() -> int:
    _load_env_from_supported_locations()
    args = _parse_args()
    prompt_cfg = _load_prompt_config(Path(args.prompt_config))
    prompt_version = str(prompt_cfg.get("prompt_version", "generic_description"))
    model = args.model or str(prompt_cfg.get("model", "gpt-5.4-mini"))
    max_completion_tokens = int(prompt_cfg.get("max_completion_tokens", 1800))
    retry_max_completion_tokens = int(prompt_cfg.get("retry_max_completion_tokens", 2400))
    prompt = str(prompt_cfg.get("prompt", ""))

    if not prompt:
        raise RuntimeError(f"Prompt config {args.prompt_config} does not contain a prompt string")

    production_lookup = _load_production_coords_lookup(DEFAULT_PRODUCTION_COORDS)
    reclass_lookup = _load_reclass_lookup(DEFAULT_RECLASS_LOG)
    processed_registry_csv = Path(args.processed_registry_csv)

    if args.use_local_cache:
        source_manifest = Path(args.source_manifest_csv)
        excluded_join_keys = _load_processed_registry(processed_registry_csv)
        rows = _select_local_cache_pairs(_load_source_manifest(source_manifest), args.max_pairs, excluded_join_keys)
        source_mode = "local_cache"
    else:
        pilot_manifest_csv = Path(args.pilot_manifest_csv)
        rows = _load_pilot_manifest(pilot_manifest_csv)
        if args.max_pairs > 0:
            rows = rows[: args.max_pairs]
        source_mode = "pilot_manifest"

    output_jsonl = Path(args.output_jsonl) if args.output_jsonl else (
        (Path(args.source_manifest_csv).parent if args.use_local_cache else Path(args.pilot_manifest_csv).parent)
        / f"generic_description_{prompt_version}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    )
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_manifest_csv = Path(args.output_manifest_csv) if args.output_manifest_csv else output_jsonl.with_name(f"{output_jsonl.stem}_manifest.csv")
    output_html = Path(args.output_html) if args.output_html else output_jsonl.with_name(f"{output_jsonl.stem}_review.html")

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
    missing_production_joins: list[dict[str, str]] = []
    processed_registry_rows: list[dict[str, str]] = []

    with output_jsonl.open("w", encoding="utf-8") as out_f:
        total_rows = len(rows)
        print(f"starting_generic_description_run total_cases={total_rows} source_mode={source_mode} prompt_version={prompt_version}", flush=True)
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
                "source_case_id": str(row.get("source_case_id", "")),
                "timestamp_utc": _utc_now(),
                "model": model,
                "prompt_version": prompt_version,
                "wafer_key": row.get("wafer_key", ""),
                "inspection_time": _parse_case_id(row.get("source_case_id"))[1] or row.get("inspection_time", ""),
                "defect_id": row.get("defect_id", ""),
                "subentity": row.get("subentity", ""),
                "lot": row.get("lot", ""),
                "lot7": row.get("lot7", ""),
                "layer": row.get("layer", ""),
                **raw_status,
            }
            record.update(_enriched_fields(row, production_lookup, reclass_lookup))
            missing_join = _missing_production_join_info(row, production_lookup, reclass_lookup)
            if missing_join:
                missing_production_joins.append(missing_join)

            if bright_temp is None or dark_temp is None:
                counts["raw_failed"] += 1
                record["status"] = "raw_download_failed"
                out_f.write(json.dumps(record) + "\n")
                print(f"case {index}/{total_rows} raw_download_failed case_id={case_id}", flush=True)
                continue
            counts["raw_ok"] += 1
            print(f"case {index}/{total_rows} inference_start case_id={case_id}", flush=True)

            try:
                parsed, raw_text, usage, tokens_used = _call_with_retry(bright_temp, dark_temp, model, prompt, max_completion_tokens, retry_max_completion_tokens)
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

            output_manifest_rows.append(
                {
                    "case_id": case_id,
                    "source_case_id": str(row.get("source_case_id", "")),
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
                    **_flatten_parsed_fields((record.get("model_call") or {}).get("parsed") or {}),
                    "vlm_status": str(record.get("status", "")),
                    "vlm_prompt_version": prompt_version,
                    "vlm_timestamp_utc": str(record.get("timestamp_utc", "")),
                }
            )

            if record.get("status") == "ok":
                processed_registry_rows.append(
                    {
                        "join_key": _join_key(record.get("wafer_key"), record.get("inspection_time"), record.get("defect_id")),
                        "wafer_key": str(record.get("wafer_key", "")),
                        "inspection_time": str(record.get("inspection_time", "")),
                        "defect_id": str(record.get("defect_id", "")),
                        "prompt_version": prompt_version,
                        "status": str(record.get("status", "")),
                        "run_jsonl_path": str(output_jsonl),
                        "run_manifest_csv_path": str(output_manifest_csv),
                        "processed_at_utc": str(record.get("timestamp_utc", "")),
                    }
                )

    print(f"prompt_char_count={len(prompt)}")
    print(f"output_jsonl={output_jsonl}")
    for key, value in counts.items():
        print(f"{key}={value}")

    if output_manifest_rows:
        # Union of keys across all rows, not just row 0 -- parsed_failed cases add an
        # extra `raw_text` key via _flatten_parsed_fields that successfully-parsed rows
        # don't have, which crashes DictWriter if fieldnames come from a single row.
        fieldnames: list[str] = []
        seen_fieldnames: set[str] = set()
        for manifest_row in output_manifest_rows:
            for key in manifest_row.keys():
                if key not in seen_fieldnames:
                    seen_fieldnames.add(key)
                    fieldnames.append(key)
        with output_manifest_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(output_manifest_rows)
        print(f"output_manifest_csv={output_manifest_csv}")

    if args.use_local_cache and processed_registry_rows:
        _append_processed_registry(processed_registry_csv, processed_registry_rows)
        print(f"processed_registry_csv={processed_registry_csv}")

    if missing_production_joins:
        print(f"missing_production_joins={len(missing_production_joins)}")
        for entry in missing_production_joins[:10]:
            print(
                "missing_production_join "
                f"source_case_id={entry.get('source_case_id', '')} "
                f"join_key={entry.get('join_key', '')} "
                f"source_wafer_key={entry.get('source_wafer_key', '')} "
                f"source_inspection_time={entry.get('source_inspection_time', '')} "
                f"source_defect_id={entry.get('source_defect_id', '')}",
                flush=True,
            )

    summary, written_html = build_report(
        input_jsonl=output_jsonl,
        pilot_manifest_csv=output_manifest_csv,
        output_html=output_html,
        with_feedback_portal=args.with_feedback_portal,
    )
    print(f"output_html={written_html}")
    print(f"report_summary={summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
