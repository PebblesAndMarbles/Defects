"""
Batch defect analysis via the Alloy /api/vision endpoint.

Processes every image in INPUT_FOLDER through the vision model with a
JSON-schema `response_format`, so the model is constrained to return a
strict, parseable JSON object (not just JSON-looking prose). Results are
written to OUTPUT_FOLDER as one JSON file per image, plus a combined
results.jsonl log.

Designed to be run repeatedly (e.g. via cron every 60 minutes) as new
images land in INPUT_FOLDER — already-processed images (an output file
already exists) are skipped, so each run only analyzes new arrivals.

Usage:
    python vision_defect_batch.py
"""

import base64
import json
import logging
from datetime import datetime
from pathlib import Path

import requests
import urllib3

# ============================================================================
# Configuration — edit these as needed
# ============================================================================

API_BASE_URL = "https://alloy.intel.com"
API_KEY = "demo-sandbox-key-12345"
MODEL = "gpt-5.4-mini"

INPUT_FOLDER = Path("./inputs")
OUTPUT_FOLDER = Path("./outputs")

PROMPT = (
    "This is a scanning electron microscope (SEM) image of a semiconductor wafer "
    "surface showing patterned lines, taken for defect inspection. Identify any "
    "surface defects (particles, foreign material, scratches, bridging, or other "
    "anomalies) visible on or across the patterned lines. If no defect is present, "
    "report 0 defects."
)

DETAIL = "high"  # "auto" | "low" | "high"
REQUEST_TIMEOUT_SECONDS = 60

# Internal Intel CA chain isn't installed in every environment this script
# runs in — set to True (or a CA bundle path string) once that's sorted out.
VERIFY_SSL = False

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

# JSON schema the model's answer must conform to (strict mode).
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "number_of_defects": {
            "type": "integer",
            "description": "Count of distinct defects visible in the image. 0 if none are present.",
        },
        "description": {
            "type": "string",
            "description": "Brief description of what is observed, including any defect(s) found.",
        },
        "further_processing_needed": {
            "type": "boolean",
            "description": "True if additional image processing/analysis (e.g. segmentation) is needed to characterize the defect(s).",
        },
        "proposed_processing_tool": {
            "type": "string",
            "description": "Proposed downstream tool for further processing, e.g. 'watershed segmentation', 'CNN classifier', or 'none'.",
        },
    },
    "required": [
        "number_of_defects",
        "description",
        "further_processing_needed",
        "proposed_processing_tool",
    ],
    "additionalProperties": False,
}

# ============================================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

if VERIFY_SSL is False:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def analyze_image(image_path: Path) -> dict:
    """Call /api/vision with a JSON-schema response_format and return the parsed result."""
    img_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")

    payload = {
        "image_base64": img_b64,
        "prompt": PROMPT,
        "model": MODEL,
        "detail": DETAIL,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "defect_analysis",
                "schema": RESPONSE_SCHEMA,
                "strict": True,
            },
        },
    }

    resp = requests.post(
        f"{API_BASE_URL}/api/vision",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json=payload,
        verify=VERIFY_SSL,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    body = resp.json()
    return json.loads(body["description"])


def main():
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    images = sorted(p for p in INPUT_FOLDER.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    if not images:
        logger.info("No images found in %s", INPUT_FOLDER)
        return

    results_log = OUTPUT_FOLDER / "results.jsonl"
    processed = 0
    skipped = 0
    failed = 0

    for image_path in images:
        result_path = OUTPUT_FOLDER / f"{image_path.stem}.json"
        if result_path.exists():
            skipped += 1
            continue

        logger.info("Analyzing %s", image_path.name)
        try:
            analysis = analyze_image(image_path)
        except Exception as e:
            logger.error("Failed to analyze %s: %s", image_path.name, e)
            failed += 1
            continue

        record = {
            "image": image_path.name,
            "model": MODEL,
            "timestamp": datetime.now().isoformat(),
            **analysis,
        }

        result_path.write_text(json.dumps(record, indent=2))
        with results_log.open("a") as f:
            f.write(json.dumps(record) + "\n")

        processed += 1
        logger.info(
            "  -> defects=%s further_processing_needed=%s tool=%s",
            analysis.get("number_of_defects"),
            analysis.get("further_processing_needed"),
            analysis.get("proposed_processing_tool"),
        )

    logger.info("Done. processed=%d skipped=%d failed=%d", processed, skipped, failed)


if __name__ == "__main__":
    main()
