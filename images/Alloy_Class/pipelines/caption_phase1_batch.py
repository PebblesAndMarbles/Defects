"""
Rob-style Phase 1 captioning runner adapted from the notebook example.

This keeps the output intentionally descriptive so you can evaluate whether
freeform captions surface useful fine-bin separation cues before locking into a
 stricter taxonomy.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
DOTENV_CANDIDATE_NAMES = (".env", ".env.context")

DEFAULT_PROMPT = (
    "You are an expert SEM image captioner. Your job is to describe images so they "
    "can later be separated into meaningful fine-bin defect categories. Focus on "
    "morphology, apparent size, orientation, relative location, interactions with "
    "patterned lines, and whether the visible object appears isolated or part of a "
    "larger pattern. If uncertainty remains, say so explicitly."
)


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


def _image_key(path: Path) -> str:
    canon = str(path.resolve()).lower()
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _iter_images(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)


def _post_caption(
    image_path: Path,
    model: str,
    prompt: str,
    timeout_seconds: int,
    max_completion_tokens: int,
) -> str:
    from alloy.core.llm import image

    result = image(
        str(image_path),
        prompt=prompt,
        model=model,
        max_completion_tokens=max_completion_tokens,
    )
    if not isinstance(result, str):
        return json.dumps(result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rob-style Phase 1 captioning batch runner")
    parser.add_argument("--input-folder", default="inputs", help="Input image folder")
    parser.add_argument("--output-folder", default="outputs/captions", help="Caption output folder")
    parser.add_argument("--model", default="gpt-5.4", help="Model name")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Caption prompt")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="Request timeout")
    parser.add_argument("--max-completion-tokens", type=int, default=500, help="Max completion tokens")
    parser.add_argument("--run-id", default=f"caption_{datetime.now().strftime('%Y%m%d_%H%M%S')}", help="Run identifier")
    return parser.parse_args()


def main() -> int:
    _load_env_from_supported_locations()
    args = _parse_args()

    input_folder = Path(args.input_folder)
    output_folder = Path(args.output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    batch_jsonl = output_folder / "caption_results.jsonl"
    error_jsonl = output_folder / "caption_status.jsonl"

    for image_path in _iter_images(input_folder):
        image_key = _image_key(image_path)
        out_file = output_folder / f"{image_key}.json"
        if out_file.exists():
            continue

        base = {
            "run_id": args.run_id,
            "timestamp_utc": _utc_now(),
            "image_key": image_key,
            "image_path": str(image_path.resolve()),
            "image_name": image_path.name,
            "model_name": args.model,
            "prompt_style": "rob_captioning",
        }

        try:
            row_t0 = time.perf_counter()
            caption = _post_caption(
                image_path=image_path,
                model=args.model,
                prompt=args.prompt,
                timeout_seconds=args.timeout_seconds,
                max_completion_tokens=args.max_completion_tokens,
            )
            row_total_seconds = time.perf_counter() - row_t0
            record = {
                **base,
                "status": "ok",
                "caption": caption,
                "raw_response_excerpt": caption[:1000],
                "timing_seconds": {
                    "row_total": round(row_total_seconds, 3),
                },
            }
            out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
            with batch_jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as exc:
            err_record = {**base, "status": "error", "error_message": str(exc)}
            with error_jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(err_record) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
