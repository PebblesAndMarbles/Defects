"""
Phase 1 BE image classification prototype runner.

Goals:
- Stay UNC-native and avoid local machine path assumptions.
- Keep per-image processing resilient (one failure does not stop batch).
- Emit structured JSON suitable for comparison experiments.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
DOTENV_CANDIDATE_NAMES = (".env", ".env.context")

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
    return json.loads(config_path.read_text(encoding="utf-8"))


def _load_phase1_settings(settings_path: Path) -> dict[str, Any]:
    return json.loads(settings_path.read_text(encoding="utf-8"))


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


def _build_request_payload(image_path: Path, cfg: RuntimeConfig) -> dict[str, Any]:
    img_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return {
        "image_base64": img_b64,
        "prompt": cfg.prompt,
        "model": cfg.model,
        "detail": cfg.detail,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "be_phase1_classifier",
                "schema": DEFAULT_RESPONSE_SCHEMA,
                "strict": True,
            },
        },
    }


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
        max_completion_tokens=500,
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


def run_batch(cfg: RuntimeConfig, run_id: str, size_metadata_by_image: dict[str, dict[str, str]] | None = None) -> dict[str, int]:
    cfg.output_folder.mkdir(parents=True, exist_ok=True)
    images = _iter_images(cfg.input_folder)

    result_jsonl = cfg.output_folder / "phase1_results.jsonl"
    status_jsonl = cfg.output_folder / "phase1_status.jsonl"

    processed = 0
    failed = 0
    skipped = 0

    for image_path in images:
        image_key = _image_key(image_path)
        out_file = cfg.output_folder / f"{image_key}.json"

        if out_file.exists():
            skipped += 1
            continue

        base = _build_record_base(image_path, cfg, run_id)
        try:
            size_meta = (size_metadata_by_image or {}).get(image_path.name)
            parsed, raw_excerpt = _post_vision(image_path, cfg, size_metadata=size_meta)
            record = {
                **base,
                "status": "ok",
                **parsed,
                "raw_response_excerpt": raw_excerpt[:1000],
            }
            if size_meta:
                record["size_metadata"] = size_meta
            out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
            with result_jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            processed += 1
        except Exception as exc:
            err_record = {
                **base,
                "status": "error",
                "error_message": str(exc),
            }
            with status_jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(err_record) + "\n")
            failed += 1

    return {"processed": processed, "failed": failed, "skipped": skipped, "total_images": len(images)}


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
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _load_env_from_supported_locations()
    runtime_paths = _load_runtime_paths(Path(args.runtime_paths))
    settings = _load_phase1_settings(Path(args.phase1_settings))
    size_metadata_by_image = _load_size_metadata(Path(args.size_metadata_csv))

    cfg = _build_runtime_config(runtime_paths, settings)
    summary = run_batch(cfg, run_id=args.run_id, size_metadata_by_image=size_metadata_by_image)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
