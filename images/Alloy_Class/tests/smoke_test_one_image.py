"""
One-image Alloy vision smoke test.

Purpose:
- verify that the selected Python/Alloy environment can authenticate
- verify that one representative image can reach the vision endpoint
- capture a concise outcome for reporting back to collaborators
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="One-image Alloy auth smoke test")
    parser.add_argument("image_path", help="Path to one test image")
    parser.add_argument(
        "--prompt",
        default="Describe the visible defect morphology in this SEM image in 1-2 sentences.",
        help="Short smoke-test prompt",
    )
    parser.add_argument("--model", default="gpt-5.4", help="Model name")
    args = parser.parse_args()

    image_path = Path(args.image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")

    from alloy.core.llm import image

    result = image(
        str(image_path),
        prompt=args.prompt,
        model=args.model,
        max_completion_tokens=300,
    )

    print(json.dumps({
        "status": "ok",
        "image_path": str(image_path),
        "model": args.model,
        "result": result,
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
