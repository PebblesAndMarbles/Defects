from __future__ import annotations

from pathlib import Path

from alloy.core.llm import chat, image


def main() -> int:
    img = sorted(Path("images/Alloy_Class/inputs").glob("*.jpg"))[0]

    image_default = image(
        str(img),
        prompt="Return JSON with key note",
        model="gpt-5.4-mini",
        max_completion_tokens=80,
    )
    print("image_default_type=" + type(image_default).__name__)

    image_usage = image(
        str(img),
        prompt="Return JSON with key note",
        model="gpt-5.4-mini",
        max_completion_tokens=80,
        include_usage=True,
    )
    print("image_usage_type=" + type(image_usage).__name__)
    if isinstance(image_usage, dict):
        print("image_usage_keys=" + ",".join(sorted(image_usage.keys())))
        print("image_usage_field_type=" + type(image_usage.get("usage")).__name__)

    chat_default = chat(
        "Say hello in 3 words.",
        model="gpt-5.4-mini",
        max_completion_tokens=40,
    )
    print("chat_default_type=" + type(chat_default).__name__)

    chat_usage = chat(
        "Say hello in 3 words.",
        model="gpt-5.4-mini",
        max_completion_tokens=40,
        include_usage=True,
    )
    print("chat_usage_type=" + type(chat_usage).__name__)
    if isinstance(chat_usage, dict):
        print("chat_usage_keys=" + ",".join(sorted(chat_usage.keys())))
        print("chat_usage_field_type=" + type(chat_usage.get("usage")).__name__)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
