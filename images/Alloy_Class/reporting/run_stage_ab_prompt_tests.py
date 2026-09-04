"""
Run Stage A and Stage B prompt tests on BF/DF image pairs with token metrics.

Token metrics behavior:
- If Alloy response includes native usage payload fields, they are recorded.
- If not present (current behavior in this runtime), a fallback estimate is used.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
DOTENV_CANDIDATE_NAMES = (".env", ".env.context")
DEFAULT_RAW_MANIFEST = (
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson"
    r"\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv"
)
DEFAULT_GAJT_DLL_SEARCH_PATHS = [
    r"D:\gajtv\configurations\wijt",
    r"C:\Users\tbatson\AppData\Roaming\SAS\JMP\AddIns\gajtv.intel.com\wijt",
]

# --- Describe-then-classify (v13) support -----------------------------------
# Promoted from tools/probe_describe_then_classify.py after Phase 3 validation
# passed 11/12 on the FN + particle-control set (see docs/v12_post_mortem.md).
# Call 1 is a neutral free-observation prompt (no Stage A context, no JSON
# contract). Call 2's evidence framework is derived at runtime from the actual
# V11 config (stageB_substrate_tier1_v10), NOT V12 -- per external review, V11
# had zero FP rate and V12's added guidance blocks caused an evidence-agreement
# regression (BMK_0018). Only the Stage-A-context sentence is stripped from
# V11's text and replaced with a reference to Call 1's observation.
V11_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "stage_ab_prompt_tests_substrate_tier1_v11.json"

CALL1_OBSERVATION_PROMPT = (
    "You are looking at a BEOL SEM defect image pair (brightfield + darkfield) of the same site. "
    "Describe what you see at the defect-comparator/trench junction zone in these images. Focus on: "
    "the defect's position relative to trench or comparator walls; any geometric irregularities "
    "(asymmetry, shortened or narrowed extent, tonal differences) in the nearest comparator or trench "
    "relative to other similar structures elsewhere in the field; and any material visible inside "
    "features that should otherwise be clear. Do not classify the defect as particle or BEEP. Do not "
    "use structured output or JSON. Describe only what is visually present, in 3-5 sentences."
)

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


def _build_describe_then_classify_call2_prompt(observation: str) -> str:
    base = _load_v11_stage_b_prompt()
    if _STAGE_A_CONTEXT_SENTENCE not in base:
        raise RuntimeError(
            "V11 stage_b prompt text no longer matches the expected Stage A context "
            "sentence -- update _STAGE_A_CONTEXT_SENTENCE to match "
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
            "sentence -- update _CLASSIFIER_INTRO to match "
            "config/stage_ab_prompt_tests_substrate_tier1_v11.json before proceeding."
        )
    return base.replace(_CLASSIFIER_INTRO, _CLASSIFIER_INTRO + observation_block, 1)


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
    for env_file in _find_upward_env_files(Path.cwd()):
        _parse_env_file(env_file)


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


def _build_pairs(images: list[Path]) -> list[tuple[str, Path, Path]]:
    grouped: dict[str, dict[str, Path]] = {}
    for image_path in images:
        key, role = _pair_key_and_role(image_path.name)
        if role is None:
            continue
        grouped.setdefault(key, {})[role] = image_path

    out: list[tuple[str, Path, Path]] = []
    for key in sorted(grouped):
        roles = grouped[key]
        bf = roles.get("brightfield")
        df = roles.get("darkfield")
        if bf and df:
            out.append((key, bf, df))
    return out


def _load_image_manifest_index(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists() or not path.is_file():
        return {}

    import csv

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
    temp_dir: Path,
    app_name: str,
    technology: str,
    gajt_dll_search_paths: list[str],
) -> tuple[Path | None, dict[str, str]]:
    image_spec = (manifest_row.get("IMAGE_FILESPEC", "") or "").strip()
    query_site = (manifest_row.get("QUERY_SITE", "") or manifest_row.get("SITE", "") or "").strip()
    if not image_spec or not query_site:
        return None, {"raw_download_status": "missing_manifest_fields"}

    try:
        secure_ftp = _load_secureftp_runtime(gajt_dll_search_paths)
    except Exception as exc:
        return None, {"raw_download_status": f"secureftp_unavailable: {exc}"}

    temp_dir.mkdir(parents=True, exist_ok=True)
    staging_root = temp_dir / "staging"
    staging_root.mkdir(parents=True, exist_ok=True)

    ds = f"{query_site}_PROD_YAS_{technology}_FTP"
    try:
        secure_ftp.FtpFiles(query_site, ds, image_spec, str(staging_root), app_name)
    except Exception as exc:
        return None, {"raw_download_status": f"ftp_error: {exc}", "raw_image_spec": image_spec}

    staged_path = staging_root / image_spec.lstrip("/\\").replace("/", os.sep)
    if not staged_path.exists() or not staged_path.is_file():
        return None, {"raw_download_status": "staged_file_missing", "raw_image_spec": image_spec}

    ext = staged_path.suffix.lower() or ".jpg"
    temp_name = f"raw_{uuid4().hex}{ext}"
    temp_file = temp_dir / temp_name
    shutil.copy2(staged_path, temp_file)

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


def _extract_json_payload(result: Any) -> tuple[dict[str, Any], str, dict[str, Any]]:
    # Returns (parsed_content, output_text, native_payload). native_payload is the
    # original full response dict, kept separately so sibling fields (usage,
    # finish_reason, model, id) survive even when the primary content field is a
    # plain string -- previously those sibling fields were silently discarded.
    if isinstance(result, dict):
        native_payload = result

        # Preferred content fields if runtime starts returning rich payloads.
        for field in ("description", "content", "output_json", "json", "result"):
            candidate = native_payload.get(field)
            if isinstance(candidate, dict):
                return candidate, json.dumps(candidate), native_payload
            if isinstance(candidate, str):
                text = candidate.strip()
                if text.startswith("{") and text.endswith("}"):
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict):
                            return parsed, candidate, native_payload
                    except json.JSONDecodeError:
                        pass
                return {"raw_text": candidate}, candidate, native_payload

        return native_payload, json.dumps(native_payload), native_payload

    if isinstance(result, str):
        text = result.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed, result, {}
            except json.JSONDecodeError:
                pass
        return {"raw_text": result}, result, {}

    as_text = str(result)
    return {"raw_text": as_text}, as_text, {}


def _extract_usage(native_payload: dict[str, Any]) -> dict[str, Any]:
    usage = native_payload.get("usage")
    if isinstance(usage, dict):
        return {
            "source": "native_usage",
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }

    return {
        "source": "estimated",
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }


def _estimate_tokens(prompt: str, output_text: str) -> dict[str, int]:
    # Practical fallback: approximately 4 characters per token for mixed technical English.
    prompt_tokens = max(1, int(len(prompt) / 4))
    completion_tokens = max(1, int(len(output_text) / 4))
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _classify_error_string(text: Any) -> str | None:
    # Best-effort classification of alloy._make_request()'s stringified error paths;
    # the installed alloy package never exposes a literal HTTP status code, so this
    # is the closest available signal to distinguish content-filter/http/timeout cases.
    if not isinstance(text, str):
        return None
    if text.startswith("Content Filter:"):
        return "content_filter"
    if text.startswith("Error: HTTP"):
        return "http_error"
    if any(marker in text for marker in ("Request timed out", "Connection failed", "Server unavailable", "Maximum retries exceeded")):
        return "network_or_timeout"
    if text.startswith("Error:"):
        return "unknown_error"
    return None


def _build_call_diagnostics(
    result: Any,
    output_text: str,
    native_payload: dict[str, Any],
    usage_source: str,
) -> dict[str, Any]:
    error_class = _classify_error_string(result) if isinstance(result, str) else None
    stripped = output_text.strip() if isinstance(output_text, str) else ""
    finish_reason = native_payload.get("finish_reason") or native_payload.get("stop_reason")
    return {
        "usage_source": usage_source,
        "error_class": error_class,
        "empty_response": bool(error_class is None and not stripped),
        "response_char_count": len(output_text) if isinstance(output_text, str) else 0,
        "finish_reason": finish_reason,
    }


def _image_payload_size_diagnostics(image_paths: list[Path], encoded_images: list[str]) -> list[dict[str, Any]]:
    # base64 expands bytes by ~1.37x; a ratio far from that suggests the image was
    # transformed (resized/recompressed) before or during encoding.
    diagnostics: list[dict[str, Any]] = []
    for image_path, encoded in zip(image_paths, encoded_images):
        source_bytes = image_path.stat().st_size
        base64_chars = len(encoded)
        ratio = (base64_chars / source_bytes) if source_bytes else None
        diagnostics.append({
            "image_path": str(image_path),
            "source_bytes": source_bytes,
            "base64_chars": base64_chars,
            "encode_ratio": round(ratio, 4) if ratio is not None else None,
        })
    return diagnostics


def _parse_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _norm_label(value: Any) -> str:
    return str(value or "").strip().lower()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _build_prompt_notes(
    raw_image_mode: bool,
    raw_strict: bool,
    raw_stage_a_only: bool,
    stage_a_brightfield_only: bool,
    stage_b_multi_image: bool,
) -> list[str]:
    notes: list[str] = []
    if stage_a_brightfield_only:
        notes.append("Stage A runs on brightfield only; darkfield reuses the brightfield Stage A result.")
    else:
        notes.append("Stage A runs independently on both brightfield and darkfield images.")

    if stage_b_multi_image:
        notes.append("Stage B submits the brightfield and darkfield pair together as a multi-image request.")
    else:
        notes.append("Stage B submits a single image per request.")

    if raw_image_mode:
        if raw_strict:
            notes.append("Raw image mode is fail-closed: the run aborts if a transient raw download cannot be resolved.")
        else:
            notes.append("Raw image mode allows fallback to the staged image when a transient raw download cannot be resolved.")
        if raw_stage_a_only:
            notes.append("Raw images are used for Stage A only; Stage B uses the staged image path.")
        else:
            notes.append("Raw images are used for both Stage A and Stage B whenever a transient raw download succeeds.")
    else:
        notes.append("Raw image mode is disabled for this run.")

    return notes


def build_prompt_bundle(
    *,
    config_path: Path,
    input_folder: Path,
    output_folder: Path,
    run_root: Path,
    run_id: str,
    cfg: dict[str, Any],
    models: list[str],
    max_completion_tokens: int,
    max_pairs: int,
    raw_image_mode: bool,
    raw_manifest_csv: Path,
    raw_temp_dir: Path,
    raw_app_name: str,
    raw_technology: str,
    raw_strict: bool,
    raw_keep_temp: bool,
    raw_stage_a_only: bool,
    stage_a_brightfield_only: bool,
    stage_b_multi_image: bool,
) -> dict[str, Any]:
    stage_a = cfg.get("stage_a") or {}
    stage_b = cfg.get("stage_b") or {}
    return {
        "run_id": run_id,
        "created_at_utc": _utc_now(),
        "config_path": str(config_path.resolve()),
        "config_name": config_path.name,
        "suite_name": cfg.get("suite_name", "stage_ab"),
        "model_name": models[0] if models else "",
        "model_names": list(models),
        "stage_a_prompt_version": stage_a.get("prompt_version", "stageA"),
        "stage_b_prompt_version": stage_b.get("prompt_version", "stageB"),
        "stage_a_prompt": stage_a.get("prompt", ""),
        "stage_b_prompt": stage_b.get("prompt", ""),
        "stage_a": {
            "prompt_version": stage_a.get("prompt_version", "stageA"),
            "prompt": stage_a.get("prompt", ""),
        },
        "stage_b": {
            "prompt_version": stage_b.get("prompt_version", "stageB"),
            "prompt": stage_b.get("prompt", ""),
        },
        "execution_flags": {
            "raw_image_mode": bool(raw_image_mode),
            "raw_strict": bool(raw_strict),
            "raw_stage_a_only": bool(raw_stage_a_only),
            "raw_keep_temp": bool(raw_keep_temp),
            "stage_a_brightfield_only": bool(stage_a_brightfield_only),
            "stage_b_multi_image": bool(stage_b_multi_image),
        },
        "paths": {
            "run_root": str(run_root.resolve()),
            "input_folder": str(input_folder.resolve()),
            "output_folder": str(output_folder.resolve()),
            "run_manifest_path": str((run_root / "run_manifest.json").resolve()),
            "prompt_bundle_path": str((run_root / "prompt_bundle.json").resolve()),
            "prompt_bundle_txt_path": str((run_root / "prompt_bundle.txt").resolve()),
        },
        "notes": _build_prompt_notes(
            raw_image_mode=raw_image_mode,
            raw_strict=raw_strict,
            raw_stage_a_only=raw_stage_a_only,
            stage_a_brightfield_only=stage_a_brightfield_only,
            stage_b_multi_image=stage_b_multi_image,
        ),
        "max_completion_tokens": max_completion_tokens,
        "max_pairs": max_pairs,
        "raw_manifest_csv": str(raw_manifest_csv.resolve()),
        "raw_temp_dir": str(raw_temp_dir.resolve()),
        "raw_app_name": raw_app_name,
        "raw_technology": raw_technology,
        "stage_b_rendering": {
            "description": "Stage B prompt is augmented per row with Stage A BF context and, when enabled, a multi-image instruction.",
            "uses_stage_a_context_per_row": True,
            "uses_multi_image_suffix": bool(stage_b_multi_image),
        },
    }


def write_prompt_bundle(bundle: dict[str, Any], bundle_path: Path) -> tuple[Path, Path]:
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_text_path = bundle_path.with_suffix(".txt")
    bundle_json = json.dumps(bundle, indent=2)
    bundle_path.write_text(bundle_json + "\n", encoding="utf-8")
    bundle_text_path.write_text("Prompt bundle provenance\n\n" + bundle_json + "\n", encoding="utf-8")
    return bundle_path, bundle_text_path


def _call_image(
    path: Path | list[Path],
    prompt: str,
    model: str,
    max_completion_tokens: int,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    image_payload_diagnostics: list[dict[str, Any]] | None = None
    if isinstance(path, list):
        import base64

        from alloy.core.config import config as alloy_config
        from alloy.core.llm.core import _make_request

        encoded_images = [base64.b64encode(image_path.read_bytes()).decode("ascii") for image_path in path]
        image_payload_diagnostics = _image_payload_size_diagnostics(path, encoded_images)
        payload: dict[str, Any] = {
            "images": encoded_images,
            "prompt": prompt,
            "model": model,
            "type": "azure",
            "max_completion_tokens": max_completion_tokens,
        }
        result = _make_request(alloy_config.vision_url, payload, max_retries=3, context="vision")
    else:
        from alloy.core.llm import image

        call_kwargs: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "max_completion_tokens": max_completion_tokens,
        }

        # Forward compatibility: use include_usage when runtime supports it.
        try:
            sig = inspect.signature(image)
            if "include_usage" in sig.parameters:
                call_kwargs["include_usage"] = True
        except (TypeError, ValueError):
            pass

        try:
            result = image(str(path), **call_kwargs)
        except TypeError:
            # Fallback for runtimes that reject additional kwargs.
            call_kwargs.pop("include_usage", None)
            result = image(str(path), **call_kwargs)

    parsed, output_text, native_payload = _extract_json_payload(result)
    usage = _extract_usage(native_payload)
    if usage["source"] == "estimated":
        est = _estimate_tokens(prompt, output_text)
        usage.update(est)
    usage.update(_build_call_diagnostics(result, output_text, native_payload, usage["source"]))
    if image_payload_diagnostics is not None:
        usage["image_payload_diagnostics"] = image_payload_diagnostics
    return parsed, output_text, usage


def run_suite(
    config_path: Path,
    input_folder: Path,
    output_folder: Path,
    run_root: Path | None,
    run_id: str,
    raw_image_mode: bool,
    raw_manifest_csv: Path,
    raw_temp_dir: Path,
    raw_app_name: str,
    raw_technology: str,
    raw_gajt_dll_search_paths: list[str],
    raw_strict: bool,
    raw_keep_temp: bool,
    raw_stage_a_only: bool,
    stage_a_brightfield_only: bool,
    stage_b_multi_image: bool,
    stage_b_describe_then_classify: bool,
    pair_keys: list[str] | None,
) -> dict[str, Any]:
    cfg = json.loads(config_path.read_text(encoding="utf-8-sig"))
    models = cfg.get("models") or ["gpt-5.4-mini"]
    max_completion_tokens = int(cfg.get("max_completion_tokens", 550))
    max_pairs = int(cfg.get("max_pairs", 5))
    run_root = run_root or output_folder

    stage_a = cfg["stage_a"]
    stage_b = cfg["stage_b"]

    pairs = _build_pairs(_iter_images(input_folder))
    if pair_keys:
        wanted = {key.strip() for key in pair_keys if key.strip()}
        pairs = [pair for pair in pairs if pair[0] in wanted]
    if max_pairs > 0:
        pairs = pairs[:max_pairs]

    output_folder.mkdir(parents=True, exist_ok=True)
    results_jsonl = output_folder / "stage_ab_results.jsonl"
    prompt_bundle = build_prompt_bundle(
        config_path=config_path,
        input_folder=input_folder,
        output_folder=output_folder,
        run_root=run_root,
        run_id=run_id,
        cfg=cfg,
        models=models,
        max_completion_tokens=max_completion_tokens,
        max_pairs=max_pairs,
        raw_image_mode=raw_image_mode,
        raw_manifest_csv=raw_manifest_csv,
        raw_temp_dir=raw_temp_dir,
        raw_app_name=raw_app_name,
        raw_technology=raw_technology,
        raw_strict=raw_strict,
        raw_keep_temp=raw_keep_temp,
        raw_stage_a_only=raw_stage_a_only,
        stage_a_brightfield_only=stage_a_brightfield_only,
        stage_b_multi_image=stage_b_multi_image,
    )
    prompt_bundle_path, prompt_bundle_txt_path = write_prompt_bundle(prompt_bundle, run_root / "prompt_bundle.json")

    summary = {
        "run_id": run_id,
        "timestamp_utc": _utc_now(),
        "suite_name": cfg.get("suite_name", "stage_ab"),
        "models": models,
        "pairs_tested": len(pairs),
        "rows": 0,
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "native_usage_rows": 0,
            "estimated_usage_rows": 0,
        },
        "quality": {
            "stage_a_avg_confidence": None,
            "stage_b_avg_confidence": None,
            "stage_b_review_rate": None,
            "stage_b_possible_beep_rate": None,
            "stage_a_stage_b_conflict_rate": None,
        },
        "raw_mode": {
            "enabled": bool(raw_image_mode),
            "strict": bool(raw_strict),
            "stage_a_only": bool(raw_stage_a_only),
            "rows_used_transient_raw_stage_a": 0,
            "rows_used_transient_raw_stage_b": 0,
            "raw_download_failures": 0,
        },
        "submission_mode": {
            "stage_b_multi_image": bool(stage_b_multi_image),
            "stage_b_describe_then_classify": bool(stage_b_describe_then_classify),
        },
        "prompt_bundle_path": str(prompt_bundle_path.resolve()),
        "prompt_bundle_txt_path": str(prompt_bundle_txt_path.resolve()),
    }

    stage_a_conf: list[float] = []
    stage_b_conf: list[float] = []
    stage_b_review_true = 0
    stage_b_possible_beep = 0
    cross_stage_conflicts = 0

    manifest_index: dict[str, dict[str, str]] = {}
    if raw_image_mode:
        manifest_index = _load_image_manifest_index(raw_manifest_csv)

    n_pairs = len(pairs)
    for model in models:
        for pair_idx, (pair_key, bf, df) in enumerate(pairs, 1):
            print(f"[{pair_idx}/{n_pairs}] pair={pair_key}", flush=True)
            pair_stage_a: dict[str, tuple[dict[str, Any], str, dict[str, Any], Path, Path, dict[str, str]]] = {}
            for role, image_path in (("brightfield", bf), ("darkfield", df)):
                if stage_a_brightfield_only and role == "darkfield":
                    pair_stage_a[role] = pair_stage_a["brightfield"]
                    continue

                infer_stage_a = image_path
                infer_stage_b = image_path
                raw_info: dict[str, str] = {}
                raw_temp_path: Path | None = None

                if raw_image_mode:
                    manifest_row = manifest_index.get(image_path.name.lower())
                    if manifest_row:
                        raw_temp_path, raw_info = _download_raw_image_to_temp(
                            manifest_row=manifest_row,
                            temp_dir=raw_temp_dir,
                            app_name=raw_app_name,
                            technology=raw_technology,
                            gajt_dll_search_paths=raw_gajt_dll_search_paths,
                        )
                        if raw_temp_path:
                            infer_stage_a = raw_temp_path
                            infer_stage_b = raw_temp_path
                        else:
                            summary["raw_mode"]["raw_download_failures"] += 1
                    else:
                        raw_info = {"raw_download_status": "manifest_row_not_found"}
                        summary["raw_mode"]["raw_download_failures"] += 1

                    if raw_strict and infer_stage_a == image_path:
                        raise RuntimeError(raw_info.get("raw_download_status", "raw_download_failed"))

                    if raw_stage_a_only:
                        infer_stage_b = image_path

                print(f"  {role}: Stage A ...", end=" ", flush=True)
                a_parsed, a_text, a_usage = _call_image(
                    path=infer_stage_a,
                    prompt=stage_a["prompt"],
                    model=model,
                    max_completion_tokens=max_completion_tokens,
                )
                _a_conf = a_parsed.get("context_confidence", "?") if isinstance(a_parsed, dict) else "?"
                _a_orient = a_parsed.get("dominant_orientation", "?") if isinstance(a_parsed, dict) else "?"
                print(f"orient={_a_orient} conf={_a_conf}", flush=True)

                pair_stage_a[role] = (a_parsed, a_text, a_usage, infer_stage_a, infer_stage_b, raw_info)

            bf_a_parsed, bf_a_text, bf_a_usage, bf_infer_stage_a, bf_infer_stage_b, bf_raw_info = pair_stage_a["brightfield"]
            df_a_parsed, df_a_text, df_a_usage, df_infer_stage_a, df_infer_stage_b, df_raw_info = pair_stage_a["darkfield"]

            stage_b_augmented_prompt = stage_b["prompt"]
            if bf_a_parsed and isinstance(bf_a_parsed, dict):
                bf_stage_a_context = json.dumps(bf_a_parsed, indent=2)
                stage_b_augmented_prompt = (
                    f"Stage A brightfield substrate analysis results:\n{bf_stage_a_context}\n\n"
                    f"Now, using the above brightfield substrate context and the paired darkfield image, {stage_b['prompt']}"
                )

            stage_b_input: Path | list[Path]
            stage_b_raw_info: dict[str, str] = {}
            if stage_b_multi_image:
                stage_b_input = [bf_infer_stage_b, df_infer_stage_b]
                stage_b_augmented_prompt = (
                    f"{stage_b_augmented_prompt}\n\n"
                    f"You are seeing a brightfield image and a darkfield image together in this request. "
                    f"Compare them jointly and mention any cross-image consistency in the rationale."
                )
            else:
                stage_b_input = bf_infer_stage_b

            print("  Stage B ...", end=" ", flush=True)
            call1_text: str | None = None
            call1_usage: dict[str, Any] | None = None
            if stage_b_describe_then_classify:
                _call1_parsed, call1_text, call1_usage = _call_image(
                    path=stage_b_input,
                    prompt=CALL1_OBSERVATION_PROMPT,
                    model=model,
                    max_completion_tokens=max_completion_tokens,
                )
                call2_prompt = _build_describe_then_classify_call2_prompt(call1_text)
                b_parsed, b_text, b_usage = _call_image(
                    path=stage_b_input,
                    prompt=call2_prompt,
                    model=model,
                    max_completion_tokens=max_completion_tokens,
                )
            else:
                b_parsed, b_text, b_usage = _call_image(
                    path=stage_b_input,
                    prompt=stage_b_augmented_prompt,
                    model=model,
                    max_completion_tokens=max_completion_tokens,
                )
            _b_class = b_parsed.get("defect_coarse_class", "?") if isinstance(b_parsed, dict) else "?"
            _b_evi   = b_parsed.get("blocked_etch_evidence", "?") if isinstance(b_parsed, dict) else "?"
            _b_rr    = b_parsed.get("review_required", "?") if isinstance(b_parsed, dict) else "?"
            print(f"class={_b_class} evi={_b_evi} rr={_b_rr}", flush=True)

            used_raw_a_bf = int(bf_infer_stage_a != bf)
            used_raw_b_bf = int(bf_infer_stage_b != bf)
            used_raw_a_df = int(df_infer_stage_a != df)
            used_raw_b_df = int(df_infer_stage_b != df)
            summary["raw_mode"]["rows_used_transient_raw_stage_a"] += used_raw_a_bf + used_raw_a_df
            summary["raw_mode"]["rows_used_transient_raw_stage_b"] += used_raw_b_bf + used_raw_b_df

            stage_b_input_paths = [str(path.resolve()) for path in (stage_b_input if isinstance(stage_b_input, list) else [stage_b_input])]

            for role, image_path in (("brightfield", bf), ("darkfield", df)):
                a_parsed, a_text, a_usage, infer_stage_a, infer_stage_b, raw_info = pair_stage_a[role]
                used_raw_a = int(infer_stage_a != image_path)
                used_raw_b = int(infer_stage_b != image_path)

                rec = {
                    "run_id": run_id,
                    "timestamp_utc": _utc_now(),
                    "pair_key": pair_key,
                    "image_name": image_path.name,
                    "pair_role": role,
                    "model_name": model,
                    "stage_a_prompt_version": stage_a.get("prompt_version", "stageA"),
                    "stage_b_prompt_version": stage_b.get("prompt_version", "stageB"),
                    "stage_a": a_parsed,
                    "stage_b": b_parsed,
                    "stage_a_raw_excerpt": a_text[:1000],
                    "stage_b_raw_excerpt": b_text[:1000],
                    "stage_a_usage": a_usage,
                    "stage_b_usage": b_usage,
                    "stage_b_input_paths": stage_b_input_paths,
                    "burned_image_path": str(image_path.resolve()),
                    "inference_image_path_stage_a": str(infer_stage_a.resolve()),
                    "inference_image_path_stage_b": str(infer_stage_b.resolve()),
                    "used_transient_raw_stage_a": used_raw_a,
                    "used_transient_raw_stage_b": used_raw_b,
                }
                if stage_b_describe_then_classify:
                    rec["stage_b_describe_then_classify"] = True
                    rec["stage_b_call1_observation"] = call1_text
                    rec["stage_b_call1_usage"] = call1_usage
                if raw_image_mode:
                    rec.update(raw_info)
                    if role == "brightfield":
                        rec["pair_stage_b_raw_info"] = dict(bf_raw_info)
                        rec["pair_stage_b_raw_info_darkfield"] = dict(df_raw_info)

                with results_jsonl.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec) + "\n")

                if raw_image_mode and raw_temp_path and raw_temp_path.exists() and not raw_keep_temp:
                    try:
                        raw_temp_path.unlink()
                    except OSError:
                        pass

                summary["rows"] += 1
                for usage in (a_usage, b_usage, call1_usage):
                    if usage is None:
                        continue
                    if usage.get("source") == "native_usage":
                        summary["usage"]["native_usage_rows"] += 1
                    else:
                        summary["usage"]["estimated_usage_rows"] += 1
                summary["usage"]["prompt_tokens"] += int(a_usage.get("prompt_tokens") or 0)
                summary["usage"]["prompt_tokens"] += int(b_usage.get("prompt_tokens") or 0)
                summary["usage"]["completion_tokens"] += int(a_usage.get("completion_tokens") or 0)
                summary["usage"]["completion_tokens"] += int(b_usage.get("completion_tokens") or 0)
                summary["usage"]["total_tokens"] += int(a_usage.get("total_tokens") or 0)
                summary["usage"]["total_tokens"] += int(b_usage.get("total_tokens") or 0)
                if call1_usage is not None:
                    summary["usage"]["prompt_tokens"] += int(call1_usage.get("prompt_tokens") or 0)
                    summary["usage"]["completion_tokens"] += int(call1_usage.get("completion_tokens") or 0)
                    summary["usage"]["total_tokens"] += int(call1_usage.get("total_tokens") or 0)

                a_conf = None
                if isinstance(a_parsed, dict):
                    a_conf = _parse_float(a_parsed.get("confidence"))
                    if a_conf is None:
                        a_conf = _parse_float(a_parsed.get("context_confidence"))
                b_conf = _parse_float(b_parsed.get("confidence")) if isinstance(b_parsed, dict) else None
                if a_conf is not None:
                    stage_a_conf.append(a_conf)
                if b_conf is not None:
                    stage_b_conf.append(b_conf)

                b_review = _as_bool(b_parsed.get("review_required")) if isinstance(b_parsed, dict) else False
                if b_review:
                    stage_b_review_true += 1

                b_cls = _norm_label(b_parsed.get("defect_coarse_class")) if isinstance(b_parsed, dict) else ""
                if b_cls == "possible_beep":
                    stage_b_possible_beep += 1

                blocked = _norm_label(b_parsed.get("blocked_etch_evidence")) if isinstance(b_parsed, dict) else ""
                substrate = _norm_label(a_parsed.get("coarse_substrate_regime")) if isinstance(a_parsed, dict) else ""
                if blocked in {"moderate", "strong"} and substrate in {"", "unknown", "indeterminate"}:
                    cross_stage_conflicts += 1

    row_count = summary["rows"] if summary["rows"] else 1
    summary["quality"]["stage_a_avg_confidence"] = (sum(stage_a_conf) / len(stage_a_conf)) if stage_a_conf else None
    summary["quality"]["stage_b_avg_confidence"] = (sum(stage_b_conf) / len(stage_b_conf)) if stage_b_conf else None
    summary["quality"]["stage_b_review_rate"] = stage_b_review_true / row_count
    summary["quality"]["stage_b_possible_beep_rate"] = stage_b_possible_beep / row_count
    summary["quality"]["stage_a_stage_b_conflict_rate"] = cross_stage_conflicts / row_count

    summary_path = output_folder / "stage_ab_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage A/B prompt tests with token metrics")
    parser.add_argument("--config", default="config/stage_ab_prompt_tests.json", help="Path to Stage A/B test config JSON")
    parser.add_argument("--input-folder", default="inputs", help="Input image folder")
    parser.add_argument("--output-folder", default="outputs/stage_ab_tests", help="Output folder")
    parser.add_argument("--run-root-folder", default=None, help="Root folder for run-level provenance artifacts")
    parser.add_argument("--raw-image-mode", action="store_true", help="Use transient raw images for VLM inference.")
    parser.add_argument("--raw-manifest-csv", default=DEFAULT_RAW_MANIFEST, help="Manifest CSV used to map burned image names to raw IMAGE_FILESPEC.")
    parser.add_argument("--raw-temp-dir", default="./outputs/stage_ab_raw_temp", help="Temporary raw image directory.")
    parser.add_argument("--raw-app-name", default="GAJT_INLINE_24601", help="SecureFTP app name for raw download.")
    parser.add_argument("--raw-technology", default="1278", help="Technology token for datasource naming.")
    parser.add_argument("--raw-gajt-dll-search-path", action="append", dest="raw_gajt_dll_search_paths", help="Additional GAJT DLL search path. Can be repeated.")
    parser.add_argument("--raw-strict", action="store_true", help="Fail run when transient raw image cannot be resolved for a row.")
    parser.add_argument("--raw-keep-temp", action="store_true", help="Keep downloaded transient raw files.")
    parser.add_argument("--raw-stage-a-only", action="store_true", help="Use raw images for Stage A only; Stage B uses staged/burned input image.")
    parser.add_argument("--stage-a-brightfield-only", action="store_true", help="Run Stage A only on brightfield while still running Stage B for both BF and DF.")
    parser.add_argument("--stage-b-multi-image", action="store_true", help="Submit Stage B with a BF+DF image list instead of a single image.")
    parser.add_argument("--stage-b-describe-then-classify", action="store_true", help="Use the v13 two-call Stage B (Call 1 free observation -> Call 2 classify from observation, drafted from V11) instead of the single-call Stage A-context-augmented prompt.")
    parser.add_argument("--pair-key", action="append", dest="pair_keys", help="Limit the run to one or more specific pair keys. Can be repeated.")
    parser.add_argument(
        "--run-id",
        default=f"stage_ab_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        help="Run identifier",
    )
    return parser.parse_args()


def main() -> int:
    _load_env_from_supported_locations()
    args = _parse_args()
    gajt_paths = args.raw_gajt_dll_search_paths or DEFAULT_GAJT_DLL_SEARCH_PATHS
    summary = run_suite(
        config_path=Path(args.config),
        input_folder=Path(args.input_folder),
        output_folder=Path(args.output_folder),
        run_root=Path(args.run_root_folder) if args.run_root_folder else None,
        run_id=args.run_id,
        raw_image_mode=args.raw_image_mode,
        raw_manifest_csv=Path(args.raw_manifest_csv),
        raw_temp_dir=Path(args.raw_temp_dir),
        raw_app_name=args.raw_app_name,
        raw_technology=args.raw_technology,
        raw_gajt_dll_search_paths=list(gajt_paths),
        raw_strict=args.raw_strict,
        raw_keep_temp=args.raw_keep_temp,
        raw_stage_a_only=args.raw_stage_a_only,
        stage_a_brightfield_only=args.stage_a_brightfield_only,
        stage_b_multi_image=args.stage_b_multi_image,
        stage_b_describe_then_classify=args.stage_b_describe_then_classify,
        pair_keys=args.pair_keys,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
