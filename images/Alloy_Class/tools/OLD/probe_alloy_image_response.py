from __future__ import annotations

import json
from pathlib import Path

from alloy.core.llm import image


def main() -> int:
    images = sorted(Path("images/Alloy_Class/inputs").glob("*.jpg"))
    if not images:
        print("no_images_found")
        return 1

    result = image(
        str(images[0]),
        prompt="Return strict JSON with one field named note.",
        model="gpt-5.4-mini",
        max_completion_tokens=80,
    )

    print(type(result).__name__)
    if isinstance(result, dict):
        print(json.dumps(result, indent=2)[:3000])
    else:
        print(str(result)[:1000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
