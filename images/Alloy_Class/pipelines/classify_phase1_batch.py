"""
Phase 1 BE image classification prototype runner.

Goals:
- Stay UNC-native and avoid local machine path assumptions.
- Keep per-image processing resilient (one failure does not stop batch).
- Emit structured JSON suitable for comparison experiments.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
DOTENV_CANDIDATE_NAMES = (".env", ".env.context")
DEFAULT_GAJT_DLL_SEARCH_PATHS = [
    r"D:\gajtv\configurations\wijt",
    r"C:\Users\tbatson\AppData\Roaming\SAS\JMP\AddIns\gajtv.intel.com\wijt",
]

DEFAULT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "primary_class": {"type": "string"},
        "secondary_class": {"type": "string"},
        "morphology": {"type": "string"},
        "location_relative": {"type": "string"},
        "size_relative": {"type": "string"},
        "confidence": {"type": "number"},
        "review_required": {"type": "boolean"},
        "rationale": {"type": "string"},
    },
    "required": [
        "primary_class",
        "morphology",
        "location_relative",
        "size_relative",
        "confidence",
        "review_required",
        "rationale",
    ],
    "additionalProperties": False,
}


@dataclass
class RuntimeConfig:
    api_base_url: str
    model: str
    detail: str
    timeout_seconds: int
    verify_ssl: bool
    ca_bundle_path: str | None
    input_folder: Path
    output_folder: Path
    prompt: str
    prompt_version: str
    max_completion_tokens: int


@dataclass
class RawImageConfig:
    enabled: bool
    manifest_csv: Path
    temp_dir: Path
    app_name: str
    technology: str
    gajt_dll_search_paths: list[str]
    strict: bool
    keep_temp: bool


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _find_upward_env_files(start_dir: Path, max_depth: int = 10) -> list[Path]:
    found: list[Path] = []
    current = start_dir.resolve()
    for _ in range(max_depth):
        for name in DOTENV_CANDIDATE_NAMES:
            candidate = current / name
            if candidate.is_file():
                found.append(candidate)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return found


def _load_env_from_supported_locations() -> None:
    explicit_env_file = os.environ.get("ALLOY_ENV_FILE", "").strip()
    if explicit_env_file:
        _parse_env_file(Path(explicit_env_file))

    cwd = Path.cwd()
    for env_file in _find_upward_env_files(cwd):
        _parse_env_file(env_file)


def _load_runtime_paths(config_path: Path) -> dict[str, Any]:
    return json.loads(config_path.read_text(encoding="utf-8-sig"))


def _load_phase1_settings(settings_path: Path) -> dict[str, Any]:
    return json.loads(settings_path.read_text(encoding="utf-8-sig"))


def _assert_alloy_importable() -> None:
    if importlib.util.find_spec("alloy") is None:
        raise RuntimeError(
            "Alloy package is not importable in the current interpreter. "
            "Bootstrap this interpreter from the UNC wheelhouse before running classification."
        )


def _load_size_metadata(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists() or not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        out: dict[str, dict[str, str]] = {}
        for row in reader:
            name = (row.get("image_name", "") or "").strip()
            if not name:
                continue
            out[name] = {
                "SIZE_X": (row.get("SIZE_X", "") or "").strip(),
                "SIZE_Y": (row.get("SIZE_Y", "") or "").strip(),
                "SIZE_D": (row.get("SIZE_D", "") or "").strip(),
                "AREA": (row.get("AREA", "") or "").strip(),
                "MANUAL_OPTICAL_CLASS": (row.get("MANUAL_OPTICAL_CLASS", "") or "").strip(),
            }
        return out


def _load_image_manifest_index(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists() or not path.is_file():
        return {}
    out: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            local_path = (row.get("LOCAL_IMAGE_FILE", "") or "").strip()
            if not local_path:
                continue
            key = Path(local_path).name.lower()
            if key not in out:
                out[key] = row
                continue

            # Prefer non-inventory rows when duplicates exist.
            existing_inv = (out[key].get("INVENTORY_ONLY", "") or "0").strip()
            current_inv = (row.get("INVENTORY_ONLY", "") or "0").strip()
            try:
                existing_is_inv = int(float(existing_inv)) == 1
            except ValueError:
                existing_is_inv = False
            try:
                current_is_inv = int(float(current_inv)) == 1
            except ValueError:
                current_is_inv = False
            if existing_is_inv and not current_is_inv:
                out[key] = row
    return out


def _load_secureftp_runtime(search_paths: list[str]):
    import clr

    for dll_dir in search_paths:
        if os.path.isdir(dll_dir) and dll_dir not in sys.path:
            sys.path.append(dll_dir)

    clr.AddReference("Intel.FabAuto.Quarc.Utilities")
    return __import__("Intel.FabAuto.Quarc", fromlist=["SecureFTP"]).SecureFTP


def _download_raw_image_to_temp(
    manifest_row: dict[str, str],
    raw_cfg: RawImageConfig,
) -> tuple[Path | None, dict[str, str]]:
    image_spec = (manifest_row.get("IMAGE_FILESPEC", "") or "").strip()
    query_site = (manifest_row.get("QUERY_SITE", "") or manifest_row.get("SITE", "") or "").strip()
    if not image_spec or not query_site:
        return None, {"raw_download_status": "missing_manifest_fields"}

    try:
        secure_ftp = _load_secureftp_runtime(raw_cfg.gajt_dll_search_paths)
    except Exception as exc:
        return None, {"raw_download_status": f"secureftp_unavailable: {exc}"}

    raw_cfg.temp_dir.mkdir(parents=True, exist_ok=True)
    staging_root = raw_cfg.temp_dir / "staging"
    staging_root.mkdir(parents=True, exist_ok=True)

    ds = f"{query_site}_PROD_YAS_{raw_cfg.technology}_FTP"
    try:
        secure_ftp.FtpFiles(query_site, ds, image_spec, str(staging_root), raw_cfg.app_name)
    except Exception as exc:
        return None, {"raw_download_status": f"ftp_error: {exc}", "raw_image_spec": image_spec}

    staged_path = staging_root / image_spec.lstrip("/\\").replace("/", os.sep)
    if not staged_path.exists() or not staged_path.is_file():
        return None, {"raw_download_status": "staged_file_missing", "raw_image_spec": image_spec}

    ext = staged_path.suffix.lower() or ".jpg"
    temp_name = f"raw_{uuid4().hex}{ext}"
    temp_file = raw_cfg.temp_dir / temp_name
    shutil.copy2(staged_path, temp_file)

    # Keep staging area bounded regardless of success/failure.
    try:
        shutil.rmtree(staging_root)
    except OSError:
        pass

    return temp_file, {
        "raw_download_status": "ok",
        "raw_image_spec": image_spec,
        "raw_query_site": query_site,
        "raw_datasource": ds,
    }


def _prompt_with_optional_metadata(base_prompt: str, metadata: dict[str, str] | None) -> str:
    if not metadata:
        return base_prompt
    pairs = [f"{k}={v}" for k, v in metadata.items() if v]
    if not pairs:
        return base_prompt
    return (
        base_prompt
        + "\n\nAdditional defect metrology context from coordinates DB "
        + "(use as supporting evidence, do not overfit): "
        + ", ".join(pairs)
    )


def _image_key(path: Path) -> str:
    canon = str(path.resolve()).lower()
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _extract_model_json(body: dict[str, Any]) -> dict[str, Any]:
    candidates: list[Any] = [
        body.get("description"),
        body.get("output_json"),
        body.get("json"),
        body.get("result"),
        body,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
        if isinstance(candidate, str):
            text = candidate.strip()
            if text.startswith("{") and text.endswith("}"):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    continue
    raise ValueError("Unable to extract structured JSON object from response")


def _post_vision(image_path: Path, cfg: RuntimeConfig, size_metadata: dict[str, str] | None = None) -> tuple[dict[str, Any], str]:
    from alloy.core.llm import image

    result = image(
        str(image_path),
        prompt=_prompt_with_optional_metadata(cfg.prompt, size_metadata),
        model=cfg.model,
        max_completion_tokens=cfg.max_completion_tokens,
    )

    if isinstance(result, dict):
        return result, json.dumps(result)
    if isinstance(result, str):
        parsed = _extract_model_json({"description": result})
        return parsed, result
    raise ValueError("Unexpected vision response type")


def _build_record_base(image_path: Path, cfg: RuntimeConfig, run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "timestamp_utc": _utc_now(),
        "image_key": _image_key(image_path),
        "image_path": str(image_path.resolve()),
        "image_name": image_path.name,
        "model_name": cfg.model,
        "prompt_version": cfg.prompt_version,
    }


def _iter_images(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)


def _pair_key_and_role(image_name: str) -> tuple[str, str | None]:
    stem = Path(image_name).stem
    if stem.endswith("_2"):
        return stem[:-2], "brightfield"
    if stem.endswith("_3"):
        return stem[:-2], "darkfield"
    return stem, None


def _build_pairs(images: list[Path]) -> tuple[list[tuple[str, Path, Path]], list[Path]]:
    grouped: dict[str, dict[str, Path]] = {}
    for image_path in images:
        pair_key, role = _pair_key_and_role(image_path.name)
        if role is None:
            continue
        grouped.setdefault(pair_key, {})[role] = image_path

    pairs: list[tuple[str, Path, Path]] = []
    for key in sorted(grouped.keys()):
        roles = grouped[key]
        bright = roles.get("brightfield")
        dark = roles.get("darkfield")
        if bright and dark:
            pairs.append((key, bright, dark))

    paired_names = {p.name for _, bright, dark in pairs for p in (bright, dark)}
    unpaired = [p for p in images if p.name not in paired_names]
    return pairs, unpaired


def run_batch(
    cfg: RuntimeConfig,
    run_id: str,
    size_metadata_by_image: dict[str, dict[str, str]] | None = None,
    max_pairs: int = 5,
    require_bf_df_pairs: bool = True,
    raw_cfg: RawImageConfig | None = None,
) -> dict[str, int]:
    cfg.output_folder.mkdir(parents=True, exist_ok=True)
    images = _iter_images(cfg.input_folder)
    pairs, unpaired = _build_pairs(images)

    selected_pairs = pairs
    if max_pairs > 0:
        selected_pairs = pairs[:max_pairs]

    selected_pair_image_names = {
        image.name
        for _, bright, dark in selected_pairs
        for image in (bright, dark)
    }

    if require_bf_df_pairs:
        selected_images = [image for image in images if image.name in selected_pair_image_names]
    else:
        selected_images = images

    pair_lookup: dict[str, tuple[str, str]] = {}
    for key, bright, dark in selected_pairs:
        pair_lookup[bright.name] = (key, dark.name)
        pair_lookup[dark.name] = (key, bright.name)

    result_jsonl = cfg.output_folder / "phase1_results.jsonl"
    status_jsonl = cfg.output_folder / "phase1_status.jsonl"

    processed = 0
    failed = 0
    skipped = 0
    raw_used = 0
    raw_deleted = 0

    manifest_index: dict[str, dict[str, str]] = {}
    if raw_cfg and raw_cfg.enabled:
        manifest_index = _load_image_manifest_index(raw_cfg.manifest_csv)

    for image_path in selected_images:
        image_key = _image_key(image_path)
        out_file = cfg.output_folder / f"{image_key}.json"

        if out_file.exists():
            skipped += 1
            continue

        base = _build_record_base(image_path, cfg, run_id)
        pair_key, pair_role = _pair_key_and_role(image_path.name)
        paired_info = pair_lookup.get(image_path.name)
        if paired_info:
            base["pair_key"] = paired_info[0]
            base["paired_image_name"] = paired_info[1]
        if pair_role:
            base["pair_role"] = pair_role

        try:
            row_t0 = time.perf_counter()
            infer_path = image_path
            raw_temp_path: Path | None = None
            raw_info: dict[str, str] = {}
            raw_download_seconds = 0.0
            if raw_cfg and raw_cfg.enabled:
                manifest_row = manifest_index.get(image_path.name.lower())
                if manifest_row:
                    raw_t0 = time.perf_counter()
                    raw_temp_path, raw_info = _download_raw_image_to_temp(manifest_row, raw_cfg)
                    raw_download_seconds = time.perf_counter() - raw_t0
                    if raw_temp_path:
                        infer_path = raw_temp_path
                        raw_used += 1
                else:
                    raw_info = {"raw_download_status": "manifest_row_not_found"}

            if raw_cfg and raw_cfg.enabled and raw_cfg.strict and infer_path == image_path:
                raise RuntimeError(raw_info.get("raw_download_status", "raw_download_failed"))

            size_meta = (size_metadata_by_image or {}).get(image_path.name)
            infer_t0 = time.perf_counter()
            parsed, raw_excerpt = _post_vision(infer_path, cfg, size_metadata=size_meta)
            inference_seconds = time.perf_counter() - infer_t0
            row_total_seconds = time.perf_counter() - row_t0
            record = {
                **base,
                "status": "ok",
                **parsed,
                "raw_response_excerpt": raw_excerpt[:1000],
                "timing_seconds": {
                    "raw_download": round(raw_download_seconds, 3),
                    "inference": round(inference_seconds, 3),
                    "row_total": round(row_total_seconds, 3),
                },
            }
            if raw_cfg and raw_cfg.enabled:
                record["used_transient_raw"] = int(infer_path != image_path)
                record["burned_image_path"] = str(image_path.resolve())
                record["inference_image_path"] = str(infer_path.resolve())
                record.update(raw_info)
            if size_meta:
                record["size_metadata"] = size_meta
            out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
            with result_jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            processed += 1

            if raw_cfg and raw_cfg.enabled and raw_temp_path and raw_temp_path.exists() and not raw_cfg.keep_temp:
                try:
                    raw_temp_path.unlink()
                    raw_deleted += 1
                except OSError:
                    pass
        except Exception as exc:
            err_record = {
                **base,
                "status": "error",
                "error_message": str(exc),
            }
            with status_jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(err_record) + "\n")
            failed += 1

    return {
        "processed": processed,
        "failed": failed,
        "skipped": skipped,
        "total_images": len(images),
        "total_pairs": len(pairs),
        "selected_pairs": len(selected_pairs),
        "unpaired_images": len(unpaired),
        "require_bf_df_pairs": int(require_bf_df_pairs),
        "selected_images": len(selected_images),
        "raw_used": raw_used,
        "raw_deleted": raw_deleted,
    }


def _build_runtime_config(runtime_paths: dict[str, Any], settings: dict[str, Any]) -> RuntimeConfig:
    input_folder = Path(settings.get("input_folder", "./inputs"))
    output_folder = Path(settings.get("output_folder", "./outputs/phase1"))

    ca_bundle: str | None = None
    if settings.get("use_shared_ca_bundle", False):
        ca_candidate = runtime_paths.get("optional_ca_bundle_unc")
        if isinstance(ca_candidate, str) and ca_candidate:
            ca_bundle = ca_candidate

    return RuntimeConfig(
        api_base_url=str(settings.get("api_base_url", "https://alloy.intel.com")),
        model=str(settings.get("model", "gpt-5.4-mini")),
        detail=str(settings.get("detail", "high")),
        timeout_seconds=int(settings.get("timeout_seconds", 60)),
        verify_ssl=bool(settings.get("verify_ssl", True)),
        ca_bundle_path=ca_bundle,
        input_folder=input_folder,
        output_folder=output_folder,
        prompt=str(settings["prompt"]),
        prompt_version=str(settings.get("prompt_version", "v1")),
        max_completion_tokens=int(settings.get("max_completion_tokens", 500)),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1 BE image classifier batch runner")
    parser.add_argument(
        "--runtime-paths",
        default="config/runtime_paths.json",
        help="Path to runtime_paths.json",
    )
    parser.add_argument(
        "--phase1-settings",
        default="config/phase1_settings.json",
        help="Path to phase1 settings JSON",
    )
    parser.add_argument(
        "--run-id",
        default=f"phase1_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        help="Run identifier for output records",
    )
    parser.add_argument(
        "--size-metadata-csv",
        default="config/defect_size_metadata.csv",
        help="Optional CSV keyed by image_name with SIZE_X/SIZE_Y/SIZE_D/AREA/MANUAL_OPTICAL_CLASS",
    )
    parser.add_argument(
        "--max-pairs",
        type=int,
        default=None,
        help="Maximum number of BF/DF pairs to process (default from settings or 5).",
    )
    parser.add_argument(
        "--allow-unpaired",
        action="store_true",
        help="Process all images, including unpaired, instead of BF/DF pairs only.",
    )
    parser.add_argument(
        "--raw-image-mode",
        action="store_true",
        help="Use transient raw image download for inference, then delete temp raw files.",
    )
    parser.add_argument(
        "--raw-manifest-csv",
        default=r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv",
        help="Image manifest CSV used to resolve raw IMAGE_FILESPEC per burned image.",
    )
    parser.add_argument(
        "--raw-temp-dir",
        default="./outputs/raw_temp",
        help="Temporary directory for transient raw image staging.",
    )
    parser.add_argument(
        "--raw-strict",
        action="store_true",
        help="Fail inference when transient raw download cannot be resolved.",
    )
    parser.add_argument(
        "--raw-keep-temp",
        action="store_true",
        help="Keep transient raw temp files (default deletes after inference).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _load_env_from_supported_locations()
    runtime_paths = _load_runtime_paths(Path(args.runtime_paths))
    settings = _load_phase1_settings(Path(args.phase1_settings))
    _assert_alloy_importable()
    size_metadata_by_image = _load_size_metadata(Path(args.size_metadata_csv))
    max_pairs = int(settings.get("max_pairs", 5))
    if args.max_pairs is not None:
        max_pairs = args.max_pairs
    require_bf_df_pairs = bool(settings.get("require_bf_df_pairs", True))
    if args.allow_unpaired:
        require_bf_df_pairs = False

    raw_enabled = bool(settings.get("use_transient_raw_images", False)) or args.raw_image_mode
    raw_cfg = RawImageConfig(
        enabled=raw_enabled,
        manifest_csv=Path(args.raw_manifest_csv),
        temp_dir=Path(args.raw_temp_dir),
        app_name=str(settings.get("raw_image_app_name", "GAJT_INLINE_24601")),
        technology=str(settings.get("raw_image_technology", "1278")),
        gajt_dll_search_paths=list(settings.get("gajt_dll_search_paths", DEFAULT_GAJT_DLL_SEARCH_PATHS)),
        strict=bool(settings.get("raw_image_strict", False)) or args.raw_strict,
        keep_temp=bool(settings.get("raw_keep_temp", False)) or args.raw_keep_temp,
    )

    cfg = _build_runtime_config(runtime_paths, settings)
    summary = run_batch(
        cfg,
        run_id=args.run_id,
        size_metadata_by_image=size_metadata_by_image,
        max_pairs=max_pairs,
        require_bf_df_pairs=require_bf_df_pairs,
        raw_cfg=raw_cfg,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
